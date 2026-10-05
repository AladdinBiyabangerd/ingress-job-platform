"use client";

import { useEffect, useState } from "react";

/**
 * True while the media query matches. Always false on the server and on the
 * first client render, so markup never differs during hydration; CSS media
 * queries handle the visual layout before this flips.
 */
export function useMediaQuery(query) {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return undefined;
    const list = window.matchMedia(query);
    const update = () => setMatches(list.matches);
    update();
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, [query]);
  return matches;
}
