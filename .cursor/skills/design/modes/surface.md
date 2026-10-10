# surface

For app UI, dashboards, admin panels, settings, and tools, where trust is earned through consistency.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `responsive`, `interaction`

## The bar

An experienced operator opens this screen for the eleventh time today and moves without hesitation.

That single sentence rules out most of what looks impressive in a portfolio. Novelty costs them time. A control that moved since yesterday costs them time. A clever animation they have now watched eleven times costs them time. On a surface register, restraint is not timidity, it is respect for someone who is here to work.

Test every proposed change against the eleventh visit, not the first.

## What fails this mode

**A pass that changed only color, spacing, or type while product states stay missing is not a surface pass.** That is the central failure. A dashboard with a beautiful palette and no empty state, no loading state, and no error state is not designed, it is decorated. The states are the product.

Also failing:
- Marketing whitespace on an operator screen. Density is a feature here.
- Motion that plays on every data refresh.
- A layout that reflows as data arrives.
- Controls that move between visits or hide behind a hover.
- Decoration competing with data: gradient bars, glowing cards, shadows on chart elements.

## What this mode is for

**1. States.** The main work. Every data region needs empty, loading, partial, error, and a realistic ideal. Every control needs its nine. Read `references/control-states.md`. Design the ideal state against realistic data volume, not three tidy rows, because the design that works at three rows and fails at three thousand is the most common failure in internal tools.

**2. Density.** Tune the information per screen to the job. An operator scanning 200 rows wants tight leading and compact rows. A settings page checked once a month can breathe. Same product, different densities, deliberately chosen.

**3. Consistency.** The same action looks the same everywhere. The same data type is formatted the same way everywhere. Dates, numbers, statuses, and currency all get one treatment. Inconsistency here is what makes an internal tool feel untrustworthy even when it is correct.

**4. Operator flow.** Walk the task the user actually repeats. Count the clicks, the mode switches, the places where they have to look somewhere else to know what to do. Controls belong near the thing they change.

**5. Scanability.** Numbers right-aligned with tabular figures. The scanned column consistently placed. Status readable without reading the row. Every number carrying a comparison, because a number with no baseline is not information.

**6. Recoverability.** Undo over confirm wherever the action is recoverable. Keyboard paths for repeated actions. State always visible: saved or unsaved, what is selected, what mode am I in.

## Procedure

1. Name the work pattern. Most surface work is `dashboard`, `workspace`, or `catalogue`. Read `references/work-patterns.md`.
2. Identify the repeated task, the one done many times a day. That task sets every priority in the pass.
3. Inventory the states that exist versus the states that are needed. This list is usually the bulk of the work.
4. Build the missing states.
5. Tune density to the job.
6. Fix consistency: one treatment per data type, one appearance per action.
7. Walk the repeated task again and count what changed.
8. Verify with realistic data. Long strings, many rows, zero rows, missing fields, a failed request.
9. Trigger every state you built. With no backend, a marked demo switch (`?state=empty`, `?state=error`) is a legitimate way to exercise them, and far better than shipping unexercised states. Then run the static checks:

```bash
python <skill-dir>/scripts/verify_static.py .
```

## Completion bar

- Product states exist: empty, loading, partial, error, and a realistic ideal for every data region.
- Control states covered, or the gaps listed.
- Density is a stated decision, not an accident.
- Data types are formatted consistently across the surface.
- Numbers are right-aligned with tabular figures where they sit in columns.
- The repeated task is named, and the pass improved it in a way you can describe.
- Tested against realistic volume, not sample data.
- If the pass only changed color, spacing, and type, it is reported as not a surface pass.

## Reporting back

Name the work pattern, the repeated task, and the density decision. List the states that now exist and did not before, and say which of them you actually triggered. Then say how the repeated task got shorter or clearer. If the states were already complete and the work really was cosmetic, say that honestly and recommend `finish` instead.
