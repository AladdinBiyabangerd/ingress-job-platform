"use client";

import { useEffect, useMemo, useState } from "react";

export const LIST_PAGE_SIZE = 10;

export function usePagination(items, pageSize = LIST_PAGE_SIZE) {
  const list = Array.isArray(items) ? items : [];
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(list.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return list.slice(start, start + pageSize);
  }, [list, currentPage, pageSize]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  function goToPage(next) {
    setPage(Math.max(1, Math.min(totalPages, next)));
  }

  function resetPage() {
    setPage(1);
  }

  return {
    pageItems,
    currentPage,
    totalPages,
    pageSize,
    total: list.length,
    goToPage,
    resetPage,
  };
}
