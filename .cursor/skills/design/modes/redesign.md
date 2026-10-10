# redesign

A full visual transformation of an existing surface, handled as a system rather than a hero makeover.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `checkup`, `review`

## What this is not

Not a recolor plus a font change. If the old design is still recognizable after swapping colors and font sizes, the redesign failed. Someone who knew the old screen should have to look twice.

Not a hero makeover. Transforming the first viewport and leaving the rest on the old system produces a page that visibly changes hands halfway down. The system is the deliverable.

Not a rewrite of behavior. Appearance changes, logic does not. If a visual decision genuinely requires a behavior change, say so and get agreement rather than quietly making it.

## Procedure

**1. Name the register and the work pattern.** `voice` or `surface`, then the pattern per zone from `references/work-patterns.md`. A redesign without these named is a mood change.

**2. Decide the system before touching a component.** Four decisions, in this order, because each constrains the next:

1. **Structure.** What leads, what defers, what the pacing is.
2. **Type.** Family, ratio, scale, measure. See `references/type.md`.
3. **Color.** Commitment level, then hue, then ramps. See `references/color.md`.
4. **Material.** Elevation, radius, border, density, texture. Pick a position and hold it: flat and bordered, or raised and shadowed, or something with real texture. Mixing all three is how a redesign ends up looking like three redesigns.

Write these down before implementing. A redesign that decides component by component ends up inconsistent, which is the exact thing it was meant to fix.

**3. Implement the system in the token layer first.** Then migrate components onto it. If there is no token layer, either create one or note that `tokenize` should follow.

**4. Cover every surface, not just the loud one.** Navigation, headers, body, cards, forms, controls, tables, footers, all the semantic states, empty and error views. A component still on the old system is the tell that this was a hero makeover.

**5. Keep what was working.** If a `review` report exists, it names what already worked. Preserving a strong element is a decision, not a failure of ambition. Say which ones you kept and why.

**6. Do not reintroduce the tells.** A redesign is the easiest place to land back on indigo, a gradient hero, and three equal cards, because those are the median answers and this mode has the most freedom. Check the result against `references/ten-tells.md` before calling it done.

**7. Verify rendered.** At a narrow and a wide width, in dark mode if it exists, with real content rather than lorem.

## Completion bar

- Register and work pattern named.
- All four system decisions stated explicitly, with reasons.
- The system lives in tokens, and real components consume it.
- Every surface migrated, or the unmigrated ones listed by name.
- Behavior unchanged, or any change flagged and agreed.
- The result scores well against the ten tells. Run the check.
- Someone who knew the old design would not mistake this for a restyle.
- Rendered and checked at two widths minimum.

## Reporting back

State the register, the pattern, and the four system decisions in a few lines each. List what was migrated and what was deliberately kept. Then recommend `/design checkup` or `/design review` to confirm the new system holds up, because a redesign is the pass most likely to introduce new problems while fixing old ones.
