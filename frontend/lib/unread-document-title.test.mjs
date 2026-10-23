import assert from "node:assert/strict";
import { formatUnreadDocumentTitle, stripUnreadTitlePrefix } from "./unread-document-title.js";

assert.equal(stripUnreadTitlePrefix("(2) Technology Jobs"), "Technology Jobs");
assert.equal(stripUnreadTitlePrefix("(99+) Technology Jobs — Open roles"), "Technology Jobs — Open roles");
assert.equal(stripUnreadTitlePrefix("Technology Jobs"), "Technology Jobs");

assert.equal(formatUnreadDocumentTitle("Technology Jobs", 2), "(2) Technology Jobs");
assert.equal(formatUnreadDocumentTitle("(2) Technology Jobs", 2), "(2) Technology Jobs");
assert.equal(formatUnreadDocumentTitle("(2) Technology Jobs", 0), "Technology Jobs");
assert.equal(formatUnreadDocumentTitle("(1) Technology Jobs — Open roles", 3), "(3) Technology Jobs — Open roles");
assert.equal(formatUnreadDocumentTitle("Technology Jobs", 100), "(99+) Technology Jobs");

console.log("unread-document-title.test.mjs: ok");
