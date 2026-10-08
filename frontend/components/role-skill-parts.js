/** Colored "you have" / "missing" summary for role suggestions and skill-gap. */

function namesFrom(items) {
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => {
      if (typeof item === "string") return item.trim();
      if (item && typeof item === "object") return String(item.name || "").trim();
      return "";
    })
    .filter(Boolean);
}

function formatNames(list, limit) {
  if (!limit || list.length <= limit) return list.join(", ");
  return `${list.slice(0, limit).join(", ")} +${list.length - limit}`;
}

export function RoleSkillParts({ t, have, missing, limit = 0 }) {
  const haveList = namesFrom(have);
  const missingList = namesFrom(missing);
  if (!haveList.length && !missingList.length) return null;

  return (
    <span className="hint role-skill-parts">
      {haveList.length ? (
        <span className="role-skill-have">
          <span className="role-skill-label">{t.skillsHave}</span>
          {`: ${formatNames(haveList, limit)}`}
        </span>
      ) : null}
      {haveList.length && missingList.length ? (
        <span className="role-skill-sep" aria-hidden="true">
          {" · "}
        </span>
      ) : null}
      {missingList.length ? (
        <span className="role-skill-missing">
          <span className="role-skill-label">{t.skillsMissing}</span>
          {`: ${formatNames(missingList, limit)}`}
        </span>
      ) : null}
    </span>
  );
}
