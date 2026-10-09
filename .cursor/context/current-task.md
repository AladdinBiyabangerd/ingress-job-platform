# Current task

## Completed
- Notifications Design C (triptych) implemented — not deployed/committed yet
- Prior: engagement `inapp_count_today` LIKE/`%i` fix (awaiting deploy)

## Current state
- `/notifications` uses 3-zone layout: filters | feed | growth rail
- Feed cards are compact; roadmap/`this_week` lives in sticky right rail
- Filter + client pagination for large lists; mobile opens rail as detail pane

## Decisions
- Filter buckets map to existing kinds (matches / learning / profile / apps)
- Öyrənmə filter = `coach_weekly` only (`match_near` stays under Fürsətlər)
- No new API fields — payload `learning_roadmap` + `roadmap` + skills only

## Remaining
1. Visual QA on desktop / tablet / mobile with many notifications
2. Commit when user asks
3. Still open from prior: deploy engagement SQL fix + worker re-run

## Relevant files
- `frontend/components/notifications-page.js`
- `frontend/app/globals.css` (`.notes-c*`)
- `frontend/lib/copy.js` (filter/growth strings az/en/ru)
- Design refs: `.cursor/context/designs/notifications-design-c-triptych.png`
