# recolor

Builds or repairs a color system in OKLCH, then applies it to real components.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `responsive`, `motion`

Read `references/color.md` before starting. Commitment levels, OKLCH construction, the 60-30-10 check, roles, contrast, and the color vision checks are all there.

## What this is not

Not an accent swap. Changing `--primary` and calling it a color pass leaves every hardcoded hex, every unearned gradient, and every failing contrast pair exactly where they were.

Not a token file. A palette that exists only in `:root` has not been applied. Every role has to appear on real UI before this mode is complete.

Not indigo. Also not indigo with the hue rotated 40 degrees so it technically is not indigo. An unearned hue scores the same as the default, so if nothing earns a hue, drop to whisper level and let type and composition carry the character.

## Procedure

**1. Audit what exists.** Find where color actually comes from. Count distinct non-scale values. A hardcoded hex in one component may be the last holdout of a token defined three files up, and changing the wrong one leaves the system inconsistent. If there are more than about 12 loose values, note that `tokenize` is the real follow-up.

**2. Pick the commitment level before the hue.** whisper, statement, conversation, or flood. The register constrains it: a `surface` register lives at whisper or statement, because flood on a screen an operator opens fifty times a day is noise they have to look past every time. Say the level out loud.

**3. Earn the hue.** The subject, the physical product, the category's opposite, or an inheritance. Write down the reason. If there is no reason, that is a real answer, and the answer is whisper.

**4. Build the ramps in OKLCH, and test them while they are still a draft.** Even lightness steps, fixed hue within a family, chroma peaking near mid-lightness and tapering at both ends. Give the neutral ramp the brand hue at 0.003 to 0.015 chroma so it does not read dead beside the brand.

Check the ramp **before** you apply it to anything:

```bash
python <skill-dir>/scripts/contrast.py --pair "oklch(0.55 0.14 42)" "#ffffff"
python <skill-dir>/scripts/contrast.py --cvd "oklch(0.45 0.13 155)" "oklch(0.55 0.19 26)"
```

This ordering matters more than it looks. An out-of-gamut color gets clipped by the browser, which silently changes the hue you designed, and a 3.3:1 pair is a rewrite. Both cost nothing to fix while the ramp is a draft and cost a migration once 40 components consume it. Write the candidate values, run the checks, fix what fails, and only then apply.

**5. Define roles by job, never by value.** `--danger`, not `--red`. Cover the full minimum role set in `color.md`, including the focus ring, which is the one everyone forgets.

**6. Apply to real components.** This is the pass. Every role has to appear on real UI: navigation, page header, body text, controls, cards, forms, all the semantic states, and at least one edge case such as a nested surface, a disabled control on a raised card, or a badge on a colored background.

**7. Run the checks.** Write the real pairs to a file and check them in one pass rather than one at a time:

```bash
# pairs.txt:  name | foreground | background [| large]
#   body on page      | var value | var value
#   muted on raised   | ...       | ...
python <skill-dir>/scripts/contrast.py --pairs pairs.txt
python <skill-dir>/scripts/contrast.py --css css/tokens.css
```

- Contrast on the real pairs as rendered, not tokens against white. A muted token on a raised surface is a different pair from the same token on the page background.
- 60-30-10 by squinting at the rendered page. If the brand hue covers half the screen at statement level, something leaked.
- Deuteranopia, protanopia, tritanopia via `--cvd`. The failure to hunt for is success and danger collapsing together. Note that the tool reports a MARGINAL band: two colors separated only by a thin lightness difference are not safe, they are lucky, and a default green/red pair usually lands there.
- Dark mode if it exists: raised background off pure black, chroma lowered, elevation by lightness not shadow, every pair re-checked.

## Completion bar

- The commitment level and the reason for the hue are both stated.
- The ramp was checked with `contrast.py` before it was applied, not after.
- No color is outside the sRGB gamut, or any exception is named.
- Ramps are OKLCH, with chroma tapered at the lightness extremes.
- Neutrals carry a trace of the brand hue.
- Every semantic role appears on at least one real component in the rendered result.
- Contrast checked on real rendered pairs, with the failing ones fixed or listed.
- All three color vision checks run, with what was found.
- Danger and success are separable without hue.
- Dark mode re-checked, or explicitly reported as not implemented.

## Reporting back

State the level, the hue, and why that hue. List the roles now live on real components. Report the contrast and color vision results as findings, including anything still failing. A role defined but not yet used by any component is *inspected*, not *applied*, and the summary has to say so.
