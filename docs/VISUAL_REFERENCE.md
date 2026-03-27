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
