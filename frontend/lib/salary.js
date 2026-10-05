/**
 * schema.org baseSalary for a job's free-text salary, without guessing.
 *
 * The salary text is shown exactly as the source wrote it; this only builds
 * the JSON-LD. Currency and period come from the text itself (no conversion,
 * no default): "45,000–55,000 GBP per annum", "€60k a year", "1500-2000 AZN
 * aylıq", "78 GBP per hour". When the currency or the period is missing or
 * ambiguous (a bare "$", two currencies, no period), nothing is returned so
 * the page carries no salary claim at all.
 */

const CODES = [
  "AZN", "GBP", "EUR", "USD", "CAD", "AUD", "NZD", "CHF", "SEK", "NOK", "DKK", "PLN", "CZK",
  "HUF", "RON", "BGN", "TRY", "UAH", "RUB", "GEL", "KZT", "INR", "JPY", "CNY", "KRW", "SGD",
  "HKD", "AED", "SAR", "QAR", "ILS", "ZAR", "BRL", "MXN", "ARS", "CLP", "COP",
];

// Unambiguous symbols and words only. "$", "¥", "kr" are left out on purpose.
const SYMBOLS = [
  [/£/, "GBP"],
  [/€/, "EUR"],
  [/₼|\bmanat\b|\bman\.(?=\s|$)/i, "AZN"],
  [/₽|\bруб/i, "RUB"],
  [/₹/, "INR"],
  [/₩/, "KRW"],
  [/₺/, "TRY"],
  [/₴|\bгрн\b/i, "UAH"],
  [/\bUS\$|\bUS\s?dollars?\b/i, "USD"],
  [/\bC\$|\bCA\$/, "CAD"],
  [/\bA\$|\bAU\$/, "AUD"],
  [/\bS\$/, "SGD"],
  [/\bR\$/, "BRL"],
];

const PERIODS = [
  ["YEAR", /\bper\s+(?:annum|year)\b|\ba\s+year\b|\bannual(?:ly)?\b|\byearly\b|\/\s*(?:year|yr|y)\b|\bp\.?\s?a\.?(?=\s|$|[),])|\billik\b|\bв\s+год\b|\bгодов/i],
  ["MONTH", /\bper\s+month\b|\ba\s+month\b|\bmonthly\b|\/\s*(?:month|mo|mon)\b|\baylıq\b|\bayda\b|\bв\s+месяц\b|\bмес\b|\/\s*мес/i],
  ["WEEK", /\bper\s+week\b|\ba\s+week\b|\bweekly\b|\/\s*(?:week|wk)\b|\bhəftəlik\b|\bв\s+неделю\b/i],
  ["DAY", /\bper\s+day\b|\ba\s+day\b|\bdaily\b|\/\s*day\b|\bgünlük\b|\bв\s+день\b/i],
  ["HOUR", /\bper\s+hour\b|\ban\s+hour\b|\bhourly\b|\/\s*(?:hour|hr|h)\b|\bsaatlıq\b|\bв\s+час\b/i],
];

export function salaryCurrency(text) {
  const raw = String(text || "");
  const found = new Set();
  const upper = raw.toUpperCase();
  for (const code of CODES) {
    if (new RegExp(`(^|[^A-Z])${code}([^A-Z]|$)`).test(upper)) found.add(code);
  }
  for (const [pattern, code] of SYMBOLS) {
    if (pattern.test(raw)) found.add(code);
  }
  return found.size === 1 ? [...found][0] : "";
}

export function salaryPeriod(text) {
  const raw = String(text || "");
  const found = PERIODS.filter(([, pattern]) => pattern.test(raw)).map(([unit]) => unit);
  return found.length === 1 ? found[0] : "";
}

function toNumber(token, suffix) {
  let digits = token.replace(/\s+/g, "");
  if (digits.includes(",") && digits.includes(".")) {
    // The later separator is the decimal one: "1,234.50" or "1.234,50".
    digits = digits.lastIndexOf(".") > digits.lastIndexOf(",")
      ? digits.replace(/,/g, "")
      : digits.replace(/\./g, "").replace(",", ".");
  } else if (/^\d{1,3}([,.]\d{3})+$/.test(digits)) {
    digits = digits.replace(/[,.]/g, ""); // thousands groups only
  } else {
    digits = digits.replace(",", ".");
  }
  let value = Number(digits);
  if (!Number.isFinite(value) || value <= 0) return undefined;
  if (suffix && /k/i.test(suffix)) value *= 1000;
  return value;
}

export function salaryAmounts(text) {
  const raw = String(text || "");
  const out = [];
  const pattern = /(\d{1,3}(?:[ \u00a0,.]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*([kK])?\b/g;
  let match;
  while ((match = pattern.exec(raw))) {
    const value = toNumber(match[1], match[2]);
    if (value !== undefined) out.push(value);
  }
  return out;
}

export function salaryJsonLd(salary) {
  const raw = String(salary || "").trim();
  if (!raw) return undefined;
  const currency = salaryCurrency(raw);
  const unitText = salaryPeriod(raw);
  if (!currency || !unitText) return undefined;
  const amounts = salaryAmounts(raw);
  if (amounts.length === 0 || amounts.length > 2) return undefined;
  const value = { "@type": "QuantitativeValue", unitText };
  if (amounts.length === 2 && amounts[0] !== amounts[1]) {
    value.minValue = Math.min(...amounts);
    value.maxValue = Math.max(...amounts);
  } else {
    value.value = amounts[0];
  }
  return { "@type": "MonetaryAmount", currency, value };
}
