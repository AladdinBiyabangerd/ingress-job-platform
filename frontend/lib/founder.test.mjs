import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { FOUNDER, founderPersonNode, founderPortfolioUrl, founderSameAs } from "./founder.js";

describe("founder attribution", () => {
  it("uses the portfolio Person @id for cross-site linking", () => {
    const person = founderPersonNode("en", { organizationId: "https://example.test/#organization" });
    assert.equal(person["@id"], "https://aladdinbiyabangerd.site/#aladdin-biyabangerd");
    assert.equal(person["@id"], FOUNDER.personId);
    assert.equal(person.name, "Aladdin Biyabangerd");
    assert.equal(person.jobTitle, "Founder & creator");
    assert.equal(person.worksFor["@id"], "https://example.test/#organization");
    assert.equal(founderPortfolioUrl("en"), "https://aladdinbiyabangerd.site/en/");
    assert.deepEqual(founderSameAs("az"), [
      "https://aladdinbiyabangerd.site/az/",
      FOUNDER.github,
      FOUNDER.linkedin,
    ]);
  });

  it("localizes sole-founder jobTitle and description", () => {
    assert.equal(founderPersonNode("az").jobTitle, "Yaradıcı və təsisçi");
    assert.equal(founderPersonNode("ru").jobTitle, "Создатель и основатель");
    assert.match(founderPersonNode("en").description, /sole founder/i);
    assert.match(founderPersonNode("az").description, /tək yaradıcısı/);
  });
});
