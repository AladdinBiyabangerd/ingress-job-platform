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

const PUBLIC_TABS = ["browse", "companies", "trends"];

test("primary nav tabs are the same for every account", () => {
  assert.deepEqual(navTabs(undefined), PUBLIC_TABS);
  assert.deepEqual(navTabs(null), PUBLIC_TABS);
  for (const me of [guest, candidate, studentCandidate, noRole, employer, dual, staff]) {
    assert.deepEqual(navTabs(me), PUBLIC_TABS);
  }
});

test("guests and candidate-only accounts never may post or moderate", () => {
  for (const me of [guest, candidate, studentCandidate, noRole]) {
    assert.equal(canPostJobs(me), false);
    assert.equal(isStaff(me), false);
  }
  assert.equal(isCandidateOnly(candidate), true);
  assert.equal(isCandidateOnly(guest), false);
});

test("employers, dual employer+candidate accounts and staff may post", () => {
  assert.equal(canPostJobs(employer), true);
  assert.equal(canPostJobs(dual), true);
  assert.equal(isCandidateOnly(dual), false);
  assert.equal(canPostJobs(staff), true);
  assert.equal(isStaff(staff), true);
});

test("a stale flag without authentication grants nothing", () => {
  assert.equal(canPostJobs({ authenticated: false, staff: true, employer: true }), false);
  assert.equal(isStaff({ authenticated: false, staff: true, employer: true }), false);
});
