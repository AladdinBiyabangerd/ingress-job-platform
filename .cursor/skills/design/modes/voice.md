# voice

For marketing, landing, campaign, portfolio, and editorial surfaces, where the reaction at arrival is the deliverable.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `recolor`, `typeset`

## The register

Voice surfaces get one moment. A visitor arrives, decides in about two seconds whether this is for them, and leaves if the answer is unclear. That is a different job from an app screen, and it grants different permissions.

Expression is allowed to lead here. Asymmetry, large type, real photography, a strong point of view, and committed color are correct. Restraint is a choice available to you, not a default you owe anyone.

What is not permitted is expression standing in for substance. A beautiful page that does not say what the product is has failed at the only job it had.

## The first viewport test

The first screen has to answer three questions:

1. **What is this.** In concrete nouns. Not "the platform for modern teams".
2. **Who is it for.** Named, or clearly implied by the language and the imagery.
3. **Why this one.** What is true here that is not true of the alternatives.

If any of the three is missing, that is the finding, and it outranks anything about spacing or palette.

Apply the cover test: cover the logo, read the first screen, and ask what this company does. If the answer is "software", the page has not started yet.

## Rules with teeth

**A supplied name is used exactly as given.** If the user says the product is called `orbital`, it is `orbital`, not `Orbital` or `ORBITAL`. Casing is part of a name. Never re-style someone's brand without being asked.

**If the subject is physical, ship real imagery.** No colored rectangle stands in for the thing itself. A product photograph, a screenshot, a render, a diagram of the actual mechanism. A gradient placeholder where the product should be is the single largest failure available on a voice surface, because the visitor came to see the thing.

Where the real asset does not exist in the repo, leave an explicit, obvious placeholder that names what belongs there (`<!-- NEEDS: photograph of the mounted sensor, 3:2 -->`) rather than filling the hole with abstract decoration. A named gap is honest. A gradient is a lie that looks finished.

**Never fabricate proof.** No invented statistics, customer names, testimonials, or logo walls. Mark them `[NEEDS: ...]`.

**Copy rules still apply.** One verb per button. Sentence case. No exclamation points. The energy comes from specificity, not punctuation.

## Procedure

1. Name the work pattern. Most voice surfaces are `lead` at the top, then some mix of `sequence`, `comparison`, and `catalogue` below. Read `references/work-patterns.md`.
2. Run the first viewport test and the cover test. Write down what fails.
3. Find the subject. What is the actual thing this page is about, and is it visible anywhere on the page.
4. Fix substance before surface: what it is, who it is for, why this one, and the real imagery. A palette change on a page that does not say what the product does is wasted work.
5. Then commit on expression: type at a real display size, a hue that is earned, a composition with a focal point, pacing between sections.
6. Check against `references/ten-tells.md`. Voice is the register where the tells cluster hardest, because a marketing page is exactly what the median answer was trained on.
7. Verify rendered, at phone width too. Most marketing traffic is on a phone.

## Completion bar

- The first viewport answers what, who, and why this one, in concrete language.
- The cover test passes.
- If the subject is physical or visual, real imagery ships, or a named placeholder marks exactly what is missing.
- Any supplied name is used verbatim.
- No fabricated proof.
- The page has a focal point and a pacing, not a stack of equal sections.
- Checked against the ten tells after the pass.
- Rendered and checked at phone width.

## Reporting back

Quote the headline and subhead as they now read. Say what the first viewport answers and what it still does not. List any `[NEEDS: ...]` placeholders left behind, because those are the user's homework and they will not find them otherwise.
