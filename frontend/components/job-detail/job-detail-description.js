import { linkParts } from "../../lib/description";
import { JdIcon } from "./jd-icons";

function Linked({ value }) {
  return linkParts(value).map((part, index) =>
    part.type === "link" ? (
      <a key={index} href={part.href} target="_blank" rel="nofollow noopener noreferrer ugc">
        {part.text}
      </a>
    ) : (
      <span key={index}>{part.text}</span>
    ),
  );
}

function SectionBlock({ section }) {
  if (!section) return null;
  return (
    <section className="jd-desc-section" data-section={section.id || undefined}>
      {section.title ? <h2 className="jd-desc-heading">{section.title}</h2> : null}
      {section.type === "list" ? (
        <ul className="jd-desc-list">
          {(section.items || []).map((item, index) => (
            <li key={index}>
              <Linked value={item} />
            </li>
          ))}
        </ul>
      ) : (
        (section.paragraphs || []).map((p, index) => (
          <p key={index} className="jd-desc-p">
            <Linked value={p} />
          </p>
        ))
      )}
    </section>
  );
}

export function JobDetailDescription({ sections, benefits, benefitsTitle = "Benefits" }) {
  const list = Array.isArray(sections) ? sections : [];
  const why = list.find((s) => s.id === "why");
  const about = list.find((s) => s.id === "about");
  const resp = list.find((s) => s.id === "responsibilities");
  const req = list.find((s) => s.id === "requirements");
  const nice = list.find((s) => s.id === "nice");
  const known = new Set(["why", "about", "responsibilities", "requirements", "nice"]);
  const rest = list.filter((s) => !known.has(s.id));
  const pair = Boolean(req && nice);
  const ordered = [why, about, resp].filter(Boolean);

  return (
    <div className="jd-description">
      {ordered.map((section) => (
        <SectionBlock key={section.id || section.title} section={section} />
      ))}
      {pair ? (
        <div className="jd-desc-pair">
          <SectionBlock section={req} />
          <SectionBlock section={nice} />
        </div>
      ) : (
        <>
          {req ? <SectionBlock section={req} /> : null}
          {nice ? <SectionBlock section={nice} /> : null}
        </>
      )}
      {rest.map((section) => (
        <SectionBlock key={section.id || section.title} section={section} />
      ))}
      {Array.isArray(benefits) && benefits.length ? (
        <section className="jd-benefits" aria-label={benefitsTitle}>
          <h2 className="jd-desc-heading">{benefitsTitle}</h2>
          <ul className="jd-benefits-grid">
            {benefits.map((item) => (
              <li key={item.id} className="jd-benefit">
                <span className="jd-benefit-icon" aria-hidden="true">
                  <JdIcon name={item.icon || "star"} size={18} />
                </span>
                <span>{item.label}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
