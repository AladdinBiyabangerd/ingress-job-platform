# interaction

Adds missing behavior rather than hover polish.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `motion`, `setup`

Read `references/control-states.md` before starting. The nine control states, the five view states, and the walk-the-control audit are there.

## What this is not

Not hover effects. Hover is one of nine states and the least important, because it does not exist on touch and it does not exist for keyboard users. A pass that added a `hover:scale-105` and nothing else did nothing.

Not styling. This mode adds behavior that is absent: the loading state that does not exist, the error path that was never built, the keyboard route that was never wired. Making an existing state prettier is `finish` or `refine`.

Not a claim about states you cannot reach. If an interaction cannot be triggered anywhere in the current UI, either wire a visible trigger or say plainly that the state is implemented but not reachable. Counting an unreachable state as done is the exact failure rule 3 exists to prevent.

## Procedure

**1. Enumerate the interactive elements.** Buttons, links, inputs, selects, checkboxes, switches, sliders, menu items, tabs, actionable rows, drag handles. Then enumerate the data regions: lists, tables, panels, charts, results.

**2. Walk each one rather than reading its CSS.** Tab to it, hover it, press it, break it, slow it down. The audit sequence is in `control-states.md`. Reading source tells you what was written, and walking tells you what a person meets.

**3. Fill the gaps, worst first.**

Focus first. `outline: none` with no replacement is the most common and most damaging failure in generated UI. Grep for it. Every interactive element needs a `:focus-visible` ring at 3:1 against both the control and the page behind it.

Then the missing paths: loading, error, empty, disabled-with-a-reason. These are where products actually spend their time.

Then reach: 44x44px minimum hit area including padding, visible labels rather than placeholders, and no functionality gated behind hover.

**4. Prefer undo over confirm wherever the action is recoverable.** Confirm dialogs get clicked through without reading, so they do not protect anyone. An undo affordance that lasts 5 to 10 seconds actually saves the work. Reserve confirmation for the genuinely irreversible, and there make the user type or click something specific rather than pressing OK.

**5. Wire the keyboard path** for anything an operator does more than a few times a day. Escape closes, Enter submits, arrow keys move within a group, and focus moves into a dialog on open and returns to the trigger on close.

**6. Trigger everything you added.** A state that was written but never fired is not verified. If there is no path to fire it, that is itself a finding and the honest fix is usually to build the trigger.

Where there is no real backend to fail, a marked demo trigger (a `?state=error` switch, a dev-only toggle) is a legitimate way to exercise a state, as long as it is obviously a demo affordance and you say so. That is much better than shipping an unexercised state and calling it done.

**7. Run the static checks.** These catch the wiring mistakes this mode is most likely to make: a label pointing at an id you renamed, an `aria-describedby` with no target, `outline: none` still lurking in a file you did not open.

```bash
python <skill-dir>/scripts/verify_static.py .
```

## Completion bar

- Every interactive element has all nine states, or the missing ones are listed with a reason.
- Focus is visible everywhere, and visually distinct from hover.
- Every data region has empty, loading, and error, plus no-results where filtering exists.
- Touch targets measured at 44x44px minimum, including padding.
- No functionality is reachable only by hover.
- Recoverable destructive actions offer undo.
- Every added state was actually triggered, or is reported as implemented but not reachable.

## Reporting back

Group by what changed: focus, states added, reach fixes, keyboard, undo. For each item say whether it was triggered and observed or only written. The distinction between "added a loading state and watched it render" and "added a loading state" is the whole point of this section, so keep it explicit.
