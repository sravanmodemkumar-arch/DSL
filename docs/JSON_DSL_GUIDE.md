# JSON DSL Guide

This document explains how to write JSON files for the STEM Video Generator. JSON is the **only input** — the engine renders exactly what you specify.

---

## Table of Contents

1. [Root Structure](#1-root-structure)
2. [Meta Object](#2-meta-object)
3. [Assets Object](#3-assets-object)
4. [Scenes Array](#4-scenes-array)
5. [Scene Types](#5-scene-types)
6. [Step Structure](#6-step-structure)
7. [Render Object](#7-render-object)
8. [Render Actions](#8-render-actions)
9. [Render Targets](#9-render-targets)
10. [Text vs Audio Rule](#10-text-vs-audio-rule)
11. [Complete Examples](#11-complete-examples)
12. [Validation Rules](#12-validation-rules)

---

## 1. Root Structure

The JSON file must be an **array** of question objects. Even for a single question, wrap it in `[]`.

```json
[
  {
    "id": "unique-question-id",
    "meta": { ... },
    "assets": { ... },
    "scenes": [ ... ]
  },
  {
    "id": "another-question",
    "meta": { ... },
    "scenes": [ ... ]
  }
]
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier. Used for file naming and database lookup. |
| `meta` | object | Yes | Subject, topic, difficulty metadata. |
| `assets` | object | No | Reusable images and SVGs. |
| `scenes` | array | Yes | Ordered list of scenes (question → solution → answer). |

---

## 2. Meta Object

```json
{
  "meta": {
    "subject": "Mathematics",
    "topic": "Arithmetic",
    "subtopic": "Time and Work",
    "difficulty": "medium",
    "chapter": "Chapter 5",
    "exam_tags": ["SSC-CGL", "Banking-IBPS"],
    "purpose_tags": ["exam", "revision"],
    "grade_tags": ["class-10"]
  }
}
```

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `subject` | string | Yes | Mathematics, Physics, Chemistry, Reasoning, etc. |
| `topic` | string | Yes | Any topic name |
| `subtopic` | string | No | More specific topic |
| `difficulty` | string | No | `easy`, `medium`, `hard` (default: medium) |
| `chapter` | string | No | Chapter name for organization |
| `exam_tags` | array | No | Target exams (SSC, UPSC, JEE, NEET, etc.) |
| `purpose_tags` | array | No | Use cases (exam, test, notes, revision) |
| `grade_tags` | array | No | Class/grade level |

---

## 3. Assets Object

Assets are reusable images and SVGs referenced by key in render instructions.

```json
{
  "assets": {
    "images": {
      "workers": "/assets/images/workers.png",
      "diagram": "/assets/images/force-diagram.png"
    },
    "svgs": {
      "work_flow": "/assets/svg/work-flow.svg",
      "circuit": "/assets/svg/circuit.svg"
    }
  }
}
```

- Paths are relative to the `storage/assets/` directory
- Reference by key name in render instructions: `"src": "workers"`
- Assets must be uploaded before processing

---

## 4. Scenes Array

Scenes define the logical sections of the video, played in order.

```json
{
  "scenes": [
    { "type": "question", ... },
    { "type": "options", ... },
    { "type": "visual_intro", ... },
    { "type": "concept", ... },
    { "type": "solution", ... },
    { "type": "answer", ... }
  ]
}
```

**Recommended order:** question → options (if MCQ) → concept → solution → answer

---

## 5. Scene Types

### 5.1 Question Scene

Displays the problem statement.

```json
{
  "type": "question",
  "text": "Which number is divisible by 9?",
  "audio": "Which number is divisible by nine?",
  "render": {
    "action": "show",
    "target": "question_block"
  }
}
```

### 5.2 Options Scene

Displays multiple choice options.

```json
{
  "type": "options",
  "render": {
    "action": "show",
    "target": "options_grid",
    "data": [
      { "key": "A", "value": "277218" },
      { "key": "B", "value": "123456" },
      { "key": "C", "value": "654321" },
      { "key": "D", "value": "111112" }
    ]
  }
}
```

### 5.3 Visual Intro Scene

Shows an image or diagram for context (no narration needed).

```json
{
  "type": "visual_intro",
  "render": {
    "action": "show",
    "target": "image",
    "src": "workers",
    "position": "center",
    "size": "medium"
  }
}
```

### 5.4 Concept Scene

Explains the underlying theory. Contains **steps**.

```json
{
  "type": "concept",
  "steps": [
    {
      "text": "Divisibility rule",
      "audio": "To check divisibility by nine, we add all digits of the number",
      "render": {
        "action": "show",
        "target": "concept_text"
      }
    },
    {
      "text": "If sum divisible",
      "audio": "If the sum of digits is divisible by nine, then the number is also divisible by nine",
      "render": {
        "action": "highlight",
        "target": "concept_text"
      }
    }
  ]
}
```

### 5.5 Solution Scene

Step-by-step problem solving. Contains **steps**.

```json
{
  "type": "solution",
  "option": "A",
  "steps": [
    { "text": "...", "audio": "...", "render": { ... } },
    { "text": "...", "audio": "...", "render": { ... } }
  ],
  "result": "correct",
  "verdict_audio": "Hence, option A is correct"
}
```

| Field | Description |
|-------|-------------|
| `option` | Which option is being solved (for MCQ) |
| `steps` | Array of step objects |
| `result` | `correct` or `incorrect` |
| `verdict_audio` | Final spoken conclusion |

### 5.6 Answer Scene

Displays the final answer.

```json
{
  "type": "answer",
  "text": "6 days",
  "audio": "The answer is six days",
  "render": {
    "action": "show_result",
    "target": "final_answer",
    "value": "6 days"
  }
}
```

---

## 6. Step Structure

Each step within a concept or solution scene.

```json
{
  "text": "2 + 7 = 9",
  "audio": "First, we take two and add seven, which gives nine",
  "render": {
    "action": "highlight",
    "target": "digits",
    "indices": [0, 1]
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Recommended | Short visual label shown on screen |
| `audio` | string | Recommended | Full spoken explanation (TTS input) |
| `render` | object | Recommended | What to display/animate on screen |

---

## 7. Render Object

Every render instruction tells the engine what to do visually.

```json
{
  "action": "show",
  "target": "equation",
  "value": "1/10 + 1/15",
  "data": [2, 7, 7, 2, 1, 8],
  "src": "work_flow",
  "expression": "27 ÷ 9 = 3",
  "position": "center",
  "size": "medium",
  "indices": [0, 1, 2],
  "timing": {
    "delay": 0,
    "duration": 0.5,
    "easing": "ease-in-out"
  },
  "style": {
    "color": "#00d4ff",
    "glow": true
  }
}
```

| Field | Type | When to use |
|-------|------|-------------|
| `action` | string | Always required |
| `target` | string | Always required |
| `value` | string/number | For equations, formulas, results |
| `data` | array | For digit_boxes, options_grid, tables |
| `src` | string | For images/SVGs (asset key name) |
| `expression` | string | For division_block |
| `position` | string | For images/SVGs placement |
| `size` | string | For images/SVGs sizing |
| `indices` | array | For highlighting specific items |
| `timing` | object | Optional animation timing |
| `style` | object | Optional visual overrides |

### Positions
`center`, `top`, `bottom`, `left`, `right`, `top-left`, `top-right`, `bottom-left`, `bottom-right`

### Sizes
`small` (25%), `medium` (50%), `large` (75%), `full` (90%)

---

## 8. Render Actions

| Action | Description | Example Use |
|--------|-------------|-------------|
| `show` | Display a new element | Show question, show equation |
| `hide` | Remove an element | Clear previous step |
| `highlight` | Emphasize an element | Highlight active digit, current formula |
| `update` | Change an element's value | Update equation from `1/10` to `3/30` |
| `animate` | Apply transition effect | Animate diagram |
| `show_result` | Display final output with emphasis | Show answer with green box |
| `draw_arrow` | Show directional flow | Point from one element to another |
| `zoom` | Focus on a specific area | Zoom into a part of diagram |
| `replace` | Swap one visual for another | Replace image with result |
| `sequence` | Execute multiple actions in order | Multi-part animation |

---

## 9. Render Targets

### Mathematics
| Target | Visual | Data |
|--------|--------|------|
| `question_block` | Question card at top | text from scene |
| `equation` | Centered math expression | `value`: "1/10 + 1/15" |
| `formula_block` | Named formula in card | `value`: "Work = 1/days" |
| `digit_boxes` | Individual digit boxes: [2][7][7] | `data`: [2,7,7] |
| `running_sum` | Progressive calculation display | `value`: 16 |
| `sum_box` | Final sum with border | `value`: 27 |
| `division_block` | Division expression | `expression`: "27 ÷ 9 = 3" |
| `final_answer` | Answer with green emphasis | `value`: "6 days" |

### Options
| Target | Visual | Data |
|--------|--------|------|
| `options_grid` | 2x2 option cards | `data`: [{key,value},...] |
| `option_A/B/C/D` | Highlight specific option | — |

### General
| Target | Visual | Data |
|--------|--------|------|
| `concept_text` | Theory explanation text | text from step audio |
| `instruction_text` | Step instruction | text from step |
| `image` | Image from assets | `src`: asset key |
| `svg` | SVG diagram from assets | `src`: asset key |
| `table` | Data table | `headers`, `rows` |

### Physics / Chemistry / Reasoning
| Target | Visual |
|--------|--------|
| `chemical_equation` | Chemical reaction display |
| `molecule_structure` | SVG molecular diagram |
| `pattern_grid` | Pattern display for reasoning |
| `number_series` | Number sequence |

---

## 10. Text vs Audio Rule

**Critical rule: text is SHORT, audio is DETAILED.**

| | Text (on screen) | Audio (spoken) |
|---|---|---|
| Purpose | Visual label | Full explanation |
| Length | 2-8 words | 1-3 sentences |
| Style | Symbolic, abbreviated | Conversational, beginner-friendly |
| Example | `"2 + 7 = 9"` | `"First, we take two and add seven, which gives nine"` |

The text appears on screen. The audio is spoken by TTS. They must convey the same step but the audio explains **why** while the text shows **what**.

---

## 11. Complete Examples

### Example 1: Simple Arithmetic

```json
[
  {
    "id": "q-add-001",
    "meta": {
      "subject": "Mathematics",
      "topic": "Arithmetic",
      "subtopic": "Addition",
      "difficulty": "easy"
    },
    "scenes": [
      {
        "type": "question",
        "text": "What is 48 + 35?",
        "audio": "What is forty eight plus thirty five?",
        "render": { "action": "show", "target": "question_block" }
      },
      {
        "type": "concept",
        "steps": [
          {
            "text": "Add units first, then tens",
            "audio": "In addition, we start by adding the units column, then move to the tens column. If the sum is more than nine, we carry over.",
            "render": { "action": "show", "target": "concept_text" }
          }
        ]
      },
      {
        "type": "solution",
        "steps": [
          {
            "text": "8 + 5 = 13",
            "audio": "First, add the units. Eight plus five equals thirteen. Write three, carry one.",
            "render": { "action": "show", "target": "equation", "value": "8 + 5 = 13 (carry 1)" }
          },
          {
            "text": "4 + 3 + 1 = 8",
            "audio": "Now the tens. Four plus three plus the carried one equals eight.",
            "render": { "action": "update", "target": "equation", "value": "4 + 3 + 1 = 8" }
          },
          {
            "text": "Answer: 83",
            "audio": "Therefore, forty eight plus thirty five equals eighty three.",
            "render": { "action": "show_result", "target": "final_answer", "value": "83" }
          }
        ]
      }
    ]
  }
]
```

### Example 2: MCQ with Digit Analysis

```json
[
  {
    "id": "q-div9-001",
    "meta": {
      "subject": "Mathematics",
      "topic": "Number System",
      "subtopic": "Divisibility by 9",
      "difficulty": "medium"
    },
    "scenes": [
      {
        "type": "question",
        "text": "Which number is divisible by 9?",
        "audio": "Which of the following numbers is divisible by nine?",
        "render": { "action": "show", "target": "question_block" }
      },
      {
        "type": "options",
        "render": {
          "action": "show",
          "target": "options_grid",
          "data": [
            { "key": "A", "value": "277218" },
            { "key": "B", "value": "123456" },
            { "key": "C", "value": "654321" },
            { "key": "D", "value": "111112" }
          ]
        }
      },
      {
        "type": "concept",
        "steps": [
          {
            "text": "Divisibility by 9",
            "audio": "A number is divisible by nine if the sum of its digits is divisible by nine.",
            "render": { "action": "show", "target": "concept_text" }
          }
        ]
      },
      {
        "type": "solution",
        "option": "A",
        "steps": [
          {
            "text": "Digits of 277218",
            "audio": "Let us check option A. The digits are two, seven, seven, two, one, and eight.",
            "render": { "action": "show", "target": "digit_boxes", "data": [2, 7, 7, 2, 1, 8] }
          },
          {
            "text": "2+7=9",
            "audio": "Two plus seven equals nine.",
            "render": { "action": "highlight", "target": "digits", "indices": [0, 1] }
          },
          {
            "text": "9+7=16",
            "audio": "Nine plus seven equals sixteen.",
            "render": { "action": "update", "target": "running_sum", "value": 16 }
          },
          {
            "text": "16+2=18",
            "audio": "Sixteen plus two equals eighteen.",
            "render": { "action": "update", "target": "running_sum", "value": 18 }
          },
          {
            "text": "18+1=19",
            "audio": "Eighteen plus one equals nineteen.",
            "render": { "action": "update", "target": "running_sum", "value": 19 }
          },
          {
            "text": "19+8=27",
            "audio": "Nineteen plus eight equals twenty seven.",
            "render": { "action": "update", "target": "running_sum", "value": 27 }
          },
          {
            "text": "Sum = 27",
            "audio": "The sum of all digits is twenty seven.",
            "render": { "action": "show_result", "target": "sum_box", "value": 27 }
          },
          {
            "text": "27 ÷ 9 = 3",
            "audio": "Twenty seven divided by nine equals three. It is divisible!",
            "render": { "action": "show", "target": "division_block", "expression": "27 ÷ 9 = 3" }
          },
          {
            "text": "Answer: A",
            "audio": "Therefore, option A is divisible by nine.",
            "render": { "action": "highlight", "target": "final_answer" }
          }
        ],
        "result": "correct",
        "verdict_audio": "Hence, option A is the correct answer."
      }
    ]
  }
]
```

### Example 3: Physics (Force)

```json
[
  {
    "id": "q-physics-force-001",
    "meta": {
      "subject": "Physics",
      "topic": "Mechanics",
      "subtopic": "Newton's Second Law",
      "difficulty": "medium"
    },
    "scenes": [
      {
        "type": "question",
        "text": "A 5 kg object accelerates at 3 m/s². Find the force.",
        "audio": "A five kilogram object accelerates at three meters per second squared. What is the force acting on it?",
        "render": { "action": "show", "target": "question_block" }
      },
      {
        "type": "concept",
        "steps": [
          {
            "text": "F = ma",
            "audio": "Newton's second law states that force equals mass times acceleration. F equals m times a.",
            "render": { "action": "show", "target": "formula_block", "value": "F = m × a" }
          }
        ]
      },
      {
        "type": "solution",
        "steps": [
          {
            "text": "m = 5 kg",
            "audio": "The mass is given as five kilograms.",
            "render": { "action": "show", "target": "equation", "value": "m = 5 kg" }
          },
          {
            "text": "a = 3 m/s²",
            "audio": "The acceleration is three meters per second squared.",
            "render": { "action": "show", "target": "equation", "value": "a = 3 m/s²" }
          },
          {
            "text": "F = 5 × 3",
            "audio": "Substituting into the formula, F equals five times three.",
            "render": { "action": "update", "target": "equation", "value": "F = 5 × 3" }
          },
          {
            "text": "F = 15 N",
            "audio": "Therefore, the force is fifteen Newtons.",
            "render": { "action": "show_result", "target": "final_answer", "value": "15 N" }
          }
        ]
      }
    ]
  }
]
```

---

## 12. Validation Rules

The engine validates your JSON **before** processing. Invalid JSON is rejected.

### Fatal Errors (processing stops)
- Missing `id` or duplicate `id`
- Missing `meta` or `meta.subject` or `meta.topic`
- Missing `scenes` array
- Invalid scene `type`
- Invalid render `action`

### Warnings (processing continues)
- Missing `text` or `audio` in a step
- Asset file not found on disk
- Invalid `position` or `size` value
- Unknown render target

### Best Practices
1. **One step = one idea.** Don't combine multiple operations in one step.
2. **Audio explains why.** Text shows what. Audio says why.
3. **Use Indian English for numbers.** "two lakh" not "two hundred thousand".
4. **Keep IDs unique and descriptive.** `q-div9-001` not `q1`.
5. **Order scenes logically.** Question → Options → Concept → Solution → Answer.
6. **Test with validation first.** Use the Validate button before processing.
