import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { clearMeCache, fetchMe, seedMeCache } from "./me-client.js";

const originalFetch = globalThis.fetch;

function installStorage() {
  const store = new Map();
  globalThis.sessionStorage = {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => {
      store.set(key, String(value));
    },
    removeItem: (key) => {
      store.delete(key);
    },
  };
}

afterEach(() => {
  clearMeCache();
  globalThis.fetch = originalFetch;
});

test("fetchMe returns seeded identity without calling the BFF", async () => {
  installStorage();
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return { json: async () => ({ authenticated: true, name: "network" }) };
  };
  seedMeCache({ authenticated: true, name: "ssr" });
  const me = await fetchMe();
  assert.equal(me.name, "ssr");
  assert.equal(calls, 0);
});

test("fetchMe hits /api/auth/me when the cache is empty", async () => {
  installStorage();
  globalThis.fetch = async (url) => {
    assert.equal(url, "/api/auth/me");
    return { json: async () => ({ authenticated: false }) };
  };
  const me = await fetchMe();
  assert.deepEqual(me, { authenticated: false });
});
