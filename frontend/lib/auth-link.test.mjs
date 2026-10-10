import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { loginHref } from "./auth-link.js";

describe("loginHref", () => {
  it("builds the OAuth start path with intent and returnTo", () => {
    assert.equal(
      loginHref({ intent: "job_employer", returnTo: "/post" }),
      "/api/auth/login?intent=job_employer&returnTo=%2Fpost",
    );
  });

  it("omits empty params", () => {
    assert.equal(loginHref({}), "/api/auth/login?");
    assert.equal(loginHref({ returnTo: "/en" }), "/api/auth/login?returnTo=%2Fen");
  });
});
