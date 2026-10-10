# smell

A detector for reflex, template, and generated sameness. It answers one question: could anything on this surface only belong to this product.

**Type:** audit. Changes nothing.
**Writes:** `.design/smell-report.md` and `.design/smell-report.html`
**Next:** `deslop`, `finish`

Read `references/ten-tells.md` before starting. The ten tells, what counts as present, and the fix direction for each are all there.

## What this is not

Not a quality audit. A surface can score 10/10 on smell and still be a bad design, because absence of cliche is not presence of judgement. `review` handles quality.

Not a fix. Rule 1: write the report and stop.

Not a hunt. The score measures absence, so finding nothing is the perfect result. Do not manufacture a finding to look thorough. A 9 or 10 that is honest is more useful than a 5 that was padded.

## Procedure

**1. Name the work pattern first.** Read `references/work-patterns.md` and decide what each zone of the surface is for. This changes the scoring. Uniform cells in a genuine `catalogue` are correct and must not be scored as a feature tile grid, whereas the same cells on a `lead` surface are the tell. Scoring before naming the pattern produces false positives, which is the fastest way to make the whole report untrustworthy.

**2. Score all ten tells, in order, every time.** Even the absent ones appear in the table. A `0` means present and needs a file and a line. A `1` means absent and says `absent`.

**3. Weight the first viewport twice.** Identity is decided in the first screen. Three tells stacked above the fold is a different problem from three spread across a long page, and the priority section has to reflect that.

**4. Cluster into priority issues.** Severity is about clustering, not count.

One generic icon card is cleanup: a P2, fixed locally. A page built from an indigo gradient, a centered hero, three equal tiles, and vague copy is an identity failure: one P0 with the individual tells as evidence beneath it, and the fix is a new lane rather than a patch.

Write the P0 as the problem, not the fix. "The first viewport belongs to no product" is a problem. "Change the gradient" is a task.

**5. Apply the cover test to copy.** Cover the logo and read the page. If the answer to "what does this company do" is "software", tell 8 is present regardless of how polished the sentences are.

**6. Write and render.**

```bash
python <skill-dir>/scripts/render_report.py .design/smell-report.md
```

## Scoring

Total out of 10, one point per absent tell.

| Score | Label |
|---|---|
| 9-10 | CLEAN |
| 7-8 | FAINT |
| 5-6 | NOTICEABLE |
| 3-4 | STRONG |
| 0-2 | OVERPOWERING |

The label describes the strength of the smell, so a low score carries a strong label. Do not soften it. A page that is genuinely a template deserves to be told so, because the whole value of this mode is that it says the thing a polite reviewer would not.

## Completion bar

- All ten tells scored, in order, with a file and a line behind every `0`.
- The work pattern is named for each zone, and the scoring respects it.
- Priority issues are clustered, not one per tell.
- Every priority issue names a mode as its fix.
- Both `.md` and `.html` exist in `.design/`.
- No source file changed.

## Reporting back

Score, label, the count of tells present, the single biggest cluster in one sentence, and the next command. Keep it to a few lines.
