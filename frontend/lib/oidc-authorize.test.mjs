import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { JOB_OIDC_SCOPE, buildAuthorizeQuery } from "./oidc-authorize.js";

function params(extra = {}) {
  return buildAuthorizeQuery({
    clientId: "job-web",
    redirectUri: "http://localhost:3010/api/auth/callback",
    state: "st",
    nonce: "nn",
    challenge: "ch",
    ...extra,
  });
}

describe("buildAuthorizeQuery", () => {
  it("reuses the Academy session when Job did not log the person out", () => {
    const query = params({ intent: "job_candidate" });
    assert.equal(query.get("prompt"), null);
    assert.equal(query.get("existing_account"), null);
    assert.equal(query.get("registration_intent"), "job_candidate");
    assert.equal(query.get("scope"), JOB_OIDC_SCOPE);
  });

  it("forces a fresh Academy login after Job logout", () => {
    const query = params({ intent: "job_employer", signedOut: true });
    assert.equal(query.get("prompt"), "login");
    assert.equal(query.get("existing_account"), null);
  });

  it("keeps the portal session when a live Job account adds a role", () => {
    const query = params({
      intent: "job_employer",
      alreadySignedIn: true,
    });
    assert.equal(query.get("prompt"), null);
    assert.equal(query.get("existing_account"), "1");
  });
});
