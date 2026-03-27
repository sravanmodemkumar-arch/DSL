"""Audio-video synchronization — builds the master timeline from JSON + audio segments.

Uses lookup-based segment matching (not iterator) to prevent sync drift.
Accumulation-based state model keeps persistent elements visible.
"""


def build_timeline(question_data, audio_segments, buffer_ms=300):
    """Build a master timeline mapping each render instruction to audio timestamps.

    Uses a (scene_index, step_index) lookup to match audio segments to render
    instructions, preventing sync drift when non-audio scenes exist.
    """
    timeline = []
    buffer_s = buffer_ms / 1000.0

    # Build lookup: (scene_idx, step_idx) -> audio segment with timing
    seg_lookup = {}
    for seg in audio_segments:
        key = (seg.get("scene_index"), seg.get("step_index"))
        seg_lookup[key] = seg

    last_end = 0.0

    for scene_idx, scene in enumerate(question_data.get("scenes", [])):
        scene_type = scene.get("type", "")

        # --- Scene with direct audio + render ---
        if scene.get("audio") and scene.get("render"):
            seg = seg_lookup.get((scene_idx, None))
            if seg:
                timeline.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "scene_index": scene_idx,
                    "scene_type": scene_type,
                    "step_index": None,
                    "render": scene["render"],
                    "text": scene.get("text", ""),
                    "audio_text": scene.get("audio", ""),
                    "word_timestamps": seg.get("word_timestamps", []),
                })
                last_end = seg["end"]

        # --- Scene with render but NO audio (visual_intro, options, etc.) ---
        # Do NOT consume any audio segment — place based on timing only.
        elif scene.get("render") and not scene.get("steps") and not scene.get("audio"):
            start = last_end + buffer_s
            # Look ahead: if next audio segment exists, end before it starts
            next_seg = _find_next_audio_segment(seg_lookup, scene_idx, question_data)
            if next_seg:
                duration = max(0.5, next_seg["start"] - start - buffer_s)
                duration = min(duration, 3.0)  # Cap at 3 seconds
            else:
                duration = 2.0
            timeline.append({
                "start": start,
                "end": start + duration,
                "scene_index": scene_idx,
                "scene_type": scene_type,
                "step_index": None,
                "render": scene["render"],
                "text": scene.get("text", ""),
                "audio_text": "",
            })
            last_end = start + duration

        # --- Steps within scene ---
        for step_idx, step in enumerate(scene.get("steps", [])):
            if step.get("audio"):
                seg = seg_lookup.get((scene_idx, step_idx))
                if seg:
                    timeline.append({
                        "start": seg["start"],
                        "end": seg["end"],
                        "scene_index": scene_idx,
                        "scene_type": scene_type,
                        "step_index": step_idx,
                        "render": step.get("render", {}),
                        "text": step.get("text", ""),
                        "audio_text": step.get("audio", ""),
                        "word_timestamps": seg.get("word_timestamps", []),
                    })
                    last_end = seg["end"]
            else:
                # Step without audio — short default duration
                start = last_end + buffer_s
                timeline.append({
                    "start": start,
                    "end": start + 1.5,
                    "scene_index": scene_idx,
                    "scene_type": scene_type,
                    "step_index": step_idx,
                    "render": step.get("render", {}),
                    "text": step.get("text", ""),
                    "audio_text": "",
                })
                last_end = start + 1.5

        # --- Verdict ---
        if scene.get("verdict_audio"):
            seg = seg_lookup.get((scene_idx, "verdict"))
            if seg:
                timeline.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "scene_index": scene_idx,
                    "scene_type": scene_type,
                    "step_index": "verdict",
                    "render": {"action": "highlight", "target": "final_answer"},
                    "text": "",
                    "audio_text": scene["verdict_audio"],
                    "word_timestamps": seg.get("word_timestamps", []),
                })
                last_end = seg["end"]

    return timeline


def _find_next_audio_segment(seg_lookup, current_scene_idx, question_data):
    """Find the next audio segment after current_scene_idx."""
    scenes = question_data.get("scenes", [])
    for si in range(current_scene_idx + 1, len(scenes)):
        scene = scenes[si]
        # Check scene-level audio
        if scene.get("audio"):
            seg = seg_lookup.get((si, None))
            if seg:
                return seg
        # Check step-level audio
        for step_idx, step in enumerate(scene.get("steps", [])):
            if step.get("audio"):
                seg = seg_lookup.get((si, step_idx))
                if seg:
                    return seg
    return None


def get_active_state(timeline, current_time, question_data):
    """Given a timestamp, compute the visual state using accumulation model.

    Elements accumulate by target type — same target replaces, different targets coexist.
    This ensures persistent elements (digit_boxes + running_sum) stay visible together.

    Supports multiple video modes: mcq, topic, true_false, fill_blank,
    numerical, match, assertion, sequence.
    """
    mode = question_data.get("mode", "mcq")
    question_text = ""
    options_data = []
    correct_option = ""

    # Extract question metadata — support both top-level question block and scene-level
    q_block = question_data.get("question", {})
    if q_block.get("text"):
        question_text = q_block["text"]
    if q_block.get("options"):
        options_data = q_block["options"]
    if q_block.get("correct"):
        correct_option = q_block["correct"]

    for scene in question_data.get("scenes", []):
        if scene.get("type") == "question" and not question_text:
            question_text = scene.get("text", "")
        elif scene.get("type") == "options" and not options_data:
            options_data = scene.get("render", {}).get("data", [])
        elif scene.get("type") == "solution" and not correct_option:
            correct_option = scene.get("option", "")

    # Accumulate state from all past timeline entries
    work_elements = {}  # target_type -> element data
    highlighted_option = ""
    show_correct = False
    step_text = ""
    question_shown = False
    options_shown = False

    for entry in timeline:
        if entry["start"] > current_time:
            break

        render = entry.get("render", {})
        action = render.get("action", "")
        target = render.get("target", "")

        # Track the step label (skip question/options — already shown at top)
        if entry.get("scene_type") not in ("question", "options", "visual_intro"):
            step_text = entry.get("text", "")

        # ── Single clean target-dispatch chain ──────────────────────────────
        # Each target is handled exactly once; show_correct is set separately
        # at the bottom so it never interferes with the elif chain.

        if target == "question_block":
            question_shown = True

        elif target == "options_grid":
            options_shown = True

        elif target.startswith("option_"):
            highlighted_option = target.replace("option_", "")

        elif action == "highlight_option" and target == "options_grid":
            highlighted_option = render.get("key", "")

        elif target in ("equation", "division_block"):
            if action in ("show", "show_result"):
                work_elements[target] = {
                    "type": target,
                    "value": render.get("value", render.get("expression", "")),
                    "highlighted": False,
                }
            elif action == "update":
                prev_val = work_elements.get(target, {}).get("value", "")
                work_elements[target] = {
                    "type": target,
                    "value": render.get("value", render.get("expression", prev_val)),
                    "highlighted": False,
                }
            elif action == "highlight":
                if target in work_elements:
                    work_elements[target]["highlighted"] = True

        elif target == "formula_block":
            if action == "show":
                work_elements["formula_block"] = {
                    "type": "formula_block",
                    "value": render.get("value", ""),
                    "highlighted": False,
                }
            elif action == "update":
                if "formula_block" in work_elements:
                    work_elements["formula_block"]["value"] = render.get(
                        "value", work_elements["formula_block"]["value"])
                    work_elements["formula_block"]["highlighted"] = False
            elif action == "highlight":
                if "formula_block" in work_elements:
                    work_elements["formula_block"]["highlighted"] = True

        elif target == "digit_boxes":
            work_elements["digit_boxes"] = {
                "type": "digit_boxes",
                "data": render.get("data", []),
                "highlighted_indices": render.get("highlighted_indices",
                                                  render.get("indices", [])),
            }

        elif target == "digits":
            if "digit_boxes" in work_elements:
                work_elements["digit_boxes"]["highlighted_indices"] = render.get("indices", [])

        elif target == "shortcut_columns":
            work_elements.pop("concept_text", None)   # mutually exclusive with text
            prev      = work_elements.get("shortcut_columns", {})
            had_right = bool(prev.get("right", {}).get("title"))
            has_right = bool(render.get("right", {}).get("title"))
            if has_right and not had_right:
                right_appeared_at = entry["start"]
            elif has_right:
                right_appeared_at = prev.get("right_appeared_at")
            else:
                right_appeared_at = None
            work_elements["shortcut_columns"] = {
                "type": "shortcut_columns",
                "left":  render.get("left",  {}),
                "right": render.get("right", {}),
                "right_appeared_at": right_appeared_at,
            }

        elif target == "fraction":
            work_elements["fraction"] = {
                "type": "fraction",
                "numerator":   str(render.get("numerator", "")),
                "denominator": str(render.get("denominator", "")),
                "result":      str(render.get("result", "")),
                "label":       render.get("label", ""),
                "highlighted": render.get("highlighted", False),
            }

        elif target == "running_sum":
            work_elements["running_sum"] = {
                "type": "running_sum",
                "value": str(render.get("value", "")),
            }

        elif target == "sum_box":
            if action in ("show", "show_result"):
                work_elements["sum_box"] = {
                    "type": "sum_box",
                    "value": str(render.get("value", "")),
                    "highlighted": render.get("highlighted", False),
                }
            elif action == "highlight":
                if "sum_box" in work_elements:
                    work_elements["sum_box"]["highlighted"] = True

        elif target == "final_answer":
            show_correct = True

        elif target == "concept_text":
            work_elements.pop("shortcut_columns", None)  # mutually exclusive with columns
            work_elements["concept_text"] = {
                "type":        "concept_text",
                "text":        render.get("value", entry.get("text", "")),
                "heading":     render.get("heading", ""),
                "items":       render.get("items", []),
                "highlighted": render.get("highlighted", action == "highlight"),
            }

        elif target == "instruction_text":
            # Clears ALL body elements — used for major section transitions
            for k in list(work_elements.keys()):
                work_elements.pop(k, None)
            work_elements["instruction_text"] = {
                "type": "instruction_text",
                "text": render.get("value", entry.get("text", "")),
            }

        elif target == "image":
            work_elements["image"] = {
                "type":     "image",
                "src_path": render.get("_resolved_path", ""),
                "position": render.get("position", "center"),
                "size":     render.get("size", "medium"),
            }

        elif target == "svg":
            work_elements["svg"] = {
                "type":     "svg",
                "src_path": render.get("_resolved_path", ""),
                "position": render.get("position", "center"),
                "size":     render.get("size", "medium"),
            }

        elif target == "table":
            work_elements["table"] = {
                "type":    "table",
                "headers": render.get("headers", []),
                "rows":    render.get("rows",    []),
            }

        elif target:
            # ── Generic fallback — any new element type works without code changes ──
            # JSON just needs: action="show", target="my_type", plus any fields.
            # Supports actions: show / show_result / update / highlight / clear
            if action in ("show", "show_result"):
                work_elements[target] = {
                    "type": target,
                    **{k: v for k, v in render.items() if k != "action"},
                }
            elif action == "update":
                if target in work_elements:
                    work_elements[target].update(
                        {k: v for k, v in render.items() if k != "action"}
                    )
            elif action == "highlight":
                if target in work_elements:
                    work_elements[target]["highlighted"] = True
            elif action == "clear":
                work_elements.pop(target, None)

        # Reveal correct option in header ONLY for answer scenes
        # (concept scenes should NOT reveal — final_answer target handles it)
        if entry.get("scene_type") == "answer":
            show_correct = True

    # --- Find active narration (word-by-word sync) ---
    active_narration = None
    for entry in timeline:
        if entry["start"] <= current_time <= entry["end"]:
            wts = entry.get("word_timestamps", [])
            if wts:
                active_narration = {
                    "word_timestamps": wts,
                    "audio_text": entry.get("audio_text", entry.get("text", "")),
                }
            break

    # --- Build final elements list ---
    elements = []

    # Topic header (for topic/match/sequence modes)
    topic_block = question_data.get("topic_header", question_data.get("topic", {}))
    if isinstance(topic_block, str):
        topic_block = {"title": topic_block}
    if topic_block and mode in ("topic", "match", "sequence"):
        elements.append({
            "type": "topic_header",
            "title": topic_block.get("title", ""),
            "subtitle": topic_block.get("subtitle", ""),
        })

    # Assertion header (for assertion mode)
    if mode == "assertion" and question_shown:
        elements.append({
            "type": "question_block",
            "text": question_text,
            "assertion": q_block.get("assertion", ""),
            "reason": q_block.get("reason", ""),
        })
    # Question (always at top once shown) — for mcq, true_false, fill_blank, numerical
    elif question_shown and question_text and mode not in ("topic", "match", "sequence"):
        elements.append({
            "type": "question_block",
            "text": question_text,
        })

    # Options (persist once shown) — only for mcq, true_false
    if options_shown and options_data and mode in ("mcq", "true_false"):
        elements.append({
            "type": "options_grid",
            "data": options_data,
            "highlighted_key": highlighted_option,
            "correct_key": correct_option if show_correct else "",
        })

    # Work area elements in logical display order
    work_order = [
        "instruction_text",
        # Visual content
        "shortcut_columns",
        "concept_text",
        "highlight_box",     # important formula / rule
        "key_facts",         # key:value pairs (History, Geography, GK)
        "process_steps",     # numbered steps (Science, Math methods)
        "two_col_text",      # two-column text comparison
        "timeline",          # chronological events (History)
        "chem_equation",     # chemical equation (Chemistry)
        "flow_chart",        # process flow (Biology, Science)
        "t_account",         # debit/credit T-account (Accounts)
        "memory_trick",      # mnemonic/acronym display
        "analogy",           # A:B::C:? (Reasoning)
        "number_line",       # number line (Math)
        "builtin_visual",    # pure-Pillow subject illustrations
        "subject_image",     # auto-fetched free photo
        "video_clip",        # embedded video asset
        "matplotlib_plot",   # scientific graph (line/bar/scatter/pie/histogram)
        "rdkit_mol",         # 2D molecular structure from SMILES
        "manim_scene",       # pre-rendered Manim animation
        # Multi-mode elements
        "title_card",        # topic mode intro card
        "section_header",    # topic mode section divider
        "blank_reveal",      # fill-in-the-blank display
        "match_columns",     # match-the-following columns
        "sequence_list",     # sequence/ordering items
        "numerical_answer",  # numerical answer box
        "image", "svg",
        # Math
        "formula_block", "equation", "division_block",
        "digit_boxes", "running_sum",
        "fraction", "sum_box",
        # Universal
        "table", "final_answer",
    ]
    for target_type in work_order:
        if target_type in work_elements:
            elements.append(work_elements[target_type])

    # Step label
    if step_text:
        elements.append({"type": "step_label", "text": step_text})

    # Progress
    total_duration = timeline[-1]["end"] if timeline else 1
    progress = min(current_time / total_duration, 1.0) if total_duration > 0 else 0

    return {
        "elements": elements,
        "progress": progress,
        "narration": active_narration,
        "current_time": current_time,
        "mode": mode,
    }
