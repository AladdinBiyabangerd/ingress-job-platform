# responsive

Recomposes the interface across contexts.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `interaction`, `setup`

## What this is not

Not a max-width tweak. If the desktop composition merely shrinks, the pass failed. Recomposition means the arrangement changes because the context changed, not because the container got narrower.

Not mobile-only. Six context classes matter, and the wide end has its own failures: text running to 140ch, a 1200px-wide form field, a dashboard with an ocean of empty space where density was the point.

Not amputation. Adapt the interface, never remove the feature. If a table does not fit, change how it is presented, do not hide three columns and hope nobody needed them.

## Context classes

Context is more than width, but width is where it starts.

| Class | Width | What changes |
|---|---|---|
| Compact | under 480 | Single column, thumb reach, full-width controls |
| Small | 480 to 768 | Two columns where content earns it |
| Medium | 768 to 1024 | Sidebar becomes viable, tables get room |
| Large | 1024 to 1440 | The design target for most app UI |
| Wide | 1440 to 1920 | Cap the measure, add density rather than air |
| Ultra | over 1920 | Do not let anything scale forever |

Beyond width:

**Input mode.** `@media (hover: hover) and (pointer: fine)` is the real test for hover, not width. A touch laptop is wide and has no reliable hover.

**Thumb reach.** On a phone the top of the screen is the hardest place to reach. Primary actions belong low. A destructive action next to a primary action at the bottom of a phone screen is a mis-tap waiting to happen.

**Safe areas.** Notches and home indicators. `env(safe-area-inset-*)` with `viewport-fit=cover`, or content sits under the system chrome.

**Text direction.** Use logical properties: `margin-inline-start`, `padding-block`, `inset-inline`. They cost nothing and they mean an RTL locale does not require a second stylesheet.

**Orientation.** Landscape phone is short. A hero at `100vh` becomes unusable.

## Tables

Tables are where responsive passes usually give up. Pick a strategy deliberately:

- **Horizontal scroll** with the first column pinned. Best when comparison across rows matters.
- **Stack to cards** at compact width, with the column name as the label. Best when each row is read on its own.
- **Priority columns.** Show the top three, put the rest behind a per-row expand. Best when there are many columns and a clear hierarchy among them.

Whichever is chosen, the data stays reachable. Hiding columns with `display:none` and no alternative is amputation.

## The 16px rule

Form inputs under 16px trigger an automatic zoom on iOS Safari when focused, which throws the user into a zoomed viewport they then have to pinch out of. It is the most common and most invisible mobile bug in generated UI. Check every input, select, and textarea.

## Procedure

1. Test at every context class. Actually resize, do not reason about it from the CSS.
2. Find the breakage: horizontal overflow, clipped content, unreachable controls, text over 76ch, tap targets under 44px, layout that only shrinks.
3. Decide the recomposition per zone. What arrangement does this content want at this size, starting from the base experience and adding structure as space earns it.
4. Prefer intrinsic layout over breakpoints. `grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr))`, `flex-wrap`, `clamp()`, and container queries where supported handle most cases without a single media query, and they do not break when the content changes.
5. Fix input mode, thumb reach, safe areas, and logical properties.
6. Pick and implement the table strategy.
7. Re-test every class after the changes.

## Completion bar

- Checked at all six context classes, and the summary says so.
- No horizontal overflow at 390px.
- The composition genuinely recomposes somewhere, it does not only scale.
- No functionality is gated behind hover.
- Form fields at 16px or larger.
- Tap targets 44x44px minimum, measured including padding.
- Tables have a named strategy and the data stays reachable.
- Safe area insets handled if the product runs on a phone.

## Reporting back

Say which classes were tested and how. List the recomposition made per zone. Name the table strategy. Anything reasoned about from source but not actually resized and observed is *inspected*, not *verified*, and needs to be labelled that way.
