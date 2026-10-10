import { JdIcon } from "./jd-icons";

function MetaItem({ icon, children }) {
  if (!children) return null;
  return (
    <li className="jd-meta-item">
      <JdIcon name={icon} size={16} />
      <span>{children}</span>
    </li>
  );
}

export function JobDetailMeta({ meta }) {
  if (!meta) return null;
  const row1 = [
    { icon: "pin", value: meta.location },
    { icon: "cloud", value: meta.remote },
    { icon: "swap", value: meta.relocation },
    { icon: "briefcase", value: meta.jobType },
  ].filter((item) => item.value);
  const row2 = [
    { icon: "shield", value: meta.experience, pill: true },
    { icon: "globe", value: meta.languages, pill: true },
    { icon: "wallet", value: meta.salary, pill: true },
  ].filter((item) => item.value);

  if (!row1.length && !row2.length && !meta.posted) return null;

  return (
    <div className="jd-meta">
      {row1.length ? (
        <ul className="jd-meta-row">
          {row1.map((item) => (
            <MetaItem key={item.icon + String(item.value)} icon={item.icon}>
              {item.value}
            </MetaItem>
          ))}
        </ul>
      ) : null}
      {row2.length || meta.posted ? (
        <div className="jd-meta-row jd-meta-row-mixed">
          <ul className="jd-meta-pills">
            {row2.map((item) => (
              <li key={item.icon + String(item.value)} className="jd-meta-pill">
                <JdIcon name={item.icon} size={15} />
                <span>{item.value}</span>
              </li>
            ))}
          </ul>
          {meta.posted ? (
            <p className="jd-meta-posted">
              <JdIcon name="clock" size={15} />
              {meta.postedDateTime ? <time dateTime={meta.postedDateTime}>{meta.posted}</time> : <span>{meta.posted}</span>}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
