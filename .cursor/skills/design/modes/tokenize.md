# tokenize

Pulls proven repetition into reusable tokens and components, then migrates real usage.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `redesign`, `responsive`

## What this is not

Not a proposal. A list of suggested token names is not a tokenize pass. At least one real usage has to move over, and the old behavior has to be verified afterwards.

Not premature abstraction. Tokenize what has proven itself by repeating, not what might repeat. A token used once is a variable with extra steps, and a component abstracted from a single instance usually gets the interface wrong.

Not a rename. Changing `--blue-500` to `--color-primary-500` without changing what consumes it moves the problem rather than solving it.

## What earns a token

**Three or more uses** of the same value for the same reason. Two identical values that mean different things are two tokens, not one, and merging them is a bug waiting for the day one of them needs to change.

That last point is the whole discipline. If a border color and a divider color are both `#E5E5E5` today, they are still separate roles. The moment the border needs to darken, a shared token forces the divider to darken with it.

## Naming by meaning, not value

A name that describes the value lies as soon as the value changes.

| Bad | Good | Why |
|---|---|---|
| `--blue-600` | `--brand` | The hue can change. The role cannot. |
| `--red` | `--danger` | Danger might not be red in every theme. |
| `--spacing-16` | `--gap-section` | Says what it is for. |
| `--font-14` | `--text-meta` | Survives a scale change. |
| `--shadow-lg` | `--elevation-raised` | Elevation is the concept, shadow is one rendering of it. |

Two-layer naming works well at any size above trivial: a primitive layer holding raw scale values (`--n-500`, `--step-2`), and a semantic layer that maps roles onto them (`--text-muted: var(--n-500)`). Components only ever consume the semantic layer. Theming, dark mode, and rebrands then happen in one place.

## Procedure

**1. Inventory the repetition.** Grep for hardcoded values: hex and rgb colors, px and rem sizes, font sizes, radii, shadows, durations, z-index values. Count occurrences of each. The count is the evidence.

**2. Group by meaning, not by value.** Two `#E5E5E5` uses that mean different things stay apart.

**3. Check what already exists.** Many codebases have a half-built token layer plus a pile of values that never migrated. Extending the existing layer beats inventing a parallel one, and a parallel system is worse than none.

**4. Define the tokens.** Semantic names, two layers where it helps. Follow the role sets in `references/color.md` and `references/type.md`.

**5. Migrate real usage.** This is the pass. Start with the highest-count values, since they carry the most benefit and reveal naming problems fastest.

**6. Verify nothing changed visually.** A tokenize pass should be a no-op on screen. If something moved or changed color, either a value was mapped wrong or two roles were wrongly merged. Diff the rendered result, and check the states too, since hover and focus values are the ones most often missed in a migration.

**7. Extract components where markup repeats.** The same rule: three or more instances of the same structure with the same meaning. Get the props from what actually varies across the real instances, not from what might vary.

**8. Note what is left.** Values that did not meet the bar, or usages that could not be migrated safely, get listed rather than silently skipped.

## Completion bar

- Tokens are named by meaning. No value names survive in the semantic layer.
- Roles that share a value today but differ in meaning are kept separate.
- At least one real usage migrated per token defined. A token with no consumer is not done.
- The rendered result is visually unchanged, including hover, focus, and disabled states.
- Remaining un-migrated usages are listed by file.
- Extracted components are consumed in at least one real place.

## Reporting back

Report counts: values found, tokens defined, usages migrated, usages remaining. State that the visual result is unchanged and say how that was verified. A token defined but not consumed is *defined*, not *migrated*, and the summary must separate the two.
