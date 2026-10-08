import assert from "node:assert/strict";
import test from "node:test";
import { descriptionBlocks, joinBrokenLines, joinLabels, linkParts, splitDescription } from "./description.js";

// What the old worker cleaner stored for a Djinni ad: every <strong> on its own line.
const DJINNI_LEGACY = [
  "We are strengthening our team and looking for a",
  "Junior",
  "Product Manager",
  "who will drive valuable features and contribute to the launch of new products.",
  "About the product:",
  "We develop and scale multiple social networking products that connect people worldwide. Our portfolio includes apps for both iOS and Android, each designed to enhance user experience, optimize engagement, and explore new business models.",
  "In this role, you will",
  "Conduct market research and competitor analysis to identify trends and opportunities",
  "Define and write detailed product requirements (PRDs, user stories, acceptance criteria)",
  "Analyze user behavior and product funnels to find areas for improvement",
  "It’s all about you",
  "1+ years of experience in product management with mobile B2C apps",
  "Strong analytical skills and experience in problem-solving through data analysis",
  "Upper-Intermediate (B2) English or higher",
  "Would be a plus",
  "Experience working with product analytics in-depth",
  "What we offer",
  "Care and support:",
  "20 paid vacation days, 15 sick days, and 6 additional days off for family events",
  "Up to 10 additional days off for public holidays",
  "100% medical insurance coverage",
  "Sports and equipment reimbursement",
].join("\n");

test("joins a sentence broken around inline tags (Djinni pattern)", () => {
  const blocks = descriptionBlocks(DJINNI_LEGACY);
  assert.deepEqual(blocks[0], {
    type: "paragraph",
    text: "We are strengthening our team and looking for a Junior Product Manager who will drive valuable features and contribute to the launch of new products.",
  });
  const texts = blocks.filter((block) => block.type !== "list").map((block) => block.text);
  assert.ok(!texts.includes("Junior"));
  assert.ok(!texts.includes("Product Manager"));
});

test("keeps real headings and rebuilds lists without markers", () => {
  const blocks = descriptionBlocks(DJINNI_LEGACY);
  const headings = blocks.filter((block) => block.type === "heading").map((block) => block.text);
  assert.deepEqual(headings, ["About the product", "It’s all about you", "Would be a plus", "What we offer", "Care and support"]);
  const lead = blocks.findIndex((block) => block.type === "paragraph" && block.text === "In this role, you will");
  assert.ok(lead > 0);
  assert.equal(blocks[lead + 1].type, "list");
  assert.equal(blocks[lead + 1].items.length, 3);
  const care = blocks.findIndex((block) => block.type === "heading" && block.text === "Care and support");
  assert.equal(blocks[care + 1].type, "list");
  assert.equal(blocks[care + 1].items.length, 4);
  assert.ok(blocks[care + 1].items.includes("Sports and equipment reimbursement"));
});

test("the new cleaner output (blank lines, bullets, Heading:) renders directly", () => {
  const raw = [
    "We are strengthening our team and looking for a Junior Product Manager who will drive valuable features.",
    "",
    "In this role, you will:",
    "",
    "• Conduct market research",
    "• Define product requirements",
    "",
    "Hiring process:",
    "",
    "1. Intro call",
    "2. Test Task",
  ].join("\n");
  assert.deepEqual(descriptionBlocks(raw), [
    { type: "paragraph", text: "We are strengthening our team and looking for a Junior Product Manager who will drive valuable features." },
    { type: "heading", text: "In this role, you will" },
    { type: "list", ordered: false, items: ["Conduct market research", "Define product requirements"] },
    { type: "heading", text: "Hiring process" },
    { type: "list", ordered: true, items: ["Intro call", "Test Task"] },
  ]);
});

test("recognises -, *, • (with or without a space) and numbered bullets", () => {
  const blocks = descriptionBlocks("Requirements:\n- Python\n* Django\n•SQL\n• Docker\n\n1) First\n2. Second");
  assert.deepEqual(blocks, [
    { type: "heading", text: "Requirements" },
    { type: "list", ordered: false, items: ["Python", "Django", "SQL", "Docker"] },
    { type: "list", ordered: true, items: ["First", "Second"] },
  ]);
});

test("a marker on its own line is attached to the next line", () => {
  assert.deepEqual(joinBrokenLines(["•", "Team events", "•", "Insurance"]), ["• Team events", "• Insurance"]);
});

test("does not merge separate sentences or capitalised list items", () => {
  const lines = ["We ship every day.", "Our team is remote.", "Python", "Django"];
  assert.deepEqual(joinBrokenLines(lines), lines);
});

test("joins wrapped lowercase continuations and punctuation lines", () => {
  assert.deepEqual(joinBrokenLines(["We build tools that help teams", "ship faster", ",", "and better."]), [
    "We build tools that help teams ship faster, and better.",
  ]);
  assert.deepEqual(joinBrokenLines(["«", "ABC Telecom", "» şirkəti satış edir."]), ["«ABC Telecom» şirkəti satış edir."]);
});

test("stray short fragments do not become headings", () => {
  const blocks = descriptionBlocks("Junior\nWe are a product company with a strong engineering culture and remote-first team.");
  assert.equal(blocks.some((block) => block.type === "heading"), false);
});

test("label/value lines are joined", () => {
  assert.deepEqual(joinLabels(["Type:", "Full time", "Location:", "UK or Canada", "Meet The Guru"]), [
    "Type: Full time",
    "Location: UK or Canada",
    "Meet The Guru",
  ]);
  assert.deepEqual(joinLabels(["Requirements:", "Python", "Django", "SQL"]), ["Requirements:", "Python", "Django", "SQL"]);
});

test("drops a leading line that repeats the title and punctuation-only blocks", () => {
  const blocks = descriptionBlocks("Junior Product Manager\n\n.\n\nWe build social apps used by millions of people around the world.", "Junior product manager");
  assert.deepEqual(blocks, [{ type: "paragraph", text: "We build social apps used by millions of people around the world." }]);
});

test("is deterministic", () => {
  assert.deepEqual(descriptionBlocks(DJINNI_LEGACY), descriptionBlocks(DJINNI_LEGACY));
});

test("links only http(s) URLs and trims trailing punctuation", () => {
  assert.deepEqual(linkParts("Apply at https://example.com/jobs/1. Thanks"), [
    { type: "text", text: "Apply at " },
    { type: "link", text: "https://example.com/jobs/1", href: "https://example.com/jobs/1" },
    { type: "text", text: ". Thanks" },
  ]);
  assert.deepEqual(linkParts("see www.example.org"), [
    { type: "text", text: "see " },
    { type: "link", text: "www.example.org", href: "https://www.example.org" },
  ]);
  assert.deepEqual(linkParts("javascript:alert(1) and data:text/html,x"), [
    { type: "text", text: "javascript:alert(1) and data:text/html,x" },
  ]);
  assert.deepEqual(linkParts("(https://example.com/a_(b))"), [
    { type: "text", text: "(" },
    { type: "link", text: "https://example.com/a_(b)", href: "https://example.com/a_(b)" },
    { type: "text", text: ")" },
  ]);
});

test("splitDescription keeps heading with following list and leaves prose alone", () => {
  const blocks = [
    { type: "paragraph", text: "Intro" },
    { type: "heading", text: "Aufgaben" },
    { type: "list", ordered: false, items: ["A", "B"] },
    { type: "paragraph", text: "Outro" },
  ];
  const { prose, lists, hasLists } = splitDescription(blocks);
  assert.equal(hasLists, true);
  assert.deepEqual(prose, [
    { type: "paragraph", text: "Intro" },
    { type: "paragraph", text: "Outro" },
  ]);
  assert.deepEqual(lists, [
    { type: "heading", text: "Aufgaben" },
    { type: "list", ordered: false, items: ["A", "B"] },
  ]);
});

test("splitDescription prose-only has no lists", () => {
  const { prose, lists, hasLists } = splitDescription([
    { type: "heading", text: "About" },
    { type: "paragraph", text: "We build tools." },
  ]);
  assert.equal(hasLists, false);
  assert.equal(lists.length, 0);
  assert.equal(prose.length, 2);
});
