# relayout

Changes structure, not spacing.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `responsive`, `interaction`

Read `references/work-patterns.md` before starting. This mode begins by naming the job.

## What this is not

Not spacing. Adjusting padding, tightening gaps, and fixing alignment are real work, but they are `finish`. If the composition after the pass is the same composition with different numbers, this was not a relayout.

Not a shuffle. Moving elements to look different without a reason produces a page that is differently wrong. Every structural change traces back to the work pattern the surface is meant to serve.

Not busywork. If the current structure already serves the pattern, say so and hand off. A relayout that cannot justify a structural change should route to `finish` rather than manufacture one.

## The required change

At least one visible structural change, drawn from this list:

- **A new focal point.** Something now leads that did not before.
- **A changed hero.** Different content type, different composition, different relationship between the text and the object.
- **A reordered sequence.** The order in which things are met has changed.
- **A different relationship between text and proof object.** Side by side instead of stacked, overlapping instead of separated, text over image instead of beside it.
- **Moved navigation.** Position, persistence, or grouping.
- **A transformed grid.** Equal columns become weighted. A grid becomes a list. A list becomes a table. A uniform set becomes one hero plus a compact remainder.

Spacing changes may accompany these. They cannot substitute for them.

## Procedure

**1. Name the work pattern for each zone.** lead, sequence, comparison, catalogue, dashboard, document, workspace. Say it out loud. This is the decision the rest of the pass follows from.

**2. Check the current structure against that pattern's demands and forbidden list.** The gap is the work.

The most common finding: the surface wants `lead` and is built as a centered stack with three equal tiles, which means nothing is ranked. Ranking is the design work that was skipped.

**3. Decide the focal object.** Say in one sentence what the eye lands on first. If you cannot, there is no hierarchy yet and that is the first thing to build.

**4. Restructure.** Change the DOM, not only the classes. Use `gap` on containers rather than margins on siblings, so the rhythm is owned in one place. Apply the 1-4-9 rhythm: 4px inside a component, 16px between components, 36px and multiples between sections.

**5. Watch the two rules that catch most mistakes.** A card inside a card is never right, so flatten it. Sibling margins fight, so replace them with a container gap.

**6. Verify it renders.** Look at it at a narrow width too, because a structural change that only works at 1440 is half a change. Full responsive recomposition is the next mode, but do not ship an obviously broken narrow view.

## Completion bar

- The work pattern is named for each zone the pass touched.
- At least one change from the required list happened, and it is visible in the rendered result.
- The focal object can be named in one sentence.
- Spacing uses `gap` on containers, following the 1-4-9 rhythm.
- No card sits inside a card.
- Nothing broke at 390px. If the narrow view needs real work, say so and hand off to `responsive`.

## Reporting back

Name the pattern, the structural change made, and the new focal object. If no structural change could be justified, say that plainly and recommend `finish` instead. Reporting "improved the layout" without naming which structural change happened is exactly the claim rule 3 forbids.
