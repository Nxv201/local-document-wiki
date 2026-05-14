# Prompts: Explore PPTX Slide Content
> Mục đích: Extract context đầy đủ từ slide để làm input cho Wiki generation.
> Mỗi prompt được thiết kế cho một loại slide hoặc mục tiêu extract khác nhau.
> Nguyên tắc chung: **Describe only what you see. Never infer or add external knowledge.**

---

## Nhóm 1 — General Extraction (dùng cho mọi loại slide)

### G1 — Full Content Dump
> Khi nào dùng: Pass đầu tiên trên bất kỳ slide nào. Lấy hết tất cả thông tin có thể thấy.

```
You are extracting content from a technical training slide.

Extract and report ALL of the following that are present:

TEXT:
- Title (exact words)
- All bullet points or body text (exact words, preserve hierarchy)
- Any labels, captions, or annotations
- Any numbers, versions, or code snippets visible

VISUALS:
- Describe each diagram, chart, or illustration in detail
- For flowcharts: list all nodes and the connections between them
- For tables: reproduce the structure (rows, columns, cell content)
- For screenshots or UI images: describe what interface or output is shown

LAYOUT CLUES:
- Are text and visuals presented as separate sections, or are they interleaved?
- Does the visual appear to explain the text, or is it supplementary?

Rule: If something is not visible in the slide, do not include it.
```

---

### G2 — Slide Intent
> Khi nào dùng: Sau G1, để hiểu slide này đang cố nói điều gì trong context training.

```
Based only on what is shown in this slide, answer:

1. What is this slide trying to teach or communicate?
2. Who is the intended audience — beginner, intermediate, or advanced engineer?
3. Is this slide standalone, or does it appear to be part of a sequence
   (e.g., "step 2 of 4", "continued from previous")?
4. What would a reader need to already know to understand this slide?

Do not add information from outside the slide.
If you cannot determine the answer, say "Cannot determine from this slide."
```

---

## Nhóm 2 — Visual-Specific (dùng khi slide chứa hình/diagram)

### V1 — Flowchart & Diagram Extractor
> Khi nào dùng: Slide có sơ đồ luồng, state machine, sequence diagram, hoặc architecture diagram.

```
This slide contains a diagram. Analyze it carefully.

1. DIAGRAM TYPE: What kind of diagram is this?
   (flowchart / state machine / sequence diagram / block diagram / architecture / other)

2. COMPONENTS: List every node, block, or element with its label.

3. CONNECTIONS: Describe every arrow or connection:
   - From [element A] → to [element B]
   - Label on the arrow (if any)
   - Direction (one-way / two-way)

4. FLOW: Describe the overall flow or process from start to end in plain language.

5. PURPOSE: What concept or process does this diagram represent?

Only describe what is drawn. Do not assume or add steps not shown.
```

---

### V2 — Table Extractor
> Khi nào dùng: Slide có bảng so sánh, specification table, hoặc data table.

```
This slide contains a table. Extract it completely.

1. Reproduce the table in markdown format:
   | Column 1 | Column 2 | ... |
   |----------|----------|-----|
   | value    | value    | ... |

2. What is being compared or listed in this table?

3. Are there any highlighted cells, special markers, or footnotes?
   If yes, describe them.

4. What conclusion or key insight does this table convey?
```

---

### V3 — Code / Terminal Screenshot
> Khi nào dùng: Slide có screenshot code, terminal output, hoặc register dump.

```
This slide contains code or terminal output. Extract it carefully.

1. Reproduce the exact code or output text shown.
   Preserve indentation and formatting as closely as possible.

2. What programming language or environment is this? (C, Assembly, shell, etc.)

3. What does this code or output demonstrate?

4. Are there any highlighted lines, comments, or annotations pointing to specific parts?
   If yes, describe what they indicate.

Only transcribe what is visibly shown. Do not complete or fix the code.
```

---

### V4 — Mixed Slide (Text + Diagram Side by Side)
> Khi nào dùng: Slide có text bên trái và hình bên phải, hoặc ngược lại.

```
This slide has both text and a visual element. Analyze them together.

TEXT SIDE:
- Extract all text content exactly as written.

VISUAL SIDE:
- Describe the visual element in detail (see diagram/flowchart rules if applicable).

RELATIONSHIP:
- Does the visual illustrate the text, or does it add separate information?
- Is there a specific part of the text that corresponds to a specific part of the visual?
- Together, what complete concept do text + visual convey that neither conveys alone?
```

---

## Nhóm 3 — Sequence & Narrative (dùng cho nhiều slide liên tiếp)

### S1 — Slide Transition Analysis
> Khi nào dùng: Cho 2 slide liên tiếp. Hiểu mạch logic giữa chúng.

```
You are given two consecutive slides from a technical presentation.

SLIDE A (first):
[Attach slide A image]

SLIDE B (second):
[Attach slide B image]

Answer:
1. What does Slide A establish or introduce?
2. What does Slide B add, extend, or contrast compared to Slide A?
3. Is there a cause-effect, before-after, problem-solution, or overview-detail relationship?
4. Write one paragraph that combines both slides into a continuous explanation.

Use only information visible in the slides.
Mark anything uncertain with [UNCERTAIN].
```

---

### S2 — Section Summary (3–5 slides)
> Khi nào dùng: Cho một nhóm slide thuộc cùng một topic/chapter.

```
You are given [N] consecutive slides from a technical training presentation.
They form a section on a single topic.

For each slide, briefly note:
- Slide [number]: [one sentence — what this slide covers]

Then write a unified summary (3–5 paragraphs) that:
- Explains the topic as a whole
- Preserves the logical progression across slides
- Highlights the most important concepts, steps, or rules

Rules:
- Use only information visible in the slides
- Do not add background knowledge or external context
- If a visual cannot be understood without additional context, note it as [DIAGRAM: description]
```

---

## Nhóm 4 — Gap Detection (phát hiện thiếu context)

### D1 — Missing Context Detector
> Khi nào dùng: Sau khi đã extract, kiểm tra xem output có đủ để sinh Wiki không.

```
Review the content you just extracted from this slide.

Identify any GAPS — information that would be needed to fully understand
this topic but is NOT present in the slide:

1. MISSING DEFINITIONS: Are any terms used without being defined?
2. MISSING STEPS: Does any process appear to have steps omitted?
3. MISSING PREREQUISITES: Does the slide assume knowledge not shown?
4. AMBIGUOUS VISUALS: Are there diagrams or images whose meaning is unclear
   without additional context?
5. INCOMPLETE DATA: Are there partial tables, truncated code, or cut-off text?

For each gap found, rate its severity:
- [HIGH] — without this, the content would be misunderstood
- [MEDIUM] — reduces clarity but core message is still clear
- [LOW] — nice to have, but not essential
```

---

### D2 — Hallucination Boundary Check
> Khi nào dùng: Trước khi đưa extracted content vào Wiki generation, kiểm tra model có bịa không.

```
You previously extracted content from a slide.

Now verify your extraction:

1. For each specific claim in your extraction, confirm:
   "Is this directly visible in the slide?" (Yes / Inferred / Not visible)

2. List any item where your answer was "Inferred" or "Not visible".

3. Remove or flag those items in your extraction.

Output format:
VERIFIED CONTENT: [items confirmed as directly visible]
FLAGGED ITEMS: [items that were inferred or not visible — to be removed]
```

---

## Nhóm 5 — Wiki-Ready Output

### W1 — Wiki Section Generator
> Khi nào dùng: Final step — sau khi đã có extracted + verified content, sinh Wiki draft.

```
You are writing a section of a technical knowledge base Wiki.

INPUT: The following content was extracted from a training slide:
[Paste extracted content here]

Write a Wiki section that:
- Has a clear heading
- Explains the concept in 2–4 paragraphs of plain prose
- Preserves all technical details from the input
- Adds NO information beyond what was provided in the input
- Ends with a "Source" line: "Source: [filename], Slide [N]"

If the input contains gaps (marked as [HIGH] or [MEDIUM]), add a note:
> ⚠ This section may be incomplete. Refer to the original slide for full context.

Do not use bullet points unless the original content is a list.
Write for an engineer who is new to this topic.
```

---

## Tóm tắt — Khi nào dùng prompt nào

| Tình huống | Prompt gợi ý |
|------------|-------------|
| Slide bất kỳ, lần đầu | G1 → G2 |
| Slide có flowchart/diagram | G1 → V1 |
| Slide có bảng | G1 → V2 |
| Slide có code/terminal | G1 → V3 |
| Slide vừa text vừa hình | G1 → V4 |
| 2 slide liên tiếp | S1 |
| Một chapter (3–5 slide) | S2 |
| Kiểm tra trước khi sinh Wiki | D1 → D2 |
| Sinh Wiki draft | W1 |
