import assert from "node:assert/strict";
import test from "node:test";
import { academyCareerPathUrl, academyCourseUrl } from "./copy.js";

test("builds Academy training URL with UTM", () => {
  const href = academyCourseUrl("cloud-computing-with-aws-and-terraform-az");
  const url = new URL(href);
  assert.equal(url.origin, "https://ingress.academy");
  assert.equal(url.pathname, "/trainings/cloud-computing-with-aws-and-terraform-az/");
  assert.equal(url.searchParams.get("utm_source"), "ingress_job");
  assert.equal(url.searchParams.get("utm_medium"), "skill_gap");
  assert.equal(url.searchParams.get("utm_campaign"), "academy_cross_sell");
});

test("returns empty for blank course id", () => {
  assert.equal(academyCourseUrl(""), "");
  assert.equal(academyCourseUrl("   "), "");
});

test("builds Academy career-path URL with UTM", () => {
  const href = academyCareerPathUrl("devops-engineer-path");
  const url = new URL(href);
  assert.equal(url.origin, "https://ingress.academy");
  assert.equal(url.pathname, "/career-paths/devops-engineer-path/");
  assert.equal(url.searchParams.get("utm_source"), "ingress_job");
  assert.equal(url.searchParams.get("utm_medium"), "skill_gap");
  assert.equal(url.searchParams.get("utm_campaign"), "academy_cross_sell");
});

test("returns empty for blank career-path id", () => {
  assert.equal(academyCareerPathUrl(""), "");
  assert.equal(academyCareerPathUrl("   "), "");
});
