"use client";

import { useState } from "react";
import { skillIconMeta, skillInitials } from "../lib/skill-icons";

export function SkillIcon({ name, className = "" }) {
  const meta = skillIconMeta(name);
  const [failed, setFailed] = useState(false);
  const wrap = `skill-icon ${className}`.trim();

  if (!meta || failed) {
    return (
      <span className={`${wrap} skill-icon-fallback`} aria-hidden="true">
        {skillInitials(name)}
      </span>
    );
  }

  return (
    <span className={wrap} aria-hidden="true">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        className="skill-icon-img"
        src={`https://cdn.simpleicons.org/${meta.slug}/${meta.color}`}
        alt=""
        width={18}
        height={18}
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
      />
    </span>
  );
}
