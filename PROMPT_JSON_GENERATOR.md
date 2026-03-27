# AI Prompt — Educational Video JSON Generator
## Universal DSL for the Python Video Engine

> **How to use**: Copy the SYSTEM PROMPT section and paste it into Claude / GPT-4 / Gemini as the system message. Then use the USER PROMPT template for each question. Get back perfect, ready-to-render JSON every time.

---

## ═══════════════════════════════════════════
## SYSTEM PROMPT (paste once per session)
## ═══════════════════════════════════════════

```
You are an expert educational video script writer specializing in Indian competitive exam preparation.
You generate structured JSON files that drive a Python video rendering engine.

YOUR ONLY OUTPUT IS VALID JSON. No markdown code fences. No explanation text. No comments outside _comment fields. Just the raw JSON array.

RENDERING ENGINE FACTS:
- JSON controls: question display, narration audio, visual elements, layout, timing, thumbnail
- Audio is converted to speech (TTS) — what you write is EXACTLY what students hear
- Each "step" in a scene = one visual change + one narration segment
- Elements accumulate — once shown, they stay visible until replaced or cleared
- The question and options are ALWAYS visible in the header once shown
- Highlighting an option turns it SAFFRON (orange) in the header options row
- final_answer turns the CORRECT option GREEN in the header options row

QUALITY CONTRACT:
- Every audio field must be natural spoken English with NO math symbols
- Every step must explain WHY, not just show WHAT
- Concepts must appear BEFORE working (rule → application, not application → rule)
- MULTIPLE CONCEPT SCENES: one scene per section (rule, option A, option B, option C, option D)
- Do NOT put everything in one concept scene — split by logical sections
- Start each new concept scene with instruction_text to clear previous elements
- When explaining a specific option, highlight it in saffron using target "option_a/b/c/d"
- Progressive reveal: add one element at a time, not everything at once
- Final step must always be { "action": "show", "target": "final_answer" } — shows correct option in GREEN
```

---

## ═══════════════════════════════════════════
## COMPLETE DSL SPECIFICATION
## ═══════════════════════════════════════════

### TOP-LEVEL STRUCTURE

```json
[
  {
    "id": "q-subject-topic-keyword",
    "thumbnail_intro_seconds": 3,
    "thumbnail": { ... },
    "meta": { ... },
    "question": { ... },
    "scenes": [ ... ],
    "assets": { ... }
  }
]
```

---

### FIELD: id
```
Format: q-[subject]-[topic]-[2-3 keywords]
Rules:  Lowercase, hyphens only, no spaces, globally unique
Examples:
  q-math-percentage-15-of-240
  q-bio-photosynthesis-byproduct
  q-hist-independence-1947
  q-chem-neutralisation-acid-base
  q-reasoning-analogy-doctor-hospital
  q-accounts-cash-ledger-debit-credit
  q-physics-ohms-law-current
```

---

### FIELD: thumbnail_intro_seconds
```
Type: integer, 0–5
Use: 0 = no intro still image
     3 = recommended for YouTube videos
     4 = recommended for reels/shorts with complex thumbnails
```

---

### FIELD: thumbnail
```json
{
  "title":      "3–4 word headline (e.g. 'Divisibility Rules')",
  "subtitle":   "Descriptive subtitle (e.g. 'Rule of 9 & Rule of 11 — Fast Method')",
  "badge":      "Exam tags (e.g. 'SSC | UPSC | Banking | Railway')",
  "topic":      "Subject — Topic (e.g. 'Mathematics — Number Theory')",
  "highlights": ["What makes this unique 1", "Key visual element 2", "Shortcut/trick 3"],
  "style":      "dark"
}
```

---

### FIELD: meta
```json
{
  "subject":    "Pick ONE: Mathematics | Biology | Chemistry | Physics | History | Geography | Accounts | Economics | Reasoning | English | Computer Science | General Knowledge",
  "topic":      "Chapter-level name (e.g. 'Percentage', 'Cell Biology', 'Freedom Struggle')",
  "subtopic":   "Specific concept (e.g. 'Finding X% of Y', 'Photosynthesis equation')",
  "difficulty": "easy | medium | hard",
  "exam":       "SSC / UPSC / JEE / NEET / CAT / IBPS / Railway / State PSC / Class 10",
  "grade":      "Class 10 | Class 11-12 | Competitive Exams | Class 6-8",
  "language":   "English"
}
```

---

### FIELD: question
```json
{
  "text":    "Display text — can use Unicode: ÷ × ≤ ≥ ² ³ √ → ≠ ± π H₂O CO₂",
  "audio":   "SPOKEN version — NO symbols, spell everything (see AUDIO RULES below)",
  "options": [
    { "key": "a", "value": "Option A display text" },
    { "key": "b", "value": "Option B display text" },
    { "key": "c", "value": "Option C display text" },
    { "key": "d", "value": "Option D display text" }
  ],
  "correct": "b"
}
```

---

### FIELD: assets (optional)
```json
{
  "images":      { "key_name": "images/subject/filename.png" },
  "svgs":        { "key_name": "svgs/subject/filename.svg" },
  "videos":      { "key_name": "videos/subject/filename.mp4" },
  "audio_clips": { "key_name": "audio_clips/filename.mp3" }
}
```
Upload files via Assets page. Use the key in `render.src` for image/svg/video targets.

---

### SCENES — STRUCTURE

```
scenes array → scene objects → steps array → step objects → render object
```

#### Scene types:
| type | purpose | has steps? | has audio? |
|------|---------|------------|------------|
| `question` | Show question in header | No | Yes |
| `options` | Show options in header | No | Yes |
| `concept` | Main explanation | Yes | Yes (per step) |
| `visual_intro` | Show image/diagram | No | No |

#### Question scene:
```json
{
  "type": "question",
  "text": "Question display text",
  "audio": "Full spoken narration — explain context, define keywords, set up the problem",
  "render": { "action": "show", "target": "question_block" }
}
```

#### Options scene:
```json
{
  "type": "options",
  "audio": "Option A [read value]. Option B [read value]. Option C [read value]. Option D [read value]. Pause and think.",
  "render": { "action": "show", "target": "options_grid" }
}
```

#### Concept scene with steps:
```json
{
  "type": "concept",
  "steps": [
    {
      "text":   "Step label (3–5 words, shown as heading)",
      "audio":  "Full narration for this step (2–4 sentences, natural speech)",
      "render": { "action": "show", "target": "ELEMENT_TYPE", ...fields }
    }
  ]
}
```

---

## ═══════════════════════════════════════════
## ALL RENDER TARGETS — COMPLETE REFERENCE
## ═══════════════════════════════════════════

### 1. `question_block`
```json
{ "action": "show", "target": "question_block" }
```
Reveals question in the dark navy header. Used only in question scene.

---

### 2. `options_grid`
```json
{ "action": "show", "target": "options_grid" }
```
Reveals 4 option pills in header. Used only in options scene.

---

### 3. `concept_text`
Blue or orange card with heading + bullet list. Most-used element for explanations.
```json
{
  "action": "show",
  "target": "concept_text",
  "heading": "Rule of 9",
  "items": [
    "Add all digits of the number.",
    "If digit sum ÷ 9 has no remainder → divisible by 9.",
    "Example: 10098 → 1+0+0+9+8 = 18 → 18÷9=2 ✓"
  ],
  "highlighted": false
}
```
- `highlighted: false` → blue accent (definitions, rules, concepts)
- `highlighted: true` → orange accent (warnings, contrasting info, emphasis)
- **Mutual exclusive with `shortcut_columns`** — one clears the other
- Items: 2–5 bullet points. Each is one display line.

---

### 4. `highlight_box`
Full-width bold rule/formula banner. Use for single golden rules.
```json
{
  "action": "show",
  "target": "highlight_box",
  "text": "Acid + Base → Salt + Water  (Neutralisation)",
  "color": "orange"
}
```
- `color`: `orange` (rules/formulas), `blue` (info), `green` (correct), `red` (warning)
- One line of large centered text inside colored card
- Use BEFORE concept_text steps — first impression

---

### 5. `key_facts`
Key:Value fact table. Blue background. Use for properties, dates, units.
```json
{
  "action": "show",
  "target": "key_facts",
  "heading": "Quick Facts",
  "facts": [
    { "key": "Year",      "value": "1947" },
    { "key": "Leader",    "value": "Mahatma Gandhi" },
    { "key": "Movement",  "value": "Non-violence / Satyagraha" },
    { "key": "Result",    "value": "Independence on 15 August 1947" }
  ]
}
```
- `key` = left column (blue bold), `value` = right column (dark text)
- 3–6 facts recommended
- Ideal for: History dates, science facts, physics units, vocabulary

---

### 6. `process_steps`
Numbered steps with orange circles. Use for procedures and methods.
```json
{
  "action": "show",
  "target": "process_steps",
  "heading": "Steps to Solve",
  "steps": [
    "Write the formula: I = V ÷ R",
    "Substitute values: V = 15V, R = 5Ω",
    "Calculate: I = 15 ÷ 5 = 3 A"
  ]
}
```
- Each string = one numbered step
- 3–5 steps recommended
- Ideal for: Math methods, Biology processes, Chemistry procedures

---

### 7. `two_col_text`
Two-column side-by-side comparison. Blue/Orange columns.
```json
{
  "action": "show",
  "target": "two_col_text",
  "left": {
    "heading": "Acids",
    "items": ["pH < 7", "Sour taste", "Turns litmus RED", "HCl, H₂SO₄"]
  },
  "right": {
    "heading": "Bases",
    "items": ["pH > 7", "Bitter taste", "Turns litmus BLUE", "NaOH, NH₃"]
  }
}
```
- Same number of items in both columns recommended
- Ideal for: comparisons, before/after, pros/cons, SI units vs symbols, two rules

---

### 8. `timeline`
Chronological events on vertical timeline. Blue dots, orange for highlights.
```json
{
  "action": "show",
  "target": "timeline",
  "heading": "Freedom Struggle Timeline",
  "events": [
    { "year": "1857", "event": "First War of Independence",        "highlight": false },
    { "year": "1885", "event": "INC founded by A.O. Hume",         "highlight": false },
    { "year": "1930", "event": "Dandi March — Salt Satyagraha",    "highlight": false },
    { "year": "1942", "event": "Quit India Movement launched",     "highlight": false },
    { "year": "1947", "event": "India gains Independence! 🎉",     "highlight": true }
  ]
}
```
- `year` can be any string: "3000 BCE", "August 1947", "Phase 1"
- `highlight: true` = orange dot + bold text
- 4–8 events recommended

---

### 9. `chem_equation`
Chemical equation with colored arrow. Green background card.
```json
{
  "action": "show",
  "target": "chem_equation",
  "reactants":  "2H₂ + O₂",
  "products":   "2H₂O",
  "conditions": "High temperature / Catalyst",
  "reversible": false
}
```
- `reversible: false` → → arrow (one-way reaction)
- `reversible: true`  → ⇌ arrow (equilibrium reaction)
- `conditions` is optional — omit if no special conditions
- Use Unicode subscripts: H₂O CO₂ H₂SO₄ Ca(OH)₂ Fe₂O₃

---

### 10. `flow_chart`
Process flow with colored boxes and arrows between them.
```json
{
  "action": "show",
  "target": "flow_chart",
  "heading": "Photosynthesis Flow",
  "steps": [
    { "text": "Sunlight absorbed by Chlorophyll",  "color": "orange" },
    { "text": "Water split → O₂ released",         "color": "blue"   },
    { "text": "CO₂ + H → Glucose formed",          "color": "green"  }
  ]
}
```
- `color`: `orange | blue | green | red`
- Steps auto-connected by downward arrows
- Keep text in each box short (≤8 words)
- Ideal for: Biology cycles, reaction steps, decision processes

---

### 11. `t_account`
Double-entry bookkeeping T-account ledger.
```json
{
  "action": "show",
  "target": "t_account",
  "name": "Cash Account",
  "debit": [
    { "desc": "Opening Balance (b/d)", "amount": "50,000" },
    { "desc": "Cash from Customers",   "amount": "80,000" }
  ],
  "credit": [
    { "desc": "Purchases (Cash)",  "amount": "40,000" },
    { "desc": "Salaries Paid",     "amount": "25,000" },
    { "desc": "Balance c/d",       "amount": "65,000" }
  ]
}
```
- `name` = account heading in navy banner
- `desc` = description, `amount` = string (use commas: "1,50,000")
- Debit = left, Credit = right

---

### 12. `memory_trick`
Mnemonic/acronym display with large colored letters.
```json
{
  "action": "show",
  "target": "memory_trick",
  "label":     "Remember the visible spectrum as:",
  "trick":     "VIBGYOR",
  "expansion": "Violet  Indigo  Blue  Green  Yellow  Orange  Red",
  "note":      "Arranged from highest to lowest frequency"
}
```
- `label` = small prompt text above acronym
- `trick` = acronym rendered LARGE with rainbow-colored letters
- `expansion` = full form, centered below
- `note` = optional small note at bottom
- Ideal for: any acronym, mnemonic, ordered list memory aid

---

### 13. `analogy`
A:B::C:? format for Reasoning questions.
```json
{
  "action": "show",
  "target": "analogy",
  "relation": "Person : Place of Work",
  "pairs": [
    ["Doctor",  "Hospital"],
    ["Teacher", "?"]
  ],
  "answer": ""
}
```
Then for the reveal step (same target, different answer):
```json
{
  "action": "show",
  "target": "analogy",
  "relation": "Person : Place of Work",
  "pairs": [
    ["Doctor",  "Hospital"],
    ["Teacher", "?"]
  ],
  "answer": "School"
}
```
- `relation` = describes the pattern (optional but helpful)
- `pairs` = array of 2-element arrays
- Show twice: first with `answer: ""`, then with the actual answer

---

### 14. `number_line`
Number line with marked and highlighted positions.
```json
{
  "action": "show",
  "target": "number_line",
  "label":     "Number Line",
  "start":     -5,
  "end":       20,
  "marks":     [-5, 0, 5, 10, 15, 20],
  "highlight": [7]
}
```
- `start/end` = integers or floats (the visible range)
- `marks` = positions to show dots (all are shown, blue)
- `highlight` = positions to highlight in orange (larger dot)

---

### 15. `equation`
Math equation in a gray card. Centered text.
```json
{ "action": "show", "target": "equation", "value": "I = V ÷ R = 15 ÷ 5" }
{ "action": "show", "target": "equation", "value": "I = 3 A", "highlighted": true }
```
- `highlighted: false` = blue accent (working steps)
- `highlighted: true` = green border + green text (final result)
- For update: `{ "action": "update", "target": "equation", "value": "new expression" }`

---

### 16. `formula_block`
Blue-background formula card with "Formula" label.
```json
{ "action": "show", "target": "formula_block", "value": "V = I × R" }
```
- Auto-adds small "Formula" label above text
- Use for named formulas (not intermediate steps)

---

### 17. `digit_boxes`
Individual digit boxes in white cards. For digit-sum methods.
```json
{
  "action": "show",
  "target": "digit_boxes",
  "data": [1, 0, 0, 9, 8],
  "highlighted_indices": []
}
```
- `data` = array of integers [1,2,3] or strings ["+1","-0","+9"]
- `highlighted_indices` = 0-based positions to highlight in blue
- For alternating signs: `["+1", "-0", "+0", "-9", "+8"]`

---

### 18. `running_sum`
Shows a running total. Usually after digit_boxes.
```json
{ "action": "show", "target": "running_sum", "value": "18" }
```
Shows as "Sum = 18" in a styled card.

---

### 19. `fraction`
Fraction display card.
```json
{
  "action": "show",
  "target": "fraction",
  "numerator":   "15",
  "denominator": "100",
  "result":      "3/20",
  "label":       "Simplify",
  "highlighted": false
}
```

---

### 20. `sum_box`
Highlighted result box for final numerical answers.
```json
{ "action": "show", "target": "sum_box", "value": "36", "highlighted": true }
```

---

### 21. `shortcut_columns`
Two-column math shortcut method. Build progressively across steps.
```json
{
  "action": "show",
  "target": "shortcut_columns",
  "left": {
    "title":       "Rule of 9",
    "digit_data":  [1, 0, 0, 9, 8],
    "operator":    "+",
    "numerator":   "18",
    "denominator": "9",
    "result":      "2",
    "verdict":     "Divisible by 9!",
    "pass":        true
  },
  "right": {
    "title":     "Rule of 11",
    "digit_data": ["+1", "-0", "+0", "-9", "+8"],
    "sum_text":  "+1 - 0 + 0 - 9 + 8 = 0",
    "verdict":   "Divisible by 11!",
    "pass":      true
  }
}
```
- Start with only `left: { "title": "..." }`, then add fields step by step
- `pass: true` → green ✓ badge, `pass: false` → red ✗ badge
- `operator` = "+" or "−" (shown between digits)
- `sum_text` = alternating sum expression string (for Rule of 11)

---

### 22. `image`
Display an uploaded image asset.
```json
{
  "action": "show",
  "target": "image",
  "src": "cell_diagram",
  "position": "center",
  "size": "medium"
}
```
- `src` = key from `assets.images` block
- `position`: `center | left | right`
- `size`: `small | medium | large`

---

### 23. `svg`
Display an uploaded SVG.
```json
{
  "action": "show",
  "target": "svg",
  "src": "number_line_svg",
  "position": "center",
  "size": "large"
}
```

---

### 24. `video_clip`
Display first frame of an uploaded video with caption.
```json
{
  "action": "show",
  "target": "video_clip",
  "src": "pendulum_demo",
  "caption": "Simple Pendulum — Oscillation Demo"
}
```

---

### 25. `table`
Data table with headers and rows.
```json
{
  "action": "show",
  "target": "table",
  "headers": ["Law", "Formula", "Unit"],
  "rows": [
    ["Ohm's Law", "V = IR", "Volt (V)"],
    ["Power",     "P = VI", "Watt (W)"],
    ["Energy",    "E = Pt", "Joule (J)"]
  ]
}
```

---

### 26. `instruction_text`
Full-width instruction that **CLEARS all other body elements**. Section transition.
```json
{
  "action": "show",
  "target": "instruction_text",
  "value": "Now applying to Option B: 10098"
}
```
Use when moving to a completely new section/focus.

---

### 27. `option_a` / `option_b` / `option_c` / `option_d`
**Highlight a specific option in SAFFRON** in the header options row while explaining it.
```json
{ "action": "show", "target": "option_b" }
```
- Use during explanation steps when you are discussing that specific option
- The highlighted option turns **saffron (orange)** background in the header
- Only one option is saffron at a time — highlighting a new one clears the previous
- Alternative syntax (same effect):
  ```json
  { "action": "highlight_option", "target": "options_grid", "key": "b" }
  ```

**Typical workflow:**
```
Step: highlight option_a → explain why Option A is wrong → saffron on A
Step: highlight option_b → explain why Option B is correct → saffron on B
Step: final_answer        → correct option turns GREEN, saffron removed
```

---

### 28. `final_answer`
**Always the very last step.** Reveals the correct option with a **GREEN badge** in the header.
```json
{ "action": "show", "target": "final_answer" }
```
- No other fields needed
- Automatically reads `question.correct` to determine which option turns green
- Removes any saffron highlight — the green badge replaces it
- Triggers `show_correct = True` — correct option stays green for rest of video

---

## ═══════════════════════════════════════════
## ACTIONS — WHEN TO USE EACH
## ═══════════════════════════════════════════

| action | when to use | example |
|--------|-------------|---------|
| `show` | First time showing this element | `{ "action": "show", "target": "equation", "value": "x = 3" }` |
| `update` | Change value of already-shown element | `{ "action": "update", "target": "equation", "value": "x = 5" }` |
| `highlight` | Add highlight effect to existing element | `{ "action": "highlight", "target": "equation" }` |
| `show_result` | Like `show` but for answer/result context | `{ "action": "show_result", "target": "sum_box", "value": "36" }` |
| `clear` | Remove element from screen | `{ "action": "clear", "target": "equation" }` |

---

## ═══════════════════════════════════════════
## AUDIO WRITING RULES — CRITICAL
## ═══════════════════════════════════════════

### Symbol → Spoken conversion table:
| Symbol | Write in audio as |
|--------|-------------------|
| H₂O | "H two O" |
| CO₂ | "carbon dioxide" |
| H₂SO₄ | "sulphuric acid" or "H two S O four" |
| ÷ | "divided by" |
| × | "multiplied by" |
| ± | "plus or minus" |
| √ | "square root of" |
| ² | "squared" |
| ³ | "cubed" |
| ≥ | "greater than or equal to" |
| ≤ | "less than or equal to" |
| ≠ | "not equal to" |
| → | "gives" or "produces" or "becomes" |
| ⇌ | "is in equilibrium with" |
| π | "pi" |
| α | "alpha" |
| β | "beta" |
| % | "percent" |
| ° | "degree" |
| Σ | "sum of" |

### Number pronunciation:
| Written | Spoken |
|---------|--------|
| 1947 | "nineteen forty seven" |
| 10098 | "ten thousand and ninety eight" |
| 277218 | "two lakh seventy seven thousand two hundred and eighteen" |
| 1,50,000 | "one lakh fifty thousand" |
| 3.14 | "three point one four" |
| ¾ | "three fourths" or "three over four" |

### Audio quality rules:
1. **Complete sentences** — no fragments. Bad: "Digit sum eighteen." Good: "The digit sum is eighteen."
2. **Explain WHY** — Bad: "1+0+0+9+8=18". Good: "Add all five digits: one plus zero plus zero plus nine plus eight equals eighteen."
3. **Natural teacher voice** — Write as you would explain to a student in class
4. **No hyphens** — "twenty-one" → "twenty one"
5. **Option keys** — Always say "Option A", never "(A)" or "paren A"
6. **Minimum 2 sentences per step** — even simple reveal steps
7. **Transition words** — Use "Now", "Let us", "Notice that", "Therefore", "So", "This means"

---

## ═══════════════════════════════════════════
## PROGRESSIVE REVEAL PATTERN
## ═══════════════════════════════════════════

```
Scene order — USE MULTIPLE CONCEPT SCENES (one per section):

  Scene 1 — type: "question"   → read the question
  Scene 2 — type: "options"    → read all 4 options
  Scene 3 — type: "concept"    → KEY RULE (highlight_box or concept_text)
  Scene 4 — type: "concept"    → Test OPTION A  (instruction_text → option_a → working)
  Scene 5 — type: "concept"    → Test OPTION B  (instruction_text → option_b → working)
  Scene 6 — type: "concept"    → Test OPTION C  (instruction_text → option_c → working)
  Scene 7 — type: "concept"    → Test OPTION D + final_answer
```

**CRITICAL: Do NOT put everything in one concept scene. Each option/section = its own concept scene.**

**Use `instruction_text` as the FIRST step in each new concept scene to clear the previous elements:**
```json
{
  "text": "Testing Option A",
  "audio": "Let us now check Option A.",
  "render": { "action": "show", "target": "instruction_text", "value": "Testing Option A: 49104" }
}
```
`instruction_text` CLEARS all body elements from the previous scene so each section starts clean.

**Full multi-scene template:**
```
Scene 3 — Rule:
  step: highlight_box   "Digit sum divisible by 9 → number divisible by 9"

Scene 4 — Option A:
  step: instruction_text  "Testing Option A: 49104"
  step: option_a          (saffron highlight in header)
  step: digit_boxes       [4,9,1,0,4]
  step: running_sum       "18"
  step: concept_text      heading="Result", items=["18 ÷ 9 = 2 ✓", "Divisible by 9"]

Scene 5 — Option B:
  step: instruction_text  "Testing Option B: 77832"
  step: option_b          (saffron highlight in header)
  step: digit_boxes       [7,7,8,3,2]
  step: running_sum       "27"
  step: concept_text      heading="Result", items=["27 ÷ 9 = 3 ✓", "Divisible by 9"]

Scene 6 — Option C:
  step: instruction_text  "Testing Option C: 35253"
  step: option_c
  step: digit_boxes       [3,5,2,5,3]
  step: running_sum       "18"

Scene 7 — Option D (the answer):
  step: instruction_text  "Testing Option D: 45390"
  step: option_d
  step: digit_boxes       [4,5,3,9,0]
  step: running_sum       "21"
  step: highlight_box     "21 is NOT divisible by 9!" color=red
  step: final_answer      ← correct option turns GREEN
```

**Progressive shortcut_columns build-up (within one scene):**
```
Step 1: left: { "title": "Rule of 9" }                            ← heading only
Step 2: left: { title + digit_data + operator }                   ← add digits
Step 3: left: { ... + numerator + denominator + result }          ← add fraction
Step 4: left: { ... + verdict + pass }                            ← add result
Step 5: left: { full }, right: { "title": "Rule of 11" }          ← start right column
Step 6: left: { full }, right: { + digit_data }                   ← add right digits
Step 7: left: { full }, right: { + sum_text + verdict + pass }    ← complete
```

---

## ═══════════════════════════════════════════
## SUBJECT → ELEMENTS GUIDE
## ═══════════════════════════════════════════

| Subject | Must-use elements | Good to add |
|---------|------------------|-------------|
| **Mathematics** | `formula_block`, `equation` | `digit_boxes`, `shortcut_columns`, `fraction`, `running_sum`, `sum_box`, `number_line` |
| **Biology** | `process_steps`, `flow_chart` | `chem_equation`, `key_facts`, `concept_text`, `image`, `memory_trick` |
| **Chemistry** | `chem_equation`, `highlight_box` | `concept_text`, `key_facts`, `two_col_text`, `flow_chart` |
| **Physics** | `formula_block`, `equation` | `highlight_box`, `two_col_text`, `key_facts`, `table` |
| **History** | `timeline`, `key_facts` | `two_col_text`, `memory_trick`, `concept_text` |
| **Geography / GK** | `key_facts`, `two_col_text` | `timeline`, `memory_trick`, `table`, `image` |
| **Accounts** | `t_account`, `highlight_box` | `key_facts`, `concept_text`, `two_col_text` |
| **Reasoning** | `analogy`, `concept_text` | `memory_trick`, `key_facts`, `process_steps` |
| **Economics** | `key_facts`, `highlight_box` | `two_col_text`, `table`, `concept_text` |
| **English Grammar** | `concept_text`, `two_col_text` | `highlight_box`, `key_facts`, `table` |
| **Computer Science** | `process_steps`, `flow_chart` | `table`, `highlight_box`, `concept_text` |

---

## ═══════════════════════════════════════════
## COMMON MISTAKES TO AVOID
## ═══════════════════════════════════════════

❌ **DON'T: Everything in one concept scene**
```
Wrong:  "scenes": [ question, options, ONE big concept scene with 15+ steps ]
Correct: "scenes": [ question, options, concept(rule), concept(optionA), concept(optionB), concept(optionC), concept(optionD+answer) ]
```

❌ **DON'T: Missing instruction_text at the start of each new section**
```
Wrong:  New concept scene starts directly with digit_boxes — old elements still visible
Correct: First step of each new concept scene: { "target": "instruction_text", "value": "Testing Option A: 49104" }
```

❌ **DON'T: Math symbols in audio**
```
Wrong:  "audio": "H₂O + CO₂ → products"
Correct: "audio": "Water and carbon dioxide react to form products"
```

❌ **DON'T: Working before concept**
```
Wrong: steps = [digit_boxes, shortcut_columns, concept_text]
Correct: steps = [concept_text (rule), shortcut_columns (working), final_answer]
```

❌ **DON'T: Show everything at once in shortcut_columns**
```
Wrong: One step with complete left AND right columns fully filled
Correct: 6-8 steps building left column, then 3-4 steps building right column
```

❌ **DON'T: Answer scene**
```
Wrong: scenes includes { "type": "answer" }
Correct: Last step in concept scene is { "render": { "target": "final_answer" } }
```

❌ **DON'T: Generic or lazy audio**
```
Wrong:  "audio": "Here is the answer."
Correct: "audio": "Therefore, ten thousand and ninety eight passes both tests. Option B is the correct answer."
```

❌ **DON'T: Trailing commas**
```
Wrong:  [{"key":"a"}, {"key":"b"},]
Correct: [{"key":"a"}, {"key":"b"}]
```

❌ **DON'T: Missing final_answer step**
```
Wrong: Last step shows sum_box or equation
Correct: Always add one final step with { "action":"show", "target":"final_answer" }
```

❌ **DON'T: Never highlight the option being explained**
```
Wrong: Explain working for Option B with no option highlight → student doesn't know which option you're testing
Correct: Add { "action":"show", "target":"option_b" } at the start of that option's working steps
```

❌ **DON'T: Use option highlight and final_answer together**
```
Wrong: Last step is { "target": "option_b" }  ← stays saffron, never turns green
Correct: Last step is ALWAYS { "target": "final_answer" } ← turns correct option GREEN
```

---

## ═══════════════════════════════════════════
## USER PROMPT TEMPLATE (fill and use)
## ═══════════════════════════════════════════

```
Generate educational video JSON for the following question.

--- QUESTION DETAILS ---
Subject:      [e.g. Mathematics / Biology / Chemistry / Physics / History / Accounts / Reasoning]
Topic:        [e.g. Percentage / Photosynthesis / Acids and Bases / Ohm's Law / Freedom Struggle]
Subtopic:     [e.g. Finding X% of Y / Balanced equation / Neutralisation / Current calculation]
Question:     [Full question text]
Option A:     [Option A value]
Option B:     [Option B value]
Option C:     [Option C value]
Option D:     [Option D value]
Correct:      [a/b/c/d]
Exam target:  [e.g. SSC CGL / UPSC / JEE Mains / NEET / Class 10 / IBPS PO]
Difficulty:   [easy / medium / hard]
Video style:  [shortcut method / step-by-step / concept explanation / comparison]

--- GENERATION RULES ---
1. Output ONLY valid JSON — no markdown, no explanation, no code fences.
2. Wrap output in a JSON array [ { ... } ].
3. Use the DSL spec provided (element types, field names, actions).
4. Audio text: NO math symbols — spell everything out in natural English.
5. Show KEY RULE first, then working steps, then final_answer last.
6. Progressive reveal — add one piece at a time to build the visual.
7. Minimum 7 concept steps, maximum 15. Include all relevant subject elements.
8. Write audio as a teacher explaining to a student — complete sentences, explain WHY.
9. Use the correct element types for this subject (see Subject → Elements Guide).
10. Include a complete thumbnail block with highlights.
```

---

## ═══════════════════════════════════════════
## COMPLETE EXAMPLE OUTPUT
## ═══════════════════════════════════════════

For reference, see the file: `sample_all_elements.json`

It contains complete working examples for all subjects:
- **Math**: Percentage (formula_block, equation, fraction, sum_box, number_line)
- **Math**: Divisibility rules (shortcut_columns full build-up)
- **Biology**: Photosynthesis (process_steps, flow_chart, chem_equation, key_facts, memory_trick)
- **Chemistry**: Acid-base (highlight_box, chem_equation, key_facts)
- **Physics**: Ohm's Law (formula_block, two_col_text, equation)
- **History**: Independence 1947 (timeline, two_col_text, key_facts, memory_trick)
- **Accounts**: Cash ledger (highlight_box, key_facts, t_account)
- **Reasoning**: Analogy (concept_text, analogy reveal pattern)

---

## ═══════════════════════════════════════════
## ANNOTATED SCHEMA FILE
## ═══════════════════════════════════════════

See `REFERENCE_SCHEMA.json` for the complete annotated schema.
Every field has a `_comment` sibling showing:
- What the field does
- Valid values
- Examples
- When to use / when to omit

The `_comment` fields are **ignored by the renderer** — they exist only for documentation.

---

*Engine: Python + Pillow + FFmpeg + gTTS | DSL version: 2.0 | Supports all subjects, all exams*
