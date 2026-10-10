# Report format

Audit modes write exactly two files into `.design/`: a markdown file and an HTML file with the same stem. Nothing else. No summary file, no extra analysis document, no notes file.

The markdown is the source of truth, because it is structured for the next mode to read and apply. The HTML is what the user opens.

**Write the markdown first, then render:**

```bash
python <skill-dir>/scripts/render_report.py .design/smell-report.md
```

The script infers the report type from the filename and writes the sibling `.html`. Do not hand-write the HTML. If the script fails, report that and leave the markdown in place rather than substituting HTML of a different shape.

---

## Shared structure

All three reports use the same skeleton so the renderer and the treatment modes can rely on it.

```markdown
# <Report type> Report — <PROJECT OR TARGET NAME>

**Score:** <n>/10 · <LABEL>
**Target:** <path or "whole UI">
**Files read:** <n>
**Verified by:** <how you checked: rendered in browser / read source only / ran dev server>

## TL;DR

Two to four sentences. The single most important thing first. No preamble,
no "I analyzed your codebase and found several opportunities".

## <Scored table>

Mode-specific. See below.

## Priority issues

### P0 — <what is broken, stated as the problem not the fix>

What is wrong, where it is (file:line), and why it matters to a user or an
operator. Two to five sentences.

**Fix:** `/design <mode>` <optional one-line direction>

### P1 — <...>

### P2 — <...>

## Inspected, not flagged

Short list of things looked at that were fine, or that could not be verified.
Anything unverifiable is named as unverified here, never counted as healthy above.

## Next

One line naming the mode to run next and why.
```

Rules that apply to all three:

**Every finding needs a file and a line.** A finding you cannot point at was guessed, not found. If it is a whole-page property (rhythm, palette, register) name the files that establish it.

**Every measurable finding states the observed value and the threshold.** "Body text 2.54:1, needs 4.5:1" is actionable. "Contrast is too low" is not. Same for touch targets (observed vs 44x44), type steps (observed ratio vs 1.3), measure (observed ch vs 60-76), and input size (observed vs 16px). A reader should be able to tell when the fix is done without opening the reference.

**Say which rung of evidence each claim rests on.** Driven in a browser, measured headless, computed from declared values, parsed, or read. The `Verified by` line covers the report as a whole; anything that differs from it gets labelled inline. Computed is legitimate evidence. Computed presented as observed is not.

**Do not inflate scores to be polite.** Most real work lands in the middle. A 9 means there is very little left to do, and it should be rare.

**A score is never given without saying what would move it.** If a dimension scored 4, the report has to say what a 7 would look like.

**Priority is by cluster, not by count.** Six findings that all sit in the first viewport are one P0 with six pieces of evidence, not six P2s.

**Report modes never edit source.** Not even an obvious one-line fix. The report is the entire output.

---

## checkup-report.md

Fast triage. A vital-sign read, not a full critique. The question it answers is: is this safe to keep building on, or is something unsafe to ship.

Score line: `**Score:** 6/10 · BUILD WITH CARE`

Verdict labels: `HEALTHY`, `BUILD WITH CARE`, `UNSAFE TO SHIP`.

The scored table is vitals:

```markdown
## Vitals

| Vital | Status | Observed |
|---|---|---|
| Contrast | critical | Body text 2.9:1, tokens.css:14 on Card.tsx:22 |
| Focus visibility | critical | `outline:none` with no replacement, globals.css:40 |
| Touch targets | warning | Icon buttons 32x32, Toolbar.tsx:18 |
| Responsive integrity | healthy | Recomposes at 640 and 1024, no overflow |
| Type hierarchy | warning | h2 and h3 both 20px, 1.0 ratio |
| Color system | warning | 19 distinct hex values, no tokens |
| Control states | critical | No focus, loading, or error on the primary form |
| View states | unverified | Could not reach the empty state from the UI |
| Motion | healthy | No motion present, no reduced-motion violation |
| Dark mode | n/a | Not implemented |
```

Statuses: `healthy`, `warning`, `critical`, `unverified`, `n/a`.

**A vital that could not be verified is marked unverified, never healthy.** This is the rule that makes a checkup worth reading. Absence of evidence is not a pass.

Every critical gets a prescription in the priority issues section naming what is broken, why it matters, and which mode fixes it.

Next modes: `finish`, `recolor`, `relayout`.

---

## smell-report.md

The detector for reflex, template, and generated sameness. Read `ten-tells.md` first.

Score line: `**Score:** 4/10 · STRONG`

Labels: `CLEAN` (9-10), `FAINT` (7-8), `NOTICEABLE` (5-6), `STRONG` (3-4), `OVERPOWERING` (0-2).

The scored table is all ten tells, always all ten, in order, even the absent ones:

```markdown
## Heuristic scores

| # | Heuristic | Score | Key finding |
|---|---|---|---|
| 1 | tech gradient | 0 | Hero.tsx:12, indigo to magenta 135deg |
| 2 | generic tech hue | 0 | tokens.css:4, #6366F1 as --primary |
| 3 | feature tile grid | 0 | Features.tsx:31, three equal cards |
| 4 | accent rail | 1 | absent |
| 5 | centered stack | 0 | Hero.tsx:8, text-center on every section |
| 6 | glass and glow | 1 | absent |
| 7 | keyword iconography | 0 | Features.tsx:34, rocket, shield, sparkle |
| 8 | vague copy | 0 | Hero.tsx:15, "Built for scale" |
| 9 | badge and emoji chrome | 1 | absent |
| 10 | flat rhythm | 1 | py-24 varies by section, paced |
```

Score 0 means present, 1 means absent. A `0` needs a file and line. A `1` says `absent`.

Priority issues are clusters. The example above is one P0: the first viewport belongs to no product, evidenced by tells 1, 2, 3, 5, 7, and 8.

Next modes: `deslop`, `finish`.

---

## review-report.md

An honest design read. It walks the primary flow as a story and marks where the story breaks.

Score line: `**Score:** 6/10 · COMPETENT`

Labels: `EXCEPTIONAL` (9-10), `STRONG` (7-8), `COMPETENT` (5-6), `ROUGH` (3-4), `BROKEN` (0-2).

Two tables. First the dimensions:

```markdown
## Dimensions

| Dimension | Score | What would move it |
|---|---|---|
| Clarity of purpose | 4 | Say what the product does in the first sentence |
| Hierarchy | 5 | One focal object instead of four equal blocks |
| Craft | 7 | Fix the two spacing inconsistencies in the nav |
| Character | 3 | Any decision that could only belong to this product |
| States and edges | 2 | Empty, error, and loading for the results list |
| Accessibility | 4 | Restore focus rings, fix the 2.9:1 body text |
```

Then the walkthrough. Seven stages, each marked `ok` or `breaks`:

```markdown
## Walkthrough

| Stage | Reads as | Note |
|---|---|---|
| arrive | breaks | Nothing in the first screen names the product category |
| promise | ok | The subhead is specific about the outcome |
| act | breaks | Two primary buttons compete, neither is obviously first |
| respond | breaks | Submit gives no feedback for 1.2s |
| wait | breaks | No loading state, the layout jumps when results land |
| succeed | ok | Success confirmation is clear and stays visible |
| fail | breaks | Network error shows a raw message, no retry |
| resolve | ok | Clear path back to the start |
```

Stages: arrive, promise, act, respond, wait, succeed, fail, resolve.

Do not inflate. A score is never given without saying what would move it, which is why the third column is mandatory.

Next modes: `finish`, `refine`.

---

## Naming the project

The H1 uses the project's real name if one can be found in `package.json`, the page title, the logo alt text, or `brief.md`. If none exists, use the target path. Do not invent a brand name.
