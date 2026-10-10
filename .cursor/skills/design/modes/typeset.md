# typeset

Builds or repairs a type system across every text role in the product.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `responsive`, `recolor`

Read `references/type.md` before starting. The roles, ratios, measures, and the loading checks are there.

## What this is not

Not a font-size tweak. Changing only the hero headline does not count as a type pass unless that is exactly what was asked for. The roles that break a system in production are the boring ones: metadata, form labels, button text, empty state copy, error copy. If the pass did not touch those, it was a headline edit.

Not a font swap. Picking a nicer family without fixing scale, measure, and leading leaves every original problem in place, now in a different typeface.

Not a token dump. Defining `--step-0` through `--step-6` and stopping is a definition, not a system. Real usage has to move onto the scale.

## Procedure

**1. Inventory what is actually rendered.** List every distinct font size, weight, line height, and family in use on the target. This is the diagnosis and it usually is the whole story: more than about eight sizes means there is no scale, and two adjacent sizes 1px apart means two steps are pretending to be one.

**2. Decide the scale.** Pick a ratio of at least 1.3 (see the table in `type.md`) and generate four to six steps, not eleven. Prefer `clamp()` over breakpoint stacks, and cap the top so display type does not run away on a wide monitor.

**3. Assign every role.** Work down the role table in `type.md`: display, headings, body, lead, small print, labels, buttons, form input, metadata, code and numerals, state copy, inline links. Each one gets a size, weight, line height, and tracking. A role you skipped is a role that will be wrong later.

**4. Fix measure and leading.** Body at 60 to 76ch, set on the text container. Leading moves opposite to size. Space above a heading larger than the space below it, using `gap` on the container rather than sibling margins.

**5. Migrate real usage.** Move components onto the scale. This is the part that makes it a pass rather than a proposal. If the codebase has a token layer, change the tokens and let consumers inherit. If it does not, that is a finding: hand off to `tokenize`.

**6. Handle numerals.** `font-variant-numeric: tabular-nums` on anything in a column, a table, a timer, or a changing price.

**7. If the family changed, verify it loads.** A name in a style value is not a loaded font. Check the network request, the computed style, or that the `@font-face` src resolves. Set `font-display: swap`, preload above-the-fold faces, and give a fallback with similar metrics. This is the single most common false claim in a type pass, so do not skip it.

## Completion bar

- Every role in the table has a defined treatment, or is explicitly listed as not present in this product.
- Adjacent hierarchy steps are at least 1.3 apart.
- Body measure lands between 60 and 76ch in the rendered result, measured not assumed.
- Form inputs are at least 16px at mobile widths.
- Real components consume the scale. Tokens alone do not count.
- If the family changed, the font is confirmed to load, and the summary says how that was confirmed.
- The rendered result was checked at a narrow and a wide viewport.

## Reporting back

Name the ratio and the step count. List which roles changed and which were already correct. If the font changed, state how the load was verified. Anything defined but not yet consumed by a component is *inspected*, not *fixed*.
