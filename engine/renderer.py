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

def _get_font(size=32, bold=False):
    font_names = []
    if bold:
        font_names += [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    font_names += [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/seguisym.ttf",   # Segoe UI Symbol — full Unicode/tick support
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ]
    for fname in font_names:
        if os.path.exists(fname):
            try:
                return ImageFont.truetype(fname, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _get_symbol_font(size=42):
    """Font guaranteed to render ✓ ✗ and other Unicode symbols."""
    for fname in [
        "C:/Windows/Fonts/seguisym.ttf",
        "C:/Windows/Fonts/seguiemj.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if os.path.exists(fname):
            try:
                return ImageFont.truetype(fname, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _get_math_font(size=36):
    font_names = [
        "C:/Windows/Fonts/cambria.ttc",
        "C:/Windows/Fonts/times.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ]
    for fname in font_names:
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
        """Render a frame — single consistent layout throughout the video.

        Always uses the compact dark header (question + options) with a white
        explanation body below. No separate full-screen intro mode.
        """
        frame = self.create_blank_frame()
        draw = ImageDraw.Draw(frame)
        elements = state.get("elements", [])

        # Separate elements
        question_el = None
        options_el = None
        work_elems = []

        for el in elements:
            etype = el.get("type")
            if etype == "question_block":
                question_el = el
            elif etype == "options_grid":
                options_el = el
            elif etype != "step_label":
                work_elems.append(el)

        work_elems = [el for el in work_elems if self._is_renderable(el)]

        # Always draw the compact header
        self._draw_header(draw, frame, question_el, options_el)

        # Karaoke strip: reserve bottom strip when narration word timestamps exist
        narration    = state.get("narration")
        current_time = state.get("current_time", 0)
        karaoke_h    = 0
        karaoke_gap  = 0
        if narration and narration.get("word_timestamps"):
            karaoke_h   = int(90 * self.scale)
            karaoke_gap = int(16 * self.scale)   # gap between body and strip

        if work_elems:

            # PPT body starts at y=259px (37px below header stripe)
            body_top    = int(259 * self.scale)
            body_bottom = self.height - int(30 * self.scale) - karaoke_h - karaoke_gap

            # Evenly distribute ALL available space — (n+1) slots so there's
            # equal padding above first element, between elements, and below last.
            heights = [self._estimate_height(el, draw) for el in work_elems]
            total_h = sum(heights)
            avail_h = body_bottom - body_top
            n = len(work_elems)
            slots = n + 1  # gaps: before first, between each, after last
            gap = int((avail_h - total_h) / slots) if avail_h > total_h else int(20 * self.scale)
            gap = max(gap, int(20 * self.scale))  # minimum comfortable gap

            y_work = body_top + gap  # leading gap before first element

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

        # Karaoke strip at bottom (with gap above it)
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
        pad_x = int(48 * s)
        pad_y = int(28 * s)
        max_w = self.content_w - 2 * pad_x
        lines = self._wrap_text(text, font, max_w)
        line_h = int(font.size * 1.35)
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

        head_font = _get_font(int(40 * s), bold=True)
        key_font  = _get_font(int(38 * s), bold=True)
        val_font  = _get_font(int(38 * s), bold=False)
        pad_x     = int(36 * s)
        pad_y     = int(20 * s)
        row_h     = int(key_font.size * 1.8)
        sep       = int(3 * s)
        head_h    = int(head_font.size * 1.5) if heading else 0
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

        head_font = _get_font(int(40 * s), bold=True)
        step_font = _get_font(int(38 * s), bold=False)
        num_font  = _get_font(int(36 * s), bold=True)
        pad_x     = int(36 * s)
        pad_y     = int(20 * s)
        num_r     = int(26 * s)          # circle radius
        line_h    = int(step_font.size * 1.6)
        head_h    = int(head_font.size * 1.5) if heading else 0
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
        head_f   = _get_font(int(40 * s), bold=True)
        body_f   = _get_font(int(36 * s), bold=False)
        pad_x    = int(28 * s)
        pad_y    = int(20 * s)
        line_h   = int(body_f.size * 1.5)
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
    def _draw_header(self, draw, frame, question_el, options_el):
        """Draw the dark navy header bar with question and options row."""
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
            return

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
            font = _get_font(int(44 * s))
            lines = self._wrap_text(element.get("text", ""), font,
                                    self.content_w - int(80 * s))
            return int(len(lines) * font.size * 1.4 + 56 * s)
        elif etype == "instruction_text":
            return int(110 * s)
        elif etype == "image":
            return int(self.height * 0.35)
        elif etype == "svg":
            return int(self.height * 0.3)
        elif etype == "table":
            rows = element.get("rows", [])
            return int((len(rows) + 1) * 64 * s + 20 * s)
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
        pad_x = int(40 * s)
        pad_y = int(20 * s)
        card_h = int(font.size * 1.3) + 2 * pad_y

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
        label_font = _get_font(int(20 * s), bold=True)
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
        font = _get_font(int(64 * s), bold=True)
        op_font = font  # operators same height as digits

        box_w = int(105 * s)
        box_h = int(115 * s)
        top_bar_h = int(6 * s)

        # Operator width — small breathing room around operator
        op_w = int(draw.textlength("+", font=op_font))
        op_gap = op_w + int(18 * s)  # operator + comfortable padding

        # Total width: boxes + tight operators between them
        total_w = len(digits) * box_w + max(0, len(digits) - 1) * op_gap
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

            # Digit text centered
            dtext = str(digit)
            tw = draw.textlength(dtext, font=font)
            draw.text(
                (x + (box_w - tw) / 2, y + top_bar_h + (box_h - top_bar_h - font.size) / 2),
                dtext, fill=text_color, font=font,
            )

            # Operator tight between boxes — centered vertically on box
            if i < len(digits) - 1:
                op_x = x + box_w + int(2 * s)
                op_y = y + (box_h - op_font.size) / 2
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
                    sep_w   = draw.textlength("   ", font=digit_font)
                    part_ws = [draw.textlength(p, font=digit_font) for p in _parts]
                    total_w = sum(part_ws) + sep_w * (len(_parts) - 1)
                    x = cx + (col_w - total_w) / 2
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
                    fx = cx + (col_w - _tfrac_w) / 2
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
                def _sum_block(cy, _st=stext):
                    stw = draw.textlength(_st, font=eq_font)
                    draw.text((cx + (col_w - stw) / 2, cy), _st, fill=bc, font=eq_font)
                blocks.append((_sum_block, eq_font.size))

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

        pad_x    = int(40 * s)
        pad_y    = int(22 * s)
        max_w    = self.content_w - 2 * pad_x
        line_gap = int(14 * s)

        head_font  = _get_font(int(44 * s), bold=True)
        body_font  = _get_font(int(40 * s), bold=False)
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
        """Step label — subtle gray text."""
        text = element.get("text", "")
        s = self.scale
        font = _get_font(int(22 * s))
        color = self._rgb("body_secondary")

        if len(text) > 80:
            text = text[:77] + "..."

        tw = draw.textlength(text, font=font)
        x = (self.width - tw) / 2
        draw.text((x, y), text, fill=color, font=font)

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

    def _is_renderable(self, el):
        etype = el.get("type")
        if etype in ("image", "svg"):
            return bool(el.get("src_path")) and os.path.exists(el["src_path"])
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
