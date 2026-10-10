# checkup

Fast triage. A vital-sign read rather than a full critique. The question it answers is narrow: is this surface safe to keep building on, or is something unsafe to ship.

**Type:** audit. Changes nothing.
**Writes:** `.design/checkup-report.md` and `.design/checkup-report.html`
**Next:** `finish`, `recolor`, `relayout`

## What this is not

Not a critique. `review` gives an opinion about whether the design is good. `checkup` only asks whether it is broken. Aesthetic judgement belongs in the other mode, so keep taste out of the vitals.

Not a fix. Rule 1 applies without exception: no source file is edited, not even a one-line `outline: none` that is obviously wrong. Write the prescription and stop.

Not thorough. This is triage, so speed matters. If a vital needs 20 minutes to verify properly, mark it unverified and move on. `review` and the system modes go deep.

## Procedure

**1. Scope it.** With a target, check that file and what it imports. Without one, find the entry points and check the primary user-facing surfaces. Say in the report which files were read.

**2. Look at it rendered if you can.** A dev server, a static file, a build output, a screenshot. Vitals verified from source alone are weaker, and the report has to say which it was in the `Verified by` line.

**3. Take the ten vitals.** Each one needs something observed, with a file and a line.

| Vital | The check |
|---|---|
| Contrast | Real pairs on the page, not tokens against white. Body 4.5:1, large 3:1. |
| Focus visibility | Grep for `outline:none` and `outline:0` with no replacement ring. Tab through if you can. |
| Touch targets | Interactive elements under 44x44px including padding. Icon buttons are the usual offender. |
| Responsive integrity | Horizontal overflow, clipped content, or unusable controls at 390px. |
| Type hierarchy | Adjacent steps under a 1.3 ratio. Body measure over 76ch. Form inputs under 16px. |
| Color system | Count distinct non-scale color values, then check the token layer is actually **consumed**. Run `contrast.py --css` on the token file. |
| Control states | Does the primary control have focus, disabled, loading, and error. See `control-states.md`. |
| View states | Does the main data region have empty, loading, and error. |
| Motion | Any animation without a `prefers-reduced-motion` guard. Animating layout properties. |
| Dark mode | If implemented, are contrast pairs still passing. If not implemented, `n/a`. |

**3a. Check whether the token layer is real.** A token file that exists but is not consumed is worse than no token file, because it looks like a system while every value is still hardcoded. For each declared token, count its `var(--x)` references against the count of its raw value pasted directly. `--primary` referenced zero times while `#6366F1` appears five times is a decorative token layer.

This matters for sequencing, not just scoring. If the token layer is dead, then fixing contrast is roughly N separate edits instead of one, so token repair has to come first. A checkup that finds this should say so and reorder its own prescriptions accordingly, rather than listing the contrast fix first because it is more severe. Severity sets what matters; dependency sets what comes first.

**4. Assign a status to each.** `healthy`, `warning`, `critical`, `unverified`, or `n/a`.

A vital that could not be verified is marked **unverified**, never healthy. This is the rule that makes a checkup worth reading. Absence of evidence is not a pass, and a report that quietly upgrades "I did not check" to "fine" is worse than no report.

**5. Score and label.** Score is out of 10, one point per healthy vital, half for warning, zero for critical. `n/a` vitals score as healthy since there is nothing to be wrong. Round down.

- `HEALTHY` 8-10, no criticals
- `BUILD WITH CARE` 5-7, or any score with one critical
- `UNSAFE TO SHIP` under 5, or two or more criticals

**6. Prescribe.** Every critical gets a priority issue naming what is broken, why it matters to a real user, and which mode fixes it. Warnings get one only if they cluster.

State the **target number**, not just the failure. "Icon buttons are 32x32" tells someone there is a problem. "Icon buttons are 32x32, the minimum is 44x44" tells them when they are done. Every measurable finding carries both the observed value and the threshold it missed, because a prescription without a target is a complaint.

Order the prescriptions by dependency first, then severity. If step 3a found a dead token layer, that goes above the contrast fix even though contrast is the more severe symptom, and say why in one line.

**7. Write and render.** Follow `references/report-format.md` exactly, then run the renderer.

```bash
python <skill-dir>/scripts/render_report.py .design/checkup-report.md
```

## Completion bar

A checkup is done when all of these hold:

- All ten vitals have a status, and every `healthy` has an observation behind it with a file and a line.
- Nothing that was not actually checked is marked healthy.
- Every measurable finding states both the observed value and the threshold it missed.
- Prescriptions are ordered by dependency, then severity.
- Every critical has a prescription naming a mode.
- Both `.md` and `.html` exist in `.design/`.
- No source file changed. Verify this before writing the summary.

## Reporting back

Give the user the score, the label, the criticals in one line each, and the recommended next command. Do not paste the whole report into the chat, because the report is the artifact and the point of writing it was to keep the summary short.
