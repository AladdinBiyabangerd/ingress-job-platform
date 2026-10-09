import assert from "node:assert/strict";
import { formatUnreadDocumentTitle, stripUnreadTitlePrefix } from "./unread-document-title.js";

assert.equal(stripUnreadTitlePrefix("(2) Ingress Job"), "Ingress Job");
assert.equal(stripUnreadTitlePrefix("(99+) Ingress Job — Open roles"), "Ingress Job — Open roles");
assert.equal(stripUnreadTitlePrefix("Ingress Job"), "Ingress Job");

assert.equal(formatUnreadDocumentTitle("Ingress Job", 2), "(2) Ingress Job");
assert.equal(formatUnreadDocumentTitle("(2) Ingress Job", 2), "(2) Ingress Job");
assert.equal(formatUnreadDocumentTitle("(2) Ingress Job", 0), "Ingress Job");
assert.equal(formatUnreadDocumentTitle("(1) Ingress Job — Open roles", 3), "(3) Ingress Job — Open roles");
assert.equal(formatUnreadDocumentTitle("Ingress Job", 100), "(99+) Ingress Job");

console.log("unread-document-title.test.mjs: ok");
