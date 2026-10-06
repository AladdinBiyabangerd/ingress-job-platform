import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import { apiBase } from "./api.js";

const KEYS = ["JOB_API_BASE_URL", "API_PRIVATE_HOST", "API_PORT", "NEXT_PUBLIC_API_BASE", "NODE_ENV"];
const saved = Object.fromEntries(KEYS.map((key) => [key, process.env[key]]));

afterEach(() => {
  for (const key of KEYS) {
    if (saved[key] === undefined) delete process.env[key];
    else process.env[key] = saved[key];
  }
});

describe("apiBase", () => {
  it("adds :8080 when Railway private URL has no port", () => {
    process.env.NODE_ENV = "production";
    process.env.JOB_API_BASE_URL = "http://api.railway.internal";
    delete process.env.API_PORT;
    assert.equal(apiBase(), "http://api.railway.internal:8080");
  });
});
