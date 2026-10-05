import { hrefFor, text } from "../lib/copy";

// Background / text pairs that read well with white UI. Picked by a hash of the slug.
const AVATAR_COLORS = [
  ["#001FFF", "#ffffff"],
  ["#092F84", "#ffffff"],
  ["#0DC6FF", "#04204f"],
  ["#17603a", "#ffffff"],
  ["#e9f7ef", "#17603a"],
  ["#F00051", "#ffffff"],
  ["#fff4e5", "#8a4b00"],
  ["#5b3cc4", "#ffffff"],
  ["#eaefff", "#092F84"],
  ["#20242b", "#ffffff"],
];

function hash(value) {
  let h = 2166136261;
  for (const ch of String(value || "")) {
    h ^= ch.codePointAt(0);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h;
}

export function initials(name) {
  const words = String(name || "")
    .replace(/["'«»“”„‘’()]/g, " ")
    .split(/\s+/)
    .filter((word) => /\p{L}|\p{N}/u.test(word));
  const letters = words
    .slice(0, 2)
    .map((word) => Array.from(word.replace(/^[^\p{L}\p{N}]+/u, ""))[0] || "")
    .join("");
  return (letters || "?").toUpperCase();
}

export function CompanyAvatar({ name, slug, size = "md" }) {
  const [background, color] = AVATAR_COLORS[hash(slug || name) % AVATAR_COLORS.length];
  return (
    <span className={`company-avatar company-avatar-${size}`} style={{ background, color }} aria-hidden="true">
      {initials(name)}
    </span>
  );
}

export function percentText(value) {
  const number = Number(value) || 0;
  return `${Number.isInteger(number) ? number : number.toFixed(1)}%`;
}

/** Share of all on-site applications, as a bar. The definition is in the title and for screen readers. */
export function Popularity({ locale, share, compact = false, withHelp = true }) {
  const t = text(locale);
  const value = Math.max(0, Math.min(100, Number(share) || 0));
  const label = `${t.statPopularity}: ${percentText(value)}`;
  return (
    <span className={compact ? "popularity compact" : "popularity"} title={t.popularityHelp}>
      <span className="popularity-head">
        <span className="popularity-label">{t.statPopularity}</span>
        <span className="popularity-value">{percentText(value)}</span>
      </span>
      <span className="popularity-track" role="img" aria-label={label}>
        <span className="popularity-fill" style={{ width: `${value > 0 ? Math.max(value, 2) : 0}%` }} />
      </span>
      {withHelp ? <span className="visually-hidden">{t.popularityHelp}</span> : null}
    </span>
  );
}

export function companyHref(locale, slug) {
  return hrefFor(locale, { companySlug: slug });
}
