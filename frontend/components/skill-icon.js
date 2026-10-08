"use client";

import { useState } from "react";
import { skillIconSrc, skillInitials } from "../lib/skill-icons";

export function SkillIcon({ name, className = "" }) {
  const src = skillIconSrc(name);
  const [failed, setFailed] = useState(false);
  const wrap = `skill-icon ${className}`.trim();

  if (!src || failed) {
    return (
      <span className={`${wrap} skill-icon-fallback`} aria-hidden="true">
        {skillInitials(name)}
      </span>
    );
  }

  return (
    <span className={wrap} aria-hidden="true">
      {/* eslint-disable-next-line @next/next/no-img-element -- Devicon CDN; Next Image domains not configured */}
      <img
        className="skill-icon-img"
        src={src}
        alt=""
        width={18}
        height={18}
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
      />
    </span>
  );
}
