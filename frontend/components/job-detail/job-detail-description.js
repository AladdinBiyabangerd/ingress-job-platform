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

export function JobDetailDescription({ sections, benefits }) {
  const list = Array.isArray(sections) ? sections : [];
  const req = list.find((s) => s.id === "requirements");
  const nice = list.find((s) => s.id === "nice");
  const rest = list.filter((s) => s.id !== "requirements" && s.id !== "nice");
  const pair = Boolean(req && nice);

  return (
    <div className="jd-description">
      {rest.map((section) => (
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
      {Array.isArray(benefits) && benefits.length ? (
        <section className="jd-benefits" aria-label="Benefits">
          <h2 className="jd-desc-heading">Benefits</h2>
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
