# Current task

## Completed
- LinkedIn extension debug: hard refresh after Reload fixes empty capture
- Auto full description: `richText` (hidden DOM) + JSON-LD prefer longer + auto-click Show more once per job
- Popup «LinkedIn script aktiv» via `content_hello`

## Current state
- Extension changes are local (Chrome Load unpacked); Railway web/API deploy not required for this
- Settings: site URL = web origin; `JOB_IMPORT_TOKEN` on API service

## Decisions
- Keep diagnostic UX (script status, subdomain matches, logs)
- Only auto-click description «Show more»; never Apply / job navigation

## Remaining work
- Manual QA: Start → open job → confirm full description without manual Show more
- Optional: quiet console logs later

## Relevant files
- `extension/content.js`, `extension/extract.js`, `extension/popup.js`, `extension/manifest.json`
- `extension/test/extract.test.js`
