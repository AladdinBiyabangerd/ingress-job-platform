export const MONTHS = {
  az: ["yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avq", "sen", "okt", "noy", "dek"],
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  ru: ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
};

/**
 * "2026-10-04T16:35:52+04:00" -> "4 okt 2026". Reads the calendar date as
 * written (the API stores Baku time) instead of converting through the
 * runtime's time zone, so the server and the browser print the same text.
 */
export function calendarDate(value, locale) {
  const match = String(value || "").trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return "";
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return "";
  const months = MONTHS[locale] || MONTHS.az;
  return `${day} ${months[month - 1]} ${match[1]}`;
}
