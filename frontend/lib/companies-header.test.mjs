import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");

test("Companies page has no hero copy / Academy promo, keeps a visually-hidden h1 and the search form", () => {
  const src = read("../components/companies.js");
  assert.ok(!src.includes("home-board-hero-copy"), "hero copy block removed");
  assert.ok(!src.includes("BoardAcademyPromo"), "Academy promo removed");
  assert.ok(!src.includes("companiesEyebrow") && !src.includes("homeBrand") && !src.includes("companiesLede"));
  assert.match(src, /<h1 id="companies-front-title" className="visually-hidden">/);
  assert.match(src, /className="home-board-search companies-board-search"/);
});

test("header nav, mobile menu and bottom nav no longer show the Learning (Öyrənmə) item", () => {
  const shell = read("../components/shell.js");
  assert.ok(!shell.includes("navLearning"));
  assert.ok(!/key: "learning"/.test(shell));
  const copy = read("./copy.js");
  assert.ok(!copy.includes("navLearning"));
});
