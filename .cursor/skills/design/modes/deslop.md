# deslop

The treatment that follows the diagnosis. It replaces every generic tell with a decision that belongs to this product.

**Type:** treatment. Changes files.
**Reads:** all three reports in `.design/`, generating any that are missing.
**Next:** `checkup`, `finish`

Read `references/ten-tells.md` and `references/work-patterns.md` before starting.

## What this is not

Not a restyle. Swapping indigo for teal, or one gradient for another, scores exactly the same on a re-run. A replacement that is a different default is not a fix.

Not cosmetic-only. Tells 3, 5, and 10 are structural. If the fix for them is real, the DOM changes, not just the classes.

Not invention. Where the fix needs a fact the codebase does not contain (a real metric, a customer name, a product photograph), mark it `[NEEDS: ...]` in the copy or leave a placeholder comment. Never fabricate a statistic, a testimonial, or a logo wall to fill a slot. A made-up number is a worse failure than a vague sentence.

## Procedure

**1. Read the reports first.** Rule 2. Check `.design/` for `smell-report.md`, `checkup-report.md`, and `review-report.md`. Generate any that are missing by running that mode now. The smell report is the work list, the checkup catches anything unsafe that a smell pass would not see, and the review says what is already working and should be left alone.

**2. Order the work by structure first.** A new palette on a broken layout is still broken, so the sequence is:

1. Structure (tells 3, 5, 10). Ranking, focal point, pacing.
2. Substance (tells 7, 8). Real imagery, specific copy.
3. Surface (tells 1, 2, 4, 6, 9). Palette, gradients, chrome.

Doing this in reverse is the most common way a deslop pass produces a page that is different but equally generic.

**3. For each tell present, make an actual decision.** The reference file has the fix direction for each. The test for every one is the same: name what the replacement is answering. "Flat sand-colored field because the product photographs are the subject and a gradient competes with them" is a decision. "Changed to a solid color" is a coin flip that landed.

**4. Re-check for new tells.** A fix that introduces a different cliche is not a fix. Replacing three equal cards with three equal cards that have real photos is still tell 3 if nothing was ranked.

**5. Verify.** A tell counts as gone when it is gone from the rendered surface, not from the source you happened to edit. Use the highest rung of the evidence ladder in `SKILL.md` you can reach, and say which one you used.

Cheap checks worth running every time:

```bash
python <skill-dir>/scripts/contrast.py --css css/tokens.css   # new palette in gamut, and readable
python <skill-dir>/scripts/verify_static.py .                 # nothing dangling after the edits
```

**6. Offer to re-run `smell`.** The score moving from 4 to 9 is the proof this pass worked, and it costs one command.

## The bar for "fixed"

A smell counts as fixed only when all three hold:

1. **The old pattern is gone from the surface.** Not from one component while three others still ship it.
2. **The replacement is specific, not a different default.** It answers something about this product.
3. **No new smell appeared in its place.**

Anything that fails one of these is reported as *attempted* or *inspected*, not fixed. Rule 3 applies hardest here, because deslop is the mode most tempting to overclaim on.

## Completion bar

- Every tell scored 0 in the smell report is either fixed under the three-part bar above, or explicitly listed as not fixed with a reason.
- At least one structural change was made if tells 3, 5, or 10 were present. A deslop that only touched color when the layout was the problem did not do its job.
- The rendered result was checked, not just the source.
- No fabricated facts were introduced.
- The completion summary uses "fixed" only where the change is visible in the rendered result, and "inspected" everywhere else.

## Reporting back

List each tell that was present, and for each say fixed or not fixed with the decision made in a few words. Name the structural change explicitly. Then offer the re-run:

```
/design smell    # confirm the score moved
```
