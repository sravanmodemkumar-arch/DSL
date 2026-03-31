"""Frame renderer — PPT-style video frames using Pillow.

Matches professional PowerPoint presentation design:
  - Dark navy header bar with question + options (always visible)
  - Orange accent stripe below header
  - Light/white body with clean typography
  - Blue accent digit boxes with operators
  - Color-coded option indicators
  - Word-by-word karaoke narration bar
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# PPT Color Palette (extracted from Divisibility_Complete_Auto.pptx)
# ---------------------------------------------------------------------------

PPT_COLORS = {
    # Layout
    "bg": "#FFFFFF",
    "header_bg": "#1A237E",
    "accent_stripe": "#EF6C00",
    # Header text
    "question_label": "#F9A825",
    "header_text": "#FFFFFF",
    # Body text
    "body_text": "#212121",
    "body_secondary": "#757575",
    "note_text": "#1A237E",
    # Accents
    "blue": "#1565C0",
    "green": "#2E7D32",
    "orange": "#EF6C00",
    "red": "#C62828",
    # Cards
    "card_bg": "#F5F5F5",
    "concept_blue_bg": "#E3F2FD",
    "concept_orange_bg": "#FFF3E0",
    "digit_bg": "#FFFFFF",
    "digit_border": "#1565C0",
    "digit_text": "#1565C0",
    # Results
    "success": "#2E7D32",
    "fail": "#C62828",
    "result_bg": "#F5F5F5",
    # Narration bar
    "narration_bg": "#1A237E",
    "narration_spoken": "#FFFFFF",
    "narration_active": "#F9A825",
    "narration_pending": "#5C6BC0",
    # Progress
    "progress": "#EF6C00",
}

# Option key → left-bar color
OPTION_BAR_COLORS = {
    "a": "#1565C0", "A": "#1565C0",
    "b": "#2E7D32", "B": "#2E7D32",
    "c": "#EF6C00", "C": "#EF6C00",
    "d": "#C62828", "D": "#C62828",
}


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

# Bundled Google Fonts (downloaded once into storage/assets/fonts/)
_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "assets", "fonts")

_FONT_REGULAR  = os.path.join(_FONTS_DIR, "Poppins-Regular.ttf")
_FONT_MEDIUM   = os.path.join(_FONTS_DIR, "Poppins-Medium.ttf")
_FONT_SEMIBOLD = os.path.join(_FONTS_DIR, "Poppins-SemiBold.ttf")
_FONT_BOLD     = os.path.join(_FONTS_DIR, "Poppins-Bold.ttf")
_FONT_MATH     = os.path.join(_FONTS_DIR, "NotoSansMath-Regular.ttf")


def _get_font(size=32, bold=False):
    # Priority: DejaVuSans (renders ALL Unicode symbols: ✓ ✗ → ÷ × √ ₂ ₃ π Σ α β)
    # Poppins looks nicer but renders ✓ ✗ → ₂ as empty boxes — DO NOT use as primary
    candidates = []
    if bold:
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            _FONT_BOLD,
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        _FONT_REGULAR,
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for fname in candidates:
        if os.path.exists(fname):
            try:
                return ImageFont.truetype(fname, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _get_symbol_font(size=42):
    """Font with ✓ ✗ → ₂ ₃ and all Unicode symbols."""
    # DejaVuSans has the best Unicode coverage — use it for symbols
    for fname in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        os.path.join(_FONTS_DIR, "NotoSansMath-Regular.ttf"),
        "/usr/share/fonts/truetype/noto/NotoSansSymbols-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf",
        "C:/Windows/Fonts/seguisym.ttf",
        "C:/Windows/Fonts/seguiemj.ttf",
    ]:
        if os.path.exists(fname):
            try:
                return ImageFont.truetype(fname, size)
            except Exception:
                continue
    return _get_font(size)


def _get_math_font(size=36):
    # DejaVuSans handles math symbols (÷ × √ ² ³ ≥ ≤ ≠ ± π Σ) correctly
    for fname in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        os.path.join(_FONTS_DIR, "NotoSansMath-Regular.ttf"),
        "/usr/share/fonts/truetype/noto/NotoSansMath-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "C:/Windows/Fonts/cambria.ttc",
        "C:/Windows/Fonts/times.ttf",
    ]:
        if os.path.exists(fname):
            try:
                return ImageFont.truetype(fname, size)
            except Exception:
                continue
    return _get_font(size)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Audio-driven digit highlight helper
# ---------------------------------------------------------------------------

_WORD_TO_DIGIT = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}

def _get_spoken_digit_highlights(narration, current_time, digit_data):
    """Return set of digit_data indices being spoken right now."""
    if not narration:
        return set()
    wts = narration.get("word_timestamps", [])
    if not wts:
        return set()

    data_strs = [str(d).lstrip("+-") for d in digit_data]

    # Sequential mapping: walk wts, match digit words to digit_data in order
    data_ptr = 0
    seq_map = []  # [(wt_index, digit_data_index)]
    for wi, wt in enumerate(wts):
        word = wt["word"].lower().strip(".,!?;:")
        mapped = _WORD_TO_DIGIT.get(word)
        if mapped is not None and data_ptr < len(data_strs):
            if data_strs[data_ptr] == mapped:
                seq_map.append((wi, data_ptr))
                data_ptr += 1

    active = set()
    for wi, di in seq_map:
        wt = wts[wi]
        if wt["start"] <= current_time <= wt["end"]:
            active.add(di)
    return active


class FrameRenderer:
    """PPT-style frame renderer with dark header + light body."""

    def __init__(self, width=1920, height=1080, theme=None, watermark=None):
        self.width = width
        self.height = height
        # Always use PPT color palette — ignore external theme override
        self.C = PPT_COLORS.copy()
        self.scale = height / 1080
        self.watermark = watermark or {}

        # Layout zones
        self.margin_x = int(width * 0.025)
        self.content_x = int(width * 0.04)
        self.usable_w = width - 2 * self.margin_x
        self.content_w = width - 2 * self.content_x
        self.spacing = int(20 * self.scale)

        # Header height: ~20% of frame (matches PPT proportions)
        self.header_h = int(height * 0.20)
        self.stripe_h = int(5 * self.scale)

    # --- Color helpers ---

    def _hex(self, key_or_color):
        """Get color from palette key or pass hex through."""
        if key_or_color.startswith("#"):
            return key_or_color
        return self.C.get(key_or_color, "#000000")

    def _rgb(self, key_or_color):
        hex_c = self._hex(key_or_color)
        hex_c = hex_c.lstrip("#")
        return tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))

    # --- Main render ---

    def create_blank_frame(self):
        return Image.new("RGB", (self.width, self.height), self._rgb("bg"))

    def render_frame(self, state):
        """Render a frame — layout adapts based on video mode.

        Modes:
          mcq (default) — dark header (question + options) + white body
          topic         — slim title bar + full body (no question/options)
          true_false    — question + T/F pills + body
          fill_blank    — question with blank + body
          numerical     — question (no options) + body
          match         — full body for match columns
          assertion     — assertion/reason header + body
          sequence      — full body for sequence items
        """
        frame = self.create_blank_frame()
        draw = ImageDraw.Draw(frame)
        elements = state.get("elements", [])
        mode = state.get("mode", "mcq")

        # Separate elements by role
        question_el = None
        options_el = None
        topic_el = None
        work_elems = []

        for el in elements:
            etype = el.get("type")
            if etype == "question_block":
                question_el = el
            elif etype == "options_grid":
                options_el = el
            elif etype == "topic_header":
                topic_el = el
            elif etype != "step_label":
                work_elems.append(el)

        work_elems = [el for el in work_elems if self._is_renderable(el)]

        # Draw header based on mode — returns body_top y coordinate
        if mode == "topic":
            body_top = self._draw_topic_bar(draw, frame, topic_el)
        elif mode in ("match", "sequence"):
            body_top = self._draw_minimal_bar(draw, frame, topic_el)
        elif mode == "numerical":
            body_top = self._draw_numerical_header(draw, frame, question_el)
        elif mode == "fill_blank":
            body_top = self._draw_header(draw, frame, question_el, None)
        elif mode == "assertion":
            body_top = self._draw_assertion_header(draw, frame, question_el)
        else:
            # mcq, true_false — standard header
            body_top = self._draw_header(draw, frame, question_el, options_el)

        # Draw step label (heading) above body content — before work_elems layout
        step_label_el = next((el for el in elements if el.get("type") == "step_label"), None)
        if step_label_el and step_label_el.get("text", "").strip():
            body_top = self._draw_step_label(draw, frame, step_label_el, body_top)

        # Karaoke strip: reserve bottom strip when narration word timestamps exist
        narration    = state.get("narration")
        current_time = state.get("current_time", 0)
        karaoke_h    = 0
        karaoke_gap  = 0
        if narration and narration.get("word_timestamps"):
            karaoke_h   = int(90 * self.scale)
            karaoke_gap = int(16 * self.scale)

        if work_elems:

            body_bottom = self.height - int(30 * self.scale) - karaoke_h - karaoke_gap

            # ── Top-aligned layout — elements start right below header ──
            # Small top margin, small gaps between elements.
            # Elements expand to fill available space via body_bottom param.
            top_pad = int(20 * self.scale)
            gap = int(16 * self.scale)
            y_work = body_top + top_pad

            for el in work_elems:
                if y_work > body_bottom:
                    break
                y_work = self._dispatch_element(
                    draw, frame, el, y_work,
                    body_bottom=body_bottom,
                    current_time=current_time,
                    narration=narration,
                )
                y_work += gap

        # Karaoke strip at bottom
        if karaoke_h > 0:
            strip_y = self.height - int(30 * self.scale) - karaoke_h
            self._draw_karaoke_strip(draw, narration, current_time, strip_y, karaoke_h)

        # Moving watermark
        self._draw_watermark(frame, current_time)

        # === PROGRESS BAR ===
        progress = state.get("progress", 0)
        if progress > 0:
            bar_h = int(5 * self.scale)
            bar_w = int(self.width * progress)
            draw.rectangle(
                [0, self.height - bar_h, bar_w, self.height],
                fill=self._rgb("progress"),
            )

        return frame

    # ------------------------------------------------------------------
    # MODE A: Full-screen question intro (PPT slide 1 — pixel-exact)
    # ------------------------------------------------------------------

    def _draw_question_intro(self, draw, frame, question_el, options_el):
        """Full-screen question layout matching PPT slide 1 exactly.

        Pixel measurements at 1920x1080 (from PPT EMU positions):
          - Blue stripe:   y=0,   h=10px
          - Orange stripe: y=10,  h=10px
          - Question text: y=96,  22pt×2=58px bold
          - Gray divider:  y=384, h=6px
          - Option row 1:  y=461, h=134px  (2 cards side by side)
          - Option row 2:  y=634, h=134px
          - Left pad: 96px, card width: 826px, gap: 77px
          - Accent bar: 12px wide, color per option key
        """
        s = self.scale

        # Top stripes (blue + orange)
        draw.rectangle([0, 0, self.width, int(10 * s)], fill=self._rgb("blue"))
        draw.rectangle([0, int(10 * s), self.width, int(20 * s)], fill=self._rgb("orange"))

        # --- Question text: y=96px, 58px bold, dark, centered ---
        if question_el:
            text = question_el.get("text", "")
            font = _get_font(int(58 * s), bold=True)
            lines = self._wrap_text(text, font, int(1728 * s))
            line_h = int(font.size * 1.35)
            q_y = int(96 * s)
            for i, line in enumerate(lines):
                tw = draw.textlength(line, font=font)
                draw.text(((self.width - tw) / 2, q_y + i * line_h),
                          line, fill=self._rgb("body_text"), font=font)

        # Gray divider at y=384px
        draw.rectangle([0, int(384 * s), self.width, int(390 * s)],
                       fill=self._rgb("card_bg"))

        # --- Option cards: 2×2 grid, pixel-exact positions ---
        if options_el:
            data = options_el.get("data", [])
            highlighted_key = options_el.get("highlighted_key", "")
            correct_key = options_el.get("correct_key", "")

            # PPT exact: left=96, card_w=826, gap=77, card_h=134, row1_y=461, row2_y=634
            left_pad = int(96 * s)
            card_w = int(826 * s)
            col_gap = int(77 * s)
            card_h = int(134 * s)
            row_gap = int(38 * s)
            bar_w = int(12 * s)
            row_y = [int(461 * s), int(634 * s)]

            key_font = _get_font(int(37 * s))          # 14pt × 2 = small key label
            val_font = _get_font(int(64 * s), bold=True)  # 24pt × 2 = large bold value

            for i, opt in enumerate(data):
                col = i % 2
                row = i // 2
                key = opt.get("key", "")
                value = str(opt.get("value", ""))

                cx = left_pad + col * (card_w + col_gap)
                cy = row_y[row]

                # Card background
                if key == correct_key:
                    card_bg = self._rgb("green")
                    key_col = (255, 255, 255)
                    val_col = (255, 255, 255)
                elif key == highlighted_key:
                    card_bg = (255, 103, 0)   # saffron
                    key_col = (255, 255, 255)
                    val_col = (255, 255, 255)
                else:
                    card_bg = self._rgb("card_bg")
                    key_col = self._rgb("body_secondary")
                    val_col = self._rgb("body_secondary")

                draw.rounded_rectangle(
                    [cx, cy, cx + card_w, cy + card_h],
                    radius=int(8 * s), fill=card_bg,
                )

                # Color-coded left accent bar
                if key not in (correct_key, highlighted_key):
                    bar_color = OPTION_BAR_COLORS.get(key.lower(), "#1565C0")
                    draw.rectangle([cx, cy, cx + bar_w, cy + card_h],
                                   fill=self._rgb(bar_color))

                # Text: "(a)  " small + "277218" large bold
                text_x = cx + bar_w + int(20 * s)
                text_cy_small = cy + int(20 * s)
                text_cy_val = cy + (card_h - val_font.size) // 2

                draw.text((text_x, text_cy_small),
                          f"({key})", fill=key_col, font=key_font)
                draw.text((text_x + draw.textlength(f"({key}) ", font=key_font),
                           text_cy_val),
                          value, fill=val_col, font=val_font)

    # ------------------------------------------------------------------
    # HEADER: dark navy bar with question + options
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Dynamic dispatch — routes any element type to its draw method.
    # To add a new type: (1) add _draw_<type> method, (2) add to work_order
    # in sync.py. No other changes needed.
    # ------------------------------------------------------------------

    def _dispatch_element(self, draw, frame, el, y,
                          body_bottom=None, current_time=0, narration=None):
        etype = el.get("type", "")
        if etype in ("equation", "division_block"):
            return self._draw_equation(draw, frame, el, y)
        elif etype == "formula_block":
            return self._draw_formula(draw, frame, el, y)
        elif etype == "digit_boxes":
            return self._draw_digit_boxes(draw, frame, el, y)
        elif etype == "running_sum":
            return self._draw_running_sum(draw, frame, el, y)
        elif etype == "shortcut_columns":
            return self._draw_shortcut_columns(draw, frame, el, y,
                                               body_bottom=body_bottom,
                                               current_time=current_time,
                                               narration=narration)
        elif etype == "fraction":
            return self._draw_fraction(draw, frame, el, y)
        elif etype == "sum_box":
            return self._draw_result_box(draw, frame, el, y)
        elif etype == "final_answer":
            return self._draw_final_answer(draw, frame, el, y)
        elif etype == "concept_text":
            return self._draw_concept_text(draw, frame, el, y)
        elif etype == "instruction_text":
            return self._draw_instruction_text(draw, frame, el, y)
        elif etype == "image":
            return self._draw_image(frame, el, y, body_bottom)
        elif etype == "svg":
            return self._draw_svg(frame, el, y, body_bottom)
        elif etype == "table":
            return self._draw_table(draw, frame, el, y)
        # ── Universal types (all subjects / all exams) ──
        elif etype == "highlight_box":
            return self._draw_highlight_box(draw, frame, el, y)
        elif etype == "key_facts":
            return self._draw_key_facts(draw, frame, el, y)
        elif etype == "process_steps":
            return self._draw_process_steps(draw, frame, el, y)
        elif etype == "two_col_text":
            return self._draw_two_col_text(draw, frame, el, y)
        elif etype == "timeline":
            return self._draw_timeline(draw, frame, el, y)
        elif etype == "chem_equation":
            return self._draw_chem_equation(draw, frame, el, y)
        elif etype == "flow_chart":
            return self._draw_flow_chart(draw, frame, el, y)
        elif etype == "t_account":
            return self._draw_t_account(draw, frame, el, y)
        elif etype == "memory_trick":
            return self._draw_memory_trick(draw, frame, el, y)
        elif etype == "video_clip":
            return self._draw_video_clip(draw, frame, el, y)
        elif etype == "analogy":
            return self._draw_analogy(draw, frame, el, y)
        elif etype == "number_line":
            return self._draw_number_line(draw, frame, el, y)
        elif etype == "builtin_visual":
            return self._draw_builtin_visual(draw, frame, el, y)
        elif etype == "subject_image":
            return self._draw_subject_image(draw, frame, el, y)
        elif etype == "matplotlib_plot":
            return self._draw_matplotlib_plot(draw, frame, el, y)
        elif etype == "map_plot":
            return self._draw_map_plot(draw, frame, el, y)
        elif etype == "geometry_3d":
            return self._draw_geometry_3d(draw, frame, el, y)
        elif etype == "rdkit_mol":
            return self._draw_rdkit_mol(draw, frame, el, y)
        elif etype == "manim_scene":
            return self._draw_manim_scene(draw, frame, el, y,
                                          current_time=current_time)
        # ── Multi-mode elements ──
        elif etype == "title_card":
            return self._draw_title_card(draw, frame, el, y)
        elif etype == "section_header":
            return self._draw_section_header(draw, frame, el, y)
        elif etype == "blank_reveal":
            return self._draw_blank_reveal(draw, frame, el, y)
        elif etype == "match_columns":
            return self._draw_match_columns(draw, frame, el, y)
        elif etype == "sequence_list":
            return self._draw_sequence_list(draw, frame, el, y)
        elif etype == "numerical_answer":
            return self._draw_numerical_answer(draw, frame, el, y)
        # ── Degree-level dedicated targets ──
        elif etype == "latex_equation":
            return self._draw_latex_equation(draw, frame, el, y)
        elif etype == "derivation_chain":
            return self._draw_derivation_chain(draw, frame, el, y)
        elif etype == "circuit_diagram":
            return self._draw_circuit_diagram(draw, frame, el, y)
        elif etype == "bohr_model":
            return self._draw_bohr_model(draw, frame, el, y)
        elif etype == "free_body_diagram":
            return self._draw_free_body_diagram(draw, frame, el, y)
        elif etype == "wave_diagram":
            return self._draw_wave_diagram(draw, frame, el, y)
        elif etype == "ray_diagram":
            return self._draw_ray_diagram(draw, frame, el, y)
        elif etype == "energy_level":
            return self._draw_energy_level(draw, frame, el, y)
        elif etype == "molecule_2d":
            return self._draw_molecule_2d(draw, frame, el, y)
        elif etype == "periodic_element":
            return self._draw_periodic_element(draw, frame, el, y)
        elif etype == "periodic_table":
            return self._draw_periodic_table_mini(draw, frame, el, y)
        elif etype == "energy_diagram":
            return self._draw_energy_diagram(draw, frame, el, y)
        elif etype == "orbital_diagram":
            return self._draw_orbital_diagram(draw, frame, el, y)
        elif etype == "cell_diagram":
            return self._draw_cell_diagram(draw, frame, el, y)
        elif etype == "punnett_square":
            return self._draw_punnett_square(draw, frame, el, y)
        elif etype == "food_chain":
            return self._draw_food_chain_degree(draw, frame, el, y)
        elif etype == "dna_structure":
            return self._draw_dna_structure(draw, frame, el, y)
        elif etype == "india_map":
            return self._draw_india_map(draw, frame, el, y)
        elif etype == "world_map":
            return self._draw_world_map(draw, frame, el, y)
        elif etype == "timeline_bar":
            return self._draw_timeline_bar(draw, frame, el, y)
        elif etype == "comparison_table":
            return self._draw_comparison_table(draw, frame, el, y)
        elif etype == "process_cycle":
            return self._draw_process_cycle(draw, frame, el, y)
        elif etype == "hierarchy_tree":
            return self._draw_hierarchy_tree(draw, frame, el, y)
        elif etype == "cause_effect":
            return self._draw_cause_effect(draw, frame, el, y)
        elif etype == "factor_tree":
            return self._draw_factor_tree(draw, frame, el, y)
        elif etype == "venn_diagram":
            return self._draw_venn_diagram_degree(draw, frame, el, y)
        elif etype == "balance_scale":
            return self._draw_balance_scale(draw, frame, el, y)
        elif etype == "coordinate_axes":
            return self._draw_coordinate_axes(draw, frame, el, y)
        elif etype == "bar_chart":
            return self._draw_bar_chart(draw, frame, el, y)
        elif etype == "pie_chart":
            return self._draw_pie_chart(draw, frame, el, y)
        elif etype == "clock_diagram":
            return self._draw_clock_diagram(draw, frame, el, y)
        elif etype == "reaction_equation":
            return self._draw_reaction_equation(draw, frame, el, y)
        # ── New ultra-pro render targets ──
        elif etype == "option_analysis":
            return self._draw_option_analysis(draw, frame, el, y,
                                              body_bottom=body_bottom)
        elif etype == "bullet_list":
            return self._draw_bullet_list(draw, frame, el, y)
        elif etype == "definition_card":
            return self._draw_definition_card(draw, frame, el, y)
        elif etype == "quote_block":
            return self._draw_quote_block(draw, frame, el, y)
        elif etype == "code_block":
            return self._draw_code_block(draw, frame, el, y)
        elif etype == "matrix":
            return self._draw_matrix(draw, frame, el, y)
        elif etype == "proof_steps":
            return self._draw_proof_steps(draw, frame, el, y)
        elif etype == "conversion_chain":
            return self._draw_conversion_chain(draw, frame, el, y)
        elif etype == "dice_visual":
            return self._draw_dice_visual(draw, frame, el, y)
        elif etype == "calendar_visual":
            return self._draw_calendar_visual(draw, frame, el, y)
        elif etype == "seating_arrangement":
            return self._draw_seating_arrangement(draw, frame, el, y)
        elif etype == "coding_decoding":
            return self._draw_coding_decoding(draw, frame, el, y)
        elif etype == "syllogism":
            return self._draw_syllogism(draw, frame, el, y)
        elif etype == "blood_relation_tree":
            return self._draw_blood_relation_tree(draw, frame, el, y)
        elif etype == "direction_diagram":
            return self._draw_direction_diagram(draw, frame, el, y)
        elif etype == "ranking_order":
            return self._draw_ranking_order(draw, frame, el, y)
        elif etype == "series_pattern":
            return self._draw_series_pattern(draw, frame, el, y)
        elif etype == "amendment_card":
            return self._draw_amendment_card(draw, frame, el, y)
        elif etype == "person_card":
            return self._draw_person_card(draw, frame, el, y)
        elif etype == "stat_card":
            return self._draw_stat_card(draw, frame, el, y)
        elif etype == "split_screen":
            return self._draw_split_screen(draw, frame, el, y)
        elif etype == "grid_check":
            return self._draw_grid_check(draw, frame, el, y)
        elif etype == "equation_steps":
            return self._draw_equation_steps(draw, frame, el, y)
        elif etype == "web_image":
            return self._draw_web_image(draw, frame, el, y)
        elif etype == "web_gif":
            return self._draw_web_gif(draw, frame, el, y)
        elif etype == "web_video":
            return self._draw_web_video(draw, frame, el, y)
        elif etype == "google_image":
            return self._draw_google_image(draw, frame, el, y)
        # ── Batch 2 ultra-pro targets ──
        elif etype == "truth_table":
            return self._draw_truth_table(draw, frame, el, y)
        elif etype == "law_card":
            return self._draw_law_card(draw, frame, el, y)
        elif etype == "tip_box":
            return self._draw_tip_box(draw, frame, el, y)
        elif etype == "warning_box":
            return self._draw_warning_box(draw, frame, el, y)
        elif etype == "event_card":
            return self._draw_event_card(draw, frame, el, y)
        elif etype == "word_breakdown":
            return self._draw_word_breakdown(draw, frame, el, y)
        elif etype == "fill_blank_sentence":
            return self._draw_fill_blank_sentence(draw, frame, el, y)
        elif etype == "venn_operations":
            return self._draw_venn_operations(draw, frame, el, y)
        elif etype == "mirror_image":
            return self._draw_mirror_image(draw, frame, el, y)
        elif etype == "clock_angle":
            return self._draw_clock_angle(draw, frame, el, y)
        elif etype == "input_output":
            return self._draw_input_output(draw, frame, el, y)
        elif etype == "cube_visual":
            return self._draw_cube_visual(draw, frame, el, y)
        elif etype == "place_value":
            return self._draw_place_value(draw, frame, el, y)
        elif etype == "spectrum_band":
            return self._draw_spectrum_band(draw, frame, el, y)
        elif etype == "ratio_bar":
            return self._draw_ratio_bar(draw, frame, el, y)
        elif etype == "percentage_bar":
            return self._draw_percentage_bar(draw, frame, el, y)
        elif etype == "odd_one_out":
            return self._draw_odd_one_out(draw, frame, el, y)
        elif etype == "flashcard":
            return self._draw_flashcard(draw, frame, el, y)
        # ── Aliases for common AI-generated target names ──
        elif etype == "instruction_lines":
            # AI sometimes generates this instead of bullet_list/concept_text
            items = el.get("data", el.get("items", el.get("lines", [])))
            if isinstance(items, str):
                items = [items]
            return self._draw_bullet_list(draw, frame, {
                "heading": el.get("heading", ""),
                "items": items,
                "icon": "arrow",
                "color": "blue",
            }, y)
        return y   # unknown type — skip silently

    # ------------------------------------------------------------------
    # Universal element renderers
    # ------------------------------------------------------------------

    def _draw_highlight_box(self, draw, frame, element, y):
        """Full-width colored box for important formula / rule.

        JSON: { "target": "highlight_box", "text": "...", "color": "orange|blue|green|red" }
        """
        text  = element.get("text", element.get("value", ""))
        color = element.get("color", "orange")
        s     = self.scale

        color_map = {
            "orange": ((239, 108, 0),   (255, 243, 224)),
            "blue":   ((21,  101, 192),  (227, 242, 253)),
            "green":  ((46,  125, 50),   (232, 245, 233)),
            "red":    ((198, 40,  40),   (255, 235, 238)),
        }
        fg, bg = color_map.get(color, color_map["orange"])

        font  = _get_font(int(52 * s), bold=True)
        pad_x = int(64 * s)
        pad_y = int(36 * s)
        max_w = self.content_w - 2 * pad_x
        lines = self._wrap_text(text, font, max_w)
        line_h = int(font.size * 1.45)
        card_h = len(lines) * line_h + 2 * pad_y

        draw.rounded_rectangle(
            [self.content_x, y, self.content_x + self.content_w, y + card_h],
            radius=int(12 * s), fill=bg,
        )
        bar_w = int(7 * s)
        draw.rectangle([self.content_x, y, self.content_x + bar_w, y + card_h], fill=fg)
        for i, line in enumerate(lines):
            tw = draw.textlength(line, font=font)
            draw.text((self.content_x + (self.content_w - tw) / 2, y + pad_y + i * line_h),
                      line, fill=fg, font=font)
        return y + card_h

    def _draw_key_facts(self, draw, frame, element, y):
        """Key : Value table — for History, Geography, Science facts.

        JSON: { "target": "key_facts",
                "heading": "Key Facts",
                "facts": [{"key": "Year", "value": "1947"}, ...] }
        """
        heading = element.get("heading", "")
        facts   = element.get("facts", [])
        s       = self.scale

        head_font = _get_font(int(46 * s), bold=True)
        key_font  = _get_font(int(44 * s), bold=True)
        val_font  = _get_font(int(44 * s), bold=False)
        pad_x     = int(52 * s)
        pad_y     = int(30 * s)
        row_h     = int(key_font.size * 2.0)
        sep       = int(3 * s)
        head_h    = int(head_font.size * 1.6) if heading else 0
        card_h    = head_h + len(facts) * row_h + 2 * pad_y

        cx = self.content_x
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(10 * s), fill=self._rgb("concept_blue_bg"),
        )
        draw.rectangle([cx, y, cx + int(5 * s), y + card_h], fill=self._rgb("blue"))

        cy = y + pad_y
        if heading:
            draw.text((cx + pad_x, cy), heading,
                      fill=self._rgb("blue"), font=head_font)
            cy += head_h

        key_col_w = int(self.content_w * 0.32)
        for fact in facts:
            k = str(fact.get("key",   ""))
            v = str(fact.get("value", ""))
            # Alternating row background
            row_bg = (235, 242, 252)
            draw.rectangle([cx + int(4*s), cy, cx + self.content_w - int(2*s),
                            cy + row_h - sep], fill=row_bg)
            draw.text((cx + pad_x,                cy + (row_h - key_font.size) // 2),
                      k, fill=self._rgb("blue"), font=key_font)
            draw.text((cx + pad_x + key_col_w,    cy + (row_h - val_font.size) // 2),
                      v, fill=self._rgb("body_text"), font=val_font)
            cy += row_h
        return y + card_h

    def _draw_process_steps(self, draw, frame, element, y):
        """Numbered step list — for Science processes, Math methods.

        JSON: { "target": "process_steps",
                "heading": "Steps",
                "steps": ["Step text 1", "Step text 2", ...] }
        """
        heading = element.get("heading", "")
        steps   = element.get("steps",   [])
        s       = self.scale

        head_font = _get_font(int(46 * s), bold=True)
        step_font = _get_font(int(44 * s), bold=False)
        num_font  = _get_font(int(42 * s), bold=True)
        pad_x     = int(52 * s)
        pad_y     = int(30 * s)
        num_r     = int(28 * s)          # circle radius
        line_h    = int(step_font.size * 1.9)
        head_h    = int(head_font.size * 1.6) if heading else 0
        card_h    = head_h + len(steps) * line_h + 2 * pad_y

        cx = self.content_x
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(10 * s), fill=self._rgb("concept_orange_bg"),
        )
        draw.rectangle([cx, y, cx + int(5 * s), y + card_h], fill=self._rgb("orange"))

        cy = y + pad_y
        if heading:
            draw.text((cx + pad_x, cy), heading,
                      fill=self._rgb("orange"), font=head_font)
            cy += head_h

        max_w = self.content_w - pad_x * 2 - num_r * 2 - int(16 * s)
        for i, step in enumerate(steps):
            # Numbered circle
            nx = cx + pad_x
            ny = cy + (line_h - num_r * 2) // 2
            draw.ellipse([nx, ny, nx + num_r * 2, ny + num_r * 2],
                         fill=self._rgb("orange"))
            nstr = str(i + 1)
            nw   = draw.textlength(nstr, font=num_font)
            draw.text((nx + (num_r * 2 - nw) / 2, ny + (num_r * 2 - num_font.size) / 2),
                      nstr, fill=(255, 255, 255), font=num_font)
            # Step text
            wrapped = self._wrap_text(step, step_font, max_w)
            for li, line in enumerate(wrapped):
                draw.text((nx + num_r * 2 + int(16 * s), cy + li * int(step_font.size * 1.3)),
                          line, fill=self._rgb("body_text"), font=step_font)
            cy += line_h
        return y + card_h

    def _draw_two_col_text(self, draw, frame, element, y):
        """Two-column text card — for comparisons, pros/cons, before/after.

        JSON: { "target": "two_col_text",
                "left":  {"heading": "Rule of 9",  "items": ["...", "..."]},
                "right": {"heading": "Rule of 11", "items": ["...", "..."]} }
        """
        left  = element.get("left",  {})
        right = element.get("right", {})
        s     = self.scale

        col_gap  = int(24 * s)
        col_w    = (self.content_w - col_gap) // 2
        head_f   = _get_font(int(46 * s), bold=True)
        body_f   = _get_font(int(44 * s), bold=False)
        pad_x    = int(44 * s)
        pad_y    = int(30 * s)
        line_h   = int(body_f.size * 1.7)
        colors   = [self._rgb("blue"), self._rgb("orange")]

        # Measure height from the taller column
        max_items = max(len(left.get("items", [])), len(right.get("items", [])))
        head_h    = int(head_f.size * 1.4)
        card_h    = head_h + max_items * line_h + 2 * pad_y

        for ci, (col_data, bc) in enumerate(zip([left, right], colors)):
            cx = self.content_x + ci * (col_w + col_gap)
            draw.rounded_rectangle(
                [cx, y, cx + col_w, y + card_h],
                radius=int(10 * s), fill=self._rgb("card_bg"),
            )
            draw.rectangle([cx, y, cx + int(5 * s), y + card_h], fill=bc)
            cy = y + pad_y
            if col_data.get("heading"):
                draw.text((cx + pad_x, cy), col_data["heading"], fill=bc, font=head_f)
                cy += head_h
            for item in col_data.get("items", []):
                draw.text((cx + pad_x, cy), f"\u2022 {item}",
                          fill=self._rgb("body_text"), font=body_f)
                cy += line_h
        return y + card_h

    # ------------------------------------------------------------------
    def _draw_topic_bar(self, draw, frame, topic_el):
        """Slim title bar for topic/explanation mode — no question, no options.
        Returns body_top y coordinate."""
        s = self.scale
        bar_h = int(100 * s)

        # Dark navy background
        draw.rectangle([0, 0, self.width, bar_h], fill=self._rgb("header_bg"))
        # Orange accent stripe
        draw.rectangle([0, bar_h, self.width, bar_h + self.stripe_h],
                       fill=self._rgb("accent_stripe"))

        if topic_el:
            pad_x = int(58 * s)
            title = topic_el.get("title", "")
            subtitle = topic_el.get("subtitle", "")

            if title:
                tf = _get_font(int(42 * s), bold=True)
                draw.text((pad_x, int(12 * s)), title,
                          fill=self._rgb("header_text"), font=tf)
            if subtitle:
                sf = _get_font(int(28 * s))
                draw.text((pad_x, int(58 * s)), subtitle,
                          fill=self._rgb("question_label"), font=sf)

        return bar_h + self.stripe_h + int(20 * s)

    def _draw_minimal_bar(self, draw, frame, topic_el):
        """Minimal header for match/sequence modes. Returns body_top."""
        s = self.scale
        bar_h = int(70 * s)

        draw.rectangle([0, 0, self.width, bar_h], fill=self._rgb("header_bg"))
        draw.rectangle([0, bar_h, self.width, bar_h + self.stripe_h],
                       fill=self._rgb("accent_stripe"))

        if topic_el:
            title = topic_el.get("title", "")
            if title:
                tf = _get_font(int(36 * s), bold=True)
                draw.text((int(58 * s), int(16 * s)), title,
                          fill=self._rgb("header_text"), font=tf)

        return bar_h + self.stripe_h + int(15 * s)

    def _draw_numerical_header(self, draw, frame, question_el):
        """Header with question only (no options) for numerical mode. Returns body_top."""
        s = self.scale
        bar_h = int(120 * s)

        draw.rectangle([0, 0, self.width, bar_h], fill=self._rgb("header_bg"))
        draw.rectangle([0, bar_h, self.width, bar_h + self.stripe_h],
                       fill=self._rgb("accent_stripe"))

        if question_el:
            text = question_el.get("text", "")
            pad_x = int(58 * s)
            q_font = _get_font(int(38 * s), bold=True)
            label_font = _get_font(int(38 * s), bold=True)

            q_y = int(15 * s)
            draw.text((pad_x, q_y), "Q: ", fill=self._rgb("question_label"), font=label_font)
            q_offset = draw.textlength("Q: ", font=label_font)

            max_w = self.content_w - q_offset - int(20 * s)
            lines = self._wrap_text(text, q_font, max_w)
            line_h = int(q_font.size * 1.25)
            for i, line in enumerate(lines):
                x = pad_x + (q_offset if i == 0 else int(20 * s))
                draw.text((x, q_y + i * line_h), line,
                          fill=self._rgb("header_text"), font=q_font)

            # "Numerical Answer" badge
            badge_font = _get_font(int(24 * s))
            badge_text = "NUMERICAL TYPE"
            bw = draw.textlength(badge_text, font=badge_font) + int(20 * s)
            bx = self.width - int(58 * s) - bw
            by = int(15 * s)
            draw.rounded_rectangle([bx, by, bx + bw, by + int(34 * s)],
                                   radius=int(6 * s), fill=self._rgb("orange"))
            draw.text((bx + int(10 * s), by + int(4 * s)), badge_text,
                      fill=(255, 255, 255), font=badge_font)

        return bar_h + self.stripe_h + int(20 * s)

    def _draw_assertion_header(self, draw, frame, question_el):
        """Header for assertion-reason mode. Shows assertion + reason. Returns body_top."""
        s = self.scale
        bar_h = int(180 * s)

        draw.rectangle([0, 0, self.width, bar_h], fill=self._rgb("header_bg"))
        draw.rectangle([0, bar_h, self.width, bar_h + self.stripe_h],
                       fill=self._rgb("accent_stripe"))

        if question_el:
            pad_x = int(58 * s)
            assertion = question_el.get("assertion", "")
            reason = question_el.get("reason", "")
            q_font = _get_font(int(32 * s), bold=True)
            label_font = _get_font(int(28 * s), bold=True)

            # Assertion
            a_y = int(12 * s)
            draw.text((pad_x, a_y), "Assertion (A): ",
                      fill=self._rgb("question_label"), font=label_font)
            a_offset = draw.textlength("Assertion (A): ", font=label_font)
            if assertion:
                lines = self._wrap_text(assertion, q_font, self.content_w - a_offset)
                for i, line in enumerate(lines[:2]):
                    draw.text((pad_x + a_offset if i == 0 else pad_x + int(20 * s),
                               a_y + i * int(q_font.size * 1.25)),
                              line, fill=self._rgb("header_text"), font=q_font)

            # Reason
            r_y = int(95 * s)
            draw.text((pad_x, r_y), "Reason (R): ",
                      fill=(255, 180, 100), font=label_font)
            r_offset = draw.textlength("Reason (R): ", font=label_font)
            if reason:
                lines = self._wrap_text(reason, q_font, self.content_w - r_offset)
                for i, line in enumerate(lines[:2]):
                    draw.text((pad_x + r_offset if i == 0 else pad_x + int(20 * s),
                               r_y + i * int(q_font.size * 1.25)),
                              line, fill=self._rgb("header_text"), font=q_font)

        return bar_h + self.stripe_h + int(15 * s)

    def _draw_header(self, draw, frame, question_el, options_el):
        """Draw the dark navy header bar with question and options row.
        Returns body_top y coordinate."""
        s = self.scale

        # Navy header background
        draw.rectangle(
            [0, 0, self.width, self.header_h],
            fill=self._rgb("header_bg"),
        )

        # Orange accent stripe
        draw.rectangle(
            [0, self.header_h, self.width, self.header_h + self.stripe_h],
            fill=self._rgb("accent_stripe"),
        )

        if not question_el and not options_el:
            return int(259 * s)

        # PPT exact: Q text at y=9.6px, options at y=105.6px
        # Left padding: 57.6px (3% of 1920)
        pad_x = int(58 * s)

        # --- Question text at y=9.6px in header ---
        if question_el:
            text = question_el.get("text", "")
            # 13pt × 2 = 35px, but make it a touch bigger for readability
            q_font = _get_font(int(38 * s), bold=True)
            label_font = _get_font(int(38 * s), bold=True)

            q_y = int(10 * s)
            # "Q:" in gold
            draw.text((pad_x, q_y), "Q: ", fill=self._rgb("question_label"), font=label_font)
            q_offset = draw.textlength("Q: ", font=label_font)

            # Question text in white, single line (header is compact)
            max_w = self.content_w - q_offset - int(20 * s)
            lines = self._wrap_text(text, q_font, max_w)
            line_h = int(q_font.size * 1.25)
            for i, line in enumerate(lines):
                x = pad_x + (q_offset if i == 0 else int(20 * s))
                draw.text((x, q_y + i * line_h), line,
                          fill=self._rgb("header_text"), font=q_font)

        # --- Options row at y=105.6px in header ---
        if options_el:
            data = options_el.get("data", [])
            highlighted_key = options_el.get("highlighted_key", "")
            correct_key = options_el.get("correct_key", "")
            opt_font = _get_font(int(36 * s), bold=True)

            # PPT exact option X positions: 57.6, 480, 883.2, 1286.4 px
            opt_x = [int(58 * s), int(480 * s), int(883 * s), int(1286 * s)]
            opt_y = int(106 * s)

            for i, opt in enumerate(data):
                if i >= len(opt_x):
                    break
                key = opt.get("key", "")
                value = str(opt.get("value", ""))
                label = f"({key}) {value}"

                if key == correct_key:
                    # Bright green filled badge — clearly identifiable
                    ow = int(draw.textlength(label, font=opt_font) + int(20 * s))
                    oh = opt_font.size + int(12 * s)
                    draw.rounded_rectangle(
                        [opt_x[i] - int(10 * s), opt_y - int(6 * s),
                         opt_x[i] + ow, opt_y + oh],
                        radius=int(8 * s), fill=(0, 180, 80),
                    )
                    color = (255, 255, 255)  # white text on green
                elif key == highlighted_key:
                    # Saffron highlight box behind active option
                    ow = draw.textlength(label, font=opt_font) + int(16 * s)
                    draw.rounded_rectangle(
                        [opt_x[i] - int(8 * s), opt_y - int(4 * s),
                         opt_x[i] + ow, opt_y + opt_font.size + int(8 * s)],
                        radius=int(6 * s), fill=(255, 103, 0),
                    )
                    color = (255, 255, 255)  # white text on saffron
                else:
                    color = self._rgb("header_text")

                draw.text((opt_x[i], opt_y), label, fill=color, font=opt_font)

        return int(259 * s)  # body_top

    # ------------------------------------------------------------------
    # New element renderers — topic/match/sequence/fill_blank/numerical
    # ------------------------------------------------------------------

    def _draw_title_card(self, draw, frame, element, y):
        """Full-width intro title card for topic mode. Centered large text."""
        s = self.scale
        avail_h = int(self.height * 0.35)
        cx, cw = self.content_x, self.content_w
        title = element.get("title", "")
        subtitle = element.get("subtitle", "")
        badge = element.get("badge", "")

        # Dark gradient background card
        draw.rounded_rectangle([cx, y, cx + cw, y + avail_h],
                               radius=int(16 * s), fill=(25, 30, 55))

        my = y + avail_h // 2
        if title:
            tf = _get_font(int(56 * s), bold=True)
            tw = draw.textlength(title, font=tf)
            draw.text((cx + (cw - tw) / 2, my - int(60 * s)),
                      title, fill=(255, 255, 255), font=tf)
        if subtitle:
            sf = _get_font(int(32 * s))
            sw = draw.textlength(subtitle, font=sf)
            draw.text((cx + (cw - sw) / 2, my + int(10 * s)),
                      subtitle, fill=(180, 200, 255), font=sf)
        if badge:
            bf = _get_font(int(22 * s), bold=True)
            bw = draw.textlength(badge, font=bf) + int(24 * s)
            bx = cx + (cw - bw) // 2
            by = my + int(55 * s)
            draw.rounded_rectangle([bx, by, bx + bw, by + int(30 * s)],
                                   radius=int(8 * s), fill=(255, 103, 0))
            draw.text((bx + int(12 * s), by + int(4 * s)), badge,
                      fill=(255, 255, 255), font=bf)
        return y + avail_h

    def _draw_section_header(self, draw, frame, element, y):
        """Section divider bar — used in topic mode between sections."""
        s = self.scale
        h = int(65 * s)
        cx, cw = self.content_x, self.content_w
        title = element.get("title", "")
        subtitle = element.get("subtitle", "")
        color = element.get("color", "blue")

        accent = self._rgb(color)
        draw.rounded_rectangle([cx, y, cx + cw, y + h],
                               radius=int(8 * s), fill=accent)

        if title:
            tf = _get_font(int(34 * s), bold=True)
            draw.text((cx + int(20 * s), y + int(6 * s)), title,
                      fill=(255, 255, 255), font=tf)
        if subtitle:
            sf = _get_font(int(22 * s))
            draw.text((cx + int(20 * s), y + int(38 * s)), subtitle,
                      fill=(220, 220, 255), font=sf)

        return y + h

    def _draw_blank_reveal(self, draw, frame, element, y):
        """Fill-in-the-blank display with optional answer reveal."""
        s = self.scale
        h = int(120 * s)
        cx, cw = self.content_x, self.content_w
        sentence = element.get("sentence", "")
        answer = element.get("answer", "")
        revealed = element.get("revealed", False)

        draw.rounded_rectangle([cx, y, cx + cw, y + h],
                               radius=int(10 * s), fill=(240, 245, 255))

        tf = _get_font(int(36 * s), bold=True)

        if "___" in sentence and revealed and answer:
            # Split around blank, draw normally then answer in green
            parts = sentence.split("___", 1)
            x = cx + int(30 * s)
            text_y = y + (h - tf.size) // 2
            draw.text((x, text_y), parts[0], fill=(30, 30, 60), font=tf)
            x += draw.textlength(parts[0], font=tf)
            af = _get_font(int(36 * s), bold=True)
            draw.text((x, text_y), answer, fill=(0, 160, 60), font=af)
            x += draw.textlength(answer, font=af)
            if len(parts) > 1:
                draw.text((x, text_y), parts[1], fill=(30, 30, 60), font=tf)
        else:
            tw = draw.textlength(sentence, font=tf)
            draw.text((cx + (cw - tw) / 2, y + (h - tf.size) // 2),
                      sentence, fill=(30, 30, 60), font=tf)
        return y + h

    def _draw_match_columns(self, draw, frame, element, y):
        """Two columns for Match-the-Following. Lines connect when revealed."""
        s = self.scale
        cx, cw = self.content_x, self.content_w
        left_items = element.get("left", [])
        right_items = element.get("right", [])
        revealed = element.get("revealed", False)
        matches = element.get("matches", {})  # {"0":"2", "1":"0", ...}

        n = max(len(left_items), len(right_items))
        row_h = int(55 * s)
        h = int(50 * s) + n * row_h
        col_w = int(cw * 0.38)
        gap = cw - 2 * col_w

        # Column headers
        hf = _get_font(int(36 * s), bold=True)
        draw.text((cx + col_w // 2 - int(50 * s), y), "Column A",
                  fill=(21, 101, 192), font=hf)
        draw.text((cx + col_w + gap + col_w // 2 - int(50 * s), y), "Column B",
                  fill=(255, 103, 0), font=hf)
        y += int(50 * s)

        rf = _get_font(int(36 * s))
        for i in range(n):
            iy = y + i * row_h
            # Left item
            if i < len(left_items):
                draw.rounded_rectangle([cx, iy, cx + col_w, iy + row_h - int(8 * s)],
                                       radius=int(6 * s), fill=(230, 240, 255))
                draw.text((cx + int(15 * s), iy + int(12 * s)),
                          f"{i+1}. {left_items[i]}", fill=(30, 30, 60), font=rf)
            # Right item
            if i < len(right_items):
                rx = cx + col_w + gap
                draw.rounded_rectangle([rx, iy, rx + col_w, iy + row_h - int(8 * s)],
                                       radius=int(6 * s), fill=(255, 240, 230))
                letter = chr(65 + i)  # A, B, C...
                draw.text((rx + int(15 * s), iy + int(12 * s)),
                          f"{letter}. {right_items[i]}", fill=(30, 30, 60), font=rf)

            # Connection lines when revealed
            if revealed and str(i) in matches:
                j = int(matches[str(i)])
                lx = cx + col_w
                ly = iy + row_h // 2
                rx2 = cx + col_w + gap
                ry = y + j * row_h + row_h // 2
                draw.line([(lx, ly), (rx2, ry)], fill=(0, 160, 60), width=int(3 * s))

        return y + n * row_h

    def _draw_sequence_list(self, draw, frame, element, y):
        """Sequence/ordering items — shuffled or revealed in correct order."""
        s = self.scale
        cx, cw = self.content_x, self.content_w
        items = element.get("items", [])
        revealed = element.get("revealed", False)
        heading = element.get("heading", "Arrange in correct order")

        hf = _get_font(int(38 * s), bold=True)
        draw.text((cx, y), heading, fill=(21, 101, 192), font=hf)
        y += int(54 * s)

        rf = _get_font(int(38 * s))
        row_h = int(64 * s)
        for i, item in enumerate(items):
            iy = y + i * row_h
            color = (220, 255, 220) if revealed else (240, 240, 250)
            border = (0, 160, 60) if revealed else (180, 180, 200)
            draw.rounded_rectangle([cx, iy, cx + cw, iy + row_h - int(8 * s)],
                                   radius=int(8 * s), fill=color, outline=border,
                                   width=int(2 * s))
            num_color = (0, 160, 60) if revealed else (100, 100, 140)
            draw.text((cx + int(20 * s), iy + int(14 * s)),
                      f"{i+1}.", fill=num_color, font=_get_font(int(38 * s), bold=True))
            draw.text((cx + int(60 * s), iy + int(14 * s)),
                      item, fill=(30, 30, 60), font=rf)

        return y + len(items) * row_h

    def _draw_numerical_answer(self, draw, frame, element, y):
        """Highlighted answer box for numerical-type questions (no options)."""
        s = self.scale
        h = int(110 * s)
        cx, cw = self.content_x, self.content_w
        value = element.get("value", "")
        unit = element.get("unit", "")
        label = element.get("label", "Answer")

        draw.rounded_rectangle([cx, y, cx + cw, y + h],
                               radius=int(12 * s), fill=(0, 160, 60))
        # Label
        lf = _get_font(int(24 * s), bold=True)
        draw.text((cx + int(20 * s), y + int(10 * s)), label,
                  fill=(200, 255, 200), font=lf)
        # Value
        vf = _get_font(int(48 * s), bold=True)
        display = f"{value} {unit}".strip()
        tw = draw.textlength(display, font=vf)
        draw.text((cx + (cw - tw) / 2, y + int(40 * s)),
                  display, fill=(255, 255, 255), font=vf)
        return y + h

    # ------------------------------------------------------------------
    # Height estimation
    # ------------------------------------------------------------------

    def _estimate_height(self, element, draw):
        s = self.scale
        etype = element.get("type")
        if etype in ("equation", "division_block"):
            return int(130 * s)
        elif etype == "formula_block":
            return int(130 * s)
        elif etype == "digit_boxes":
            return int(135 * s)
        elif etype == "shortcut_columns":
            body_top = int(259 * s)
            return self.height - body_top - int(90 * s)
        elif etype == "fraction":
            return int(130 * s)
        elif etype == "running_sum":
            return int(80 * s)
        elif etype == "sum_box":
            return int(120 * s)
        elif etype == "final_answer":
            return int(160 * s)
        elif etype == "concept_text":
            head_font = _get_font(int(52 * s), bold=True)
            body_font = _get_font(int(48 * s))
            pad_y     = int(32 * s)
            line_gap  = int(18 * s)
            h = 2 * pad_y
            if element.get("heading", ""):
                h += int(head_font.size * 1.3) + line_gap
            items = element.get("items", [])
            if items:
                max_w = self.content_w - int(128 * s)
                for item in items:
                    wrapped = self._wrap_text(item, body_font, max_w)
                    h += len(wrapped) * int(body_font.size * 1.45) + line_gap
            else:
                text = element.get("text", "")
                if text:
                    for line in self._wrap_text(text, body_font, self.content_w - int(112 * s)):
                        h += int(body_font.size * 1.45)
            return max(h, int(120 * s))
        elif etype == "instruction_text":
            return int(110 * s)
        elif etype == "image":
            return int(self.height * 0.35)
        elif etype == "svg":
            return int(self.height * 0.3)
        elif etype == "table":
            rows = element.get("rows", [])
            return int((len(rows) + 1) * 64 * s + 20 * s)
        # Multi-mode elements
        elif etype == "title_card":
            return int(self.height * 0.35)
        elif etype == "section_header":
            return int(65 * s)
        elif etype == "blank_reveal":
            return int(120 * s)
        elif etype == "match_columns":
            n = max(len(element.get("left", [])), len(element.get("right", [])))
            return int(50 * s + n * 55 * s)
        elif etype == "sequence_list":
            return int(45 * s + len(element.get("items", [])) * 55 * s)
        elif etype == "numerical_answer":
            return int(110 * s)
        elif etype == "map_plot":
            return int(self.height * 0.44)
        elif etype == "geometry_3d":
            return int(self.height * 0.42)
        # ── New ultra-pro targets ──
        elif etype == "option_analysis":
            checks = element.get("checks", [])
            return int((100 + len(checks) * 160 + 80 + 64) * s)
        elif etype == "bullet_list":
            items = element.get("items", [])
            return int((56 + 50 + len(items) * 76) * s)
        elif etype == "definition_card":
            return int(260 * s)
        elif etype == "quote_block":
            return int(220 * s)
        elif etype == "code_block":
            code = element.get("code", element.get("value", ""))
            lines = code.split("\\n") if "\\n" in code else code.split("\n")
            return int((48 + len(lines) * 52) * s)
        elif etype == "matrix":
            rows = element.get("rows", [])
            return int(len(rows) * 60 * s + 30 * s)
        elif etype == "proof_steps":
            steps = element.get("steps", [])
            return int((66 + len(steps) * 72 + 56) * s)
        elif etype == "conversion_chain":
            return int(120 * s)
        elif etype == "dice_visual":
            return int(160 * s)
        elif etype == "calendar_visual":
            return int(360 * s)
        elif etype == "seating_arrangement":
            layout = element.get("layout", "circular")
            return int(380 * s) if layout == "circular" else int(160 * s)
        elif etype == "coding_decoding":
            mapping = element.get("mapping", {})
            cols = min(len(mapping), 13)
            rows_n = (len(mapping) + cols - 1) // cols if cols else 1
            return int((50 + rows_n * 120) * s)
        elif etype == "syllogism":
            premises = element.get("premises", [])
            return int((40 + len(premises) * 72 + 120) * s)
        elif etype == "blood_relation_tree":
            members = element.get("members", [])
            levels = set(m.get("level", 0) for m in members)
            return int((20 + len(levels) * 140) * s)
        elif etype == "direction_diagram":
            return int(380 * s)
        elif etype == "ranking_order":
            return int(120 * s)
        elif etype == "series_pattern":
            return int(130 * s)
        elif etype == "amendment_card":
            return int(280 * s)
        elif etype == "person_card":
            facts = element.get("facts", {})
            return int((140 + len(facts) * 42) * s)
        elif etype == "stat_card":
            return int(150 * s)
        elif etype == "split_screen":
            return int(320 * s)
        elif etype == "grid_check":
            options = element.get("options", [])
            return int((50 + (len(options) + 1) * 56 + 12) * s)
        elif etype == "equation_steps":
            steps = element.get("steps", [])
            return int((66 + len(steps) * 84 + 56) * s)
        elif etype in ("web_image", "web_gif", "google_image"):
            size = element.get("size", "medium")
            return int(self.height * {"small": 0.25, "medium": 0.35, "large": 0.50}.get(size, 0.35))
        elif etype == "web_video":
            return int(self.height * 0.35)
        # ── Batch 2 targets ──
        elif etype == "truth_table":
            rows = element.get("rows", [])
            return int((48 + 48 + len(rows) * 50 + 12) * s)
        elif etype == "law_card":
            return int(300 * s)
        elif etype in ("tip_box", "warning_box"):
            return int(180 * s)
        elif etype == "event_card":
            return int(280 * s)
        elif etype == "word_breakdown":
            return int(200 * s)
        elif etype == "fill_blank_sentence":
            return int(120 * s)
        elif etype == "venn_operations":
            return int(340 * s)
        elif etype == "mirror_image":
            return int(200 * s)
        elif etype == "clock_angle":
            return int(360 * s)
        elif etype == "input_output":
            steps = element.get("steps", [])
            return int((48 + len(steps) * 48 + 12) * s)
        elif etype == "cube_visual":
            return int(260 * s)
        elif etype == "place_value":
            return int(140 * s)
        elif etype == "spectrum_band":
            return int(140 * s)
        elif etype == "ratio_bar":
            items = element.get("items", [])
            return int((48 + len(items) * 68) * s)
        elif etype == "percentage_bar":
            return int(170 * s)
        elif etype == "odd_one_out":
            return int(140 * s)
        elif etype == "flashcard":
            return int(250 * s)
        return int(80 * s)

    # ------------------------------------------------------------------
    # BODY ELEMENTS
    # ------------------------------------------------------------------

    def _draw_equation(self, draw, frame, element, y):
        """Equation card — light gray bg, centered text."""
        value = str(element.get("value", element.get("expression", "")))
        highlighted = element.get("highlighted", False)
        s = self.scale
        font = _get_math_font(int(56 * s))

        tw = draw.textlength(value, font=font)
        pad_x = int(56 * s)
        pad_y = int(30 * s)
        card_h = int(font.size * 1.5) + 2 * pad_y

        card_x = self.content_x
        card_w = self.content_w
        draw.rounded_rectangle(
            [card_x, y, card_x + card_w, y + card_h],
            radius=int(10 * s), fill=self._rgb("card_bg"),
        )

        # Blue left accent bar
        bar_w = int(5 * s)
        accent = "blue" if not highlighted else "green"
        draw.rectangle(
            [card_x, y, card_x + bar_w, y + card_h],
            fill=self._rgb(accent),
        )

        if highlighted:
            draw.rounded_rectangle(
                [card_x, y, card_x + card_w, y + card_h],
                radius=int(10 * s),
                outline=self._rgb("green"), width=int(2 * s),
            )

        color = self._rgb("blue" if not highlighted else "green")
        text_x = card_x + (card_w - tw) / 2
        draw.text((text_x, y + pad_y), value, fill=color, font=font)

        return y + card_h

    def _draw_formula(self, draw, frame, element, y):
        """Formula card — light blue bg with left accent bar."""
        value = str(element.get("value", ""))
        highlighted = element.get("highlighted", False)
        s = self.scale
        font = _get_font(int(48 * s))

        pad_x = int(36 * s)
        pad_y = int(18 * s)
        card_h = int(font.size * 1.3) + 2 * pad_y + int(24 * s)

        card_x = self.content_x
        card_w = self.content_w
        bg = "concept_blue_bg" if not highlighted else "concept_orange_bg"
        draw.rounded_rectangle(
            [card_x, y, card_x + card_w, y + card_h],
            radius=int(10 * s), fill=self._rgb(bg),
        )

        # Left accent bar
        bar_w = int(5 * s)
        bar_color = "blue" if not highlighted else "orange"
        draw.rectangle(
            [card_x, y, card_x + bar_w, y + card_h],
            fill=self._rgb(bar_color),
        )

        # "Formula" label
        label_font = _get_font(int(28 * s), bold=True)
        draw.text(
            (card_x + pad_x, y + int(6 * s)),
            "Formula", fill=self._rgb("body_secondary"), font=label_font,
        )

        # Value
        tw = draw.textlength(value, font=font)
        text_x = card_x + (card_w - tw) / 2
        color = self._rgb("body_text")
        draw.text((text_x, y + pad_y + int(14 * s)), value, fill=color, font=font)

        return y + card_h

    def _draw_digit_boxes(self, draw, frame, element, y):
        """PPT-style digit boxes — white cards with blue top bar + operators."""
        digits = element.get("data", [])
        if not digits:
            return y

        highlighted_indices = element.get("highlighted_indices", [])
        s = self.scale
        n = len(digits)

        # Base sizes
        font_size = int(64 * s)
        box_w = int(105 * s)
        box_h = int(115 * s)
        op_pad = int(18 * s)

        # Scale down if too many digits to fit within content width
        max_w = self.content_w
        font = _get_font(font_size, bold=True)
        op_w = int(draw.textlength("+", font=font))
        op_gap = op_w + op_pad
        total_w = n * box_w + max(0, n - 1) * op_gap

        if total_w > max_w and n > 1:
            ratio = max_w / total_w
            box_w = int(box_w * ratio)
            box_h = int(box_h * ratio)
            font_size = max(int(font_size * ratio), int(24 * s))
            font = _get_font(font_size, bold=True)
            op_w = int(draw.textlength("+", font=font))
            op_pad = int(op_pad * ratio)
            op_gap = op_w + op_pad
            total_w = n * box_w + max(0, n - 1) * op_gap

        op_font = font
        top_bar_h = int(6 * s)

        start_x = (self.width - total_w) / 2

        for i, digit in enumerate(digits):
            x = start_x + i * (box_w + op_gap)
            is_hl = i in highlighted_indices

            # Box background
            if is_hl:
                box_bg = self._rgb("blue")
                text_color = (255, 255, 255)
            else:
                box_bg = self._rgb("digit_bg")
                text_color = self._rgb("digit_text")

            # White box with shadow effect
            if not is_hl:
                shadow = self._rgb("card_bg")
                draw.rounded_rectangle(
                    [x + 2, y + 2, x + box_w + 2, y + box_h + 2],
                    radius=int(8 * s), fill=shadow,
                )

            draw.rounded_rectangle(
                [x, y, x + box_w, y + box_h],
                radius=int(8 * s), fill=box_bg,
                outline=self._rgb("digit_border"), width=int(1 * s),
            )

            # Blue top bar
            draw.rectangle(
                [x, y, x + box_w, y + top_bar_h],
                fill=self._rgb("digit_border"),
            )

            # Digit text centered — use bbox for accurate vertical centering
            dtext = str(digit)
            tw = draw.textlength(dtext, font=font)
            bbox = font.getbbox(dtext)
            text_h = bbox[3] - bbox[1]
            text_y = y + top_bar_h + (box_h - top_bar_h - text_h) / 2 - bbox[1]
            draw.text(
                (x + (box_w - tw) / 2, text_y),
                dtext, fill=text_color, font=font,
            )

            # Operator tight between boxes — centered vertically on box
            if i < len(digits) - 1:
                op_x = x + box_w + int(2 * s)
                op_bbox = op_font.getbbox("+")
                op_text_h = op_bbox[3] - op_bbox[1]
                op_y = y + (box_h - op_text_h) / 2 - op_bbox[1]
                draw.text((op_x, op_y), "+", fill=self._rgb("blue"), font=op_font)

        return y + box_h

    def _draw_shortcut_columns(self, draw, frame, element, y, body_bottom=None, current_time=0, narration=None):
        """Two-column layout: bordered boxes, content evenly distributed to fill full height."""
        s = self.scale
        col_gap   = int(28 * s)
        col_w     = (self.content_w - col_gap) // 2
        col_x     = [self.content_x, self.content_x + col_w + col_gap]
        pad       = int(28 * s)
        border_w  = int(3 * s)

        title_font   = _get_font(int(52 * s), bold=True)    # heading: bold only
        digit_font   = _get_font(int(60 * s), bold=False)  # digits: not bold
        frac_font    = _get_math_font(int(50 * s))
        eq_font      = _get_math_font(int(54 * s))
        verdict_font = _get_font(int(48 * s), bold=False)  # verdict: not bold

        border_colors = [self._rgb("blue"), self._rgb("orange")]
        left_data  = element.get("left",  {})
        right_data = element.get("right", {})

        # Only include columns that have content (at least a title)
        active_sides   = []
        active_colors  = []
        if left_data.get("title"):
            active_sides.append(left_data)
            active_colors.append(self._rgb("blue"))
        if right_data.get("title"):
            active_sides.append(right_data)
            active_colors.append(self._rgb("blue"))   # same color as left

        n_cols  = max(1, len(active_sides))
        col_w   = (self.content_w - col_gap * (n_cols - 1)) // n_cols
        col_x   = [self.content_x + i * (col_w + col_gap) for i in range(n_cols)]
        sides         = active_sides
        border_colors = active_colors

        if body_bottom is None:
            body_bottom = self.height - int(90 * s)
        box_h = max(int(200 * s), body_bottom - y)

        # Compute right-column slide-in offset
        anim_duration = 0.5  # seconds
        right_appeared_at = element.get("right_appeared_at")
        if right_appeared_at is not None and current_time is not None:
            elapsed = current_time - right_appeared_at
            t = max(0.0, min(1.0, elapsed / anim_duration))
            # ease-out cubic: fast start, slow finish
            anim_t = 1.0 - (1.0 - t) ** 3
        else:
            anim_t = 1.0

        for side_i, col_data in enumerate(sides):
            cx = col_x[side_i]
            bc = border_colors[side_i]

            # Slide-in for the right column (side_i == last column with >1 cols)
            slide_x = 0
            if side_i == len(sides) - 1 and len(sides) > 1 and anim_t < 1.0:
                slide_x = int(col_w * (1.0 - anim_t))
            cx += slide_x

            # ── Outer border (no fill) ───────────────────────────
            draw.rounded_rectangle(
                [cx, y, cx + col_w, y + box_h],
                radius=int(14 * s), outline=bc, width=border_w,
            )

            # ── Build content blocks [(draw_fn, height)] ─────────
            line_h = int(3 * s)
            sep_h  = int(2 * s)
            blocks = []  # list of (callable, height)

            # Title block — bold heading, gap, then separator line
            title = col_data.get("title", "")
            title_gap = int(18 * s)
            title_h = title_font.size + title_gap + sep_h
            def _title_block(cy, _title=title, _tgap=title_gap):
                tw = draw.textlength(_title, font=title_font)
                draw.text((cx + (col_w - tw) / 2, cy), _title, fill=bc, font=title_font)
                sep_y = cy + title_font.size + _tgap
                draw.line([cx + pad, sep_y, cx + col_w - pad, sep_y], fill=bc, width=sep_h)
            blocks.append((_title_block, title_h))

            # Digits block — per-element rendering with audio-driven saffron highlight
            digits = col_data.get("digit_data", [])
            if digits:
                has_signs = any(str(d)[:1] in ('+', '-') for d in digits)
                if has_signs:
                    # Rule 11: each signed digit is one part
                    d_parts    = [str(d) for d in digits]
                    d_part_idx = list(range(len(digits)))   # part i → digit i
                else:
                    # Rule 9: interleave digits and operators
                    op = col_data.get("operator", "+")
                    d_parts    = []
                    d_part_idx = []
                    for i, d in enumerate(digits):
                        d_parts.append(str(d))
                        d_part_idx.append(i)          # digit index
                        if i < len(digits) - 1:
                            d_parts.append(op)
                            d_part_idx.append(None)   # operator — not a digit

                # No audio-driven highlighting (sync issues)
                hl_set = set()

                def _digit_block(cy, _parts=d_parts, _pidx=d_part_idx, _hl=hl_set, _bc=bc):
                    usable = col_w - 2 * pad
                    sep_w   = draw.textlength("   ", font=digit_font)
                    part_ws = [draw.textlength(p, font=digit_font) for p in _parts]
                    total_w = sum(part_ws) + sep_w * (len(_parts) - 1)
                    # Shrink separator if content overflows column
                    if total_w > usable and len(_parts) > 1:
                        parts_only = sum(part_ws)
                        avail_sep = usable - parts_only
                        sep_w = max(int(4 * s), int(avail_sep / (len(_parts) - 1)))
                        total_w = parts_only + sep_w * (len(_parts) - 1)
                    # Clamp x so content never goes left of column + pad
                    x = cx + max(pad, (col_w - total_w) / 2)
                    for i, (part, pw) in enumerate(zip(_parts, part_ws)):
                        di = _pidx[i]
                        is_hl = (di is not None) and (di in _hl)
                        if is_hl:
                            pad_hl = int(5 * s)
                            draw.rounded_rectangle(
                                [x - pad_hl, cy - pad_hl,
                                 x + pw + pad_hl, cy + digit_font.size + pad_hl],
                                radius=int(4 * s), fill=(255, 103, 0)  # saffron
                            )
                            color = (255, 255, 255)
                        else:
                            color = _bc
                        draw.text((x, cy), part, fill=color, font=digit_font)
                        x += pw + sep_w
                blocks.append((_digit_block, digit_font.size + int(10 * s)))

            # Fraction block (Rule 9)
            if col_data.get("numerator"):
                num = str(col_data["numerator"])
                den = str(col_data["denominator"])
                res = str(col_data["result"])
                nw  = draw.textlength(num, font=frac_font)
                dw  = draw.textlength(den, font=frac_font)
                fw  = max(nw, dw) + int(20 * s)
                eq_str = f"  =  {res}"
                total_frac_w = fw + int(16 * s) + draw.textlength(eq_str, font=eq_font)
                frac_h = frac_font.size * 2 + line_h + int(24 * s)
                def _frac_block(cy, _num=num, _den=den, _nw=nw, _dw=dw, _fw=fw,
                                _eq=eq_str, _tfrac_w=total_frac_w):
                    fx = cx + max(pad, (col_w - _tfrac_w) / 2)
                    ly = cy + frac_font.size + int(8 * s)
                    draw.text((fx + (_fw - _nw) / 2, cy), _num, fill=bc, font=frac_font)
                    draw.rectangle([fx, ly, fx + _fw, ly + line_h], fill=bc)
                    draw.text((fx + (_fw - _dw) / 2, ly + line_h + int(6 * s)), _den, fill=bc, font=frac_font)
                    mid_y = ly + line_h / 2 - eq_font.size / 2
                    draw.text((fx + _fw + int(16 * s), mid_y), _eq, fill=self._rgb("green"), font=eq_font)
                blocks.append((_frac_block, frac_h))

            # Sum expression block (Rule 11)
            elif col_data.get("sum_text"):
                stext = col_data["sum_text"]
                usable_sum = col_w - 2 * pad
                sum_font = eq_font
                stw_check = draw.textlength(stext, font=sum_font)
                if stw_check > usable_sum:
                    smaller_size = max(int(28 * s), int(54 * s * usable_sum / stw_check))
                    sum_font = _get_math_font(smaller_size)
                def _sum_block(cy, _st=stext, _sf=sum_font):
                    stw = draw.textlength(_st, font=_sf)
                    draw.text((cx + max(pad, (col_w - stw) / 2), cy), _st, fill=bc, font=_sf)
                blocks.append((_sum_block, sum_font.size))

            # Verdict block
            verdict  = col_data.get("verdict", "")
            is_pass  = col_data.get("pass", True)
            if verdict:
                vcolor = self._rgb("green") if is_pass else self._rgb("red")
                def _verdict_block(cy, _v=verdict, _vc=vcolor):
                    vtw = draw.textlength(_v, font=verdict_font)
                    draw.text((cx + (col_w - vtw) / 2, cy), _v, fill=_vc, font=verdict_font)
                blocks.append((_verdict_block, verdict_font.size))

            # ── Distribute blocks evenly in box (n+1 gaps) ───────
            inner_h    = box_h - 2 * pad
            total_content_h = sum(h for _, h in blocks)
            n          = len(blocks)
            gap        = max(int(16 * s), (inner_h - total_content_h) // (n + 1))
            cy         = y + pad + gap

            for fn, h in blocks:
                fn(cy)
                cy += h + gap

        return y + box_h

    def _draw_fraction(self, draw, frame, element, y):
        """Compact inline math fraction — same total height as one text line.

        Layout (all on one baseline row):
            num                = result   [LABEL]
           ─────
            den
        The fraction is vertically compact so it fits the same row height
        as surrounding text elements.
        """
        numerator   = str(element.get("numerator", ""))
        denominator = str(element.get("denominator", ""))
        result      = str(element.get("result", ""))
        label       = element.get("label", "")
        highlighted = element.get("highlighted", False)
        s = self.scale

        # Compact sizes — fraction fits in ~1.8× single line
        num_font = _get_math_font(int(48 * s))
        eq_font  = _get_math_font(int(52 * s))
        lbl_font = _get_symbol_font(int(80 * s))

        num_w = draw.textlength(numerator,   font=num_font)
        den_w = draw.textlength(denominator, font=num_font)
        frac_w = max(num_w, den_w) + int(20 * s)
        line_h = int(4 * s)
        v_gap  = int(8 * s)

        frac_h = num_font.size + v_gap + line_h + v_gap + num_font.size

        # Build right-side string
        result_str = f"  =  {result}" if result else ""
        lbl_str    = f"  {label}" if label else ""
        res_w  = draw.textlength(result_str, font=eq_font) if result_str else 0
        lbl_w  = draw.textlength(lbl_str,    font=lbl_font) if lbl_str else 0
        eq_gap = int(28 * s)

        total_w = frac_w + (eq_gap + res_w + lbl_w if result_str else 0)
        fx = (self.width - total_w) / 2

        line_y = y + num_font.size + v_gap

        # ── Numerator ──
        draw.text(
            (fx + (frac_w - num_w) / 2, y),
            numerator, fill=self._rgb("blue"), font=num_font,
        )
        # ── Fraction line ──
        draw.rectangle(
            [fx, line_y, fx + frac_w, line_y + line_h],
            fill=self._rgb("blue"),
        )
        # ── Denominator ──
        draw.text(
            (fx + (frac_w - den_w) / 2, line_y + line_h + v_gap),
            denominator, fill=self._rgb("blue"), font=num_font,
        )

        # ── = result, centered on fraction line ──
        if result_str:
            mid_y = line_y + line_h / 2 - eq_font.size / 2
            rx = fx + frac_w + eq_gap
            res_color = self._rgb("green" if highlighted else "body_text")
            draw.text((rx, mid_y), result_str, fill=res_color, font=eq_font)

            # ── Symbol badge — both in colored box, unified style ──
            if label:
                lx = rx + draw.textlength(result_str, font=eq_font) + int(16 * s)
                is_pass = label in ("\u2713", "\u2714", "\u2705")
                lbl_color = self._rgb("green") if is_pass else self._rgb("red")
                lbl_w = draw.textlength(label, font=lbl_font)
                pad = int(14 * s)
                lbl_y = line_y + line_h / 2 - lbl_font.size / 2
                draw.rounded_rectangle(
                    [lx - pad, lbl_y - int(8 * s),
                     lx + lbl_w + pad, lbl_y + lbl_font.size + int(8 * s)],
                    radius=int(8 * s), fill=lbl_color,
                )
                draw.text((lx, lbl_y), label, fill=(255, 255, 255), font=lbl_font)

        # ── Green highlight border ──
        if highlighted:
            pad = int(16 * s)
            draw.rounded_rectangle(
                [fx - pad, y - pad,
                 fx + total_w + pad, y + frac_h + pad],
                radius=int(10 * s),
                outline=self._rgb("green"), width=int(3 * s),
            )

        return y + frac_h + int(12 * s)

    def _draw_running_sum(self, draw, frame, element, y):
        """Running sum in orange bold text."""
        value = str(element.get("value", ""))
        s = self.scale
        font = _get_font(int(52 * s), bold=True)
        color = self._rgb("orange")

        label = f"Running Sum: {value}"
        tw = draw.textlength(label, font=font)
        x = (self.width - tw) / 2
        draw.text((x, y), label, fill=color, font=font)

        return y + int(font.size * 1.4)

    def _draw_result_box(self, draw, frame, element, y):
        """Result box — gray bg with sum value."""
        value = str(element.get("value", ""))
        highlighted = element.get("highlighted", False)
        s = self.scale
        font = _get_math_font(int(56 * s))

        label = value  # value already contains full text like "Sum = 27  — PASS"
        tw = draw.textlength(label, font=font)
        pad_x = int(36 * s)
        pad_y = int(20 * s)
        card_h = int(font.size * 1.3) + 2 * pad_y

        card_x = self.content_x
        card_w = self.content_w
        draw.rounded_rectangle(
            [card_x, y, card_x + card_w, y + card_h],
            radius=int(10 * s), fill=self._rgb("result_bg"),
        )

        color = self._rgb("green" if highlighted else "body_text")
        text_x = card_x + (card_w - tw) / 2
        draw.text((text_x, y + pad_y), label, fill=color, font=font)

        if highlighted:
            draw.rounded_rectangle(
                [card_x, y, card_x + card_w, y + card_h],
                radius=int(10 * s),
                outline=self._rgb("green"), width=int(3 * s),
            )

        return y + card_h

    def _draw_final_answer(self, draw, frame, element, y):
        """Final answer with green success styling."""
        value = str(element.get("value", ""))
        highlighted = element.get("highlighted", False)
        s = self.scale
        font = _get_font(int(60 * s), bold=True)
        check_font = _get_font(int(48 * s), bold=True)

        label = f"Answer: {value}" if value else "Correct!"
        tw = draw.textlength(label, font=font)
        pad = int(30 * s)
        card_h = int(font.size * 1.3) + 2 * pad

        card_x = self.content_x + self.content_w * 0.1
        card_w = self.content_w * 0.8

        # Green background card
        draw.rounded_rectangle(
            [card_x, y, card_x + card_w, y + card_h],
            radius=int(12 * s),
            fill=self._rgb("green"),
        )

        # White text centered
        text_x = card_x + (card_w - tw) / 2
        draw.text((text_x, y + pad), label, fill=(255, 255, 255), font=font)

        # Checkmark
        if highlighted:
            check = "\u2714"
            cw = draw.textlength(check, font=check_font)
            draw.text(
                (card_x + int(16 * s), y + (card_h - check_font.size) / 2),
                check, fill=(255, 255, 255), font=check_font,
            )

        return y + card_h

    def _draw_concept_text(self, draw, frame, element, y):
        """Concept card — supports single text, optional heading, and bullet items.

        JSON fields:
          text       — single paragraph (plain string)
          heading    — optional bold heading above text/items
          items      — list of bullet-point strings (replaces text if present)
          highlighted — use orange accent instead of blue
        """
        text        = element.get("text", "")
        heading     = element.get("heading", "")
        items       = element.get("items", [])
        highlighted = element.get("highlighted", False)
        s           = self.scale

        pad_x    = int(56 * s)
        pad_y    = int(32 * s)
        max_w    = self.content_w - 2 * pad_x
        line_gap = int(18 * s)

        head_font  = _get_font(int(52 * s), bold=True)
        body_font  = _get_font(int(48 * s), bold=False)
        line_h_b   = int(body_font.size * 1.45)
        line_h_h   = int(head_font.size * 1.3)

        bar_color = "orange" if highlighted else "blue"
        bg        = "concept_orange_bg" if highlighted else "concept_blue_bg"
        bc        = self._rgb(bar_color)
        text_col  = self._rgb("body_text")

        # ── Measure total height ────────────────────────────────────────
        total_h = 0
        if heading:
            total_h += line_h_h + line_gap
        if items:
            for item in items:
                wrapped = self._wrap_text(item, body_font, max_w - int(36 * s))
                total_h += len(wrapped) * line_h_b + line_gap
        elif text:
            for line in self._wrap_text(text, body_font, max_w):
                total_h += line_h_b
        card_h = total_h + 2 * pad_y

        card_x = self.content_x
        draw.rounded_rectangle(
            [card_x, y, card_x + self.content_w, y + card_h],
            radius=int(10 * s), fill=self._rgb(bg),
        )
        bar_w = int(5 * s)
        draw.rectangle([card_x, y, card_x + bar_w, y + card_h], fill=bc)

        cy = y + pad_y

        # Heading
        if heading:
            draw.text((card_x + pad_x, cy), heading, fill=bc, font=head_font)
            cy += line_h_h + line_gap

        # Bullet items
        if items:
            bullet = "\u2022"
            bw     = draw.textlength(bullet + " ", font=body_font)
            for item in items:
                wrapped = self._wrap_text(item, body_font, max_w - int(36 * s))
                draw.text((card_x + pad_x, cy), bullet, fill=bc, font=body_font)
                for li, line in enumerate(wrapped):
                    draw.text((card_x + pad_x + bw, cy + li * line_h_b),
                              line, fill=text_col, font=body_font)
                cy += len(wrapped) * line_h_b + line_gap
        elif text:
            for line in self._wrap_text(text, body_font, max_w):
                draw.text((card_x + pad_x, cy), line, fill=text_col, font=body_font)
                cy += line_h_b

        return y + card_h

    def _draw_instruction_text(self, draw, frame, element, y):
        """Section title banner — orange bar with white bold text."""
        text = element.get("text", "")
        s = self.scale
        font = _get_font(int(48 * s), bold=True)

        pad_x = int(36 * s)
        pad_y = int(18 * s)
        banner_h = int(font.size * 1.3) + 2 * pad_y

        # Orange banner full width
        draw.rounded_rectangle(
            [self.content_x, y, self.content_x + self.content_w, y + banner_h],
            radius=int(8 * s), fill=self._rgb("orange"),
        )

        # White bold text centered
        tw = draw.textlength(text, font=font)
        x = self.content_x + (self.content_w - tw) / 2
        draw.text((x, y + pad_y), text, fill=(255, 255, 255), font=font)

        return y + banner_h

    def _draw_step_label(self, draw, frame, element, y):
        """Step heading — bold blue label shown above body content for each step."""
        text = element.get("text", "")
        if not text.strip():
            return y
        s = self.scale
        if len(text) > 80:
            text = text[:77] + "..."
        font = _get_font(int(42 * s), bold=True)
        pad_y = int(12 * s)
        tw = draw.textlength(text, font=font)
        x = (self.width - tw) / 2
        draw.text((x, y + pad_y), text, fill=self._rgb("blue"), font=font)
        return y + int(font.size * 1.5) + pad_y

    def _draw_image(self, frame, element, y, max_y):
        src = element.get("src_path", "")
        if not src or not os.path.exists(src):
            return y
        try:
            img = Image.open(src).convert("RGBA")
            size = element.get("size", "medium")
            max_ratio = {"small": 0.3, "medium": 0.5, "large": 0.7, "full": 0.9}
            ratio = max_ratio.get(size, 0.5)
            target_w = int(self.content_w * ratio)
            max_h = int((max_y - y) * 0.8)
            img.thumbnail((target_w, max_h), Image.LANCZOS)
            x = (self.width - img.width) // 2
            frame.paste(img, (x, int(y)), img if img.mode == "RGBA" else None)
            return y + img.height
        except Exception:
            return y

    def _draw_svg(self, frame, element, y, max_y):
        src = element.get("src_path", "")
        if not src or not os.path.exists(src):
            return y
        try:
            import cairosvg
            import io
            target_w = int(self.content_w * 0.5)
            png_data = cairosvg.svg2png(url=src, output_width=target_w)
            img = Image.open(io.BytesIO(png_data)).convert("RGBA")
            x = (self.width - img.width) // 2
            frame.paste(img, (x, int(y)), img)
            return y + img.height
        except Exception:
            return y

    def _draw_table(self, draw, frame, element, y):
        """Table with blue header row — PPT style."""
        headers = element.get("headers", [])
        rows = element.get("rows", [])
        s = self.scale
        font = _get_font(int(36 * s))
        header_font = _get_font(int(38 * s), bold=True)

        cols = len(headers)
        if cols == 0:
            return y

        table_w = self.content_w
        col_w = int(table_w / cols)
        row_h = int(64 * s)
        cx = self.content_x

        # Header row — blue background
        for i, h in enumerate(headers):
            x = cx + i * col_w
            draw.rectangle(
                [x, y, x + col_w, y + row_h],
                fill=self._rgb("blue"),
            )
            draw.text(
                (x + int(12 * s), y + int(10 * s)),
                str(h), fill=(255, 255, 255), font=header_font,
            )

        # Data rows
        for j, row in enumerate(rows):
            for i, cell in enumerate(row):
                x = cx + i * col_w
                ry = y + (j + 1) * row_h
                bg = self._rgb("card_bg") if j % 2 == 0 else self._rgb("bg")
                draw.rectangle([x, ry, x + col_w, ry + row_h], fill=bg)
                draw.text(
                    (x + int(12 * s), ry + int(10 * s)),
                    str(cell), fill=self._rgb("body_text"), font=font,
                )

        total_h = (len(rows) + 1) * row_h
        return y + total_h

    # ------------------------------------------------------------------
    # ACTIVE WORD BADGE
    # ------------------------------------------------------------------

    def _get_active_word(self, word_timestamps, current_time):
        """Return the word currently being spoken."""
        for wt in word_timestamps:
            if wt["start"] <= current_time <= wt["end"]:
                return wt["word"]
        return None

    def _draw_active_word(self, draw, word):
        """Draw a small orange badge at the bottom center with the current word."""
        s = self.scale
        font = _get_font(int(34 * s), bold=True)
        pad_x = int(28 * s)
        pad_y = int(10 * s)
        badge_h = font.size + 2 * pad_y
        badge_margin = int(12 * s)

        tw = draw.textlength(word, font=font)
        badge_w = tw + 2 * pad_x
        bx = (self.width - badge_w) / 2
        by = self.height - badge_h - badge_margin

        draw.rounded_rectangle(
            [bx, by, bx + badge_w, by + badge_h],
            radius=int(8 * s), fill=self._rgb("accent_stripe"),
        )
        draw.text(
            (bx + pad_x, by + pad_y),
            word, fill=(255, 255, 255), font=font,
        )
        return badge_h + badge_margin

    def _draw_timeline(self, draw, frame, element, y):
        """Chronological timeline for History, Science, etc.

        JSON: { "target": "timeline",
                "heading": "Important Events",
                "events": [{"year": "1947", "event": "Independence Day", "highlight": true}, ...] }
        """
        heading = element.get("heading", "")
        events  = element.get("events", [])
        s       = self.scale

        head_f  = _get_font(int(40 * s), bold=True)
        year_f  = _get_font(int(36 * s), bold=True)
        evt_f   = _get_font(int(34 * s), bold=False)
        pad_x   = int(36 * s)
        pad_y   = int(18 * s)
        row_h   = int(max(year_f.size, evt_f.size) * 1.9)
        head_h  = int(head_f.size * 1.5) if heading else 0
        card_h  = head_h + len(events) * row_h + 2 * pad_y
        dot_r   = int(10 * s)
        year_w  = int(self.content_w * 0.22)
        line_x  = self.content_x + pad_x + year_w + int(20 * s)

        cx = self.content_x
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(10 * s), fill=(240, 248, 255),
        )
        draw.rectangle([cx, y, cx + int(5 * s), y + card_h], fill=self._rgb("blue"))

        # Vertical timeline bar
        if events:
            bar_top = y + pad_y + head_h + row_h // 2
            bar_bot = y + pad_y + head_h + (len(events) - 1) * row_h + row_h // 2
            draw.rectangle([line_x - int(2*s), bar_top, line_x + int(2*s), bar_bot],
                           fill=self._rgb("blue"))

        cy = y + pad_y
        if heading:
            draw.text((cx + pad_x, cy), heading, fill=self._rgb("blue"), font=head_f)
            cy += head_h

        for evt in events:
            hl     = evt.get("highlight", False)
            yr     = str(evt.get("year", ""))
            txt    = str(evt.get("event", ""))
            dot_y  = cy + (row_h - dot_r * 2) // 2
            dot_c  = self._rgb("orange") if hl else self._rgb("blue")
            # Year label
            draw.text((cx + pad_x, cy + (row_h - year_f.size) // 2),
                      yr, fill=self._rgb("blue"), font=year_f)
            # Dot on bar
            draw.ellipse([line_x - dot_r, dot_y, line_x + dot_r, dot_y + dot_r * 2],
                         fill=dot_c)
            # Event text
            max_w = self.content_w - year_w - pad_x * 2 - int(40 * s)
            wrapped = self._wrap_text(txt, evt_f, max_w)
            ec = self._rgb("orange") if hl else self._rgb("body_text")
            ef = _get_font(int(34 * s), bold=hl)
            for li, line in enumerate(wrapped[:2]):
                draw.text((line_x + dot_r + int(16 * s),
                           cy + (row_h - ef.size) // 2 + li * int(ef.size * 1.2)),
                          line, fill=ec, font=ef)
            cy += row_h
        return y + card_h

    def _draw_chem_equation(self, draw, frame, element, y):
        """Chemical equation with arrow and conditions.

        JSON: { "target": "chem_equation",
                "reactants": "2H2 + O2",
                "products": "2H2O",
                "conditions": "High Temp / Catalyst",
                "reversible": false }
        """
        reactants  = element.get("reactants", "")
        products   = element.get("products",  "")
        conditions = element.get("conditions","")
        reversible = element.get("reversible", False)
        s          = self.scale

        chem_f  = _get_font(int(56 * s), bold=True)
        cond_f  = _get_font(int(32 * s), bold=False)
        pad_x   = int(48 * s)
        pad_y   = int(32 * s)
        arrow   = " \u21cc " if reversible else " \u2192 "   # ⇌ or →
        eq_text = reactants + arrow + products

        eq_w    = draw.textlength(eq_text, font=chem_f)
        cond_w  = draw.textlength(conditions, font=cond_f) if conditions else 0
        card_w  = self.content_w
        line_h  = chem_f.size
        card_h  = line_h + (cond_f.size + int(12*s) if conditions else 0) + 2 * pad_y

        cx = self.content_x
        draw.rounded_rectangle(
            [cx, y, cx + card_w, y + card_h],
            radius=int(12 * s), fill=(232, 245, 233),
        )
        draw.rectangle([cx, y, cx + int(6*s), y + card_h], fill=self._rgb("green"))

        # Centered equation
        draw.text((cx + (card_w - eq_w) / 2, y + pad_y), eq_text,
                  fill=self._rgb("green"), font=chem_f)
        if conditions:
            cy = y + pad_y + line_h + int(10 * s)
            draw.text((cx + (card_w - cond_w) / 2, cy),
                      f"Conditions: {conditions}", fill=self._rgb("body_secondary"), font=cond_f)
        return y + card_h

    def _draw_flow_chart(self, draw, frame, element, y):
        """Process flow diagram — boxes with arrows between them.

        JSON: { "target": "flow_chart",
                "heading": "Photosynthesis",
                "steps": [{"text": "Light Energy", "color": "orange"},
                           {"text": "Chlorophyll", "color": "green"}, ...] }
        """
        heading = element.get("heading", "")
        steps   = element.get("steps",   [])
        s       = self.scale

        head_f  = _get_font(int(38 * s), bold=True)
        step_f  = _get_font(int(36 * s), bold=False)
        pad_x   = int(24 * s)
        pad_y   = int(18 * s)
        box_h   = int(step_f.size * 1.8)
        arr_h   = int(28 * s)
        head_h  = int(head_f.size * 1.5) if heading else 0
        total_h = head_h + len(steps) * box_h + max(0, len(steps)-1) * arr_h + 2 * pad_y

        cx = self.content_x
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + total_h],
            radius=int(10 * s), fill=(255, 253, 231),
        )
        draw.rectangle([cx, y, cx + int(5*s), y + total_h], fill=self._rgb("orange"))

        cy = y + pad_y
        if heading:
            draw.text((cx + pad_x * 2, cy), heading, fill=self._rgb("orange"), font=head_f)
            cy += head_h

        COLOR_MAP = {"orange": (239,108,0), "green": (46,125,50),
                     "blue": (21,101,192), "red": (198,40,40)}
        box_w = self.content_w - pad_x * 4

        for i, step in enumerate(steps):
            txt  = step.get("text", step) if isinstance(step, dict) else str(step)
            clr  = step.get("color", "blue") if isinstance(step, dict) else "blue"
            fc   = COLOR_MAP.get(clr, COLOR_MAP["blue"])
            bg   = tuple(min(255, c + 200) for c in fc)

            bx = cx + pad_x * 2
            draw.rounded_rectangle(
                [bx, cy, bx + box_w, cy + box_h],
                radius=int(8 * s), fill=bg, outline=fc, width=int(2*s),
            )
            tw = draw.textlength(txt, font=step_f)
            draw.text((bx + (box_w - tw) / 2, cy + (box_h - step_f.size) / 2),
                      txt, fill=fc, font=step_f)
            cy += box_h
            if i < len(steps) - 1:
                ax = bx + box_w // 2
                draw.line([(ax, cy), (ax, cy + arr_h - int(6*s))], fill=(100,100,100), width=int(2*s))
                # Arrow head
                hw = int(10 * s)
                draw.polygon([(ax - hw, cy + arr_h - int(12*s)),
                               (ax + hw, cy + arr_h - int(12*s)),
                               (ax,      cy + arr_h)], fill=(100,100,100))
                cy += arr_h
        return y + total_h

    def _draw_t_account(self, draw, frame, element, y):
        """T-Account for Accounts subject — debit left, credit right.

        JSON: { "target": "t_account",
                "name": "Cash Account",
                "debit":  [{"desc": "Opening Balance", "amount": "50,000"}, ...],
                "credit": [{"desc": "Purchases",       "amount": "80,000"}, ...] }
        """
        name   = element.get("name", "Account")
        debits = element.get("debit",  [])
        credits= element.get("credit", [])
        s      = self.scale

        name_f = _get_font(int(42 * s), bold=True)
        hdr_f  = _get_font(int(32 * s), bold=True)
        row_f  = _get_font(int(30 * s), bold=False)
        pad    = int(20 * s)
        row_h  = int(row_f.size * 1.8)
        name_h = int(name_f.size * 1.5)
        hdr_h  = int(hdr_f.size * 1.6)
        max_rows = max(len(debits), len(credits), 1)
        card_h = name_h + hdr_h + max_rows * row_h + 2 * pad
        half   = self.content_w // 2
        cx     = self.content_x

        # Outer card
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(10 * s), fill=(255, 255, 255),
            outline=self._rgb("blue"), width=int(2*s),
        )
        # Account name banner
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + name_h],
            radius=int(10 * s), fill=self._rgb("header_bg"),
        )
        nw = draw.textlength(name, font=name_f)
        draw.text((cx + (self.content_w - nw) / 2, y + (name_h - name_f.size) / 2),
                  name, fill=(255,255,255), font=name_f)

        # Column headers
        hy = y + name_h
        draw.rectangle([cx, hy, cx + half, hy + hdr_h], fill=(230,240,255))
        draw.rectangle([cx + half, hy, cx + self.content_w, hy + hdr_h], fill=(255,235,230))
        draw.text((cx + pad, hy + (hdr_h - hdr_f.size) / 2),
                  "Dr (Debit)", fill=self._rgb("blue"), font=hdr_f)
        draw.text((cx + half + pad, hy + (hdr_h - hdr_f.size) / 2),
                  "Cr (Credit)", fill=self._rgb("red"), font=hdr_f)
        # Center divider
        draw.line([(cx + half, hy), (cx + half, y + card_h)], fill=self._rgb("blue"), width=int(2*s))

        # Rows
        ry = y + name_h + hdr_h
        for i in range(max_rows):
            row_bg = (248,251,255) if i % 2 == 0 else (255,255,255)
            draw.rectangle([cx + int(3*s), ry, cx + self.content_w - int(3*s), ry + row_h], fill=row_bg)
            # Debit row
            if i < len(debits):
                d = debits[i]
                draw.text((cx + pad, ry + (row_h - row_f.size) / 2),
                          str(d.get("desc", "")), fill=self._rgb("body_text"), font=row_f)
                amt = str(d.get("amount", ""))
                aw  = draw.textlength(amt, font=row_f)
                draw.text((cx + half - aw - pad, ry + (row_h - row_f.size) / 2),
                          amt, fill=self._rgb("blue"), font=row_f)
            # Credit row
            if i < len(credits):
                c = credits[i]
                draw.text((cx + half + pad, ry + (row_h - row_f.size) / 2),
                          str(c.get("desc", "")), fill=self._rgb("body_text"), font=row_f)
                amt = str(c.get("amount", ""))
                aw  = draw.textlength(amt, font=row_f)
                draw.text((cx + self.content_w - aw - pad, ry + (row_h - row_f.size) / 2),
                          amt, fill=self._rgb("red"), font=row_f)
            ry += row_h
        return y + card_h

    def _draw_memory_trick(self, draw, frame, element, y):
        """Mnemonic / memory trick display for any subject.

        JSON: { "target": "memory_trick",
                "label":     "Remember using:",
                "trick":     "VIBGYOR",
                "expansion": "Violet Indigo Blue Green Yellow Orange Red",
                "note":      "Colors of visible spectrum" }
        """
        label     = element.get("label",     "Memory Trick")
        trick     = element.get("trick",     "")
        expansion = element.get("expansion", "")
        note      = element.get("note",      "")
        s         = self.scale

        lbl_f   = _get_font(int(32 * s), bold=False)
        trick_f = _get_font(int(72 * s), bold=True)
        exp_f   = _get_font(int(36 * s), bold=False)
        note_f  = _get_font(int(28 * s), bold=False)
        pad_x   = int(48 * s)
        pad_y   = int(24 * s)

        trick_h = trick_f.size
        exp_h   = exp_f.size if expansion else 0
        note_h  = note_f.size + int(8*s) if note else 0
        lbl_h   = lbl_f.size + int(8*s)
        card_h  = lbl_h + trick_h + (int(16*s) if expansion else 0) + exp_h + note_h + 2 * pad_y

        cx = self.content_x
        # Gradient-style card (amber background)
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(12 * s), fill=(255, 248, 220),
        )
        draw.rectangle([cx, y, cx + int(6*s), y + card_h], fill=self._rgb("orange"))

        cy = y + pad_y
        draw.text((cx + pad_x, cy), label, fill=self._rgb("body_secondary"), font=lbl_f)
        cy += lbl_h

        # Big trick text centered with colored letters
        letters = list(trick)
        COLORS  = [(239,108,0),(21,101,192),(46,125,50),(198,40,40),(123,31,162),(0,131,143),(136,14,79)]
        total_w = draw.textlength(trick, font=trick_f)
        tx = cx + (self.content_w - total_w) / 2
        for li, ch in enumerate(letters):
            cw = draw.textlength(ch, font=trick_f)
            draw.text((tx, cy), ch, fill=COLORS[li % len(COLORS)], font=trick_f)
            tx += cw
        cy += trick_h + int(16 * s)

        if expansion:
            ew = draw.textlength(expansion, font=exp_f)
            draw.text((cx + (self.content_w - ew) / 2, cy),
                      expansion, fill=self._rgb("body_text"), font=exp_f)
            cy += exp_h

        if note:
            cy += int(8 * s)
            draw.text((cx + pad_x, cy), note, fill=self._rgb("body_secondary"), font=note_f)
        return y + card_h

    def _draw_video_clip(self, draw, frame, element, y):
        """Display first frame of a video asset with caption overlay.

        JSON: { "target": "video_clip",
                "src_path": "/path/to/clip.mp4",   (resolved by pipeline)
                "caption":  "Simple Pendulum Motion" }
        """
        src_path = element.get("src_path", "")
        caption  = element.get("caption", "Video Clip")
        s        = self.scale

        # Try to extract first frame via ffmpeg
        frame_img = None
        if src_path and os.path.exists(src_path):
            import subprocess, tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            tmp.close()
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", src_path, "-vframes", "1", tmp.name],
                    capture_output=True, timeout=10,
                )
                if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
                    frame_img = Image.open(tmp.name).convert("RGB")
            except Exception:
                pass
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

        avail_h = int(self.height * 0.38)
        avail_w = self.content_w
        cx      = self.content_x
        cap_h   = int(48 * s)
        img_h   = avail_h - cap_h

        # Draw background
        draw.rounded_rectangle(
            [cx, y, cx + avail_w, y + avail_h],
            radius=int(10 * s), fill=(20, 20, 30),
        )

        if frame_img:
            ratio   = min(avail_w / frame_img.width, img_h / frame_img.height)
            new_w   = int(frame_img.width  * ratio)
            new_h   = int(frame_img.height * ratio)
            frame_img = frame_img.resize((new_w, new_h), Image.LANCZOS)
            paste_x = cx + (avail_w - new_w) // 2
            paste_y = y  + (img_h   - new_h) // 2
            frame.paste(frame_img, (paste_x, paste_y))
        else:
            # Placeholder
            play_f = _get_font(int(48 * s), bold=True)
            draw.text((cx + avail_w // 2 - int(20*s), y + img_h // 2 - int(24*s)),
                      "\u25b6", fill=(255,255,255), font=play_f)

        # Caption bar
        cap_y  = y + img_h
        draw.rectangle([cx, cap_y, cx + avail_w, cap_y + cap_h], fill=(40,40,60))
        cap_f  = _get_font(int(30 * s), bold=False)
        cw     = draw.textlength(caption, font=cap_f)
        draw.text((cx + (avail_w - cw) / 2, cap_y + (cap_h - cap_f.size) / 2),
                  caption, fill=(200, 200, 255), font=cap_f)
        return y + avail_h

    def _draw_analogy(self, draw, frame, element, y):
        """Analogy display for Reasoning subject: A : B :: C : ?

        JSON: { "target": "analogy",
                "pairs": [["Dog", "Bark"], ["Cat", "?"]],
                "relation": "Animal : Sound",
                "answer": "Meow" }
        """
        pairs    = element.get("pairs",    [])
        relation = element.get("relation", "")
        answer   = element.get("answer",   "")
        s        = self.scale

        head_f  = _get_font(int(36 * s), bold=True)
        pair_f  = _get_font(int(58 * s), bold=True)
        sep_f   = _get_font(int(52 * s), bold=False)
        ans_f   = _get_font(int(56 * s), bold=True)
        pad_x   = int(40 * s)
        pad_y   = int(28 * s)
        card_h  = int(pair_f.size * 2.2) + 2 * pad_y + (head_f.size + int(12*s) if relation else 0)

        cx = self.content_x
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(12 * s), fill=(243, 229, 245),
        )
        draw.rectangle([cx, y, cx + int(6*s), y + card_h], fill=(123, 31, 162))

        cy = y + pad_y
        if relation:
            draw.text((cx + pad_x, cy), f"Relation: {relation}",
                      fill=(123, 31, 162), font=head_f)
            cy += head_f.size + int(12*s)

        # Build analogy string
        parts = []
        for i, pair in enumerate(pairs):
            a = str(pair[0]) if len(pair) > 0 else ""
            b = str(pair[1]) if len(pair) > 1 else "?"
            parts.append(f"{a} : {b}")
            if i < len(pairs) - 1:
                parts.append(" :: ")

        x = cx + pad_x
        COLORS = [(21,101,192), (46,125,50), (239,108,0), (198,40,40)]
        for pi, part in enumerate(parts):
            if part.strip() == "::":
                pw = draw.textlength(part, font=sep_f)
                draw.text((x, cy + (pair_f.size - sep_f.size) // 2),
                          part, fill=(100,100,100), font=sep_f)
            else:
                pw  = draw.textlength(part, font=pair_f)
                col = COLORS[pi // 2 % len(COLORS)]
                f   = ans_f if "?" in part and answer else pair_f
                draw.text((x, cy), part.replace("?", answer if answer else "?"),
                          fill=col, font=f)
            x += draw.textlength(part, font=pair_f)
        return y + card_h

    def _draw_number_line(self, draw, frame, element, y):
        """Number line for Math — with marks and highlights.

        JSON: { "target": "number_line",
                "start": -5, "end": 10,
                "marks": [0, 3, 7],
                "highlight": [3, 7],
                "label": "Number Line" }
        """
        start     = element.get("start",     0)
        end       = element.get("end",       10)
        marks     = element.get("marks",     [])
        highlight = set(element.get("highlight", []))
        label     = element.get("label",     "")
        s         = self.scale

        lbl_f  = _get_font(int(34 * s), bold=True)
        num_f  = _get_font(int(28 * s), bold=False)
        pad_x  = int(60 * s)
        pad_y  = int(28 * s)
        card_h = int(120 * s) + (lbl_f.size + int(16*s) if label else 0)
        line_y = y + pad_y + (lbl_f.size + int(16*s) if label else 0) + int(30 * s)
        line_w = self.content_w - pad_x * 2

        cx = self.content_x
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(10 * s), fill=(240, 248, 255),
        )
        draw.rectangle([cx, y, cx + int(5*s), y + card_h], fill=self._rgb("blue"))

        if label:
            draw.text((cx + pad_x, y + pad_y), label, fill=self._rgb("blue"), font=lbl_f)

        # Main line
        lx0 = cx + pad_x
        lx1 = cx + pad_x + line_w
        draw.line([(lx0, line_y), (lx1, line_y)], fill=self._rgb("blue"), width=int(3*s))
        # Arrow heads
        aw = int(12 * s)
        draw.polygon([(lx1, line_y), (lx1-aw, line_y-aw//2), (lx1-aw, line_y+aw//2)],
                     fill=self._rgb("blue"))
        draw.polygon([(lx0, line_y), (lx0+aw, line_y-aw//2), (lx0+aw, line_y+aw//2)],
                     fill=self._rgb("blue"))

        span = max(end - start, 1)
        def to_x(v):
            return lx0 + int((v - start) / span * line_w)

        tick_h = int(12 * s)
        all_marks = sorted(set([start, end] + marks))
        for m in all_marks:
            mx  = to_x(m)
            hl  = m in highlight
            col = self._rgb("orange") if hl else self._rgb("blue")
            r   = int(8 * s) if hl else int(4 * s)
            draw.ellipse([mx - r, line_y - r, mx + r, line_y + r], fill=col)
            lbl = str(m)
            lw  = draw.textlength(lbl, font=num_f)
            draw.text((mx - lw / 2, line_y + tick_h + int(4*s)), lbl, fill=col, font=num_f)
        return y + card_h

    # ------------------------------------------------------------------
    def _draw_watermark(self, frame, current_time):
        """Draw a semi-transparent watermark that shifts position every 4 seconds."""
        wm = self.watermark
        if not wm.get("enabled"):
            return

        s          = self.scale
        img_path   = wm.get("image_path", "")
        text       = wm.get("text", "")
        opacity    = int(wm.get("opacity", 0.35) * 255)

        # 8 positions (relative x,y) — cycle every 4 s, stays below header
        positions = [
            (0.07, 0.26), (0.70, 0.26),
            (0.07, 0.65), (0.70, 0.65),
            (0.38, 0.46), (0.20, 0.56),
            (0.55, 0.32), (0.48, 0.68),
        ]
        rx, ry = positions[int(current_time / 4) % len(positions)]
        px = int(rx * self.width)
        py = int(ry * self.height)

        if img_path and os.path.exists(img_path):
            try:
                wm_img = Image.open(img_path).convert("RGBA")
                max_w  = int(self.width * 0.12)
                ratio  = max_w / max(wm_img.width, 1)
                new_w, new_h = max_w, max(1, int(wm_img.height * ratio))
                wm_img = wm_img.resize((new_w, new_h), Image.LANCZOS)
                *_, a = wm_img.split()
                a = a.point(lambda v: min(v, opacity))
                wm_img.putalpha(a)
                px = min(px, self.width  - new_w - 10)
                py = min(py, self.height - new_h - 10)
                frame.paste(wm_img, (max(0, px), max(0, py)), wm_img)
            except Exception:
                pass
        elif text:
            font    = _get_font(int(28 * s), bold=False)
            overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            odraw   = ImageDraw.Draw(overlay)
            odraw.text((px + 1, py + 1), text, fill=(0, 0, 0, opacity // 2), font=font)
            odraw.text((px,     py    ), text, fill=(255, 255, 255, opacity), font=font)
            composited = Image.alpha_composite(frame.convert("RGBA"), overlay)
            frame.paste(composited.convert("RGB"))

    # ------------------------------------------------------------------
    def _draw_karaoke_strip(self, draw, narration, current_time, strip_y, strip_h):
        """Simple sentence line — no word highlighting, just plain centered text."""
        s   = self.scale
        wts = narration.get("word_timestamps", [])
        if not wts:
            return

        # Find current word index
        cur_idx = -1
        for i, wt in enumerate(wts):
            if wt["start"] <= current_time <= wt["end"]:
                cur_idx = i
                break
        if cur_idx == -1:
            for i in range(len(wts) - 1, -1, -1):
                if wts[i]["start"] <= current_time:
                    cur_idx = i
                    break
        if cur_idx == -1:
            return

        # Find sentence boundaries (words ending with . ? !)
        sent_start = 0
        for i in range(cur_idx - 1, -1, -1):
            if wts[i]["word"].rstrip()[-1:] in ('.', '?', '!'):
                sent_start = i + 1
                break
        sent_end = len(wts) - 1
        for i in range(cur_idx, len(wts)):
            sent_end = i
            if wts[i]["word"].rstrip()[-1:] in ('.', '?', '!'):
                break

        sentence_text = " ".join(wt["word"] for wt in wts[sent_start:sent_end + 1])

        # Draw strip background
        draw.rectangle([0, strip_y, self.width, strip_y + strip_h],
                       fill=(26, 35, 126))

        # Single plain white centered line
        font = _get_font(int(36 * s), bold=False)
        max_w = self.width - int(80 * s)

        # Trim sentence if too wide (from left)
        words = sentence_text.split()
        while len(words) > 1:
            test = " ".join(words)
            if draw.textlength(test, font=font) <= max_w:
                break
            words.pop(0)
        text = " ".join(words)

        tw = draw.textlength(text, font=font)
        x  = (self.width - tw) // 2
        y  = strip_y + (strip_h - font.size) // 2
        draw.text((x, y), text, fill=(255, 255, 255), font=font)

    # NARRATION BAR (word-by-word karaoke — kept for reference)
    # ------------------------------------------------------------------

    def _estimate_narration_height(self, draw, word_timestamps):
        s = self.scale
        font = _get_font(int(30 * s), bold=True)
        space_w = draw.textlength(" ", font=font)
        max_w = self.content_w - int(40 * s)

        num_lines = 1
        line_w = 0
        for wt in word_timestamps:
            word_w = draw.textlength(wt["word"], font=font)
            needed = (space_w if line_w > 0 else 0) + word_w
            if line_w > 0 and line_w + needed > max_w:
                num_lines += 1
                line_w = word_w
            else:
                line_w += needed

        line_h = int(font.size * 1.5)
        return num_lines * line_h + int(24 * s)

    def _draw_narration(self, draw, frame, narration, current_time, y):
        """Word-by-word karaoke — dark navy bar matching header."""
        word_timestamps = narration.get("word_timestamps", [])
        if not word_timestamps:
            return y

        s = self.scale
        font = _get_font(int(30 * s), bold=True)
        space_w = draw.textlength(" ", font=font)
        max_w = self.content_w - int(40 * s)

        # Build lines with word coloring
        lines = []
        current_line = []
        line_w = 0

        spoken_color = self._rgb("narration_spoken")
        active_color = self._rgb("narration_active")
        pending_color = self._rgb("narration_pending")

        for wt in word_timestamps:
            word = wt["word"]
            w_start = wt["start"]
            w_end = wt["end"]
            word_w = draw.textlength(word, font=font)

            if w_end <= current_time:
                color = spoken_color
                active = False
            elif w_start <= current_time:
                color = active_color
                active = True
            else:
                color = pending_color
                active = False

            needed = (space_w if line_w > 0 else 0) + word_w
            if line_w > 0 and line_w + needed > max_w:
                lines.append(current_line)
                current_line = []
                line_w = 0
                needed = word_w

            current_line.append({
                "word": word, "color": color,
                "width": word_w, "active": active,
            })
            line_w += needed

        if current_line:
            lines.append(current_line)

        # Draw dark navy bar
        line_h = int(font.size * 1.5)
        pad_y = int(12 * s)
        total_h = len(lines) * line_h + 2 * pad_y

        draw.rounded_rectangle(
            [self.margin_x, y, self.margin_x + self.usable_w, y + total_h],
            radius=int(8 * s), fill=self._rgb("narration_bg"),
        )

        # Orange top accent
        draw.rectangle(
            [self.margin_x, y, self.margin_x + self.usable_w, y + int(3 * s)],
            fill=self._rgb("accent_stripe"),
        )

        # Draw words
        text_y = y + pad_y + int(3 * s)
        for line in lines:
            total_line_w = sum(wd["width"] for wd in line)
            total_line_w += space_w * max(0, len(line) - 1)
            cx = (self.width - total_line_w) / 2

            for wd in line:
                draw.text((cx, text_y), wd["word"], fill=wd["color"], font=font)
                if wd["active"]:
                    uy = text_y + font.size + int(2 * s)
                    draw.line(
                        [cx, uy, cx + wd["width"], uy],
                        fill=self._rgb("narration_active"), width=int(3 * s),
                    )
                cx += wd["width"] + space_w

            text_y += line_h

        return y + total_h

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _wrap_text(self, text, font, max_width):
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            try:
                tw = font.getlength(test)
            except AttributeError:
                tw = len(test) * font.size * 0.6
            if tw <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    # ------------------------------------------------------------------
    # builtin_visual — pure Pillow subject illustrations (no external files)
    # ------------------------------------------------------------------

    def _draw_builtin_visual(self, draw, frame, element, y):
        """Draw a copyright-free subject illustration using pure Pillow geometry.

        JSON:
          { "target": "builtin_visual",
            "visual": "cell|dna|atom|circuit|beaker|pendulum|
                       food_chain|force|optics|clock|teacher|leaf",
            "label":  "Animal Cell Structure",
            "color":  "blue|green|orange|red"   (optional tint)
          }
        """
        visual = element.get("visual", "")
        label  = element.get("label", "")
        color  = element.get("color", "blue")
        s      = self.scale

        color_map = {
            "blue":   (21,  101, 192),
            "green":  (46,  125, 50),
            "orange": (239, 108, 0),
            "red":    (198, 40,  40),
            "purple": (94,  53,  177),
        }
        accent = color_map.get(color, color_map["blue"])
        bg_col = tuple(min(255, c + 210) for c in accent)   # very light tint

        card_h = int(280 * s)
        cx     = self.content_x
        cw     = self.content_w
        lbl_f  = _get_font(int(34 * s), bold=True)

        # Card background
        draw.rounded_rectangle(
            [cx, y, cx + cw, y + card_h],
            radius=int(12 * s), fill=bg_col,
        )
        draw.rectangle([cx, y, cx + int(6 * s), y + card_h], fill=accent)

        # Label at top-left
        if label:
            draw.text((cx + int(24 * s), y + int(14 * s)), label,
                      fill=accent, font=lbl_f)

        # Drawing canvas for the illustration (centred inside card)
        draw_y   = y + (lbl_f.size + int(28 * s) if label else int(20 * s))
        draw_h   = card_h - (lbl_f.size + int(40 * s) if label else int(30 * s))
        draw_cx  = cx + cw // 2
        draw_cy  = draw_y + draw_h // 2

        fn = {
            # ── Biology ──────────────────────────────────────────────────
            "cell":                self._vi_cell,
            "plant_cell":          self._vi_plant_cell,
            "dna":                 self._vi_dna,
            "leaf":                self._vi_leaf,
            "food_chain":          self._vi_food_chain,
            "heart":               self._vi_heart,
            "neuron":              self._vi_neuron,
            "eye":                 self._vi_eye,
            "blood_cells":         self._vi_blood_cells,
            "mitosis":             self._vi_mitosis,
            "osmosis":             self._vi_osmosis,
            "punnett_square":      self._vi_punnett_square,
            "ecosystem_pyramid":   self._vi_ecosystem_pyramid,
            "water_cycle":         self._vi_water_cycle,
            "nitrogen_cycle":      self._vi_nitrogen_cycle,
            "virus":               self._vi_virus,
            "bacteria":            self._vi_bacteria,
            "digestive_system":    self._vi_digestive_system,
            # ── Physics ──────────────────────────────────────────────────
            "atom":                self._vi_atom,
            "circuit":             self._vi_circuit,
            "pendulum":            self._vi_pendulum,
            "optics":              self._vi_optics,
            "force":               self._vi_force,
            "wave":                self._vi_wave,
            "concave_mirror":      self._vi_concave_mirror,
            "convex_mirror":       self._vi_convex_mirror,
            "bar_magnet":          self._vi_bar_magnet,
            "solenoid":            self._vi_solenoid,
            "projectile":          self._vi_projectile,
            "inclined_plane":      self._vi_inclined_plane,
            "transformer":         self._vi_transformer,
            "capacitor":           self._vi_capacitor,
            "nuclear_fission":     self._vi_nuclear_fission,
            "photoelectric":       self._vi_photoelectric,
            "circular_motion":     self._vi_circular_motion,
            "pulley":              self._vi_pulley,
            "pressure_column":     self._vi_pressure_column,
            "carnot_engine":       self._vi_carnot_engine,
            # ── Chemistry ────────────────────────────────────────────────
            "beaker":              self._vi_beaker,
            "molecule":            self._vi_molecule,
            "periodic_element":    self._vi_periodic_element,
            "ph_scale":            self._vi_ph_scale,
            "electrolysis":        self._vi_electrolysis,
            "galvanic_cell":       self._vi_galvanic_cell,
            "bond_ionic":          self._vi_bond_ionic,
            "bond_covalent":       self._vi_bond_covalent,
            "benzene":             self._vi_benzene,
            "activation_energy":   self._vi_activation_energy,
            "test_tube":           self._vi_test_tube,
            "distillation":        self._vi_distillation,
            # ── Math ─────────────────────────────────────────────────────
            "clock":               self._vi_clock,
            "venn_diagram":        self._vi_venn_diagram,
            "coordinate_plane":    self._vi_coordinate_plane,
            "pie_chart":           self._vi_pie_chart,
            "bar_chart":           self._vi_bar_chart,
            "triangle_parts":      self._vi_triangle_parts,
            "circle_parts":        self._vi_circle_parts,
            "number_pattern":      self._vi_number_pattern,
            "fraction_visual":     self._vi_fraction_visual,
            "normal_distribution": self._vi_normal_distribution,
            # ── Geography ────────────────────────────────────────────────
            "compass":             self._vi_compass,
            "rock_cycle":          self._vi_rock_cycle,
            "climate_zones":       self._vi_climate_zones,
            "river_landforms":     self._vi_river_landforms,
            # ── Civics / Polity ───────────────────────────────────────────
            "government_structure":self._vi_government_structure,
            "parliament":          self._vi_parliament,
            # ── Economics ────────────────────────────────────────────────
            "supply_demand":       self._vi_supply_demand,
            "production_possibility": self._vi_ppf,
            # ── Computer Science ─────────────────────────────────────────
            "flowchart":           self._vi_flowchart,
            "binary_tree":         self._vi_binary_tree,
            "stack_visual":        self._vi_stack_visual,
            "queue_visual":        self._vi_queue_visual,
            "array_visual":        self._vi_array_visual,
            "osi_layers":          self._vi_osi_layers,
            # ── Reasoning ────────────────────────────────────────────────
            "seating_circle":      self._vi_seating_circle,
            "direction_sense":     self._vi_direction_sense,
            "blood_relation":      self._vi_blood_relation,
            # ── Universal ────────────────────────────────────────────────
            "teacher":             self._vi_teacher,
            "comparison_table":    self._vi_comparison_table,
            "steps_visual":        self._vi_steps_visual,
            "lightbulb":           self._vi_lightbulb,
            "trophy":              self._vi_trophy,
            "timeline_visual":     self._vi_timeline_visual,
        }.get(visual)

        if fn:
            fn(draw, frame, cx, draw_y, cw, draw_h, draw_cx, draw_cy, accent, s)

        return y + card_h

    # ── Individual illustration drawers ─────────────────────────────────

    def _vi_cell(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Animal cell — oval membrane + nucleus + organelles."""
        rw = int(cw * 0.38)
        rh = int(dh * 0.72)
        # Outer membrane
        draw.ellipse([mx - rw, my - rh, mx + rw, my + rh],
                     outline=accent, width=int(4 * s))
        # Nucleus (dark filled ellipse, offset left)
        nw, nh = int(rw * 0.40), int(rh * 0.38)
        nx, ny = mx - int(rw * 0.18), my - int(rh * 0.08)
        draw.ellipse([nx - nw, ny - nh, nx + nw, ny + nh],
                     fill=tuple(max(0, c - 40) for c in accent),
                     outline=(255, 255, 255), width=int(2 * s))
        # Nucleolus (white dot inside nucleus)
        nd = int(nw * 0.28)
        draw.ellipse([nx - nd, ny - nd, nx + nd, ny + nd], fill=(255, 255, 255))
        # Mitochondria (small rounded rect, right side)
        for i, (ox, oy) in enumerate([(int(rw*0.35), 0), (int(rw*0.20), int(rh*0.40))]):
            mw2, mh2 = int(rw * 0.22), int(rh * 0.14)
            draw.rounded_rectangle(
                [mx + ox - mw2, my + oy - mh2, mx + ox + mw2, my + oy + mh2],
                radius=int(mh2 * 0.5), outline=accent, width=int(2 * s),
            )
        # Vacuole (small circle, bottom right)
        vr = int(rh * 0.12)
        draw.ellipse([mx + int(rw*0.15) - vr, my + int(rh*0.40) - vr,
                      mx + int(rw*0.15) + vr, my + int(rh*0.40) + vr],
                     outline=accent, width=int(2 * s))

    def _vi_dna(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """DNA double helix — two sine-wave strands with rungs."""
        import math
        x0, x1 = cx + int(cw * 0.12), cx + int(cw * 0.88)
        amp     = int(dh * 0.30)
        steps   = 40
        pts_a, pts_b = [], []
        for i in range(steps + 1):
            t  = i / steps
            x  = x0 + int(t * (x1 - x0))
            ya = my + int(amp * math.sin(t * 4 * math.pi))
            yb = my + int(amp * math.sin(t * 4 * math.pi + math.pi))
            pts_a.append((x, ya))
            pts_b.append((x, yb))
        # Draw strands
        for i in range(len(pts_a) - 1):
            draw.line([pts_a[i], pts_a[i + 1]], fill=accent, width=int(3 * s))
            draw.line([pts_b[i], pts_b[i + 1]],
                      fill=tuple(min(255, c + 80) for c in accent), width=int(3 * s))
        # Base pair rungs every ~4 steps
        for i in range(0, steps + 1, 4):
            draw.line([pts_a[i], pts_b[i]], fill=(150, 150, 150), width=int(2 * s))

    def _vi_atom(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Bohr model atom — nucleus + 3 electron orbits."""
        import math
        # Nucleus
        nr = int(min(cw, dh) * 0.07)
        draw.ellipse([mx - nr, my - nr, mx + nr, my + nr], fill=accent)
        # Orbits
        orbits = [(int(cw * 0.22), 0), (int(cw * 0.30), 55), (int(cw * 0.40), 30)]
        for rx, angle_deg in orbits:
            ry = int(rx * 0.45)
            # Rotate bounding box by angle
            a  = math.radians(angle_deg)
            # Draw rotated ellipse approximation using arc-like polygon
            pts = []
            for t in range(0, 361, 8):
                rad = math.radians(t)
                ex  = rx * math.cos(rad)
                ey  = ry * math.sin(rad)
                # rotate by angle
                px2 = ex * math.cos(a) - ey * math.sin(a)
                py2 = ex * math.sin(a) + ey * math.cos(a)
                pts.append((mx + int(px2 * s * 0.9), my + int(py2 * s * 0.9)))
            if len(pts) >= 2:
                draw.line(pts, fill=accent, width=int(2 * s))
            # Electron dot
            er   = int(6 * s)
            e_t  = 0.7  # t position for electron
            rad2 = math.radians(t * e_t)
            ex   = rx * math.cos(rad2)
            ey   = ry * math.sin(rad2)
            px2  = ex * math.cos(a) - ey * math.sin(a)
            py2  = ex * math.sin(a) + ey * math.cos(a)
            ex2  = mx + int(px2 * s * 0.9)
            ey2  = my + int(py2 * s * 0.9)
            draw.ellipse([ex2 - er, ey2 - er, ex2 + er, ey2 + er],
                         fill=(255, 220, 50))

    def _vi_circuit(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Simple series circuit — battery, resistor, bulb."""
        # Outer rectangle loop
        lx = cx + int(cw * 0.10)
        rx = cx + int(cw * 0.90)
        ty = my - int(dh * 0.28)
        by = my + int(dh * 0.28)
        w  = int(3 * s)
        lw = int(rx - lx)
        lh = int(by - ty)
        # Draw wires
        draw.line([(lx, ty), (rx, ty)], fill=(80, 80, 80), width=w)   # top
        draw.line([(lx, by), (rx, by)], fill=(80, 80, 80), width=w)   # bottom
        draw.line([(lx, ty), (lx, by)], fill=(80, 80, 80), width=w)   # left
        # Right wire in two halves (bulb in middle)
        draw.line([(rx, ty), (rx, my - int(dh*0.12))], fill=(80,80,80), width=w)
        draw.line([(rx, my + int(dh*0.12)), (rx, by)], fill=(80,80,80), width=w)
        # Battery on bottom-left
        bx = lx + int(lw * 0.20)
        for i, (h, col) in enumerate([(14, accent), (9, (200,200,200))]):
            bh = int(h * s)
            bxi = bx + i * int(10 * s)
            draw.line([(bxi, by - int(20*s)), (bxi, by + int(20*s))],
                      fill=col, width=int(4 * s))
        # Resistor (zigzag) on top-center
        zx0 = lx + int(lw * 0.35)
        zx1 = lx + int(lw * 0.65)
        zy  = ty
        zpts = [(zx0, zy)]
        segs = 6
        sw   = (zx1 - zx0) // segs
        for i in range(segs):
            zxm = zx0 + i * sw + sw // 2
            zpts.append((zxm, zy - int(14 * s) if i % 2 == 0 else zy + int(14 * s)))
        zpts.append((zx1, zy))
        draw.line(zpts, fill=accent, width=w)
        # Bulb on right (circle + cross)
        br  = int(18 * s)
        draw.ellipse([rx - br, my - br, rx + br, my + br],
                     outline=(255, 200, 0), width=int(3 * s))
        draw.line([(rx - int(br*0.6), my - int(br*0.6)),
                   (rx + int(br*0.6), my + int(br*0.6))],
                  fill=(255, 200, 0), width=int(2 * s))
        draw.line([(rx + int(br*0.6), my - int(br*0.6)),
                   (rx - int(br*0.6), my + int(br*0.6))],
                  fill=(255, 200, 0), width=int(2 * s))

    def _vi_beaker(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Chemistry beaker with liquid and bubbles."""
        bw  = int(cw * 0.28)
        bh  = int(dh * 0.82)
        bx0 = mx - bw // 2
        bx1 = mx + bw // 2
        by0 = my - bh // 2
        by1 = my + bh // 2
        w   = int(3 * s)
        # Beaker outline (trapezoid — wider at top)
        tw  = int(bw * 1.12)
        draw.polygon([
            (mx - tw // 2, by0), (mx + tw // 2, by0),
            (mx + bw // 2, by1), (mx - bw // 2, by1),
        ], outline=accent, width=w)
        # Liquid fill (2/3 height)
        liq_y  = by0 + bh // 3
        liq_col = tuple(min(255, c + 150) for c in accent)
        draw.polygon([
            (mx - bw // 2 + w, liq_y), (mx + bw // 2 - w, liq_y),
            (mx + bw // 2 - w, by1 - w), (mx - bw // 2 + w, by1 - w),
        ], fill=liq_col)
        # Spout
        draw.line([(mx + tw // 2, by0), (mx + tw // 2 + int(20 * s), by0 - int(10 * s))],
                  fill=accent, width=w)
        # Bubbles
        import math
        for i, (bxo, byo, br) in enumerate([
            (int(-bw * 0.15), int(bh * 0.12), int(7 * s)),
            (int(bw * 0.10),  int(bh * 0.25), int(5 * s)),
            (int(-bw * 0.05), int(bh * 0.38), int(6 * s)),
        ]):
            bxc = mx + bxo
            byc = liq_y + byo
            draw.ellipse([bxc - br, byc - br, bxc + br, byc + br],
                         outline=(255, 255, 255), width=int(2 * s))

    def _vi_pendulum(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Simple pendulum — pivot + string + bob + arc path."""
        import math
        pivot_y = my - int(dh * 0.38)
        str_len = int(dh * 0.60)
        angle   = 35   # degrees from vertical
        rad     = math.radians(angle)
        bob_x   = mx + int(str_len * math.sin(rad))
        bob_y   = pivot_y + int(str_len * math.cos(rad))
        bob_r   = int(18 * s)
        # Ceiling mount
        draw.line([(mx - int(30*s), pivot_y), (mx + int(30*s), pivot_y)],
                  fill=(100, 100, 100), width=int(4 * s))
        draw.rectangle([mx - int(6*s), pivot_y - int(4*s),
                         mx + int(6*s), pivot_y + int(4*s)], fill=(100,100,100))
        # Arc (dashed path) — draw arc approximation with dots
        for t in range(-35, 36, 5):
            ar = math.radians(t)
            ax = mx + int(str_len * math.sin(ar))
            ay = pivot_y + int(str_len * math.cos(ar))
            r2 = int(3 * s)
            draw.ellipse([ax - r2, ay - r2, ax + r2, ay + r2],
                         fill=(180, 180, 180))
        # String
        draw.line([(mx, pivot_y), (bob_x, bob_y)], fill=accent, width=int(2 * s))
        # Pivot dot
        pr = int(6 * s)
        draw.ellipse([mx - pr, pivot_y - pr, mx + pr, pivot_y + pr], fill=accent)
        # Bob
        draw.ellipse([bob_x - bob_r, bob_y - bob_r,
                      bob_x + bob_r, bob_y + bob_r], fill=accent)
        # Velocity arrow
        draw.line([(bob_x - int(28*s), bob_y + int(8*s)),
                   (bob_x - int(6*s),  bob_y + int(8*s))],
                  fill=(239,108,0), width=int(3*s))
        draw.polygon([(bob_x - int(6*s), bob_y + int(8*s)),
                      (bob_x - int(14*s), bob_y + int(2*s)),
                      (bob_x - int(14*s), bob_y + int(14*s))],
                     fill=(239,108,0))

    def _vi_food_chain(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Food chain: Sun → Grass → Rabbit → Fox (horizontal with arrows)."""
        labels = ["Sun", "Grass", "Rabbit", "Fox"]
        n      = len(labels)
        step   = cw // (n + 1)
        fy     = my
        r      = int(dh * 0.28)
        colors = [(255, 200, 0), (46, 125, 50), (150, 100, 50), (198, 40, 40)]
        xs     = [cx + step * (i + 1) for i in range(n)]
        lbl_f  = _get_font(int(26 * s), bold=True)
        for i, (lx, lbl, col) in enumerate(zip(xs, labels, colors)):
            draw.ellipse([lx - r, fy - r, lx + r, fy + r], fill=col)
            tw = draw.textlength(lbl, font=lbl_f)
            draw.text((lx - tw // 2, fy + r + int(6 * s)), lbl,
                      fill=(60, 60, 60), font=lbl_f)
            if i < n - 1:
                ax0 = lx + r + int(4 * s)
                ax1 = xs[i + 1] - r - int(4 * s)
                draw.line([(ax0, fy), (ax1, fy)], fill=accent, width=int(2 * s))
                draw.polygon([(ax1, fy), (ax1 - int(12*s), fy - int(6*s)),
                               (ax1 - int(12*s), fy + int(6*s))], fill=accent)

    def _vi_force(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Force diagram — object with labelled force arrows."""
        # Central box (object)
        bw, bh = int(cw * 0.14), int(dh * 0.24)
        draw.rounded_rectangle([mx - bw, my - bh, mx + bw, my + bh],
                                radius=int(8 * s), fill=(230, 230, 230),
                                outline=accent, width=int(3 * s))
        obj_f = _get_font(int(26 * s), bold=True)
        draw.text((mx - int(draw.textlength("Object", font=obj_f) / 2),
                   my - obj_f.size // 2), "Object", fill=accent, font=obj_f)
        # Arrows: up (Normal), down (Weight), right (Applied), left (Friction)
        arr = int(dh * 0.30)
        arrow_defs = [
            (0,  -arr - bh, 0, -bh, "Normal N",   (46, 125, 50)),
            (0,   bh,       0,  arr + bh, "Weight W",  (198, 40, 40)),
            (bw,  0,        bw + arr, 0,  "F applied", (21, 101, 192)),
            (-bw - arr, 0,  -bw, 0, "Friction f", (239, 108, 0)),
        ]
        lbl_f = _get_font(int(24 * s), bold=False)
        for x0, y0, x1, y1, lbl, col in arrow_defs:
            draw.line([(mx + x0, my + y0), (mx + x1, my + y1)],
                      fill=col, width=int(3 * s))
            # Arrowhead
            dx = x1 - x0
            dy2 = y1 - y0
            length = max(1, (dx**2 + dy2**2) ** 0.5)
            ux, uy = dx / length, dy2 / length
            perp = (-uy * 8 * s, ux * 8 * s)
            tip  = (mx + x1, my + y1)
            draw.polygon([
                tip,
                (tip[0] - ux * 16 * s + perp[0], tip[1] - uy * 16 * s + perp[1]),
                (tip[0] - ux * 16 * s - perp[0], tip[1] - uy * 16 * s - perp[1]),
            ], fill=col)
            draw.text((mx + x1 + int(4 * s), my + y1 - int(14 * s)),
                      lbl, fill=col, font=lbl_f)

    def _vi_optics(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Convex lens with incident and refracted rays."""
        import math
        # Lens (vertical oval)
        lw, lh = int(cw * 0.04), int(dh * 0.65)
        draw.ellipse([mx - lw, my - lh // 2, mx + lw, my + lh // 2],
                     fill=(173, 216, 230), outline=accent, width=int(3 * s))
        # Optical axis
        ax0 = cx + int(cw * 0.06)
        ax1 = cx + int(cw * 0.94)
        draw.line([(ax0, my), (ax1, my)], fill=(180, 180, 180), width=int(1 * s))
        # Focal point
        focal = int(cw * 0.22)
        fr    = int(5 * s)
        draw.ellipse([mx + focal - fr, my - fr, mx + focal + fr, my + fr],
                     fill=(239, 108, 0))
        f_f = _get_font(int(22 * s))
        draw.text((mx + focal + int(8 * s), my - int(22 * s)), "F",
                  fill=(239, 108, 0), font=f_f)
        # Incident rays (parallel, from left)
        for offset in [-int(dh * 0.22), 0, int(dh * 0.22)]:
            ix0, iy0 = ax0, my + offset
            ix1, iy1 = mx, my + offset
            draw.line([(ix0, iy0), (ix1, iy1)], fill=accent, width=int(2 * s))
            # Refracted to focal point
            draw.line([(ix1, iy1), (mx + focal, my)],
                      fill=(239, 108, 0), width=int(2 * s))

    def _vi_clock(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Analog clock — for Time & Work problems."""
        import math
        cr  = int(min(cw, dh) * 0.38)
        # Clock face
        draw.ellipse([mx - cr, my - cr, mx + cr, my + cr],
                     fill=(255, 255, 255), outline=accent, width=int(4 * s))
        # Hour marks
        for i in range(12):
            ang  = math.radians(i * 30 - 90)
            r0   = cr - int(8 * s)
            r1   = cr - int(18 * s) if i % 3 == 0 else cr - int(12 * s)
            x0   = mx + int(r0 * math.cos(ang))
            y0   = my + int(r0 * math.sin(ang))
            x1   = mx + int(r1 * math.cos(ang))
            y1   = my + int(r1 * math.sin(ang))
            draw.line([(x0, y0), (x1, y1)], fill=accent,
                      width=int(3 * s) if i % 3 == 0 else int(2 * s))
        # Hour hand (pointing to 10)
        ha  = math.radians(10 * 30 - 90)
        draw.line([(mx, my), (mx + int(cr * 0.55 * math.cos(ha)),
                              my + int(cr * 0.55 * math.sin(ha)))],
                  fill=accent, width=int(5 * s))
        # Minute hand (pointing to 12)
        ma  = math.radians(-90)
        draw.line([(mx, my), (mx + int(cr * 0.78 * math.cos(ma)),
                              my + int(cr * 0.78 * math.sin(ma)))],
                  fill=(50, 50, 50), width=int(3 * s))
        # Centre dot
        dr = int(7 * s)
        draw.ellipse([mx - dr, my - dr, mx + dr, my + dr], fill=accent)

    def _vi_teacher(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Stick-figure teacher with speech bubble."""
        # Head
        hr  = int(dh * 0.14)
        hx  = mx - int(cw * 0.10)
        hy  = my - int(dh * 0.28)
        draw.ellipse([hx - hr, hy - hr, hx + hr, hy + hr],
                     fill=(255, 220, 177), outline=accent, width=int(2 * s))
        # Body
        by0 = hy + hr
        by1 = my + int(dh * 0.20)
        draw.line([(hx, by0), (hx, by1)], fill=accent, width=int(3 * s))
        # Arms — left raised, right pointing
        draw.line([(hx, by0 + int(dh * 0.08)),
                   (hx - int(cw * 0.10), by0 - int(dh * 0.05))],
                  fill=accent, width=int(3 * s))
        draw.line([(hx, by0 + int(dh * 0.08)),
                   (hx + int(cw * 0.14), by0 + int(dh * 0.04))],
                  fill=accent, width=int(3 * s))
        # Legs
        draw.line([(hx, by1), (hx - int(cw * 0.06), by1 + int(dh * 0.18))],
                  fill=accent, width=int(3 * s))
        draw.line([(hx, by1), (hx + int(cw * 0.06), by1 + int(dh * 0.18))],
                  fill=accent, width=int(3 * s))
        # Speech bubble
        bx0 = hx + int(cw * 0.08)
        bx1 = cx + int(cw * 0.90)
        bby0 = hy - int(dh * 0.26)
        bby1 = hy + int(dh * 0.08)
        draw.rounded_rectangle([bx0, bby0, bx1, bby1],
                                radius=int(12 * s), fill=(255, 255, 255),
                                outline=accent, width=int(2 * s))
        # Bubble tail
        draw.polygon([(bx0, bby0 + int((bby1-bby0)*0.6)),
                      (bx0 - int(18*s), bby0 + int((bby1-bby0)*0.75)),
                      (bx0, bby0 + int((bby1-bby0)*0.85))],
                     fill=(255, 255, 255), outline=accent)
        sf = _get_font(int(26 * s), bold=True)
        btext = "Let's learn!"
        draw.text((bx0 + int(16 * s), bby0 + int((bby1 - bby0 - sf.size) / 2)),
                  btext, fill=accent, font=sf)

    def _vi_leaf(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Leaf cross-section — for biology (photosynthesis, plant structure)."""
        import math
        lw = int(cw * 0.36)
        lh = int(dh * 0.50)
        # Leaf outline (ellipse)
        draw.ellipse([mx - lw, my - lh, mx + lw, my + lh],
                     fill=(200, 240, 200), outline=(46, 125, 50), width=int(3 * s))
        # Midrib
        draw.line([(mx - lw, my), (mx + lw, my)],
                  fill=(46, 125, 50), width=int(3 * s))
        # Veins (diagonal)
        for i, side in enumerate([-1, 1]):
            for frac in [0.25, 0.50, 0.70]:
                vx0 = mx + int(side * lw * frac)
                vy0 = my
                vx1 = vx0 + int(side * lw * 0.18)
                vy1 = my - int(lh * 0.50)
                draw.line([(vx0, vy0), (vx1, vy1)],
                          fill=(46, 125, 50), width=int(2 * s))
        # Sun arrow (top-right)
        sun_x, sun_y = cx + int(cw * 0.82), dy + int(dh * 0.12)
        sr = int(12 * s)
        draw.ellipse([sun_x - sr, sun_y - sr, sun_x + sr, sun_y + sr],
                     fill=(255, 200, 0))
        draw.line([(sun_x, sun_y + sr + int(4*s)), (mx, my - lh)],
                  fill=(255, 200, 0), width=int(2 * s))

    def _vi_molecule(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Simple molecule diagram (e.g. H2O / CO2 style)."""
        # Central atom (Carbon / Oxygen)
        cr  = int(dh * 0.18)
        draw.ellipse([mx - cr, my - cr, mx + cr, my + cr], fill=accent)
        cf  = _get_font(int(28 * s), bold=True)
        draw.text((mx - int(draw.textlength("C", font=cf) / 2), my - cf.size // 2),
                  "C", fill=(255, 255, 255), font=cf)
        # Bonded atoms (left and right — Oxygen)
        bond_dist = int(cw * 0.28)
        or2       = int(cr * 0.80)
        for side, lbl in [(-1, "O"), (1, "O")]:
            bx = mx + side * bond_dist
            by = my
            # Bond line(s) — double bond
            draw.line([(mx + side * cr, my - int(4*s)),
                       (bx - side * or2, my - int(4*s))],
                      fill=(100, 100, 100), width=int(2 * s))
            draw.line([(mx + side * cr, my + int(4*s)),
                       (bx - side * or2, my + int(4*s))],
                      fill=(100, 100, 100), width=int(2 * s))
            col = (198, 40, 40)
            draw.ellipse([bx - or2, by - or2, bx + or2, by + or2], fill=col)
            draw.text((bx - int(draw.textlength(lbl, font=cf) / 2), by - cf.size // 2),
                      lbl, fill=(255, 255, 255), font=cf)

    def _vi_wave(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Transverse wave — amplitude, wavelength labels."""
        import math
        x0, x1 = cx + int(cw * 0.06), cx + int(cw * 0.94)
        amp = int(dh * 0.32)
        steps = 60
        pts = []
        for i in range(steps + 1):
            t  = i / steps
            x  = x0 + int(t * (x1 - x0))
            y2 = my + int(amp * math.sin(t * 4 * math.pi))
            pts.append((x, y2))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=accent, width=int(3 * s))
        # Equilibrium line
        draw.line([(x0, my), (x1, my)], fill=(180, 180, 180),
                  width=int(1 * s))
        # Amplitude arrow
        peak_x = x0 + (x1 - x0) // 8
        draw.line([(peak_x, my), (peak_x, my - amp)],
                  fill=(239, 108, 0), width=int(2 * s))
        af = _get_font(int(24 * s))
        draw.text((peak_x + int(6 * s), my - amp // 2 - af.size // 2),
                  "A", fill=(239, 108, 0), font=af)
        # Wavelength arrow (one full cycle)
        lam_x0 = x0 + (x1 - x0) // 4
        lam_x1 = x0 + (x1 - x0) * 3 // 4
        lam_y  = my + amp + int(20 * s)
        draw.line([(lam_x0, lam_y), (lam_x1, lam_y)],
                  fill=(21, 101, 192), width=int(2 * s))
        lf = _get_font(int(24 * s))
        tw = draw.textlength("λ", font=lf)
        draw.text(((lam_x0 + lam_x1) // 2 - int(tw / 2), lam_y + int(4 * s)),
                  "λ", fill=(21, 101, 192), font=lf)

    # ── BIOLOGY: New visuals ─────────────────────────────────────────

    def _vi_plant_cell(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Plant cell — rectangular wall, chloroplasts, central vacuole."""
        rw, rh = int(cw * 0.38), int(dh * 0.72)
        draw.rectangle([mx - rw, my - rh, mx + rw, my + rh], outline=accent, width=int(4 * s))
        draw.rectangle([mx - rw + int(8 * s), my - rh + int(8 * s),
                        mx + rw - int(8 * s), my + rh - int(8 * s)],
                       outline=accent, width=int(2 * s))
        vw, vh = int(rw * 0.55), int(rh * 0.50)
        draw.ellipse([mx - vw, my - vh, mx + vw, my + vh],
                     outline=(100, 180, 255), width=int(3 * s))
        f = _get_font(int(18 * s))
        draw.text((mx - int(30 * s), my - int(8 * s)), "Vacuole",
                  fill=(100, 150, 200), font=f)
        nw, nh = int(rw * 0.28), int(rh * 0.25)
        nx = mx - int(rw * 0.50)
        draw.ellipse([nx - nw, my - nh, nx + nw, my + nh],
                     fill=tuple(max(0, c - 40) for c in accent),
                     outline=(255, 255, 255), width=int(2 * s))
        for ox, oy in [(int(rw * 0.35), -int(rh * 0.45)),
                       (int(rw * 0.50), int(rh * 0.20)),
                       (-int(rw * 0.15), int(rh * 0.55))]:
            ew, eh = int(rw * 0.14), int(rh * 0.08)
            draw.ellipse([mx + ox - ew, my + oy - eh, mx + ox + ew, my + oy + eh],
                         fill=(34, 139, 34))
        draw.text((mx + int(rw * 0.20), my - int(rh * 0.55)),
                  "Chloroplast", fill=(34, 139, 34), font=f)

    def _vi_heart(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Heart — 4 chambers RA/LA/RV/LV."""
        rw, rh = int(cw * 0.30), int(dh * 0.40)
        draw.ellipse([mx - rw, my - rh, mx + rw, my + rh],
                     outline=(200, 60, 60), width=int(4 * s))
        draw.line([(mx, my - rh), (mx, my + rh)], fill=(200, 60, 60), width=int(3 * s))
        draw.line([(mx - rw, my), (mx + rw, my)], fill=(200, 60, 60), width=int(3 * s))
        f = _get_font(int(20 * s), bold=True)
        draw.text((mx - rw // 2 - int(12 * s), my - rh // 2 - int(10 * s)),
                  "LA", fill=(200, 60, 60), font=f)
        draw.text((mx + rw // 4 - int(4 * s), my - rh // 2 - int(10 * s)),
                  "RA", fill=(100, 60, 200), font=f)
        draw.text((mx - rw // 2 - int(12 * s), my + rh // 4 - int(4 * s)),
                  "LV", fill=(200, 60, 60), font=f)
        draw.text((mx + rw // 4 - int(4 * s), my + rh // 4 - int(4 * s)),
                  "RV", fill=(100, 60, 200), font=f)
        sf = _get_font(int(16 * s))
        draw.text((mx - rw - int(60 * s), my - rh // 2),
                  "Oxygenated", fill=(200, 60, 60), font=sf)
        draw.text((mx + rw + int(8 * s), my - rh // 2),
                  "Deoxygenated", fill=(100, 60, 200), font=sf)

    def _vi_neuron(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Neuron — dendrites, cell body, axon, terminal."""
        bx, by = mx - int(cw * 0.25), my
        br = int(dh * 0.18)
        draw.ellipse([bx - br, by - br, bx + br, by + br],
                     fill=accent, outline=(255, 255, 255), width=int(2 * s))
        f = _get_font(int(14 * s))
        draw.text((bx - int(14 * s), by - int(7 * s)), "Cell Body",
                  fill=(255, 255, 255), font=f)
        for dy2 in [-int(dh * 0.30), 0, int(dh * 0.30)]:
            dx = bx - br
            draw.line([(dx, by + dy2), (dx - int(cw * 0.12), by + dy2 - int(10 * s))],
                      fill=accent, width=int(2 * s))
            draw.line([(dx, by + dy2), (dx - int(cw * 0.12), by + dy2 + int(10 * s))],
                      fill=accent, width=int(2 * s))
        ax_end = mx + int(cw * 0.30)
        draw.line([(bx + br, by), (ax_end, by)], fill=accent, width=int(3 * s))
        for i in range(4):
            sx = bx + br + int(i * (ax_end - bx - br) / 4) + int(10 * s)
            sw = int((ax_end - bx - br) / 4 * 0.6)
            draw.rounded_rectangle([sx, by - int(10 * s), sx + sw, by + int(10 * s)],
                                   radius=int(5 * s), fill=(200, 200, 220))
        for dy2 in [-int(12 * s), 0, int(12 * s)]:
            draw.ellipse([ax_end, by + dy2 - int(5 * s),
                          ax_end + int(10 * s), by + dy2 + int(5 * s)], fill=accent)
        draw.text((bx - br - int(cw * 0.10), my - int(dh * 0.38)),
                  "Dendrites", fill=accent, font=f)
        draw.text((mx - int(10 * s), my + int(16 * s)), "Axon", fill=accent, font=f)

    def _vi_eye(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Eye cross-section — cornea, lens, retina, optic nerve."""
        rw, rh = int(cw * 0.32), int(dh * 0.38)
        draw.ellipse([mx - rw, my - rh, mx + rw, my + rh],
                     outline=accent, width=int(3 * s))
        lw = int(rw * 0.15)
        draw.ellipse([mx - int(rw * 0.30) - lw, my - int(rh * 0.50),
                      mx - int(rw * 0.30) + lw, my + int(rh * 0.50)],
                     outline=(100, 150, 255), width=int(3 * s))
        draw.arc([mx - rw, my - rh, mx + rw, my + rh], -60, 60,
                 fill=(200, 80, 80), width=int(6 * s))
        draw.line([(mx + rw, my), (mx + rw + int(40 * s), my + int(20 * s))],
                  fill=(200, 150, 50), width=int(4 * s))
        draw.arc([mx - rw, my - rh, mx + rw, my + rh], 150, 210,
                 fill=(150, 220, 255), width=int(5 * s))
        f = _get_font(int(16 * s))
        draw.text((mx - int(rw * 0.55), my - int(rh * 0.20)),
                  "Lens", fill=(100, 150, 255), font=f)
        draw.text((mx + int(rw * 0.55), my - int(5 * s)),
                  "Retina", fill=(200, 80, 80), font=f)
        draw.text((mx + rw + int(10 * s), my + int(25 * s)),
                  "Optic Nerve", fill=(200, 150, 50), font=f)
        draw.text((mx - rw - int(50 * s), my - int(5 * s)),
                  "Cornea", fill=(150, 220, 255), font=f)

    def _vi_blood_cells(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Three blood cell types: RBC, WBC, Platelet."""
        f = _get_font(int(18 * s), bold=True)
        sf = _get_font(int(15 * s))
        gap = int(cw * 0.28)
        for i, (label, color, sub) in enumerate([
            ("RBC", (200, 60, 60), "Red Blood Cell"),
            ("WBC", (100, 100, 220), "White Blood Cell"),
            ("Platelet", (180, 150, 220), "Thrombocyte"),
        ]):
            cx2 = mx + (i - 1) * gap
            r = int(dh * 0.22) if i < 2 else int(dh * 0.12)
            draw.ellipse([cx2 - r, my - r, cx2 + r, my + r],
                         fill=color, outline=(255, 255, 255), width=int(2 * s))
            if i == 0:
                draw.ellipse([cx2 - int(r * 0.4), my - int(r * 0.4),
                              cx2 + int(r * 0.4), my + int(r * 0.4)],
                             fill=tuple(max(0, c - 30) for c in color))
            elif i == 1:
                for ox, oy in [(-int(r * 0.2), -int(r * 0.2)),
                               (int(r * 0.2), int(r * 0.2))]:
                    draw.ellipse([cx2 + ox - int(r * 0.3), my + oy - int(r * 0.3),
                                  cx2 + ox + int(r * 0.3), my + oy + int(r * 0.3)],
                                 fill=tuple(min(255, c + 40) for c in color))
            tw = draw.textlength(label, font=f)
            draw.text((cx2 - tw // 2, my + r + int(8 * s)), label, fill=color, font=f)
            tw2 = draw.textlength(sub, font=sf)
            draw.text((cx2 - tw2 // 2, my + r + int(8 * s) + f.size + int(4 * s)),
                      sub, fill=(120, 120, 120), font=sf)

    def _vi_mitosis(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Mitosis — 4 phase boxes with arrows."""
        f = _get_font(int(16 * s), bold=True)
        phases = ["Prophase", "Metaphase", "Anaphase", "Telophase"]
        n = len(phases)
        bw = int(cw * 0.18)
        bh = int(dh * 0.60)
        gap = (cw - n * bw) / (n + 1)
        colors = [(180, 80, 80), (80, 140, 200), (80, 180, 80), (200, 140, 60)]
        for i, (ph, col) in enumerate(zip(phases, colors)):
            x = cx + int(gap * (i + 1) + bw * i)
            draw.rounded_rectangle([x, my - bh // 2, x + bw, my + bh // 2],
                                   radius=int(8 * s), outline=col, width=int(3 * s))
            tw = draw.textlength(ph, font=f)
            draw.text((x + (bw - tw) // 2, my + bh // 2 + int(8 * s)),
                      ph, fill=col, font=f)
            if i < n - 1:
                ax = x + bw + int(gap * 0.2)
                draw.line([(ax, my), (ax + int(gap * 0.5), my)],
                          fill=(150, 150, 150), width=int(2 * s))

    def _vi_osmosis(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Osmosis — membrane with water molecules moving."""
        rw, rh = int(cw * 0.38), int(dh * 0.40)
        draw.rectangle([mx - rw, my - rh, mx + rw, my + rh],
                       outline=(150, 150, 150), width=int(2 * s))
        for i in range(8):
            y1 = my - rh + i * (2 * rh) // 8
            y2 = y1 + rh // 8
            draw.line([(mx, y1), (mx, y2)], fill=accent, width=int(3 * s))
        f = _get_font(int(16 * s))
        draw.text((mx - int(30 * s), my - rh - int(22 * s)),
                  "Membrane", fill=accent, font=f)
        positions_left = [(-0.7, -0.5), (-0.5, -0.2), (-0.8, 0.1), (-0.3, 0.3),
                          (-0.6, 0.5), (-0.4, -0.6), (-0.2, 0.0), (-0.7, 0.4),
                          (-0.5, 0.6), (-0.3, -0.4), (-0.6, -0.1), (-0.4, 0.2)]
        for px, py in positions_left:
            x = mx + int(rw * px)
            y2 = my + int(rh * py)
            draw.ellipse([x - int(4 * s), y2 - int(4 * s),
                          x + int(4 * s), y2 + int(4 * s)], fill=(100, 180, 255))
        positions_right = [(0.3, -0.3), (0.5, 0.1), (0.7, 0.4), (0.4, -0.5), (0.6, 0.2)]
        for px, py in positions_right:
            x = mx + int(rw * px)
            y2 = my + int(rh * py)
            draw.ellipse([x - int(4 * s), y2 - int(4 * s),
                          x + int(4 * s), y2 + int(4 * s)], fill=(100, 180, 255))
        draw.line([(mx - int(30 * s), my + rh + int(15 * s)),
                   (mx + int(30 * s), my + rh + int(15 * s))],
                  fill=(239, 108, 0), width=int(2 * s))
        draw.text((mx - rw + int(5 * s), my + rh + int(6 * s)),
                  "High", fill=(100, 180, 255), font=f)
        draw.text((mx + rw - int(30 * s), my + rh + int(6 * s)),
                  "Low", fill=(100, 180, 255), font=f)

    def _vi_punnett_square(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Punnett square 2x2 genetics grid."""
        sz = int(min(cw * 0.12, dh * 0.28))
        f = _get_font(int(22 * s), bold=True)
        sf = _get_font(int(18 * s))
        x0, y0 = mx - sz, my - sz
        alleles = [["BB", "Bb"], ["Bb", "bb"]]
        parents = ["B", "b"]
        for r in range(2):
            for c in range(2):
                x = x0 + c * sz
                y = y0 + r * sz
                col = (80, 180, 80) if "B" in alleles[r][c] else (200, 100, 100)
                draw.rectangle([x, y, x + sz, y + sz], outline=accent, width=int(2 * s))
                txt = alleles[r][c]
                tw = draw.textlength(txt, font=f)
                draw.text((x + (sz - tw) // 2, y + (sz - f.size) // 2),
                          txt, fill=col, font=f)
        for c in range(2):
            tw = draw.textlength(parents[c], font=sf)
            draw.text((x0 + c * sz + (sz - tw) // 2, y0 - int(24 * s)),
                      parents[c], fill=accent, font=sf)
        for r in range(2):
            draw.text((x0 - int(24 * s), y0 + r * sz + (sz - sf.size) // 2),
                      parents[r], fill=accent, font=sf)

    def _vi_ecosystem_pyramid(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Energy pyramid — 4 tiers."""
        f = _get_font(int(16 * s), bold=True)
        tiers = ["Tertiary", "Secondary", "Primary", "Producers"]
        colors = [(200, 60, 60), (239, 108, 0), (80, 140, 200), (46, 125, 50)]
        n = len(tiers)
        tier_h = int(dh * 0.20)
        top_w = int(cw * 0.18)
        bot_w = int(cw * 0.70)
        y0 = my - int(n * tier_h / 2)
        for i, (t, col) in enumerate(zip(tiers, colors)):
            w = top_w + int((bot_w - top_w) * i / (n - 1))
            y = y0 + i * tier_h
            draw.rectangle([mx - w // 2, y, mx + w // 2, y + tier_h - int(4 * s)], fill=col)
            tw = draw.textlength(t, font=f)
            draw.text((mx - tw // 2, y + (tier_h - int(4 * s) - f.size) // 2),
                      t, fill=(255, 255, 255), font=f)

    def _vi_water_cycle(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Water cycle — sun, cloud, rain, river, evaporation."""
        f = _get_font(int(15 * s))
        sr = int(dh * 0.10)
        sx, sy = cx + int(cw * 0.12), dy + int(dh * 0.18)
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 200, 0))
        draw.text((sx - int(10 * s), sy + sr + int(4 * s)), "Sun",
                  fill=(200, 150, 0), font=f)
        clx, cly = mx + int(cw * 0.15), dy + int(dh * 0.15)
        for ox, oy, cr in [(0, 0, int(18 * s)), (int(15 * s), -int(5 * s), int(14 * s)),
                           (-int(15 * s), -int(3 * s), int(12 * s))]:
            draw.ellipse([clx + ox - cr, cly + oy - cr, clx + ox + cr, cly + oy + cr],
                         fill=(180, 200, 230))
        for i in range(4):
            rx = clx - int(12 * s) + i * int(10 * s)
            ry = cly + int(20 * s) + i * int(5 * s)
            draw.line([(rx, ry), (rx - int(3 * s), ry + int(10 * s))],
                      fill=(100, 150, 255), width=int(2 * s))
        draw.text((clx - int(15 * s), cly + int(35 * s)), "Rain",
                  fill=(100, 150, 255), font=f)
        gy = my + int(dh * 0.30)
        draw.line([(cx + int(cw * 0.05), gy), (cx + int(cw * 0.95), gy)],
                  fill=(139, 90, 43), width=int(3 * s))
        draw.line([(mx - int(cw * 0.15), gy + int(8 * s)),
                   (mx + int(cw * 0.20), gy + int(8 * s))],
                  fill=(60, 120, 220), width=int(4 * s))
        draw.line([(mx - int(cw * 0.12), gy - int(5 * s)),
                   (mx - int(cw * 0.05), dy + int(dh * 0.35))],
                  fill=(200, 100, 100), width=int(2 * s))
        draw.text((mx - int(cw * 0.22), my - int(dh * 0.08)),
                  "Evaporation", fill=(200, 100, 100), font=f)

    def _vi_nitrogen_cycle(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Nitrogen cycle — circular flow."""
        f = _get_font(int(14 * s))
        nodes = ["N2 (Air)", "Bacteria", "Plants", "Animals", "Decomposers"]
        n = len(nodes)
        r = int(min(cw, dh) * 0.30)
        colors = [(100, 150, 255), (200, 100, 100), (46, 125, 50),
                  (200, 150, 60), (150, 100, 60)]
        for i, (nd, col) in enumerate(zip(nodes, colors)):
            angle = -math.pi / 2 + 2 * math.pi * i / n
            nx = mx + int(r * math.cos(angle))
            ny = my + int(r * math.sin(angle))
            nr = int(dh * 0.10)
            draw.ellipse([nx - nr, ny - nr, nx + nr, ny + nr],
                         fill=col, outline=(255, 255, 255), width=int(2 * s))
            tw = draw.textlength(nd, font=f)
            draw.text((nx - tw // 2, ny - f.size // 2), nd,
                      fill=(255, 255, 255), font=f)

    def _vi_virus(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Virus — icosahedral with spikes."""
        r = int(min(cw, dh) * 0.18)
        pts = [(mx + int(r * math.cos(math.pi * 2 * i / 6)),
                my + int(r * math.sin(math.pi * 2 * i / 6))) for i in range(6)]
        draw.polygon(pts, fill=tuple(min(255, c + 180) for c in accent),
                     outline=accent, width=int(3 * s))
        for i in range(12):
            angle = math.pi * 2 * i / 12
            x1 = mx + int(r * math.cos(angle))
            y1 = my + int(r * math.sin(angle))
            x2 = mx + int((r + int(18 * s)) * math.cos(angle))
            y2 = my + int((r + int(18 * s)) * math.sin(angle))
            draw.line([(x1, y1), (x2, y2)], fill=accent, width=int(2 * s))
            draw.ellipse([x2 - int(4 * s), y2 - int(4 * s),
                          x2 + int(4 * s), y2 + int(4 * s)], fill=accent)
        draw.ellipse([mx - int(r * 0.35), my - int(r * 0.35),
                      mx + int(r * 0.35), my + int(r * 0.35)],
                     outline=accent, width=int(2 * s))
        f = _get_font(int(14 * s))
        draw.text((mx - int(12 * s), my - int(7 * s)), "DNA", fill=accent, font=f)

    def _vi_bacteria(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Bacteria — rod shape with flagella."""
        rw, rh = int(cw * 0.20), int(dh * 0.16)
        draw.rounded_rectangle([mx - rw, my - rh, mx + rw, my + rh],
                               radius=rh, fill=accent)
        draw.ellipse([mx - int(rw * 0.30), my - int(rh * 0.40),
                      mx + int(rw * 0.30), my + int(rh * 0.40)],
                     outline=(255, 255, 255), width=int(2 * s))
        for dy2 in [-int(8 * s), 0, int(8 * s)]:
            pts = []
            for i in range(15):
                x = mx + rw + int(i * 4 * s)
                y = my + dy2 + int(5 * s * math.sin(i * 0.8))
                pts.append((x, y))
            for j in range(len(pts) - 1):
                draw.line([pts[j], pts[j + 1]], fill=accent, width=int(2 * s))
        f = _get_font(int(16 * s))
        draw.text((mx - int(20 * s), my + rh + int(10 * s)),
                  "Rod Bacterium", fill=accent, font=f)

    def _vi_digestive_system(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Digestive system — simplified vertical path."""
        f = _get_font(int(15 * s))
        parts = ["Mouth", "Esophagus", "Stomach", "Sm. Intestine", "Lg. Intestine"]
        n = len(parts)
        step_h = int(dh * 0.17)
        y0 = dy + int(dh * 0.04)
        colors = [(200, 120, 120), (180, 140, 100), (200, 160, 80),
                  (120, 180, 120), (100, 140, 160)]
        for i, (p, col) in enumerate(zip(parts, colors)):
            y = y0 + i * step_h
            bw = int(cw * 0.22)
            draw.rounded_rectangle([mx - bw, y, mx + bw, y + step_h - int(6 * s)],
                                   radius=int(6 * s), fill=col)
            tw = draw.textlength(p, font=f)
            draw.text((mx - tw // 2, y + (step_h - int(6 * s) - f.size) // 2),
                      p, fill=(255, 255, 255), font=f)
            if i < n - 1:
                draw.line([(mx, y + step_h - int(6 * s)), (mx, y + step_h)],
                          fill=(150, 150, 150), width=int(2 * s))

    # ── PHYSICS: New visuals ─────────────────────────────────────────

    def _vi_concave_mirror(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Concave mirror — curved mirror with C, F, rays converging."""
        draw.line([(cx + int(cw * 0.05), my), (cx + int(cw * 0.95), my)],
                  fill=(180, 180, 180), width=int(1 * s))
        mr_x = cx + int(cw * 0.80)
        draw.arc([mr_x - int(cw * 0.30), my - int(dh * 0.40),
                  mr_x + int(cw * 0.10), my + int(dh * 0.40)],
                 120, 240, fill=accent, width=int(4 * s))
        f = _get_font(int(16 * s))
        fp_x = cx + int(cw * 0.55)
        cp_x = cx + int(cw * 0.35)
        draw.ellipse([fp_x - int(3 * s), my - int(3 * s),
                      fp_x + int(3 * s), my + int(3 * s)], fill=(239, 108, 0))
        draw.text((fp_x - int(3 * s), my + int(8 * s)), "F",
                  fill=(239, 108, 0), font=f)
        draw.ellipse([cp_x - int(3 * s), my - int(3 * s),
                      cp_x + int(3 * s), my + int(3 * s)], fill=(200, 60, 60))
        draw.text((cp_x - int(3 * s), my + int(8 * s)), "C",
                  fill=(200, 60, 60), font=f)
        draw.line([(cx + int(cw * 0.10), my - int(dh * 0.25)), (mr_x, my - int(dh * 0.25))],
                  fill=(255, 200, 0), width=int(2 * s))
        draw.line([(mr_x, my - int(dh * 0.25)), (fp_x, my)],
                  fill=(255, 200, 0), width=int(2 * s))

    def _vi_convex_mirror(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Convex mirror — diverging rays."""
        draw.line([(cx + int(cw * 0.05), my), (cx + int(cw * 0.95), my)],
                  fill=(180, 180, 180), width=int(1 * s))
        mr_x = cx + int(cw * 0.80)
        draw.arc([mr_x - int(cw * 0.10), my - int(dh * 0.40),
                  mr_x + int(cw * 0.30), my + int(dh * 0.40)],
                 -60, 60, fill=accent, width=int(4 * s))
        f = _get_font(int(16 * s))
        fp_x = cx + int(cw * 0.90)
        draw.text((fp_x, my + int(8 * s)), "F", fill=(239, 108, 0), font=f)
        draw.line([(cx + int(cw * 0.10), my - int(dh * 0.20)), (mr_x, my - int(dh * 0.20))],
                  fill=(255, 200, 0), width=int(2 * s))
        draw.line([(mr_x, my - int(dh * 0.20)),
                   (mr_x - int(cw * 0.15), my - int(dh * 0.35))],
                  fill=(255, 200, 0), width=int(2 * s))
        draw.text((mx - int(20 * s), my + int(dh * 0.35)),
                  "Convex Mirror", fill=accent, font=f)

    def _vi_bar_magnet(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Bar magnet with field lines N/S."""
        mw, mh = int(cw * 0.28), int(dh * 0.14)
        draw.rectangle([mx - mw, my - mh, mx, my + mh], fill=(200, 60, 60))
        draw.rectangle([mx, my - mh, mx + mw, my + mh], fill=(80, 80, 200))
        f = _get_font(int(22 * s), bold=True)
        draw.text((mx - mw // 2 - int(6 * s), my - int(10 * s)),
                  "N", fill=(255, 255, 255), font=f)
        draw.text((mx + mw // 2 - int(6 * s), my - int(10 * s)),
                  "S", fill=(255, 255, 255), font=f)
        for dy2 in [-int(dh * 0.30), -int(dh * 0.18), int(dh * 0.18), int(dh * 0.30)]:
            draw.arc([mx - mw - int(cw * 0.12), my + dy2 - int(dh * 0.08),
                      mx + mw + int(cw * 0.12), my + dy2 + int(dh * 0.08)],
                     0, 180 if dy2 < 0 else 180, fill=(150, 150, 150), width=int(1 * s))

    def _vi_solenoid(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Solenoid — coil with magnetic field."""
        x0, x1 = cx + int(cw * 0.15), cx + int(cw * 0.85)
        coil_y_top = my - int(dh * 0.20)
        coil_y_bot = my + int(dh * 0.20)
        turns = 8
        for i in range(turns):
            tx = x0 + int(i * (x1 - x0) / turns)
            tx2 = x0 + int((i + 0.5) * (x1 - x0) / turns)
            draw.arc([tx, coil_y_top, tx2, coil_y_bot], 0, 180,
                     fill=accent, width=int(2 * s))
            draw.arc([tx, coil_y_top, tx2, coil_y_bot], 180, 360,
                     fill=tuple(max(0, c - 60) for c in accent), width=int(2 * s))
        draw.line([(mx, my), (x1 + int(20 * s), my)],
                  fill=(200, 60, 60), width=int(2 * s))
        f = _get_font(int(16 * s))
        draw.text((x1 + int(5 * s), my - int(20 * s)), "B field",
                  fill=(200, 60, 60), font=f)

    def _vi_projectile(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Projectile motion — parabolic path with velocity components."""
        x0 = cx + int(cw * 0.10)
        y_ground = my + int(dh * 0.35)
        draw.line([(x0, y_ground), (cx + int(cw * 0.90), y_ground)],
                  fill=(150, 150, 150), width=int(2 * s))
        pts = []
        for i in range(30):
            t = i / 29
            px = x0 + int(t * cw * 0.75)
            py = y_ground - int(4 * dh * 0.55 * t * (1 - t))
            pts.append((px, py))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=accent, width=int(3 * s))
        draw.ellipse([pts[0][0] - int(5 * s), pts[0][1] - int(5 * s),
                      pts[0][0] + int(5 * s), pts[0][1] + int(5 * s)], fill=accent)
        f = _get_font(int(16 * s))
        draw.text((x0 + int(10 * s), y_ground - int(dh * 0.15)),
                  "Vx", fill=(80, 140, 200), font=f)
        draw.text((x0 - int(5 * s), y_ground - int(dh * 0.45)),
                  "Vy", fill=(200, 60, 60), font=f)
        peak = pts[14]
        draw.text((peak[0] - int(20 * s), peak[1] - int(20 * s)),
                  "Max Height", fill=accent, font=f)

    def _vi_inclined_plane(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Inclined plane — ramp with force decomposition."""
        bx = cx + int(cw * 0.12)
        by = my + int(dh * 0.35)
        tx = cx + int(cw * 0.75)
        ty = my - int(dh * 0.30)
        draw.polygon([(bx, by), (tx, by), (tx, ty)], outline=accent, width=int(3 * s))
        obj_x = (bx + tx) // 2
        obj_y = (by + ty) // 2 + int(dh * 0.02)
        draw.rectangle([obj_x - int(12 * s), obj_y - int(12 * s),
                        obj_x + int(12 * s), obj_y + int(12 * s)],
                       fill=(239, 108, 0), outline=(255, 255, 255), width=int(2 * s))
        f = _get_font(int(16 * s))
        draw.line([(obj_x, obj_y), (obj_x, obj_y + int(30 * s))],
                  fill=(200, 60, 60), width=int(2 * s))
        draw.text((obj_x + int(5 * s), obj_y + int(20 * s)),
                  "mg", fill=(200, 60, 60), font=f)
        draw.text((bx + int(cw * 0.05), by + int(8 * s)),
                  "theta", fill=accent, font=f)

    def _vi_transformer(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Transformer — primary/secondary coils + iron core."""
        core_w = int(cw * 0.06)
        core_h = int(dh * 0.50)
        draw.rectangle([mx - int(cw * 0.15), my - core_h // 2,
                        mx - int(cw * 0.15) + core_w, my + core_h // 2],
                       fill=(100, 100, 100))
        draw.rectangle([mx + int(cw * 0.15) - core_w, my - core_h // 2,
                        mx + int(cw * 0.15), my + core_h // 2],
                       fill=(100, 100, 100))
        draw.rectangle([mx - int(cw * 0.15), my - core_h // 2,
                        mx + int(cw * 0.15), my - core_h // 2 + core_w],
                       fill=(100, 100, 100))
        draw.rectangle([mx - int(cw * 0.15), my + core_h // 2 - core_w,
                        mx + int(cw * 0.15), my + core_h // 2],
                       fill=(100, 100, 100))
        for i in range(6):
            cy = my - core_h // 2 + int((i + 0.5) * core_h / 6)
            draw.arc([mx - int(cw * 0.30), cy - int(8 * s),
                      mx - int(cw * 0.15), cy + int(8 * s)],
                     90, 270, fill=(200, 60, 60), width=int(2 * s))
        for i in range(8):
            cy = my - core_h // 2 + int((i + 0.5) * core_h / 8)
            draw.arc([mx + int(cw * 0.15), cy - int(6 * s),
                      mx + int(cw * 0.30), cy + int(6 * s)],
                     -90, 90, fill=(80, 140, 200), width=int(2 * s))
        f = _get_font(int(16 * s))
        draw.text((mx - int(cw * 0.38), my + core_h // 2 + int(8 * s)),
                  "Primary", fill=(200, 60, 60), font=f)
        draw.text((mx + int(cw * 0.10), my + core_h // 2 + int(8 * s)),
                  "Secondary", fill=(80, 140, 200), font=f)

    def _vi_capacitor(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Capacitor — parallel plates with E-field lines."""
        pw = int(4 * s)
        ph = int(dh * 0.55)
        gap = int(cw * 0.12)
        draw.rectangle([mx - gap // 2 - pw, my - ph // 2,
                        mx - gap // 2, my + ph // 2], fill=(200, 60, 60))
        draw.rectangle([mx + gap // 2, my - ph // 2,
                        mx + gap // 2 + pw, my + ph // 2], fill=(80, 80, 200))
        for i in range(5):
            ly = my - ph // 2 + int((i + 0.5) * ph / 5)
            draw.line([(mx - gap // 2 + int(4 * s), ly),
                       (mx + gap // 2 - int(4 * s), ly)],
                      fill=(150, 150, 150), width=int(1 * s))
        f = _get_font(int(18 * s), bold=True)
        draw.text((mx - gap // 2 - pw - int(20 * s), my - int(10 * s)),
                  "+", fill=(200, 60, 60), font=f)
        draw.text((mx + gap // 2 + pw + int(8 * s), my - int(10 * s)),
                  "-", fill=(80, 80, 200), font=f)
        sf = _get_font(int(16 * s))
        draw.text((mx - int(8 * s), my + ph // 2 + int(8 * s)),
                  "E", fill=(150, 150, 150), font=sf)

    def _vi_nuclear_fission(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Nuclear fission — large atom splits into two + neutrons."""
        r = int(dh * 0.18)
        draw.ellipse([mx - int(cw * 0.28) - r, my - r,
                      mx - int(cw * 0.28) + r, my + r],
                     fill=(100, 150, 255), outline=accent, width=int(3 * s))
        f = _get_font(int(16 * s))
        draw.text((mx - int(cw * 0.28) - int(16 * s), my - int(8 * s)),
                  "U-235", fill=(255, 255, 255), font=f)
        draw.line([(mx - int(cw * 0.10), my), (mx + int(cw * 0.05), my)],
                  fill=(239, 108, 0), width=int(2 * s))
        r2 = int(r * 0.65)
        draw.ellipse([mx + int(cw * 0.15) - r2, my - int(dh * 0.18) - r2,
                      mx + int(cw * 0.15) + r2, my - int(dh * 0.18) + r2],
                     fill=(80, 180, 80), outline=accent, width=int(2 * s))
        draw.ellipse([mx + int(cw * 0.15) - r2, my + int(dh * 0.18) - r2,
                      mx + int(cw * 0.15) + r2, my + int(dh * 0.18) + r2],
                     fill=(200, 100, 100), outline=accent, width=int(2 * s))
        for dx, dy2 in [(int(cw * 0.28), -int(dh * 0.10)),
                        (int(cw * 0.30), int(dh * 0.15)),
                        (int(cw * 0.32), 0)]:
            draw.ellipse([mx + dx - int(4 * s), my + dy2 - int(4 * s),
                          mx + dx + int(4 * s), my + dy2 + int(4 * s)],
                         fill=(255, 200, 0))
        draw.text((mx + int(cw * 0.25), my + int(dh * 0.30)),
                  "neutrons", fill=(200, 150, 0), font=f)

    def _vi_photoelectric(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Photoelectric effect — photon hitting metal, electron ejected."""
        pw, ph = int(cw * 0.15), int(dh * 0.50)
        plate_x = mx
        draw.rectangle([plate_x - pw // 2, my - ph // 2,
                        plate_x + pw // 2, my + ph // 2],
                       fill=(160, 160, 180), outline=accent, width=int(2 * s))
        f = _get_font(int(16 * s))
        draw.text((plate_x - int(16 * s), my + ph // 2 + int(8 * s)),
                  "Metal", fill=accent, font=f)
        for i in range(3):
            wy = my - int(dh * 0.15) + i * int(dh * 0.15)
            wx = plate_x - pw // 2 - int(cw * 0.25)
            pts = []
            for j in range(12):
                x = wx + int(j * cw * 0.02)
                y = wy + int(5 * s * math.sin(j * 1.2))
                pts.append((x, y))
            for j in range(len(pts) - 1):
                draw.line([pts[j], pts[j + 1]], fill=(255, 200, 0), width=int(2 * s))
        draw.text((wx - int(10 * s), my - int(dh * 0.30)),
                  "Photons", fill=(255, 200, 0), font=f)
        for i in range(2):
            ex = plate_x + pw // 2 + int(cw * 0.08) + i * int(cw * 0.10)
            ey = my - int(dh * 0.10) + i * int(dh * 0.15)
            draw.ellipse([ex - int(4 * s), ey - int(4 * s),
                          ex + int(4 * s), ey + int(4 * s)], fill=(80, 140, 200))
            draw.line([(plate_x + pw // 2, ey), (ex, ey)],
                      fill=(80, 140, 200), width=int(1 * s))
        draw.text((plate_x + pw // 2 + int(cw * 0.12), my - int(dh * 0.25)),
                  "e-", fill=(80, 140, 200), font=f)

    def _vi_circular_motion(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Circular motion — circle with centripetal and velocity arrows."""
        r = int(min(cw, dh) * 0.28)
        draw.ellipse([mx - r, my - r, mx + r, my + r],
                     outline=accent, width=int(2 * s))
        obj_x, obj_y = mx + r, my
        draw.ellipse([obj_x - int(8 * s), obj_y - int(8 * s),
                      obj_x + int(8 * s), obj_y + int(8 * s)], fill=(239, 108, 0))
        draw.line([(obj_x, obj_y), (mx + int(r * 0.5), obj_y)],
                  fill=(200, 60, 60), width=int(3 * s))
        draw.line([(obj_x, obj_y), (obj_x, obj_y - int(r * 0.5))],
                  fill=(80, 140, 200), width=int(3 * s))
        f = _get_font(int(16 * s))
        draw.text((mx + int(r * 0.4), obj_y + int(10 * s)),
                  "Fc", fill=(200, 60, 60), font=f)
        draw.text((obj_x + int(8 * s), obj_y - int(r * 0.4)),
                  "v", fill=(80, 140, 200), font=f)
        draw.ellipse([mx - int(3 * s), my - int(3 * s),
                      mx + int(3 * s), my + int(3 * s)], fill=accent)

    def _vi_pulley(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Pulley system — fixed pulley with rope and weights."""
        pr = int(dh * 0.10)
        py_top = dy + int(dh * 0.08)
        draw.line([(mx, dy), (mx, py_top)], fill=(100, 100, 100), width=int(3 * s))
        draw.ellipse([mx - pr, py_top - pr, mx + pr, py_top + pr],
                     outline=accent, width=int(3 * s))
        draw.ellipse([mx - int(3 * s), py_top - int(3 * s),
                      mx + int(3 * s), py_top + int(3 * s)], fill=accent)
        left_x = mx - pr
        right_x = mx + pr
        lh = int(dh * 0.50)
        rh_val = int(dh * 0.35)
        draw.line([(left_x, py_top), (left_x, py_top + lh)],
                  fill=(139, 90, 43), width=int(2 * s))
        draw.line([(right_x, py_top), (right_x, py_top + rh_val)],
                  fill=(139, 90, 43), width=int(2 * s))
        bsz = int(dh * 0.10)
        draw.rectangle([left_x - bsz, py_top + lh, left_x + bsz, py_top + lh + bsz],
                       fill=(200, 60, 60))
        draw.rectangle([right_x - bsz, py_top + rh_val, right_x + bsz, py_top + rh_val + bsz],
                       fill=(80, 140, 200))
        f = _get_font(int(16 * s))
        draw.text((left_x - bsz, py_top + lh + bsz + int(5 * s)),
                  "m1", fill=(200, 60, 60), font=f)
        draw.text((right_x - bsz, py_top + rh_val + bsz + int(5 * s)),
                  "m2", fill=(80, 140, 200), font=f)

    def _vi_pressure_column(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Fluid pressure column — container with height h and P=rho*g*h."""
        cw2 = int(cw * 0.20)
        ch = int(dh * 0.65)
        x0 = mx - cw2 // 2
        y0 = my - ch // 2
        draw.rectangle([x0, y0, x0 + cw2, y0 + ch],
                       outline=accent, width=int(3 * s))
        fluid_h = int(ch * 0.70)
        draw.rectangle([x0 + int(3 * s), y0 + ch - fluid_h,
                        x0 + cw2 - int(3 * s), y0 + ch - int(3 * s)],
                       fill=(100, 150, 255, 128))
        f = _get_font(int(16 * s))
        draw.line([(x0 + cw2 + int(10 * s), y0 + ch - fluid_h),
                   (x0 + cw2 + int(10 * s), y0 + ch)],
                  fill=(239, 108, 0), width=int(2 * s))
        draw.text((x0 + cw2 + int(16 * s), my - int(5 * s)),
                  "h", fill=(239, 108, 0), font=f)
        bf = _get_font(int(18 * s), bold=True)
        draw.text((mx - int(cw * 0.25), my + ch // 2 + int(12 * s)),
                  "P = rho g h", fill=accent, font=bf)

    def _vi_carnot_engine(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Carnot engine — hot/cold reservoir + engine + work output."""
        f = _get_font(int(16 * s), bold=True)
        bw, bh = int(cw * 0.22), int(dh * 0.18)
        draw.rounded_rectangle([mx - bw // 2, my - int(dh * 0.38) - bh // 2,
                                mx + bw // 2, my - int(dh * 0.38) + bh // 2],
                               radius=int(6 * s), fill=(200, 60, 60))
        draw.text((mx - int(12 * s), my - int(dh * 0.38) - int(8 * s)),
                  "HOT", fill=(255, 255, 255), font=f)
        draw.rounded_rectangle([mx - bw // 2, my - bh // 2,
                                mx + bw // 2, my + bh // 2],
                               radius=int(6 * s), fill=(239, 180, 0))
        draw.text((mx - int(20 * s), my - int(8 * s)),
                  "Engine", fill=(255, 255, 255), font=f)
        draw.rounded_rectangle([mx - bw // 2, my + int(dh * 0.38) - bh // 2,
                                mx + bw // 2, my + int(dh * 0.38) + bh // 2],
                               radius=int(6 * s), fill=(80, 120, 200))
        draw.text((mx - int(16 * s), my + int(dh * 0.38) - int(8 * s)),
                  "COLD", fill=(255, 255, 255), font=f)
        draw.line([(mx, my - int(dh * 0.38) + bh // 2), (mx, my - bh // 2)],
                  fill=(200, 60, 60), width=int(2 * s))
        draw.line([(mx, my + bh // 2), (mx, my + int(dh * 0.38) - bh // 2)],
                  fill=(80, 120, 200), width=int(2 * s))
        sf = _get_font(int(14 * s))
        draw.text((mx + int(5 * s), my - int(dh * 0.22)), "Qh",
                  fill=(200, 60, 60), font=sf)
        draw.text((mx + int(5 * s), my + int(dh * 0.22)), "Qc",
                  fill=(80, 120, 200), font=sf)
        draw.line([(mx + bw // 2, my), (mx + bw // 2 + int(cw * 0.15), my)],
                  fill=(46, 125, 50), width=int(3 * s))
        draw.text((mx + bw // 2 + int(cw * 0.05), my - int(18 * s)),
                  "W", fill=(46, 125, 50), font=f)

    # ── CHEMISTRY: New visuals ───────────────────────────────────────

    def _vi_periodic_element(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Periodic element card — atomic number, symbol, name, mass."""
        bw, bh = int(cw * 0.25), int(dh * 0.70)
        draw.rounded_rectangle([mx - bw, my - bh // 2, mx + bw, my + bh // 2],
                               radius=int(10 * s), outline=accent, width=int(4 * s))
        sf = _get_font(int(18 * s))
        draw.text((mx - bw + int(12 * s), my - bh // 2 + int(10 * s)),
                  "26", fill=accent, font=sf)
        bf = _get_font(int(52 * s), bold=True)
        tw = draw.textlength("Fe", font=bf)
        draw.text((mx - tw // 2, my - int(25 * s)), "Fe", fill=accent, font=bf)
        nf = _get_font(int(22 * s))
        tw2 = draw.textlength("Iron", font=nf)
        draw.text((mx - tw2 // 2, my + int(30 * s)), "Iron", fill=accent, font=nf)
        mf = _get_font(int(16 * s))
        tw3 = draw.textlength("55.845", font=mf)
        draw.text((mx - tw3 // 2, my + bh // 2 - int(28 * s)),
                  "55.845", fill=(120, 120, 120), font=mf)

    def _vi_ph_scale(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """pH scale — gradient bar 0-14."""
        bw = int(cw * 0.80)
        bh = int(dh * 0.22)
        x0 = mx - bw // 2
        seg_w = bw // 15
        colors_ph = [
            (255, 0, 0), (255, 50, 0), (255, 100, 0), (255, 150, 0),
            (255, 200, 0), (255, 255, 0), (200, 255, 0), (0, 255, 0),
            (0, 200, 100), (0, 150, 200), (0, 100, 255), (0, 50, 255),
            (50, 0, 255), (100, 0, 200), (150, 0, 150),
        ]
        for i in range(15):
            draw.rectangle([x0 + i * seg_w, my - bh // 2,
                            x0 + (i + 1) * seg_w, my + bh // 2],
                           fill=colors_ph[i])
        sf = _get_font(int(14 * s))
        for i in range(0, 15, 2):
            tx = x0 + i * seg_w + seg_w // 2
            draw.text((tx - int(4 * s), my + bh // 2 + int(5 * s)),
                      str(i), fill=(80, 80, 80), font=sf)
        f = _get_font(int(18 * s), bold=True)
        draw.text((x0, my - bh // 2 - int(24 * s)),
                  "Acidic", fill=(255, 0, 0), font=f)
        tw = draw.textlength("Basic", font=f)
        draw.text((x0 + bw - tw, my - bh // 2 - int(24 * s)),
                  "Basic", fill=(0, 0, 200), font=f)
        tw2 = draw.textlength("Neutral", font=f)
        draw.text((mx - tw2 // 2, my - bh // 2 - int(24 * s)),
                  "Neutral", fill=(0, 150, 0), font=f)

    def _vi_electrolysis(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Electrolysis — container with two electrodes + bubbles."""
        cw2 = int(cw * 0.45)
        ch = int(dh * 0.50)
        x0 = mx - cw2 // 2
        y0 = my - ch // 2
        draw.rectangle([x0, y0, x0 + cw2, y0 + ch],
                       outline=accent, width=int(3 * s))
        draw.rectangle([x0 + int(3 * s), y0 + ch // 4, x0 + cw2 - int(3 * s), y0 + ch],
                       fill=(200, 220, 255))
        ew = int(4 * s)
        lx = x0 + int(cw2 * 0.25)
        rx = x0 + int(cw2 * 0.75)
        draw.rectangle([lx - ew, y0 + int(ch * 0.15), lx + ew, y0 + ch - int(5 * s)],
                       fill=(100, 100, 100))
        draw.rectangle([rx - ew, y0 + int(ch * 0.15), rx + ew, y0 + ch - int(5 * s)],
                       fill=(100, 100, 100))
        f = _get_font(int(16 * s))
        draw.text((lx - int(20 * s), y0 - int(20 * s)),
                  "Anode +", fill=(200, 60, 60), font=f)
        draw.text((rx - int(28 * s), y0 - int(20 * s)),
                  "Cathode -", fill=(80, 80, 200), font=f)
        for by2 in [int(ch * 0.35), int(ch * 0.50), int(ch * 0.65)]:
            draw.ellipse([lx + int(8 * s), y0 + by2 - int(3 * s),
                          lx + int(14 * s), y0 + by2 + int(3 * s)],
                         fill=(200, 200, 255))
            draw.ellipse([rx + int(8 * s), y0 + by2 - int(3 * s),
                          rx + int(14 * s), y0 + by2 + int(3 * s)],
                         fill=(200, 200, 255))

    def _vi_galvanic_cell(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Galvanic cell — Zn/Cu cells with salt bridge."""
        f = _get_font(int(16 * s), bold=True)
        hw = int(cw * 0.18)
        hh = int(dh * 0.35)
        lx = mx - int(cw * 0.20)
        rx = mx + int(cw * 0.20)
        draw.rectangle([lx - hw, my - hh // 2, lx + hw, my + hh // 2],
                       outline=(100, 100, 100), width=int(2 * s))
        draw.rectangle([lx - hw + int(2 * s), my, lx + hw - int(2 * s), my + hh // 2],
                       fill=(180, 200, 220))
        draw.rectangle([rx - hw, my - hh // 2, rx + hw, my + hh // 2],
                       outline=(200, 120, 50), width=int(2 * s))
        draw.rectangle([rx - hw + int(2 * s), my, rx + hw - int(2 * s), my + hh // 2],
                       fill=(180, 220, 255))
        draw.text((lx - int(8 * s), my + hh // 2 + int(6 * s)),
                  "Zn", fill=(100, 100, 100), font=f)
        draw.text((rx - int(8 * s), my + hh // 2 + int(6 * s)),
                  "Cu", fill=(200, 120, 50), font=f)
        draw.arc([mx - int(cw * 0.15), my - hh // 2 - int(dh * 0.10),
                  mx + int(cw * 0.15), my - hh // 2 + int(dh * 0.10)],
                 0, 180, fill=(200, 200, 0), width=int(3 * s))
        sf = _get_font(int(14 * s))
        draw.text((mx - int(30 * s), my - hh // 2 - int(dh * 0.18)),
                  "Salt Bridge", fill=(180, 180, 0), font=sf)

    def _vi_bond_ionic(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Ionic bond — Na+ and Cl- with attraction."""
        r = int(dh * 0.20)
        gap = int(cw * 0.20)
        draw.ellipse([mx - gap - r, my - r, mx - gap + r, my + r],
                     fill=(200, 60, 60), outline=(255, 255, 255), width=int(2 * s))
        draw.ellipse([mx + gap - r, my - r, mx + gap + r, my + r],
                     fill=(80, 140, 200), outline=(255, 255, 255), width=int(2 * s))
        f = _get_font(int(24 * s), bold=True)
        draw.text((mx - gap - int(18 * s), my - int(12 * s)),
                  "Na+", fill=(255, 255, 255), font=f)
        draw.text((mx + gap - int(14 * s), my - int(12 * s)),
                  "Cl-", fill=(255, 255, 255), font=f)
        for i in range(3):
            dx = mx - gap + r + int((2 * gap - 2 * r) * (i + 1) / 4)
            draw.line([(dx, my - int(3 * s)), (dx + int(8 * s), my - int(3 * s))],
                      fill=(239, 108, 0), width=int(2 * s))
        sf = _get_font(int(16 * s))
        draw.text((mx - int(40 * s), my + r + int(12 * s)),
                  "Ionic Bond", fill=accent, font=sf)

    def _vi_bond_covalent(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Covalent bond — two atoms with shared electron cloud."""
        r = int(dh * 0.22)
        overlap = int(r * 0.40)
        draw.ellipse([mx - overlap - r, my - r, mx - overlap + r, my + r],
                     outline=(200, 60, 60), width=int(3 * s))
        draw.ellipse([mx + overlap - r, my - r, mx + overlap + r, my + r],
                     outline=(80, 140, 200), width=int(3 * s))
        draw.ellipse([mx - int(r * 0.25), my - int(r * 0.35),
                      mx + int(r * 0.25), my + int(r * 0.35)],
                     fill=(220, 200, 255))
        f = _get_font(int(16 * s))
        draw.text((mx - int(35 * s), my + r + int(10 * s)),
                  "Shared electrons", fill=(140, 100, 200), font=f)

    def _vi_benzene(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Benzene — hexagonal ring with circle inside."""
        r = int(min(cw, dh) * 0.25)
        pts = [(mx + int(r * math.cos(math.pi / 2 + math.pi * 2 * i / 6)),
                my - int(r * math.sin(math.pi / 2 + math.pi * 2 * i / 6)))
               for i in range(6)]
        draw.polygon(pts, outline=accent, width=int(3 * s))
        inner_r = int(r * 0.55)
        draw.ellipse([mx - inner_r, my - inner_r, mx + inner_r, my + inner_r],
                     outline=accent, width=int(2 * s))
        for pt in pts:
            draw.ellipse([pt[0] - int(5 * s), pt[1] - int(5 * s),
                          pt[0] + int(5 * s), pt[1] + int(5 * s)], fill=accent)
        f = _get_font(int(16 * s))
        draw.text((mx - int(15 * s), my + r + int(12 * s)),
                  "C6H6", fill=accent, font=f)

    def _vi_activation_energy(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Activation energy — reaction progress hill diagram."""
        x0, x1 = cx + int(cw * 0.08), cx + int(cw * 0.92)
        y_base = my + int(dh * 0.35)
        draw.line([(x0, y_base), (x1, y_base)], fill=(150, 150, 150), width=int(1 * s))
        draw.line([(x0, y_base), (x0, my - int(dh * 0.40))],
                  fill=(150, 150, 150), width=int(1 * s))
        reactant_y = my + int(dh * 0.10)
        peak_y = my - int(dh * 0.32)
        product_y = my + int(dh * 0.20)
        pts = []
        for i in range(40):
            t = i / 39
            px = x0 + int(t * (x1 - x0))
            if t < 0.15:
                py = reactant_y
            elif t < 0.50:
                frac = (t - 0.15) / 0.35
                py = reactant_y + int((peak_y - reactant_y) * math.sin(frac * math.pi / 2))
            elif t < 0.65:
                frac = (t - 0.50) / 0.15
                py = peak_y + int((product_y - peak_y) * frac * frac)
            else:
                py = product_y
            pts.append((px, py))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=accent, width=int(3 * s))
        f = _get_font(int(16 * s))
        ea_x = x0 + int((x1 - x0) * 0.30)
        draw.line([(ea_x, reactant_y), (ea_x, peak_y)],
                  fill=(239, 108, 0), width=int(2 * s))
        draw.text((ea_x + int(6 * s), (reactant_y + peak_y) // 2),
                  "Ea", fill=(239, 108, 0), font=f)
        draw.text((x0 + int(10 * s), reactant_y - int(18 * s)),
                  "Reactants", fill=accent, font=f)
        draw.text((x1 - int(70 * s), product_y - int(18 * s)),
                  "Products", fill=accent, font=f)

    def _vi_test_tube(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Test tube with colored liquid and bubbles."""
        tw_half = int(cw * 0.06)
        th = int(dh * 0.65)
        y0 = my - th // 2
        draw.rounded_rectangle([mx - tw_half, y0, mx + tw_half, y0 + th],
                               radius=tw_half, outline=accent, width=int(3 * s))
        liquid_h = int(th * 0.55)
        draw.rounded_rectangle([mx - tw_half + int(3 * s), y0 + th - liquid_h,
                                mx + tw_half - int(3 * s), y0 + th - int(3 * s)],
                               radius=tw_half - int(3 * s), fill=(100, 200, 150))
        for i, (bx, by) in enumerate([(int(3 * s), -int(th * 0.15)),
                                      (-int(5 * s), -int(th * 0.25)),
                                      (int(1 * s), -int(th * 0.35))]):
            br = int(3 * s + i)
            draw.ellipse([mx + bx - br, y0 + th + by - br,
                          mx + bx + br, y0 + th + by + br],
                         outline=(255, 255, 255), width=int(1 * s))
        f = _get_font(int(16 * s))
        draw.text((mx + tw_half + int(10 * s), my - int(8 * s)),
                  "Solution", fill=accent, font=f)

    def _vi_distillation(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Distillation — flask + condenser + collection."""
        f = _get_font(int(14 * s))
        fw = int(cw * 0.10)
        fh = int(dh * 0.30)
        fx = mx - int(cw * 0.25)
        fy = my
        draw.rounded_rectangle([fx - fw, fy - fh // 2, fx + fw, fy + fh // 2],
                               radius=int(8 * s), outline=accent, width=int(2 * s))
        draw.rectangle([fx - fw + int(2 * s), fy, fx + fw - int(2 * s), fy + fh // 2],
                       fill=(180, 220, 255))
        draw.text((fx - int(12 * s), fy + fh // 2 + int(5 * s)),
                  "Flask", fill=accent, font=f)
        cx2 = mx + int(cw * 0.05)
        draw.line([(fx + fw, fy - fh // 4), (cx2, fy - fh // 4)],
                  fill=(150, 150, 150), width=int(2 * s))
        draw.line([(cx2, fy - fh // 4), (mx + int(cw * 0.20), fy + fh // 4)],
                  fill=(150, 150, 150), width=int(2 * s))
        draw.text((cx2 - int(5 * s), fy - fh // 4 - int(18 * s)),
                  "Condenser", fill=(150, 150, 150), font=f)
        cf_x = mx + int(cw * 0.25)
        draw.rounded_rectangle([cf_x - fw, fy, cf_x + fw, fy + fh // 2],
                               radius=int(6 * s), outline=accent, width=int(2 * s))
        draw.text((cf_x - int(20 * s), fy + fh // 2 + int(5 * s)),
                  "Collect", fill=accent, font=f)

    # ── MATH: New visuals ────────────────────────────────────────────

    def _vi_venn_diagram(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Venn diagram — two overlapping circles A, B."""
        r = int(min(cw, dh) * 0.26)
        offset = int(r * 0.55)
        draw.ellipse([mx - offset - r, my - r, mx - offset + r, my + r],
                     outline=(200, 60, 60), width=int(3 * s))
        draw.ellipse([mx + offset - r, my - r, mx + offset + r, my + r],
                     outline=(80, 140, 200), width=int(3 * s))
        f = _get_font(int(24 * s), bold=True)
        draw.text((mx - offset - int(12 * s), my - int(12 * s)),
                  "A", fill=(200, 60, 60), font=f)
        draw.text((mx + offset - int(8 * s), my - int(12 * s)),
                  "B", fill=(80, 140, 200), font=f)
        sf = _get_font(int(16 * s))
        draw.text((mx - int(16 * s), my + r + int(10 * s)),
                  "A n B", fill=accent, font=sf)

    def _vi_coordinate_plane(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Coordinate plane — X-Y axes with quadrant labels."""
        ax_len = int(min(cw, dh) * 0.38)
        draw.line([(mx - ax_len, my), (mx + ax_len, my)],
                  fill=accent, width=int(2 * s))
        draw.line([(mx, my + ax_len), (mx, my - ax_len)],
                  fill=accent, width=int(2 * s))
        draw.polygon([(mx + ax_len - int(8 * s), my - int(5 * s)),
                      (mx + ax_len - int(8 * s), my + int(5 * s)),
                      (mx + ax_len, my)], fill=accent)
        draw.polygon([(mx - int(5 * s), my - ax_len + int(8 * s)),
                      (mx + int(5 * s), my - ax_len + int(8 * s)),
                      (mx, my - ax_len)], fill=accent)
        f = _get_font(int(18 * s))
        draw.text((mx + ax_len - int(20 * s), my + int(8 * s)),
                  "X", fill=accent, font=f)
        draw.text((mx + int(8 * s), my - ax_len + int(4 * s)),
                  "Y", fill=accent, font=f)
        sf = _get_font(int(16 * s))
        draw.text((mx + int(ax_len * 0.3), my - int(ax_len * 0.5)),
                  "I", fill=(150, 150, 150), font=sf)
        draw.text((mx - int(ax_len * 0.5), my - int(ax_len * 0.5)),
                  "II", fill=(150, 150, 150), font=sf)
        draw.text((mx - int(ax_len * 0.6), my + int(ax_len * 0.3)),
                  "III", fill=(150, 150, 150), font=sf)
        draw.text((mx + int(ax_len * 0.3), my + int(ax_len * 0.3)),
                  "IV", fill=(150, 150, 150), font=sf)

    def _vi_pie_chart(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Pie chart — 4 sectors with labels."""
        r = int(min(cw, dh) * 0.28)
        angles = [0, 90, 200, 300, 360]
        colors = [(200, 60, 60), (80, 140, 200), (46, 125, 50), (239, 108, 0)]
        labels = ["25%", "30%", "28%", "17%"]
        for i in range(4):
            draw.pieslice([mx - r, my - r, mx + r, my + r],
                          angles[i], angles[i + 1], fill=colors[i],
                          outline=(255, 255, 255), width=int(2 * s))
        f = _get_font(int(16 * s), bold=True)
        label_r = r + int(20 * s)
        for i in range(4):
            mid_angle = (angles[i] + angles[i + 1]) / 2
            lx = mx + int(label_r * math.cos(math.radians(mid_angle)))
            ly = my + int(label_r * math.sin(math.radians(mid_angle)))
            draw.text((lx - int(12 * s), ly - int(8 * s)),
                      labels[i], fill=colors[i], font=f)

    def _vi_bar_chart(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Bar chart — 4 bars with values."""
        values = [65, 85, 45, 70]
        labels = ["A", "B", "C", "D"]
        colors = [(200, 60, 60), (80, 140, 200), (46, 125, 50), (239, 108, 0)]
        n = len(values)
        max_v = max(values)
        chart_w = int(cw * 0.70)
        chart_h = int(dh * 0.60)
        x0 = mx - chart_w // 2
        y_base = my + chart_h // 2
        bar_w = int(chart_w / n * 0.60)
        gap = int(chart_w / n * 0.40)
        draw.line([(x0, y_base), (x0 + chart_w, y_base)],
                  fill=(150, 150, 150), width=int(1 * s))
        f = _get_font(int(16 * s))
        for i in range(n):
            bh = int(chart_h * values[i] / max_v)
            bx = x0 + int(i * chart_w / n) + gap // 2
            draw.rectangle([bx, y_base - bh, bx + bar_w, y_base], fill=colors[i])
            draw.text((bx + bar_w // 2 - int(4 * s), y_base + int(5 * s)),
                      labels[i], fill=colors[i], font=f)
            draw.text((bx + bar_w // 2 - int(8 * s), y_base - bh - int(18 * s)),
                      str(values[i]), fill=colors[i], font=f)

    def _vi_triangle_parts(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Triangle with labeled angles and sides."""
        hw, hh = int(cw * 0.28), int(dh * 0.35)
        pts = [(mx, my - hh), (mx - hw, my + hh), (mx + hw, my + hh)]
        draw.polygon(pts, outline=accent, width=int(3 * s))
        f = _get_font(int(18 * s), bold=True)
        draw.text((mx - int(4 * s), my - hh - int(22 * s)),
                  "A", fill=(200, 60, 60), font=f)
        draw.text((mx - hw - int(22 * s), my + hh + int(4 * s)),
                  "B", fill=(80, 140, 200), font=f)
        draw.text((mx + hw + int(6 * s), my + hh + int(4 * s)),
                  "C", fill=(46, 125, 50), font=f)
        sf = _get_font(int(16 * s))
        draw.text(((pts[1][0] + pts[2][0]) // 2 - int(4 * s), my + hh + int(22 * s)),
                  "a", fill=accent, font=sf)
        draw.text((mx + hw // 2 + int(8 * s), my - int(4 * s)),
                  "b", fill=accent, font=sf)
        draw.text((mx - hw // 2 - int(18 * s), my - int(4 * s)),
                  "c", fill=accent, font=sf)

    def _vi_circle_parts(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Circle with radius, diameter, chord, arc labeled."""
        r = int(min(cw, dh) * 0.28)
        draw.ellipse([mx - r, my - r, mx + r, my + r],
                     outline=accent, width=int(3 * s))
        draw.ellipse([mx - int(3 * s), my - int(3 * s),
                      mx + int(3 * s), my + int(3 * s)], fill=accent)
        draw.line([(mx, my), (mx + r, my)], fill=(200, 60, 60), width=int(2 * s))
        draw.line([(mx - r, my), (mx + r, my)],
                  fill=(80, 140, 200), width=int(2 * s))
        chord_y = my - int(r * 0.50)
        chord_hw = int(r * math.cos(math.asin(0.50)))
        draw.line([(mx - chord_hw, chord_y), (mx + chord_hw, chord_y)],
                  fill=(46, 125, 50), width=int(2 * s))
        f = _get_font(int(16 * s))
        draw.text((mx + r // 2 - int(4 * s), my + int(6 * s)),
                  "r", fill=(200, 60, 60), font=f)
        draw.text((mx - int(4 * s), my + int(20 * s)),
                  "d", fill=(80, 140, 200), font=f)
        draw.text((mx - int(15 * s), chord_y - int(20 * s)),
                  "chord", fill=(46, 125, 50), font=f)

    def _vi_number_pattern(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Number pattern — sequence boxes with arrows."""
        nums = [2, 5, 8, 11, 14]
        n = len(nums)
        bsz = int(min(cw * 0.12, dh * 0.35))
        gap = int(cw * 0.04)
        total_w = n * bsz + (n - 1) * gap
        x0 = mx - total_w // 2
        f = _get_font(int(22 * s), bold=True)
        sf = _get_font(int(16 * s))
        for i, num in enumerate(nums):
            x = x0 + i * (bsz + gap)
            draw.rounded_rectangle([x, my - bsz // 2, x + bsz, my + bsz // 2],
                                   radius=int(6 * s), outline=accent, width=int(2 * s))
            tw = draw.textlength(str(num), font=f)
            draw.text((x + (bsz - tw) // 2, my - f.size // 2),
                      str(num), fill=accent, font=f)
            if i < n - 1:
                draw.text((x + bsz + gap // 2 - int(6 * s), my - bsz // 2 - int(18 * s)),
                          "+3", fill=(239, 108, 0), font=sf)

    def _vi_fraction_visual(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Fraction visual — rectangle divided into parts, some shaded."""
        total = 5
        shaded = 3
        bw = int(cw * 0.65)
        bh = int(dh * 0.30)
        x0 = mx - bw // 2
        seg_w = bw // total
        for i in range(total):
            col = accent if i < shaded else (230, 230, 230)
            draw.rectangle([x0 + i * seg_w, my - bh // 2,
                            x0 + (i + 1) * seg_w, my + bh // 2],
                           fill=col, outline=(255, 255, 255), width=int(2 * s))
        f = _get_font(int(28 * s), bold=True)
        txt = f"{shaded}/{total}"
        tw = draw.textlength(txt, font=f)
        draw.text((mx - tw // 2, my + bh // 2 + int(12 * s)),
                  txt, fill=accent, font=f)

    def _vi_normal_distribution(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Normal distribution — bell curve with mu and sigma labels."""
        x0, x1 = cx + int(cw * 0.08), cx + int(cw * 0.92)
        y_base = my + int(dh * 0.35)
        draw.line([(x0, y_base), (x1, y_base)], fill=(150, 150, 150), width=int(1 * s))
        peak_h = int(dh * 0.60)
        pts = []
        for i in range(50):
            t = (i / 49 - 0.5) * 6
            px = x0 + int(i * (x1 - x0) / 49)
            py = y_base - int(peak_h * math.exp(-t * t / 2))
            pts.append((px, py))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=accent, width=int(3 * s))
        f = _get_font(int(18 * s))
        draw.text((mx - int(5 * s), y_base + int(6 * s)),
                  "mu", fill=accent, font=f)
        sigma_x = mx + int((x1 - x0) / 6)
        draw.line([(mx, y_base - int(4 * s)), (sigma_x, y_base - int(4 * s))],
                  fill=(239, 108, 0), width=int(2 * s))
        draw.text((sigma_x + int(4 * s), y_base - int(12 * s)),
                  "sigma", fill=(239, 108, 0), font=f)

    # ── GEOGRAPHY: New visuals ───────────────────────────────────────

    def _vi_compass(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """8-point compass rose."""
        r = int(min(cw, dh) * 0.30)
        draw.ellipse([mx - r, my - r, mx + r, my + r],
                     outline=accent, width=int(2 * s))
        f = _get_font(int(20 * s), bold=True)
        sf = _get_font(int(14 * s))
        dirs_main = [("N", 0), ("E", 90), ("S", 180), ("W", 270)]
        dirs_sub = [("NE", 45), ("SE", 135), ("SW", 225), ("NW", 315)]
        for label, angle in dirs_main:
            rad = math.radians(angle - 90)
            tx = mx + int((r + int(16 * s)) * math.cos(rad))
            ty = my + int((r + int(16 * s)) * math.sin(rad))
            tw = draw.textlength(label, font=f)
            col = (200, 60, 60) if label == "N" else accent
            draw.text((tx - tw // 2, ty - f.size // 2), label, fill=col, font=f)
            lx = mx + int(r * 0.85 * math.cos(rad))
            ly = my + int(r * 0.85 * math.sin(rad))
            draw.line([(mx, my), (lx, ly)], fill=accent, width=int(2 * s))
        for label, angle in dirs_sub:
            rad = math.radians(angle - 90)
            lx = mx + int(r * 0.60 * math.cos(rad))
            ly = my + int(r * 0.60 * math.sin(rad))
            draw.line([(mx, my), (lx, ly)], fill=(180, 180, 180), width=int(1 * s))

    def _vi_rock_cycle(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Rock cycle — triangle: Igneous, Sedimentary, Metamorphic."""
        f = _get_font(int(16 * s), bold=True)
        r = int(min(cw, dh) * 0.28)
        nodes = [("Igneous", (200, 80, 80)), ("Sedimentary", (180, 160, 100)),
                 ("Metamorphic", (120, 120, 180))]
        positions = [(mx, my - int(r * 0.85)),
                     (mx + int(r * 0.80), my + int(r * 0.55)),
                     (mx - int(r * 0.80), my + int(r * 0.55))]
        nr = int(dh * 0.10)
        for (label, col), (px, py) in zip(nodes, positions):
            draw.ellipse([px - nr, py - nr, px + nr, py + nr],
                         fill=col, outline=(255, 255, 255), width=int(2 * s))
            tw = draw.textlength(label, font=f)
            draw.text((px - tw // 2, py + nr + int(4 * s)), label, fill=col, font=f)
        for i in range(3):
            p1 = positions[i]
            p2 = positions[(i + 1) % 3]
            amx = (p1[0] + p2[0]) // 2
            amy = (p1[1] + p2[1]) // 2
            draw.line([(p1[0], p1[1] + nr), (amx, amy)],
                      fill=(150, 150, 150), width=int(2 * s))

    def _vi_climate_zones(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Climate zones — horizontal bands."""
        f = _get_font(int(16 * s), bold=True)
        zones = [("Polar", (180, 200, 240)), ("Temperate", (140, 200, 140)),
                 ("Tropical", (240, 200, 100)), ("Temperate", (140, 200, 140)),
                 ("Polar", (180, 200, 240))]
        n = len(zones)
        zone_h = int(dh * 0.16)
        y0 = my - int(n * zone_h / 2)
        bw = int(cw * 0.70)
        for i, (label, col) in enumerate(zones):
            y = y0 + i * zone_h
            draw.rectangle([mx - bw // 2, y, mx + bw // 2, y + zone_h], fill=col)
            tw = draw.textlength(label, font=f)
            draw.text((mx - tw // 2, y + (zone_h - f.size) // 2),
                      label, fill=(60, 60, 60), font=f)

    def _vi_river_landforms(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """River landforms — delta, meander, oxbow."""
        f = _get_font(int(16 * s))
        x0 = cx + int(cw * 0.05)
        river_y = my
        pts = [(x0, river_y)]
        for i in range(20):
            t = i / 19
            x = x0 + int(t * cw * 0.90)
            y = river_y + int(25 * s * math.sin(t * 6))
            pts.append((x, y))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=(60, 120, 220), width=int(4 * s))
        draw.text((x0, river_y + int(dh * 0.20)),
                  "Meander", fill=(60, 120, 220), font=f)
        dx = cx + int(cw * 0.80)
        draw.polygon([(dx, river_y - int(dh * 0.10)),
                      (dx + int(cw * 0.10), river_y + int(dh * 0.15)),
                      (dx - int(cw * 0.10), river_y + int(dh * 0.15))],
                     fill=(180, 160, 100), outline=(60, 120, 220), width=int(2 * s))
        draw.text((dx - int(15 * s), river_y + int(dh * 0.20)),
                  "Delta", fill=(139, 90, 43), font=f)
        ox = mx - int(cw * 0.05)
        oy = river_y - int(dh * 0.28)
        draw.arc([ox - int(15 * s), oy - int(12 * s),
                  ox + int(15 * s), oy + int(12 * s)],
                 0, 300, fill=(60, 120, 220), width=int(3 * s))
        draw.text((ox - int(20 * s), oy - int(22 * s)),
                  "Oxbow", fill=(60, 120, 220), font=f)

    # ── POLITY: New visuals ──────────────────────────────────────────

    def _vi_government_structure(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """3 pillars — Legislature, Executive, Judiciary."""
        f = _get_font(int(16 * s), bold=True)
        pillars = [("Legislature", (200, 60, 60)),
                   ("Executive", (239, 108, 0)),
                   ("Judiciary", (80, 140, 200))]
        pw = int(cw * 0.22)
        ph = int(dh * 0.55)
        gap = int(cw * 0.04)
        x0 = mx - int((3 * pw + 2 * gap) / 2)
        base_y = my + ph // 2
        for i, (label, col) in enumerate(pillars):
            x = x0 + i * (pw + gap)
            draw.rectangle([x, my - ph // 2, x + pw, base_y], fill=col)
            tw = draw.textlength(label, font=f)
            draw.text((x + (pw - tw) // 2, my - int(8 * s)),
                      label, fill=(255, 255, 255), font=f)
        draw.rectangle([x0 - int(10 * s), base_y,
                        x0 + 3 * pw + 2 * gap + int(10 * s),
                        base_y + int(dh * 0.08)],
                       fill=accent)
        bf = _get_font(int(18 * s), bold=True)
        tw2 = draw.textlength("Government", font=bf)
        draw.text((mx - tw2 // 2, base_y + int(dh * 0.10)),
                  "Government", fill=accent, font=bf)

    def _vi_parliament(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Parliament — Lok Sabha + Rajya Sabha boxes."""
        f = _get_font(int(18 * s), bold=True)
        bw = int(cw * 0.50)
        bh = int(dh * 0.25)
        gap = int(dh * 0.08)
        draw.rounded_rectangle([mx - bw // 2, my - gap // 2 - bh,
                                mx + bw // 2, my - gap // 2],
                               radius=int(8 * s), fill=(200, 60, 60))
        tw = draw.textlength("Rajya Sabha (Upper)", font=f)
        draw.text((mx - tw // 2, my - gap // 2 - bh // 2 - int(10 * s)),
                  "Rajya Sabha (Upper)", fill=(255, 255, 255), font=f)
        draw.rounded_rectangle([mx - bw // 2, my + gap // 2,
                                mx + bw // 2, my + gap // 2 + bh],
                               radius=int(8 * s), fill=(80, 140, 200))
        tw2 = draw.textlength("Lok Sabha (Lower)", font=f)
        draw.text((mx - tw2 // 2, my + gap // 2 + bh // 2 - int(10 * s)),
                  "Lok Sabha (Lower)", fill=(255, 255, 255), font=f)
        sf = _get_font(int(14 * s))
        draw.text((mx - int(30 * s), my - int(5 * s)),
                  "Parliament", fill=accent, font=sf)

    # ── ECONOMICS: New visuals ───────────────────────────────────────

    def _vi_supply_demand(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Supply and demand — intersecting curves with equilibrium."""
        x0, x1 = cx + int(cw * 0.12), cx + int(cw * 0.88)
        y0, y1 = dy + int(dh * 0.08), dy + int(dh * 0.88)
        draw.line([(x0, y1), (x1, y1)], fill=accent, width=int(2 * s))
        draw.line([(x0, y1), (x0, y0)], fill=accent, width=int(2 * s))
        draw.line([(x0, y0 + int((y1 - y0) * 0.10)),
                   (x1 - int(10 * s), y1 - int((y1 - y0) * 0.10))],
                  fill=(200, 60, 60), width=int(3 * s))
        draw.line([(x0, y1 - int((y1 - y0) * 0.10)),
                   (x1 - int(10 * s), y0 + int((y1 - y0) * 0.10))],
                  fill=(80, 140, 200), width=int(3 * s))
        eq_x = (x0 + x1) // 2
        eq_y = (y0 + y1) // 2
        draw.ellipse([eq_x - int(5 * s), eq_y - int(5 * s),
                      eq_x + int(5 * s), eq_y + int(5 * s)], fill=(239, 108, 0))
        f = _get_font(int(16 * s))
        draw.text((x1 - int(10 * s), y0 + int((y1 - y0) * 0.05)),
                  "S", fill=(200, 60, 60), font=f)
        draw.text((x1 - int(10 * s), y1 - int((y1 - y0) * 0.15)),
                  "D", fill=(80, 140, 200), font=f)
        draw.text((eq_x + int(8 * s), eq_y - int(18 * s)),
                  "Equilibrium", fill=(239, 108, 0), font=f)
        draw.text((x0 - int(5 * s), y0 - int(16 * s)), "P", fill=accent, font=f)
        draw.text((x1 - int(8 * s), y1 + int(6 * s)), "Q", fill=accent, font=f)

    def _vi_ppf(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Production Possibility Frontier — concave curve."""
        x0, x1 = cx + int(cw * 0.12), cx + int(cw * 0.85)
        y0, y1 = dy + int(dh * 0.08), dy + int(dh * 0.85)
        draw.line([(x0, y1), (x1, y1)], fill=accent, width=int(2 * s))
        draw.line([(x0, y1), (x0, y0)], fill=accent, width=int(2 * s))
        pts = []
        for i in range(30):
            t = i / 29
            px = x0 + int(t * (x1 - x0) * 0.90)
            py = y0 + int((y1 - y0) * 0.10) + int((y1 - y0) * 0.80 * (1 - math.sqrt(1 - t * t)))
            pts.append((px, py))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=accent, width=int(3 * s))
        f = _get_font(int(16 * s))
        draw.text((x0 - int(5 * s), y0 - int(18 * s)),
                  "Good Y", fill=accent, font=f)
        draw.text((x1 - int(30 * s), y1 + int(6 * s)),
                  "Good X", fill=accent, font=f)
        draw.text((mx - int(10 * s), my - int(dh * 0.15)),
                  "PPF", fill=(239, 108, 0), font=f)

    # ── COMPUTER SCIENCE: New visuals ────────────────────────────────

    def _vi_flowchart(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Flowchart — Start → Process → Decision → End."""
        f = _get_font(int(16 * s))
        bw, bh = int(cw * 0.22), int(dh * 0.14)
        y0 = dy + int(dh * 0.05)
        shapes = [("Start", (46, 125, 50)), ("Process", (80, 140, 200)),
                  ("Decision", (239, 108, 0)), ("End", (200, 60, 60))]
        for i, (label, col) in enumerate(shapes):
            y = y0 + i * int(dh * 0.22)
            if label in ("Start", "End"):
                draw.rounded_rectangle([mx - bw // 2, y, mx + bw // 2, y + bh],
                                       radius=bh // 2, fill=col)
            elif label == "Decision":
                pts = [(mx, y), (mx + bw // 2, y + bh // 2),
                       (mx, y + bh), (mx - bw // 2, y + bh // 2)]
                draw.polygon(pts, fill=col)
            else:
                draw.rectangle([mx - bw // 2, y, mx + bw // 2, y + bh], fill=col)
            tw = draw.textlength(label, font=f)
            draw.text((mx - tw // 2, y + (bh - f.size) // 2),
                      label, fill=(255, 255, 255), font=f)
            if i < len(shapes) - 1:
                draw.line([(mx, y + bh), (mx, y + int(dh * 0.22))],
                          fill=(150, 150, 150), width=int(2 * s))

    def _vi_binary_tree(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Binary tree — 3 levels."""
        nr = int(dh * 0.08)
        f = _get_font(int(16 * s), bold=True)
        nodes = [(mx, dy + int(dh * 0.10), "1")]
        level2 = [(mx - int(cw * 0.18), my - int(dh * 0.05), "2"),
                  (mx + int(cw * 0.18), my - int(dh * 0.05), "3")]
        level3 = [(mx - int(cw * 0.28), my + int(dh * 0.25), "4"),
                  (mx - int(cw * 0.08), my + int(dh * 0.25), "5"),
                  (mx + int(cw * 0.08), my + int(dh * 0.25), "6"),
                  (mx + int(cw * 0.28), my + int(dh * 0.25), "7")]
        draw.line([(nodes[0][0], nodes[0][1] + nr), (level2[0][0], level2[0][1] - nr)],
                  fill=(150, 150, 150), width=int(2 * s))
        draw.line([(nodes[0][0], nodes[0][1] + nr), (level2[1][0], level2[1][1] - nr)],
                  fill=(150, 150, 150), width=int(2 * s))
        for i in range(2):
            draw.line([(level2[i][0], level2[i][1] + nr),
                       (level3[i * 2][0], level3[i * 2][1] - nr)],
                      fill=(150, 150, 150), width=int(2 * s))
            draw.line([(level2[i][0], level2[i][1] + nr),
                       (level3[i * 2 + 1][0], level3[i * 2 + 1][1] - nr)],
                      fill=(150, 150, 150), width=int(2 * s))
        for x, y, val in nodes + level2 + level3:
            draw.ellipse([x - nr, y - nr, x + nr, y + nr],
                         fill=accent, outline=(255, 255, 255), width=int(2 * s))
            tw = draw.textlength(val, font=f)
            draw.text((x - tw // 2, y - f.size // 2), val,
                      fill=(255, 255, 255), font=f)

    def _vi_stack_visual(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Stack — LIFO with push/pop arrows."""
        f = _get_font(int(18 * s), bold=True)
        sf = _get_font(int(14 * s))
        bw = int(cw * 0.25)
        bh = int(dh * 0.12)
        items = ["10", "20", "30", "40"]
        n = len(items)
        y_base = my + int(n * bh / 2)
        for i, val in enumerate(items):
            y = y_base - (i + 1) * bh
            col = accent if i == n - 1 else tuple(min(255, c + 80) for c in accent)
            draw.rectangle([mx - bw // 2, y, mx + bw // 2, y + bh],
                           fill=col, outline=(255, 255, 255), width=int(2 * s))
            tw = draw.textlength(val, font=f)
            draw.text((mx - tw // 2, y + (bh - f.size) // 2),
                      val, fill=(255, 255, 255), font=f)
        top_y = y_base - n * bh
        draw.line([(mx + bw // 2 + int(15 * s), top_y + bh),
                   (mx + bw // 2 + int(15 * s), top_y - int(10 * s))],
                  fill=(200, 60, 60), width=int(2 * s))
        draw.text((mx + bw // 2 + int(20 * s), top_y - int(5 * s)),
                  "Push/Pop", fill=(200, 60, 60), font=sf)
        draw.text((mx - int(16 * s), y_base + int(8 * s)),
                  "LIFO", fill=accent, font=sf)

    def _vi_queue_visual(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Queue — FIFO with enqueue/dequeue arrows."""
        f = _get_font(int(18 * s), bold=True)
        sf = _get_font(int(14 * s))
        bw = int(cw * 0.12)
        bh = int(dh * 0.35)
        items = ["A", "B", "C", "D"]
        n = len(items)
        x0 = mx - int(n * bw / 2)
        for i, val in enumerate(items):
            x = x0 + i * bw
            col = accent if i == 0 else tuple(min(255, c + 60) for c in accent)
            draw.rectangle([x, my - bh // 2, x + bw, my + bh // 2],
                           fill=col, outline=(255, 255, 255), width=int(2 * s))
            tw = draw.textlength(val, font=f)
            draw.text((x + (bw - tw) // 2, my - f.size // 2),
                      val, fill=(255, 255, 255), font=f)
        draw.text((x0 - int(cw * 0.10), my - int(8 * s)),
                  "Out", fill=(200, 60, 60), font=sf)
        draw.text((x0 + n * bw + int(8 * s), my - int(8 * s)),
                  "In", fill=(46, 125, 50), font=sf)
        draw.text((mx - int(12 * s), my + bh // 2 + int(10 * s)),
                  "FIFO", fill=accent, font=sf)

    def _vi_array_visual(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Array — boxes with index numbers."""
        f = _get_font(int(20 * s), bold=True)
        sf = _get_font(int(14 * s))
        items = [42, 17, 56, 8, 31, 94]
        n = len(items)
        bw = int(cw * 0.10)
        bh = int(dh * 0.35)
        x0 = mx - int(n * bw / 2)
        for i, val in enumerate(items):
            x = x0 + i * bw
            draw.rectangle([x, my - bh // 2, x + bw, my + bh // 2],
                           fill=accent, outline=(255, 255, 255), width=int(2 * s))
            tw = draw.textlength(str(val), font=f)
            draw.text((x + (bw - tw) // 2, my - f.size // 2),
                      str(val), fill=(255, 255, 255), font=f)
            tw2 = draw.textlength(str(i), font=sf)
            draw.text((x + (bw - tw2) // 2, my + bh // 2 + int(5 * s)),
                      str(i), fill=(120, 120, 120), font=sf)

    def _vi_osi_layers(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """OSI 7-layer model — stacked boxes."""
        f = _get_font(int(14 * s))
        layers = ["Application", "Presentation", "Session", "Transport",
                  "Network", "Data Link", "Physical"]
        n = len(layers)
        bw = int(cw * 0.50)
        bh = int(dh / n * 0.88)
        y0 = my - int(n * bh / 2)
        colors = [(200, 60, 60), (239, 140, 0), (239, 200, 0), (46, 125, 50),
                  (0, 150, 200), (80, 80, 200), (140, 60, 200)]
        for i, (layer, col) in enumerate(zip(layers, colors)):
            y = y0 + i * bh
            draw.rectangle([mx - bw // 2, y, mx + bw // 2, y + bh - int(2 * s)],
                           fill=col)
            tw = draw.textlength(f"{7 - i}. {layer}", font=f)
            draw.text((mx - tw // 2, y + (bh - int(2 * s) - f.size) // 2),
                      f"{7 - i}. {layer}", fill=(255, 255, 255), font=f)

    # ── REASONING: New visuals ───────────────────────────────────────

    def _vi_seating_circle(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Circular seating arrangement with person positions."""
        r = int(min(cw, dh) * 0.28)
        draw.ellipse([mx - r, my - r, mx + r, my + r],
                     outline=(200, 200, 200), width=int(2 * s))
        f = _get_font(int(16 * s), bold=True)
        persons = ["P1", "P2", "P3", "P4", "P5", "P6"]
        n = len(persons)
        pr = int(dh * 0.06)
        for i, p in enumerate(persons):
            angle = -math.pi / 2 + 2 * math.pi * i / n
            px = mx + int(r * math.cos(angle))
            py = my + int(r * math.sin(angle))
            draw.ellipse([px - pr, py - pr, px + pr, py + pr],
                         fill=accent, outline=(255, 255, 255), width=int(2 * s))
            tw = draw.textlength(p, font=f)
            lx = mx + int((r + int(22 * s)) * math.cos(angle))
            ly = my + int((r + int(22 * s)) * math.sin(angle))
            draw.text((lx - tw // 2, ly - f.size // 2), p, fill=accent, font=f)

    def _vi_direction_sense(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Direction sense — 8-direction compass for reasoning problems."""
        r = int(min(cw, dh) * 0.32)
        f = _get_font(int(18 * s), bold=True)
        dirs = [("N", 0), ("NE", 45), ("E", 90), ("SE", 135),
                ("S", 180), ("SW", 225), ("W", 270), ("NW", 315)]
        for label, angle in dirs:
            rad = math.radians(angle - 90)
            lx = mx + int((r + int(18 * s)) * math.cos(rad))
            ly = my + int((r + int(18 * s)) * math.sin(rad))
            tw = draw.textlength(label, font=f)
            col = (200, 60, 60) if label == "N" else accent
            draw.text((lx - tw // 2, ly - f.size // 2), label, fill=col, font=f)
            ex = mx + int(r * 0.75 * math.cos(rad))
            ey = my + int(r * 0.75 * math.sin(rad))
            draw.line([(mx, my), (ex, ey)], fill=accent, width=int(2 * s))
        draw.ellipse([mx - int(4 * s), my - int(4 * s),
                      mx + int(4 * s), my + int(4 * s)], fill=accent)

    def _vi_blood_relation(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Family tree — grandparent → parent → child."""
        f = _get_font(int(16 * s), bold=True)
        nr = int(dh * 0.08)
        levels = [("Grand Parent", my - int(dh * 0.32)),
                  ("Father    Mother", my - int(dh * 0.05)),
                  ("Child", my + int(dh * 0.22))]
        for label, y in levels:
            draw.ellipse([mx - nr * 2, y - nr, mx + nr * 2, y + nr],
                         fill=accent, outline=(255, 255, 255), width=int(2 * s))
            tw = draw.textlength(label, font=f)
            draw.text((mx - tw // 2, y - f.size // 2),
                      label, fill=(255, 255, 255), font=f)
        for i in range(len(levels) - 1):
            draw.line([(mx, levels[i][1] + nr), (mx, levels[i + 1][1] - nr)],
                      fill=(150, 150, 150), width=int(2 * s))

    # ── UNIVERSAL: New visuals ───────────────────────────────────────

    def _vi_comparison_table(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """2-column comparison table."""
        f = _get_font(int(16 * s), bold=True)
        sf = _get_font(int(14 * s))
        tw = int(cw * 0.40)
        th = int(dh * 0.14)
        x1 = mx - int(cw * 0.02) - tw
        x2 = mx + int(cw * 0.02)
        headers = [("Feature A", (200, 60, 60)), ("Feature B", (80, 140, 200))]
        for i, (h, col) in enumerate(headers):
            x = x1 if i == 0 else x2
            draw.rectangle([x, my - int(dh * 0.35), x + tw, my - int(dh * 0.35) + th],
                           fill=col)
            htw = draw.textlength(h, font=f)
            draw.text((x + (tw - htw) // 2, my - int(dh * 0.35) + (th - f.size) // 2),
                      h, fill=(255, 255, 255), font=f)
        for r in range(3):
            y = my - int(dh * 0.35) + (r + 1) * th
            for i in range(2):
                x = x1 if i == 0 else x2
                draw.rectangle([x, y, x + tw, y + th],
                               outline=(200, 200, 200), width=int(1 * s))
                draw.text((x + int(8 * s), y + (th - sf.size) // 2),
                          f"Item {r + 1}", fill=(100, 100, 100), font=sf)

    def _vi_steps_visual(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Numbered step boxes 1→2→3→4 with arrows."""
        f = _get_font(int(22 * s), bold=True)
        n = 4
        bsz = int(min(cw * 0.14, dh * 0.35))
        gap = int(cw * 0.06)
        total = n * bsz + (n - 1) * gap
        x0 = mx - total // 2
        colors = [(200, 60, 60), (239, 108, 0), (80, 140, 200), (46, 125, 50)]
        for i in range(n):
            x = x0 + i * (bsz + gap)
            draw.rounded_rectangle([x, my - bsz // 2, x + bsz, my + bsz // 2],
                                   radius=int(8 * s), fill=colors[i])
            tw = draw.textlength(str(i + 1), font=f)
            draw.text((x + (bsz - tw) // 2, my - f.size // 2),
                      str(i + 1), fill=(255, 255, 255), font=f)
            if i < n - 1:
                ax = x + bsz + int(gap * 0.15)
                draw.line([(ax, my), (ax + int(gap * 0.60), my)],
                          fill=(150, 150, 150), width=int(2 * s))

    def _vi_lightbulb(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Lightbulb icon — idea/concept."""
        r = int(dh * 0.22)
        draw.ellipse([mx - r, my - r - int(dh * 0.05), mx + r, my + r - int(dh * 0.05)],
                     fill=(255, 230, 100), outline=(239, 180, 0), width=int(3 * s))
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = mx + int((r + int(5 * s)) * math.cos(rad))
            y1 = my - int(dh * 0.05) + int((r + int(5 * s)) * math.sin(rad))
            x2 = mx + int((r + int(15 * s)) * math.cos(rad))
            y2 = my - int(dh * 0.05) + int((r + int(15 * s)) * math.sin(rad))
            draw.line([(x1, y1), (x2, y2)], fill=(239, 180, 0), width=int(2 * s))
        base_w = int(r * 0.50)
        base_y = my + r - int(dh * 0.05)
        draw.rectangle([mx - base_w, base_y, mx + base_w, base_y + int(dh * 0.10)],
                       fill=(180, 180, 180))

    def _vi_trophy(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Trophy cup — correct answer celebration."""
        cup_w = int(cw * 0.12)
        cup_h = int(dh * 0.30)
        cup_y = my - int(dh * 0.15)
        draw.rounded_rectangle([mx - cup_w, cup_y, mx + cup_w, cup_y + cup_h],
                               radius=int(8 * s), fill=(255, 200, 0),
                               outline=(200, 150, 0), width=int(3 * s))
        draw.arc([mx - cup_w - int(cw * 0.06), cup_y + int(cup_h * 0.10),
                  mx - cup_w + int(5 * s), cup_y + int(cup_h * 0.60)],
                 90, 270, fill=(200, 150, 0), width=int(3 * s))
        draw.arc([mx + cup_w - int(5 * s), cup_y + int(cup_h * 0.10),
                  mx + cup_w + int(cw * 0.06), cup_y + int(cup_h * 0.60)],
                 -90, 90, fill=(200, 150, 0), width=int(3 * s))
        stem_w = int(cup_w * 0.25)
        stem_y = cup_y + cup_h
        draw.rectangle([mx - stem_w, stem_y, mx + stem_w, stem_y + int(dh * 0.10)],
                       fill=(200, 150, 0))
        base_w = int(cup_w * 0.70)
        draw.rectangle([mx - base_w, stem_y + int(dh * 0.10),
                        mx + base_w, stem_y + int(dh * 0.14)],
                       fill=(200, 150, 0))
        f = _get_font(int(22 * s), bold=True)
        draw.text((mx - int(6 * s), cup_y + int(cup_h * 0.25)),
                  "1", fill=(200, 150, 0), font=f)

    def _vi_timeline_visual(self, draw, frame, cx, dy, cw, dh, mx, my, accent, s):
        """Horizontal timeline with event markers."""
        x0, x1 = cx + int(cw * 0.08), cx + int(cw * 0.92)
        draw.line([(x0, my), (x1, my)], fill=accent, width=int(3 * s))
        f = _get_font(int(14 * s))
        events = ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"]
        n = len(events)
        for i, ev in enumerate(events):
            x = x0 + int(i * (x1 - x0) / (n - 1))
            draw.ellipse([x - int(6 * s), my - int(6 * s),
                          x + int(6 * s), my + int(6 * s)], fill=accent)
            tw = draw.textlength(ev, font=f)
            ty = my + int(15 * s) if i % 2 == 0 else my - int(15 * s) - f.size
            draw.text((x - tw // 2, ty), ev, fill=accent, font=f)

    # ------------------------------------------------------------------
    # matplotlib_plot — scientific graphs rendered via matplotlib
    # ------------------------------------------------------------------

    def _draw_matplotlib_plot(self, draw, frame, element, y):
        """Render a matplotlib figure and embed as PIL Image.

        JSON:
          { "target": "matplotlib_plot",
            "plot_type": "line|bar|scatter|pie|histogram",
            "title": "Velocity vs Time",
            "xlabel": "Time (s)", "ylabel": "Velocity (m/s)",
            "data": {"x": [0,1,2,3,4], "y": [0,5,10,15,20]},
            "color": "blue",
            "caption": "optional caption"
          }
        Falls back to text placeholder if matplotlib is not installed.
        """
        s = self.scale
        avail_h = int(self.height * 0.38)
        avail_w = self.content_w
        cx = self.content_x
        caption = element.get("caption", "")
        cap_h = int(48 * s) if caption else 0
        plot_h = avail_h - cap_h

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from io import BytesIO

            plot_type = element.get("plot_type", "line")
            if plot_type.endswith("3d"):
                return self._draw_plot_3d(draw, frame, element, y)
            data = element.get("data", {})
            title = element.get("title", "")
            xlabel = element.get("xlabel", "")
            ylabel = element.get("ylabel", "")
            color = element.get("color", "blue")

            fig, ax = plt.subplots(figsize=(avail_w / 100, plot_h / 100), dpi=100)
            x_data = data.get("x", [])
            y_data = data.get("y", [])

            if plot_type == "bar":
                labels = data.get("labels", [str(i) for i in range(len(y_data))])
                ax.bar(labels[:len(y_data)], y_data, color=color)
            elif plot_type == "scatter":
                ax.scatter(x_data, y_data, color=color, s=50)
            elif plot_type == "pie":
                labels = data.get("labels", [str(i) for i in range(len(y_data))])
                ax.pie(y_data, labels=labels[:len(y_data)], autopct="%1.1f%%")
            elif plot_type == "histogram":
                ax.hist(y_data, bins=data.get("bins", 10), color=color, edgecolor="white")
            else:
                ax.plot(x_data, y_data, color=color, linewidth=2, marker="o", markersize=4)

            if title:
                ax.set_title(title, fontsize=14, fontweight="bold")
            if xlabel:
                ax.set_xlabel(xlabel, fontsize=11)
            if ylabel:
                ax.set_ylabel(ylabel, fontsize=11)
            if plot_type != "pie":
                ax.grid(True, alpha=0.3)
            fig.tight_layout()

            buf = BytesIO()
            fig.savefig(buf, format="PNG", bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)

            plot_img = Image.open(buf).convert("RGB")
            ratio = min(avail_w / plot_img.width, plot_h / plot_img.height)
            new_w = int(plot_img.width * ratio)
            new_h = int(plot_img.height * ratio)
            plot_img = plot_img.resize((new_w, new_h), Image.LANCZOS)
            paste_x = cx + (avail_w - new_w) // 2
            paste_y = y + (plot_h - new_h) // 2
            frame.paste(plot_img, (paste_x, paste_y))

        except ImportError:
            pf = _get_font(int(28 * s), bold=True)
            title = element.get("title", "Plot")
            tw = draw.textlength(title, font=pf)
            draw.rounded_rectangle([cx, y, cx + avail_w, y + plot_h],
                                   radius=int(10 * s), fill=(245, 245, 245))
            draw.text((cx + (avail_w - tw) / 2, y + (plot_h - pf.size) / 2),
                      title, fill=(120, 120, 120), font=pf)
            sf = _get_font(int(18 * s))
            draw.text((cx + int(20 * s), y + plot_h - int(30 * s)),
                      "pip install matplotlib", fill=(180, 180, 180), font=sf)

        if caption:
            cap_y = y + plot_h
            draw.rectangle([cx, cap_y, cx + avail_w, cap_y + cap_h], fill=(40, 40, 60))
            cf = _get_font(int(30 * s))
            cw2 = draw.textlength(caption, font=cf)
            draw.text((cx + (avail_w - cw2) / 2, cap_y + (cap_h - cf.size) / 2),
                      caption, fill=(200, 200, 255), font=cf)

        return y + avail_h

    # ------------------------------------------------------------------
    # plot_3d — 3D mathematical plots via matplotlib mpl_toolkits.mplot3d
    # ------------------------------------------------------------------

    def _draw_plot_3d(self, draw, frame, element, y):
        """3D plot: surface3d, wireframe3d, scatter3d, line3d, bar3d.

        JSON:
          { "target": "matplotlib_plot", "plot_type": "surface3d",
            "expression": "sin(x)*cos(y)",
            "x_range": [-3.14, 3.14], "y_range": [-3.14, 3.14],
            "xlabel": "x", "ylabel": "y", "zlabel": "z",
            "colormap": "viridis", "elev": 25, "azim": 45,
            "title": "z = sin(x)·cos(y)", "caption": "optional" }

          { "plot_type": "scatter3d",
            "data": {"x":[1,2,3],"y":[2,4,1],"z":[3,1,4]}, "color":"#00d4ff" }

          { "plot_type": "bar3d",
            "data": {"x":[0,1,2],"y":[0,0,0],"z":[3,5,2],
                     "dx":[0.6,0.6,0.6],"dy":[0.6,0.6,0.6]} }
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        from io import BytesIO

        s       = self.scale
        avail_h = int(self.height * 0.42)
        avail_w = self.content_w
        cx      = self.content_x
        caption = element.get("caption", "")
        cap_h   = int(48 * s) if caption else 0
        plot_h  = avail_h - cap_h

        try:
            from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

            plot_type = element.get("plot_type", "surface3d")
            data      = element.get("data", {})
            title     = element.get("title", "")
            xlabel    = element.get("xlabel", "x")
            ylabel    = element.get("ylabel", "y")
            zlabel    = element.get("zlabel", "z")
            color     = element.get("color", "#00d4ff")

            fig = plt.figure(figsize=(avail_w / 100, plot_h / 100), dpi=100)
            fig.patch.set_facecolor("#1a1a2e")
            ax = fig.add_subplot(111, projection="3d")
            ax.set_facecolor("#1a1a2e")
            for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
                pane.fill = False
                pane.set_edgecolor("#2a2a4a")
            for ln in (ax.xaxis.line, ax.yaxis.line, ax.zaxis.line):
                ln.set_color("#444466")
            ax.tick_params(colors="#888888", labelsize=7)
            for lbl in (ax.xaxis.label, ax.yaxis.label, ax.zaxis.label):
                lbl.set_color("#aaaacc")

            if plot_type in ("surface3d", "wireframe3d"):
                expr    = element.get("expression", "sin(x)*cos(y)")
                x_range = element.get("x_range", [-3.14, 3.14])
                y_range = element.get("y_range", [-3.14, 3.14])
                xv      = np.linspace(x_range[0], x_range[1], 50)
                yv      = np.linspace(y_range[0], y_range[1], 50)
                X, Y    = np.meshgrid(xv, yv)
                ns = {k: getattr(np, k) for k in
                      ("sin","cos","tan","exp","sqrt","log","abs","pi","e")}
                ns.update({"x": X, "y": Y})
                try:
                    Z = eval(expr, {"__builtins__": {}}, ns)  # pylint: disable=eval-used
                except Exception:
                    Z = np.sin(X) * np.cos(Y)
                if plot_type == "wireframe3d":
                    ax.plot_wireframe(X, Y, Z, color=color, linewidth=0.5, alpha=0.85)
                else:
                    ax.plot_surface(X, Y, Z,
                                    cmap=element.get("colormap", "viridis"),
                                    alpha=0.85, linewidth=0)

            elif plot_type == "scatter3d":
                ax.scatter(data.get("x", []), data.get("y", []), data.get("z", []),
                           c=color, s=50, depthshade=True)

            elif plot_type == "line3d":
                ax.plot(data.get("x", []), data.get("y", []), data.get("z", []),
                        color=color, linewidth=2)

            elif plot_type == "bar3d":
                xd = data.get("x", [0]); yd = data.get("y", [0]); zd = data.get("z", [1])
                dx = data.get("dx", [0.6] * len(xd))
                dy = data.get("dy", [0.6] * len(yd))
                ax.bar3d(xd, yd, [0] * len(zd), dx, dy, zd,
                         color=color, alpha=0.8, shade=True)

            ax.set_xlabel(xlabel, labelpad=6)
            ax.set_ylabel(ylabel, labelpad=6)
            ax.set_zlabel(zlabel, labelpad=6)
            if title:
                ax.set_title(title, color="white", fontsize=int(13 * s),
                             fontweight="bold", pad=8)
            ax.view_init(elev=element.get("elev", 25), azim=element.get("azim", 45))
            plt.tight_layout(pad=0.3)

            buf = BytesIO()
            fig.savefig(buf, format="PNG", bbox_inches="tight",
                        facecolor="#1a1a2e", dpi=100)
            plt.close(fig)
            buf.seek(0)
            plot_img = Image.open(buf).convert("RGB")
            ratio    = min(avail_w / plot_img.width, plot_h / plot_img.height)
            new_w    = int(plot_img.width  * ratio)
            new_h    = int(plot_img.height * ratio)
            plot_img = plot_img.resize((new_w, new_h), Image.LANCZOS)
            frame.paste(plot_img, (cx + (avail_w - new_w) // 2,
                                   y  + (plot_h  - new_h) // 2))

        except Exception as err:
            pf = _get_font(int(26 * s))
            draw.rounded_rectangle([cx, y, cx + avail_w, y + plot_h],
                                   radius=int(10 * s), fill=(30, 30, 50))
            draw.text((cx + int(20 * s), y + int(20 * s)),
                      f"3D plot error: {err}", fill=(200, 100, 100), font=pf)

        if caption:
            cap_y = y + plot_h
            draw.rectangle([cx, cap_y, cx + avail_w, cap_y + cap_h], fill=(40, 40, 60))
            cf  = _get_font(int(30 * s))
            cw2 = draw.textlength(caption, font=cf)
            draw.text((cx + (avail_w - cw2) / 2, cap_y + (cap_h - cf.size) / 2),
                      caption, fill=(200, 200, 255), font=cf)

        return y + avail_h

    # ------------------------------------------------------------------
    # map_plot — geographic maps via geopandas + matplotlib
    # ------------------------------------------------------------------

    def _draw_map_plot(self, draw, frame, element, y):
        """Geographic map: world highlight, choropleth, India states.

        JSON:
          { "target": "map_plot",
            "map_type": "world_highlight | world_choropleth | india_states | india_choropleth",
            "highlight": ["India", "China"],
            "data": {"India": 85, "China": 92},
            "title": "Title", "caption": "Caption",
            "color_scheme": "YlOrRd",
            "label_highlighted": true }
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from io import BytesIO

        s       = self.scale
        avail_h = int(self.height * 0.44)
        avail_w = self.content_w
        cx      = self.content_x
        caption = element.get("caption", "")
        cap_h   = int(48 * s) if caption else 0
        plot_h  = avail_h - cap_h

        try:
            import geopandas as gpd

            map_type    = element.get("map_type", "world_highlight")
            highlight   = element.get("highlight", [])
            data_vals   = element.get("data", {})
            title       = element.get("title", "")
            cmap        = element.get("color_scheme", "YlOrRd")
            show_labels = element.get("label_highlighted", True)

            def _load_world():
                try:
                    return gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
                except Exception:
                    pass
                try:
                    from geodatasets import get_path as _gp
                    return gpd.read_file(_gp("naturalearth.land"))
                except Exception:
                    pass
                return None

            def _load_india_states():
                import os, urllib.request
                cache_dir  = os.path.join(os.path.dirname(__file__),
                                          "..", "storage", "assets", "map_data")
                os.makedirs(cache_dir, exist_ok=True)
                cache_file = os.path.join(cache_dir, "india_states.geojson")
                if not os.path.exists(cache_file):
                    url = ("https://raw.githubusercontent.com/geohacker/india"
                           "/master/state/india_state.geojson")
                    try:
                        urllib.request.urlretrieve(url, cache_file)
                    except Exception:
                        return None
                try:
                    return gpd.read_file(cache_file)
                except Exception:
                    return None

            fig, ax = plt.subplots(figsize=(avail_w / 100, plot_h / 100), dpi=100)
            fig.patch.set_facecolor("#0d1117")
            ax.set_facecolor("#0d1117")

            if map_type in ("world_highlight", "world_choropleth"):
                world = _load_world()
                if world is None:
                    raise ImportError("geopandas world data unavailable — pip install geopandas geodatasets")
                if map_type == "world_choropleth" and data_vals:
                    world["_val"] = world["name"].map(data_vals)
                    world.plot(column="_val", ax=ax, legend=True,
                               missing_kwds={"color": "#1e2a3a", "edgecolor": "#2a3a4a"},
                               cmap=cmap, edgecolor="#2a3a4a", linewidth=0.4)
                else:
                    colors = ["#00d4ff" if n in highlight else "#1e2a3a"
                              for n in world["name"]]
                    world.plot(ax=ax, color=colors, edgecolor="#2a3a4a", linewidth=0.4)
                    if show_labels:
                        for _, row in world.iterrows():
                            if row["name"] in highlight:
                                c = row.geometry.centroid
                                ax.annotate(row["name"], (c.x, c.y),
                                            ha="center", fontsize=7,
                                            color="white", fontweight="bold",
                                            bbox=dict(boxstyle="round,pad=0.15",
                                                      facecolor="#00d4ff",
                                                      alpha=0.75, edgecolor="none"))

            elif map_type in ("india_states", "india_choropleth"):
                india = _load_india_states()
                if india is None:
                    world = _load_world()
                    if world is None:
                        raise ImportError("Map data unavailable")
                    colors = ["#00d4ff" if n == "India" else "#1e2a3a"
                              for n in world["name"]]
                    world.plot(ax=ax, color=colors, edgecolor="#2a3a4a", linewidth=0.4)
                    row_in = world[world["name"] == "India"]
                    if not row_in.empty:
                        mnx, mny, mxx, mxy = row_in.total_bounds
                        ax.set_xlim(mnx - 2, mxx + 2); ax.set_ylim(mny - 2, mxy + 2)
                else:
                    name_col = next((c for c in ("NAME_1", "ST_NM", "name", "state", "NAME")
                                     if c in india.columns), india.columns[0])
                    if map_type == "india_choropleth" and data_vals:
                        india["_val"] = india[name_col].map(data_vals)
                        india.plot(column="_val", ax=ax, legend=True,
                                   missing_kwds={"color": "#1e2a3a"},
                                   cmap=cmap, edgecolor="#4a5a6a", linewidth=0.6)
                    else:
                        colors = ["#00d4ff" if n in highlight else "#1e2a3a"
                                  for n in india[name_col]]
                        india.plot(ax=ax, color=colors, edgecolor="#4a5a6a", linewidth=0.6)
                        if show_labels:
                            for _, row in india.iterrows():
                                if row[name_col] in highlight:
                                    c = row.geometry.centroid
                                    ax.annotate(row[name_col], (c.x, c.y),
                                                ha="center", fontsize=7,
                                                color="white", fontweight="bold",
                                                bbox=dict(boxstyle="round,pad=0.15",
                                                          facecolor="#00d4ff",
                                                          alpha=0.75, edgecolor="none"))

            ax.axis("off")
            if title:
                ax.set_title(title, color="white", fontsize=int(13 * s),
                             fontweight="bold", pad=6)
            plt.tight_layout(pad=0.2)

            buf = BytesIO()
            fig.savefig(buf, format="PNG", bbox_inches="tight",
                        facecolor="#0d1117", dpi=100)
            plt.close(fig)
            buf.seek(0)
            plot_img = Image.open(buf).convert("RGB")
            ratio    = min(avail_w / plot_img.width, plot_h / plot_img.height)
            new_w    = int(plot_img.width  * ratio)
            new_h    = int(plot_img.height * ratio)
            plot_img = plot_img.resize((new_w, new_h), Image.LANCZOS)
            frame.paste(plot_img, (cx + (avail_w - new_w) // 2,
                                   y  + (plot_h  - new_h) // 2))

        except ImportError as err:
            pf = _get_font(int(30 * s))
            draw.rounded_rectangle([cx, y, cx + avail_w, y + plot_h],
                                   radius=int(10 * s), fill=(20, 30, 50))
            msg = str(err) or "pip install geopandas geodatasets"
            mw  = draw.textlength(msg, font=pf)
            draw.text((cx + (avail_w - mw) / 2, y + (plot_h - pf.size) / 2),
                      msg, fill=(100, 180, 255), font=pf)
        except Exception as err:
            pf = _get_font(int(26 * s))
            draw.rounded_rectangle([cx, y, cx + avail_w, y + plot_h],
                                   radius=int(10 * s), fill=(30, 20, 40))
            draw.text((cx + int(20 * s), y + int(20 * s)),
                      f"Map error: {err}", fill=(220, 100, 100), font=pf)

        if caption:
            cap_y = y + plot_h
            draw.rectangle([cx, cap_y, cx + avail_w, cap_y + cap_h], fill=(40, 40, 60))
            cf  = _get_font(int(30 * s))
            cw2 = draw.textlength(caption, font=cf)
            draw.text((cx + (avail_w - cw2) / 2, cap_y + (cap_h - cf.size) / 2),
                      caption, fill=(200, 200, 255), font=cf)

        return y + avail_h

    # ------------------------------------------------------------------
    # geometry_3d — 3D solids: cube, cylinder, cone, sphere, pyramid, prism
    # ------------------------------------------------------------------

    def _draw_geometry_3d(self, draw, frame, element, y):
        """3D geometric solid rendered with matplotlib mpl_toolkits.mplot3d.

        JSON:
          { "target": "geometry_3d",
            "shape": "cube|cuboid|cylinder|cone|sphere|pyramid|prism",
            "dimensions": {"side": 4} | {"length":6,"width":3,"height":4} |
                          {"radius":3,"height":8} | {"base":4,"height":5},
            "color": "#00d4ff",
            "show_dimensions": true,
            "label": "Cube (a = 4 cm)",
            "caption": "Volume = a³ = 64 cm³",
            "elev": 20, "azim": 45 }
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        from io import BytesIO

        s       = self.scale
        avail_h = int(self.height * 0.42)
        avail_w = self.content_w
        cx      = self.content_x
        caption = element.get("caption", "")
        cap_h   = int(48 * s) if caption else 0
        plot_h  = avail_h - cap_h

        try:
            from mpl_toolkits.mplot3d import Axes3D            # noqa: F401
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection

            shape     = element.get("shape", "cube")
            dims      = element.get("dimensions", {})
            label     = element.get("label", shape.replace("_", " ").title())
            color_hex = element.get("color", "#00d4ff")
            show_dims = element.get("show_dimensions", True)
            elev      = element.get("elev", 20)
            azim      = element.get("azim", 45)

            h_str = color_hex.lstrip("#")
            fc    = tuple(int(h_str[i:i+2], 16) / 255 for i in (0, 2, 4))

            fig = plt.figure(figsize=(avail_w / 100, plot_h / 100), dpi=100)
            fig.patch.set_facecolor("#1a1a2e")
            ax  = fig.add_subplot(111, projection="3d")
            ax.set_facecolor("#1a1a2e")
            for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
                pane.fill = False
                pane.set_edgecolor("#2a2a4a")
            for ln in (ax.xaxis.line, ax.yaxis.line, ax.zaxis.line):
                ln.set_color("#333355")
            ax.tick_params(colors="#666688", labelsize=6)
            ax.grid(True, alpha=0.12, color="#2a2a5a")

            af = 0.55   # face alpha
            ec = "#ffffff"
            lw = 0.7

            def _add_box(lx, ly, lz):
                v = np.array([[0,0,0],[lx,0,0],[lx,ly,0],[0,ly,0],
                               [0,0,lz],[lx,0,lz],[lx,ly,lz],[0,ly,lz]], float)
                faces = [v[[0,1,2,3]], v[[4,5,6,7]],
                         v[[0,1,5,4]], v[[2,3,7,6]],
                         v[[0,3,7,4]], v[[1,2,6,5]]]
                ax.add_collection3d(Poly3DCollection(faces, alpha=af,
                                    facecolor=fc, edgecolor=ec, linewidth=lw))
                ax.set_xlim(-0.3, lx+0.3)
                ax.set_ylim(-0.3, ly+0.3)
                ax.set_zlim(0, lz+0.3)
                if show_dims:
                    kw = {"color": "white", "fontsize": 9, "ha": "center"}
                    ax.text(lx/2,  -0.5,  -0.4, f"{lx}", **kw)
                    ax.text(lx+0.4, ly/2, -0.4, f"{ly}", **kw)
                    ax.text(-0.5,  -0.5,   lz/2, f"{lz}", **kw)

            if shape in ("cube", "cuboid"):
                lx = dims.get("length", dims.get("side", 4))
                ly = dims.get("width",  dims.get("side", lx))
                lz = dims.get("height", dims.get("side", lx))
                _add_box(float(lx), float(ly), float(lz))

            elif shape == "cylinder":
                r   = float(dims.get("radius", 3))
                h_c = float(dims.get("height", 6))
                th  = np.linspace(0, 2 * np.pi, 60)
                ax.plot_surface(np.array([r*np.cos(th), r*np.cos(th)]),
                                np.array([r*np.sin(th), r*np.sin(th)]),
                                np.array([np.zeros_like(th), np.full_like(th, h_c)]),
                                color=fc, alpha=af, linewidth=0)
                th2, rr = np.meshgrid(th, [0, r])
                for z_cap in (0, h_c):
                    ax.plot_surface(rr*np.cos(th2), rr*np.sin(th2),
                                    np.full_like(th2, z_cap), color=fc, alpha=af, linewidth=0)
                ax.set_xlim(-r-.3, r+.3); ax.set_ylim(-r-.3, r+.3); ax.set_zlim(0, h_c+.3)
                if show_dims:
                    ax.text(r+.3, 0, h_c/2, f"h={h_c}", color="white", fontsize=9)
                    ax.text(0, r+.3, -.5, f"r={r}", color="white", fontsize=9)

            elif shape == "cone":
                r   = float(dims.get("radius", 3))
                h_c = float(dims.get("height", 6))
                th  = np.linspace(0, 2 * np.pi, 60)
                zv  = np.linspace(0, h_c, 40)
                T, Z = np.meshgrid(th, zv)
                Rv   = r * (1 - Z / h_c)
                ax.plot_surface(Rv*np.cos(T), Rv*np.sin(T), Z,
                                color=fc, alpha=af, linewidth=0)
                th2, rr = np.meshgrid(th, [0, r])
                ax.plot_surface(rr*np.cos(th2), rr*np.sin(th2),
                                np.zeros_like(th2), color=fc, alpha=af, linewidth=0)
                ax.set_xlim(-r-.3, r+.3); ax.set_ylim(-r-.3, r+.3); ax.set_zlim(0, h_c+.3)
                if show_dims:
                    ax.text(r+.3, 0, h_c/2, f"h={h_c}", color="white", fontsize=9)
                    ax.text(0, r+.3, -.5, f"r={r}", color="white", fontsize=9)

            elif shape == "sphere":
                r  = float(dims.get("radius", 3))
                u  = np.linspace(0, 2*np.pi, 60)
                va = np.linspace(0, np.pi, 40)
                U, V = np.meshgrid(u, va)
                ax.plot_surface(r*np.cos(U)*np.sin(V),
                                r*np.sin(U)*np.sin(V),
                                r*np.cos(V), color=fc, alpha=af, linewidth=0)
                d = r + .3
                ax.set_xlim(-d, d); ax.set_ylim(-d, d); ax.set_zlim(-d, d)
                if show_dims:
                    ax.text(r+.3, 0, 0, f"r={r}", color="white", fontsize=9)

            elif shape == "pyramid":
                bl = float(dims.get("base", dims.get("length", 4)))
                bw = float(dims.get("width", bl))
                hp = float(dims.get("height", 5))
                apex = np.array([bl/2, bw/2, hp])
                b    = np.array([[0,0,0],[bl,0,0],[bl,bw,0],[0,bw,0]], float)
                faces = [b.tolist(),
                         [b[0].tolist(), b[1].tolist(), apex.tolist()],
                         [b[1].tolist(), b[2].tolist(), apex.tolist()],
                         [b[2].tolist(), b[3].tolist(), apex.tolist()],
                         [b[3].tolist(), b[0].tolist(), apex.tolist()]]
                ax.add_collection3d(Poly3DCollection(faces, alpha=af,
                                    facecolor=fc, edgecolor=ec, linewidth=lw))
                ax.set_xlim(-.3, bl+.3); ax.set_ylim(-.3, bw+.3); ax.set_zlim(0, hp+.3)
                if show_dims:
                    ax.text(bl/2, -.5, -.4, f"l={bl}", color="white", fontsize=9, ha="center")
                    ax.text(bl+.3, bw/2, -.4, f"w={bw}", color="white", fontsize=9)
                    ax.text(-.5, -.5, hp/2, f"h={hp}", color="white", fontsize=9)

            elif shape in ("prism", "triangular_prism"):
                base = float(dims.get("base", 4))
                lng  = float(dims.get("length", 6))
                ht   = float(dims.get("height", 3))
                v    = np.array([[0,0,0],[base,0,0],[base/2,0,ht],
                                  [0,lng,0],[base,lng,0],[base/2,lng,ht]], float)
                faces = [v[[0,1,2]].tolist(), v[[3,4,5]].tolist(),
                         v[[0,1,4,3]].tolist(), v[[1,2,5,4]].tolist(),
                         v[[0,2,5,3]].tolist()]
                ax.add_collection3d(Poly3DCollection(faces, alpha=af,
                                    facecolor=fc, edgecolor=ec, linewidth=lw))
                ax.set_xlim(-.3, base+.3); ax.set_ylim(-.3, lng+.3); ax.set_zlim(0, ht+.3)
                if show_dims:
                    ax.text(base/2, -.5, -.3, f"b={base}", color="white", fontsize=9, ha="center")
                    ax.text(base+.3, lng/2, -.3, f"l={lng}", color="white", fontsize=9)
                    ax.text(-.5, -.5, ht/2, f"h={ht}", color="white", fontsize=9)

            ax.view_init(elev=elev, azim=azim)
            if label:
                ax.set_title(label, color="white", fontsize=int(12 * s),
                             fontweight="bold", pad=6)
            if not show_dims:
                ax.set_xticklabels([]); ax.set_yticklabels([]); ax.set_zticklabels([])
            plt.tight_layout(pad=0.3)

            buf = BytesIO()
            fig.savefig(buf, format="PNG", bbox_inches="tight",
                        facecolor="#1a1a2e", dpi=100)
            plt.close(fig)
            buf.seek(0)
            plot_img = Image.open(buf).convert("RGB")
            ratio    = min(avail_w / plot_img.width, plot_h / plot_img.height)
            new_w    = int(plot_img.width  * ratio)
            new_h    = int(plot_img.height * ratio)
            plot_img = plot_img.resize((new_w, new_h), Image.LANCZOS)
            frame.paste(plot_img, (cx + (avail_w - new_w) // 2,
                                   y  + (plot_h  - new_h) // 2))

        except Exception as err:
            pf = _get_font(int(26 * s))
            draw.rounded_rectangle([cx, y, cx + avail_w, y + plot_h],
                                   radius=int(10 * s), fill=(25, 25, 45))
            draw.text((cx + int(20 * s), y + int(20 * s)),
                      f"Geometry 3D error: {err}", fill=(200, 100, 100), font=pf)

        if caption:
            cap_y = y + plot_h
            draw.rectangle([cx, cap_y, cx + avail_w, cap_y + cap_h], fill=(40, 40, 60))
            cf  = _get_font(int(30 * s))
            cw2 = draw.textlength(caption, font=cf)
            draw.text((cx + (avail_w - cw2) / 2, cap_y + (cap_h - cf.size) / 2),
                      caption, fill=(200, 200, 255), font=cf)

        return y + avail_h

    # ------------------------------------------------------------------
    # rdkit_mol — 2D molecular structure from SMILES
    # ------------------------------------------------------------------

    def _draw_rdkit_mol(self, draw, frame, element, y):
        """Render a 2D molecular structure from SMILES string using RDKit.

        JSON:
          { "target": "rdkit_mol",
            "smiles": "c1ccccc1",
            "name": "Benzene",
            "caption": "Aromatic hydrocarbon"
          }
        Falls back to builtin_visual "molecule" if RDKit is not installed.
        """
        s = self.scale
        avail_h = int(self.height * 0.35)
        avail_w = self.content_w
        cx = self.content_x
        name = element.get("name", "")
        caption = element.get("caption", "")
        smiles = element.get("smiles", "")
        cap_h = int(48 * s) if caption else 0
        img_h = avail_h - cap_h

        draw.rounded_rectangle([cx, y, cx + avail_w, y + avail_h],
                               radius=int(10 * s), fill=(245, 245, 245))

        rendered = False
        try:
            from rdkit import Chem
            from rdkit.Chem import Draw as ChemDraw
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                mol_img = ChemDraw.MolToImage(mol, size=(min(avail_w, img_h * 2), img_h))
                mol_img = mol_img.convert("RGB")
                ratio = min(avail_w / mol_img.width, img_h / mol_img.height) * 0.85
                new_w = int(mol_img.width * ratio)
                new_h = int(mol_img.height * ratio)
                mol_img = mol_img.resize((new_w, new_h), Image.LANCZOS)
                paste_x = cx + (avail_w - new_w) // 2
                paste_y = y + (img_h - new_h) // 2
                frame.paste(mol_img, (paste_x, paste_y))
                rendered = True
        except ImportError:
            pass

        if not rendered:
            pf = _get_font(int(32 * s), bold=True)
            display = name or smiles or "Molecule"
            tw = draw.textlength(display, font=pf)
            draw.text((cx + (avail_w - tw) / 2, y + (img_h - pf.size) / 2 - int(15 * s)),
                      display, fill=(21, 101, 192), font=pf)
            sf = _get_font(int(20 * s))
            if smiles:
                tw2 = draw.textlength(f"SMILES: {smiles}", font=sf)
                draw.text((cx + (avail_w - tw2) / 2, y + (img_h + pf.size) / 2),
                          f"SMILES: {smiles}", fill=(120, 120, 120), font=sf)

        if name and rendered:
            nf = _get_font(int(24 * s), bold=True)
            tw3 = draw.textlength(name, font=nf)
            draw.text((cx + (avail_w - tw3) / 2, y + int(8 * s)),
                      name, fill=(21, 101, 192), font=nf)

        if caption:
            cap_y = y + img_h
            draw.rectangle([cx, cap_y, cx + avail_w, cap_y + cap_h], fill=(40, 40, 60))
            cf = _get_font(int(30 * s))
            cw2 = draw.textlength(caption, font=cf)
            draw.text((cx + (avail_w - cw2) / 2, cap_y + (cap_h - cf.size) / 2),
                      caption, fill=(200, 200, 255), font=cf)

        return y + avail_h

    # ------------------------------------------------------------------
    # manim_scene — animated Manim scene composited from pre-rendered frames
    # ------------------------------------------------------------------

    def _draw_manim_scene(self, draw, frame, element, y, current_time=0):
        """Render a pre-rendered Manim animation frame.

        JSON:
          { "target": "manim_scene",
            "scene_type": "function_plot",
            "params": { "function": "np.sin(x)", "x_range": [-4,4], ... },
            "caption": "y = sin(x)"
          }

        Pipeline pre-renders the scene and injects _manim_cache_dir,
        _manim_total_frames, _step_start, _step_end into the element.
        This method reads the correct frame based on animation progress.
        Falls back to a styled placeholder if Manim is not installed.
        """
        s = self.scale
        avail_h = int(self.height * 0.42)
        avail_w = self.content_w
        cx = self.content_x
        caption = element.get("caption", "")
        cap_h = int(48 * s) if caption else 0
        img_h = avail_h - cap_h

        cache_dir = element.get("_manim_cache_dir")
        step_start = element.get("_step_start", 0)
        step_end = element.get("_step_end", 1)
        step_dur = max(step_end - step_start, 0.001)
        progress = max(0.0, min((current_time - step_start) / step_dur, 1.0))

        rendered = False
        if cache_dir:
            try:
                from engine.manim_renderer import get_frame_path
                fpath = get_frame_path(cache_dir, progress)
                if fpath and os.path.exists(fpath):
                    manim_img = Image.open(fpath).convert("RGB")
                    ratio = min(avail_w / manim_img.width,
                                img_h / manim_img.height) * 0.95
                    new_w = int(manim_img.width * ratio)
                    new_h = int(manim_img.height * ratio)
                    manim_img = manim_img.resize((new_w, new_h), Image.LANCZOS)
                    paste_x = cx + (avail_w - new_w) // 2
                    paste_y = y + (img_h - new_h) // 2
                    frame.paste(manim_img, (paste_x, paste_y))
                    rendered = True
            except Exception:
                pass

        if not rendered:
            # Fallback placeholder
            scene_type = element.get("scene_type", "animation")
            draw.rounded_rectangle([cx, y, cx + avail_w, y + img_h],
                                   radius=int(10 * s), fill=(30, 30, 50))
            # Play-button triangle icon
            icon_size = int(60 * s)
            mx, my = cx + avail_w // 2, y + img_h // 2 - int(20 * s)
            draw.polygon([(mx - icon_size // 2, my - icon_size // 2),
                          (mx - icon_size // 2, my + icon_size // 2),
                          (mx + icon_size // 2, my)],
                         fill=(80, 140, 255))

            tf = _get_font(int(30 * s), bold=True)
            title = f"Manim: {scene_type}"
            tw = draw.textlength(title, font=tf)
            draw.text((cx + (avail_w - tw) / 2, my + icon_size // 2 + int(15 * s)),
                      title, fill=(120, 180, 255), font=tf)

            sf = _get_font(int(18 * s))
            hint = "pip install manim"
            hw = draw.textlength(hint, font=sf)
            draw.text((cx + (avail_w - hw) / 2, y + img_h - int(30 * s)),
                      hint, fill=(100, 100, 140), font=sf)

        if caption:
            cap_y = y + img_h
            draw.rectangle([cx, cap_y, cx + avail_w, cap_y + cap_h],
                           fill=(40, 40, 60))
            cf = _get_font(int(30 * s))
            cw2 = draw.textlength(caption, font=cf)
            draw.text((cx + (avail_w - cw2) / 2, cap_y + (cap_h - cf.size) / 2),
                      caption, fill=(200, 200, 255), font=cf)

        return y + avail_h

    # ------------------------------------------------------------------
    # subject_image — fetch free image via Pixabay and embed it
    # ------------------------------------------------------------------

    def _draw_subject_image(self, draw, frame, element, y):
        """Embed a Pixabay free image (fetched + cached on demand).

        JSON:
          { "target": "subject_image",
            "query":   "animal cell biology microscope",
            "subject": "biology",
            "topic":   "cell",
            "caption": "Animal Cell under microscope"
          }
        The pipeline pre-resolves src_path; renderer uses it if present,
        otherwise attempts a live fetch.
        """
        src_path = element.get("src_path", "")
        caption  = element.get("caption",  "")
        query    = element.get("query",    "")
        subject  = element.get("subject",  "")
        topic    = element.get("topic",    "")
        s        = self.scale

        # Try live fetch if no pre-resolved path
        if not src_path or not os.path.exists(src_path):
            try:
                from engine.free_media import resolve_media
                src_path = resolve_media(query, "image", subject, topic)
            except Exception:
                src_path = ""

        avail_h = int(self.height * 0.35)
        avail_w = self.content_w
        cx      = self.content_x
        cap_h   = int(48 * s) if caption else 0
        img_h   = avail_h - cap_h

        # Background card
        draw.rounded_rectangle(
            [cx, y, cx + avail_w, y + avail_h],
            radius=int(10 * s), fill=(245, 245, 245),
        )

        if src_path and os.path.exists(src_path):
            try:
                img      = Image.open(src_path).convert("RGB")
                ratio    = min(avail_w / img.width, img_h / img.height)
                new_w    = int(img.width  * ratio)
                new_h    = int(img.height * ratio)
                img      = img.resize((new_w, new_h), Image.LANCZOS)
                paste_x  = cx + (avail_w - new_w) // 2
                paste_y  = y  + (img_h   - new_h) // 2
                frame.paste(img, (paste_x, paste_y))
            except Exception:
                pass
        else:
            pf = _get_font(int(36 * s), bold=True)
            msg = query or "Image unavailable"
            tw  = draw.textlength(msg, font=pf)
            draw.text((cx + (avail_w - tw) / 2, y + (img_h - pf.size) / 2),
                      msg, fill=(160, 160, 160), font=pf)

        if caption:
            cap_y = y + img_h
            draw.rectangle([cx, cap_y, cx + avail_w, cap_y + cap_h],
                           fill=(40, 40, 60))
            cf  = _get_font(int(30 * s))
            cw2 = draw.textlength(caption, font=cf)
            draw.text((cx + (avail_w - cw2) / 2, cap_y + (cap_h - cf.size) / 2),
                      caption, fill=(200, 200, 255), font=cf)

        return y + avail_h

    # ==================================================================
    # DEGREE-LEVEL DEDICATED TARGET RENDERERS
    # ==================================================================

    def _draw_latex_equation(self, draw, frame, element, y):
        """Render LaTeX equation via matplotlib.mathtext."""
        value = element.get("value", "")
        s = self.scale
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from io import BytesIO
            fig, ax = plt.subplots(figsize=(12, 2), dpi=150)
            ax.axis("off")
            fontsize = max(16, int(28 * s))
            ax.text(0.5, 0.5, value, fontsize=fontsize, ha="center", va="center",
                    transform=ax.transAxes, color="#1A237E")
            fig.patch.set_facecolor("white")
            fig.tight_layout(pad=0.5)
            buf = BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
            plt.close(fig)
            buf.seek(0)
            img = Image.open(buf).convert("RGB")
            ratio = min(self.content_w / img.width, int(200 * s) / img.height)
            new_w, new_h = int(img.width * ratio), int(img.height * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            px = self.content_x + (self.content_w - new_w) // 2
            frame.paste(img, (px, int(y)))
            return y + new_h + int(20 * s)
        except Exception:
            return self._draw_equation_element(draw, frame,
                {"type": "equation", "value": value, "highlighted": False}, y)

    def _draw_derivation_chain(self, draw, frame, element, y):
        """Step-by-step LaTeX derivation — renders each step."""
        steps = element.get("steps", [])
        s = self.scale
        for step_text in steps:
            y = self._draw_latex_equation(draw, frame, {"value": step_text}, y)
            y += int(8 * s)
        return y

    def _draw_circuit_diagram(self, draw, frame, element, y):
        """Electric circuit via schemdraw → PIL."""
        components = element.get("components", [])
        topology = element.get("topology", "series")
        s = self.scale
        try:
            import schemdraw
            import schemdraw.elements as elm
            from io import BytesIO
            with schemdraw.Drawing(show=False) as d:
                d.config(fontsize=14)
                comp_map = {
                    "resistor": elm.Resistor, "capacitor": elm.Capacitor,
                    "inductor": elm.Inductor, "battery": elm.Battery,
                    "switch": elm.Switch, "ground": elm.Ground,
                    "wire": elm.Line, "bulb": elm.Lamp,
                }
                for c in components:
                    ctype = c.get("type", "wire")
                    label = c.get("label", "")
                    elem_cls = comp_map.get(ctype, elm.Line)
                    el_drawn = d.add(elem_cls().label(label) if label else elem_cls())
                if topology == "series":
                    d.add(elm.Line().down())
                    d.add(elm.Line().left().tox(d.anchors.get("start", (0,0))[0] if hasattr(d, 'anchors') else 0))
            buf = BytesIO()
            d.save(buf, fmt="png", dpi=150)
            buf.seek(0)
            img = Image.open(buf).convert("RGB")
            ratio = min(self.content_w / img.width, int(350 * s) / img.height)
            new_w, new_h = int(img.width * ratio), int(img.height * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            px = self.content_x + (self.content_w - new_w) // 2
            frame.paste(img, (px, int(y)))
            return y + new_h + int(20 * s)
        except Exception:
            return self._draw_builtin_visual(draw, frame,
                {"type": "builtin_visual", "visual": "circuit", "label": "Circuit Diagram", "color": "blue"}, y)

    def _draw_bohr_model(self, draw, frame, element, y):
        """Bohr atomic model with concentric electron shells."""
        symbol = element.get("element", element.get("symbol", "?"))
        atomic_num = element.get("atomic_number", 0)
        shells = element.get("electrons_per_shell", [])
        s = self.scale
        cx_center = self.content_x + self.content_w // 2
        cy_center = int(y + 160 * s)
        nucleus_r = int(30 * s)
        shell_gap = int(45 * s)
        # Nucleus
        draw.ellipse([cx_center - nucleus_r, cy_center - nucleus_r,
                      cx_center + nucleus_r, cy_center + nucleus_r],
                     fill=(200, 50, 50))
        nf = _get_font(int(28 * s), bold=True)
        ntxt = f"{symbol}\n{atomic_num}"
        draw.text((cx_center - int(15 * s), cy_center - int(18 * s)), ntxt,
                  fill=(255, 255, 255), font=nf)
        # Shells
        import math
        for i, e_count in enumerate(shells):
            r = nucleus_r + (i + 1) * shell_gap
            draw.ellipse([cx_center - r, cy_center - r, cx_center + r, cy_center + r],
                         outline=(80, 80, 180), width=int(2 * s))
            # Electrons as dots
            for j in range(e_count):
                angle = 2 * math.pi * j / e_count - math.pi / 2
                ex = cx_center + int(r * math.cos(angle))
                ey = cy_center + int(r * math.sin(angle))
                dot_r = int(6 * s)
                draw.ellipse([ex - dot_r, ey - dot_r, ex + dot_r, ey + dot_r],
                             fill=(0, 100, 255))
            # Shell label
            lf = _get_font(int(20 * s))
            draw.text((cx_center + r + int(5 * s), cy_center - int(10 * s)),
                      f"n={i+1} ({e_count}e⁻)", fill=(80, 80, 180), font=lf)
        total_h = nucleus_r + len(shells) * shell_gap + int(60 * s)
        return y + total_h * 2

    def _draw_free_body_diagram(self, draw, frame, element, y):
        """Force vector arrows from center object."""
        forces = element.get("forces", [])
        s = self.scale
        cx = self.content_x + self.content_w // 2
        cy = int(y + 180 * s)
        box_size = int(50 * s)
        # Object box
        draw.rounded_rectangle([cx - box_size, cy - box_size, cx + box_size, cy + box_size],
                               radius=int(8 * s), fill=(220, 220, 240), outline=(60, 60, 100), width=int(2 * s))
        bf = _get_font(int(22 * s), bold=True)
        draw.text((cx - int(15 * s), cy - int(12 * s)), "obj", fill=(60, 60, 100), font=bf)
        # Arrows
        dir_map = {
            "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
            "diagonal_ur": (0.7, -0.7), "diagonal_ul": (-0.7, -0.7),
            "diagonal_dr": (0.7, 0.7), "diagonal_dl": (-0.7, 0.7),
        }
        arrow_len = int(120 * s)
        lf = _get_font(int(24 * s), bold=True)
        colors = [(220, 50, 50), (50, 50, 220), (50, 180, 50), (200, 120, 0)]
        for i, f in enumerate(forces):
            direction = f.get("direction", "up")
            label = f.get("label", "F")
            dx, dy = dir_map.get(direction, (0, -1))
            x1 = cx + int(dx * box_size)
            y1 = cy + int(dy * box_size)
            x2 = cx + int(dx * (box_size + arrow_len))
            y2 = cy + int(dy * (box_size + arrow_len))
            color = colors[i % len(colors)]
            draw.line([x1, y1, x2, y2], fill=color, width=int(4 * s))
            # Arrowhead
            draw.polygon([(x2, y2),
                          (x2 - int(dx * 12 * s) + int(dy * 8 * s), y2 - int(dy * 12 * s) - int(dx * 8 * s)),
                          (x2 - int(dx * 12 * s) - int(dy * 8 * s), y2 - int(dy * 12 * s) + int(dx * 8 * s))],
                         fill=color)
            draw.text((x2 + int(5 * s), y2 - int(12 * s)), label, fill=color, font=lf)
        return y + int(380 * s)

    def _draw_wave_diagram(self, draw, frame, element, y):
        """Transverse/longitudinal wave with labeled parts."""
        import math
        wave_type = element.get("wave_type", "transverse")
        params = element.get("params", {})
        wavelength = params.get("wavelength", 2)
        amplitude = params.get("amplitude", 1)
        label_parts = params.get("label_parts", True)
        s = self.scale
        cx = self.content_x + int(40 * s)
        w = self.content_w - int(80 * s)
        h = int(200 * s)
        mid_y = int(y + h // 2)
        # Axis
        draw.line([cx, mid_y, cx + w, mid_y], fill=(180, 180, 180), width=int(1 * s))
        # Wave
        points = []
        for px in range(w):
            t = px / w * 4 * math.pi
            wy = mid_y - int(amplitude * (h * 0.35) * math.sin(t))
            points.append((cx + px, wy))
        for i in range(len(points) - 1):
            draw.line([points[i], points[i+1]], fill=(0, 100, 220), width=int(3 * s))
        if label_parts:
            lf = _get_font(int(20 * s))
            # Crest
            draw.text((cx + w // 8, int(y + 10 * s)), "Crest", fill=(220, 50, 50), font=lf)
            # Trough
            draw.text((cx + w * 3 // 8, int(y + h - 30 * s)), "Trough", fill=(220, 50, 50), font=lf)
            # Wavelength arrow
            lam_y = int(y + h + 10 * s)
            qw = w // 4
            draw.line([cx + qw, lam_y, cx + qw * 3, lam_y], fill=(0, 150, 0), width=int(2 * s))
            draw.text((cx + qw * 2 - int(10 * s), lam_y + int(5 * s)), "λ", fill=(0, 150, 0),
                      font=_get_font(int(26 * s), bold=True))
            # Amplitude
            amp_x = cx + int(10 * s)
            draw.line([amp_x, mid_y, amp_x, int(y + h * 0.15)], fill=(200, 0, 200), width=int(2 * s))
            draw.text((amp_x + int(5 * s), int(y + h * 0.25)), "A", fill=(200, 0, 200),
                      font=_get_font(int(24 * s), bold=True))
        return y + h + int(50 * s)

    def _draw_ray_diagram(self, draw, frame, element, y):
        """Optics ray diagram for mirrors/lenses."""
        optic_type = element.get("optic_type", "convex_lens")
        params = element.get("params", {})
        s = self.scale
        # Fallback to builtin optics visual
        visual_map = {
            "convex_lens": "optics", "concave_lens": "optics",
            "concave_mirror": "concave_mirror", "convex_mirror": "convex_mirror",
        }
        visual = visual_map.get(optic_type, "optics")
        return self._draw_builtin_visual(draw, frame,
            {"type": "builtin_visual", "visual": visual,
             "label": optic_type.replace("_", " ").title(), "color": "blue"}, y)

    def _draw_energy_level(self, draw, frame, element, y):
        """Quantum energy level diagram with transitions."""
        atom = element.get("atom", "H")
        transitions = element.get("transitions", [])
        s = self.scale
        cx = self.content_x + int(60 * s)
        w = self.content_w - int(120 * s)
        levels = 5
        level_gap = int(50 * s)
        lf = _get_font(int(22 * s))
        bf = _get_font(int(24 * s), bold=True)
        draw.text((cx, y), f"{atom} Energy Levels", fill=(26, 35, 126), font=bf)
        y += int(40 * s)
        level_y = {}
        for n in range(1, levels + 1):
            ly = y + (levels - n) * level_gap
            level_y[n] = ly
            draw.line([cx, ly, cx + w, ly], fill=(60, 60, 100), width=int(2 * s))
            draw.text((cx + w + int(10 * s), ly - int(10 * s)), f"n={n}", fill=(60, 60, 100), font=lf)
        # Transitions
        colors_t = {"emission": (220, 50, 50), "absorption": (50, 50, 220)}
        for t in transitions:
            n_from = t.get("from", 3)
            n_to = t.get("to", 1)
            ttype = t.get("type", "emission")
            label = t.get("label", "")
            if n_from in level_y and n_to in level_y:
                x_pos = cx + w // 3 + transitions.index(t) * int(80 * s)
                color = colors_t.get(ttype, (100, 100, 100))
                draw.line([x_pos, level_y[n_from], x_pos, level_y[n_to]],
                          fill=color, width=int(3 * s))
                mid = (level_y[n_from] + level_y[n_to]) // 2
                if label:
                    draw.text((x_pos + int(5 * s), mid), label, fill=color, font=lf)
        return y + levels * level_gap + int(30 * s)

    def _draw_molecule_2d(self, draw, frame, element, y):
        """2D molecule from SMILES via RDKit, fallback to rdkit_mol handler."""
        return self._draw_rdkit_mol(draw, frame, {
            "smiles": element.get("smiles", ""),
            "name": element.get("name", ""),
            "caption": element.get("name", ""),
        }, y)

    def _draw_periodic_element(self, draw, frame, element, y):
        """Single element tile — symbol, atomic number, mass, name."""
        symbol = element.get("symbol", "?")
        atomic_num = element.get("atomic_number", 0)
        atomic_mass = element.get("atomic_mass", 0)
        name = element.get("name", "")
        s = self.scale
        tile_w = int(220 * s)
        tile_h = int(260 * s)
        tx = self.content_x + (self.content_w - tile_w) // 2
        # Tile bg
        draw.rounded_rectangle([tx, y, tx + tile_w, y + tile_h],
                               radius=int(12 * s), fill=(230, 240, 255), outline=(26, 35, 126), width=int(3 * s))
        nf = _get_font(int(22 * s))
        sf = _get_font(int(72 * s), bold=True)
        mf = _get_font(int(20 * s))
        # Atomic number
        draw.text((tx + int(12 * s), y + int(10 * s)), str(atomic_num), fill=(100, 100, 150), font=nf)
        # Symbol
        stw = draw.textlength(symbol, font=sf)
        draw.text((tx + (tile_w - stw) / 2, y + int(50 * s)), symbol, fill=(26, 35, 126), font=sf)
        # Name
        ntw = draw.textlength(name, font=nf)
        draw.text((tx + (tile_w - ntw) / 2, y + int(160 * s)), name, fill=(60, 60, 100), font=nf)
        # Mass
        mass_str = f"{atomic_mass:.3f}" if atomic_mass else ""
        mtw = draw.textlength(mass_str, font=mf)
        draw.text((tx + (tile_w - mtw) / 2, y + int(200 * s)), mass_str, fill=(120, 120, 160), font=mf)
        return y + tile_h + int(20 * s)

    def _draw_periodic_table_mini(self, draw, frame, element, y):
        """Mini periodic table with highlighted elements/groups."""
        highlight = set(element.get("highlight_elements", []))
        s = self.scale
        # Simplified — show first 36 elements in grid
        elements_data = [
            "H","He","Li","Be","B","C","N","O","F","Ne",
            "Na","Mg","Al","Si","P","S","Cl","Ar","K","Ca",
            "Sc","Ti","V","Cr","Mn","Fe","Co","Ni","Cu","Zn",
            "Ga","Ge","As","Se","Br","Kr"
        ]
        cols = 18
        cell_w = int(self.content_w / cols)
        cell_h = int(cell_w * 1.2)
        cf = _get_font(max(10, int(14 * s)))
        cx = self.content_x
        for i, sym in enumerate(elements_data):
            col = i % cols
            row = i // cols
            ex = cx + col * cell_w
            ey = y + row * cell_h
            fill = (255, 200, 100) if sym in highlight else (230, 240, 255)
            draw.rectangle([ex, ey, ex + cell_w - 1, ey + cell_h - 1], fill=fill, outline=(180, 180, 200))
            tw = draw.textlength(sym, font=cf)
            draw.text((ex + (cell_w - tw) / 2, ey + int(4 * s)), sym, fill=(30, 30, 80), font=cf)
        rows_used = (len(elements_data) + cols - 1) // cols
        return y + rows_used * cell_h + int(20 * s)

    def _draw_energy_diagram(self, draw, frame, element, y):
        """Potential energy curve — exothermic/endothermic."""
        reaction_type = element.get("reaction_type", "exothermic")
        ea = element.get("activation_energy", 80)
        dh = element.get("delta_h", -50)
        s = self.scale
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np
            from io import BytesIO
            fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
            x = np.linspace(0, 10, 200)
            reactant_e = 50
            product_e = reactant_e + dh
            peak_e = reactant_e + ea
            curve = np.where(x < 3, reactant_e, np.where(x < 5,
                reactant_e + (peak_e - reactant_e) * np.exp(-((x - 4)**2) / 0.5),
                product_e + (peak_e - product_e) * np.exp(-((x - 4)**2) / 0.5)))
            # Smooth gaussian-like curve
            from scipy.ndimage import gaussian_filter1d
            curve = gaussian_filter1d(curve, sigma=10)
            ax.plot(x, curve, color="#1A237E", linewidth=2.5)
            ax.axhline(y=reactant_e, color="gray", linestyle="--", alpha=0.5)
            ax.axhline(y=product_e, color="gray", linestyle="--", alpha=0.5)
            ax.set_xlabel("Reaction Progress →", fontsize=12)
            ax.set_ylabel("Potential Energy", fontsize=12)
            title = f"{'Exothermic' if dh < 0 else 'Endothermic'} Reaction"
            ax.set_title(title, fontsize=14, fontweight="bold")
            ax.annotate(f"Ea = {ea}", xy=(4, peak_e), fontsize=11, ha="center", color="red")
            ax.annotate(f"ΔH = {dh}", xy=(7, (reactant_e + product_e) / 2), fontsize=11, color="blue")
            fig.tight_layout()
            buf = BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
            plt.close(fig)
            buf.seek(0)
            img = Image.open(buf).convert("RGB")
            ratio = min(self.content_w / img.width, int(350 * s) / img.height)
            new_w, new_h = int(img.width * ratio), int(img.height * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            px = self.content_x + (self.content_w - new_w) // 2
            frame.paste(img, (px, int(y)))
            return y + new_h + int(20 * s)
        except Exception:
            return self._draw_builtin_visual(draw, frame,
                {"type": "builtin_visual", "visual": "activation_energy",
                 "label": f"{'Exothermic' if dh < 0 else 'Endothermic'} Reaction", "color": "orange"}, y)

    def _draw_orbital_diagram(self, draw, frame, element, y):
        """Electron orbital filling — box notation."""
        config_str = element.get("configuration", "1s²")
        s = self.scale
        import re
        orbitals = re.findall(r'(\d[spdf])(\d*[⁰¹²³⁴⁵⁶⁷⁸⁹]*|\d*)', config_str)
        cx = self.content_x + int(20 * s)
        box_w = int(28 * s)
        box_h = int(36 * s)
        gap = int(6 * s)
        lf = _get_font(int(20 * s))
        bf = _get_font(int(18 * s), bold=True)
        # Title
        name = element.get("element", "")
        if name:
            draw.text((cx, y), f"{name}: {config_str}", fill=(26, 35, 126), font=_get_font(int(26 * s), bold=True))
            y += int(40 * s)
        max_boxes = {"s": 1, "p": 3, "d": 5, "f": 7}
        superscripts = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
        for orb_name, electrons_str in orbitals:
            electrons_str = electrons_str.translate(superscripts)
            n_electrons = int(electrons_str) if electrons_str else 0
            sublevel = orb_name[-1]
            n_boxes = max_boxes.get(sublevel, 1)
            draw.text((cx, y + int(5 * s)), orb_name, fill=(60, 60, 100), font=lf)
            bx = cx + int(40 * s)
            for b in range(n_boxes):
                x1 = bx + b * (box_w + gap)
                draw.rectangle([x1, y, x1 + box_w, y + box_h], outline=(100, 100, 150), width=int(2 * s))
                e_in_box = min(2, max(0, n_electrons - b * 2))
                if e_in_box >= 1:
                    draw.text((x1 + int(4 * s), y + int(2 * s)), "↑", fill=(220, 50, 50), font=bf)
                if e_in_box >= 2:
                    draw.text((x1 + int(14 * s), y + int(2 * s)), "↓", fill=(50, 50, 220), font=bf)
            y += box_h + int(10 * s)
        return y + int(10 * s)

    def _draw_cell_diagram(self, draw, frame, element, y):
        """Labeled cell diagram with callout arrows."""
        cell_type = element.get("cell_type", "animal")
        label_parts = element.get("label_parts", [])
        visual = "cell" if cell_type == "animal" else "plant_cell" if cell_type == "plant" else "cell"
        return self._draw_builtin_visual(draw, frame,
            {"type": "builtin_visual", "visual": visual,
             "label": f"{cell_type.title()} Cell", "color": "green"}, y)

    def _draw_punnett_square(self, draw, frame, element, y):
        """Genetics Punnett square — 2×2 monohybrid."""
        parent1 = element.get("parent1", "Aa")
        parent2 = element.get("parent2", "Aa")
        trait = element.get("trait_name", "Trait")
        s = self.scale
        cell_size = int(80 * s)
        cx = self.content_x + (self.content_w - cell_size * 3) // 2
        bf = _get_font(int(28 * s), bold=True)
        lf = _get_font(int(24 * s))
        # Title
        draw.text((cx, y), f"Punnett Square: {parent1} × {parent2}", fill=(26, 35, 126), font=bf)
        y += int(45 * s)
        alleles1 = list(parent1)
        alleles2 = list(parent2)
        # Header row
        for j, a in enumerate(alleles2):
            x = cx + (j + 1) * cell_size
            draw.rectangle([x, y, x + cell_size, y + cell_size], fill=(26, 35, 126))
            tw = draw.textlength(a, font=bf)
            draw.text((x + (cell_size - tw) / 2, y + int(20 * s)), a, fill=(255, 255, 255), font=bf)
        y += cell_size
        # Grid
        dom_color = (200, 240, 200)
        rec_color = (255, 240, 200)
        for i, a1 in enumerate(alleles1):
            # Row header
            rx = cx
            ry = y + i * cell_size
            draw.rectangle([rx, ry, rx + cell_size, ry + cell_size], fill=(26, 35, 126))
            tw = draw.textlength(a1, font=bf)
            draw.text((rx + (cell_size - tw) / 2, ry + int(20 * s)), a1, fill=(255, 255, 255), font=bf)
            for j, a2 in enumerate(alleles2):
                gx = cx + (j + 1) * cell_size
                gy = ry
                genotype = a1 + a2
                is_homo_rec = genotype.lower() == genotype
                fill = rec_color if is_homo_rec else dom_color
                draw.rectangle([gx, gy, gx + cell_size, gy + cell_size], fill=fill, outline=(150, 150, 180))
                tw = draw.textlength(genotype, font=lf)
                draw.text((gx + (cell_size - tw) / 2, gy + int(22 * s)), genotype, fill=(30, 30, 80), font=lf)
        total_h = len(alleles1) * cell_size + int(20 * s)
        return y + total_h

    def _draw_food_chain_degree(self, draw, frame, element, y):
        """Food chain with labeled energy flow arrows."""
        organisms = element.get("organisms", [])
        s = self.scale
        if not organisms:
            return y
        box_w = int(min(180 * s, (self.content_w - int(40 * s) * len(organisms)) / len(organisms)))
        box_h = int(60 * s)
        gap = int(50 * s)
        total_w = len(organisms) * box_w + (len(organisms) - 1) * gap
        start_x = self.content_x + (self.content_w - total_w) // 2
        bf = _get_font(int(22 * s), bold=True)
        lf = _get_font(int(16 * s))
        colors = [(120, 200, 80), (80, 180, 120), (60, 140, 200), (200, 120, 60), (180, 60, 60)]
        for i, org in enumerate(organisms):
            bx = start_x + i * (box_w + gap)
            color = colors[i % len(colors)]
            draw.rounded_rectangle([bx, y, bx + box_w, y + box_h],
                                   radius=int(8 * s), fill=color, outline=(50, 50, 50))
            tw = draw.textlength(org, font=bf)
            draw.text((bx + (box_w - tw) / 2, y + int(15 * s)), org, fill=(255, 255, 255), font=bf)
            # Trophic label
            trophic = ["Producer", "Primary", "Secondary", "Tertiary", "Apex"][min(i, 4)]
            tw2 = draw.textlength(trophic, font=lf)
            draw.text((bx + (box_w - tw2) / 2, y + box_h + int(5 * s)), trophic, fill=(100, 100, 100), font=lf)
            # Arrow
            if i < len(organisms) - 1:
                ax1 = bx + box_w + int(5 * s)
                ax2 = bx + box_w + gap - int(5 * s)
                ay = y + box_h // 2
                draw.line([ax1, ay, ax2, ay], fill=(200, 100, 0), width=int(3 * s))
                draw.polygon([(ax2, ay), (ax2 - int(10 * s), ay - int(7 * s)),
                              (ax2 - int(10 * s), ay + int(7 * s))], fill=(200, 100, 0))
        return y + box_h + int(40 * s)

    def _draw_dna_structure(self, draw, frame, element, y):
        """DNA double helix with base pair labels."""
        sequence = element.get("sequence", "ATGC")
        s = self.scale
        return self._draw_builtin_visual(draw, frame,
            {"type": "builtin_visual", "visual": "dna",
             "label": f"DNA: {sequence[:8]}", "color": "blue"}, y)

    def _draw_india_map(self, draw, frame, element, y):
        """India map via geopandas or fallback to map_plot."""
        return self._draw_map_plot(draw, frame, {
            "type": "map_plot", "map_type": "india_states",
            "highlighted": element.get("highlight_states", []),
            "data": element.get("choropleth_data", {}),
            "title": element.get("title", "India"),
        }, y)

    def _draw_world_map(self, draw, frame, element, y):
        """World map via geopandas or fallback to map_plot."""
        return self._draw_map_plot(draw, frame, {
            "type": "map_plot", "map_type": "world_highlight",
            "countries": element.get("highlight_countries", []),
            "title": element.get("title", "World Map"),
        }, y)

    def _draw_timeline_bar(self, draw, frame, element, y):
        """Horizontal timeline with events."""
        events = element.get("events", [])
        if not events:
            return y
        s = self.scale
        cx = self.content_x + int(40 * s)
        w = self.content_w - int(80 * s)
        line_y = int(y + 80 * s)
        # Main line
        draw.line([cx, line_y, cx + w, line_y], fill=(100, 100, 150), width=int(3 * s))
        lf = _get_font(int(18 * s))
        bf = _get_font(int(20 * s), bold=True)
        gap = w // max(1, len(events))
        for i, ev in enumerate(events):
            ex = cx + i * gap + gap // 2
            year = str(ev.get("year", ""))
            event = ev.get("event", "")
            dot_r = int(6 * s)
            draw.ellipse([ex - dot_r, line_y - dot_r, ex + dot_r, line_y + dot_r], fill=(239, 108, 0))
            # Alternate above/below
            if i % 2 == 0:
                draw.line([ex, line_y - dot_r, ex, line_y - int(40 * s)], fill=(150, 150, 180))
                draw.text((ex - int(20 * s), line_y - int(60 * s)), year, fill=(26, 35, 126), font=bf)
                draw.text((ex - int(30 * s), line_y - int(80 * s)), event[:25], fill=(80, 80, 120), font=lf)
            else:
                draw.line([ex, line_y + dot_r, ex, line_y + int(40 * s)], fill=(150, 150, 180))
                draw.text((ex - int(20 * s), line_y + int(45 * s)), year, fill=(26, 35, 126), font=bf)
                draw.text((ex - int(30 * s), line_y + int(65 * s)), event[:25], fill=(80, 80, 120), font=lf)
        return y + int(180 * s)

    def _draw_comparison_table(self, draw, frame, element, y):
        """Multi-column comparison table."""
        return self._draw_table(draw, frame, element, y)

    def _draw_process_cycle(self, draw, frame, element, y):
        """Circular cycle diagram."""
        steps = element.get("steps", [])
        heading = element.get("heading", "")
        s = self.scale
        if not steps:
            return y
        import math
        cx_c = self.content_x + self.content_w // 2
        cy_c = int(y + 150 * s)
        radius = int(120 * s)
        bf = _get_font(int(20 * s), bold=True)
        lf = _get_font(int(16 * s))
        if heading:
            hw = draw.textlength(heading, font=bf)
            draw.text((cx_c - hw / 2, y), heading, fill=(26, 35, 126), font=bf)
        n = len(steps)
        for i, step in enumerate(steps):
            angle = 2 * math.pi * i / n - math.pi / 2
            sx = cx_c + int(radius * math.cos(angle))
            sy = cy_c + int(radius * math.sin(angle))
            box_r = int(35 * s)
            draw.ellipse([sx - box_r, sy - box_r, sx + box_r, sy + box_r],
                         fill=(230, 240, 255), outline=(26, 35, 126), width=int(2 * s))
            text = step if isinstance(step, str) else step.get("text", "")
            tw = draw.textlength(text[:10], font=lf)
            draw.text((sx - tw / 2, sy - int(8 * s)), text[:10], fill=(26, 35, 126), font=lf)
            # Arrow to next
            next_angle = 2 * math.pi * ((i + 1) % n) / n - math.pi / 2
            nx = cx_c + int(radius * math.cos(next_angle))
            ny = cy_c + int(radius * math.sin(next_angle))
            mid_x = (sx + nx) // 2
            mid_y_a = (sy + ny) // 2
            draw.line([sx + int(box_r * math.cos(next_angle - math.pi * i / n)),
                       sy + int(box_r * math.sin(next_angle - math.pi * i / n)),
                       nx - int(box_r * math.cos(next_angle - math.pi * i / n)),
                       ny - int(box_r * math.sin(next_angle - math.pi * i / n))],
                      fill=(200, 100, 0), width=int(2 * s))
        return y + int(320 * s)

    def _draw_hierarchy_tree(self, draw, frame, element, y):
        """Tree hierarchy diagram."""
        return self._draw_builtin_visual(draw, frame,
            {"type": "builtin_visual", "visual": "binary_tree",
             "label": element.get("heading", "Hierarchy"), "color": "blue"}, y)

    def _draw_cause_effect(self, draw, frame, element, y):
        """Cause → Effect arrows."""
        causes = element.get("causes", element.get("left", []))
        effects = element.get("effects", element.get("right", []))
        if isinstance(causes, dict):
            causes = causes.get("items", [])
        if isinstance(effects, dict):
            effects = effects.get("items", [])
        return self._draw_flow_chart(draw, frame, {
            "type": "flow_chart", "heading": "Cause → Effect",
            "steps": [{"text": c, "color": "blue"} for c in causes] +
                     [{"text": e, "color": "orange"} for e in effects],
        }, y)

    def _draw_factor_tree(self, draw, frame, element, y):
        """Prime factor tree."""
        number = element.get("number", element.get("value", 0))
        s = self.scale
        bf = _get_font(int(32 * s), bold=True)
        lf = _get_font(int(24 * s))
        cx = self.content_x + self.content_w // 2
        draw.text((cx - int(20 * s), y), str(number), fill=(26, 35, 126), font=bf)
        # Simple factorization display
        n = int(number) if number else 0
        factors = []
        d = 2
        temp = n
        while d * d <= temp and temp > 1:
            while temp % d == 0:
                factors.append(d)
                temp //= d
            d += 1
        if temp > 1:
            factors.append(temp)
        if factors:
            y += int(50 * s)
            fact_str = " × ".join(str(f) for f in factors)
            draw.text((cx - draw.textlength(fact_str, font=lf) / 2, y),
                      f"= {fact_str}", fill=(200, 100, 0), font=lf)
            y += int(40 * s)
        return y + int(20 * s)

    def _draw_venn_diagram_degree(self, draw, frame, element, y):
        """Venn diagram with labeled sets."""
        return self._draw_builtin_visual(draw, frame,
            {"type": "builtin_visual", "visual": "venn_diagram",
             "label": element.get("heading", "Venn Diagram"), "color": "blue"}, y)

    def _draw_balance_scale(self, draw, frame, element, y):
        """Balance scale visualization."""
        left_val = element.get("left", "?")
        right_val = element.get("right", "?")
        s = self.scale
        cx = self.content_x + self.content_w // 2
        bf = _get_font(int(28 * s), bold=True)
        lf = _get_font(int(24 * s))
        # Base triangle
        base_y = int(y + 180 * s)
        draw.polygon([(cx, base_y - int(20 * s)), (cx - int(30 * s), base_y), (cx + int(30 * s), base_y)],
                     fill=(100, 100, 150))
        # Beam
        beam_w = int(300 * s)
        draw.line([cx - beam_w // 2, base_y - int(22 * s), cx + beam_w // 2, base_y - int(22 * s)],
                  fill=(80, 80, 120), width=int(4 * s))
        # Pans
        pan_w = int(100 * s)
        for side, val, offset in [("L", str(left_val), -beam_w // 2), ("R", str(right_val), beam_w // 2)]:
            px = cx + offset
            pan_y = base_y - int(22 * s)
            draw.line([px, pan_y, px, pan_y + int(40 * s)], fill=(120, 120, 150), width=int(2 * s))
            draw.arc([px - pan_w // 2, pan_y + int(30 * s), px + pan_w // 2, pan_y + int(60 * s)],
                     0, 180, fill=(120, 120, 150), width=int(2 * s))
            tw = draw.textlength(val, font=bf)
            draw.text((px - tw / 2, pan_y + int(65 * s)), val, fill=(26, 35, 126), font=bf)
        # Equals
        draw.text((cx - int(8 * s), base_y - int(55 * s)), "=", fill=(200, 100, 0), font=bf)
        return base_y + int(100 * s)

    def _draw_coordinate_axes(self, draw, frame, element, y):
        """2D coordinate system with optional points."""
        s = self.scale
        return self._draw_builtin_visual(draw, frame,
            {"type": "builtin_visual", "visual": "coordinate_plane",
             "label": element.get("title", "Coordinate Axes"), "color": "blue"}, y)

    def _draw_bar_chart(self, draw, frame, element, y):
        """Bar chart via matplotlib."""
        return self._draw_matplotlib_plot(draw, frame, {
            "type": "matplotlib_plot", "plot_type": "bar",
            "title": element.get("title", ""),
            "data": element.get("data", {}),
            "xlabel": element.get("xlabel", ""),
            "ylabel": element.get("ylabel", ""),
            "color": element.get("color", "blue"),
        }, y)

    def _draw_pie_chart(self, draw, frame, element, y):
        """Pie chart via matplotlib."""
        return self._draw_matplotlib_plot(draw, frame, {
            "type": "matplotlib_plot", "plot_type": "pie",
            "title": element.get("title", ""),
            "data": element.get("data", {}),
            "color": element.get("color", "blue"),
        }, y)

    def _draw_clock_diagram(self, draw, frame, element, y):
        """Clock face diagram."""
        return self._draw_builtin_visual(draw, frame,
            {"type": "builtin_visual", "visual": "clock",
             "label": element.get("label", "Clock"), "color": "blue"}, y)

    def _draw_reaction_equation(self, draw, frame, element, y):
        """Balanced chemical equation with state symbols."""
        return self._draw_chem_equation(draw, frame, {
            "type": "chem_equation",
            "reactants": element.get("reactants", ""),
            "products": element.get("products", ""),
            "conditions": element.get("conditions", ""),
            "reversible": element.get("reversible", False),
        }, y)

    # ------------------------------------------------------------------
    # NEW ULTRA-PRO RENDER TARGETS
    # ------------------------------------------------------------------

    def _draw_option_analysis(self, draw, frame, element, y,
                              body_bottom=None, **_kw):
        """Full-body option check — big header, rule cards, verdict.

        JSON: { "target": "option_analysis",
                "option_key": "a", "option_value": "277218",
                "checks": [
                    {"rule": "Rule of 9", "working": "2+7+7+2+1+8 = 27", "result": "27 ÷ 9 = 3", "pass": true},
                    {"rule": "Rule of 11", "working": "+2−7+7−2+1−8 = −7", "result": "−7 ≠ 0 or ÷11", "pass": false}
                ],
                "verdict": "fail"  }
        """
        opt_key   = element.get("option_key", "?").upper()
        opt_value = str(element.get("option_value", ""))
        checks    = element.get("checks", [])
        verdict   = element.get("verdict", "").lower()
        s = self.scale

        bar_color_hex = OPTION_BAR_COLORS.get(opt_key.lower(), "#1565C0")
        bar_color = self._rgb(bar_color_hex)
        cx = self.content_x
        cw = self.content_w
        pad_x = int(40 * s)
        bb = body_bottom or (self.height - int(120 * s))
        avail_h = bb - y

        # ── Fonts — scale up to fill space ──
        opt_font   = _get_font(int(56 * s), bold=True)
        val_font   = _get_font(int(72 * s), bold=True)
        rule_font  = _get_font(int(44 * s), bold=True)
        work_font  = _get_math_font(int(48 * s))
        res_font   = _get_font(int(44 * s), bold=True)
        sym_font   = _get_symbol_font(int(56 * s))
        verd_font  = _get_font(int(42 * s), bold=True)

        n_checks = max(len(checks), 1)
        # Dynamic sizing: header band + rule cards + verdict fill the body
        header_h  = int(100 * s)
        verdict_h = int(64 * s)
        gap       = int(16 * s)
        rule_area = avail_h - header_h - verdict_h - gap * (n_checks + 2)
        rule_h    = max(int(140 * s), rule_area // n_checks)

        # ── Option header band (colored) ──
        draw.rounded_rectangle(
            [cx, y, cx + cw, y + header_h],
            radius=int(14 * s), fill=bar_color,
        )
        # "Option A" small label
        draw.text((cx + pad_x, y + int(12 * s)),
                  f"Option {opt_key}", fill=(255, 255, 255, 200), font=opt_font)
        # Big value centered
        vw = draw.textlength(opt_value, font=val_font)
        draw.text(((self.width - vw) / 2, y + int(16 * s)),
                  opt_value, fill=(255, 255, 255), font=val_font)
        hy = y + header_h + gap

        # ── Rule check cards ──
        for ck in checks:
            passed = ck.get("pass", False)
            rule   = ck.get("rule", "")
            work   = ck.get("working", "")
            result = ck.get("result", "")

            # Card colors
            if passed:
                card_bg    = (232, 245, 233)
                accent     = self._rgb("success")
                border_col = self._rgb("success")
            else:
                card_bg    = (255, 235, 238)
                accent     = self._rgb("fail")
                border_col = self._rgb("fail")

            # Full-width rule card
            draw.rounded_rectangle(
                [cx, hy, cx + cw, hy + rule_h],
                radius=int(12 * s), fill=card_bg,
                outline=border_col, width=int(2 * s),
            )
            # Left accent bar
            draw.rectangle([cx, hy, cx + int(8 * s), hy + rule_h], fill=accent)

            # ── Rule heading bar at top of card ──
            rule_hdr_h = int(48 * s)
            draw.rounded_rectangle(
                [cx + int(8 * s), hy, cx + cw, hy + rule_hdr_h],
                radius=int(12 * s), fill=accent,
            )
            draw.rectangle([cx + int(8 * s), hy + int(24 * s),
                            cx + cw, hy + rule_hdr_h], fill=accent)
            # Rule name in white on accent band
            draw.text((cx + pad_x + int(8 * s), hy + int(6 * s)),
                      rule, fill=(255, 255, 255), font=rule_font)
            # Pass/fail badge right side of heading
            sym = "✔ PASS" if passed else "✘ FAIL"
            sw = draw.textlength(sym, font=rule_font)
            draw.text((cx + cw - pad_x - sw, hy + int(6 * s)),
                      sym, fill=(255, 255, 255), font=rule_font)

            # ── Working line (large, centered in card) ──
            work_y = hy + rule_hdr_h + int((rule_h - rule_hdr_h) * 0.2)
            draw.text((cx + pad_x + int(16 * s), work_y),
                      work, fill=self._rgb("body_text"), font=work_font)

            # ── Result line (below working, right-aligned) ──
            res_y = work_y + int(work_font.size * 1.6)
            if result:
                # Result text
                draw.text((cx + pad_x + int(16 * s), res_y),
                          result, fill=accent, font=res_font)
                # Big symbol at right
                draw.text((cx + cw - pad_x - int(60 * s),
                           hy + rule_hdr_h + int((rule_h - rule_hdr_h - sym_font.size) / 2)),
                          "✔" if passed else "✘", fill=accent, font=sym_font)

            hy += rule_h + gap

        # ── Verdict bar (full width) ──
        if "pass" in verdict or "both" in verdict.lower():
            vtext  = "✔  PASSES ALL RULES"
            vcolor = (255, 255, 255)
            vbg    = self._rgb("success")
        else:
            vtext  = "✘  DOES NOT PASS"
            vcolor = (255, 255, 255)
            vbg    = self._rgb("fail")

        draw.rounded_rectangle(
            [cx, hy, cx + cw, hy + verdict_h],
            radius=int(10 * s), fill=vbg,
        )
        vw = draw.textlength(vtext, font=verd_font)
        draw.text(((self.width - vw) / 2, hy + (verdict_h - verd_font.size) / 2),
                  vtext, fill=vcolor, font=verd_font)

        return hy + verdict_h

    def _draw_bullet_list(self, draw, frame, element, y):
        """Bullet point list with optional title and icons.

        JSON: { "target": "bullet_list",
                "heading": "Key Points",
                "items": ["First point", "Second point", ...],
                "icon": "bullet|check|arrow|star",
                "color": "blue" }
        """
        heading = element.get("heading", "")
        items   = element.get("items", [])
        icon    = element.get("icon", "bullet")
        color   = element.get("color", "blue")
        s = self.scale

        icons = {"bullet": "\u2022", "check": "\u2713", "arrow": "\u25B6", "star": "\u2605"}
        icon_char = icons.get(icon, "\u2022")
        accent = self._rgb(color if color in self.C else "blue")

        head_font = _get_font(int(46 * s), bold=True)
        body_font = _get_font(int(42 * s))
        icon_font = _get_symbol_font(int(38 * s))
        pad_x = int(52 * s)
        pad_y = int(28 * s)
        line_h = int(body_font.size * 1.8)
        head_h = int(head_font.size * 1.5) if heading else 0

        # Measure lines
        total_lines = 0
        max_w = self.content_w - pad_x * 2 - int(50 * s)
        for item in items:
            total_lines += max(1, len(self._wrap_text(item, body_font, max_w)))
        card_h = head_h + total_lines * line_h + 2 * pad_y
        cx = self.content_x

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(10 * s), fill=(245, 248, 255),
        )
        draw.rectangle([cx, y, cx + int(5 * s), y + card_h], fill=accent)

        cy = y + pad_y
        if heading:
            draw.text((cx + pad_x, cy), heading, fill=accent, font=head_font)
            cy += head_h

        for item in items:
            draw.text((cx + pad_x, cy + int(2 * s)), icon_char,
                      fill=accent, font=icon_font)
            wrapped = self._wrap_text(item, body_font, max_w)
            for li, line in enumerate(wrapped):
                draw.text((cx + pad_x + int(42 * s), cy + li * int(body_font.size * 1.3)),
                          line, fill=self._rgb("body_text"), font=body_font)
            cy += max(1, len(wrapped)) * line_h
        return y + card_h

    def _draw_definition_card(self, draw, frame, element, y):
        """Term + definition card — GK, vocabulary, science terms.

        JSON: { "target": "definition_card",
                "term": "Osmosis",
                "definition": "Movement of water molecules through a semipermeable membrane...",
                "category": "Biology",
                "color": "green" }
        """
        term       = element.get("term", "")
        definition = element.get("definition", "")
        category   = element.get("category", "")
        color      = element.get("color", "blue")
        s = self.scale

        accent = self._rgb(color if color in self.C else "blue")
        term_font = _get_font(int(52 * s), bold=True)
        def_font  = _get_font(int(40 * s))
        cat_font  = _get_font(int(28 * s), bold=True)
        pad_x = int(52 * s)
        pad_y = int(32 * s)

        max_w = self.content_w - 2 * pad_x
        def_lines = self._wrap_text(definition, def_font, max_w)
        line_h = int(def_font.size * 1.5)
        cat_h = int(40 * s) if category else 0
        term_h = int(term_font.size * 1.5)
        card_h = cat_h + term_h + len(def_lines) * line_h + 2 * pad_y + int(16 * s)
        cx = self.content_x

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(14 * s), fill=(255, 255, 255),
        )
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(14 * s), outline=accent, width=int(3 * s),
        )
        draw.rectangle([cx, y, cx + int(8 * s), y + card_h], fill=accent)

        cy = y + pad_y
        if category:
            # Category badge
            cw = draw.textlength(category.upper(), font=cat_font) + int(24 * s)
            draw.rounded_rectangle(
                [cx + pad_x, cy, cx + pad_x + cw, cy + int(32 * s)],
                radius=int(4 * s), fill=accent,
            )
            draw.text((cx + pad_x + int(12 * s), cy + int(4 * s)),
                      category.upper(), fill=(255, 255, 255), font=cat_font)
            cy += cat_h

        draw.text((cx + pad_x, cy), term, fill=accent, font=term_font)
        cy += term_h
        # Divider line
        draw.line([cx + pad_x, cy, cx + self.content_w - pad_x, cy],
                  fill=(*accent, 80) if len(accent) == 3 else accent, width=int(2 * s))
        cy += int(16 * s)
        for line in def_lines:
            draw.text((cx + pad_x, cy), line,
                      fill=self._rgb("body_text"), font=def_font)
            cy += line_h
        return y + card_h

    def _draw_quote_block(self, draw, frame, element, y):
        """Quote block — articles, provisions, famous quotes.

        JSON: { "target": "quote_block",
                "text": "We the people of India...",
                "source": "Preamble, Constitution of India",
                "color": "blue" }
        """
        text   = element.get("text", element.get("value", ""))
        source = element.get("source", element.get("attribution", ""))
        color  = element.get("color", "blue")
        s = self.scale

        accent = self._rgb(color if color in self.C else "blue")
        quote_font = _get_font(int(44 * s))
        src_font   = _get_font(int(32 * s), bold=True)
        big_quote  = _get_font(int(80 * s), bold=True)
        pad_x = int(80 * s)
        pad_y = int(36 * s)

        max_w = self.content_w - 2 * pad_x
        lines = self._wrap_text(text, quote_font, max_w)
        line_h = int(quote_font.size * 1.6)
        src_h = int(48 * s) if source else 0
        card_h = len(lines) * line_h + src_h + 2 * pad_y
        cx = self.content_x

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(12 * s), fill=(245, 248, 255),
        )
        draw.rectangle([cx, y, cx + int(6 * s), y + card_h], fill=accent)

        # Big opening quote mark
        draw.text((cx + int(24 * s), y + pad_y - int(20 * s)),
                  "\u201C", fill=(*accent[:3],) if isinstance(accent, tuple) else accent,
                  font=big_quote)

        cy = y + pad_y
        for line in lines:
            draw.text((cx + pad_x, cy), line,
                      fill=self._rgb("body_text"), font=quote_font)
            cy += line_h
        if source:
            cy += int(8 * s)
            draw.text((cx + pad_x, cy), f"\u2014 {source}",
                      fill=accent, font=src_font)
        return y + card_h

    def _draw_code_block(self, draw, frame, element, y):
        """Syntax-highlighted code block — CS questions.

        JSON: { "target": "code_block",
                "code": "def hello():\\n    print('Hello')",
                "language": "python",
                "highlight_lines": [2] }
        """
        code = element.get("code", element.get("value", ""))
        highlight_lines = element.get("highlight_lines", [])
        s = self.scale

        mono_font = _get_font(int(32 * s))  # monospace-ish
        line_num_font = _get_font(int(26 * s))
        pad_x = int(48 * s)
        pad_y = int(24 * s)
        line_h = int(mono_font.size * 1.6)

        code_lines = code.split("\\n") if "\\n" in code else code.split("\n")
        card_h = len(code_lines) * line_h + 2 * pad_y
        cx = self.content_x
        gutter_w = int(60 * s)

        # Dark code background
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(10 * s), fill=(30, 30, 46),
        )
        # Gutter
        draw.rectangle([cx, y, cx + gutter_w, y + card_h], fill=(22, 22, 36))

        cy = y + pad_y
        for i, line in enumerate(code_lines):
            lnum = i + 1
            # Highlight line background
            if lnum in highlight_lines:
                draw.rectangle(
                    [cx + gutter_w, cy - int(2 * s),
                     cx + self.content_w, cy + line_h - int(2 * s)],
                    fill=(60, 60, 90),
                )
            # Line number
            nw = draw.textlength(str(lnum), font=line_num_font)
            draw.text((cx + gutter_w - nw - int(12 * s), cy + int(4 * s)),
                      str(lnum), fill=(100, 100, 140), font=line_num_font)
            # Code text — basic keyword coloring
            self._draw_code_line(draw, cx + gutter_w + int(16 * s), cy,
                                 line, mono_font, s)
            cy += line_h
        return y + card_h

    def _draw_code_line(self, draw, x, y, line, font, s):
        """Simple keyword-colored code line."""
        keywords = {"def", "class", "if", "else", "elif", "for", "while", "return",
                    "import", "from", "in", "not", "and", "or", "True", "False", "None",
                    "int", "float", "str", "print", "len", "range", "void", "main",
                    "public", "static", "private", "#include", "using", "namespace"}
        tokens = line.split(" ")
        cx = x
        for tok in tokens:
            clean = tok.strip("():,;{}")
            if clean in keywords:
                color = (198, 120, 221)  # purple for keywords
            elif tok.startswith(("'", '"')) or tok.endswith(("'", '"')):
                color = (152, 195, 121)  # green for strings
            elif tok.replace(".", "").replace("-", "").isdigit():
                color = (209, 154, 102)  # orange for numbers
            elif tok.startswith("#") or tok.startswith("//"):
                color = (92, 99, 112)    # gray for comments
                draw.text((cx, y), " ".join(tokens[tokens.index(tok):]),
                          fill=color, font=font)
                return
            else:
                color = (171, 178, 191)  # light gray default
            draw.text((cx, y), tok + " ", fill=color, font=font)
            cx += draw.textlength(tok + " ", font=font)

    def _draw_matrix(self, draw, frame, element, y):
        """Mathematical matrix with brackets.

        JSON: { "target": "matrix",
                "label": "A",
                "rows": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                "highlight_cells": [[0,1], [1,2]] }
        """
        label = element.get("label", "")
        rows  = element.get("rows", [])
        highlights = element.get("highlight_cells", [])
        s = self.scale
        if not rows:
            return y

        num_font = _get_math_font(int(44 * s))
        lbl_font = _get_font(int(40 * s), bold=True)
        cell_w = int(80 * s)
        cell_h = int(60 * s)
        pad = int(20 * s)
        bracket_w = int(12 * s)

        n_rows = len(rows)
        n_cols = max(len(r) for r in rows) if rows else 0
        mat_w = n_cols * cell_w
        mat_h = n_rows * cell_h

        total_w = mat_w + 2 * bracket_w + 2 * pad
        lbl_w = draw.textlength(f"{label} = ", font=lbl_font) if label else 0
        start_x = self.content_x + (self.content_w - total_w - lbl_w) // 2

        # Label
        if label:
            draw.text((start_x, y + mat_h // 2 - int(20 * s)),
                      f"{label} = ", fill=self._rgb("blue"), font=lbl_font)
            start_x += lbl_w

        bx = start_x
        # Left bracket
        draw.line([bx + bracket_w, y, bx, y], fill=self._rgb("body_text"), width=int(3 * s))
        draw.line([bx, y, bx, y + mat_h], fill=self._rgb("body_text"), width=int(3 * s))
        draw.line([bx, y + mat_h, bx + bracket_w, y + mat_h],
                  fill=self._rgb("body_text"), width=int(3 * s))
        # Right bracket
        rx = bx + bracket_w + mat_w + pad
        draw.line([rx - bracket_w, y, rx, y], fill=self._rgb("body_text"), width=int(3 * s))
        draw.line([rx, y, rx, y + mat_h], fill=self._rgb("body_text"), width=int(3 * s))
        draw.line([rx, y + mat_h, rx - bracket_w, y + mat_h],
                  fill=self._rgb("body_text"), width=int(3 * s))

        # Cells
        for ri, row in enumerate(rows):
            for ci, val in enumerate(row):
                cx = bx + bracket_w + pad // 2 + ci * cell_w
                cy = y + ri * cell_h
                if [ri, ci] in highlights:
                    draw.rounded_rectangle(
                        [cx, cy, cx + cell_w - int(4 * s), cy + cell_h - int(4 * s)],
                        radius=int(4 * s), fill=(255, 243, 224),
                    )
                vstr = str(val)
                vw = draw.textlength(vstr, font=num_font)
                draw.text((cx + (cell_w - vw) / 2, cy + (cell_h - num_font.size) / 2),
                          vstr, fill=self._rgb("body_text"), font=num_font)
        return y + mat_h + int(30 * s)

    def _draw_proof_steps(self, draw, frame, element, y):
        """Formal proof with numbered statements + reasons.

        JSON: { "target": "proof_steps",
                "heading": "Proof",
                "steps": [
                    {"statement": "AB = CD", "reason": "Given"},
                    {"statement": "∠A = ∠C", "reason": "Alternate angles"}
                ] }
        """
        heading = element.get("heading", "Proof")
        steps   = element.get("steps", [])
        s = self.scale

        head_font = _get_font(int(44 * s), bold=True)
        stmt_font = _get_math_font(int(38 * s))
        reas_font = _get_font(int(32 * s))
        pad_x = int(48 * s)
        pad_y = int(28 * s)
        row_h = int(72 * s)
        head_h = int(head_font.size * 1.5)
        card_h = head_h + len(steps) * row_h + 2 * pad_y
        cx = self.content_x

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(10 * s), fill=(248, 248, 255),
        )
        draw.rectangle([cx, y, cx + int(5 * s), y + card_h], fill=self._rgb("blue"))

        cy = y + pad_y
        draw.text((cx + pad_x, cy), heading, fill=self._rgb("blue"), font=head_font)
        cy += head_h

        num_font = _get_font(int(30 * s), bold=True)
        half_w = (self.content_w - 2 * pad_x) // 2

        for i, step in enumerate(steps):
            stmt = step.get("statement", "") if isinstance(step, dict) else str(step)
            reason = step.get("reason", "") if isinstance(step, dict) else ""

            # Number
            nstr = str(i + 1) + "."
            draw.text((cx + pad_x, cy + int(4 * s)), nstr,
                      fill=self._rgb("blue"), font=num_font)
            # Statement
            draw.text((cx + pad_x + int(40 * s), cy),
                      stmt, fill=self._rgb("body_text"), font=stmt_font)
            # Reason (right-aligned, italic-ish)
            if reason:
                rtxt = f"[{reason}]"
                rw = draw.textlength(rtxt, font=reas_font)
                draw.text((cx + self.content_w - pad_x - rw, cy + int(8 * s)),
                          rtxt, fill=self._rgb("body_secondary"), font=reas_font)
            cy += row_h
        return y + card_h

    def _draw_conversion_chain(self, draw, frame, element, y):
        """Unit conversion chain: km → m → cm with multipliers.

        JSON: { "target": "conversion_chain",
                "steps": [
                    {"value": "5 km", "operation": "× 1000"},
                    {"value": "5000 m", "operation": "× 100"},
                    {"value": "500000 cm"}
                ] }
        """
        steps = element.get("steps", [])
        s = self.scale
        if not steps:
            return y

        val_font = _get_font(int(44 * s), bold=True)
        op_font  = _get_font(int(32 * s), bold=True)
        arrow_font = _get_symbol_font(int(36 * s))
        pad_y = int(24 * s)
        box_h = int(64 * s)
        arrow_w = int(100 * s)

        n = len(steps)
        box_w = min(int(220 * s), (self.content_w - (n - 1) * arrow_w) // n)
        total_w = n * box_w + (n - 1) * arrow_w
        start_x = self.content_x + (self.content_w - total_w) // 2

        for i, step in enumerate(steps):
            bx = start_x + i * (box_w + arrow_w)
            val = step.get("value", "")
            op  = step.get("operation", "")

            # Value box
            draw.rounded_rectangle(
                [bx, y + pad_y, bx + box_w, y + pad_y + box_h],
                radius=int(8 * s), fill=self._rgb("concept_blue_bg"),
                outline=self._rgb("blue"), width=int(2 * s),
            )
            vw = draw.textlength(val, font=val_font)
            draw.text((bx + (box_w - vw) / 2, y + pad_y + (box_h - val_font.size) / 2),
                      val, fill=self._rgb("blue"), font=val_font)

            # Arrow + operation label
            if i < n - 1 and op:
                ax = bx + box_w
                ay = y + pad_y + box_h // 2
                draw.text((ax + int(10 * s), ay - int(30 * s)),
                          op, fill=self._rgb("orange"), font=op_font)
                draw.text((ax + arrow_w // 2 - int(10 * s), ay - int(12 * s)),
                          "\u2192", fill=self._rgb("orange"), font=arrow_font)

        return y + pad_y + box_h + int(30 * s)

    def _draw_dice_visual(self, draw, frame, element, y):
        """Dice faces for probability questions.

        JSON: { "target": "dice_visual",
                "faces": [1, 3, 6],
                "highlight": [6],
                "label": "Favorable outcomes" }
        """
        faces     = element.get("faces", [1, 2, 3, 4, 5, 6])
        highlight = element.get("highlight", [])
        label     = element.get("label", "")
        s = self.scale

        die_size = int(80 * s)
        gap = int(20 * s)
        dot_r = int(8 * s)
        lbl_font = _get_font(int(36 * s), bold=True)

        n = len(faces)
        total_w = n * die_size + (n - 1) * gap
        start_x = self.content_x + (self.content_w - total_w) // 2

        if label:
            lw = draw.textlength(label, font=lbl_font)
            draw.text(((self.width - lw) / 2, y), label,
                      fill=self._rgb("note_text"), font=lbl_font)
            y += int(48 * s)

        # Dot positions for each face value (relative to die center)
        _dot_pos = {
            1: [(0, 0)],
            2: [(-1, -1), (1, 1)],
            3: [(-1, -1), (0, 0), (1, 1)],
            4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
            5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],
            6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)],
        }

        for i, face in enumerate(faces):
            dx = start_x + i * (die_size + gap)
            dy = y
            is_hl = face in highlight
            bg = (255, 243, 224) if is_hl else (255, 255, 255)
            outline = self._rgb("orange") if is_hl else (180, 180, 200)

            draw.rounded_rectangle(
                [dx, dy, dx + die_size, dy + die_size],
                radius=int(8 * s), fill=bg, outline=outline, width=int(2 * s),
            )
            cx_d = dx + die_size // 2
            cy_d = dy + die_size // 2
            offset = int(22 * s)
            for (px, py) in _dot_pos.get(face, []):
                ex = cx_d + px * offset
                ey = cy_d + py * offset
                draw.ellipse([ex - dot_r, ey - dot_r, ex + dot_r, ey + dot_r],
                             fill=(30, 30, 60))
        return y + die_size + int(20 * s)

    def _draw_calendar_visual(self, draw, frame, element, y):
        """Calendar month grid with highlighted dates.

        JSON: { "target": "calendar_visual",
                "month": "March", "year": 2026,
                "highlight_dates": [5, 15, 25],
                "start_day": 0 }
        """
        month_name = element.get("month", "")
        year       = element.get("year", "")
        highlights = element.get("highlight_dates", [])
        start_day  = element.get("start_day", 0)  # 0=Mon
        days_in_month = element.get("days", 31)
        s = self.scale

        head_font = _get_font(int(36 * s), bold=True)
        day_font  = _get_font(int(28 * s))
        num_font  = _get_font(int(26 * s))
        cell_w = int(90 * s)
        cell_h = int(52 * s)
        hdr_h  = int(48 * s)

        total_w = 7 * cell_w
        start_x = self.content_x + (self.content_w - total_w) // 2

        # Month/Year header
        title = f"{month_name} {year}" if month_name else str(year)
        tw = draw.textlength(title, font=head_font)
        draw.text(((self.width - tw) / 2, y), title,
                  fill=self._rgb("note_text"), font=head_font)
        y += hdr_h

        # Day headers
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, d in enumerate(days):
            dw = draw.textlength(d, font=day_font)
            draw.text((start_x + i * cell_w + (cell_w - dw) / 2, y),
                      d, fill=self._rgb("body_secondary"), font=day_font)
        y += int(36 * s)

        # Date grid
        row_y = y
        col = start_day
        for day in range(1, days_in_month + 1):
            cx = start_x + col * cell_w
            is_hl = day in highlights
            if is_hl:
                draw.rounded_rectangle(
                    [cx + int(4 * s), row_y + int(2 * s),
                     cx + cell_w - int(4 * s), row_y + cell_h - int(2 * s)],
                    radius=int(6 * s), fill=self._rgb("orange"),
                )
                fc = (255, 255, 255)
            else:
                fc = self._rgb("body_text")
            nw = draw.textlength(str(day), font=num_font)
            draw.text((cx + (cell_w - nw) / 2, row_y + (cell_h - num_font.size) / 2),
                      str(day), fill=fc, font=num_font)
            col += 1
            if col >= 7:
                col = 0
                row_y += cell_h

        total_rows = (start_day + days_in_month + 6) // 7
        return y + total_rows * cell_h + int(16 * s)

    def _draw_seating_arrangement(self, draw, frame, element, y):
        """Linear or circular seating arrangement — reasoning puzzles.

        JSON: { "target": "seating_arrangement",
                "layout": "circular|linear",
                "seats": ["A", "B", "C", "D", "E"],
                "highlight": ["B", "D"],
                "facing": "center|outward" }
        """
        layout  = element.get("layout", "circular")
        seats   = element.get("seats", [])
        highlight = set(element.get("highlight", []))
        s = self.scale
        if not seats:
            return y

        name_font = _get_font(int(28 * s), bold=True)
        seat_r = int(32 * s)
        n = len(seats)

        if layout == "linear":
            gap = int(20 * s)
            total_w = n * (seat_r * 2 + gap) - gap
            start_x = self.content_x + (self.content_w - total_w) // 2
            cy_c = y + int(80 * s)

            # Table bar
            draw.rounded_rectangle(
                [start_x - int(20 * s), cy_c + seat_r + int(4 * s),
                 start_x + total_w + int(20 * s), cy_c + seat_r + int(16 * s)],
                radius=int(4 * s), fill=(200, 200, 220),
            )

            for i, name in enumerate(seats):
                cx = start_x + i * (seat_r * 2 + gap) + seat_r
                is_hl = name in highlight
                bg = self._rgb("orange") if is_hl else self._rgb("concept_blue_bg")
                outline = self._rgb("orange") if is_hl else self._rgb("blue")
                fc = (255, 255, 255) if is_hl else self._rgb("blue")
                draw.ellipse([cx - seat_r, cy_c - seat_r, cx + seat_r, cy_c + seat_r],
                             fill=bg, outline=outline, width=int(2 * s))
                nw = draw.textlength(name, font=name_font)
                draw.text((cx - nw / 2, cy_c - name_font.size / 2),
                          name, fill=fc, font=name_font)
            return cy_c + seat_r + int(40 * s)
        else:  # circular
            radius = min(int(150 * s), (self.content_w - 4 * seat_r) // 2)
            cx_c = self.content_x + self.content_w // 2
            cy_c = y + radius + seat_r + int(20 * s)

            # Center table
            table_r = radius - seat_r - int(15 * s)
            if table_r > int(30 * s):
                draw.ellipse([cx_c - table_r, cy_c - table_r,
                              cx_c + table_r, cy_c + table_r],
                             fill=(230, 230, 240), outline=(200, 200, 220), width=int(2 * s))

            for i, name in enumerate(seats):
                angle = 2 * math.pi * i / n - math.pi / 2
                sx = cx_c + int(radius * math.cos(angle))
                sy = cy_c + int(radius * math.sin(angle))
                is_hl = name in highlight
                bg = self._rgb("orange") if is_hl else (255, 255, 255)
                outline = self._rgb("orange") if is_hl else self._rgb("blue")
                fc = (255, 255, 255) if is_hl else self._rgb("blue")
                draw.ellipse([sx - seat_r, sy - seat_r, sx + seat_r, sy + seat_r],
                             fill=bg, outline=outline, width=int(2 * s))
                nw = draw.textlength(name, font=name_font)
                draw.text((sx - nw / 2, sy - name_font.size / 2),
                          name, fill=fc, font=name_font)
            return cy_c + radius + seat_r + int(30 * s)

    def _draw_coding_decoding(self, draw, frame, element, y):
        """Letter ↔ number / symbol mapping grid — reasoning.

        JSON: { "target": "coding_decoding",
                "heading": "Code Table",
                "mapping": {"A": "1", "B": "2", "C": "3", ...},
                "highlight_keys": ["B", "D"] }
        """
        heading = element.get("heading", "")
        mapping = element.get("mapping", {})
        highlight_keys = set(element.get("highlight_keys", []))
        s = self.scale
        if not mapping:
            return y

        head_font = _get_font(int(40 * s), bold=True)
        key_font  = _get_font(int(34 * s), bold=True)
        val_font  = _get_font(int(32 * s))
        cell_w = int(72 * s)
        cell_h = int(56 * s)
        pad_y = int(24 * s)

        keys = list(mapping.keys())
        n = len(keys)
        cols = min(n, 13)
        rows_needed = (n + cols - 1) // cols
        total_w = cols * cell_w
        start_x = self.content_x + (self.content_w - total_w) // 2

        if heading:
            hw = draw.textlength(heading, font=head_font)
            draw.text(((self.width - hw) / 2, y), heading,
                      fill=self._rgb("note_text"), font=head_font)
            y += int(50 * s)

        for row_idx in range(rows_needed):
            for ci in range(cols):
                idx = row_idx * cols + ci
                if idx >= n:
                    break
                k = keys[idx]
                v = str(mapping[k])
                cx = start_x + ci * cell_w
                ky = y + row_idx * (cell_h * 2 + int(8 * s))

                is_hl = k in highlight_keys
                bg = (255, 243, 224) if is_hl else self._rgb("concept_blue_bg")
                border = self._rgb("orange") if is_hl else self._rgb("blue")

                # Key cell (top)
                draw.rounded_rectangle(
                    [cx + 2, ky, cx + cell_w - 2, ky + cell_h],
                    radius=int(4 * s), fill=border,
                )
                kw = draw.textlength(k, font=key_font)
                draw.text((cx + (cell_w - kw) / 2, ky + (cell_h - key_font.size) / 2),
                          k, fill=(255, 255, 255), font=key_font)
                # Value cell (bottom)
                draw.rounded_rectangle(
                    [cx + 2, ky + cell_h, cx + cell_w - 2, ky + cell_h * 2],
                    radius=int(4 * s), fill=bg, outline=border, width=int(1 * s),
                )
                vw = draw.textlength(v, font=val_font)
                draw.text((cx + (cell_w - vw) / 2, ky + cell_h + (cell_h - val_font.size) / 2),
                          v, fill=self._rgb("body_text"), font=val_font)

        total_h = rows_needed * (cell_h * 2 + int(8 * s)) + pad_y
        return y + total_h

    def _draw_syllogism(self, draw, frame, element, y):
        """Syllogism with premises and conclusion — Venn visual.

        JSON: { "target": "syllogism",
                "premises": ["All dogs are animals", "All animals are living beings"],
                "conclusion": "All dogs are living beings",
                "valid": true }
        """
        premises   = element.get("premises", [])
        conclusion = element.get("conclusion", "")
        valid      = element.get("valid", True)
        s = self.scale

        prem_font = _get_font(int(40 * s))
        conc_font = _get_font(int(42 * s), bold=True)
        lbl_font  = _get_font(int(32 * s), bold=True)
        sym_font  = _get_symbol_font(int(44 * s))
        pad_x = int(52 * s)
        pad_y = int(28 * s)
        line_h = int(prem_font.size * 1.8)

        card_h = len(premises) * line_h + int(80 * s) + 2 * pad_y
        cx = self.content_x

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(10 * s), fill=(248, 248, 255),
        )
        draw.rectangle([cx, y, cx + int(5 * s), y + card_h], fill=self._rgb("blue"))

        cy = y + pad_y
        draw.text((cx + pad_x, cy), "Premises:", fill=self._rgb("blue"), font=lbl_font)
        cy += int(40 * s)
        for p in premises:
            draw.text((cx + pad_x + int(20 * s), cy), f"\u2022 {p}",
                      fill=self._rgb("body_text"), font=prem_font)
            cy += line_h
        # Divider
        cy += int(8 * s)
        draw.line([cx + pad_x, cy, cx + self.content_w - pad_x, cy],
                  fill=(200, 200, 220), width=int(2 * s))
        cy += int(16 * s)
        # Conclusion
        sym = "\u2234"  # ∴
        draw.text((cx + pad_x, cy), sym, fill=self._rgb("blue"), font=sym_font)
        draw.text((cx + pad_x + int(40 * s), cy), conclusion,
                  fill=self._rgb("body_text"), font=conc_font)
        cy += int(conc_font.size * 1.4)
        # Validity badge
        if valid:
            badge_text, badge_color = "\u2713 VALID", self._rgb("success")
        else:
            badge_text, badge_color = "\u2717 INVALID", self._rgb("fail")
        bw = draw.textlength(badge_text, font=lbl_font) + int(20 * s)
        draw.rounded_rectangle(
            [cx + self.content_w - pad_x - bw, cy,
             cx + self.content_w - pad_x, cy + int(36 * s)],
            radius=int(4 * s), fill=badge_color,
        )
        draw.text((cx + self.content_w - pad_x - bw + int(10 * s), cy + int(4 * s)),
                  badge_text, fill=(255, 255, 255), font=lbl_font)
        return y + card_h

    def _draw_blood_relation_tree(self, draw, frame, element, y):
        """Family tree for blood relation problems.

        JSON: { "target": "blood_relation_tree",
                "members": [
                    {"name": "Ram", "relation": "Father", "level": 0},
                    {"name": "Sita", "relation": "Mother", "level": 0},
                    {"name": "Arjun", "relation": "Son", "level": 1}
                ],
                "highlight": ["Arjun"] }
        """
        members   = element.get("members", [])
        highlight = set(element.get("highlight", []))
        s = self.scale
        if not members:
            return y

        name_font = _get_font(int(28 * s), bold=True)
        rel_font  = _get_font(int(22 * s))
        box_w = int(120 * s)
        box_h = int(60 * s)
        level_gap = int(80 * s)
        h_gap = int(30 * s)

        levels = {}
        for m in members:
            lvl = m.get("level", 0)
            levels.setdefault(lvl, []).append(m)

        cy = y + int(20 * s)
        for lvl in sorted(levels.keys()):
            lvl_members = levels[lvl]
            n = len(lvl_members)
            total_w = n * box_w + (n - 1) * h_gap
            start_x = self.content_x + (self.content_w - total_w) // 2

            for i, m in enumerate(lvl_members):
                mx = start_x + i * (box_w + h_gap)
                name = m.get("name", "")
                rel  = m.get("relation", "")
                is_hl = name in highlight

                bg = self._rgb("orange") if is_hl else self._rgb("concept_blue_bg")
                border = self._rgb("orange") if is_hl else self._rgb("blue")
                fc = (255, 255, 255) if is_hl else self._rgb("blue")

                draw.rounded_rectangle(
                    [mx, cy, mx + box_w, cy + box_h],
                    radius=int(8 * s), fill=bg, outline=border, width=int(2 * s),
                )
                nw = draw.textlength(name, font=name_font)
                draw.text((mx + (box_w - nw) / 2, cy + int(6 * s)),
                          name, fill=fc, font=name_font)
                if rel:
                    rw = draw.textlength(rel, font=rel_font)
                    draw.text((mx + (box_w - rw) / 2, cy + int(34 * s)),
                              rel, fill=fc if is_hl else self._rgb("body_secondary"),
                              font=rel_font)

                # Vertical connector to next level
                if lvl < max(levels.keys()):
                    draw.line([mx + box_w // 2, cy + box_h,
                               mx + box_w // 2, cy + box_h + level_gap // 2],
                              fill=(180, 180, 200), width=int(2 * s))
            cy += box_h + level_gap

        return cy

    def _draw_direction_diagram(self, draw, frame, element, y):
        """Direction-based path visualization — reasoning.

        JSON: { "target": "direction_diagram",
                "moves": [
                    {"direction": "North", "distance": "5 km"},
                    {"direction": "East", "distance": "3 km"},
                    {"direction": "South", "distance": "2 km"}
                ],
                "start_label": "Home",
                "end_label": "Office" }
        """
        moves = element.get("moves", [])
        start_label = element.get("start_label", "Start")
        end_label = element.get("end_label", "End")
        s = self.scale
        if not moves:
            return y

        font = _get_font(int(24 * s))
        lbl_font = _get_font(int(28 * s), bold=True)
        dot_r = int(8 * s)
        arrow_len = int(80 * s)

        dir_map = {
            "north": (0, -1), "south": (0, 1),
            "east": (1, 0), "west": (-1, 0),
            "ne": (1, -1), "nw": (-1, -1),
            "se": (1, 1), "sw": (-1, 1),
            "n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0),
        }

        cx = self.content_x + self.content_w // 2
        cy = y + int(180 * s)

        # Draw compass rose in corner
        comp_cx = self.content_x + self.content_w - int(80 * s)
        comp_cy = y + int(60 * s)
        comp_r = int(35 * s)
        comp_font = _get_font(int(18 * s), bold=True)
        for d, (dx, dy), lbl in [("N", (0, -1), "N"), ("S", (0, 1), "S"),
                                   ("E", (1, 0), "E"), ("W", (-1, 0), "W")]:
            ex = comp_cx + dx * comp_r
            ey = comp_cy + dy * comp_r
            draw.text((ex - int(6 * s), ey - int(10 * s)), lbl,
                      fill=self._rgb("body_secondary"), font=comp_font)

        # Start dot
        draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
                     fill=self._rgb("green"))
        draw.text((cx + int(12 * s), cy - int(14 * s)), start_label,
                  fill=self._rgb("green"), font=lbl_font)

        # Draw moves
        px, py = cx, cy
        for move in moves:
            d = move.get("direction", "").lower().replace("-", "").replace(" ", "")
            dist = move.get("distance", "")
            dx, dy = dir_map.get(d, (0, 0))
            nx = px + dx * arrow_len
            ny = py + dy * arrow_len

            draw.line([px, py, nx, ny], fill=self._rgb("blue"), width=int(3 * s))
            # Arrowhead
            draw.ellipse([nx - int(4 * s), ny - int(4 * s),
                          nx + int(4 * s), ny + int(4 * s)],
                         fill=self._rgb("blue"))
            # Distance label
            mid_x = (px + nx) // 2
            mid_y = (py + ny) // 2
            draw.text((mid_x + int(8 * s), mid_y - int(16 * s)),
                      dist, fill=self._rgb("orange"), font=font)
            px, py = nx, ny

        # End dot
        draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r],
                     fill=self._rgb("red"))
        draw.text((px + int(12 * s), py - int(14 * s)), end_label,
                  fill=self._rgb("red"), font=lbl_font)

        return max(cy + int(200 * s), py + int(40 * s))

    def _draw_ranking_order(self, draw, frame, element, y):
        """Linear ranking / position visualization.

        JSON: { "target": "ranking_order",
                "heading": "Height Order (Tallest → Shortest)",
                "items": ["Ram", "Shyam", "Gita", "Priya", "Hari"],
                "highlight": ["Gita"],
                "numbered": true }
        """
        heading  = element.get("heading", "")
        items    = element.get("items", [])
        highlight = set(element.get("highlight", []))
        numbered = element.get("numbered", True)
        s = self.scale
        if not items:
            return y

        head_font = _get_font(int(40 * s), bold=True)
        name_font = _get_font(int(34 * s), bold=True)
        num_font  = _get_font(int(26 * s), bold=True)
        pad_y = int(20 * s)
        chip_h = int(52 * s)
        chip_gap = int(12 * s)

        if heading:
            hw = draw.textlength(heading, font=head_font)
            draw.text(((self.width - hw) / 2, y), heading,
                      fill=self._rgb("note_text"), font=head_font)
            y += int(52 * s)

        n = len(items)
        chip_w = min(int(160 * s), (self.content_w - (n - 1) * chip_gap) // n)
        total_w = n * chip_w + (n - 1) * chip_gap
        start_x = self.content_x + (self.content_w - total_w) // 2

        # Connecting line
        line_y = y + chip_h // 2
        draw.line([start_x, line_y, start_x + total_w, line_y],
                  fill=(200, 200, 220), width=int(3 * s))

        for i, item in enumerate(items):
            ix = start_x + i * (chip_w + chip_gap)
            is_hl = item in highlight
            bg = self._rgb("orange") if is_hl else self._rgb("concept_blue_bg")
            fc = (255, 255, 255) if is_hl else self._rgb("blue")
            border = self._rgb("orange") if is_hl else self._rgb("blue")

            draw.rounded_rectangle(
                [ix, y, ix + chip_w, y + chip_h],
                radius=int(8 * s), fill=bg, outline=border, width=int(2 * s),
            )
            label = f"{i+1}. {item}" if numbered else item
            lw = draw.textlength(label, font=name_font)
            # Truncate if needed
            if lw > chip_w - int(12 * s):
                label = item[:6] + ".."
                lw = draw.textlength(label, font=name_font)
            draw.text((ix + (chip_w - lw) / 2, y + (chip_h - name_font.size) / 2),
                      label, fill=fc, font=name_font)

        return y + chip_h + pad_y

    def _draw_series_pattern(self, draw, frame, element, y):
        """Number/letter series with difference arrows.

        JSON: { "target": "series_pattern",
                "series": [2, 5, 10, 17, 26],
                "differences": ["+3", "+5", "+7", "+9"],
                "next": "?",
                "next_diff": "+11" }
        """
        series = element.get("series", [])
        diffs  = element.get("differences", [])
        nxt    = element.get("next", "")
        nxt_diff = element.get("next_diff", "")
        s = self.scale
        if not series:
            return y

        num_font = _get_font(int(44 * s), bold=True)
        diff_font = _get_font(int(28 * s), bold=True)
        box_size = int(72 * s)
        gap = int(50 * s)

        all_items = [str(v) for v in series]
        if nxt:
            all_items.append(str(nxt))
        all_diffs = list(diffs)
        if nxt_diff:
            all_diffs.append(nxt_diff)

        n = len(all_items)
        total_w = n * box_size + (n - 1) * gap
        start_x = self.content_x + (self.content_w - total_w) // 2

        for i, val in enumerate(all_items):
            bx = start_x + i * (box_size + gap)
            is_unknown = (val == "?" or val == str(nxt))
            bg = (255, 243, 224) if is_unknown else self._rgb("concept_blue_bg")
            border = self._rgb("orange") if is_unknown else self._rgb("blue")

            draw.rounded_rectangle(
                [bx, y, bx + box_size, y + box_size],
                radius=int(8 * s), fill=bg, outline=border, width=int(2 * s),
            )
            vw = draw.textlength(val, font=num_font)
            draw.text((bx + (box_size - vw) / 2, y + (box_size - num_font.size) / 2),
                      val, fill=self._rgb("orange") if is_unknown else self._rgb("blue"),
                      font=num_font)

            # Difference arrow above
            if i < len(all_diffs):
                ax = bx + box_size
                ay = y - int(8 * s)
                # Curved arrow
                draw.line([ax + int(4 * s), ay, ax + gap - int(4 * s), ay],
                          fill=self._rgb("orange"), width=int(2 * s))
                dw = draw.textlength(all_diffs[i], font=diff_font)
                draw.text((ax + (gap - dw) / 2, ay - int(26 * s)),
                          all_diffs[i], fill=self._rgb("orange"), font=diff_font)

        return y + box_size + int(24 * s)

    def _draw_amendment_card(self, draw, frame, element, y):
        """Constitutional amendment / article card — polity.

        JSON: { "target": "amendment_card",
                "number": "Article 21",
                "title": "Right to Life",
                "description": "No person shall be deprived of his life or personal liberty...",
                "category": "Fundamental Rights",
                "color": "blue" }
        """
        number = element.get("number", "")
        title  = element.get("title", "")
        desc   = element.get("description", "")
        category = element.get("category", "")
        color  = element.get("color", "blue")
        s = self.scale

        accent = self._rgb(color if color in self.C else "blue")
        num_font  = _get_font(int(56 * s), bold=True)
        title_font = _get_font(int(42 * s), bold=True)
        desc_font  = _get_font(int(36 * s))
        cat_font   = _get_font(int(26 * s), bold=True)
        pad_x = int(48 * s)
        pad_y = int(32 * s)

        max_w = self.content_w - 2 * pad_x
        desc_lines = self._wrap_text(desc, desc_font, max_w) if desc else []
        line_h = int(desc_font.size * 1.5)
        card_h = int(num_font.size * 1.4) + int(title_font.size * 1.4) + \
                 len(desc_lines) * line_h + 2 * pad_y + int(40 * s)
        cx = self.content_x

        # Top accent band
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(12 * s), fill=(255, 255, 255),
        )
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + int(8 * s)],
            radius=0, fill=accent,
        )
        draw.rectangle([cx, y, cx + int(8 * s), y + card_h], fill=accent)

        cy = y + pad_y + int(8 * s)
        if category:
            cw = draw.textlength(category.upper(), font=cat_font) + int(20 * s)
            draw.rounded_rectangle(
                [cx + self.content_w - pad_x - cw, cy - int(4 * s),
                 cx + self.content_w - pad_x, cy + int(28 * s)],
                radius=int(4 * s), fill=accent,
            )
            draw.text((cx + self.content_w - pad_x - cw + int(10 * s), cy),
                      category.upper(), fill=(255, 255, 255), font=cat_font)

        draw.text((cx + pad_x, cy), number, fill=accent, font=num_font)
        cy += int(num_font.size * 1.4)
        draw.text((cx + pad_x, cy), title, fill=self._rgb("body_text"), font=title_font)
        cy += int(title_font.size * 1.4)
        cy += int(8 * s)
        for line in desc_lines:
            draw.text((cx + pad_x, cy), line,
                      fill=self._rgb("body_secondary"), font=desc_font)
            cy += line_h
        return y + card_h

    def _draw_person_card(self, draw, frame, element, y):
        """Person profile card — historical figures, scientists, leaders.

        JSON: { "target": "person_card",
                "name": "Mahatma Gandhi",
                "title": "Father of the Nation",
                "facts": {"Born": "1869", "Died": "1948", "Known for": "Non-violence"},
                "image_path": "",
                "color": "orange" }
        """
        name  = element.get("name", "")
        title = element.get("title", "")
        facts = element.get("facts", {})
        img_path = element.get("image_path", element.get("src_path", ""))
        color = element.get("color", "blue")
        s = self.scale

        accent = self._rgb(color if color in self.C else "blue")
        name_font  = _get_font(int(48 * s), bold=True)
        title_font = _get_font(int(34 * s))
        key_font   = _get_font(int(30 * s), bold=True)
        val_font   = _get_font(int(30 * s))
        pad_x = int(48 * s)
        pad_y = int(32 * s)

        fact_h = len(facts) * int(42 * s)
        card_h = int(name_font.size * 1.4) + int(title_font.size * 1.4) + fact_h + 2 * pad_y + int(24 * s)
        cx = self.content_x
        img_area_w = int(160 * s)

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(12 * s), fill=(255, 255, 255),
        )
        draw.rectangle([cx, y, cx + int(8 * s), y + card_h], fill=accent)

        # Avatar placeholder (or image)
        ax = cx + pad_x
        ay = y + pad_y
        avatar_size = int(100 * s)

        if img_path and os.path.exists(img_path):
            try:
                img = Image.open(img_path).convert("RGB")
                img = img.resize((avatar_size, avatar_size), Image.LANCZOS)
                frame.paste(img, (ax, ay))
            except Exception:
                draw.rounded_rectangle(
                    [ax, ay, ax + avatar_size, ay + avatar_size],
                    radius=int(50 * s), fill=accent,
                )
                init = name[0] if name else "?"
                iw = draw.textlength(init, font=name_font)
                draw.text((ax + (avatar_size - iw) / 2, ay + (avatar_size - name_font.size) / 2),
                          init, fill=(255, 255, 255), font=name_font)
        else:
            draw.rounded_rectangle(
                [ax, ay, ax + avatar_size, ay + avatar_size],
                radius=int(50 * s), fill=accent,
            )
            init = name[0] if name else "?"
            iw = draw.textlength(init, font=name_font)
            draw.text((ax + (avatar_size - iw) / 2, ay + (avatar_size - name_font.size) / 2),
                      init, fill=(255, 255, 255), font=name_font)

        # Text area (right of avatar)
        tx = ax + avatar_size + int(28 * s)
        ty = ay
        draw.text((tx, ty), name, fill=accent, font=name_font)
        ty += int(name_font.size * 1.4)
        if title:
            draw.text((tx, ty), title, fill=self._rgb("body_secondary"), font=title_font)
        ty += int(title_font.size * 1.4) + int(12 * s)

        # Facts as key: value pairs
        for k, v in facts.items():
            draw.text((tx, ty), f"{k}: ", fill=self._rgb("blue"), font=key_font)
            kw = draw.textlength(f"{k}: ", font=key_font)
            draw.text((tx + kw, ty), str(v), fill=self._rgb("body_text"), font=val_font)
            ty += int(42 * s)

        return y + card_h

    def _draw_stat_card(self, draw, frame, element, y):
        """Big number statistic card — economics, GK, current affairs.

        JSON: { "target": "stat_card",
                "stats": [
                    {"label": "GDP Growth", "value": "7.2%", "color": "green"},
                    {"label": "Inflation", "value": "4.5%", "color": "red"},
                    {"label": "Fiscal Deficit", "value": "5.9%", "color": "orange"}
                ] }
        """
        stats = element.get("stats", [])
        s = self.scale
        if not stats:
            return y

        big_font = _get_font(int(64 * s), bold=True)
        lbl_font = _get_font(int(30 * s))
        pad = int(24 * s)
        card_h = int(130 * s)

        n = len(stats)
        col_w = (self.content_w - (n - 1) * int(16 * s)) // n

        for i, stat in enumerate(stats):
            sx = self.content_x + i * (col_w + int(16 * s))
            color = stat.get("color", "blue")
            accent = self._rgb(color if color in self.C else "blue")
            value = str(stat.get("value", ""))
            label = stat.get("label", "")

            draw.rounded_rectangle(
                [sx, y, sx + col_w, y + card_h],
                radius=int(10 * s), fill=(248, 248, 255),
            )
            draw.rectangle([sx, y, sx + int(5 * s), y + card_h], fill=accent)

            # Big value
            vw = draw.textlength(value, font=big_font)
            draw.text((sx + (col_w - vw) / 2, y + pad),
                      value, fill=accent, font=big_font)
            # Label
            lw = draw.textlength(label, font=lbl_font)
            draw.text((sx + (col_w - lw) / 2, y + card_h - pad - lbl_font.size),
                      label, fill=self._rgb("body_secondary"), font=lbl_font)

        return y + card_h + int(16 * s)

    def _draw_split_screen(self, draw, frame, element, y):
        """Side-by-side comparison with headers and content.

        JSON: { "target": "split_screen",
                "left":  {"heading": "Before", "content": "Old method...", "color": "red"},
                "right": {"heading": "After",  "content": "New method...", "color": "green"} }
        """
        left  = element.get("left", {})
        right = element.get("right", {})
        s = self.scale

        head_font = _get_font(int(42 * s), bold=True)
        body_font = _get_font(int(36 * s))
        pad_x = int(36 * s)
        pad_y = int(28 * s)
        col_gap = int(20 * s)
        col_w = (self.content_w - col_gap) // 2
        vs_font = _get_font(int(32 * s), bold=True)

        # Measure height
        max_lines = 0
        for side in [left, right]:
            content = side.get("content", "")
            items = side.get("items", [])
            if items:
                max_lines = max(max_lines, len(items))
            elif content:
                wrapped = self._wrap_text(content, body_font, col_w - 2 * pad_x)
                max_lines = max(max_lines, len(wrapped))

        line_h = int(body_font.size * 1.6)
        head_h = int(head_font.size * 1.5)
        card_h = head_h + max_lines * line_h + 2 * pad_y

        for ci, (side, default_color) in enumerate([(left, "blue"), (right, "green")]):
            sx = self.content_x + ci * (col_w + col_gap)
            color = side.get("color", default_color)
            accent = self._rgb(color if color in self.C else default_color)
            heading = side.get("heading", "")
            content = side.get("content", "")
            items = side.get("items", [])

            # Card
            draw.rounded_rectangle(
                [sx, y, sx + col_w, y + card_h],
                radius=int(10 * s), fill=(248, 250, 255),
            )
            # Header band
            draw.rounded_rectangle(
                [sx, y, sx + col_w, y + head_h + pad_y],
                radius=int(10 * s), fill=accent,
            )
            draw.rectangle([sx, y + head_h, sx + col_w, y + head_h + pad_y], fill=accent)

            if heading:
                hw = draw.textlength(heading, font=head_font)
                draw.text((sx + (col_w - hw) / 2, y + pad_y // 2),
                          heading, fill=(255, 255, 255), font=head_font)

            cy = y + head_h + pad_y + int(8 * s)
            if items:
                for item in items:
                    draw.text((sx + pad_x, cy), f"\u2022 {item}",
                              fill=self._rgb("body_text"), font=body_font)
                    cy += line_h
            elif content:
                for line in self._wrap_text(content, body_font, col_w - 2 * pad_x):
                    draw.text((sx + pad_x, cy), line,
                              fill=self._rgb("body_text"), font=body_font)
                    cy += line_h

        # "VS" circle in center
        vs_cx = self.content_x + col_w + col_gap // 2
        vs_cy = y + card_h // 2
        vs_r = int(24 * s)
        draw.ellipse([vs_cx - vs_r, vs_cy - vs_r, vs_cx + vs_r, vs_cy + vs_r],
                     fill=self._rgb("orange"))
        vw = draw.textlength("VS", font=vs_font)
        draw.text((vs_cx - vw / 2, vs_cy - vs_font.size / 2),
                  "VS", fill=(255, 255, 255), font=vs_font)

        return y + card_h

    def _draw_grid_check(self, draw, frame, element, y):
        """Options × Criteria matrix with ✔/✘ marks.

        JSON: { "target": "grid_check",
                "criteria": ["Rule of 9", "Rule of 11"],
                "options": [
                    {"label": "A: 277218", "checks": [true, false]},
                    {"label": "B: 10098",  "checks": [true, true]},
                    {"label": "C: 12345",  "checks": [false, false]},
                    {"label": "D: 181998", "checks": [true, false]}
                ],
                "correct_row": 1 }
        """
        criteria = element.get("criteria", [])
        options  = element.get("options", [])
        correct_row = element.get("correct_row", -1)
        s = self.scale
        if not options or not criteria:
            return y

        head_font = _get_font(int(32 * s), bold=True)
        cell_font = _get_font(int(30 * s))
        sym_font  = _get_symbol_font(int(36 * s))
        label_font = _get_font(int(32 * s), bold=True)

        n_cols = len(criteria) + 1  # +1 for label column
        n_rows = len(options) + 1   # +1 for header row
        label_col_w = int(220 * s)
        check_col_w = (self.content_w - label_col_w) // max(1, len(criteria))
        row_h = int(56 * s)
        hdr_h = int(50 * s)

        cx = self.content_x

        # Header row
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + hdr_h],
            radius=int(8 * s), fill=self._rgb("header_bg"),
        )
        draw.text((cx + int(16 * s), y + int(10 * s)), "Option",
                  fill=(255, 255, 255), font=head_font)
        for ci, crit in enumerate(criteria):
            ccx = cx + label_col_w + ci * check_col_w
            cw = draw.textlength(crit, font=head_font)
            draw.text((ccx + (check_col_w - cw) / 2, y + int(10 * s)),
                      crit, fill=(255, 255, 255), font=head_font)

        # Data rows
        ry = y + hdr_h
        for ri, opt in enumerate(options):
            is_correct = (ri == correct_row)
            row_bg = (232, 245, 233) if is_correct else \
                     (248, 248, 255) if ri % 2 == 0 else (255, 255, 255)
            draw.rectangle([cx, ry, cx + self.content_w, ry + row_h], fill=row_bg)

            # Label
            draw.text((cx + int(16 * s), ry + int(12 * s)),
                      opt.get("label", ""), fill=self._rgb("body_text"), font=label_font)

            # Check marks
            for ci, passed in enumerate(opt.get("checks", [])):
                ccx = cx + label_col_w + ci * check_col_w
                sym = "\u2713" if passed else "\u2717"
                sym_color = self._rgb("success") if passed else self._rgb("fail")
                sw = draw.textlength(sym, font=sym_font)
                draw.text((ccx + (check_col_w - sw) / 2, ry + int(8 * s)),
                          sym, fill=sym_color, font=sym_font)
            ry += row_h

        # Bottom border
        draw.line([cx, ry, cx + self.content_w, ry],
                  fill=(200, 200, 220), width=int(2 * s))

        return ry + int(12 * s)

    def _draw_equation_steps(self, draw, frame, element, y):
        """Step-by-step equation solving with = alignment.

        JSON: { "target": "equation_steps",
                "heading": "Solving for x",
                "steps": [
                    "2x + 5 = 15",
                    "2x = 15 − 5",
                    "2x = 10",
                    "x = 5"
                ],
                "highlight_step": 3 }
        """
        heading = element.get("heading", "")
        steps   = element.get("steps", [])
        highlight_step = element.get("highlight_step", -1)
        s = self.scale

        head_font = _get_font(int(42 * s), bold=True)
        step_font = _get_math_font(int(44 * s))
        num_font  = _get_font(int(26 * s))
        pad_x = int(60 * s)
        pad_y = int(28 * s)
        line_h = int(step_font.size * 1.9)
        head_h = int(head_font.size * 1.5) if heading else 0
        card_h = head_h + len(steps) * line_h + 2 * pad_y
        cx = self.content_x

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(10 * s), fill=(248, 248, 255),
        )
        draw.rectangle([cx, y, cx + int(5 * s), y + card_h], fill=self._rgb("blue"))

        cy = y + pad_y
        if heading:
            draw.text((cx + pad_x, cy), heading, fill=self._rgb("blue"), font=head_font)
            cy += head_h

        for i, step in enumerate(steps):
            is_hl = (i == highlight_step)
            if is_hl:
                draw.rounded_rectangle(
                    [cx + pad_x - int(8 * s), cy - int(4 * s),
                     cx + self.content_w - pad_x, cy + line_h - int(4 * s)],
                    radius=int(6 * s), fill=(255, 243, 224),
                )
            # Step number
            draw.text((cx + pad_x, cy + int(10 * s)),
                      f"({i+1})", fill=self._rgb("body_secondary"), font=num_font)
            # Equation text — try to align on '='
            eq_x = cx + pad_x + int(50 * s)
            text_color = self._rgb("orange") if is_hl else self._rgb("body_text")
            draw.text((eq_x, cy), step, fill=text_color, font=step_font)
            cy += line_h

        return y + card_h

    def _draw_web_image(self, draw, frame, element, y):
        """Image loaded from URL — resolved by pipeline.

        JSON: { "target": "web_image",
                "url": "https://example.com/image.png",
                "caption": "Diagram",
                "size": "medium|large|small" }
        """
        src_path = element.get("src_path", element.get("_resolved_path", ""))
        caption  = element.get("caption", "")
        size     = element.get("size", "medium")
        s = self.scale

        size_map = {"small": 0.25, "medium": 0.35, "large": 0.50}
        max_h = int(self.height * size_map.get(size, 0.35))
        max_w = int(self.content_w * 0.85)
        cap_font = _get_font(int(28 * s))

        if src_path and os.path.exists(src_path):
            try:
                img = Image.open(src_path).convert("RGB")
                ratio = min(max_w / img.width, max_h / img.height)
                new_w, new_h = int(img.width * ratio), int(img.height * ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                px = self.content_x + (self.content_w - new_w) // 2
                frame.paste(img, (px, int(y)))
                y += new_h + int(8 * s)
                if caption:
                    cw = draw.textlength(caption, font=cap_font)
                    draw.text(((self.width - cw) / 2, y), caption,
                              fill=self._rgb("body_secondary"), font=cap_font)
                    y += int(36 * s)
                return y
            except Exception:
                pass

        # Fallback: placeholder
        ph_h = int(120 * s)
        draw.rounded_rectangle(
            [self.content_x + int(100 * s), y,
             self.content_x + self.content_w - int(100 * s), y + ph_h],
            radius=int(10 * s), fill=(240, 240, 245), outline=(200, 200, 210),
        )
        ph_text = caption or "(Image)"
        pw = draw.textlength(ph_text, font=cap_font)
        draw.text(((self.width - pw) / 2, y + (ph_h - cap_font.size) / 2),
                  ph_text, fill=self._rgb("body_secondary"), font=cap_font)
        return y + ph_h + int(12 * s)

    def _draw_web_gif(self, draw, frame, element, y):
        """GIF loaded from URL — first frame rendered as still.

        JSON: { "target": "web_gif",
                "url": "https://example.com/anim.gif",
                "caption": "Animation" }
        """
        # GIFs are resolved to local path by pipeline; render first frame
        return self._draw_web_image(draw, frame, element, y)

    def _draw_web_video(self, draw, frame, element, y):
        """Video clip from URL — rendered as still poster with play icon.

        JSON: { "target": "web_video",
                "url": "https://example.com/clip.mp4",
                "caption": "Experiment Demo" }
        """
        return self._draw_video_clip(draw, frame, element, y)

    def _draw_google_image(self, draw, frame, element, y):
        """Auto-searched image from Google/providers — resolved by pipeline.

        JSON: { "target": "google_image",
                "query": "solar system diagram",
                "caption": "Solar System",
                "size": "medium" }
        """
        return self._draw_web_image(draw, frame, element, y)

    # ------------------------------------------------------------------
    # BATCH 2 — 18 MORE ULTRA-PRO RENDER TARGETS
    # ------------------------------------------------------------------

    def _draw_truth_table(self, draw, frame, element, y):
        """Boolean logic truth table — CS, reasoning, discrete math.

        JSON: { "target": "truth_table",
                "heading": "AND Gate",
                "variables": ["p", "q"],
                "expression": "p ∧ q",
                "rows": [[true,true,true],[true,false,false],[false,true,false],[false,false,false]],
                "highlight_row": 0 }
        """
        heading = element.get("heading", "")
        variables = element.get("variables", ["p", "q"])
        expression = element.get("expression", "")
        rows = element.get("rows", [])
        highlight_row = element.get("highlight_row", -1)
        s = self.scale

        head_font = _get_font(int(36 * s), bold=True)
        cell_font = _get_font(int(32 * s))
        sym_font = _get_symbol_font(int(34 * s))
        pad_x = int(24 * s)
        row_h = int(50 * s)
        hdr_h = int(48 * s)

        cols = variables + ([expression] if expression else [])
        n_cols = len(cols)
        col_w = min(int(180 * s), self.content_w // max(1, n_cols))
        total_w = n_cols * col_w
        cx = self.content_x + (self.content_w - total_w) // 2

        if heading:
            hw = draw.textlength(heading, font=head_font)
            draw.text(((self.width - hw) / 2, y), heading,
                      fill=self._rgb("note_text"), font=head_font)
            y += int(48 * s)

        # Header row
        draw.rounded_rectangle(
            [cx, y, cx + total_w, y + hdr_h],
            radius=int(6 * s), fill=self._rgb("header_bg"),
        )
        for ci, col_name in enumerate(cols):
            ccx = cx + ci * col_w
            cw = draw.textlength(col_name, font=head_font)
            draw.text((ccx + (col_w - cw) / 2, y + int(8 * s)),
                      col_name, fill=(255, 255, 255), font=head_font)

        # Data rows
        ry = y + hdr_h
        for ri, row in enumerate(rows):
            is_hl = (ri == highlight_row)
            row_bg = (255, 243, 224) if is_hl else \
                     (248, 248, 255) if ri % 2 == 0 else (255, 255, 255)
            draw.rectangle([cx, ry, cx + total_w, ry + row_h], fill=row_bg)

            for ci, val in enumerate(row):
                ccx = cx + ci * col_w
                if isinstance(val, bool):
                    txt = "T" if val else "F"
                    color = self._rgb("success") if val else self._rgb("fail")
                else:
                    txt = str(val)
                    color = self._rgb("body_text")
                tw = draw.textlength(txt, font=cell_font)
                draw.text((ccx + (col_w - tw) / 2, ry + int(10 * s)),
                          txt, fill=color, font=cell_font)
            ry += row_h

        draw.line([cx, ry, cx + total_w, ry], fill=(200, 200, 220), width=int(2 * s))
        return ry + int(12 * s)

    def _draw_law_card(self, draw, frame, element, y):
        """Named scientific law / theorem card — Physics, Chemistry.

        JSON: { "target": "law_card",
                "name": "Newton's Second Law",
                "formula": "F = ma",
                "statement": "Force equals mass times acceleration.",
                "units": "F in Newtons, m in kg, a in m/s²",
                "color": "blue" }
        """
        name = element.get("name", "")
        formula = element.get("formula", "")
        statement = element.get("statement", "")
        units = element.get("units", "")
        color = element.get("color", "blue")
        s = self.scale

        accent = self._rgb(color if color in self.C else "blue")
        name_font = _get_font(int(44 * s), bold=True)
        form_font = _get_math_font(int(56 * s))
        stmt_font = _get_font(int(36 * s))
        unit_font = _get_font(int(28 * s))
        pad_x = int(52 * s)
        pad_y = int(28 * s)

        max_w = self.content_w - 2 * pad_x
        stmt_lines = self._wrap_text(statement, stmt_font, max_w) if statement else []
        line_h = int(stmt_font.size * 1.5)
        form_h = int(form_font.size * 1.6) if formula else 0
        unit_h = int(40 * s) if units else 0
        card_h = int(name_font.size * 1.5) + form_h + len(stmt_lines) * line_h + unit_h + 2 * pad_y + int(24 * s)
        cx = self.content_x

        # Card with gradient-style top band
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(14 * s), fill=(255, 255, 255),
        )
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + int(60 * s)],
            radius=int(14 * s), fill=accent,
        )
        draw.rectangle([cx, y + int(40 * s), cx + self.content_w, y + int(60 * s)], fill=accent)
        draw.rectangle([cx, y, cx + int(8 * s), y + card_h], fill=accent)

        cy = y + int(10 * s)
        # Law name in white on accent band
        nw = draw.textlength(name, font=name_font)
        draw.text(((self.width - nw) / 2, cy), name,
                  fill=(255, 255, 255), font=name_font)
        cy += int(60 * s) + int(12 * s)

        # Formula centered, large
        if formula:
            fw = draw.textlength(formula, font=form_font)
            draw.text(((self.width - fw) / 2, cy), formula,
                      fill=accent, font=form_font)
            cy += form_h

        # Statement
        for line in stmt_lines:
            lw = draw.textlength(line, font=stmt_font)
            draw.text(((self.width - lw) / 2, cy), line,
                      fill=self._rgb("body_text"), font=stmt_font)
            cy += line_h

        # Units
        if units:
            cy += int(8 * s)
            uw = draw.textlength(units, font=unit_font)
            draw.text(((self.width - uw) / 2, cy), units,
                      fill=self._rgb("body_secondary"), font=unit_font)

        return y + card_h

    def _draw_tip_box(self, draw, frame, element, y):
        """Exam shortcut / quick tip box — all subjects.

        JSON: { "target": "tip_box",
                "title": "Quick Tip",
                "text": "Multiply by 11: write digits, insert sum in middle.",
                "color": "green" }
        """
        title = element.get("title", "Quick Tip")
        text = element.get("text", element.get("value", ""))
        color = element.get("color", "green")
        s = self.scale

        color_map = {
            "green": ((46, 125, 50), (232, 245, 233), "\u2728"),
            "blue":  ((21, 101, 192), (227, 242, 253), "\U0001f4a1"),
            "orange": ((239, 108, 0), (255, 243, 224), "\u26A1"),
        }
        fg, bg, icon = color_map.get(color, color_map["green"])

        title_font = _get_font(int(42 * s), bold=True)
        text_font = _get_font(int(38 * s))
        icon_font = _get_symbol_font(int(48 * s))
        pad_x = int(52 * s)
        pad_y = int(28 * s)

        max_w = self.content_w - 2 * pad_x - int(60 * s)
        lines = self._wrap_text(text, text_font, max_w)
        line_h = int(text_font.size * 1.5)
        title_h = int(title_font.size * 1.5)
        card_h = title_h + len(lines) * line_h + 2 * pad_y
        cx = self.content_x

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(12 * s), fill=bg,
        )
        draw.rectangle([cx, y, cx + int(7 * s), y + card_h], fill=fg)

        # Icon + title
        cy = y + pad_y
        draw.text((cx + pad_x, cy - int(4 * s)), icon, fill=fg, font=icon_font)
        draw.text((cx + pad_x + int(52 * s), cy), title, fill=fg, font=title_font)
        cy += title_h

        for line in lines:
            draw.text((cx + pad_x + int(52 * s), cy), line,
                      fill=self._rgb("body_text"), font=text_font)
            cy += line_h
        return y + card_h

    def _draw_warning_box(self, draw, frame, element, y):
        """Common mistake / trap warning — all subjects.

        JSON: { "target": "warning_box",
                "title": "Common Mistake",
                "text": "Students forget to check divisibility by 11 after passing rule of 9." }
        """
        title = element.get("title", "Common Mistake")
        text = element.get("text", element.get("value", ""))
        s = self.scale

        fg = self._rgb("fail")
        bg = (255, 235, 238)

        title_font = _get_font(int(42 * s), bold=True)
        text_font = _get_font(int(38 * s))
        icon_font = _get_symbol_font(int(48 * s))
        pad_x = int(52 * s)
        pad_y = int(28 * s)

        max_w = self.content_w - 2 * pad_x - int(60 * s)
        lines = self._wrap_text(text, text_font, max_w)
        line_h = int(text_font.size * 1.5)
        title_h = int(title_font.size * 1.5)
        card_h = title_h + len(lines) * line_h + 2 * pad_y
        cx = self.content_x

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(12 * s), fill=bg,
        )
        draw.rectangle([cx, y, cx + int(7 * s), y + card_h], fill=fg)

        cy = y + pad_y
        draw.text((cx + pad_x, cy - int(4 * s)), "\u26A0", fill=fg, font=icon_font)
        draw.text((cx + pad_x + int(52 * s), cy), title, fill=fg, font=title_font)
        cy += title_h

        for line in lines:
            draw.text((cx + pad_x + int(52 * s), cy), line,
                      fill=self._rgb("body_text"), font=text_font)
            cy += line_h
        return y + card_h

    def _draw_event_card(self, draw, frame, element, y):
        """Event card — GK / current affairs / history.

        JSON: { "target": "event_card",
                "date": "15 August 1947",
                "title": "Indian Independence",
                "place": "New Delhi",
                "significance": "India gained freedom from British rule after 200 years.",
                "color": "orange" }
        """
        date = element.get("date", "")
        title = element.get("title", "")
        place = element.get("place", "")
        significance = element.get("significance", "")
        color = element.get("color", "orange")
        s = self.scale

        accent = self._rgb(color if color in self.C else "orange")
        date_font = _get_font(int(52 * s), bold=True)
        title_font = _get_font(int(42 * s), bold=True)
        detail_font = _get_font(int(34 * s))
        pad_x = int(52 * s)
        pad_y = int(28 * s)

        max_w = self.content_w - 2 * pad_x
        sig_lines = self._wrap_text(significance, detail_font, max_w) if significance else []
        line_h = int(detail_font.size * 1.5)
        card_h = int(date_font.size * 1.4) + int(title_font.size * 1.4) + \
                 (int(36 * s) if place else 0) + len(sig_lines) * line_h + 2 * pad_y + int(20 * s)
        cx = self.content_x

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(14 * s), fill=(255, 255, 255),
        )
        draw.rectangle([cx, y, cx + int(8 * s), y + card_h], fill=accent)

        cy = y + pad_y
        # Big date
        draw.text((cx + pad_x, cy), date, fill=accent, font=date_font)
        cy += int(date_font.size * 1.4)
        # Title
        draw.text((cx + pad_x, cy), title, fill=self._rgb("body_text"), font=title_font)
        cy += int(title_font.size * 1.4)
        # Place
        if place:
            draw.text((cx + pad_x, cy), f"\U0001F4CD {place}",
                      fill=self._rgb("body_secondary"), font=detail_font)
            cy += int(36 * s)
        # Divider
        cy += int(4 * s)
        draw.line([cx + pad_x, cy, cx + self.content_w - pad_x, cy],
                  fill=(220, 220, 230), width=int(2 * s))
        cy += int(12 * s)
        # Significance
        for line in sig_lines:
            draw.text((cx + pad_x, cy), line,
                      fill=self._rgb("body_text"), font=detail_font)
            cy += line_h
        return y + card_h

    def _draw_word_breakdown(self, draw, frame, element, y):
        """Prefix + root + suffix breakdown — English vocabulary.

        JSON: { "target": "word_breakdown",
                "word": "unhappiness",
                "parts": [
                    {"text": "un-", "type": "prefix", "meaning": "not"},
                    {"text": "happy", "type": "root", "meaning": "feeling joy"},
                    {"text": "-ness", "type": "suffix", "meaning": "state of"}
                ] }
        """
        word = element.get("word", "")
        parts = element.get("parts", [])
        s = self.scale

        word_font = _get_font(int(52 * s), bold=True)
        part_font = _get_font(int(40 * s), bold=True)
        type_font = _get_font(int(26 * s), bold=True)
        mean_font = _get_font(int(30 * s))
        pad_y = int(28 * s)

        type_colors = {
            "prefix": self._rgb("blue"),
            "root": self._rgb("green"),
            "suffix": self._rgb("orange"),
        }
        type_bgs = {
            "prefix": (227, 242, 253),
            "root": (232, 245, 233),
            "suffix": (255, 243, 224),
        }

        # Word header
        ww = draw.textlength(word, font=word_font)
        draw.text(((self.width - ww) / 2, y), word,
                  fill=self._rgb("note_text"), font=word_font)
        y += int(word_font.size * 1.6)

        # Parts side by side
        n = len(parts)
        gap = int(16 * s)
        box_w = min(int(280 * s), (self.content_w - (n - 1) * gap) // max(1, n))
        box_h = int(120 * s)
        total_w = n * box_w + (n - 1) * gap
        start_x = self.content_x + (self.content_w - total_w) // 2

        # Connecting line
        if n > 1:
            draw.line([start_x + box_w // 2, y + box_h // 2,
                       start_x + total_w - box_w // 2, y + box_h // 2],
                      fill=(200, 200, 220), width=int(2 * s))

        for i, part in enumerate(parts):
            px = start_x + i * (box_w + gap)
            ptype = part.get("type", "root")
            ptext = part.get("text", "")
            pmean = part.get("meaning", "")
            fg = type_colors.get(ptype, self._rgb("blue"))
            bg = type_bgs.get(ptype, (240, 240, 255))

            draw.rounded_rectangle(
                [px, y, px + box_w, y + box_h],
                radius=int(10 * s), fill=bg, outline=fg, width=int(2 * s),
            )
            # Type badge at top
            tw = draw.textlength(ptype.upper(), font=type_font) + int(16 * s)
            draw.rounded_rectangle(
                [px + (box_w - tw) // 2, y - int(4 * s),
                 px + (box_w + tw) // 2, y + int(24 * s)],
                radius=int(4 * s), fill=fg,
            )
            btw = draw.textlength(ptype.upper(), font=type_font)
            draw.text((px + (box_w - btw) / 2, y), ptype.upper(),
                      fill=(255, 255, 255), font=type_font)

            # Part text
            ptw = draw.textlength(ptext, font=part_font)
            draw.text((px + (box_w - ptw) / 2, y + int(32 * s)),
                      ptext, fill=fg, font=part_font)
            # Meaning
            if pmean:
                mw = draw.textlength(pmean, font=mean_font)
                draw.text((px + (box_w - mw) / 2, y + int(76 * s)),
                          pmean, fill=self._rgb("body_secondary"), font=mean_font)

        return y + box_h + int(20 * s)

    def _draw_fill_blank_sentence(self, draw, frame, element, y):
        """Sentence with _____ blank + answer reveal — English.

        JSON: { "target": "fill_blank_sentence",
                "sentence": "The sun _____ in the east.",
                "answer": "rises",
                "revealed": true }
        """
        sentence = element.get("sentence", "")
        answer = element.get("answer", "")
        revealed = element.get("revealed", False)
        s = self.scale

        sent_font = _get_font(int(44 * s))
        ans_font = _get_font(int(46 * s), bold=True)
        pad_x = int(60 * s)
        pad_y = int(36 * s)
        cx = self.content_x

        # Split on blank
        if "_____" in sentence:
            parts = sentence.split("_____", 1)
        elif "___" in sentence:
            parts = sentence.split("___", 1)
        else:
            parts = [sentence, ""]

        card_h = int(120 * s)
        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(12 * s), fill=(248, 248, 255),
        )
        draw.rectangle([cx, y, cx + int(5 * s), y + card_h], fill=self._rgb("blue"))

        # Draw sentence with blank
        tx = cx + pad_x
        ty = y + pad_y
        draw.text((tx, ty), parts[0], fill=self._rgb("body_text"), font=sent_font)
        tx += draw.textlength(parts[0], font=sent_font)

        if revealed:
            # Show answer in green
            draw.text((tx, ty - int(4 * s)), answer,
                      fill=self._rgb("success"), font=ans_font)
            # Underline
            aw = draw.textlength(answer, font=ans_font)
            draw.line([tx, ty + ans_font.size + int(4 * s),
                       tx + aw, ty + ans_font.size + int(4 * s)],
                      fill=self._rgb("success"), width=int(3 * s))
            tx += aw
        else:
            # Show blank line
            blank_w = int(150 * s)
            draw.line([tx, ty + sent_font.size + int(4 * s),
                       tx + blank_w, ty + sent_font.size + int(4 * s)],
                      fill=self._rgb("body_secondary"), width=int(3 * s))
            tx += blank_w

        if len(parts) > 1:
            draw.text((tx, ty), parts[1], fill=self._rgb("body_text"), font=sent_font)

        return y + card_h

    def _draw_venn_operations(self, draw, frame, element, y):
        """Venn diagram with shaded regions for set operations.

        JSON: { "target": "venn_operations",
                "set_a": "A", "set_b": "B",
                "operation": "intersection|union|a_minus_b|b_minus_a|complement",
                "label": "A ∩ B" }
        """
        set_a = element.get("set_a", "A")
        set_b = element.get("set_b", "B")
        operation = element.get("operation", "intersection")
        label = element.get("label", "")
        s = self.scale

        lbl_font = _get_font(int(40 * s), bold=True)
        set_font = _get_font(int(32 * s), bold=True)
        r = int(110 * s)
        overlap = int(60 * s)
        cx_center = self.content_x + self.content_w // 2
        cy_center = y + r + int(50 * s)
        cx_a = cx_center - overlap // 2
        cx_b = cx_center + overlap // 2

        # Label
        if label:
            lw = draw.textlength(label, font=lbl_font)
            draw.text(((self.width - lw) / 2, y), label,
                      fill=self._rgb("note_text"), font=lbl_font)

        # Universal set rectangle
        rect_pad = int(40 * s)
        draw.rounded_rectangle(
            [cx_center - r - overlap - rect_pad, cy_center - r - rect_pad,
             cx_center + r + overlap + rect_pad, cy_center + r + rect_pad],
            radius=int(8 * s), outline=(180, 180, 200), width=int(2 * s),
        )

        # Draw using PIL image compositing for proper shading
        from PIL import ImageDraw as ID2
        mask = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        md = ID2.Draw(mask)

        shade_a = (21, 101, 192, 60)
        shade_b = (239, 108, 0, 60)
        shade_both = (128, 0, 128, 80)

        if operation == "union":
            md.ellipse([cx_a - r, cy_center - r, cx_a + r, cy_center + r], fill=shade_a)
            md.ellipse([cx_b - r, cy_center - r, cx_b + r, cy_center + r], fill=shade_b)
        elif operation == "intersection":
            # Draw both circles lightly, intersection darker via overlap
            md.ellipse([cx_a - r, cy_center - r, cx_a + r, cy_center + r], fill=shade_a)
            md.ellipse([cx_b - r, cy_center - r, cx_b + r, cy_center + r], fill=shade_a)
        elif operation == "a_minus_b":
            md.ellipse([cx_a - r, cy_center - r, cx_a + r, cy_center + r], fill=shade_a)
        elif operation == "b_minus_a":
            md.ellipse([cx_b - r, cy_center - r, cx_b + r, cy_center + r], fill=shade_b)
        elif operation == "complement":
            md.rectangle([cx_center - r - overlap - rect_pad, cy_center - r - rect_pad,
                          cx_center + r + overlap + rect_pad, cy_center + r + rect_pad],
                         fill=(200, 200, 220, 40))

        frame.paste(Image.alpha_composite(
            frame.convert("RGBA"), mask).convert("RGB"), (0, 0))

        # Circle outlines
        draw_new = ImageDraw.Draw(frame)
        draw_new.ellipse([cx_a - r, cy_center - r, cx_a + r, cy_center + r],
                         outline=self._rgb("blue"), width=int(3 * s))
        draw_new.ellipse([cx_b - r, cy_center - r, cx_b + r, cy_center + r],
                         outline=self._rgb("orange"), width=int(3 * s))

        # Set labels
        draw_new.text((cx_a - r + int(20 * s), cy_center - int(12 * s)),
                      set_a, fill=self._rgb("blue"), font=set_font)
        draw_new.text((cx_b + r - int(50 * s), cy_center - int(12 * s)),
                      set_b, fill=self._rgb("orange"), font=set_font)

        return cy_center + r + rect_pad + int(20 * s)

    def _draw_mirror_image(self, draw, frame, element, y):
        """Mirror / water reflection visualization — non-verbal reasoning.

        JSON: { "target": "mirror_image",
                "original": "AMBULANCE",
                "mirrored": "ECNALUBMA",
                "mirror_type": "vertical|horizontal",
                "label": "Mirror Image" }
        """
        original = element.get("original", "")
        mirrored = element.get("mirrored", "")
        mirror_type = element.get("mirror_type", "vertical")
        label_text = element.get("label", "Mirror Image")
        s = self.scale

        big_font = _get_font(int(52 * s), bold=True)
        lbl_font = _get_font(int(32 * s), bold=True)
        tag_font = _get_font(int(26 * s))
        pad = int(40 * s)

        # Label
        lw = draw.textlength(label_text, font=lbl_font)
        draw.text(((self.width - lw) / 2, y), label_text,
                  fill=self._rgb("note_text"), font=lbl_font)
        y += int(48 * s)

        box_w = int(400 * s)
        box_h = int(100 * s)
        gap = int(60 * s)
        total_w = 2 * box_w + gap
        start_x = self.content_x + (self.content_w - total_w) // 2

        # Original box
        draw.rounded_rectangle(
            [start_x, y, start_x + box_w, y + box_h],
            radius=int(10 * s), fill=(227, 242, 253), outline=self._rgb("blue"), width=int(2 * s),
        )
        draw.text((start_x + int(12 * s), y - int(2 * s)), "Original",
                  fill=self._rgb("blue"), font=tag_font)
        ow = draw.textlength(original, font=big_font)
        draw.text((start_x + (box_w - ow) / 2, y + (box_h - big_font.size) / 2),
                  original, fill=self._rgb("blue"), font=big_font)

        # Mirror line
        mx = start_x + box_w + gap // 2
        draw.line([mx, y - int(10 * s), mx, y + box_h + int(10 * s)],
                  fill=(180, 180, 200), width=int(3 * s))
        draw.text((mx - int(30 * s), y + box_h + int(14 * s)), "Mirror",
                  fill=self._rgb("body_secondary"), font=tag_font)

        # Mirrored box
        mx2 = start_x + box_w + gap
        draw.rounded_rectangle(
            [mx2, y, mx2 + box_w, y + box_h],
            radius=int(10 * s), fill=(255, 243, 224), outline=self._rgb("orange"), width=int(2 * s),
        )
        draw.text((mx2 + int(12 * s), y - int(2 * s)), "Reflection",
                  fill=self._rgb("orange"), font=tag_font)
        mw = draw.textlength(mirrored, font=big_font)
        draw.text((mx2 + (box_w - mw) / 2, y + (box_h - big_font.size) / 2),
                  mirrored, fill=self._rgb("orange"), font=big_font)

        return y + box_h + int(40 * s)

    def _draw_clock_angle(self, draw, frame, element, y):
        """Clock face with calculated angle between hands.

        JSON: { "target": "clock_angle",
                "hour": 3, "minute": 30,
                "angle": 75,
                "label": "Angle = 75°" }
        """
        hour = element.get("hour", 12)
        minute = element.get("minute", 0)
        angle_val = element.get("angle", 0)
        label_text = element.get("label", "")
        s = self.scale

        radius = int(130 * s)
        cx_c = self.content_x + self.content_w // 2
        cy_c = y + radius + int(30 * s)
        num_font = _get_font(int(24 * s), bold=True)
        lbl_font = _get_font(int(36 * s), bold=True)

        # Clock face
        draw.ellipse([cx_c - radius, cy_c - radius, cx_c + radius, cy_c + radius],
                     fill=(255, 255, 255), outline=(60, 60, 100), width=int(3 * s))

        # Hour marks and numbers
        for i in range(1, 13):
            angle = math.radians(i * 30 - 90)
            # Tick mark
            tx1 = cx_c + int((radius - int(12 * s)) * math.cos(angle))
            ty1 = cy_c + int((radius - int(12 * s)) * math.sin(angle))
            tx2 = cx_c + int((radius - int(4 * s)) * math.cos(angle))
            ty2 = cy_c + int((radius - int(4 * s)) * math.sin(angle))
            draw.line([tx1, ty1, tx2, ty2], fill=(60, 60, 100), width=int(2 * s))
            # Number
            nx = cx_c + int((radius - int(30 * s)) * math.cos(angle))
            ny = cy_c + int((radius - int(30 * s)) * math.sin(angle))
            nstr = str(i)
            nw = draw.textlength(nstr, font=num_font)
            draw.text((nx - nw / 2, ny - num_font.size / 2), nstr,
                      fill=(60, 60, 100), font=num_font)

        # Hour hand
        h_angle = math.radians((hour % 12 + minute / 60) * 30 - 90)
        h_len = int(radius * 0.55)
        hx = cx_c + int(h_len * math.cos(h_angle))
        hy = cy_c + int(h_len * math.sin(h_angle))
        draw.line([cx_c, cy_c, hx, hy], fill=(26, 35, 126), width=int(5 * s))

        # Minute hand
        m_angle = math.radians(minute * 6 - 90)
        m_len = int(radius * 0.80)
        mx_h = cx_c + int(m_len * math.cos(m_angle))
        my_h = cy_c + int(m_len * math.sin(m_angle))
        draw.line([cx_c, cy_c, mx_h, my_h], fill=self._rgb("blue"), width=int(3 * s))

        # Center dot
        dot_r = int(6 * s)
        draw.ellipse([cx_c - dot_r, cy_c - dot_r, cx_c + dot_r, cy_c + dot_r],
                     fill=(26, 35, 126))

        # Angle arc between hands
        if angle_val > 0:
            arc_r = int(40 * s)
            start_deg = math.degrees(h_angle)
            end_deg = math.degrees(m_angle)
            draw.arc([cx_c - arc_r, cy_c - arc_r, cx_c + arc_r, cy_c + arc_r],
                     start_deg, end_deg, fill=self._rgb("orange"), width=int(3 * s))

        # Label
        if label_text:
            lw = draw.textlength(label_text, font=lbl_font)
            draw.text(((self.width - lw) / 2, cy_c + radius + int(16 * s)),
                      label_text, fill=self._rgb("orange"), font=lbl_font)

        return cy_c + radius + int(60 * s)

    def _draw_input_output(self, draw, frame, element, y):
        """Machine input-output reasoning table.

        JSON: { "target": "input_output",
                "heading": "Machine Input-Output",
                "steps": [
                    {"label": "Input", "values": ["25", "cat", "13", "dog", "8"]},
                    {"label": "Step 1", "values": ["8", "25", "cat", "13", "dog"]},
                    {"label": "Step 2", "values": ["8", "13", "25", "cat", "dog"]}
                ],
                "highlight_step": 2 }
        """
        heading = element.get("heading", "")
        steps = element.get("steps", [])
        highlight_step = element.get("highlight_step", -1)
        s = self.scale

        head_font = _get_font(int(38 * s), bold=True)
        lbl_font = _get_font(int(30 * s), bold=True)
        val_font = _get_font(int(28 * s))
        pad = int(20 * s)
        row_h = int(48 * s)
        lbl_w = int(100 * s)

        if heading:
            hw = draw.textlength(heading, font=head_font)
            draw.text(((self.width - hw) / 2, y), heading,
                      fill=self._rgb("note_text"), font=head_font)
            y += int(48 * s)

        cx = self.content_x + pad
        max_vals = max((len(st.get("values", [])) for st in steps), default=0)
        val_w = min(int(120 * s), (self.content_w - 2 * pad - lbl_w) // max(1, max_vals))

        for si, step in enumerate(steps):
            is_hl = (si == highlight_step)
            row_bg = (255, 243, 224) if is_hl else \
                     (248, 248, 255) if si % 2 == 0 else (255, 255, 255)
            draw.rectangle([cx, y, cx + self.content_w - 2 * pad, y + row_h], fill=row_bg)

            # Label
            lbl = step.get("label", f"Step {si}")
            draw.text((cx + int(8 * s), y + int(10 * s)), lbl,
                      fill=self._rgb("blue"), font=lbl_font)

            # Values
            for vi, val in enumerate(step.get("values", [])):
                vx = cx + lbl_w + vi * val_w
                vw = draw.textlength(str(val), font=val_font)
                draw.text((vx + (val_w - vw) / 2, y + int(12 * s)),
                          str(val), fill=self._rgb("body_text"), font=val_font)
            y += row_h

        return y + int(12 * s)

    def _draw_cube_visual(self, draw, frame, element, y):
        """Painted cube / dice unfolding — reasoning.

        JSON: { "target": "cube_visual",
                "faces": ["R", "B", "G", "Y", "W", "O"],
                "label": "Painted Cube",
                "highlight_faces": [0, 2] }
        """
        faces = element.get("faces", ["1", "2", "3", "4", "5", "6"])
        label_text = element.get("label", "")
        highlight_faces = set(element.get("highlight_faces", []))
        s = self.scale

        lbl_font = _get_font(int(36 * s), bold=True)
        face_font = _get_font(int(32 * s), bold=True)
        cell = int(64 * s)
        gap = int(2 * s)

        face_colors = {
            "R": (220, 50, 50), "B": (50, 100, 220), "G": (50, 180, 50),
            "Y": (230, 200, 30), "W": (240, 240, 240), "O": (239, 108, 0),
        }

        if label_text:
            lw = draw.textlength(label_text, font=lbl_font)
            draw.text(((self.width - lw) / 2, y), label_text,
                      fill=self._rgb("note_text"), font=lbl_font)
            y += int(48 * s)

        # Cross-shaped unfolding: [1] on top, [2][3][4][5] middle row, [6] bottom
        #     [0]
        # [1][2][3][4]
        #     [5]
        positions = [
            (1, 0),  # face 0: top
            (0, 1),  # face 1: left
            (1, 1),  # face 2: front
            (2, 1),  # face 3: right
            (3, 1),  # face 4: back
            (1, 2),  # face 5: bottom
        ]
        total_w = 4 * (cell + gap)
        total_h = 3 * (cell + gap)
        start_x = self.content_x + (self.content_w - total_w) // 2

        for i, (col, row) in enumerate(positions):
            if i >= len(faces):
                break
            fx = start_x + col * (cell + gap)
            fy = y + row * (cell + gap)
            face_val = str(faces[i])
            is_hl = i in highlight_faces

            bg = face_colors.get(face_val.upper(), (220, 220, 230))
            if is_hl:
                outline = self._rgb("orange")
                outline_w = int(4 * s)
            else:
                outline = (180, 180, 200)
                outline_w = int(2 * s)

            draw.rounded_rectangle(
                [fx, fy, fx + cell, fy + cell],
                radius=int(4 * s), fill=bg, outline=outline, width=outline_w,
            )
            # Face label
            fw_t = draw.textlength(face_val, font=face_font)
            fc = (255, 255, 255) if sum(bg) < 500 else (30, 30, 60)
            draw.text((fx + (cell - fw_t) / 2, fy + (cell - face_font.size) / 2),
                      face_val, fill=fc, font=face_font)

        return y + total_h + int(20 * s)

    def _draw_place_value(self, draw, frame, element, y):
        """Place value chart — math number system.

        JSON: { "target": "place_value",
                "number": "34567",
                "places": ["Ten-Thousands", "Thousands", "Hundreds", "Tens", "Ones"],
                "highlight_place": 2 }
        """
        number = str(element.get("number", ""))
        places = element.get("places", [])
        highlight_place = element.get("highlight_place", -1)
        s = self.scale

        if not places:
            place_names = ["Ten-Thousands", "Thousands", "Hundreds", "Tens", "Ones"]
            places = place_names[max(0, 5 - len(number)):]

        head_font = _get_font(int(26 * s), bold=True)
        digit_font = _get_font(int(52 * s), bold=True)
        val_font = _get_font(int(24 * s))
        pad = int(16 * s)
        cell_w = min(int(160 * s), (self.content_w - pad * 2) // max(1, len(number)))
        cell_h = int(110 * s)
        total_w = len(number) * cell_w
        start_x = self.content_x + (self.content_w - total_w) // 2

        for i, digit in enumerate(number):
            cx = start_x + i * cell_w
            is_hl = (i == highlight_place)
            bg = (255, 243, 224) if is_hl else self._rgb("concept_blue_bg")
            border = self._rgb("orange") if is_hl else self._rgb("blue")
            fg = self._rgb("orange") if is_hl else self._rgb("blue")

            draw.rounded_rectangle(
                [cx + 2, y, cx + cell_w - 2, y + cell_h],
                radius=int(8 * s), fill=bg, outline=border, width=int(2 * s),
            )
            # Place name at top
            if i < len(places):
                pw = draw.textlength(places[i], font=head_font)
                draw.text((cx + (cell_w - pw) / 2, y + int(6 * s)),
                          places[i], fill=border, font=head_font)
            # Big digit
            dw = draw.textlength(digit, font=digit_font)
            draw.text((cx + (cell_w - dw) / 2, y + int(34 * s)),
                      digit, fill=fg, font=digit_font)
            # Place value
            place_val = int(digit) * (10 ** (len(number) - 1 - i))
            pv_str = f"= {place_val:,}"
            pvw = draw.textlength(pv_str, font=val_font)
            draw.text((cx + (cell_w - pvw) / 2, y + int(86 * s)),
                      pv_str, fill=self._rgb("body_secondary"), font=val_font)

        return y + cell_h + int(20 * s)

    def _draw_spectrum_band(self, draw, frame, element, y):
        """Electromagnetic / visible light spectrum band — physics.

        JSON: { "target": "spectrum_band",
                "type": "visible|em",
                "highlight": "green",
                "label": "Visible Light Spectrum" }
        """
        spec_type = element.get("type", "visible")
        highlight = element.get("highlight", "")
        label_text = element.get("label", "")
        s = self.scale

        lbl_font = _get_font(int(36 * s), bold=True)
        tag_font = _get_font(int(22 * s))

        if label_text:
            lw = draw.textlength(label_text, font=lbl_font)
            draw.text(((self.width - lw) / 2, y), label_text,
                      fill=self._rgb("note_text"), font=lbl_font)
            y += int(48 * s)

        bar_h = int(60 * s)
        cx = self.content_x + int(40 * s)
        bar_w = self.content_w - int(80 * s)

        if spec_type == "visible":
            colors = [
                ("Violet", (148, 0, 211)), ("Indigo", (75, 0, 130)),
                ("Blue", (0, 0, 255)), ("Green", (0, 128, 0)),
                ("Yellow", (255, 255, 0)), ("Orange", (255, 165, 0)),
                ("Red", (255, 0, 0)),
            ]
        else:
            colors = [
                ("Gamma", (80, 0, 120)), ("X-ray", (120, 0, 180)),
                ("UV", (148, 0, 211)), ("Visible", (0, 200, 0)),
                ("IR", (200, 50, 0)), ("Micro", (180, 100, 0)),
                ("Radio", (150, 150, 0)),
            ]

        n = len(colors)
        seg_w = bar_w // n

        for i, (name, rgb) in enumerate(colors):
            sx = cx + i * seg_w
            is_hl = highlight.lower() in name.lower()

            draw.rectangle([sx, y, sx + seg_w, y + bar_h], fill=rgb)
            if is_hl:
                draw.rectangle([sx, y, sx + seg_w, y + bar_h],
                               outline=(255, 255, 255), width=int(4 * s))
                # Arrow below
                draw.polygon(
                    [(sx + seg_w // 2, y + bar_h + int(20 * s)),
                     (sx + seg_w // 2 - int(8 * s), y + bar_h + int(8 * s)),
                     (sx + seg_w // 2 + int(8 * s), y + bar_h + int(8 * s))],
                    fill=(255, 255, 255))

            # Label below
            tw = draw.textlength(name, font=tag_font)
            # Determine text color for readability
            fc = (255, 255, 255) if sum(rgb) < 350 else (30, 30, 60)
            draw.text((sx + (seg_w - tw) / 2, y + (bar_h - tag_font.size) / 2),
                      name, fill=fc, font=tag_font)

        return y + bar_h + int(30 * s)

    def _draw_ratio_bar(self, draw, frame, element, y):
        """Ratio comparison bars — math ratio & proportion.

        JSON: { "target": "ratio_bar",
                "items": [
                    {"label": "Boys", "value": 3, "color": "blue"},
                    {"label": "Girls", "value": 5, "color": "orange"}
                ],
                "label": "Ratio 3:5" }
        """
        items = element.get("items", [])
        label_text = element.get("label", "")
        s = self.scale

        lbl_font = _get_font(int(36 * s), bold=True)
        bar_font = _get_font(int(30 * s), bold=True)
        val_font = _get_font(int(28 * s))

        if label_text:
            lw = draw.textlength(label_text, font=lbl_font)
            draw.text(((self.width - lw) / 2, y), label_text,
                      fill=self._rgb("note_text"), font=lbl_font)
            y += int(48 * s)

        total = sum(it.get("value", 1) for it in items)
        bar_h = int(48 * s)
        bar_gap = int(20 * s)
        max_bar_w = self.content_w - int(200 * s)
        label_w = int(100 * s)
        cx = self.content_x + label_w + int(16 * s)

        for it in items:
            val = it.get("value", 1)
            name = it.get("label", "")
            color = it.get("color", "blue")
            accent = self._rgb(color if color in self.C else "blue")
            w = int(max_bar_w * val / max(1, total))

            # Label left
            draw.text((self.content_x + int(8 * s), y + (bar_h - bar_font.size) / 2),
                      name, fill=self._rgb("body_text"), font=bar_font)
            # Bar
            draw.rounded_rectangle(
                [cx, y, cx + w, y + bar_h],
                radius=int(6 * s), fill=accent,
            )
            # Value inside bar
            vstr = str(val)
            vw = draw.textlength(vstr, font=val_font)
            if vw < w - int(16 * s):
                draw.text((cx + w - vw - int(12 * s), y + (bar_h - val_font.size) / 2),
                          vstr, fill=(255, 255, 255), font=val_font)
            else:
                draw.text((cx + w + int(8 * s), y + (bar_h - val_font.size) / 2),
                          vstr, fill=accent, font=val_font)
            y += bar_h + bar_gap

        return y

    def _draw_percentage_bar(self, draw, frame, element, y):
        """Percentage strip visualization — math.

        JSON: { "target": "percentage_bar",
                "value": 65,
                "total": 100,
                "label": "65% Passed",
                "color": "green" }
        """
        value = element.get("value", 0)
        total = element.get("total", 100)
        label_text = element.get("label", "")
        color = element.get("color", "blue")
        s = self.scale

        accent = self._rgb(color if color in self.C else "blue")
        lbl_font = _get_font(int(36 * s), bold=True)
        pct_font = _get_font(int(48 * s), bold=True)
        tag_font = _get_font(int(28 * s))

        if label_text:
            lw = draw.textlength(label_text, font=lbl_font)
            draw.text(((self.width - lw) / 2, y), label_text,
                      fill=self._rgb("note_text"), font=lbl_font)
            y += int(48 * s)

        bar_h = int(40 * s)
        bar_x = self.content_x + int(60 * s)
        bar_w = self.content_w - int(120 * s)
        pct = min(value / max(1, total), 1.0)
        fill_w = int(bar_w * pct)

        # Background bar
        draw.rounded_rectangle(
            [bar_x, y, bar_x + bar_w, y + bar_h],
            radius=int(8 * s), fill=(230, 230, 235),
        )
        # Filled portion
        if fill_w > int(16 * s):
            draw.rounded_rectangle(
                [bar_x, y, bar_x + fill_w, y + bar_h],
                radius=int(8 * s), fill=accent,
            )

        # Percentage text centered
        pct_text = f"{int(pct * 100)}%"
        pw = draw.textlength(pct_text, font=pct_font)
        draw.text(((self.width - pw) / 2, y + bar_h + int(8 * s)),
                  pct_text, fill=accent, font=pct_font)

        # Min/max labels
        draw.text((bar_x, y + bar_h + int(8 * s)), "0", fill=self._rgb("body_secondary"), font=tag_font)
        tw = draw.textlength(str(total), font=tag_font)
        draw.text((bar_x + bar_w - tw, y + bar_h + int(8 * s)),
                  str(total), fill=self._rgb("body_secondary"), font=tag_font)

        return y + bar_h + int(70 * s)

    def _draw_odd_one_out(self, draw, frame, element, y):
        """Grid of items with odd one highlighted — reasoning.

        JSON: { "target": "odd_one_out",
                "items": ["Rose", "Lily", "Mango", "Tulip", "Daisy"],
                "odd_index": 2,
                "reason": "Mango is a fruit, rest are flowers" }
        """
        items = element.get("items", [])
        odd_index = element.get("odd_index", -1)
        reason = element.get("reason", "")
        s = self.scale

        item_font = _get_font(int(36 * s), bold=True)
        reason_font = _get_font(int(32 * s))
        pad = int(16 * s)
        chip_h = int(56 * s)
        chip_gap = int(14 * s)

        n = len(items)
        chip_w = min(int(200 * s), (self.content_w - (n - 1) * chip_gap) // max(1, n))
        total_w = n * chip_w + (n - 1) * chip_gap
        start_x = self.content_x + (self.content_w - total_w) // 2

        for i, item in enumerate(items):
            ix = start_x + i * (chip_w + chip_gap)
            is_odd = (i == odd_index)
            bg = (255, 235, 238) if is_odd else self._rgb("concept_blue_bg")
            border = self._rgb("fail") if is_odd else self._rgb("blue")
            fc = self._rgb("fail") if is_odd else self._rgb("blue")

            draw.rounded_rectangle(
                [ix, y, ix + chip_w, y + chip_h],
                radius=int(8 * s), fill=bg, outline=border, width=int(2 * s),
            )
            # Strike-through for odd
            tw = draw.textlength(item, font=item_font)
            tx = ix + (chip_w - tw) / 2
            ty = y + (chip_h - item_font.size) / 2
            draw.text((tx, ty), item, fill=fc, font=item_font)
            if is_odd:
                draw.line([tx, ty + item_font.size // 2,
                           tx + tw, ty + item_font.size // 2],
                          fill=self._rgb("fail"), width=int(3 * s))

        y += chip_h + int(12 * s)

        if reason:
            rw = draw.textlength(reason, font=reason_font)
            draw.text(((self.width - rw) / 2, y), reason,
                      fill=self._rgb("body_secondary"), font=reason_font)
            y += int(40 * s)

        return y + pad

    def _draw_flashcard(self, draw, frame, element, y):
        """Front/back flashcard style — all subjects.

        JSON: { "target": "flashcard",
                "front": "What is the capital of France?",
                "back": "Paris",
                "revealed": true,
                "color": "blue" }
        """
        front = element.get("front", "")
        back = element.get("back", "")
        revealed = element.get("revealed", False)
        color = element.get("color", "blue")
        s = self.scale

        accent = self._rgb(color if color in self.C else "blue")
        q_font = _get_font(int(42 * s), bold=True)
        a_font = _get_font(int(48 * s), bold=True)
        tag_font = _get_font(int(26 * s), bold=True)
        pad_x = int(60 * s)
        pad_y = int(36 * s)
        cx = self.content_x

        max_w = self.content_w - 2 * pad_x
        q_lines = self._wrap_text(front, q_font, max_w)
        a_lines = self._wrap_text(back, a_font, max_w) if revealed else []
        line_h_q = int(q_font.size * 1.5)
        line_h_a = int(a_font.size * 1.5)
        card_h = len(q_lines) * line_h_q + (len(a_lines) * line_h_a if revealed else 0) + \
                 2 * pad_y + (int(50 * s) if revealed else 0)

        draw.rounded_rectangle(
            [cx, y, cx + self.content_w, y + card_h],
            radius=int(16 * s), fill=(255, 255, 255),
            outline=accent, width=int(3 * s),
        )

        cy = y + pad_y
        # "Q" badge
        draw.rounded_rectangle(
            [cx + pad_x, cy - int(4 * s), cx + pad_x + int(32 * s), cy + int(28 * s)],
            radius=int(4 * s), fill=accent,
        )
        draw.text((cx + pad_x + int(8 * s), cy), "Q",
                  fill=(255, 255, 255), font=tag_font)

        # Question text
        for line in q_lines:
            lw = draw.textlength(line, font=q_font)
            draw.text(((self.width - lw) / 2, cy), line,
                      fill=self._rgb("body_text"), font=q_font)
            cy += line_h_q

        if revealed:
            # Divider
            cy += int(12 * s)
            draw.line([cx + pad_x, cy, cx + self.content_w - pad_x, cy],
                      fill=accent, width=int(2 * s))
            cy += int(16 * s)

            # "A" badge
            draw.rounded_rectangle(
                [cx + pad_x, cy - int(4 * s), cx + pad_x + int(32 * s), cy + int(28 * s)],
                radius=int(4 * s), fill=self._rgb("success"),
            )
            draw.text((cx + pad_x + int(8 * s), cy), "A",
                      fill=(255, 255, 255), font=tag_font)

            for line in a_lines:
                lw = draw.textlength(line, font=a_font)
                draw.text(((self.width - lw) / 2, cy), line,
                          fill=self._rgb("success"), font=a_font)
                cy += line_h_a

        return y + card_h

    def _is_renderable(self, el):
        etype = el.get("type")
        if etype in ("image", "svg"):
            return bool(el.get("src_path")) and os.path.exists(el["src_path"])
        # subject_image and builtin_visual always attempt to render
        return True


# ---------------------------------------------------------------------------
# Standalone Thumbnail Generator
# ---------------------------------------------------------------------------

def generate_thumbnail(thumb_data, output_path, width=1280, height=720):
    """Generate a thumbnail matching the video's PPT style (dark header + white body).

    thumb_data keys:
      title      — bold heading in header  (e.g. "Number Theory")
      subtitle   — text below title        (e.g. "Divisibility Rules")
      badge      — exam tag                (e.g. "SSC | UPSC | Banking")
      topic      — body section label      (e.g. "Number Theory Shortcut")
      highlights — bullet points in body   (e.g. ["Rule of 9", "Rule of 11"])
    """
    img  = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    s    = width / 1280

    topic      = thumb_data.get("topic", "")
    badge      = thumb_data.get("badge", "")
    title      = thumb_data.get("title", "")
    subtitle   = thumb_data.get("subtitle", "")
    highlights = thumb_data.get("highlights", [])

    # ── HEADER (matches video: dark navy + orange stripe) ────────────────
    header_h     = int(180 * s)
    stripe_h     = int(6 * s)
    header_color = (26, 35, 126)   # #1A237E
    stripe_color = (239, 108, 0)   # #EF6C00

    draw.rectangle([0, 0, width, header_h], fill=header_color)
    draw.rectangle([0, header_h, width, header_h + stripe_h], fill=stripe_color)

    # Header: "Q:" label style — topic label
    pad_x = int(48 * s)
    label_f = _get_font(int(32 * s), bold=True)
    draw.text((pad_x, int(22 * s)), topic.upper() if topic else "",
              fill=(249, 168, 37), font=label_f)

    # Header: main title bold white
    title_f = _get_font(int(72 * s), bold=True)
    draw.text((pad_x, int(55 * s)), title, fill=(255, 255, 255), font=title_f)

    # ── BODY (white, like video body) ────────────────────────────────────
    body_top = header_h + stripe_h
    body_pad = int(55 * s)
    y = body_top + body_pad

    # Subtitle — orange, large
    sub_f = _get_font(int(58 * s), bold=True)
    draw.text((pad_x, y), subtitle, fill=(239, 108, 0), font=sub_f)
    y += int(sub_f.size * 1.3)

    # Divider
    draw.line([(pad_x, y), (width - pad_x, y)], fill=(200, 200, 200), width=int(2 * s))
    y += int(28 * s)

    # Highlights — dynamic layout
    # Available vertical space from y to badge area
    if highlights:
        col_colors = [(41, 98, 255), (239, 108, 0)]
        items      = highlights[:4]
        n          = len(items)
        badge_top  = height - int(60 * s)
        avail_h    = badge_top - y - int(20 * s)
        box_gap    = int(18 * s)
        total_gap  = box_gap * (n - 1)
        box_h      = max(int(70 * s), (avail_h - total_gap) // n)
        bul_f      = _get_font(min(int(52 * s), box_h - int(20 * s)), bold=True)
        box_w      = width - pad_x * 2

        for i, item in enumerate(items):
            by = y + i * (box_h + box_gap)
            bc = col_colors[i % len(col_colors)]
            draw.rounded_rectangle(
                [pad_x, by, pad_x + box_w, by + box_h],
                radius=int(14 * s), outline=bc, width=int(3 * s)
            )
            tw = draw.textlength(item, font=bul_f)
            draw.text((pad_x + (box_w - tw) // 2, by + (box_h - bul_f.size) // 2),
                      item, fill=bc, font=bul_f)

    # ── Badge (bottom-right corner) ───────────────────────────────────────
    if badge:
        bg_f  = _get_font(int(28 * s), bold=False)
        bg_h  = int(bg_f.size * 1.8)
        bg_y  = height - bg_h - int(25 * s)
        bw    = int(draw.textlength(badge, font=bg_f) + int(40 * s))
        bx    = width - bw - int(20 * s)
        draw.rounded_rectangle(
            [bx, bg_y, bx + bw, bg_y + bg_h],
            radius=int(8*s), fill=header_color
        )
        draw.text((bx + int(20*s), bg_y + int(bg_h * 0.12)),
                  badge, fill=(255, 255, 255), font=bg_f)

    img.save(output_path, "PNG")
    return output_path
