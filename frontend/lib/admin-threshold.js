/**
 * Queue threshold panel (Faizə görə dərc et / AI ilə yenidən yoxla / Faizə uyğun rədd et).
 * Mirrors the API's `_ids_by_threshold`: rows without that score never match.
 */

export function jobScore(job, score) {
  const raw = score === "rule" ? job?.rule_confidence : job?.ai_confidence;
  if (raw == null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function thresholdMatchIds(items, score, op, threshold, status = "pending") {
  const raw = String(threshold ?? "").trim();
  const cut = Number(raw);
  const want = status === "rejected" ? "rejected" : "pending";
  if (raw === "" || !Number.isFinite(cut)) return [];
  return (items || [])
    .filter((job) => {
      if (job?.status !== want) return false;
      const value = jobScore(job, score);
      if (value == null) return false;
      return op === "lte" ? value <= cut : value >= cut;
    })
    .map((job) => job.id);
}
