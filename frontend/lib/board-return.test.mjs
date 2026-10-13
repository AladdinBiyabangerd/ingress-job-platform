import test from "node:test";
import assert from "node:assert/strict";
import { boardReturnHref, isBoardReturnUrl } from "./board-return.js";

test("accepts only board paths", () => {
  assert.equal(isBoardReturnUrl("/?remote=true&page=2"), true);
  assert.equal(isBoardReturnUrl("/en?stack=Java"), true);
  assert.equal(isBoardReturnUrl("/jobs/12"), false);
  assert.equal(isBoardReturnUrl("//evil.com/?a"), false);
  assert.equal(isBoardReturnUrl("https://evil.com/"), false);
});

test("returns saved url for same locale only", () => {
  assert.equal(boardReturnHref({ url: "/?stack=Java" }, "/"), "/?stack=Java");
  assert.equal(boardReturnHref({ url: "/en?stack=Java" }, "/"), "/");
  assert.equal(boardReturnHref({ url: "/en?q=x" }, "/en"), "/en?q=x");
  assert.equal(boardReturnHref(null, "/ru"), "/ru");
});
