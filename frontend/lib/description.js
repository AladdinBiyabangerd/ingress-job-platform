/**
 * Turns a stored job description (plain text from the worker's cleaner, an
 * LLM-tidied version, or older text where every inline HTML tag became its own
 * line) into display blocks: headings, paragraphs and lists.
 *
 * Pure and deterministic, so the server render and any client render match.
 * Nothing here returns HTML; the page renders the blocks as React elements and
 * only ever links http(s) URLs.
 */

const TERMINAL = /[.!?…:;]["'”»’)\]]*$/u;
const SENTENCE_END = /[.!?…]["'”»’)\]]*$/u;
const OPEN_ONLY = /^[«“„"'(\[‘]+$/u;
const CLOSE_START = /^[»”’)\],.;:!?%]/u;
const MARKER_ONLY = /^(?:[•●▪‣◦·∙■□➤►✓✔→*]|[-–—])$/u;
const BULLET = /^(?:[•●▪‣◦·∙■□➤►✓✔→]\s*|[*\-–—]\s+)(\S.*)$/u;
const NUMBERED = /^(\d{1,2})[.)]\s+(\S.*)$/u;
const RULE = /^[-_=*~•.\s]{3,}$/u;
const PUNCT_ONLY = /^[,.;:!?]+$/u;
const LOWER_START = /^\p{Ll}/u;
const UPPER_START = /^[\p{Lu}\d]/u;
const ENDS_LOWER = /\p{Ll}$/u;
const URL_ONLY = /^(?:https?:\/\/|www\.)\S+$/iu;

const CONNECTORS = new Set(
  (
    "a an the and or of for to with in on at by as from into onto our your their its " +
    "who whom whose that which than via per including about across within without but nor " +
    "və ilə üçün olan bir da də ya həm və ki kimi görə qədər " +
    "и в во на с со для по к ко о об от из или а но что как же при до за под над без у"
  ).split(/\s+/),
);

const LIST_MAX = 220;
const HEADING_MAX = 70;

function words(line) {
  return line.split(/\s+/).filter(Boolean);
}

function lastWord(line) {
  const list = words(line);
  return (list[list.length - 1] || "").toLowerCase().replace(/[^\p{L}]/gu, "");
}

export function bulletOf(line) {
  const numbered = line.match(NUMBERED);
  if (numbered) return { ordered: true, text: numbered[2].trim() };
  const marked = line.match(BULLET);
  if (marked) return { ordered: false, text: marked[1].trim() };
  return null;
}

function isFragment(line) {
  return line.length <= 40 && words(line).length <= 4 && !TERMINAL.test(line) && !bulletOf(line);
}

function isLabel(line) {
  return /^[^:]{1,30}:$/u.test(line) && words(line).length <= 3 && !bulletOf(line);
}

function isValue(line) {
  if (!line || bulletOf(line) || line.endsWith(":")) return false;
  return line.length <= 120 || URL_ONLY.test(line);
}

function headingLike(line) {
  if (!line || line.length > 50 || bulletOf(line)) return false;
  if (TERMINAL.test(line) || /[,;:]/.test(line)) return false;
  if (!/^\p{Lu}/u.test(line)) return false;
  return words(line).length <= 6;
}

function explicitHeading(line) {
  return line.endsWith(":") && line.length <= HEADING_MAX && words(line).length <= 9 && !bulletOf(line);
}

/** Raw text -> groups of trimmed lines; a blank line (or a rule) starts a new group. */
function groupsOf(raw) {
  const groups = [];
  let current = [];
  const lines = String(raw || "")
    .replace(/\r\n?/g, "\n")
    .replace(/[\u00a0\u2007\u202f]/g, " ")
    .replace(/[\u200b\u200c\u200d\ufeff]/g, "")
    .split("\n");
  for (const rawLine of lines) {
    const line = rawLine.replace(/[ \t]+/g, " ").trim();
    if (!line || RULE.test(line)) {
      if (current.length) groups.push(current);
      current = [];
      continue;
    }
    current.push(line);
  }
  if (current.length) groups.push(current);
  return groups;
}

/**
 * Glue lines that were split mid-sentence (an inline tag such as <strong> or
 * <a> rendered as its own line). "looking for a" / "Junior" / "Product
 * Manager" / "who will drive..." becomes one sentence.
 */
export function joinBrokenLines(lines) {
  const out = [];
  lines = lines.filter((line, index) => {
    const next = lines[index + 1];
    return !(next && next.replace(/:$/u, "") === line && next !== line);
  });
  let joined = false;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const prev = out[out.length - 1];
    const next = lines[i + 1];
    if (prev === undefined) {
      out.push(line);
      joined = false;
      continue;
    }
    if (MARKER_ONLY.test(prev)) {
      out[out.length - 1] = `${/[-–—]/u.test(prev) ? "-" : "•"} ${line}`;
      joined = false;
      continue;
    }
    if (OPEN_ONLY.test(prev) || /[«“„]$/u.test(prev)) {
      out[out.length - 1] = prev + line;
      joined = true;
      continue;
    }
    if (PUNCT_ONLY.test(line) || (CLOSE_START.test(line) && !bulletOf(line))) {
      out[out.length - 1] = prev + line;
      joined = true;
      continue;
    }
    if (shouldJoin(prev, line, next, joined)) {
      out[out.length - 1] = `${prev} ${line}`;
      joined = true;
      continue;
    }
    out.push(line);
    joined = false;
  }
  return out;
}

function shouldJoin(prev, line, next, prevJoined) {
  if (bulletOf(line) || MARKER_ONLY.test(line)) return false;
  if (TERMINAL.test(prev)) return false;
  if (/[,(\-–—/&+]$/u.test(prev)) return true;
  if (CONNECTORS.has(lastWord(prev)) && !explicitHeading(line)) return true;
  const midSentence = prevJoined || (ENDS_LOWER.test(prev) && words(prev).length >= 2);
  if (LOWER_START.test(line) && (midSentence || prev.length > 60)) return true;
  if (isFragment(line) && next && (LOWER_START.test(next) || CLOSE_START.test(next)) && midSentence) return true;
  return false;
}

/** "Type:" / "Full time" / "Salary:" / "$100k" -> "Type: Full time", "Salary: $100k". */
export function joinLabels(lines) {
  const out = [];
  let i = 0;
  while (i < lines.length) {
    let j = i;
    let pairs = 0;
    while (j + 1 < lines.length && isLabel(lines[j]) && isValue(lines[j + 1])) {
      pairs += 1;
      j += 2;
    }
    const after = lines[j];
    const single =
      pairs === 1 &&
      words(lines[i]).length <= 2 &&
      (lines[i + 1].length <= 40 || URL_ONLY.test(lines[i + 1])) &&
      (after === undefined || after.length > 80 || isLabel(after));
    if (pairs >= 2 || single) {
      for (let k = i; k < j; k += 2) out.push(`${lines[k]} ${lines[k + 1]}`);
      i = j;
      continue;
    }
    out.push(lines[i]);
    i += 1;
  }
  return out;
}

function kindOf(line) {
  if (bulletOf(line)) return "bullet";
  if (explicitHeading(line)) return "heading";
  if (line.endsWith(":")) return "lead";
  if (line.length > LIST_MAX) return "long";
  return "short";
}

function pushParagraphs(out, lines) {
  for (const line of lines) out.push({ type: "paragraph", text: line });
}

function pushList(out, items, ordered = false) {
  const last = out[out.length - 1];
  if (last && last.type === "list" && last.ordered === ordered && last.loose) {
    last.items.push(...items);
    return;
  }
  out.push({ type: "list", ordered, items: [...items] });
}

/** Lines without bullet markers: decide between headings, a list and paragraphs. */
function classifyRun(run, context, nextKind, out) {
  let lines = run;
  let ctx = context;
  if (lines.length >= 3 && headingLike(lines[0]) && words(lines[0]).length >= 2) {
    out.push({ type: "heading", text: lines[0] });
    lines = lines.slice(1);
    ctx = true;
  } else if (
    !ctx &&
    lines.length >= 3 &&
    words(lines[0]).length <= 8 &&
    ENDS_LOWER.test(lines[0]) &&
    (lines[0].includes(",") || words(lines[0]).length >= 3) &&
    UPPER_START.test(lines[1]) &&
    lines[0].length <= 80
  ) {
    out.push({ type: "paragraph", text: lines[0] });
    lines = lines.slice(1);
    ctx = true;
  }

  // Short headings inside a run of items, e.g. "It’s all about you" before longer lines.
  const parts = [];
  let current = [];
  lines.forEach((line, index) => {
    const following = lines[index + 1];
    const isLast = index === lines.length - 1;
    const innerHeading =
      headingLike(line) &&
      line.length <= 32 &&
      following !== undefined &&
      following.length >= Math.max(35, line.length * 2.2) &&
      (words(line).length >= 2 || (lines[index + 2] !== undefined && current.length === 0));
    // A change of rhythm: long items, then a short title, then short items ("Hiring process").
    const before = current.slice(-2);
    const after = lines.slice(index + 1, index + 3);
    const rhythmHeading =
      headingLike(line) &&
      line.length <= 32 &&
      words(line).length >= 2 &&
      before.length === 2 &&
      after.length === 2 &&
      (before[0].length + before[1].length) / 2 >= line.length * 2 &&
      Math.max(after[0].length, after[1].length) <= Math.max(20, line.length * 1.3);
    const average = current.length ? current.reduce((sum, item) => sum + item.length, 0) / current.length : 0;
    const sandwiched =
      words(line).length === 1 &&
      line.length <= 24 &&
      current.length > 0 &&
      following !== undefined &&
      current[current.length - 1].length >= Math.max(35, line.length * 2.5) &&
      following.length >= Math.max(35, line.length * 2.5);
    const tailHeading =
      isLast &&
      lines.length > 1 &&
      headingLike(line) &&
      words(line).length >= 2 &&
      line.length <= 32 &&
      line.length <= average * 0.6 &&
      (nextKind === "heading" || nextKind === "bullet");
    if (innerHeading || rhythmHeading || sandwiched || tailHeading) {
      parts.push({ lines: current });
      parts.push({ heading: line });
      current = [];
      return;
    }
    current.push(line);
  });
  parts.push({ lines: current });

  for (const part of parts) {
    if (part.heading) {
      out.push({ type: "heading", text: part.heading });
      ctx = true;
      continue;
    }
    const items = part.lines;
    if (!items.length) continue;
    const average = items.reduce((sum, line) => sum + line.length, 0) / items.length;
    const prose = items.every((line) => SENTENCE_END.test(line)) && average > 110;
    if (!prose && (items.length >= 3 || (items.length >= 2 && ctx))) {
      out.push({ type: "list", ordered: false, items: [...items] });
    } else if (
      items.length === 1 &&
      run.length === 1 &&
      headingLike(items[0]) &&
      ((words(items[0]).length >= 2 && nextKind !== "end") || nextKind === "bullet")
    ) {
      out.push({ type: "heading", text: items[0] });
    } else {
      pushParagraphs(out, items);
    }
    ctx = false;
  }
}

function classifyGroup(lines, context, nextGroupStart, out) {
  let ctx = context;
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const kind = kindOf(line);
    if (kind === "bullet") {
      const first = bulletOf(line);
      const items = [];
      while (i < lines.length && bulletOf(lines[i]) && bulletOf(lines[i]).ordered === first.ordered) {
        items.push(bulletOf(lines[i]).text);
        i += 1;
      }
      out.push({ type: "list", ordered: first.ordered, items });
      ctx = false;
      continue;
    }
    if (kind === "heading") {
      out.push({ type: "heading", text: line.replace(/\s*:$/u, "") });
      ctx = true;
      i += 1;
      continue;
    }
    if (kind === "lead") {
      out.push({ type: "paragraph", text: line });
      ctx = true;
      i += 1;
      continue;
    }
    if (kind === "long") {
      out.push({ type: "paragraph", text: line });
      ctx = false;
      i += 1;
      continue;
    }
    const run = [];
    while (i < lines.length && kindOf(lines[i]) === "short") {
      run.push(lines[i]);
      i += 1;
    }
    const nextKind = i < lines.length ? kindOf(lines[i]) : nextGroupStart ? kindOf(nextGroupStart) : "end";
    classifyRun(run, ctx, nextKind, out);
    const last = out[out.length - 1];
    ctx = Boolean(last && last.type === "heading");
  }
  return ctx;
}

/** Description text -> [{type: "heading"|"paragraph", text} | {type: "list", ordered, items}]. */
export function descriptionBlocks(raw, title = "") {
  const groups = groupsOf(raw).map((group) => joinLabels(joinBrokenLines(group)));
  const wanted = String(title || "").trim().toLowerCase();
  if (wanted && groups.length && groups[0][0] && groups[0][0].toLowerCase() === wanted) {
    groups[0] = groups[0].slice(1);
  }
  const out = [];
  let ctx = false;
  groups.forEach((group, index) => {
    if (!group.length) return;
    const nextStart = groups[index + 1] ? groups[index + 1][0] : undefined;
    ctx = classifyGroup(group, ctx, nextStart, out);
  });
  return out.filter((block) => (block.type === "list" ? block.items.length : /[\p{L}\p{N}]/u.test(block.text)));
}

const URL_RE = /\b(?:https?:\/\/|www\.)[^\s<>"'«»“”]+/giu;

/** Splits text into plain parts and safe http(s) links. */
export function linkParts(value) {
  const textValue = String(value || "");
  const parts = [];
  let last = 0;
  for (const match of textValue.matchAll(URL_RE)) {
    let url = match[0];
    const trailing = url.match(/[.,;:!?)\]]+$/u);
    if (trailing) {
      let cut = trailing[0];
      if (cut.startsWith(")") && url.includes("(")) cut = cut.slice(1);
      url = url.slice(0, url.length - cut.length);
    }
    const start = match.index;
    if (start > last) parts.push({ type: "text", text: textValue.slice(last, start) });
    const href = url.toLowerCase().startsWith("www.") ? `https://${url}` : url;
    if (/^https?:\/\/[^\s/]+\.[^\s/]+/iu.test(href)) {
      parts.push({ type: "link", text: url, href });
    } else {
      parts.push({ type: "text", text: url });
    }
    last = start + url.length;
  }
  if (last < textValue.length) parts.push({ type: "text", text: textValue.slice(last) });
  return parts;
}
