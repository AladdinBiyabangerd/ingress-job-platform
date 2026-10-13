"use client";

import { setCategoryCatalog } from "../lib/copy";

/** Registers the job_categories list from the layout fetch on the client. */
export function CategorySeed({ items }) {
  setCategoryCatalog(items);
  return null;
}
