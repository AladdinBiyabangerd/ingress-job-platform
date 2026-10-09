# Current task

## Completed
- Notifications Design C (triptych) implemented — not deployed/committed yet
- Prior: engagement `inapp_count_today` LIKE/`%i` fix (awaiting deploy)

## Current state
- `/notifications` uses 3-zone layout: filters | feed | growth rail
- Growth rail upgraded from plain bullet list → journey: hero + match ring + skill pills + vertical path spine + course CTA
- Filter + client pagination for large lists; mobile opens rail as detail pane

## Decisions
- Filter buckets map to existing kinds (matches / learning / profile / apps)
- Öyrənmə filter = `coach_weekly` only (`match_near` stays under Fürsətlər)
- No new API fields — payload `learning_roadmap` + `roadmap` + skills only
- Rail reuses roadmap SkillPills + check styles; path is timeline not nested cards

## Remaining
1. User visual review of richer growth rail (live `/notifications`)
2. Commit when user asks
3. Still open from prior: deploy engagement SQL fix + worker re-run

## Relevant files
- `frontend/components/notifications-page.js` (`GrowthRail`, `RailMatchRing`)
- `frontend/components/roadmap.js` (exported `SkillPills`)
- `frontend/app/globals.css` (`.notes-c-rail*`)
- Preview: `.cursor/context/designs/notes-c-rail-journey.png`
- Design refs: `.cursor/context/designs/notifications-design-c-triptych.png`
