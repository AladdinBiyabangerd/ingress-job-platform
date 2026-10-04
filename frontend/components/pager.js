"use client";

import { text } from "../lib/copy";

export function Pager({ locale, currentPage, totalPages, total, pageSize, onPageChange }) {
  const t = text(locale);
  if (!total || total <= pageSize) return null;

  return (
    <nav className="pager" aria-label={t.pageOf(currentPage, totalPages)}>
      <button
        type="button"
        className="pager-btn"
        disabled={currentPage <= 1}
        onClick={() => onPageChange(currentPage - 1)}
      >
        {t.pagePrev}
      </button>
      <span className="pager-status">{t.pageOf(currentPage, totalPages)}</span>
      <button
        type="button"
        className="pager-btn"
        disabled={currentPage >= totalPages}
        onClick={() => onPageChange(currentPage + 1)}
      >
        {t.pageNext}
      </button>
    </nav>
  );
}
