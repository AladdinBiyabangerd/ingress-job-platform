/** Client-side list filters for admin moderation tables. */

export function emptyAdminListFilter() {
  return {
    aiOp: "gte",
    aiValue: "",
    ruleOp: "gte",
    ruleValue: "",
    source: "",
  };
}

export function adminListFilterActive(filter) {
  if (!filter) return false;
  return (
    String(filter.aiValue || "").trim() !== "" ||
    String(filter.ruleValue || "").trim() !== "" ||
    String(filter.source || "").trim() !== ""
  );
}

function numericScore(item, kind) {
  const raw = kind === "rule" ? item.rule_confidence : item.ai_confidence;
  if (raw == null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function scorePasses(value, op, cut) {
  if (value == null) return false;
  return op === "lte" ? value <= cut : value >= cut;
}

export function matchesAdminListFilter(item, filter) {
  if (!filter) return true;

  const aiRaw = String(filter.aiValue || "").trim();
  if (aiRaw !== "") {
    const cut = Number(aiRaw);
    if (Number.isFinite(cut) && !scorePasses(numericScore(item, "ai"), filter.aiOp, cut)) {
      return false;
    }
  }

  const ruleRaw = String(filter.ruleValue || "").trim();
  if (ruleRaw !== "") {
    const cut = Number(ruleRaw);
    if (Number.isFinite(cut) && !scorePasses(numericScore(item, "rule"), filter.ruleOp, cut)) {
      return false;
    }
  }

  const q = String(filter.source || "").trim().toLowerCase();
  if (q) {
    const name = String(item.source_name || "").toLowerCase();
    const url = String(item.source_url || "").toLowerCase();
    if (!name.includes(q) && !url.includes(q)) return false;
  }

  return true;
}

export function filterAdminList(items, filter) {
  const list = Array.isArray(items) ? items : [];
  if (!adminListFilterActive(filter)) return list;
  return list.filter((item) => matchesAdminListFilter(item, filter));
}
