# Typography

A type system is not a font size. It is every text role in the product answered consistently, including the ones nobody looks at until they are ugly in production.

## The roles

A `typeset` pass covers all of these. Changing only the hero headline does not count as a type pass unless that is exactly what was asked for.

| Role | What it needs |
|---|---|
| Display | Hero and section peaks. The only place tight tracking belongs. |
| Headings h1 to h4 | A scale with real ratios between steps, and a defined space above and below. |
| Body | Measure, leading, and a size that survives on a phone. |
| Lead / intro | A larger body variant that is not just a bigger paragraph. |
| Small print | Captions, footnotes, legal. Still has to be readable, so not 11px grey on grey. |
| Labels | Form labels, field names. Always visible, never replaced by a placeholder. |
| Buttons and controls | Usually needs its own size and weight, and often tighter than body. |
| Form input text | At least 16px on mobile or iOS Safari zooms the page on focus. |
| Metadata | Timestamps, counts, statuses, breadcrumbs. The most commonly forgotten role. |
| Code and numerals | Tabular figures for anything in a column. A mono face if code appears. |
| Empty, error, loading copy | These are type roles too, and they are where systems fall apart. |
| Links inline in body | Distinguishable from body text by more than color alone. |

If the pass did not touch metadata, form text, and state copy, it was a headline tweak.

---

## Scale

**Minimum 1.3 ratio between hierarchy steps.** Below that, two steps read as a rendering accident rather than a decision. Common working ratios:

| Ratio | Character |
|---|---|
| 1.200 | Too tight for headings. Fine inside a dense UI. |
| 1.333 | Reliable general purpose. |
| 1.414 | Confident, good for marketing. |
| 1.500 | Strong contrast, needs space to breathe. |
| 1.618 | Dramatic. Works when there are few steps. |

Do not use every step the ratio generates. Four to six sizes is a system. Eleven is a spreadsheet.

Hierarchy is carried by more than size: weight, color, spacing, and case all contribute. Two elements at the same size can sit at different levels if weight and color say so. This matters most in dense UI where you have run out of room to grow.

Fluid sizing with `clamp()` is preferred over a stack of breakpoint overrides:

```css
--step-0: clamp(1rem, 0.95rem + 0.25vw, 1.125rem);
--step-3: clamp(2rem, 1.6rem + 2vw, 3.5rem);
```

Cap the top so display type does not become absurd on a 32 inch monitor.

---

## Measure and leading

**Body measure 60 to 76ch.** Wider and the eye loses its return line. Narrower and it breaks too often. Set it with `max-width: 68ch` on the text container, not on a wrapper that also holds images.

Leading moves opposite to size:

| Size | Line height |
|---|---|
| Display 48px and up | 1.0 to 1.1 |
| Headings | 1.15 to 1.3 |
| Body | 1.5 to 1.65 |
| Small print | 1.4 to 1.5 |

Tight leading on body text is the most common readability failure. Loose leading on display type is the most common polish failure.

Tracking: negative on display (about -0.02em), zero on body, slightly positive on small uppercase (about 0.05em). Never track out body text.

## Spacing around text

Space above a heading is larger than the space below it, so the heading groups with the content it introduces. Getting this backwards is why some pages feel like a list of disconnected blocks.

Use `gap` on the container rather than margins on siblings, so the rhythm is owned in one place.

---

## Choosing faces

Three fonts only when each has a distinct role: **display**, **body**, **UI**. Two is usually enough. One well-chosen family with a real weight range is a legitimate answer and is often the strongest one.

Pairing that works: high contrast in one axis, agreement in the others. A geometric sans display over a humanist sans body works because the skeletons differ while the proportions agree. Two similar grotesques fight.

Match x-height between paired faces or the body will look wrong beside the heading at the same nominal size.

## Loading and fallbacks

If the font changes, **verify the font actually loads**. A name in a style value is not a loaded font, and this is the single most common false claim in a type pass. Check the network request, or check the computed style in the browser, or confirm the `@font-face` and the file path resolve.

- `font-display: swap` so text is readable during load.
- Preload the one or two faces used above the fold.
- Set a real fallback stack with similar metrics, and use `size-adjust` if the swap causes a visible jump.
- Subset to the characters actually used if the file is large.
- Variable fonts beat four static weights on file size once you need more than two weights.

## Numerals

Tabular figures for anything in a column, a table, a timer, or a price that updates:

```css
font-variant-numeric: tabular-nums;
```

Proportional figures elsewhere. Without this, numbers jitter as they change, which reads as a bug.

---

## Auditing type

1. List every distinct font size actually rendered on the target. More than about eight means there is no scale.
2. Compute the ratio between adjacent steps. Anything under 1.3 is two steps pretending to be one.
3. Measure the body column in ch. Full-width body text is a failure regardless of anything else.
4. Check line height against the table above at each size.
5. Check form input font size on mobile. Under 16px triggers iOS Safari zoom.
6. Check the forgotten roles: metadata, labels, empty state copy, error copy, button text.
7. Check heading spacing: is space above larger than space below.
8. If a custom font is declared, confirm it loads.
