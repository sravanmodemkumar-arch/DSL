"""
Manim Animation Renderer — Pre-built scene templates for educational videos.

Renders parameterized Manim scenes to PNG frame sequences, which are then
composited into video frames by the main FrameRenderer.

Architecture:
  1. Pipeline calls prerender_scene() during asset resolution
  2. Manim renders animation → MP4 → FFmpeg extracts PNG frames
  3. FrameRenderer reads cached PNGs at the correct animation progress

Graceful fallback: if Manim is not installed, returns None and the
FrameRenderer shows a text placeholder.

Scene templates cover Math, Physics, Chemistry — parameterized via JSON.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------
try:
    import manim
    MANIM_AVAILABLE = True
except ImportError:
    MANIM_AVAILABLE = False

# ---------------------------------------------------------------------------
# Cache directory
# ---------------------------------------------------------------------------
CACHE_DIR = Path("storage/cache/manim")


def _cache_key(scene_type, params, duration_s, fps):
    """Deterministic hash for a unique scene configuration."""
    blob = json.dumps({"t": scene_type, "p": params, "d": round(duration_s, 2),
                        "f": fps}, sort_keys=True)
    return hashlib.md5(blob.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def prerender_scene(scene_type, params, duration_s, fps=30,
                    width=1200, height=800, ffmpeg_path="ffmpeg"):
    """Pre-render a Manim scene to a directory of numbered PNGs.

    Returns (cache_dir: str, total_frames: int) on success.
    Returns (None, 0) if Manim is not installed or scene_type unknown.
    """
    if not MANIM_AVAILABLE:
        return None, 0

    key = _cache_key(scene_type, params, duration_s, fps)
    cache_path = CACHE_DIR / key
    count_file = cache_path / "_frame_count.txt"

    # Already cached?
    if cache_path.exists() and count_file.exists():
        try:
            total = int(count_file.read_text().strip())
            if total > 0:
                return str(cache_path), total
        except (ValueError, OSError):
            pass

    # Validate scene type
    builder = _SCENE_BUILDERS.get(scene_type)
    if not builder:
        return None, 0

    cache_path.mkdir(parents=True, exist_ok=True)
    tmp_media = cache_path / "_media"
    tmp_media.mkdir(exist_ok=True)

    try:
        # Build scene code dynamically
        code = builder(params, duration_s)

        # Write temp Python file
        script = cache_path / "_scene.py"
        script.write_text(code, encoding="utf-8")

        # Render with Manim CLI
        cmd = [
            "manim", "render",
            "-ql",                              # low quality (faster)
            "--fps", str(fps),
            "--pixel_width", str(width),
            "--pixel_height", str(height),
            "--media_dir", str(tmp_media),
            "--disable_caching",
            str(script),
            "GeneratedScene",
        ]
        subprocess.run(cmd, capture_output=True, timeout=120, check=True)

        # Find rendered video
        video = _find_video(tmp_media)
        if not video:
            return None, 0

        # Extract frames with FFmpeg
        total = _extract_frames(video, cache_path, fps, ffmpeg_path)
        if total > 0:
            count_file.write_text(str(total))
            # Cleanup Manim media artifacts
            shutil.rmtree(tmp_media, ignore_errors=True)
            script.unlink(missing_ok=True)
            return str(cache_path), total

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        pass

    # Cleanup on failure
    shutil.rmtree(cache_path, ignore_errors=True)
    return None, 0


def get_frame_path(cache_dir, progress):
    """Get the PNG path for a given animation progress (0.0 – 1.0).

    Returns the file path string, or None if not found.
    """
    if not cache_dir:
        return None
    try:
        count_file = Path(cache_dir) / "_frame_count.txt"
        total = int(count_file.read_text().strip())
    except (OSError, ValueError):
        return None
    if total <= 0:
        return None

    idx = max(0, min(int(progress * total), total - 1))
    path = os.path.join(cache_dir, f"frame_{idx:06d}.png")
    return path if os.path.exists(path) else None


# ═══════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _find_video(media_dir):
    """Locate the MP4 rendered by Manim somewhere under media_dir."""
    for root, _dirs, files in os.walk(str(media_dir)):
        for f in files:
            if f.endswith(".mp4"):
                return os.path.join(root, f)
    return None


def _extract_frames(video_path, output_dir, fps, ffmpeg_path="ffmpeg"):
    """Extract all frames from video to numbered PNGs. Returns frame count."""
    pattern = os.path.join(str(output_dir), "frame_%06d.png")
    cmd = [
        ffmpeg_path, "-y",
        "-i", video_path,
        "-vf", f"fps={fps}",
        pattern,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return 0

    count = len([f for f in os.listdir(str(output_dir))
                 if f.startswith("frame_") and f.endswith(".png")])
    return count


# ═══════════════════════════════════════════════════════════════════════════
# SCENE TEMPLATE BUILDERS
# Each returns a complete Python source string defining a Manim Scene.
# The scene class MUST be named 'GeneratedScene'.
# Params dict and duration_s are injected into the code.
# ═══════════════════════════════════════════════════════════════════════════

def _header():
    """Common imports for all Manim scene scripts."""
    return "from manim import *\nimport numpy as np\n\n"


# ---------------------------------------------------------------------------
# 1. FUNCTION PLOT — Animated function graphing
# Params: function (str), x_range, y_range, color, title, show_axes_labels
# ---------------------------------------------------------------------------
def _build_function_plot(params, dur):
    fn = params.get("function", "np.sin(x)")
    x_range = params.get("x_range", [-4, 4, 0.01])
    y_range = params.get("y_range", [-2, 2])
    color = params.get("color", "BLUE")
    title = params.get("title", "")
    xlabel = params.get("xlabel", "x")
    ylabel = params.get("ylabel", "y")
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        axes = Axes(
            x_range={x_range[:2] + [1]},
            y_range={y_range + [1]},
            x_length=10, y_length=6,
            axis_config={{"include_numbers": True}},
        )
        labels = axes.get_axis_labels(x_label="{xlabel}", y_label="{ylabel}")
        graph = axes.plot(lambda x: {fn}, color={color})
        title_text = Text("{title}", font_size=36).to_edge(UP) if "{title}" else VGroup()
        self.play(Create(axes), Write(labels), run_time={dur * 0.25:.2f})
        if "{title}":
            self.play(FadeIn(title_text), run_time={dur * 0.1:.2f})
        self.play(Create(graph), run_time={dur * 0.55:.2f})
        self.wait({dur * 0.1:.2f})
'''


# ---------------------------------------------------------------------------
# 2. MULTI FUNCTION — Plot multiple functions on same axes
# Params: functions [{expr, color, label}], x_range, y_range, title
# ---------------------------------------------------------------------------
def _build_multi_function(params, dur):
    functions = params.get("functions", [{"expr": "np.sin(x)", "color": "BLUE", "label": "sin(x)"}])
    x_range = params.get("x_range", [-4, 4])
    y_range = params.get("y_range", [-2, 2])
    title = params.get("title", "")
    n = len(functions)
    lines = []
    for i, f in enumerate(functions):
        lines.append(f'        g{i} = axes.plot(lambda x: {f["expr"]}, color={f.get("color", "BLUE")})')
        lines.append(f'        l{i} = axes.get_graph_label(g{i}, label="{f.get("label", "")}", x_val={x_range[1] - 0.5})')
    creates = ", ".join(f"Create(g{i}), FadeIn(l{i})" for i in range(n))
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        axes = Axes(
            x_range={x_range + [1]}, y_range={y_range + [1]},
            x_length=10, y_length=6,
            axis_config={{"include_numbers": True}},
        )
        labels = axes.get_axis_labels()
{chr(10).join(lines)}
        self.play(Create(axes), Write(labels), run_time={dur * 0.2:.2f})
        self.play({creates}, run_time={dur * 0.65:.2f})
        self.wait({dur * 0.15:.2f})
'''


# ---------------------------------------------------------------------------
# 3. DERIVATIVE — Tangent line sliding along a curve
# Params: function, x_range, color, tangent_color, x_values
# ---------------------------------------------------------------------------
def _build_derivative(params, dur):
    fn = params.get("function", "np.sin(x)")
    x_range = params.get("x_range", [-3, 3])
    color = params.get("color", "BLUE")
    tc = params.get("tangent_color", "YELLOW")
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        axes = Axes(x_range={x_range + [1]}, y_range=[-2, 2, 1],
                    x_length=10, y_length=6, axis_config={{"include_numbers": True}})
        labels = axes.get_axis_labels()
        graph = axes.plot(lambda x: {fn}, color={color})
        self.play(Create(axes), Write(labels), run_time={dur * 0.2:.2f})
        self.play(Create(graph), run_time={dur * 0.2:.2f})

        # Sliding tangent
        dot = Dot(color={tc})
        tangent = always_redraw(lambda: axes.get_secant_slope_group(
            x=dot.get_center()[0] / (10 / ({x_range[1]} - {x_range[0]})) + ({x_range[0]} + {x_range[1]}) / 2,
            graph=graph, dx=0.01, secant_line_length=3,
            secant_line_color={tc}
        ))
        dot.move_to(axes.c2p({x_range[0] + 0.5}, 0))
        self.play(Create(dot), Create(tangent), run_time={dur * 0.1:.2f})
        self.play(dot.animate.move_to(axes.c2p({x_range[1] - 0.5}, 0)),
                  run_time={dur * 0.4:.2f}, rate_func=linear)
        self.wait({dur * 0.1:.2f})
'''


# ---------------------------------------------------------------------------
# 4. INTEGRAL / AREA UNDER CURVE
# Params: function, x_range, area_range, color, area_color
# ---------------------------------------------------------------------------
def _build_integral(params, dur):
    fn = params.get("function", "0.5 * x**2")
    x_range = params.get("x_range", [-1, 4])
    area = params.get("area_range", [0, 3])
    color = params.get("color", "BLUE")
    ac = params.get("area_color", "BLUE")
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        axes = Axes(x_range={x_range + [1]}, y_range=[-1, 5, 1],
                    x_length=10, y_length=6, axis_config={{"include_numbers": True}})
        labels = axes.get_axis_labels()
        graph = axes.plot(lambda x: {fn}, color={color})
        area = axes.get_area(graph, x_range={area}, color={ac}, opacity=0.4)
        self.play(Create(axes), Write(labels), run_time={dur * 0.2:.2f})
        self.play(Create(graph), run_time={dur * 0.25:.2f})
        self.play(FadeIn(area), run_time={dur * 0.35:.2f})
        label = MathTex(r"\\int_{{{area[0]}}}^{{{area[1]}}} f(x)\\,dx", font_size=36).to_corner(UR)
        self.play(Write(label), run_time={dur * 0.15:.2f})
        self.wait({dur * 0.05:.2f})
'''


# ---------------------------------------------------------------------------
# 5. VECTOR ADDITION — Two vectors and their sum
# Params: v1, v2, colors, show_components
# ---------------------------------------------------------------------------
def _build_vector_addition(params, dur):
    v1 = params.get("v1", [2, 1, 0])
    v2 = params.get("v2", [1, 2, 0])
    c1 = params.get("color_1", "BLUE")
    c2 = params.get("color_2", "RED")
    cs = params.get("color_sum", "GREEN")
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        plane = NumberPlane(x_range=[-5, 5], y_range=[-4, 4])
        self.play(Create(plane), run_time={dur * 0.15:.2f})

        v1 = Arrow(ORIGIN, {v1}, buff=0, color={c1}, stroke_width=5)
        v2 = Arrow(ORIGIN, {v2}, buff=0, color={c2}, stroke_width=5)
        l1 = MathTex(r"\\vec{{a}}", color={c1}).next_to(v1, UP)
        l2 = MathTex(r"\\vec{{b}}", color={c2}).next_to(v2, RIGHT)
        self.play(GrowArrow(v1), Write(l1), run_time={dur * 0.15:.2f})
        self.play(GrowArrow(v2), Write(l2), run_time={dur * 0.15:.2f})

        v2_shifted = Arrow(np.array({v1}), np.array({v1}) + np.array({v2}),
                           buff=0, color={c2}, stroke_width=5)
        self.play(Transform(v2.copy(), v2_shifted), run_time={dur * 0.15:.2f})

        v_sum_end = (np.array({v1}) + np.array({v2})).tolist()
        v_sum = Arrow(ORIGIN, v_sum_end, buff=0, color={cs}, stroke_width=6)
        ls = MathTex(r"\\vec{{a}}+\\vec{{b}}", color={cs}).next_to(v_sum, RIGHT)
        self.play(GrowArrow(v_sum), Write(ls), run_time={dur * 0.2:.2f})
        self.wait({dur * 0.2:.2f})
'''


# ---------------------------------------------------------------------------
# 6. MATRIX TRANSFORM — 2D space transformation
# Params: matrix (2x2 list), title
# ---------------------------------------------------------------------------
def _build_matrix_transform(params, dur):
    matrix = params.get("matrix", [[2, 1], [0, 1]])
    title = params.get("title", "Linear Transformation")
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        plane = NumberPlane(x_range=[-5, 5], y_range=[-5, 5])
        title = Text("{title}", font_size=32).to_edge(UP)
        mat_tex = MathTex(r"\\begin{{bmatrix}} {matrix[0][0]} & {matrix[0][1]} \\\\ {matrix[1][0]} & {matrix[1][1]} \\end{{bmatrix}}", font_size=36).to_corner(UR)
        self.play(Create(plane), Write(title), Write(mat_tex), run_time={dur * 0.25:.2f})

        i_hat = Arrow(ORIGIN, RIGHT, buff=0, color=GREEN, stroke_width=5)
        j_hat = Arrow(ORIGIN, UP, buff=0, color=RED, stroke_width=5)
        self.play(GrowArrow(i_hat), GrowArrow(j_hat), run_time={dur * 0.15:.2f})

        matrix = {matrix}
        self.play(
            ApplyMatrix(matrix, plane),
            ApplyMatrix(matrix, i_hat),
            ApplyMatrix(matrix, j_hat),
            run_time={dur * 0.5:.2f}
        )
        self.wait({dur * 0.1:.2f})
'''


# ---------------------------------------------------------------------------
# 7. PYTHAGOREAN THEOREM — Visual proof
# Params: a, b (side lengths)
# ---------------------------------------------------------------------------
def _build_pythagorean(params, dur):
    a = params.get("a", 3)
    b = params.get("b", 4)
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        a, b = {a}, {b}
        c = np.sqrt(a**2 + b**2)
        # Right triangle
        tri = Polygon(ORIGIN, RIGHT * a, RIGHT * a + UP * b, color=WHITE, stroke_width=3)
        tri.move_to(ORIGIN)
        a_label = MathTex(f"a={a}").next_to(tri, DOWN)
        b_label = MathTex(f"b={b}").next_to(tri, RIGHT)
        c_label = MathTex(f"c={{c:.1f}}").move_to(tri.get_center() + LEFT * 0.8 + UP * 0.3)
        self.play(Create(tri), run_time={dur * 0.15:.2f})
        self.play(Write(a_label), Write(b_label), Write(c_label), run_time={dur * 0.1:.2f})

        # Squares on each side
        sq_a = Square(side_length=a, color=BLUE, fill_opacity=0.3).next_to(tri, DOWN, buff=0)
        sq_b = Square(side_length=b, color=RED, fill_opacity=0.3).next_to(tri, RIGHT, buff=0)
        sq_c = Square(side_length=c, color=GREEN, fill_opacity=0.3)
        sq_c.rotate(np.arctan(b/a)).move_to(tri.get_center() + LEFT * 2 + UP * 1.5)

        self.play(FadeIn(sq_a), run_time={dur * 0.15:.2f})
        self.play(FadeIn(sq_b), run_time={dur * 0.15:.2f})
        self.play(FadeIn(sq_c), run_time={dur * 0.15:.2f})

        formula = MathTex(f"a^2 + b^2 = c^2", font_size=42, color=YELLOW).to_edge(DOWN)
        self.play(Write(formula), run_time={dur * 0.1:.2f})
        self.wait({dur * 0.05:.2f})
'''


# ---------------------------------------------------------------------------
# 8. CIRCLE THEOREM — Inscribed angle, tangent, etc.
# Params: theorem (inscribed_angle | tangent | chord), show_labels
# ---------------------------------------------------------------------------
def _build_circle_theorem(params, dur):
    theorem = params.get("theorem", "inscribed_angle")
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        circle = Circle(radius=2.5, color=WHITE, stroke_width=2)
        center = Dot(ORIGIN, color=YELLOW)
        self.play(Create(circle), Create(center), run_time={dur * 0.15:.2f})

        if "{theorem}" == "inscribed_angle":
            A = circle.point_at_angle(0.3)
            B = circle.point_at_angle(2.0)
            C = circle.point_at_angle(4.5)
            arc = ArcBetweenPoints(A, B, angle=0, color=RED, stroke_width=4)
            central = Angle(Line(ORIGIN, A), Line(ORIGIN, B), radius=0.5, color=RED)
            inscribed = Angle(Line(C, A), Line(C, B), radius=0.5, color=BLUE)
            self.play(Create(Dot(A, color=RED)), Create(Dot(B, color=RED)),
                      Create(Dot(C, color=BLUE)), run_time={dur * 0.1:.2f})
            self.play(Create(Line(ORIGIN, A, color=RED)), Create(Line(ORIGIN, B, color=RED)),
                      Create(central), run_time={dur * 0.15:.2f})
            self.play(Create(Line(C, A, color=BLUE)), Create(Line(C, B, color=BLUE)),
                      Create(inscribed), run_time={dur * 0.15:.2f})
            label = MathTex(r"\\text{{Central}} = 2 \\times \\text{{Inscribed}}",
                           font_size=32, color=YELLOW).to_edge(DOWN)
            self.play(Write(label), run_time={dur * 0.15:.2f})
        elif "{theorem}" == "tangent":
            P = circle.point_at_angle(PI/4)
            tangent = Line(P + 2.5 * (P / np.linalg.norm(P)), P - 2.5 * (P / np.linalg.norm(P)),
                          color=GREEN, stroke_width=3).rotate(PI/2, about_point=P)
            radius_line = Line(ORIGIN, P, color=RED, stroke_width=3)
            right_angle = RightAngle(radius_line, tangent, length=0.3, color=YELLOW)
            self.play(Create(radius_line), run_time={dur * 0.15:.2f})
            self.play(Create(tangent), run_time={dur * 0.15:.2f})
            self.play(Create(right_angle), run_time={dur * 0.1:.2f})
            label = MathTex(r"\\text{{Tangent}} \\perp \\text{{Radius}}",
                           font_size=32, color=YELLOW).to_edge(DOWN)
            self.play(Write(label), run_time={dur * 0.15:.2f})
        self.wait({dur * 0.15:.2f})
'''


# ---------------------------------------------------------------------------
# 9. WAVE PROPAGATION — Transverse / longitudinal wave animation
# Params: wave_type (transverse|longitudinal), wavelength, amplitude, speed
# ---------------------------------------------------------------------------
def _build_wave(params, dur):
    wtype = params.get("wave_type", "transverse")
    amp = params.get("amplitude", 1.5)
    wl = params.get("wavelength", 2)
    title = params.get("title", "Wave Propagation")
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        title = Text("{title}", font_size=32).to_edge(UP)
        self.play(Write(title), run_time={dur * 0.1:.2f})
        axes = Axes(x_range=[0, 10, 1], y_range=[-2.5, 2.5, 1],
                    x_length=10, y_length=5, axis_config={{"include_numbers": True}})
        xl = axes.get_x_axis_label("x")
        yl = axes.get_y_axis_label("y")
        self.play(Create(axes), Write(xl), Write(yl), run_time={dur * 0.15:.2f})

        t_tracker = ValueTracker(0)
        wave = always_redraw(lambda: axes.plot(
            lambda x: {amp} * np.sin(2 * PI / {wl} * (x - t_tracker.get_value())),
            color=BLUE, stroke_width=3
        ))
        self.play(Create(wave), run_time={dur * 0.1:.2f})

        # Animate wave moving
        amp_line = DoubleArrow(axes.c2p(1, 0), axes.c2p(1, {amp}), color=YELLOW, buff=0)
        amp_label = MathTex(r"A = {amp}", font_size=28, color=YELLOW).next_to(amp_line, RIGHT)
        wl_line = DoubleArrow(axes.c2p(0, -{amp} - 0.3), axes.c2p({wl}, -{amp} - 0.3),
                              color=RED, buff=0)
        wl_label = MathTex(r"\\lambda = {wl}", font_size=28, color=RED).next_to(wl_line, DOWN)
        self.play(GrowArrow(amp_line), Write(amp_label),
                  GrowArrow(wl_line), Write(wl_label), run_time={dur * 0.15:.2f})
        self.play(t_tracker.animate.set_value(4), run_time={dur * 0.4:.2f}, rate_func=linear)
        self.wait({dur * 0.1:.2f})
'''


# ---------------------------------------------------------------------------
# 10. PROJECTILE MOTION — Parabolic trajectory
# Params: v0, angle, g, show_components
# ---------------------------------------------------------------------------
def _build_projectile(params, dur):
    v0 = params.get("v0", 10)
    angle = params.get("angle", 45)
    g = params.get("g", 9.8)
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        v0, angle_deg, g = {v0}, {angle}, {g}
        angle_rad = angle_deg * PI / 180
        t_flight = 2 * v0 * np.sin(angle_rad) / g
        x_max = v0 * np.cos(angle_rad) * t_flight
        y_max = (v0 * np.sin(angle_rad))**2 / (2 * g)

        axes = Axes(x_range=[0, x_max * 1.2, x_max / 5],
                    y_range=[0, y_max * 1.4, y_max / 3],
                    x_length=10, y_length=5.5,
                    axis_config={{"include_numbers": True}})
        labels = axes.get_axis_labels(x_label="x (m)", y_label="y (m)")
        self.play(Create(axes), Write(labels), run_time={dur * 0.15:.2f})

        path = axes.plot_parametric_curve(
            lambda t: np.array([v0 * np.cos(angle_rad) * t,
                                v0 * np.sin(angle_rad) * t - 0.5 * g * t**2, 0]),
            t_range=[0, t_flight], color=YELLOW, stroke_width=3
        )
        self.play(Create(path), run_time={dur * 0.35:.2f})

        # Ball tracing the path
        ball = Dot(color=RED, radius=0.12)
        ball.move_to(axes.c2p(0, 0))
        self.play(MoveAlongPath(ball, path), run_time={dur * 0.3:.2f})

        info = VGroup(
            MathTex(f"v_0 = {v0}\\\\, m/s", font_size=28),
            MathTex(f"\\\\theta = {angle_deg}^\\circ", font_size=28),
            MathTex(f"R = {{x_max:.1f}}\\\\, m", font_size=28),
            MathTex(f"H = {{y_max:.1f}}\\\\, m", font_size=28),
        ).arrange(DOWN, aligned_edge=LEFT).to_corner(UR).scale(0.8)
        self.play(Write(info), run_time={dur * 0.15:.2f})
        self.wait({dur * 0.05:.2f})
'''


# ---------------------------------------------------------------------------
# 11. PENDULUM MOTION — Simple harmonic motion
# Params: length, amplitude_deg, show_energy
# ---------------------------------------------------------------------------
def _build_pendulum(params, dur):
    length = params.get("length", 3)
    amp = params.get("amplitude_deg", 30)
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        pivot = UP * 3
        L = {length}
        amp_rad = {amp} * PI / 180

        support = Line(LEFT * 2 + UP * 3, RIGHT * 2 + UP * 3, color=GREY, stroke_width=4)
        self.play(Create(support), run_time={dur * 0.05:.2f})

        theta = ValueTracker(amp_rad)
        rod = always_redraw(lambda: Line(
            pivot,
            pivot + L * np.array([np.sin(theta.get_value()), -np.cos(theta.get_value()), 0]),
            color=WHITE, stroke_width=3
        ))
        bob = always_redraw(lambda: Dot(
            pivot + L * np.array([np.sin(theta.get_value()), -np.cos(theta.get_value()), 0]),
            color=RED, radius=0.15
        ))
        arc = always_redraw(lambda: Arc(
            start_angle=-PI/2 - amp_rad, angle=2 * amp_rad,
            radius=0.8, arc_center=pivot, color=YELLOW
        ))
        self.play(Create(rod), Create(bob), Create(arc), run_time={dur * 0.1:.2f})

        # Oscillate 3 times
        cycle_time = {dur * 0.75:.2f} / 6
        for _ in range(3):
            self.play(theta.animate.set_value(-amp_rad), run_time=cycle_time,
                      rate_func=there_and_back_with_pause)
            self.play(theta.animate.set_value(amp_rad), run_time=cycle_time,
                      rate_func=there_and_back_with_pause)
        self.wait({dur * 0.1:.2f})
'''


# ---------------------------------------------------------------------------
# 12. ELECTRIC FIELD — Field lines around charges
# Params: charges [{q, pos}], field_type (point|dipole|parallel_plate)
# ---------------------------------------------------------------------------
def _build_electric_field(params, dur):
    field_type = params.get("field_type", "dipole")
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        if "{field_type}" == "dipole":
            pos_charge = Dot(LEFT * 2, color=RED, radius=0.25)
            neg_charge = Dot(RIGHT * 2, color=BLUE, radius=0.25)
            plus = MathTex("+", color=WHITE, font_size=28).move_to(pos_charge)
            minus = MathTex("-", color=WHITE, font_size=28).move_to(neg_charge)
            self.play(Create(pos_charge), Create(neg_charge),
                      Write(plus), Write(minus), run_time={dur * 0.15:.2f})

            # Field lines
            lines = VGroup()
            for angle in np.linspace(-PI/3, PI/3, 8):
                start = LEFT * 2 + 0.3 * np.array([np.cos(angle), np.sin(angle), 0])
                end = RIGHT * 2 - 0.3 * np.array([np.cos(angle), np.sin(angle), 0])
                mid_y = 2.5 * np.sin(angle)
                pts = [start, start/2 + UP * mid_y, end/2 + UP * mid_y, end]
                line = CubicBezier(*pts, color=YELLOW, stroke_width=1.5)
                arrow = Arrow(pts[-2], end, buff=0, color=YELLOW, stroke_width=1.5,
                             max_tip_length_to_length_ratio=0.15)
                lines.add(line, arrow)
            self.play(Create(lines), run_time={dur * 0.5:.2f})
            label = MathTex(r"\\vec{{E}}", font_size=36, color=YELLOW).to_edge(DOWN)
            self.play(Write(label), run_time={dur * 0.1:.2f})
        elif "{field_type}" == "point":
            charge = Dot(ORIGIN, color=RED, radius=0.3)
            plus = MathTex("+q", color=WHITE, font_size=24).move_to(charge)
            self.play(Create(charge), Write(plus), run_time={dur * 0.1:.2f})
            lines = VGroup()
            for angle in np.linspace(0, 2 * PI, 12, endpoint=False):
                direction = np.array([np.cos(angle), np.sin(angle), 0])
                arrow = Arrow(0.4 * direction, 2.8 * direction, buff=0,
                             color=YELLOW, stroke_width=2)
                lines.add(arrow)
            self.play(Create(lines), run_time={dur * 0.5:.2f})
        self.wait({dur * 0.25:.2f})
'''


# ---------------------------------------------------------------------------
# 13. LENS RAY DIAGRAM — Convex / concave lens
# Params: lens_type (convex|concave), focal_length, object_distance
# ---------------------------------------------------------------------------
def _build_lens_ray(params, dur):
    lens_type = params.get("lens_type", "convex")
    f = params.get("focal_length", 2)
    u = params.get("object_distance", 4)
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        lens_type = "{lens_type}"
        f = {f}
        u = {u}
        v = (u * f) / (u - f) if u != f else 10

        # Principal axis
        axis = Line(LEFT * 6, RIGHT * 6, color=GREY, stroke_width=1)
        self.play(Create(axis), run_time={dur * 0.05:.2f})

        # Lens
        lens = Line(UP * 2.5, DOWN * 2.5, color=WHITE, stroke_width=3)
        f1 = Dot(LEFT * f, color=YELLOW, radius=0.08)
        f2 = Dot(RIGHT * f, color=YELLOW, radius=0.08)
        f1_label = MathTex("F", font_size=24).next_to(f1, DOWN)
        f2_label = MathTex("F'", font_size=24).next_to(f2, DOWN)
        self.play(Create(lens), Create(f1), Create(f2),
                  Write(f1_label), Write(f2_label), run_time={dur * 0.1:.2f})

        # Object
        obj_top = LEFT * u + UP * 1
        obj = Arrow(LEFT * u, obj_top, buff=0, color=GREEN, stroke_width=4)
        self.play(GrowArrow(obj), run_time={dur * 0.1:.2f})

        # Ray 1: parallel to axis → through F'
        r1a = Arrow(obj_top, UP * 1, buff=0, color=RED, stroke_width=2)
        r1_end = RIGHT * 5 + (RIGHT * 5 - RIGHT * f) * (-1 / f)
        r1b = Arrow(UP * 1, RIGHT * 5 + DOWN * (5 / f), buff=0, color=RED, stroke_width=2)
        self.play(GrowArrow(r1a), run_time={dur * 0.1:.2f})
        self.play(GrowArrow(r1b), run_time={dur * 0.1:.2f})

        # Ray 2: through center → straight
        r2 = Arrow(obj_top, RIGHT * 5 + DOWN * (5 / u), buff=0, color=BLUE, stroke_width=2)
        self.play(GrowArrow(r2), run_time={dur * 0.15:.2f})

        # Image
        img_h = -1 * v / u
        img = Arrow(RIGHT * v, RIGHT * v + DOWN * abs(img_h), buff=0,
                    color=ORANGE, stroke_width=4)
        self.play(GrowArrow(img), run_time={dur * 0.1:.2f})
        info = MathTex(f"u={u}, f={f}, v={{v:.1f}}", font_size=28).to_edge(DOWN)
        self.play(Write(info), run_time={dur * 0.1:.2f})
        self.wait({dur * 0.1:.2f})
'''


# ---------------------------------------------------------------------------
# 14. ENERGY DIAGRAM — Activation energy / enthalpy
# Params: reactant_e, product_e, activation_e, title, labels
# ---------------------------------------------------------------------------
def _build_energy_diagram(params, dur):
    re = params.get("reactant_energy", 50)
    pe = params.get("product_energy", 30)
    ae = params.get("activation_energy", 80)
    title = params.get("title", "Energy Profile")
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        axes = Axes(x_range=[0, 10, 2], y_range=[0, 100, 20],
                    x_length=8, y_length=5,
                    axis_config={{"include_numbers": True}})
        x_label = axes.get_x_axis_label("Reaction Progress")
        y_label = axes.get_y_axis_label("Energy (kJ)")
        title = Text("{title}", font_size=30).to_edge(UP)
        self.play(Create(axes), Write(x_label), Write(y_label),
                  Write(title), run_time={dur * 0.15:.2f})

        # Energy curve
        re, pe, ae = {re}, {pe}, {ae}
        curve = axes.plot(
            lambda x: re + (ae - re) * np.exp(-((x - 4)**2) / 2) + (pe - re) * (x / 10)
            if x < 10 else pe,
            x_range=[0, 9.5], color=YELLOW, stroke_width=3
        )
        self.play(Create(curve), run_time={dur * 0.25:.2f})

        # Labels
        r_line = DashedLine(axes.c2p(0, re), axes.c2p(3, re), color=BLUE)
        p_line = DashedLine(axes.c2p(7, pe), axes.c2p(10, pe), color=GREEN)
        a_line = DashedLine(axes.c2p(4, re), axes.c2p(4, ae), color=RED)
        r_label = Text("Reactants", font_size=22, color=BLUE).next_to(r_line, LEFT)
        p_label = Text("Products", font_size=22, color=GREEN).next_to(p_line, RIGHT)
        ea_label = MathTex(f"E_a = {ae - re}", font_size=26, color=RED).next_to(a_line, RIGHT)
        self.play(Create(r_line), Write(r_label), run_time={dur * 0.1:.2f})
        self.play(Create(p_line), Write(p_label), run_time={dur * 0.1:.2f})
        self.play(Create(a_line), Write(ea_label), run_time={dur * 0.1:.2f})

        dh = MathTex(f"\\Delta H = {pe - re}\\\\, kJ", font_size=28, color=ORANGE).to_corner(DR)
        self.play(Write(dh), run_time={dur * 0.1:.2f})
        self.wait({dur * 0.1:.2f})
'''


# ---------------------------------------------------------------------------
# 15. EQUATION TRANSFORM — Morph one equation into another
# Params: equations (list of LaTeX strings)
# ---------------------------------------------------------------------------
def _build_equation_transform(params, dur):
    equations = params.get("equations", [r"a^2 + b^2 = c^2", r"c = \\sqrt{a^2 + b^2}"])
    n = len(equations)
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        equations = {equations}
        step_time = {dur:.2f} / (len(equations) + 0.5)
        prev = MathTex(equations[0], font_size=52)
        self.play(Write(prev), run_time=step_time)
        for eq_str in equations[1:]:
            nxt = MathTex(eq_str, font_size=52)
            self.play(TransformMatchingShapes(prev, nxt), run_time=step_time)
            prev = nxt
        self.wait(step_time * 0.5)
'''


# ---------------------------------------------------------------------------
# 16. TEXT REVEAL — Animated text / bullet points appearing
# Params: lines (list of strings), title, style (write|fade|typewriter)
# ---------------------------------------------------------------------------
def _build_text_reveal(params, dur):
    lines = params.get("lines", ["Point 1", "Point 2", "Point 3"])
    title = params.get("title", "")
    color = params.get("color", "WHITE")
    n = len(lines)
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        items = VGroup()
        title_text = Text("{title}", font_size=36, color=YELLOW).to_edge(UP) if "{title}" else None
        if title_text:
            self.play(Write(title_text), run_time={dur * 0.15:.2f})

        lines = {lines}
        for i, line in enumerate(lines):
            bullet = Text(f"• {{line}}", font_size=28, color={color})
            items.add(bullet)
        items.arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        items.next_to(title_text if title_text else UP * 2, DOWN, buff=0.5)

        step_time = {dur * 0.7:.2f} / len(lines)
        for item in items:
            self.play(Write(item), run_time=step_time)
        self.wait({dur * 0.15:.2f})
'''


# ---------------------------------------------------------------------------
# 17. BAR CHART ANIMATED — Bars growing
# Params: values, labels, colors, title
# ---------------------------------------------------------------------------
def _build_bar_chart(params, dur):
    values = params.get("values", [3, 5, 2, 7, 4])
    labels = params.get("labels", None)
    title = params.get("title", "")
    colors = params.get("colors", ["BLUE", "RED", "GREEN", "YELLOW", "PURPLE"])
    if labels is None:
        labels = [str(i + 1) for i in range(len(values))]
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        values = {values}
        labels = {labels}
        colors = [{", ".join(colors[:len(values)])}]
        chart = BarChart(
            values, bar_names=labels,
            y_range=[0, max(values) + 2, max(1, max(values) // 5)],
            x_length=10, y_length=5.5,
            bar_colors=colors,
        )
        title = Text("{title}", font_size=32).to_edge(UP) if "{title}" else VGroup()
        self.play(Write(title), run_time={dur * 0.1:.2f})
        self.play(Create(chart), run_time={dur * 0.6:.2f})

        # Value labels on bars
        vals = VGroup()
        for i, bar in enumerate(chart.bars):
            v = Text(str(values[i]), font_size=22, color=WHITE)
            v.next_to(bar, UP, buff=0.1)
            vals.add(v)
        self.play(Write(vals), run_time={dur * 0.2:.2f})
        self.wait({dur * 0.1:.2f})
'''


# ---------------------------------------------------------------------------
# 18. NUMBER LINE WALK — Point moving along number line
# Params: start, end, operations [{op, value}]
# ---------------------------------------------------------------------------
def _build_number_line_walk(params, dur):
    start = params.get("start", 0)
    end = params.get("end", 10)
    operations = params.get("operations", [{"op": "+", "value": 3}, {"op": "+", "value": 2}])
    n = len(operations)
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        nl = NumberLine(x_range=[{start}, {end}, 1], length=10,
                        include_numbers=True, include_tip=True)
        self.play(Create(nl), run_time={dur * 0.15:.2f})

        pos = {start}
        dot = Dot(nl.n2p(pos), color=RED, radius=0.15)
        label = MathTex(str(pos), font_size=28, color=RED).next_to(dot, UP)
        self.play(Create(dot), Write(label), run_time={dur * 0.1:.2f})

        operations = {json.dumps(operations)}
        step_time = {dur * 0.6:.2f} / len(operations)
        for op in operations:
            val = op["value"]
            new_pos = pos + val if op["op"] == "+" else pos - val
            op_text = MathTex(f"{{op['op']}} {{val}}", font_size=26, color=YELLOW).next_to(dot, UP * 2)
            self.play(Write(op_text), run_time=step_time * 0.3)
            arc = ArcBetweenPoints(nl.n2p(pos), nl.n2p(new_pos),
                                   angle=PI/3 if val > 0 else -PI/3, color=YELLOW)
            self.play(Create(arc), run_time=step_time * 0.3)
            new_label = MathTex(str(new_pos), font_size=28, color=RED).next_to(nl.n2p(new_pos), UP)
            self.play(dot.animate.move_to(nl.n2p(new_pos)),
                      Transform(label, new_label),
                      FadeOut(op_text), FadeOut(arc),
                      run_time=step_time * 0.4)
            pos = new_pos
        self.wait({dur * 0.15:.2f})
'''


# ---------------------------------------------------------------------------
# 19. TRIG CIRCLE — Unit circle with sin/cos visualization
# Params: angle_range, show_sin, show_cos, show_tan
# ---------------------------------------------------------------------------
def _build_trig_circle(params, dur):
    show_sin = params.get("show_sin", True)
    show_cos = params.get("show_cos", True)
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        plane = NumberPlane(x_range=[-1.8, 1.8], y_range=[-1.8, 1.8],
                           x_length=6, y_length=6, background_line_style={{"stroke_opacity": 0.3}})
        circle = Circle(radius=plane.x_length / 3.6, color=WHITE, stroke_width=2)
        circle.move_to(plane.c2p(0, 0))
        self.play(Create(plane), Create(circle), run_time={dur * 0.15:.2f})

        theta = ValueTracker(0)
        radius_line = always_redraw(lambda: Line(
            plane.c2p(0, 0),
            plane.c2p(np.cos(theta.get_value()), np.sin(theta.get_value())),
            color=WHITE, stroke_width=3
        ))
        dot = always_redraw(lambda: Dot(
            plane.c2p(np.cos(theta.get_value()), np.sin(theta.get_value())),
            color=RED, radius=0.08
        ))

        sin_line = always_redraw(lambda: Line(
            plane.c2p(np.cos(theta.get_value()), 0),
            plane.c2p(np.cos(theta.get_value()), np.sin(theta.get_value())),
            color=BLUE, stroke_width=4
        )) if {show_sin} else VGroup()
        cos_line = always_redraw(lambda: Line(
            plane.c2p(0, 0),
            plane.c2p(np.cos(theta.get_value()), 0),
            color=GREEN, stroke_width=4
        )) if {show_cos} else VGroup()

        sin_label = always_redraw(lambda: MathTex(
            f"\\sin\\\\theta = {{np.sin(theta.get_value()):.2f}}",
            font_size=24, color=BLUE
        ).to_corner(UR)) if {show_sin} else VGroup()
        cos_label = always_redraw(lambda: MathTex(
            f"\\cos\\\\theta = {{np.cos(theta.get_value()):.2f}}",
            font_size=24, color=GREEN
        ).next_to(sin_label if {show_sin} else UP * 3, DOWN)) if {show_cos} else VGroup()

        self.play(Create(radius_line), Create(dot),
                  Create(sin_line), Create(cos_line),
                  Write(sin_label), Write(cos_label),
                  run_time={dur * 0.1:.2f})
        self.play(theta.animate.set_value(2 * PI),
                  run_time={dur * 0.65:.2f}, rate_func=linear)
        self.wait({dur * 0.1:.2f})
'''


# ---------------------------------------------------------------------------
# 20. GRAPH NETWORK — Tree / graph visualization
# Params: nodes [{id, label}], edges [{from, to}], directed, layout
# ---------------------------------------------------------------------------
def _build_graph_network(params, dur):
    nodes = params.get("nodes", [1, 2, 3, 4, 5])
    edges = params.get("edges", [(1, 2), (1, 3), (2, 4), (2, 5)])
    directed = params.get("directed", False)
    title = params.get("title", "")
    # Convert to tuples for Manim
    edge_tuples = [tuple(e) for e in edges]
    return _header() + f'''
class GeneratedScene(Scene):
    def construct(self):
        vertices = {nodes}
        edges = {edge_tuples}
        graph = Graph(vertices, edges,
                      layout="tree" if len(edges) < len(vertices) * 2 else "spring",
                      root_vertex={nodes[0]},
                      vertex_config={{"radius": 0.3, "fill_color": BLUE}},
                      edge_config={{"stroke_width": 2}})
        title = Text("{title}", font_size=32).to_edge(UP) if "{title}" else VGroup()
        self.play(Write(title), run_time={dur * 0.1:.2f})
        self.play(Create(graph), run_time={dur * 0.6:.2f})

        # Highlight nodes one by one
        step = {dur * 0.2:.2f} / max(len(vertices), 1)
        for v in vertices:
            self.play(graph[v].animate.set_fill(YELLOW), run_time=step)
            self.play(graph[v].animate.set_fill(BLUE), run_time=step * 0.3)
        self.wait({dur * 0.1:.2f})
'''


# ═══════════════════════════════════════════════════════════════════════════
# SCENE REGISTRY — maps scene_type string → builder function
# ═══════════════════════════════════════════════════════════════════════════

_SCENE_BUILDERS = {
    # Math
    "function_plot":       _build_function_plot,
    "multi_function":      _build_multi_function,
    "derivative":          _build_derivative,
    "integral":            _build_integral,
    "vector_addition":     _build_vector_addition,
    "matrix_transform":    _build_matrix_transform,
    "pythagorean":         _build_pythagorean,
    "circle_theorem":      _build_circle_theorem,
    "number_line_walk":    _build_number_line_walk,
    "trig_circle":         _build_trig_circle,
    "equation_transform":  _build_equation_transform,

    # Physics
    "wave":                _build_wave,
    "projectile":          _build_projectile,
    "pendulum":            _build_pendulum,
    "electric_field":      _build_electric_field,
    "lens_ray":            _build_lens_ray,

    # Chemistry
    "energy_diagram":      _build_energy_diagram,

    # General
    "text_reveal":         _build_text_reveal,
    "bar_chart_anim":      _build_bar_chart,
    "graph_network":       _build_graph_network,
}

# Public: list all available scene types
AVAILABLE_SCENES = list(_SCENE_BUILDERS.keys())
