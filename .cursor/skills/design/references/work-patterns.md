# The seven work patterns

A centered hero with three feature cards is not a layout decision. It is the absence of one.

Before touching any visual property, name what the surface is actually for. There are seven jobs a surface can have. Naming one tells you what the composition must do and what it is not allowed to do, which is why this comes before spacing, color, or type.

## Naming the pattern

Ask what the reader is doing on this surface, not what is on it.

| The reader is | Pattern |
|---|---|
| meeting one thing for the first time | **lead** |
| following an order that carries meaning | **sequence** |
| choosing between options | **comparison** |
| scanning many peers to find one | **catalogue** |
| checking state, then drilling in | **dashboard** |
| reading | **document** |
| doing work over time | **workspace** |

A page can hold more than one, and long pages usually do: a `lead` first viewport, then a `sequence`, then a `comparison` at the pricing block. Name each zone. What is not allowed is failing to name any of them and defaulting to stacked equal blocks, which is how flat rhythm happens.

State the pattern out loud in the completion summary. "Named this surface a comparison and rebuilt the plan block around a broken-out recommended tier" is a design decision. "Improved the layout" is not.

---

## lead

One thing dominates and everything else defers.

**Use for:** product hero, campaign page, single-feature announcement, portfolio piece, the first viewport of almost any marketing page.

**Composition demands:**
- One focal object carries at least 60% of the visual weight. Usually a real image, a live demo, a product shot, or a single line of large type. Not a paragraph.
- Support is ranked, not equal. Second element is clearly second.
- Asymmetry is the default. A reading edge on the left with the focal object opposite reads faster than a centered stack.
- One primary action. A second action, if any, is visibly quieter.

**Forbidden:** three of anything at equal weight. Centered stack with no focal object. A gradient standing in for the thing itself.

**Fails when:** you cannot say in one sentence what the eye lands on first.

## sequence

Order carries the meaning.

**Use for:** how it works, onboarding, timelines, changelogs, multi-step forms, tutorials, migration guides.

**Composition demands:**
- The order is visible without reading. Numbers, a connecting line, directional flow, or progressive indentation.
- One continuous line of travel. The eye should never have to jump back to find step 3.
- Spacing marks phases. Steps within a phase sit closer than the gap between phases. This is the 1-4-9 rhythm doing real work.
- Progress is shown where the sequence is live (a form, an install). Where am I, how many left.

**Forbidden:** an even grid of steps, which destroys order. Steps of equal visual weight when one is genuinely the hard part.

**Fails when:** shuffling the items would not change the reader's understanding. Then it was never a sequence, it is a catalogue.

## comparison

The reader is choosing.

**Use for:** pricing and plans, versus pages, alternatives pages, feature matrices, before and after.

**Composition demands:**
- Parallel structure. Same rows, same order, same units, so differences land on the same line and can be read across.
- A deliberate winner. One option breaks out of the grid: raised, wider, marked, or differently colored. A comparison with no recommendation is a shrug.
- Differences carry the emphasis, not the shared rows. If nine of ten rows are identical checkmarks, collapse them into one line and give the space to the row that differs.
- Honest framing. A comparison that hides the competitor's advantage reads as marketing and loses trust.

**Forbidden:** three identical cards with only the number changing. Feature lists so long the difference is buried.

**Fails when:** the reader still cannot tell which one is for them.

## catalogue

Many peers, and the reader is scanning to find one.

**Use for:** product grids, blog indexes, template galleries, search results, team pages, integration directories.

**Composition demands:**
- Uniform cells are correct here. This is the one pattern where an even grid is the right answer, so do not score it as a feature tile grid.
- Every cell carries a real distinguishing signal: an image of the actual item, a price, a date, an author, a status. A cell that is icon plus title plus generic blurb is a tile grid wearing a catalogue costume.
- Filter, sort, and search are first-class controls, not an afterthought, as soon as the set passes roughly 12 items.
- Empty and no-results states are designed, with a way out of them. See `control-states.md`.
- Scanning order is obvious. Consistent alignment of the one field people scan by.

**Forbidden:** infinite scroll with no count and no way back to a result. Cells that vary in height enough to break the scan line.

**Fails when:** finding a specific known item takes more than a few seconds.

## dashboard

State at a glance, then drill down.

**Use for:** analytics, monitoring, admin overview, status pages, reporting.

**Composition demands:**
- Density is a feature. Whitespace tuned for a marketing page wastes an operator's screen. Tighten toward the surface register.
- The most-watched number sits top left, at the largest size on the screen.
- One hero visualization, supported by smaller ones. Six equal charts is the tile grid problem again.
- Every number carries a comparison: versus last period, versus target, versus normal. A number with no baseline is not information.
- Decoration never competes with data. No gradient fills on bars, no glow, no drop shadows on chart elements.
- Stale, loading, partial, and zero data states are designed. Real dashboards spend time in all four.

**Forbidden:** decorative color on data. Charts without axis labels or units. A KPI row where every tile is the same size regardless of importance.

**Fails when:** an operator cannot tell in two seconds whether anything is wrong.

## document

Reading is the job.

**Use for:** documentation, articles, legal, changelog detail, long-form editorial, README-style pages.

**Composition demands:**
- One measure column, 60 to 76ch. Everything else is subordinate to it.
- Vertical rhythm is generous and consistent. Space above a heading is clearly larger than space below it, so headings group with their content.
- Headings are scannable and honest. The heading tree should read as a table of contents on its own.
- Code, tables, and images may break the measure, and should, because that is what marks them as different.
- Navigation is persistent for anything longer than a screen or two. Where am I in the whole.

**Forbidden:** full-width body text. Centered body paragraphs. Justified text. Decorative elements inside the reading column.

**Fails when:** the reader loses their line, or cannot find a specific section without scrolling the whole page.

## workspace

The user is doing work over time, and will come back tomorrow.

**Use for:** editors, builders, inboxes, settings, complex forms, admin CRUD, anything with a save.

**Composition demands:**
- The object of work gets the center and the most space. Chrome shrinks to fit around it.
- Controls sit near the thing they change. A toolbar 900px away from the selection is a lookup task on every use.
- State is always visible: saved or unsaved, who else is here, what mode am I in, what is selected.
- Undo is preferred over confirm wherever the action is recoverable. Confirm dialogs get clicked through, undo actually saves the work.
- Keyboard path for anything done more than a few times a day.
- Persistent chrome stays put. Controls must not move between visits, because muscle memory is the whole value.

**Forbidden:** destructive action with no undo and no confirm. Layout that reflows as the user works. Hiding a frequently used control behind a hover or a menu.

**Fails when:** the eleventh visit is no faster than the first.

---

## Using the pattern in a mode

`relayout`, `redesign`, `voice`, `surface`, and `finish` all begin here. The procedure is the same:

1. Name the pattern for each zone of the target.
2. Check the current composition against that pattern's demands and its forbidden list.
3. The gap between the two is the work list.
4. In the completion summary, name the pattern and the structural change it required.

If the current composition already satisfies the pattern, say so and stop. A relayout with no justified structural change should hand off to `finish` rather than move things to look busy.
