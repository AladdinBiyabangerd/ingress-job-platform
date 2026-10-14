"use client";

import { useLayoutEffect, useState } from "react";
import { browseHrefFromPersist } from "../lib/board-persist";
import { hrefFor } from "../lib/copy";

/**
 * Browse/home link that appends persisted board filters after mount
 * so leave → Jobs / logo keeps the same filters until clear.
 */
export function PersistedBrowseLink({
  locale,
  className,
  children,
  "aria-current": ariaCurrent,
  ...rest
}) {
  const base = hrefFor(locale) || "/";
  const [href, setHref] = useState(base);

  useLayoutEffect(() => {
    setHref(browseHrefFromPersist(locale));
  }, [locale]);

  return (
    <a href={href} className={className} aria-current={ariaCurrent} {...rest}>
      {children}
    </a>
  );
}
