# setup

Reads the repository and writes the project's design context so every later command is more specific.

**Type:** treatment. Writes one file, changes no source.
**Writes:** `.design/brief.md`
**Next:** `tokenize`, `redesign`

## What this is not

Not a requirement. `brief.md` is optional everywhere else. Modes work without it and never block on a missing file. If a later mode stops to ask for a brief, that mode is wrong.

Not an interview. Read the repository first and answer everything you can from it. Ask the user only about what genuinely cannot be inferred, and ask a few questions at once rather than one at a time.

Not invention. Where the repo does not say, the brief says unknown. A confidently wrong brief is worse than a short one, because every later mode will build on it.

## What to read

- `package.json`, `README`, and any docs folder for what the product is and who it is for.
- Existing design tokens, theme files, Tailwind config, CSS custom properties.
- The component library, if there is one, for conventions already in use.
- The primary pages and the surfaces users spend time in.
- Any existing brand assets: logo files, favicon, OG images, a marketing site in the repo.
- Copy already written. It carries the voice better than anything else.

## The brief

Write `.design/brief.md`. Keep it short enough that a mode reads it in seconds, because a brief nobody reads has no effect.

```markdown
# Design brief — <project>

## Product
What it does, in one sentence, in concrete nouns.

## Audience
Who uses it, how often, and under what conditions. Daily operator, one-time
visitor, expert, and beginner all imply different designs.

## Register
voice or surface, and why. If the project has both a marketing site and an
app, name the split by path.

## Work patterns
The dominant pattern per major surface. See references/work-patterns.md.

## Color
Commitment level, brand hue, and what earns it. Existing tokens if any.
Mark unknown rather than guessing.

## Type
Families in use, and whether they are loading. Scale ratio if one exists.

## Material
Elevation, radius, border, density. The position the product already takes.

## Constraints
Framework, styling approach, browser support, accessibility target, dark mode,
i18n and RTL, anything that limits what a mode may do.

## Conventions
Where tokens live, where components live, how styles are authored, naming
patterns already in use.

## Do not touch
Anything a mode must leave alone: vendor components, legacy areas mid-migration,
a brand mark that is fixed.

## Unknown
Explicitly listed. Each line is a question worth asking the user later.
```

## Blank projects

If there is no HTML, CSS, or JS to read, this mode has almost nothing to infer, so ask instead. Get the product, the audience, the register, and whether any brand exists. Then write the brief from the answers and record the design decisions in `.design/taste.md` as they get made, so later runs stay consistent rather than re-deciding.

## Procedure

1. Read the repository. Prefer evidence over assumption at every line.
2. Draft the brief, marking anything uncertain as unknown.
3. Ask the user about the unknowns that matter most, batched into one message. Three or four questions, not a form.
4. Write `.design/brief.md`.
5. Say what is still unknown and what would resolve it.

## Completion bar

- `.design/brief.md` exists and every section is either filled from evidence or marked unknown.
- Nothing is asserted that the repository does not support.
- No source file changed.
- The unknowns section is real, not empty for the sake of looking complete.

## Reporting back

Summarize what was inferred, what was asked, and what is still unknown. Then recommend the next command based on what the brief revealed: `tokenize` if values are scattered, `redesign` if the system is coherent but dated, `checkup` if something looked unsafe while reading.
