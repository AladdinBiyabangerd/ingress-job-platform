import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildEndSessionUrl, postLogoutRedirectUri } from "./oidc-logout.js";

const HINT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiI0MiJ9.c2ln";

describe("buildEndSessionUrl", () => {
  it("sends id_token_hint, client_id and the registered return URI", () => {
    const href = buildEndSessionUrl({
      endSessionUrl: "https://ingress.academy/portal/oauth/logout",
      clientId: "job-web",
      idTokenHint: HINT,
      postLogoutRedirectUri: postLogoutRedirectUri("https://web-production-dba98.up.railway.app"),
    });
    const url = new URL(href);
    assert.equal(url.origin + url.pathname, "https://ingress.academy/portal/oauth/logout");
    assert.equal(url.searchParams.get("client_id"), "job-web");
    assert.equal(url.searchParams.get("id_token_hint"), HINT);
    assert.equal(
      url.searchParams.get("post_logout_redirect_uri"),
      "https://web-production-dba98.up.railway.app/",
    );
  });

  it("omits a malformed hint so Academy asks to confirm instead", () => {
    const href = buildEndSessionUrl({
      endSessionUrl: "https://ingress.academy/portal/oauth/logout",
      clientId: "job-web",
      idTokenHint: "not a jwt",
      postLogoutRedirectUri: "http://localhost:3010/",
    });
    const url = new URL(href);
    assert.equal(url.searchParams.get("id_token_hint"), null);
    assert.equal(url.searchParams.get("client_id"), "job-web");
  });

  it("is disabled without an endpoint and rejects odd schemes", () => {
    assert.equal(buildEndSessionUrl({ endSessionUrl: "", clientId: "job-web" }), "");
    assert.equal(buildEndSessionUrl({ endSessionUrl: "javascript:alert(1)", clientId: "x" }), "");
  });
});

describe("postLogoutRedirectUri", () => {
  it("is always the site root (exact match in Academy)", () => {
    assert.equal(postLogoutRedirectUri("http://localhost:3010"), "http://localhost:3010/");
  });
});
