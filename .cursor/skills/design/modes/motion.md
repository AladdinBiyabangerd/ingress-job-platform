# motion

Creates a page-wide motion system first, then tunes what already exists.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `interaction`, `responsive`

## What this is not

Not easing tweaks. Adjusting a cubic-bezier on one button only counts as a motion pass when a complete system is already in place. If the page has three transitions and none of them share a duration, the job is to build the system, not polish one curve.

Not decoration. Scroll-triggered fade-ups on every section is a tell, not a motion system. Motion earns its place by explaining a relationship: where this came from, where it went, what is loading, what changed.

Not a failure that ships silently. If nothing meaningful moves after the pass, the mode failed. Say so rather than reporting a system that has no visible effect.

## The system

A motion system is four decisions, then applied consistently.

**Durations.** Three values, not twelve.

| Token | Value | For |
|---|---|---|
| `--dur-fast` | 120 to 160ms | Hover, press, small state flips |
| `--dur-base` | 200 to 260ms | Panels, dropdowns, tooltips, most things |
| `--dur-slow` | 320 to 420ms | Page and modal transitions, large movement |

Distance sets duration. A 4px shift at 300ms feels broken. A full-screen sheet at 120ms feels violent.

**Easing.** Ease out for entrances, so the thing arrives fast and settles. Ease in for exits. Never bounce, and never `linear` except for continuous motion like a spinner or a progress bar.

```css
--ease-out: cubic-bezier(0.2, 0, 0, 1);
--ease-in:  cubic-bezier(0.4, 0, 1, 1);
```

**Asymmetry.** Exits run at about 70% of the entrance duration. Leaving should feel faster than arriving, because the user has already decided.

**Properties.** Animate `transform` and `opacity` only. These are the two the compositor can handle without layout work. Animating `width`, `height`, `top`, `left`, or `margin` causes a reflow on every frame and will jank on a mid-range phone. Where a size change is genuinely needed, use a transform scale, or `grid-template-rows: 0fr` to `1fr`, or a `clip-path`.

## Reduced motion

`prefers-reduced-motion` is not optional. It is a vestibular accessibility need, not a preference toggle.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

The blanket rule is a floor, not the finished job. Where motion carries meaning (a panel that slides in from the side it belongs to), reduced motion should keep a cross-fade so the relationship still reads, rather than having the element appear from nowhere.

## Procedure

1. Inventory every animation and transition currently in the codebase. Note durations, easings, and animated properties.
2. Find the layout-property animations. These are the correctness bugs and they come first.
3. Define the four decisions above as tokens.
4. Migrate existing transitions onto the tokens.
5. Add motion where a relationship needs explaining and there is none: state changes with no feedback, panels that appear instantly, lists that reorder with no continuity, loading with no transition into the loaded state.
6. Add the reduced-motion guard, and check the meaningful cases keep a fade.
7. Watch it run. Throttle the CPU if the tooling allows. Look for jank, for anything animating layout, and for motion that is now competing with itself.

## Completion bar

- Duration, easing, exit ratio, and property rules exist as tokens.
- Existing transitions consume the tokens rather than sitting on ad hoc values.
- No animation touches a layout-triggering property, or any exception is named with a reason.
- `prefers-reduced-motion` is handled, and meaningful motion degrades to a fade rather than vanishing.
- Something visibly moves in the rendered result that did not before, or that moved wrongly before and moves correctly now. If nothing does, report the pass as failed.

## Reporting back

Name the three durations, the easing pair, and the exit ratio. List what now moves that did not. State the reduced-motion handling. If you could not run the interface to watch it, say the motion was implemented but not observed, which is *inspected*, not *verified*.
