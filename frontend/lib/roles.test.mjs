import assert from "node:assert/strict";
import { test } from "node:test";
import { canPostJobs, isCandidateOnly, isStaff, navTabs } from "./roles.js";

const guest = { authenticated: false };
const candidate = { authenticated: true, candidate: true, employer: false, staff: false };
const studentCandidate = { authenticated: true, candidate: true, employer: false, staff: false, scopes: ["job:candidate", "student"] };
const employer = { authenticated: true, employer: true, candidate: false, staff: false };
const dual = { authenticated: true, employer: true, candidate: true, staff: false };
const staff = { authenticated: true, staff: true, employer: false, candidate: false };
const noRole = { authenticated: true, employer: false, candidate: false, staff: false };

test("before /me loads only the public tabs exist", () => {
  assert.deepEqual(navTabs(undefined), ["browse", "companies"]);
  assert.deepEqual(navTabs(null), ["browse", "companies"]);
});

test("guests and candidate-only accounts never see Post or Moderation", () => {
  for (const me of [guest, candidate, studentCandidate, noRole]) {
    assert.deepEqual(navTabs(me), ["browse", "companies"]);
    assert.equal(canPostJobs(me), false);
    assert.equal(isStaff(me), false);
  }
  assert.equal(isCandidateOnly(candidate), true);
  assert.equal(isCandidateOnly(guest), false);
});

test("employers, dual employer+candidate accounts and staff may post", () => {
  assert.deepEqual(navTabs(employer), ["browse", "companies", "post"]);
  assert.deepEqual(navTabs(dual), ["browse", "companies", "post"]);
  assert.equal(isCandidateOnly(dual), false);
  assert.deepEqual(navTabs(staff), ["browse", "companies", "post", "admin"]);
});

test("a stale flag without authentication grants nothing", () => {
  assert.deepEqual(navTabs({ authenticated: false, staff: true, employer: true }), ["browse", "companies"]);
});
