# refine

Changes the character of a design. The diagnosis picks the move.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `finish`, `responsive`

## What this is not

Not a polish pass. One hover effect or one copy edit is not a refinement. Character is a property of the whole surface, so a refinement that touched one component did not change anything.

Not everything at once. Opposing moves are not combined unless the surface has separate zones that genuinely need separate treatment. Pushing and settling the same zone means neither happened.

Not a substitute for structure. If the problem is that nothing is ranked, the answer is `relayout`. Refine works on a composition that is already sound.

## The five moves

Diagnose first, then pick. Naming the move is most of the work, because the wrong move applied well makes things worse than the right move applied roughly.

### push
Raise the energy. Bigger type, higher contrast, bolder weights, more committed color, tighter tracking on display, a real focal moment.

**For:** surfaces that are timid. Everything is medium grey at medium size, nothing is loud, the page reads as a wireframe someone forgot to finish.

**Fails when:** the surface was already loud. Then it becomes noise.

### settle
Lower the noise. Fewer competing elements, calmer color, restored alignment, more space, less contrast between things that are not actually different.

**For:** surfaces that shout. Four things fighting to be first, three accent colors, every element with a shadow and a border and a gradient.

**Fails when:** applied to something that was already quiet. Then it disappears.

### strip
Remove until only what earns its place remains. Delete decorative elements, redundant labels, dividers that separate nothing, icons that restate their headings, wrappers that wrap one thing.

**For:** surfaces carrying accumulated debris from earlier directions.

**Test:** remove it and see whether anyone would miss it. If not, it was debris.

### texture
Add material character. Grain, rule lines, real photography, tighter typographic detail, considered borders, a hint of paper or ink or metal, a deliberate edge treatment.

**For:** surfaces that are technically correct and completely flavourless. Well-spaced, well-typed, and indistinguishable from every other well-made thing.

**Fails when:** applied before structure and type are sound. Texture on a broken layout is decoration on a problem.

### proof
Replace claims with evidence. Real numbers, real screenshots, real names, real logs, the actual object. Anything a reader has to take on faith becomes something they can see.

**For:** surfaces where the copy is doing all the work and none of it is checkable.

**Never fabricate.** If the real number is not available, mark it `[NEEDS: ...]` and say so. An invented statistic is a worse outcome than a vague sentence.

## Opposing pairs

`push` opposes `settle`. `strip` opposes `texture`.

Do not run both halves of a pair on the same zone. Running them on different zones is fine and sometimes exactly right: settle a busy dashboard header while pushing the one metric that matters.

`proof` composes with any of the others.

## Procedure

1. Read the surface and name the problem in one sentence. Timid, shouting, cluttered, flavourless, or unsupported.
2. Pick one move. Two only if there are genuinely separate zones, and say which move applies to which zone.
3. Apply it across the whole surface or the whole zone, not to one component.
4. Check the result against the ten tells, since `push` and `texture` are the moves most likely to reintroduce a gradient or a glow.
5. Verify rendered. Character is not visible in a diff.

## Completion bar

- The move is named, with the one-sentence diagnosis that chose it.
- It was applied across the whole surface or a clearly named zone.
- Opposing moves were not combined on the same zone.
- The rendered result is visibly different in character, not just in detail.
- No new tells were introduced.
- No facts were fabricated in a `proof` pass.

## Reporting back

Name the diagnosis, the move, and the scope. Then say what visibly changed. If the honest answer is that the change is subtle, say subtle, because a refine pass that claims a transformation it did not make is the exact failure rule 3 exists to catch.
