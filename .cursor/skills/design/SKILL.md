---
name: design
description: Audit and fix the design of interfaces that already exist in files, across 17 modes (checkup, smell, review, deslop, typeset, recolor, motion, interaction, relayout, responsive, redesign, tokenize, setup, finish, refine, voice, surface). Use this whenever the user types "/design" or "design" followed by a mode name or a target file. Also use it, without waiting for the word "design", whenever someone says a screen looks generic, AI-generated, templated, sloppy, boring, flat, weak, unfinished, or "like every other landing page", or asks to audit, critique, review, de-slop, restyle, recolor, retype, relayout, tighten, polish, or ship-check an existing page or component. Trigger on complaints about a hero, feature cards, spacing, type hierarchy, color palette, motion, hover or focus states, empty and error states, dark mode, or responsive behavior in code that is already written. For inventing a brand new interface from nothing, prefer the frontend-design skill; this skill is for UI that is already in files.
---

# design

Generated UI has a look. The model was never missing the capability, it was missing the policy of *when*. Absent a policy it picks the median answer, and the median of every landing page ever written is indigo, centered, three tiles.

This skill is that policy: a curriculum of principles, a catalogue of common violations, and a bar each mode must clear before it may claim it did anything.

## The four rules

Every mode inherits these. They are what keep the loop honest.

**1. Report modes only report.** `checkup`, `smell`, and `review` write their `.md` and `.html` artifacts and stop. They never edit a source file, not even an obvious one-line fix. Fixing is a separate, explicit command, so an audit never changes a file behind the user's back.

**2. Treatment modes read the reports first.** Any mode that changes the interface checks `.design/` before deciding what to change, applies the findings that are relevant to its own job, and then still runs its own full bar. A report is a head start, not a substitute for looking.

**3. Truthful completion.** Say "added", "fixed", or "changed" only when the change is visible in the rendered result. If something was looked at and left alone, the word is *inspected*, not *fixed*. If a state was implemented but cannot be reached in the current UI, say so plainly instead of counting it. A pass that cannot point at a visible change does not get to claim it made one.

**4. Never invent evidence.** Good design work is specific, and specificity needs facts. When the facts are not in the repository, the answer is a marked gap, never a plausible number.

This one needs saying because the pressure runs the other way. Diagnosing that a page is vague is easy, and the obvious repair is to write something concrete. If the real latency, price, accuracy, or customer name is unknown, writing a believable one produces a page that reads beautifully and is a lie. A fabricated statistic is a worse outcome than the vague sentence it replaced, because vagueness announces itself and a fake number does not.

So: no invented statistics, benchmarks, prices, customer names, testimonials, logo walls, or capability claims. Leave `[NEEDS: throughput figure, per capture]` in the copy, or an HTML comment naming exactly what belongs there. Then list every marker you left in the completion summary, because the user will not find them otherwise.

Real content that already exists in the repository is not invention. Pulling the actual product nouns out of `package.json`, a dashboard, a schema, or existing copy is exactly right, and it is usually where the specifics were hiding.

Rules 3 and 4 are the ones that keep the other two honest. Before writing any completion summary, re-read the diff, check every verb against what actually moved, and check every concrete claim against something that existed before you wrote it.

## Routing

Parse the invocation, then act.

| Invocation | Do this |
|---|---|
| `design <mode> [target]` | Read `modes/<mode>.md` and follow it against `target`. No target means the whole UI. |
| `design help` | Print the mode table below with one line each. Do not run anything. |
| `design <freeform text>` | Map to the closest mode with the table below, say which mode was picked and why in one line, then run it. |
| `design` alone | Look in `.design/`. If a report exists, apply its most critical findings using the mode each prescribes. If none exists, run `checkup` first, then apply the P0 findings in the same pass. |

### Freeform routing

Match on the user's complaint, not on keywords they happened to use.

| The user says | Mode |
|---|---|
| looks AI-generated, generic, templated, like every other site | `deslop` |
| is this OK to ship, what is broken, quick check | `checkup` |
| give me an honest critique, what do you think of this | `review` |
| feels weak, timid, flat, boring, too loud, too busy | `refine` |
| type is hard to scan, hierarchy is flat, fonts are wrong | `typeset` |
| colors are off, palette is bad, needs a different feel | `recolor` |
| nothing moves, feels static, transitions are janky | `motion` |
| no hover states, cannot tab to it, no loading state | `interaction` |
| structure is wrong, everything is stacked, no focal point | `relayout` |
| broken on mobile, does not fit small screens | `responsive` |
| make it look completely different, start the visuals over | `redesign` |
| same styles copy-pasted everywhere, needs a system | `tokenize` |
| make it production-ready, ship-ready, feel finished | `finish` |
| landing page, campaign, marketing, portfolio character | `voice` |
| dashboard, admin, settings, internal tool feel | `surface` |
| set up design context for this repo | `setup` |

When two modes fit, prefer the one that changes structure over the one that changes surface, because a new palette on a broken layout is still broken.

## The modes

Read the mode file before starting. Do not work from this table alone.

**Audit** (report only, changes nothing)

| Mode | Job | Writes |
|---|---|---|
| `checkup` | Fast triage. Is this safe to keep building on. | `checkup-report.{md,html}` |
| `smell` | Name the generic and reflexive patterns. | `smell-report.{md,html}` |
| `review` | Honest scored critique, walked as a story. | `review-report.{md,html}` |

**Fix**

| Mode | Job |
|---|---|
| `deslop` | Replace every generic tell with a decision that belongs to this product. |

**System**

| Mode | Job |
|---|---|
| `typeset` | Build or repair the type system across every text role. |
| `recolor` | Build or repair the color system in OKLCH, applied to real components. |
| `motion` | Build the page-wide motion system, then tune what exists. |
| `interaction` | Add missing behavior and states, not hover polish. |

**Compose**

| Mode | Job |
|---|---|
| `relayout` | Change structure, not spacing. |
| `responsive` | Recompose across contexts, not shrink. |

**Build**

| Mode | Job |
|---|---|
| `redesign` | Full visual transformation, handled as a system. |
| `tokenize` | Pull proven repetition into tokens and components, then migrate usage. |
| `setup` | Read the repo and write `brief.md` so later commands are more specific. |

**Ship**

| Mode | Job |
|---|---|
| `finish` | Pre-ship pass. Use it like a real person, remove the friction found. |
| `refine` | Change the character. One of push, settle, strip, proof, texture. |
| `voice` | Marketing and editorial surfaces, where arrival is the deliverable. |
| `surface` | App UI, where trust is earned through consistency. |

## Name the job before the pixels

A centered hero with three feature cards is not a layout decision, it is the absence of one.

Before touching any visual property, name the surface's job as one of seven work patterns: **lead, sequence, comparison, catalogue, dashboard, document, workspace**. The composition follows from that. Read `references/work-patterns.md` for what each one demands and forbids. Every compose, build, and ship mode starts here.

## Register: voice or surface

Two registers, different permissions.

**Voice** covers marketing, landing, campaign, portfolio, and editorial. The reaction on arrival is the deliverable. Expression is allowed to lead. Asymmetry, large type, real photography, and a strong point of view are correct here.

**Surface** covers app UI, dashboards, admin, settings, and tools. Trust is earned through consistency. The bar is an experienced operator opening the screen for the eleventh time that day and moving without hesitation. Novelty costs them time, so restraint is correct here.

Decide the register before any mode that changes appearance. A voice move on a surface register reads as noise, and a surface move on a voice register reads as a wireframe.

## Core rules

Every mode inherits these. Full detail in `references/`.

**Color.** OKLCH first. Pick a commitment level before picking a hue: whisper, statement, conversation, or flood. 60-30-10 split. Neutrals carry a trace of the brand hue. Clamp chroma at the lightness extremes. Never default to indigo. See `references/color.md`.

**Typography.** Body measure 60 to 76ch. Minimum 1.3 ratio between hierarchy steps. Three fonts only when each has a distinct role: display, body, UI. See `references/type.md`.

**Layout.** 1-4-9 rhythm: 4px inside a component, 16px between components, 36px and its multiples between sections. Use `gap`, never sibling margins. A card inside a card is never right.

**Motion.** Animate `transform` and `opacity` only. Ease out, never bounce. Exits run at about 70% of entrance duration. `prefers-reduced-motion` is not optional.

**Interaction.** Nine states per control. Touch targets at least 44x44px. Labels are always visible, and a placeholder is not a label. See `references/control-states.md`.

**Responsive.** Base experience first, more structure as space earns it. Never gate functionality behind hover. Adapt the interface, never amputate the feature.

**Copy.** One verb per button. Sentence case. No exclamation points. Errors are recovery paths, not blame.

## Reports

Audit modes write exactly two files into `.design/`, and only those two. No summary file, no extra analysis document.

```text
.design/
├── checkup-report.md      ← what the next mode reads
├── checkup-report.html    ← what the user opens
├── smell-report.md
├── smell-report.html
├── review-report.md
├── review-report.html
├── brief.md               ← only after design setup
└── taste.md               ← only for blank projects
```

The markdown is the source of truth because it is structured for the next mode to apply. The HTML is the artifact the user opens, and it must be a designed diagnostic page, not markdown dropped into a browser.

Write the markdown first, then render the HTML with the bundled script. Do not hand-write the HTML.

```bash
python scripts/render_report.py .design/smell-report.md
```

The script reads the markdown, infers the report type from the filename, and writes the sibling `.html`. It needs no packages beyond the standard library. If it fails for any reason, say so and leave the markdown in place rather than substituting hand-written HTML of a different shape. Report structure and the exact section order are in `references/report-format.md`. Read that file before writing any report.

## Blank projects

If the target has no HTML, CSS, or JS to work on, create `index.html` first with semantic structure, Tailwind, and design tokens, then apply the requested mode to it. Record the decisions made (hue, commitment level, type scale, work pattern, register) in `.design/taste.md` so later runs stay consistent instead of re-deciding.

## Working against real files

Design work is file work. A few habits that keep it from going wrong:

Read before writing. Find where the value actually comes from. A hardcoded hex in one component may be the last holdout of a token defined three files up, and changing the wrong one leaves the system inconsistent.

Prefer editing the source of truth. Changing a token that 40 components consume is a design pass. Changing 40 components is a migration, and it usually means the token was missing.

Verify what you can see. If the project runs, run it and look. If a font is set, confirm it loads rather than trusting a name in a style value. If a state was added, trigger it. Rule 3 is only checkable if you actually check.

Leave logic alone unless the mode says otherwise. `redesign` changes appearance, not behavior. If a design fix needs a behavior change, say that instead of quietly making it.

## Bundled scripts

Three things get needed on almost every pass. They are written already, so use them rather than rebuilding them each time.

```bash
python <skill-dir>/scripts/contrast.py --pair "oklch(0.55 0.14 42)" "#ffffff"
python <skill-dir>/scripts/contrast.py --css css/tokens.css        # gamut + lightness sweep
python <skill-dir>/scripts/contrast.py --cvd "#16A34A" "#DC2626"   # color vision separability
python <skill-dir>/scripts/verify_static.py .                      # dangling refs, labels, focus, motion
python <skill-dir>/scripts/render_report.py .design/smell-report.md
```

`contrast.py` handles hex, rgb, hsl, oklch, and oklab, computes WCAG ratios, flags colors outside the sRGB gamut, and simulates deuteranopia, protanopia, and tritanopia. Run it **before** committing to a palette, not after. Catching an out-of-gamut color or a 3.3:1 pair while the ramp is still a draft costs nothing; catching it once the palette is on 40 components costs a migration.

`verify_static.py` catches the boring breakage a design edit causes: a `var()` pointing at a renamed token, a `getElementById` for a removed id, a label pointing at nothing, an unbalanced stylesheet, `outline: none` with no replacement, animation with no reduced-motion guard. It says nothing about whether the design is good, and it prints its own limits so those limits end up in your report.

Both exit non-zero on failure, so they can gate a pass.

## Verifying without a browser

Often there is no browser. That is normal, and it does not excuse an unverified claim. What it changes is which claims are available to you.

Work down this ladder and use the highest rung you can reach:

1. **Drive a real browser** if one is available. Best evidence. Assert the URL inside the same call that takes the measurement, because a shared browser can be navigated by another session between your navigate and your screenshot.
2. **Headless measurement.** Serve the project and run a measurement harness. Get `scrollWidth`, computed styles, tab-stop counts, and hit-area boxes as numbers.
3. **Compute it.** Contrast, gamut, color vision, and grid arithmetic are deterministic. `contrast.py` covers the color half. Layout arithmetic from declared CSS is legitimate evidence as long as you label it as computed rather than observed.
4. **Parse it.** `verify_static.py` for dangling references and structural integrity.
5. **Read it.** Weakest rung. Sufficient for "this token is defined", never for "this renders correctly".

Say in the report which rung each claim rests on. The `Verified by` line exists for this.

What you may never do is promote a lower rung to a higher one. "The CSS says 44px" is not "the hit area measures 44px", and "no overflow rule exists" is not "it does not overflow". Anything you could not reach is **unverified**, and unverified is not healthy.

If you serve the project, pick an unusual port and confirm you actually bound it. A stale server on a common port will happily serve you someone else's files, and every measurement after that is fiction.

## References

Read these when the mode calls for them, not upfront.

| File | When |
|---|---|
| `references/ten-tells.md` | `smell`, `deslop`, `checkup`. The ten patterns and how to score them. |
| `references/work-patterns.md` | Any compose, build, or ship mode. The seven jobs a surface can have. |
| `references/control-states.md` | `interaction`, `finish`, `surface`. Nine control states, five view states. |
| `references/color.md` | `recolor`, `deslop`, `redesign`, `voice`. Commitment levels, OKLCH, contrast, color vision. |
| `references/type.md` | `typeset`, `redesign`, `voice`. Scale, measure, roles, loading. |
| `references/report-format.md` | Any audit mode, before writing. Exact report structure. |

| Script | When |
|---|---|
| `scripts/contrast.py` | Any mode touching color. Run before committing a palette. |
| `scripts/verify_static.py` | After any edit, especially when no browser is available. |
| `scripts/render_report.py` | Audit modes, after writing the markdown. |
