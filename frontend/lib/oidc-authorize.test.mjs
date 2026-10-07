import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  JOB_OIDC_SCOPE,
  buildAuthorizeQuery,
  buildJobAccountLoginUrl,
} from "./oidc-authorize.js";

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

describe("buildJobAccountLoginUrl", () => {
  it("uses relative authorize path in next= (matches Academy job-account)", () => {
    const authorizeParams = params({
      intent: "job_candidate",
      returnToAbsolute: "https://web-production-dba98.up.railway.app/",
    });
    const href = buildJobAccountLoginUrl({
      jobAccountUrl: "https://ingress.academy/portal/job-account/",
      authorizeUrl: "https://ingress.academy/portal/oauth/authorize",
      authorizeParams,
      intent: "job_candidate",
      returnToAbsolute: "https://web-production-dba98.up.railway.app/",
    });
    const url = new URL(href);
    assert.equal(url.origin, "https://ingress.academy");
    assert.equal(url.pathname, "/portal/job-account/");
    assert.equal(url.searchParams.get("registration_intent"), "job_candidate");
    assert.equal(url.searchParams.get("return_to"), "https://web-production-dba98.up.railway.app/");
    const next = url.searchParams.get("next");
    assert.ok(next.startsWith("/portal/oauth/authorize?"));
    assert.equal(next.includes("https://ingress.academy"), false);
    assert.match(next, /registration_intent=job_candidate/);
    assert.match(next, /client_id=job-web/);
  });
});
