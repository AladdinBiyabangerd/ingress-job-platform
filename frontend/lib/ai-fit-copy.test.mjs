import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { copy } from "./copy.js";

// Keys of worker.fit_mapping.VISA_NOTES_AZ (market_fit_detail.visa_note.key).
const VISA_NOTE_KEYS = ["weak", "remote_route", "no_sponsorship", "work_authorization", "candidate_location"];
const ROUTES = ["relocation+visa_conditional", "visa_conditional", "remote_az_explicit", "remote_worldwide"];

describe("AI fit popover copy", () => {
  for (const lang of ["az", "en", "ru"]) {
    it(`${lang}: every visa note and v9 route has a label`, () => {
      const t = copy[lang].aiFit;
      assert.ok(t.visa);
      for (const key of VISA_NOTE_KEYS) assert.ok(t.visaNotes[key], `${lang} visaNotes.${key}`);
      for (const route of ROUTES) assert.ok(t.routes[route], `${lang} routes.${route}`);
    });
  }
});
