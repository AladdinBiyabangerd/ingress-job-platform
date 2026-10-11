import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { FOUNDER } from "./founder.js";
import {
  companiesJsonLd,
  companyJsonLd,
  companyMetadata,
  homeJsonLd,
  homeMetadata,
  hreflangMap,
  localePath,
  trendSkillJsonLd,
  trendSkillMetadata,
  trendsJsonLd,
} from "./seo.js";

describe("localePath + hreflang", () => {
  it("builds locale hubs, companies, trends, and skill paths", () => {
    assert.equal(localePath("az"), "/");
    assert.equal(localePath("en"), "/en");
    assert.equal(localePath("az", { mode: "companies" }), "/companies");
    assert.equal(localePath("ru", { mode: "trends" }), "/ru/trends");
    assert.equal(localePath("en", { mode: "trend", skillId: 12 }), "/en/trends/12");
    assert.equal(localePath("az", { mode: "trendJobs", skillId: 12 }), "/trends/12/jobs");
  });

  it("emits hreflang including x-default", () => {
    const map = hreflangMap({ mode: "companies" });
    assert.match(map.az, /\/companies$/);
    assert.match(map.en, /\/en\/companies$/);
    assert.match(map.ru, /\/ru\/companies$/);
    assert.equal(map["x-default"], map.az);
  });
});

describe("metadata", () => {
  it("home metadata includes founder keywords and canonical languages", () => {
    const meta = homeMetadata("az");
    assert.match(meta.title, /Ingress Job/);
    assert.ok(meta.keywords.includes("Aladdin Biyabangerd"));
    assert.equal(meta.creator, FOUNDER.name);
    assert.ok(meta.alternates.languages.az);
    assert.equal(meta.robots.index, true);
  });

  it("company and skill metadata are page-specific", () => {
    const company = companyMetadata("en", {
      name: "Acme",
      slug: "acme",
      open_jobs: 3,
      locations: ["Baku"],
      top_tech: [{ name: "React" }],
    });
    assert.match(company.title, /Acme/);
    assert.ok(company.keywords.includes("React"));
    assert.match(company.alternates.canonical, /\/en\/companies\/acme$/);

    const skill = trendSkillMetadata("az", { skill_id: 7, name: "Python" });
    assert.match(skill.title, /Python/);
    assert.match(skill.alternates.canonical, /\/trends\/7$/);

    const jobs = trendSkillMetadata("az", { skill_id: 7, name: "Python" }, { jobs: true });
    assert.match(jobs.alternates.canonical, /\/trends\/7\/jobs$/);
    assert.notEqual(jobs.title, skill.title);
  });
});

describe("JSON-LD graphs", () => {
  it("home graph has Organization, Person, WebSite SearchAction, CollectionPage", () => {
    const graph = homeJsonLd("en")["@graph"];
    const types = graph.map((node) => node["@type"]);
    assert.ok(types.includes("Organization"));
    assert.ok(types.includes("Person"));
    assert.ok(types.includes("WebSite"));
    assert.ok(types.includes("CollectionPage"));
    const site = graph.find((node) => node["@type"] === "WebSite");
    assert.equal(site.potentialAction["@type"], "SearchAction");
    assert.match(site.potentialAction.target.urlTemplate, /q=\{search_term_string\}/);
    assert.equal(site.creator["@id"], FOUNDER.personId);
    const org = graph.find((node) => node["@type"] === "Organization");
    assert.equal(org.founder["@id"], FOUNDER.personId);
    assert.equal(org.email, FOUNDER.email);
  });

  it("companies / trends / company / skill graphs include breadcrumbs", () => {
    assert.ok(companiesJsonLd("az")["@graph"].some((n) => n["@type"] === "BreadcrumbList"));
    assert.ok(trendsJsonLd("ru")["@graph"].some((n) => n["@type"] === "BreadcrumbList"));
    const company = companyJsonLd("en", { name: "Acme", slug: "acme", open_jobs: 2, top_tech: [] });
    assert.ok(company["@graph"].some((n) => n["@type"] === "ProfilePage"));
    assert.ok(company["@graph"].some((n) => n["@type"] === "Organization" && n.name === "Acme"));
    const skill = trendSkillJsonLd("az", { skill_id: 3, name: "Go" });
    assert.ok(skill["@graph"].some((n) => n["@type"] === "BreadcrumbList"));
  });
});
