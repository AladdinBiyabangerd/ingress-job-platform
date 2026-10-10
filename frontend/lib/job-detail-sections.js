/** Map description blocks → titled detail sections (deterministic, no i18n). */

function normalizeHeading(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[:：]+$/u, "");
}

const WHY_KEYS = new Set([
  "why this role is interesting",
  "why this role",
  "niyə bu rol maraqlıdır",
  "niyə maraqlıdır",
  "почему эта роль интересна",
  "почему эта вакансия интересна",
]);
const ABOUT_KEYS = new Set([
  "about the role",
  "about",
  "about the product",
  "rol haqqında",
  "о роли",
  "о вакансии",
]);
const RESP_KEYS = new Set([
  "key responsibilities",
  "responsibilities",
  "what you'll do",
  "what you will do",
  "what you do",
  "in this role you will",
  "əsas vəzifələr",
  "vəzifələr",
  "обязанности",
  "чем предстоит заниматься",
]);
const REQ_KEYS = new Set([
  "requirements",
  "what we're looking for",
  "what we are looking for",
  "who we're looking for",
  "tələblər",
  "требования",
  "мы ищем",
]);
const NICE_KEYS = new Set([
  "nice to have",
  "would be a plus",
  "preferred qualifications and technologies",
  "preferred qualifications",
  "preferred",
  "üstünlük",
  "будет плюсом",
  "желательно",
]);
const BENEFIT_KEYS = new Set([
  "benefits",
  "what we offer",
  "what the employer offers",
  "what you'll get",
  "imkanlar",
  "льготы",
  "что мы предлагаем",
  "мы предлагаем",
]);

function sectionKind(title) {
  const key = normalizeHeading(title);
  if (WHY_KEYS.has(key)) return "why";
  if (ABOUT_KEYS.has(key)) return "about";
  if (RESP_KEYS.has(key)) return "responsibilities";
  if (REQ_KEYS.has(key)) return "requirements";
  if (NICE_KEYS.has(key)) return "nice";
  if (BENEFIT_KEYS.has(key)) return "benefits";
  // "What Acme is looking for" / "What Distribusion is looking for"
  if (/^what .+ is looking for$/u.test(key) || /^what .+ looking for$/u.test(key)) {
    return "requirements";
  }
  return "other";
}

/** Turn description blocks into titled sections for the detail layout. */
export function sectionsFromBlocks(blocks) {
  const sections = [];
  let current = null;

  function start(title, id) {
    const known = !String(id).startsWith("sec-");
    if (known) {
      const existing = sections.find((sec) => sec.id === id);
      if (existing) {
        current = existing;
        return;
      }
    }
    current = { id, title, type: "prose", paragraphs: [], items: [] };
    sections.push(current);
  }

  for (const block of blocks || []) {
    if (block.type === "heading") {
      const kind = sectionKind(block.text);
      start(block.text, kind === "other" ? `sec-${sections.length}` : kind);
      continue;
    }
    if (!current) start("", `sec-${sections.length}`);
    if (block.type === "list") {
      current.type = "list";
      current.items.push(...(block.items || []));
    } else if (block.text) {
      if (current.type === "list" && current.items.length) {
        start("", `sec-${sections.length}`);
      }
      current.type = "prose";
      current.paragraphs.push(block.text);
    }
  }

  return sections.filter((sec) => sec.paragraphs.length || sec.items.length);
}

export function benefitsFromSections(sections) {
  const benefit = (sections || []).find((sec) => sec.id === "benefits");
  if (!benefit || !benefit.items?.length) return [];
  if (benefit.items.some((item) => String(item).length > 80)) return [];
  return benefit.items.slice(0, 6).map((label, index) => ({
    id: `b-${index}`,
    label,
    icon: ["clock", "heart", "book", "globe", "shield", "star"][index % 6],
  }));
}

export function firstIntro(blocks, sections) {
  const about = (sections || []).find((sec) => sec.id === "about");
  if (about?.paragraphs?.[0]) {
    const value = about.paragraphs[0].trim();
    if (value.length <= 220) return value;
    return `${value.slice(0, 200).trim()}…`;
  }
  const why = (sections || []).find((sec) => sec.id === "why");
  if (why?.items?.length) {
    const value = why.items.slice(0, 2).join(" ");
    if (value.length <= 220) return value;
    return `${value.slice(0, 200).trim()}…`;
  }
  if (why?.paragraphs?.[0]) {
    const value = why.paragraphs[0].trim();
    if (value.length <= 220) return value;
    return `${value.slice(0, 200).trim()}…`;
  }
  const first = (blocks || []).find((b) => b.type !== "heading" && b.type !== "list" && b.text);
  if (!first?.text) return "";
  const value = first.text.trim();
  if (value.length <= 220) return value;
  return `${value.slice(0, 200).trim()}…`;
}
