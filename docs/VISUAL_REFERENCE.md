# Visual Reference

Complete reference for all visual elements available in the rendering engine.

---

## 6-Layer Visual System

| Layer | Source | Offline? | Install |
|-------|--------|----------|---------|
| `builtin_visual` | 74 Pillow-drawn diagrams | Yes | None |
| `subject_image` | Pixabay/Wikimedia/Pexels/Unsplash | No | API keys (optional) |
| `video_clip` | Pixabay/Pexels stock video | No | API keys (optional) |
| `matplotlib_plot` | Scientific graphs | Yes | `pip install matplotlib` |
| `rdkit_mol` | Molecular structures | Yes | `pip install rdkit` |
| `manim_scene` | 20 animated templates | Yes | `pip install manim` |

---

## Built-in Visuals (74)

### Biology (18)

| Visual | Description |
|--------|-------------|
| `cell` | Animal cell with nucleus, mitochondria, vacuole |
| `plant_cell` | Plant cell with cell wall, chloroplasts |
| `dna` | DNA double helix with base pairs |
| `leaf` | Leaf with veins and sunlight arrow |
| `food_chain` | Sun -> Grass -> Rabbit -> Fox chain |
| `heart` | 4-chamber heart with blood flow |
| `neuron` | Dendrites -> cell body -> axon -> terminal |
| `eye` | Eye cross-section with labeled parts |
| `blood_cells` | RBC, WBC, Platelet side by side |
| `mitosis` | 4 phases: Prophase, Metaphase, Anaphase, Telophase |
| `osmosis` | Membrane with water flow direction |
| `punnett_square` | 2x2 genetics grid |
| `ecosystem_pyramid` | Energy pyramid (4 levels) |
| `water_cycle` | Evaporation, condensation, precipitation |
| `nitrogen_cycle` | Circular nitrogen flow |
| `virus` | Icosahedral virus with spikes |
| `bacteria` | Rod bacterium with flagella |
| `digestive_system` | Mouth to intestines pathway |

### Physics (20)

| Visual | Description |
|--------|-------------|
| `atom` | Bohr model with 3 electron orbits |
| `circuit` | Series circuit with battery, resistor, bulb |
| `pendulum` | Pendulum with arc and velocity arrow |
| `optics` | Convex lens with ray diagram |
| `force` | Object with N, W, F, f force arrows |
| `wave` | Transverse wave with amplitude and wavelength |
| `concave_mirror` | Converging mirror with C, F points |
| `convex_mirror` | Diverging mirror with virtual focus |
| `bar_magnet` | N/S magnet with field lines |
| `solenoid` | Coil with magnetic field |
| `projectile` | Parabolic path with velocity components |
| `inclined_plane` | Ramp with force decomposition |
| `transformer` | Primary/secondary coils with iron core |
| `capacitor` | Parallel plates with E-field |
| `nuclear_fission` | U-235 splitting into fragments |
| `photoelectric` | Photon ejecting electron from metal |
| `circular_motion` | Circle with centripetal force |
| `pulley` | Fixed pulley with two masses |
| `pressure_column` | Fluid column with P=rho*g*h |
| `carnot_engine` | Hot/cold reservoirs with engine |

### Chemistry (12)

| Visual | Description |
|--------|-------------|
| `molecule` | CO2-style central + bonded atoms |
| `beaker` | Beaker with colored liquid |
| `periodic_element` | Element card (Fe, 26, Iron, 55.845) |
| `ph_scale` | pH 0-14 gradient bar |
| `electrolysis` | Container with anode/cathode |
| `galvanic_cell` | Zn-Cu cell with salt bridge |
| `bond_ionic` | Na+ and Cl- with attraction |
| `bond_covalent` | Overlapping atoms with shared cloud |
| `benzene` | Hexagonal ring C6H6 |
| `activation_energy` | Reaction energy hill |
| `test_tube` | Test tube with solution |
| `distillation` | Flask + condenser + collection |

### Math (10)

| Visual | Description |
|--------|-------------|
| `clock` | Analog clock with hour/minute hands |
| `venn_diagram` | Two overlapping circles |
| `coordinate_plane` | X-Y axes with quadrant labels |
| `pie_chart` | 4-sector pie chart |
| `bar_chart` | 4-bar chart with values |
| `triangle_parts` | Triangle with angles and sides labeled |
| `circle_parts` | Circle with radius, diameter, chord |
| `number_pattern` | Sequence boxes with +3 arrows |
| `fraction_visual` | Rectangle divided with shading (3/5) |
| `normal_distribution` | Bell curve with mu and sigma |

### Geography (4)

| Visual | Description |
|--------|-------------|
| `compass` | 8-point compass rose |
| `rock_cycle` | Igneous -> Sedimentary -> Metamorphic |
| `climate_zones` | Polar / Temperate / Tropical bands |
| `river_landforms` | Meander, delta, oxbow lake |

### Polity (2)

| Visual | Description |
|--------|-------------|
| `government_structure` | Legislature, Executive, Judiciary pillars |
| `parliament` | Rajya Sabha + Lok Sabha |

### Economics (2)

| Visual | Description |
|--------|-------------|
| `supply_demand` | Intersecting S and D curves |
| `production_possibility` | Concave PPF curve |

### Computer Science (6)

| Visual | Description |
|--------|-------------|
| `flowchart` | Start -> Process -> Decision -> End |
| `binary_tree` | 3-level tree with nodes |
| `stack_visual` | LIFO stack with push/pop |
| `queue_visual` | FIFO queue with In/Out |
| `array_visual` | Array boxes with indices 0-5 |
| `osi_layers` | 7-layer OSI model |

### Reasoning (3)

| Visual | Description |
|--------|-------------|
| `seating_circle` | Circular table with positions |
| `direction_sense` | 8-direction compass |
| `blood_relation` | Family tree diagram |

### Universal (6)

| Visual | Description |
|--------|-------------|
| `teacher` | Teacher figure with speech bubble |
| `comparison_table` | 2-column comparison |
| `steps_visual` | Numbered step boxes 1->2->3->4 |
| `lightbulb` | Lightbulb idea icon |
| `trophy` | Trophy cup (correct answer) |
| `timeline_visual` | Horizontal timeline |

### Usage

```json
{
  "action": "show",
  "target": "builtin_visual",
  "visual": "cell",
  "label": "Animal Cell",
  "color": "green"
}
```

Colors: `blue` | `green` | `orange` | `red` | `purple`

---

## Manim Animated Scenes (20)

### Math (11)

| Scene Type | Animation |
|-----------|-----------|
| `function_plot` | Function being traced on axes |
| `multi_function` | Multiple functions plotted together |
| `derivative` | Tangent line sliding along curve |
| `integral` | Area under curve being filled |
| `vector_addition` | Two vectors + resultant arrow |
| `matrix_transform` | 2D space transformation |
| `pythagorean` | Visual proof with squares on sides |
| `circle_theorem` | Inscribed angle / tangent theorem |
| `number_line_walk` | Point moving with operations |
| `trig_circle` | Unit circle with sin/cos projections |
| `equation_transform` | Equation morphing step by step |

### Physics (5)

| Scene Type | Animation |
|-----------|-----------|
| `wave` | Wave propagation (transverse/longitudinal) |
| `projectile` | Parabolic trajectory with components |
| `pendulum` | Simple harmonic oscillation |
| `electric_field` | Field lines (dipole/point charge) |
| `lens_ray` | Ray diagram through lens |

### Chemistry (1)

| Scene Type | Animation |
|-----------|-----------|
| `energy_diagram` | Reaction energy profile |

### General (3)

| Scene Type | Animation |
|-----------|-----------|
| `text_reveal` | Animated bullet points |
| `bar_chart_anim` | Bars growing |
| `graph_network` | Tree/graph visualization |

### Usage

```json
{
  "action": "show",
  "target": "manim_scene",
  "scene_type": "function_plot",
  "params": {
    "function": "np.sin(x)",
    "x_range": [-4, 4],
    "color": "BLUE",
    "title": "y = sin(x)"
  },
  "caption": "Sine function"
}
```

Manim colors: `BLUE`, `RED`, `GREEN`, `YELLOW`, `ORANGE`, `PURPLE`, `WHITE`, `TEAL`, `PINK`

---

## matplotlib Plots

Supported plot types: `line`, `bar`, `scatter`, `pie`, `histogram`

```json
{
  "action": "show",
  "target": "matplotlib_plot",
  "plot_type": "line",
  "title": "Velocity vs Time",
  "xlabel": "Time (s)",
  "ylabel": "Velocity (m/s)",
  "data": { "x": [0, 1, 2, 3, 4], "y": [0, 5, 10, 15, 20] },
  "color": "blue"
}
```

---

## RDKit Molecules

2D molecular structure from SMILES notation.

```json
{
  "action": "show",
  "target": "rdkit_mol",
  "smiles": "c1ccccc1",
  "name": "Benzene"
}
```

Common SMILES: `O` (water), `CCO` (ethanol), `c1ccccc1` (benzene), `CC(=O)O` (acetic acid)

---

## Free Media (Auto-fetched)

### Subject Image

```json
{
  "action": "show",
  "target": "subject_image",
  "query": "plant cell microscope biology",
  "subject": "biology",
  "topic": "cell",
  "caption": "Plant Cell"
}
```

Provider priority: Wikimedia (no key) -> Pixabay -> Pexels -> Unsplash

### Video Clip

```json
{
  "action": "show",
  "target": "video_clip",
  "query": "pendulum physics experiment",
  "subject": "physics",
  "caption": "Pendulum Demo"
}
```

---

## New Render Targets (Ultra-Pro)

### Option Analysis — Single-Screen Option Check

Shows one MCQ option tested against rules with working + verdict on ONE screen.

```json
{
  "action": "show",
  "target": "option_analysis",
  "option_key": "a",
  "option_value": "277218",
  "checks": [
    {"rule": "Rule of 9", "working": "2+7+7+2+1+8 = 27", "result": "27 ÷ 9 = 3", "pass": true},
    {"rule": "Rule of 11", "working": "+2−7+7−2+1−8 = −7", "result": "−7 ≠ 0 or ÷11", "pass": false}
  ],
  "verdict": "fail"
}
```

### Grid Check — Options × Criteria Matrix

Truth-table style grid with ✔/✘ for all options at once.

```json
{
  "action": "show",
  "target": "grid_check",
  "criteria": ["Rule of 9", "Rule of 11"],
  "options": [
    {"label": "A: 277218", "checks": [true, false]},
    {"label": "B: 10098",  "checks": [true, true]},
    {"label": "C: 12345",  "checks": [false, false]},
    {"label": "D: 181998", "checks": [true, false]}
  ],
  "correct_row": 1
}
```

### Bullet List

Bullet points with optional icon style and color.

```json
{
  "action": "show",
  "target": "bullet_list",
  "heading": "Key Points",
  "items": ["First point", "Second point", "Third point"],
  "icon": "bullet|check|arrow|star",
  "color": "blue"
}
```

### Definition Card — Term + Definition

```json
{
  "action": "show",
  "target": "definition_card",
  "term": "Osmosis",
  "definition": "Movement of water molecules through a semipermeable membrane from a region of lower solute concentration to higher.",
  "category": "Biology",
  "color": "green"
}
```

### Quote Block — Articles, Provisions, Famous Quotes

```json
{
  "action": "show",
  "target": "quote_block",
  "text": "We the people of India, having solemnly resolved to constitute India into a sovereign socialist secular democratic republic...",
  "source": "Preamble, Constitution of India",
  "color": "blue"
}
```

### Code Block — Syntax-Highlighted Code (CS)

```json
{
  "action": "show",
  "target": "code_block",
  "code": "def hello():\\n    print('Hello')\\n    return True",
  "language": "python",
  "highlight_lines": [2]
}
```

### Matrix — Mathematical Matrix

```json
{
  "action": "show",
  "target": "matrix",
  "label": "A",
  "rows": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
  "highlight_cells": [[0, 1], [1, 2]]
}
```

### Proof Steps — Formal Proof

```json
{
  "action": "show",
  "target": "proof_steps",
  "heading": "Proof: Triangle Congruence",
  "steps": [
    {"statement": "AB = CD", "reason": "Given"},
    {"statement": "∠A = ∠C", "reason": "Alternate interior angles"},
    {"statement": "△ABD ≅ △CDB", "reason": "SAS Congruence"}
  ]
}
```

### Equation Steps — Step-by-Step Solving

```json
{
  "action": "show",
  "target": "equation_steps",
  "heading": "Solving for x",
  "steps": ["2x + 5 = 15", "2x = 15 − 5", "2x = 10", "x = 5"],
  "highlight_step": 3
}
```

### Conversion Chain — Unit Conversion

```json
{
  "action": "show",
  "target": "conversion_chain",
  "steps": [
    {"value": "5 km", "operation": "× 1000"},
    {"value": "5000 m", "operation": "× 100"},
    {"value": "500000 cm"}
  ]
}
```

### Series Pattern — Number/Letter Series

```json
{
  "action": "show",
  "target": "series_pattern",
  "series": [2, 5, 10, 17, 26],
  "differences": ["+3", "+5", "+7", "+9"],
  "next": "?",
  "next_diff": "+11"
}
```

### Dice Visual — Probability

```json
{
  "action": "show",
  "target": "dice_visual",
  "faces": [1, 2, 3, 4, 5, 6],
  "highlight": [2, 4, 6],
  "label": "Even outcomes"
}
```

### Calendar Visual — Month Grid

```json
{
  "action": "show",
  "target": "calendar_visual",
  "month": "March",
  "year": 2026,
  "highlight_dates": [5, 15, 25],
  "start_day": 6,
  "days": 31
}
```

### Seating Arrangement — Reasoning

```json
{
  "action": "show",
  "target": "seating_arrangement",
  "layout": "circular",
  "seats": ["A", "B", "C", "D", "E", "F"],
  "highlight": ["B", "E"],
  "facing": "center"
}
```

Linear layout:

```json
{
  "action": "show",
  "target": "seating_arrangement",
  "layout": "linear",
  "seats": ["Ram", "Shyam", "Gita", "Priya"],
  "highlight": ["Gita"]
}
```

### Coding Decoding — Letter↔Number Mapping

```json
{
  "action": "show",
  "target": "coding_decoding",
  "heading": "Code Table",
  "mapping": {"A": "Z", "B": "Y", "C": "X", "D": "W", "E": "V"},
  "highlight_keys": ["B", "D"]
}
```

### Syllogism — Premises + Conclusion

```json
{
  "action": "show",
  "target": "syllogism",
  "premises": ["All dogs are animals", "All animals are living beings"],
  "conclusion": "All dogs are living beings",
  "valid": true
}
```

### Blood Relation Tree — Family Tree

```json
{
  "action": "show",
  "target": "blood_relation_tree",
  "members": [
    {"name": "Ram", "relation": "Father", "level": 0},
    {"name": "Sita", "relation": "Mother", "level": 0},
    {"name": "Arjun", "relation": "Son", "level": 1},
    {"name": "Priya", "relation": "Daughter", "level": 1}
  ],
  "highlight": ["Arjun"]
}
```

### Direction Diagram — Path Visualization

```json
{
  "action": "show",
  "target": "direction_diagram",
  "moves": [
    {"direction": "North", "distance": "5 km"},
    {"direction": "East", "distance": "3 km"},
    {"direction": "South", "distance": "2 km"}
  ],
  "start_label": "Home",
  "end_label": "Office"
}
```

### Ranking Order — Position Visualization

```json
{
  "action": "show",
  "target": "ranking_order",
  "heading": "Height Order (Tallest → Shortest)",
  "items": ["Ram", "Shyam", "Gita", "Priya", "Hari"],
  "highlight": ["Gita"],
  "numbered": true
}
```

### Amendment Card — Constitutional Articles (Polity)

```json
{
  "action": "show",
  "target": "amendment_card",
  "number": "Article 21",
  "title": "Right to Life",
  "description": "No person shall be deprived of his life or personal liberty except according to procedure established by law.",
  "category": "Fundamental Rights",
  "color": "blue"
}
```

### Person Card — Historical Figures / Scientists

```json
{
  "action": "show",
  "target": "person_card",
  "name": "Mahatma Gandhi",
  "title": "Father of the Nation",
  "facts": {"Born": "1869", "Died": "1948", "Known for": "Non-violence"},
  "image_url": "https://example.com/gandhi.jpg",
  "color": "orange"
}
```

### Stat Card — Big Number Statistics

```json
{
  "action": "show",
  "target": "stat_card",
  "stats": [
    {"label": "GDP Growth", "value": "7.2%", "color": "green"},
    {"label": "Inflation", "value": "4.5%", "color": "red"},
    {"label": "Fiscal Deficit", "value": "5.9%", "color": "orange"}
  ]
}
```

### Split Screen — Side-by-Side Comparison

```json
{
  "action": "show",
  "target": "split_screen",
  "left":  {"heading": "Before", "items": ["Old method", "Slower"], "color": "red"},
  "right": {"heading": "After",  "items": ["New method", "Faster"], "color": "green"}
}
```

---

## External Media (URL-based)

### Web Image — Direct URL

Downloads and displays an image from any URL.

```json
{
  "action": "show",
  "target": "web_image",
  "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/solar_system.jpg",
  "caption": "Solar System",
  "size": "medium"
}
```

Sizes: `small` | `medium` | `large`

### Web GIF — Animated GIF from URL

Downloads GIF, renders first frame as still in video.

```json
{
  "action": "show",
  "target": "web_gif",
  "url": "https://example.com/animation.gif",
  "caption": "Chemical Reaction"
}
```

### Web Video — Video Clip from URL

Downloads and embeds external video.

```json
{
  "action": "show",
  "target": "web_video",
  "url": "https://example.com/experiment.mp4",
  "caption": "Pendulum Experiment"
}
```

### Google Image — Auto-Search

Searches free image providers (Wikimedia, Pixabay, Pexels, Unsplash) and downloads best match.

```json
{
  "action": "show",
  "target": "google_image",
  "query": "mitochondria electron microscope",
  "caption": "Mitochondria",
  "size": "medium"
}
```

---

## Batch 2 — Exam-Specific Targets

### Truth Table — Boolean Logic

```json
{
  "action": "show",
  "target": "truth_table",
  "heading": "AND Gate",
  "variables": ["p", "q"],
  "expression": "p ∧ q",
  "rows": [[true,true,true],[true,false,false],[false,true,false],[false,false,false]],
  "highlight_row": 0
}
```

### Law Card — Named Scientific Law

```json
{
  "action": "show",
  "target": "law_card",
  "name": "Newton's Second Law",
  "formula": "F = ma",
  "statement": "Force equals mass times acceleration.",
  "units": "F in Newtons, m in kg, a in m/s²",
  "color": "blue"
}
```

### Tip Box — Exam Shortcut

```json
{
  "action": "show",
  "target": "tip_box",
  "title": "Quick Tip",
  "text": "To multiply any number by 11, write the digits and insert their sum in the middle.",
  "color": "green"
}
```

### Warning Box — Common Mistake

```json
{
  "action": "show",
  "target": "warning_box",
  "title": "Common Mistake",
  "text": "Students forget to check divisibility by 11 after passing rule of 9."
}
```

### Event Card — GK / History

```json
{
  "action": "show",
  "target": "event_card",
  "date": "15 August 1947",
  "title": "Indian Independence",
  "place": "New Delhi",
  "significance": "India gained freedom from British rule after 200 years of colonial oppression.",
  "color": "orange"
}
```

### Word Breakdown — English Vocabulary

```json
{
  "action": "show",
  "target": "word_breakdown",
  "word": "unhappiness",
  "parts": [
    {"text": "un-", "type": "prefix", "meaning": "not"},
    {"text": "happy", "type": "root", "meaning": "feeling joy"},
    {"text": "-ness", "type": "suffix", "meaning": "state of"}
  ]
}
```

### Fill Blank Sentence — English

```json
{
  "action": "show",
  "target": "fill_blank_sentence",
  "sentence": "The sun _____ in the east.",
  "answer": "rises",
  "revealed": true
}
```

### Venn Operations — Set Theory

```json
{
  "action": "show",
  "target": "venn_operations",
  "set_a": "A",
  "set_b": "B",
  "operation": "intersection",
  "label": "A ∩ B"
}
```

Operations: `intersection` | `union` | `a_minus_b` | `b_minus_a` | `complement`

### Mirror Image — Non-verbal Reasoning

```json
{
  "action": "show",
  "target": "mirror_image",
  "original": "AMBULANCE",
  "mirrored": "ECNALUBMA",
  "mirror_type": "vertical",
  "label": "Mirror Image"
}
```

### Clock Angle — Reasoning

```json
{
  "action": "show",
  "target": "clock_angle",
  "hour": 3,
  "minute": 30,
  "angle": 75,
  "label": "Angle = 75°"
}
```

### Input Output — Machine Reasoning

```json
{
  "action": "show",
  "target": "input_output",
  "heading": "Machine Input-Output",
  "steps": [
    {"label": "Input",  "values": ["25", "cat", "13", "dog", "8"]},
    {"label": "Step 1", "values": ["8", "25", "cat", "13", "dog"]},
    {"label": "Step 2", "values": ["8", "13", "25", "cat", "dog"]}
  ],
  "highlight_step": 2
}
```

### Cube Visual — Painted Cube

```json
{
  "action": "show",
  "target": "cube_visual",
  "faces": ["R", "B", "G", "Y", "W", "O"],
  "label": "Painted Cube — Unfolded",
  "highlight_faces": [0, 2]
}
```

### Place Value — Number System

```json
{
  "action": "show",
  "target": "place_value",
  "number": "34567",
  "places": ["Ten-Thousands", "Thousands", "Hundreds", "Tens", "Ones"],
  "highlight_place": 2
}
```

### Spectrum Band — EM / Visible Light

```json
{
  "action": "show",
  "target": "spectrum_band",
  "type": "visible",
  "highlight": "green",
  "label": "Visible Light Spectrum"
}
```

Types: `visible` | `em`

### Ratio Bar — Ratio & Proportion

```json
{
  "action": "show",
  "target": "ratio_bar",
  "items": [
    {"label": "Boys", "value": 3, "color": "blue"},
    {"label": "Girls", "value": 5, "color": "orange"}
  ],
  "label": "Ratio 3:5"
}
```

### Percentage Bar — Percentage Strip

```json
{
  "action": "show",
  "target": "percentage_bar",
  "value": 65,
  "total": 100,
  "label": "65% Students Passed",
  "color": "green"
}
```

### Odd One Out — Reasoning

```json
{
  "action": "show",
  "target": "odd_one_out",
  "items": ["Rose", "Lily", "Mango", "Tulip", "Daisy"],
  "odd_index": 2,
  "reason": "Mango is a fruit, rest are flowers"
}
```

### Flashcard — All Subjects

```json
{
  "action": "show",
  "target": "flashcard",
  "front": "What is the capital of France?",
  "back": "Paris",
  "revealed": true,
  "color": "blue"
}
```
