# The ten tells

Ask designers to label what makes an interface read as machine-made and they land on the same short list. Roughly nine tenths of that recognition signal sits in ten patterns.

Each one is defensible alone. A gradient is not a crime. Centered is sometimes right. What gives the game away is the co-occurrence: the same ten choices, together, on every surface, because each one is the safest available answer.

That matters for how you score. A single tell is cleanup. A cluster is an identity failure, and the fix is a new lane rather than a patch.

## How to score

Each tell scores **0 if present, 1 if absent**. Total out of 10. Higher is better, and 10/10 means the surface has none of them.

The score measures absence. Finding nothing is the perfect result, so do not go hunting for something to report in order to look thorough.

| Score | Label | What it means |
|---|---|---|
| 9-10 | CLEAN | Nothing generic to remove. Move to `refine` or `finish`. |
| 7-8 | FAINT | Isolated reflexes. Local cleanup with `deslop`. |
| 5-6 | NOTICEABLE | The surface reads as competent but anonymous. |
| 3-4 | STRONG | Multiple tells cluster. Structural work needed. |
| 0-2 | OVERPOWERING | Nothing here could only belong to this product. |

Severity is about clustering, not count. Three tells spread across a long page is a different problem from three tells stacked in the first viewport. Weight anything in the first screen twice, because that is where identity is decided.

Every score needs a file and a line. A tell you cannot point at did not get scored, it got guessed.

---

## 1. Tech gradient

A two-hue diagonal gradient used as decoration rather than meaning. Most often indigo to magenta, blue to purple, or teal to blue, on a hero background, a heading, a button, or a blurred blob behind the content.

**Present when:** `bg-gradient-to-r from-indigo-500 to-purple-600`, `background: linear-gradient(135deg, #6366f1, #a855f7)`, gradient text on a headline, glowing radial blobs positioned absolutely behind a hero.

**Why it reads as generated:** the gradient carries no information. It is not showing a range, a state, or a depth relationship. It is there because the surface looked empty.

**The fix is not "remove the gradient".** It is to decide what that area is doing. A flat committed field of one hue, a real photograph, a data-derived gradient where the direction means something, or genuine negative space are all decisions. A different gradient is not.

## 2. Generic tech hue

The brand color is an unmodified framework default in the indigo, violet, or blue-500 family.

**Present when:** `#6366F1`, `#8B5CF6`, `#3B82F6`, `indigo-600`, `violet-500`, or any near-identical hue used as the primary, with no evidence the product earned that hue.

**Why it reads as generated:** it is the median of every landing page ever written, so it is the safest answer, which is exactly why it says nothing.

**The fix:** pick a hue the product has a reason for, and a commitment level to go with it. See `color.md`. A hue is earned by the subject matter, the physical product, the industry's opposite, or a deliberate inheritance. Swapping indigo for teal without a reason scores the same.

## 3. Feature tile grid

Three or four visually identical cards in an even grid, each with an icon over a heading over two lines of body copy.

**Present when:** `grid-cols-3` of equal cards, same height, same weight, same internal structure, with nothing marking one as more important than the others.

**Why it reads as generated:** real products do not have three equally important features. The even grid is a refusal to rank, and ranking is the actual design work.

**The fix:** rank them. Give the strongest one more space, a real image, or a live demo, and let the rest be a compact list. Or drop to two with genuine contrast. Or use a `sequence` or `comparison` pattern if that is the real job. See `work-patterns.md`.

**Not a tell when:** the surface is a genuine `catalogue` (product grid, blog index, search results) where the items really are peers and the reader is scanning to find one. Uniform cells are correct there. Check the work pattern before scoring this.

## 4. Accent rail

Decorative colored chrome that carries no meaning. A thin gradient bar across the top of the page, a colored left border on every card, a glowing divider line, an underline swash under one word in the heading.

**Present when:** `border-l-4 border-indigo-500` applied to every card regardless of state, a full-width 2px gradient strip, decorative corner brackets, a glowing ring around a container.

**Why it reads as generated:** it is applied uniformly, so it cannot be signalling anything. A colored left border that means "this one is selected" or "this one errored" is good design. One on every card is wallpaper.

**The fix:** either give the rail a job (state, category, severity, progress) or delete it and let structure do the work.

## 5. Centered stack

Everything centered on the vertical axis with no asymmetry anywhere: centered eyebrow, centered headline, centered paragraph at `max-w-2xl mx-auto`, centered button pair, centered section headings all the way down.

**Present when:** `text-center` on every section header, hero content in a single centered column, no element that breaks the axis.

**Why it reads as generated:** centering is the safe default when you have not decided what leads. It also destroys the reading edge, so the eye has to re-find the start of each line.

**The fix:** decide the focal point and let the composition serve it. A `lead` pattern wants one dominant object with support ranked below it, usually asymmetric. Centering a short headline over a real product image is a decision. Centering everything is not.

**Not a tell when:** the content is genuinely a single short statement with nothing to rank against it, or the register is editorial and the symmetry is committed to hard (large type, real imagery, deliberate stillness).

## 6. Glass and glow

Frosted translucent cards floating on a dark background, with soft outer shadows and hairline white borders.

**Present when:** `backdrop-blur` plus `bg-white/5` plus `border-white/10` plus a large soft `shadow`, repeated across every container on the page.

**Why it reads as generated:** it is a texture applied to avoid deciding a hierarchy. Everything floats at the same elevation, so elevation stops meaning anything.

**The fix:** use elevation as information. One or two surfaces are raised because they are actually above the rest (a menu, a dialog, the active item). The rest sit flat on the page.

## 7. Keyword iconography

Line icons chosen by matching a word in the heading. Rocket for speed, shield for security, sparkles for AI, lightning for performance, puzzle piece for integrations, globe for global.

**Present when:** every feature has an icon, the icons are all the same weight and size, and each one is the literal noun of its heading.

**Why it reads as generated:** the icon adds nothing the heading did not already say. It fills a slot in a template.

**The fix:** remove icons that only restate the heading. Where a visual genuinely helps, use the real thing: a screenshot of the feature, a chart of the actual metric, a photograph of the physical object, a small live demo. If the subject is physical, ship real imagery. No colored rectangle stands in for the thing itself.

## 8. Vague copy

Claims with no object. Nothing on the surface could only be true of this product.

**Present when:** "Seamlessly integrate with your workflow", "Built for scale", "Powerful yet simple", "Everything you need", "Take your X to the next level", "Get started in minutes" with no evidence.

**Test:** paste the headline into a competitor's site. If it still fits, it is vague. Or cover the logo and ask what this company does. If the answer is "software", the copy failed.

**Why it reads as generated:** specificity requires knowing the product. The median answer is a claim that fits everything.

**The fix:** replace claims with evidence. Real numbers, real names, real constraints, the actual noun. "Route satellite tasking requests in under 40 seconds" beats "Powerful and fast". If the specifics are unknown, mark them as `[NEEDS: actual figure]` in the copy rather than inventing a number. Never fabricate a statistic, customer name, or testimonial to fill a slot.

## 9. Badge and emoji chrome

Decorative status furniture near the top: a pill badge above the headline, emoji as bullets or in headings, gradient text on one word, a fake "trusted by" strip of grey placeholder logos.

**Present when:** `✨ Now with AI`, `🚀 Ship faster`, a `New` pill that is not linked to anything, emoji leading list items, one word of the headline in gradient text.

**Why it reads as generated:** it is energy applied on top of copy that lacks its own. The exclamation point of layout.

**The fix:** if the badge announces something real, link it to the thing and use plain type. Otherwise remove it. Sentence case, no exclamation points, one verb per button.

## 10. Flat rhythm

Every section the same height, the same vertical padding, the same heading size, alternating left-right image placement, with no pacing and no climax.

**Present when:** four or more consecutive sections with identical `py-*` values and identical heading treatment, and no section that is deliberately shorter, denser, quieter, or louder than its neighbours.

**Why it reads as generated:** the page was assembled from equal blocks rather than composed. A reader gets no signal about what matters, so they skim and leave.

**The fix:** pace it. One section should be the peak and should look like it. Short punctuation sections between long ones. Density changes where the content changes. Use the 1-4-9 rhythm to make the gaps mean something rather than defaulting every section to the same padding.

---

## Reporting the score

Put the per-tell table in the report with a file and line for every 0. Then write priority issues by cluster, not by tell. Six separate findings that all live in the first viewport are one P0 called "the first viewport belongs to no product", with the six as evidence beneath it.

Each priority issue names what is broken, why it matters, and which mode fixes it. See `report-format.md`.
