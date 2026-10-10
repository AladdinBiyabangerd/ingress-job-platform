# States

Most missing design work is missing states. A control that only has a rest style is not finished, it is sketched.

Two lists: nine states every control has to survive, and five states every view has to survive.

---

## Nine control states

Applies to buttons, links, inputs, selects, checkboxes, radios, switches, sliders, menu items, tabs, and rows that can be acted on.

| # | State | What it must do |
|---|---|---|
| 1 | **default** | Read as interactive without hover. Affordance is visible at rest. |
| 2 | **hover** | Confirm the target before commitment. Pointer only, never the sole carrier of information. |
| 3 | **focus-visible** | Visible keyboard ring, at least 3:1 against both the control and the page behind it. Never `outline: none` without a replacement. |
| 4 | **active** | Fires on press, not release. Confirms the click landed. |
| 5 | **selected** | Persistent, distinguishable from hover and from focus. This is the one most often collapsed into hover. |
| 6 | **disabled** | Reads as unavailable, not as low-priority. Explain why nearby, because a disabled control with no reason is a dead end. |
| 7 | **loading** | The control keeps its width so the layout does not jump. Blocks repeat submission. |
| 8 | **error** | Attached to the control, not floating at the top of the form. Says what to do next. |
| 9 | **success** | Visible confirmation that the thing happened. Optimistic UI still needs a way to show it failed later. |

### Checks that catch the usual failures

Hover and focus must be visually distinct. A shared style means keyboard users get no signal about what pointer users are doing, and mouse users get no signal about focus.

Focus must never be removed. `outline: none` without a replacement ring is the single most common accessibility failure in generated UI. Grep for it.

Disabled must not be the only feedback. If a submit button is disabled until the form is valid, the user needs to see which field is holding it. Prefer an enabled button that explains the problem on click.

Loading must not resize. Swapping a label for a spinner shrinks the button and moves everything beside it. Reserve the width.

Error must be reachable. If validation only appears on submit and the invalid field is above the fold, scroll to it and focus it.

Touch targets at least 44x44px, including the padding around a small icon. Measure the hit area, not the glyph.

Labels are always visible. A placeholder is not a label: it disappears the moment the user types, which is exactly when they need it, and it fails for screen readers.

Never gate functionality behind hover. Anything that only appears on hover is invisible on touch and to keyboard users. If a row action only shows on hover, it needs a persistent alternative.

---

## Five view states

Applies to any region that loads, lists, or filters data: tables, lists, cards, panels, charts, search results, whole pages.

| State | What it must do |
|---|---|
| **empty** | First run, nothing here yet. Explain what will appear and give one action to make it happen. Not a shrug. |
| **loading** | Match the shape of the loaded result so the layout does not jump. Skeletons over spinners for known shapes. |
| **partial** | Some data, some missing or still arriving. Show what is here rather than blocking the whole view. |
| **error** | What failed, whether it is retryable, and a retry control. Never a raw stack trace, never blame the user. |
| **ideal** | The populated, working state. Design this one against realistic data volume, not three tidy rows. |

Two extra cases worth designing when they apply: **no results** after filtering, which is different from empty and needs a way to clear the filter, and **too much**, where the realistic data volume is 10,000 rows and the design assumed 10.

---

## Copy inside states

Errors are recovery paths, not blame. "Enter a date after today" beats "Invalid input". Never "You entered the wrong thing".

One verb per button. "Save", not "Save changes now". Sentence case. No exclamation points.

Empty states name the thing. "No invoices yet. Create your first one to see it here" beats "Nothing to display".

Loading copy is only worth having when the wait is long enough to worry about. Then say what is happening, not "Loading...".

---

## Auditing states

Walk the control, do not read the CSS. For each interactive element:

1. Tab to it. Is the ring visible.
2. Hover it. Is that different from focus.
3. Press it. Does something happen on press.
4. Trigger the failure path. Submit it empty, disconnect the network, pass a bad value.
5. Trigger the slow path. Throttle it and watch for layout jump.
6. If it can be selected, select it, then hover something else and confirm selection still reads.

Anything you could not trigger is **inspected**, not verified. Report it that way. If a state exists in the code but there is no path to it in the current UI, either wire a visible trigger or say plainly that the state is implemented but not reachable. Counting an unreachable state as done is exactly the kind of claim rule 3 forbids.
