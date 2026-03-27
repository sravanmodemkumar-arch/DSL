# UNIVERSAL JSON-DRIVEN STEM VIDEO GENERATION SYSTEM (ULTRA-DETAILED MASTER PROMPT)

You are a world-class system architect, rendering engine designer, instructional expert, and multimedia pipeline engineer with 30+ years of experience in building large-scale educational platforms used by millions of learners. Your task is to design a **fully deterministic, JSON-driven video generation system** capable of producing high-quality, deeply explanatory educational videos across **Mathematics, Physics, Chemistry, and Reasoning**, where every visual, animation, transition, explanation, and synchronization is controlled entirely through JSON instructions. The system must not rely on any AI-based decision-making at runtime; instead, it must act as a strict execution engine that interprets JSON and renders video output exactly as defined.

---

# 1. CORE PHILOSOPHY

1.1 Deterministic Execution

* The system must behave like a compiler or rendering engine.
* JSON is the only source of truth.
* No inference, no guessing, no automatic corrections.

1.2 Separation of Concerns

* JSON defines logic and visuals.
* Rendering engine executes instructions.
* Audio system narrates detailed explanations.

1.3 Pedagogical Priority

* Designed for weak and average students.
* Step-by-step, slow, clear explanations.
* Visual clarity over visual complexity.

---

# 2. SYSTEM OBJECTIVE

The system must:

* Accept structured JSON input
* Render educational videos up to 8 minutes per question
* Support all STEM domains:

  * Mathematics (Arithmetic, Algebra, Geometry, etc.)
  * Physics (Mechanics, Electricity, Optics, etc.)
  * Chemistry (Organic, Inorganic, Physical)
  * Reasoning (Logical, Analytical, Pattern-based)
* Generate synchronized audio + visuals
* Allow download and YouTube upload
* Support scalable batch processing

---

# 3. JSON AS DOMAIN-SPECIFIC LANGUAGE (DSL)

3.1 JSON is not just data — it is a **rendering instruction language**.

3.2 JSON must explicitly define:

* Scene structure
* Step flow
* Visual components
* Animation triggers
* Highlight sequences
* Diagram references
* Formula rendering
* Timing (optional but supported)

3.3 The engine must NOT:

* Derive formulas
* Calculate results unless explicitly given
* Add missing steps

---

# 4. HIGH-LEVEL JSON STRUCTURE

Each question JSON must include:

* id
* meta
* assets
* scenes

---

# 5. META STRUCTURE

Meta must include:

* subject (Mathematics / Physics / Chemistry / Reasoning)
* topic
* subtopic
* difficulty (easy / medium / hard)

---

# 6. ASSETS SYSTEM

Assets define reusable resources.

6.1 Image Assets:

* Local file paths
* Example:
  "/assets/images/workers.png"

6.2 SVG Assets:

* Used for diagrams and structured visuals
* Example:
  "/assets/svg/force-diagram.svg"

6.3 Usage Rules:

* Refer by key inside render instructions
* Must be preloaded before rendering

---

# 7. SCENE SYSTEM

Scenes define logical sections of the video:

* question
* options
* concept
* solution
* answer
* visual_intro (optional)

Each scene contains steps.

---

# 8. STEP STRUCTURE (MANDATORY)

Each step must include:

* text → visual text (minimal)
* audio → detailed explanation
* render → rendering instruction

---

# 9. RENDER ENGINE (CORE)

Each render block must define:

* action
* target
* data (optional)
* position (optional)
* size (optional)
* timing (optional)

---

# 10. RENDER ACTION TYPES

10.1 show
Display element

10.2 hide
Remove element

10.3 highlight
Focus on element

10.4 update
Change value or state

10.5 animate
Apply transition

10.6 show_result
Display final output

10.7 draw_arrow
Show flow or direction

10.8 zoom
Focus zoom area

10.9 replace
Swap visual

10.10 sequence
Execute multiple sub-actions

---

# 11. VISUAL COMPONENT SYSTEM

The system must support multiple visual types:

---

## 11.1 Mathematical Components

* digit_boxes → [2] [7] [7]
* equation_block → 27 ÷ 9 = 3
* fraction_block → 1/10
* algebra_block → x + 5 = 10
* graph (if defined via SVG)

---

## 11.2 Physics Components

* formula_block → F = ma
* unit_block → m/s²
* diagram → force arrows, motion paths
* variable_highlight

---

## 11.3 Chemistry Components

* chemical_equation → H2 + O2 → H2O
* reaction_flow (SVG)
* molecule_structure (SVG)
* periodic_table_highlight

---

## 11.4 Reasoning Components

* pattern_grid
* number_series
* sequence_highlight

---

## 11.5 General Components

* image (local)
* svg (diagram)
* table
* chart (bar, pie — via SVG)

---

# 12. TABLE SUPPORT

Tables must be defined explicitly in JSON.

Example:

* headers
* rows

Used for:

* comparison
* data representation
* reasoning problems

---

# 13. CHART SUPPORT

Charts must be SVG-based:

* bar chart
* pie chart
* line chart

All values must be defined in JSON.

---

# 14. VISUAL DESIGN RULES

* Use 80–90% screen for explanation
* Keep UI minimal
* Avoid clutter
* Focus on one idea per step
* Use large readable elements

---

# 15. AUDIO SYSTEM

15.1 Audio must:

* Be natural spoken English
* Be beginner-friendly
* Explain logic fully

15.2 Numbers:

* Use Indian format (lakh, crore)

---

# 16. TEXT VS AUDIO RULE

Text:

* Short
* Symbolic

Audio:

* Full explanation

---

# 17. MICRO-STEP EXPLANATION RULE

* One logical step per entry
* No combined operations
* Explain reasoning fully

---

# 18. SYNCHRONIZATION

* Audio timestamps drive rendering
* Each render aligns with audio segment

---

# 19. VIDEO FLOW

1. Question
2. Options
3. Concept
4. Step-by-step solution
5. Final answer

---

# 20. VIDEO OUTPUT

* Format: MP4
* Codec: H.264
* Duration: up to 8 minutes

---

# 21. BACKEND PIPELINE

1. Parse JSON
2. Validate schema
3. Generate audio
4. Map timestamps
5. Execute render instructions
6. Generate frames
7. Encode video

---

# 22. PARALLEL PROCESSING

* Each question runs independently
* CPU-based scaling
* Queue system

---

# 23. DASHBOARD

Must include:

* JSON upload
* Live preview
* Processing status
* Video library
* Download option
* YouTube upload

---

# 24. STORAGE

* /videos/
* /json/
* /assets/

---

# 25. YOUTUBE SYSTEM

* Manual upload
* Bulk upload
* Status tracking

---

# 26. ERROR HANDLING

* Strict validation
* Fail on invalid JSON
* Log errors

---

# 27. EXTENSIBILITY

* Add new render types
* Add new subjects
* Extend DSL

---

# 28. SECURITY

* Validate paths
* Prevent injection
* Restrict uploads

---

# 29. PERFORMANCE

* Optimize CPU usage
* Batch rendering
* Efficient encoding

---

# 30. FINAL REQUIREMENT

The system must produce:

* Clean visuals
* Deep explanations
* Perfect sync
* Predictable output

---

# 31. ABSOLUTE RULE

The rendering engine must NEVER:

* Guess logic
* Modify JSON
* Add missing steps

It must ONLY:

* Execute JSON instructions exactly

---

# FINAL STATEMENT

This system is not an AI renderer — it is a **JSON execution engine for educational video generation**, capable of rendering any STEM concept (math, physics, chemistry, reasoning) using explicit instructions including equations, diagrams, tables, charts, images, and SVGs, ensuring complete control, scalability, and professional-quality output.
