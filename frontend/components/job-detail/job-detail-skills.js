import { text } from "../../lib/copy";

export function JobDetailSkills({ locale, skills }) {
  const t = text(locale);
  const list = Array.isArray(skills) ? skills.filter(Boolean) : [];
  if (!list.length) return null;

  return (
    <section className="jd-skills" aria-label={t.jdTechSkills}>
      <h2 className="jd-section-title">{t.jdTechSkills}</h2>
      <ul className="jd-skill-list">
        {list.map((name) => (
          <li key={name} className="jd-skill-pill">
            {name}
          </li>
        ))}
      </ul>
    </section>
  );
}
