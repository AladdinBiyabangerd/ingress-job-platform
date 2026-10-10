# Color

Two decisions come before the hue, and skipping them is how every project ends up indigo.

## 1. Pick the commitment level first

How much of the surface is color allowed to occupy. This is a bigger decision than which hue, because it sets the whole character.

| Level | Chroma range | What it looks like | Right for |
|---|---|---|---|
| **whisper** | 0.02 to 0.06 | Near-neutral UI. Color appears only in state and one accent. | Tools, dashboards, anything used all day. Editorial with strong photography. |
| **statement** | 0.10 to 0.18 | One saturated hue owns the brand moments. Neutrals everywhere else. | Most products. The safe, correct default. |
| **conversation** | 0.10 to 0.18 on two hues | Two hues in dialogue, one lead and one counter, roughly 3:1 in use. | Products with two real modes or two audiences. Editorial. |
| **flood** | 0.15 to 0.25 | Color is the surface. Large fields of hue, neutrals are the accent. | Campaign pages, launches, portfolio, anything with one moment to land. |

The surface register constrains this. A `surface` register (dashboards, admin, tools) lives at whisper or statement. Flood on an app screen is noise that an operator has to look past a hundred times a day. A `voice` register can go anywhere.

State the level chosen and why in the completion summary.

## 2. Earn the hue

A hue is earned by something outside the interface:

- **The subject.** What the product actually touches. Soil, blood, ocean, steel, paper, night sky, currency.
- **The physical product.** If there is a real object, its real color.
- **The industry's opposite.** A deliberate break from what the category defaults to, which is itself a decision as long as you can say what you are breaking from.
- **Inheritance.** An existing brand, a parent company, a heritage mark.
- **The data.** Where the palette is carrying meaning, the semantics come first and the brand color has to fit around them.

Never default to indigo. Also do not simply swap indigo for teal, since an unearned hue scores the same as the default. If nothing earns a hue, that is a signal the level should be whisper and the interface should carry its character through type and composition instead.

---

## OKLCH

Author in OKLCH. It is perceptually uniform, so equal lightness numbers look equally light across hues, which is what makes a generated scale usable without hand-fixing every step.

```css
:root {
  /* L        C      H */
  --brand:   oklch(0.58 0.14 42);
  --brand-hi:oklch(0.68 0.13 42);
  --brand-lo:oklch(0.44 0.13 42);
}
```

**Lightness** (0 to 1) is the one that carries hierarchy. Build the scale by moving L in even steps.

**Chroma** (0 upward, roughly 0.37 max in sRGB) is the commitment level from above.

**Hue** (0 to 360) stays fixed across a family. Changing hue between steps of the same scale is what makes a palette look muddy.

### Clamp chroma at the extremes

Lightness above about 0.92 or below about 0.25 cannot hold high chroma. Push it and the color either clips out of gamut or turns to mud. Taper it:

```css
--brand-50:  oklch(0.97 0.02 42);   /* chroma pulled way down */
--brand-100: oklch(0.94 0.04 42);
--brand-300: oklch(0.80 0.10 42);
--brand-500: oklch(0.62 0.15 42);   /* peak chroma near mid lightness */
--brand-700: oklch(0.46 0.13 42);
--brand-900: oklch(0.30 0.07 42);   /* pulled down again */
```

Peak chroma sits near the middle of the lightness range, not at the ends.

### Neutrals carry a trace of the brand hue

Pure grey next to a saturated brand color looks dead and slightly wrong. Give the neutral ramp the brand hue at very low chroma:

```css
--n-0:  oklch(0.99 0.003 42);
--n-100:oklch(0.96 0.005 42);
--n-500:oklch(0.55 0.012 42);
--n-900:oklch(0.18 0.010 42);
```

Chroma of 0.003 to 0.015 is enough. Above that the neutrals stop reading as neutral.

---

## The 60-30-10 split

Roughly 60% dominant (usually the neutral field), 30% secondary (surfaces, borders, muted text), 10% accent (the brand hue and the primary action).

This is a check, not a formula. If the brand hue is covering half the screen at statement level, the level was wrong or the hue leaked into places it does not belong. Look at the actual rendered page, squint, and estimate.

At flood level the ratio inverts, which is the point of the level.

---

## Semantic roles

Roles are named by job, never by value. `--danger`, not `--red`. When the palette changes, a role name survives and a color name lies.

Minimum role set for any real interface:

```
background, surface, surface-raised, border, border-strong,
text, text-muted, text-inverse,
brand, brand-hover, brand-active, brand-subtle,
success, warning, danger, info  (each with a subtle background variant)
focus-ring
```

Every role has to appear on real UI before a `recolor` is complete. Defining tokens is not a color pass. Navigation, page header, body, controls, cards, forms, states, and at least one edge case all need to be checked against the new palette in the rendered result.

Danger and success must not rely on hue alone, because roughly 1 in 12 men cannot separate red from green. Pair them with an icon, a label, or a position.

---

## Contrast

| Content | Minimum |
|---|---|
| Body text | 4.5:1 |
| Large text (18.66px bold or 24px) | 3:1 |
| Icons and control boundaries | 3:1 |
| Focus ring against both the control and the page behind it | 3:1 |
| Disabled text | exempt, but still needs to read as disabled |

Check the real pairs on the page, not the token against white. A muted text token on a raised surface is a different pair from the same token on the page background.

In OKLCH, a lightness difference of about 0.35 usually clears 4.5:1 for text on a neutral background, which is a useful first guess. It is a guess, not a result. Compute the real ratio before claiming a fix.

## Color vision

Check the palette under **deuteranopia**, **protanopia**, and **tritanopia** before calling a `recolor` done. The failures to look for:

- Success and danger collapsing into the same color. Most common, and most serious.
- A categorical chart palette losing two series to each other.
- A selected state that is only signalled by a hue change.
- Link color that stops separating from body text.

The fix is not always a new hue. Adding a lightness difference between two colors that share a hue problem usually solves it and costs nothing.

## Dark mode

Dark mode is not an inversion.

- Raise the dark background off pure black, around L 0.15 to 0.20. Pure black plus high contrast text causes halation.
- Lower chroma across the board. The same chroma reads far more saturated on dark.
- Elevation is lighter, not shadowed. Shadows barely read on dark, so raised surfaces step up in lightness instead.
- Re-check every contrast pair. A ratio that passed on light does not carry over.

---

## Auditing color

1. Find where color actually comes from. A hex in a component may be the last holdout of a token defined three files up.
2. Count the distinct colors in use. More than about 12 non-scale values means there is no system, and the answer is `tokenize`.
3. Look for the tells: indigo family default, decorative two-hue gradient, color used as decoration where it carries no meaning. See `ten-tells.md`.
4. Check the split by squinting at the rendered page.
5. Run the contrast pairs.
6. Run the three color vision checks.
7. Check dark mode if it exists. If it does not, say so rather than pretending it was checked.
