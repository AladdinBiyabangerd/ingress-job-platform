import {
  academyCareerPathUrl,
  academyCourseLabel,
  academyCourseUrl,
} from "../lib/academy-urls";

const GROWTH_CAP_PCT = 300;
const MAX_COURSE_LINKS = 2;

export function sharePct(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return Math.round(value * 100);
}

export function growthLabel(t, growth) {
  if (typeof growth !== "number" || Number.isNaN(growth)) return null;
  const pct = Math.round(growth * 100);
  if (!Number.isFinite(pct) || pct === 0) return null;
  if (Math.abs(pct) > GROWTH_CAP_PCT) {
    return pct > 0 ? t.recommendationsGapGrowthSurge : t.recommendationsGapGrowthDrop;
  }
  return t.recommendationsGapGrowth(pct);
}

export function CareerPathLink({ t, pathId }) {
  const href = academyCareerPathUrl(pathId);
  if (!href) return null;
  return (
    <a className="skills-career-link" href={href} target="_blank" rel="noreferrer">
      {t.recommendationsGapCareerPath}
    </a>
  );
}

export function AcademyCourseLinks({ item }) {
  const courses = Array.isArray(item?.academy_courses)
    ? item.academy_courses.map((id) => String(id || "").trim()).filter(Boolean)
    : [];
  if (!courses.length) return null;
  const visible = courses.slice(0, MAX_COURSE_LINKS);
  const extra = courses.length - visible.length;
  return (
    <span className="skills-course-links">
      {visible.map((courseId) => {
        const href = academyCourseUrl(courseId);
        if (!href) return null;
        const label = academyCourseLabel(courseId);
        return (
          <a
            key={courseId}
            className="skills-course-link"
            href={href}
            target="_blank"
            rel="noreferrer"
            title={label}
          >
            {label}
          </a>
        );
      })}
      {extra > 0 ? (
        <span className="skills-course-more" title={courses.slice(MAX_COURSE_LINKS).map(academyCourseLabel).join(", ")}>
          +{extra}
        </span>
      ) : null}
    </span>
  );
}

export function OftenWith({ t, item }) {
  const hit = item?.often_with;
  if (!hit || typeof hit !== "object") return null;
  const base = String(hit.base_name || "").trim();
  const pct = sharePct(hit.share);
  if (!base || pct === null) return null;
  return <span className="hint">{t.recommendationsGapOftenWith(base, pct)}</span>;
}

export function SkillShareBar({ share }) {
  const pct = sharePct(share);
  if (pct === null) return null;
  const width = Math.max(4, Math.min(100, pct));
  return (
    <div className="skills-share" title={`${pct}%`}>
      <div className="skills-share-track" aria-hidden="true">
        <div className="skills-share-fill" style={{ width: `${width}%` }} />
      </div>
      <span className="skills-share-label">{pct}%</span>
    </div>
  );
}

export function SkillRow({ t, item, tone }) {
  const growth = growthLabel(t, item.growth);
  const showCourses = tone === "missing";
  return (
    <li className={`skills-row skills-row-${tone}`}>
      <div className="skills-row-top">
        <strong className="skills-row-name">{item.name}</strong>
        {showCourses ? <AcademyCourseLinks item={item} /> : null}
      </div>
      <SkillShareBar share={item.share} />
      <div className="skills-row-meta">
        {growth ? <span className="hint">{growth}</span> : null}
        <OftenWith t={t} item={item} />
      </div>
    </li>
  );
}
