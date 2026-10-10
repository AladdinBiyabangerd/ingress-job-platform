# finish

The pre-ship pass. Use the interface like a real person, then remove the friction you found.

**Type:** treatment. Changes files.
**Reads:** `.design/` reports if present.
**Next:** `typeset`, `recolor`

## What this is not

Not a redesign. If the composition changed, that was `relayout` or `redesign` wearing this mode's name. Finish works within the design that exists.

Not additive by default. Finish is often subtraction. The most common improvement at this stage is removing something that was never earning its place.

Not a source read. This is the mode where you have to actually use the thing. A finish pass conducted entirely by reading CSS will find the wrong problems and miss the real ones.

## Use it like a person

Click, tab, wait, fail, resize, submit, delete, undo, come back. Do the things a user does, including the ones nobody designs for.

| Action | What it exposes |
|---|---|
| Tab through the whole page | Focus order, invisible rings, traps, skip links |
| Submit the form empty | Validation, error copy, whether focus moves to the problem |
| Submit it twice, fast | Double-submit protection, loading state |
| Throttle the network | Loading states, layout jump when content lands |
| Paste a 400-character name | Overflow, truncation, tooltip on truncated text |
| Paste an emoji and an RTL string | Encoding, direction, line height blowout |
| Resize to 390 and to 1920 | Overflow, measure, wasted space |
| Zoom the browser to 200% | Reflow, clipped content, fixed heights |
| Delete something | Confirm or undo, and what the list looks like at zero |
| Come back to the page | Preserved state, scroll position, stale data |
| Turn on reduced motion | Whether anything still moves that should not |
| Load with an empty account | The empty state nobody designed |

## The usual finds

**Inconsistency.** Two buttons with different padding. Three shades of border. Two spacings that should be one. Fixing these is most of what finish is.

**Overflow.** Long strings, long lists, long words. Every container needs a decision: wrap, truncate with a title attribute, or scroll.

**Missing feedback.** An action that happens with no acknowledgement. The user clicks again because nothing told them the first one worked.

**Copy.** One verb per button. Sentence case. No exclamation points. Errors as recovery paths, never blame. This is cheap to fix and it is a large share of how finished a product feels.

**Leftovers.** A decorative element from an earlier direction. A divider that separates nothing. An icon that restates its label. Remove them.

**Alignment.** Things that are nearly aligned read as broken in a way that things which are obviously offset do not. Find the near misses.

## Procedure

1. Run the interface. If it does not run, say so plainly, because a finish pass from source alone is a different and weaker thing and the summary has to admit it. See the evidence ladder in `SKILL.md` for what you may claim from each rung.
2. Work the table above, writing down what you find as you go.
3. Read any existing reports for what was already flagged.
4. Fix in order: broken, then inconsistent, then unnecessary. Broken means a user cannot complete something. Unnecessary means it can be deleted.
5. Re-walk the flow after fixing. Finish passes commonly introduce small regressions because so many small edits land at once.
6. Run the static checks. A finish pass makes many small edits, which is exactly the situation that leaves a dangling reference behind.

```bash
python <skill-dir>/scripts/verify_static.py .
python <skill-dir>/scripts/contrast.py --pairs pairs.txt
```

## Completion bar

- The interface was actually used, or the summary states clearly that it could not be run.
- Every item in the actions table was attempted, with the untried ones named.
- Fixes are ordered broken, inconsistent, unnecessary, and the summary reflects that.
- Something was removed, or the summary says why nothing needed removing.
- The flow was re-walked after the edits.
- Every claim maps to a visible change in the rendered result.

## Reporting back

Rule 3 bites hardest here, because a finish pass makes many small changes and the temptation to summarize them generously is strongest.

Group findings into fixed, inspected and left alone, and found but not fixed. Say which of the table's actions could not be performed. "Tabbed the whole page and restored focus rings on 6 controls" is a claim you can defend. "Improved accessibility" is not.
