# JSON DSL Guide

This guide explains how to write JSON files that drive the video generation engine.

---

## Basic Structure

Every JSON file is an **array** of question/topic objects:

```json
[
  {
    "id": "q-math-percentage-basic",
    "mode": "mcq",
    "thumbnail": { ... },
    "meta": { ... },
    "youtube": { ... },
    "question": { ... },
    "scenes": [ ... ]
  }
]
```

Batch processing: put multiple objects in the array to generate multiple videos from one upload.

---

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier. Format: `q-subject-topic-keyword` |
| `meta` | object | Subject, topic, difficulty, exam tags |
| `scenes` | array | Ordered list of scenes (question, options, concept) |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `mode` | string | Video format (default: `mcq`). See modes below |
| `thumbnail` | object | Video thumbnail design |
| `youtube` | object | YouTube upload metadata |
| `question` | object | Question text, options, correct answer |
| `topic_header` | object | Title bar for topic/match/sequence modes |
| `assets` | object | References to uploaded images/SVGs/videos |

---

## Modes

### MCQ (default)

Standard multiple-choice question with 4 options.

```json
{
  "mode": "mcq",
  "question": {
    "text": "What is 15% of 240?",
    "audio": "What is fifteen percent of two hundred and forty?",
    "options": [
      { "key": "a", "value": "32" },
      { "key": "b", "value": "36" },
      { "key": "c", "value": "40" },
      { "key": "d", "value": "44" }
    ],
    "correct": "b"
  },
  "scenes": [
    { "type": "question", ... },
    { "type": "options", ... },
    { "type": "concept", "steps": [ ... ] },
    { "type": "concept", "steps": [ ..., { "render": { "target": "final_answer" } } ] }
  ]
}
```

### Topic Explanation

Free-form lecture with no question or options.

```json
{
  "mode": "topic",
  "topic_header": {
    "title": "Photosynthesis",
    "subtitle": "How plants make food from sunlight"
  },
  "scenes": [
    { "type": "intro", "steps": [{ "render": { "target": "title_card", "title": "..." } }] },
    { "type": "concept", "steps": [{ "render": { "target": "section_header", ... } }, ...] },
    { "type": "concept", "steps": [{ "render": { "target": "concept_text", ... } }, ...] }
  ]
}
```

### Numerical

Calculate answer, no multiple choice options.

```json
{
  "mode": "numerical",
  "question": { "text": "Find the current if V=15V, R=5ohm", ... },
  "scenes": [
    { "type": "question", ... },
    { "type": "concept", "steps": [
      ...,
      { "render": { "target": "numerical_answer", "value": "3", "unit": "A" } }
    ]}
  ]
}
```

### True/False

```json
{
  "mode": "true_false",
  "question": {
    "options": [
      { "key": "a", "value": "True" },
      { "key": "b", "value": "False" }
    ],
    "correct": "a"
  }
}
```

### Fill in the Blank

```json
{
  "mode": "fill_blank",
  "question": { "text": "The powerhouse of the cell is ___" },
  "scenes": [
    ...,
    { "type": "concept", "steps": [
      { "render": { "target": "blank_reveal", "sentence": "The powerhouse of the cell is ___", "answer": "Mitochondria", "revealed": true } }
    ]}
  ]
}
```

### Match the Following

```json
{
  "mode": "match",
  "topic_header": { "title": "Match the Following" },
  "scenes": [
    { "type": "concept", "steps": [
      { "render": { "target": "match_columns", "left": ["A", "B"], "right": ["X", "Y"], "matches": {}, "revealed": false } },
      ...,
      { "render": { "target": "match_columns", "left": ["A", "B"], "right": ["X", "Y"], "matches": {"0":"1","1":"0"}, "revealed": true } }
    ]}
  ]
}
```

### Assertion & Reason

```json
{
  "mode": "assertion",
  "question": {
    "text": "Consider the following statements:",
    "assertion": "Photosynthesis occurs in chloroplasts.",
    "reason": "Chloroplasts contain chlorophyll.",
    "options": [
      { "key": "a", "value": "Both A and R are true and R explains A" },
      { "key": "b", "value": "Both A and R are true but R does not explain A" },
      { "key": "c", "value": "A is true but R is false" },
      { "key": "d", "value": "A is false but R is true" }
    ],
    "correct": "a"
  }
}
```

### Sequence / Ordering

```json
{
  "mode": "sequence",
  "topic_header": { "title": "Arrange in Order" },
  "scenes": [
    { "type": "concept", "steps": [
      { "render": { "target": "sequence_list", "items": ["Step A", "Step B", "Step C"], "revealed": false } },
      ...,
      { "render": { "target": "sequence_list", "items": ["Step A", "Step B", "Step C"], "revealed": true } }
    ]}
  ]
}
```

---

## Scenes

Scenes are processed in order. Each scene has a `type` and either direct `audio`/`render` or a `steps` array.

### Scene Types

| Type | Purpose | Has steps? |
|------|---------|------------|
| `question` | Show question in header | No |
| `options` | Show options in header | No |
| `concept` | Main explanation content | Yes |
| `visual_intro` | Show image without audio | No |
| `intro` | Topic mode intro | Yes |

### Steps

Each step in a concept scene has:
- `text` -- Short label shown as heading
- `audio` -- Full narration (natural speech, no math symbols)
- `render` -- One visual action on one target

**Critical rule:** One step = one visual element. Never combine multiple visual changes in one step.

---

## Render Actions

| Action | When to Use |
|--------|-------------|
| `show` | First time displaying an element |
| `update` | Changing value of already-visible element |
| `highlight` | Adding emphasis to existing element |
| `show_result` | Like show, but for final answers |
| `clear` | Removing an element from screen |

---

## Audio Rules

All `audio` fields are sent directly to TTS. They must be:
- Natural spoken English (complete sentences)
- No math symbols -- spell everything out
- Minimum 2 sentences per step
- Numbers in words: `1947` -> `"nineteen forty seven"`

| Symbol | Write as |
|--------|----------|
| `H₂O` | "H two O" |
| `÷` | "divided by" |
| `×` | "multiplied by" |
| `²` | "squared" |
| `√` | "square root of" |
| `%` | "percent" |
| `π` | "pi" |

---

## Visual Elements Quick Reference

**Text/Concept:**
`concept_text`, `highlight_box`, `formula_block`, `instruction_text`

**Math Working:**
`equation`, `digit_boxes`, `running_sum`, `fraction`, `sum_box`, `shortcut_columns`, `number_line`

**Science:**
`chem_equation`, `flow_chart`, `key_facts`, `process_steps`, `two_col_text`, `t_account`

**General:**
`table`, `timeline`, `memory_trick`, `analogy`, `image`, `svg`

**Visuals:**
`builtin_visual` (74 diagrams), `subject_image` (auto-fetch photo), `video_clip`, `matplotlib_plot`, `rdkit_mol`, `manim_scene`

**Mode-specific:**
`title_card`, `section_header`, `blank_reveal`, `match_columns`, `sequence_list`, `numerical_answer`

**Layout:**
`question_block`, `options_grid`, `option_a/b/c/d`, `final_answer`

For detailed field documentation, see [REFERENCE_SCHEMA.json](../REFERENCE_SCHEMA.json).

---

## Generating JSON with AI

Use [PROMPT_JSON_GENERATOR.md](../PROMPT_JSON_GENERATOR.md) as a system prompt for Claude, GPT-4, or Gemini. It contains the complete DSL specification, rules, and a fill-in-the-blank template.

1. Copy the SYSTEM PROMPT section into your AI's system message
2. Use the USER PROMPT TEMPLATE, filling in your question details
3. The AI outputs valid JSON ready to upload

The prompt enforces all rules: scene ordering, one-element-per-step, audio quality, visual requirements.
