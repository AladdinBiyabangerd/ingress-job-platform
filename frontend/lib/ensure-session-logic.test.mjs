import assert from "node:assert/strict";
import { test } from "node:test";
import {
  ensureSessionLogic,
  shouldRefreshAccess,
  sessionEntriesFromTokens,
} from "./server/ensure-session-logic.js";

function clampAge(value, fallback, max) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return fallback;
  return Math.max(1, Math.min(Math.floor(number), max));
}

function clearEntries() {
  return [
    ["job_at", "", 0],
    ["job_rt", "", 0],
    ["job_exp", "", 0],
    ["job_guest", "1", 86400],
  ];
}

test("shouldRefreshAccess is false when exp is beyond skew", () => {
  assert.equal(
    shouldRefreshAccess({ access: "a", expUnix: 1_000_200, now: 1_000_000, force: false }),
    false,
  );
});

test("shouldRefreshAccess is true near expiry or without exp", () => {
  assert.equal(
    shouldRefreshAccess({ access: "a", expUnix: 1_000_050, now: 1_000_000, force: false }),
    true,
  );
  assert.equal(
    shouldRefreshAccess({ access: "a", expUnix: Number.NaN, now: 1_000_000, force: false }),
    true,
  );
});

test("guest lock returns no session", async () => {
  const result = await ensureSessionLogic({
    getCookie: (name) => (name === "job_guest" ? "1" : null),
    fetchFn: async () => {
      throw new Error("should not fetch");
    },
    apiBaseUrl: "http://api.test",
    clampAge,
    clearEntries,
  });
  assert.equal(result.guest, true);
  assert.equal(result.access, null);
  assert.deepEqual(result.cookieEntries, []);
});

test("near-exp refresh sets job_at job_rt job_exp", async () => {
  const cookies = {
    job_at: "old-access",
    job_rt: "r".repeat(40),
    job_exp: String(1_000_050),
  };
  let called = false;
  const result = await ensureSessionLogic({
    getCookie: (name) => cookies[name] || null,
    fetchFn: async (url, init) => {
      called = true;
      assert.match(url, /\/api\/v1\/auth\/refresh$/);
      assert.equal(JSON.parse(init.body).refresh_token, cookies.job_rt);
      return {
        ok: true,
        json: async () => ({
          access_token: "new-access",
          expires_in: 900,
          refresh_token: "n".repeat(40),
          refresh_expires_in: 3600,
        }),
      };
    },
    apiBaseUrl: "http://api.test",
    now: 1_000_000,
    clampAge,
    clearEntries,
  });
  assert.equal(called, true);
  assert.equal(result.access, "new-access");
  assert.deepEqual(
    result.cookieEntries.map(([name]) => name),
    ["job_at", "job_exp", "job_rt"],
  );
  assert.equal(result.cookieEntries.find(([n]) => n === "job_exp")[1], "1000900");
});

test("5xx keeps cookies and returns existing access", async () => {
  const result = await ensureSessionLogic({
    getCookie: (name) => ({
      job_at: "still-valid",
      job_rt: "r".repeat(40),
      job_exp: String(1_000_050),
    }[name] || null),
    fetchFn: async () => ({ ok: false, status: 503 }),
    apiBaseUrl: "http://api.test",
    now: 1_000_000,
    clampAge,
    clearEntries,
  });
  assert.equal(result.kept, true);
  assert.equal(result.access, "still-valid");
  assert.deepEqual(result.cookieEntries, []);
});

test("refresh 401 clears session cookies", async () => {
  const result = await ensureSessionLogic({
    getCookie: (name) => ({
      job_at: "old",
      job_rt: "r".repeat(40),
      job_exp: String(1_000_050),
    }[name] || null),
    fetchFn: async () => ({ ok: false, status: 401 }),
    apiBaseUrl: "http://api.test",
    now: 1_000_000,
    clampAge,
    clearEntries,
  });
  assert.equal(result.access, null);
  assert.ok(result.cookieEntries.some(([n, , age]) => n === "job_guest" && age === 86400));
});

test("sessionEntriesFromTokens includes job_exp", () => {
  const entries = sessionEntriesFromTokens(
    { access_token: "a", expires_in: 900, refresh_token: "r".repeat(40), refresh_expires_in: 3600 },
    { now: 1_000_000, clampAge },
  );
  assert.equal(entries.find(([n]) => n === "job_exp")[1], "1000900");
});
