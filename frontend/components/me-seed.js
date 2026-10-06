"use client";

import { createContext, useContext } from "react";
import { seedMeCache } from "../lib/me-client";

const MeContext = createContext(undefined);

/** Puts SSR /me into context and the client cache so AccountBar skips the BFF. */
export function MeSeed({ me, children }) {
  if (typeof window !== "undefined" && me && typeof me === "object") {
    seedMeCache(me);
  }
  return <MeContext.Provider value={me}>{children}</MeContext.Provider>;
}

export function useInitialMe() {
  return useContext(MeContext);
}
