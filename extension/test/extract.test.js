// Çalışdırmaq: node --test extension/test   (jsdom lazımdır: npm i --no-save jsdom, və ya NODE_PATH)
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { decodeApplyUrl, jobIdFromUrl, extract, findShowMore } = require("../extract.js");

test("safety/go decoding strips utm and returns external url", () => {
  const href =
    "https://www.linkedin.com/safety/go/?url=https%3A%2F%2Fjobs.ashbyhq.com%2Fpragmatike%2F4cc505dc%3Futm_source%3Dlinkedin%26ref%3Dx&urlhash=ab";
  assert.strictEqual(decodeApplyUrl(href), "https://jobs.ashbyhq.com/pragmatike/4cc505dc?ref=x");
  assert.strictEqual(decodeApplyUrl("/safety/go?url=https%3A%2F%2Fa.example%2Fj"), "https://a.example/j");
  assert.strictEqual(decodeApplyUrl("https://www.linkedin.com/jobs/view/123/"), "");
  assert.strictEqual(decodeApplyUrl("https://www.linkedin.com/safety/go/?url=javascript%3Aalert(1)"), "");
  assert.strictEqual(decodeApplyUrl("https://acme.example/apply"), "https://acme.example/apply");
});

test("job id from currentJobId or /jobs/view", () => {
  assert.strictEqual(jobIdFromUrl("https://www.linkedin.com/jobs/search-results/?currentJobId=4300001234&x=1"), "4300001234");
  assert.strictEqual(jobIdFromUrl("https://www.linkedin.com/jobs/view/4300001234/"), "4300001234");
  assert.strictEqual(jobIdFromUrl("https://www.linkedin.com/jobs/view/sre-at-acme-4300001234"), "4300001234");
  assert.strictEqual(jobIdFromUrl("https://www.linkedin.com/feed/"), "");
});

let JSDOM;
try { ({ JSDOM } = require("jsdom")); } catch (_) {}

test("Turkish layout extraction", { skip: !JSDOM && "jsdom yoxdur" }, () => {
  const html = fs.readFileSync(path.join(__dirname, "fixture-tr.html"), "utf8");
  const dom = new JSDOM(html);
  const { window } = dom;
  // jsdom innerText-i dəstəkləmir: blok elementlər arasında sətir keçidi ilə əvəz edirik.
  const BLOCK = /^(DIV|P|H[1-6]|LI|UL|SECTION|MAIN|BUTTON|A|SPAN)$/;
  function inner(n) {
    if (n.nodeType === 3) return n.textContent;
    if (n.nodeType !== 1 || /^(SCRIPT|STYLE)$/.test(n.tagName)) return "";
    const s = [...n.childNodes].map(inner).join("");
    return /^(DIV|P|H[1-6]|LI|SECTION|MAIN|BUTTON)$/.test(n.tagName) ? "\n" + s + "\n" : s;
  }
  Object.defineProperty(window.HTMLElement.prototype, "innerText", {
    get() { return inner(this).replace(/\n+/g, "\n").trim(); }
  });
  const job = extract(window.document, "https://www.linkedin.com/jobs/search-results/?currentJobId=4300001234");
  assert.strictEqual(job.linkedin_id, "4300001234");
  assert.strictEqual(job.title, "Senior Site Reliability Engineer / Kubernetes (Remote)");
  assert.strictEqual(job.company, "Pragmatike");
  assert.strictEqual(job.location, "Türkiye");
  assert.strictEqual(job.posted, "1 hafta önce");
  assert.strictEqual(job.workplace_type, "Uzaktan");
  assert.strictEqual(job.remote, true);
  assert.strictEqual(job.employment_type, "Tam Zamanlı");
  assert.strictEqual(job.apply_url, "https://jobs.ashbyhq.com/pragmatike/4cc505dc-1111-2222-3333-444455556666");
  // Easy Apply: xarici link yoxdur -> LinkedIn ünvanı
  const easy = new JSDOM(html.replace(/<a href="https:\/\/www\.linkedin\.com\/safety[^>]*>.*?<\/a>/, '<button>Kolay Başvuru</button>'));
  Object.defineProperty(easy.window.HTMLElement.prototype, "innerText", { get() { return inner(this).replace(/\n+/g, "\n").trim(); } });
  const e = extract(easy.window.document, "https://www.linkedin.com/jobs/view/4300001234/");
  assert.strictEqual(e.apply_url, "https://www.linkedin.com/jobs/view/4300001234/");
  assert.match(job.description, /Kubernetes at scale/);
  assert.match(job.description, /Terraform, Go and Python/);
  assert.doesNotMatch(job.description, /consultancy|İş ilanı hakkında|Şirket hakkında/);
});

test("findShowMore + hidden full description via textContent", { skip: !JSDOM && "jsdom yoxdur" }, () => {
  const html = `<!doctype html><html><body>
    <h1>SRE Kubernetes</h1>
    <a href="/company/acme/">Acme</a>
    <div id="job-details">
      <p class="visible">Short teaser only.</p>
      <p class="hidden-full" style="display:none">Full role owns Kubernetes, Terraform, Go and Python on-call.</p>
      <button aria-expanded="false">Show more</button>
    </div>
  </body></html>`;
  const { window } = new JSDOM(html);
  // Görünən mətn qısa; textContent isə gizli tam mətni də ehtiva edir.
  Object.defineProperty(window.HTMLElement.prototype, "innerText", {
    get() {
      if (this.id === "job-details") return "Short teaser only.\nShow more";
      return (this.textContent || "").trim();
    },
  });
  const btn = findShowMore(window.document);
  assert.ok(btn);
  assert.match(btn.textContent, /Show more/i);
  const job = extract(window.document, "https://www.linkedin.com/jobs/view/4300001234/");
  assert.ok(job, "extract returned null");
  assert.match(job.description, /Kubernetes/);
  assert.doesNotMatch(job.description, /^Short teaser only\.?$/);
});

// EN (Easy Apply / xarici Apply) nümunələri, sintetik düzənlər: test/fixtures.js
const { CASES } = require("./fixtures.js");
function withInnerText(window) {
  function inner(n) {
    if (n.nodeType === 3) return n.textContent;
    if (n.nodeType !== 1 || /^(SCRIPT|STYLE)$/.test(n.tagName)) return "";
    const s = [...n.childNodes].map(inner).join("");
    return /^(DIV|P|H[1-6]|LI|SECTION|MAIN|BUTTON)$/.test(n.tagName) ? "\n" + s + "\n" : s;
  }
  Object.defineProperty(window.HTMLElement.prototype, "innerText", { get() { return inner(this).replace(/\n+/g, "\n").trim(); } });
}
for (const c of CASES) {
  test(c.name, { skip: !JSDOM && "jsdom yoxdur" }, () => {
    const { window } = new JSDOM(c.html);
    withInnerText(window);
    const job = extract(window.document, c.url);
    const { has, ...fields } = c.expect;
    for (const [k, v] of Object.entries(fields)) assert.strictEqual(job[k], v, k);
    for (const re of has) assert.match(job.description, re);
    assert.doesNotMatch(
      job.description,
      /Your profile and resume|Show match details|BETA|Is this information helpful|Job match summary|doesn't have enough|Responses managed|See how you compare|Premium|Company blurb|About the job|About the company/
    );
  });
}
