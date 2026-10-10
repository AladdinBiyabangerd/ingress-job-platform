# review

An honest design read. It walks the primary flow as a story and marks where the story breaks.

**Type:** audit. Changes nothing.
**Writes:** `.design/review-report.md` and `.design/review-report.html`
**Next:** `finish`, `refine`

## What this is not

Not encouragement. Scores are not inflated to be polite. Most real work lands in the middle, and a review that tells everyone they are at 8 is worth nothing to anyone. If the honest number is 4, write 4 and say what a 7 looks like.

Not a checklist. `checkup` covers whether things are broken. This mode covers whether the design is any good, which is a different question and needs judgement rather than measurement.

Not a fix. Rule 1: report and stop.

## The story

Design work is judged by what happens to a person moving through it, not by a screenshot. So walk the primary flow in order and mark where it breaks.

| Stage | The question |
|---|---|
| **arrive** | In the first two seconds, what is this and is it for me. |
| **promise** | What does it claim, and is the claim specific enough to be checkable. |
| **act** | What is the one thing to do here, and is it obviously first. |
| **respond** | Does the interface acknowledge the action immediately. |
| **wait** | What happens during the gap. Is there a state, does the layout hold still. |
| **succeed** | Is it clear the thing worked, and does the confirmation stay long enough to read. |
| **fail** | What happens when it does not work. Is there a way out and a way to retry. |
| **resolve** | What now. Is there a next step, or a clean way back. |

Each stage gets `ok` or `breaks`, with one line saying why. A stage that could not be exercised is marked `unverified`, not `ok`.

Pick the primary flow deliberately and name it in the report. On a landing page that is arrive through to the first conversion action. In an app it is the task the product exists to do. Reviewing a flow nobody uses produces findings nobody cares about.

## Dimensions

Six dimensions, each scored out of 10, each with a third column saying what would move it. That column is mandatory: a score without a path is a verdict, not a review.

| Dimension | What it measures |
|---|---|
| Clarity of purpose | Can a first-time visitor say what this is and who it is for. |
| Hierarchy | Does the composition rank things, and does the ranking match what matters. |
| Craft | Consistency, alignment, spacing discipline, the small things that signal care. |
| Character | Is there a point of view. Could this only be this product. |
| States and edges | Empty, loading, error, overflow, long strings, zero results, realistic volume. |
| Accessibility | Contrast, focus, keyboard path, touch targets, labels, reduced motion. |

Overall score is the honest weighted read, not the mean. A surface that is beautiful and unusable is not a 6. Say which dimensions drove the number.

| Score | Label |
|---|---|
| 9-10 | EXCEPTIONAL |
| 7-8 | STRONG |
| 5-6 | COMPETENT |
| 3-4 | ROUGH |
| 0-2 | BROKEN |

## Procedure

1. Name the work pattern and register. Read `references/work-patterns.md`. A dashboard judged against marketing criteria produces nonsense findings.
2. Name the primary flow.
3. Walk it, stage by stage. Use the running interface if there is one. Note what could not be exercised.
4. Score the six dimensions, each with a "what would move it".
5. Write priority issues by cluster, worst first. Each one names a mode as its fix.
6. Say what is genuinely working, briefly, in `Inspected, not flagged`. Not as a cushion, but because a treatment mode needs to know what not to touch.
7. Write and render.

```bash
python <skill-dir>/scripts/render_report.py .design/review-report.md
```

## Completion bar

- All eight story stages marked, with a reason on every `breaks`.
- All six dimensions scored, each with a concrete "what would move it".
- The primary flow, work pattern, and register are all named in the report.
- Priority issues are clustered and each names a fix mode.
- Anything not exercised is marked unverified rather than passed.
- Both `.md` and `.html` exist. No source file changed.

## Reporting back

Overall score and label, the two lowest dimensions, the stage where the story first breaks, and the next command. A few lines, not the report.
