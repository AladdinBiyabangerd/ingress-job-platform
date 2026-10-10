import { hrefFor, text } from "../lib/copy";
import { ingressUrl } from "../lib/ingress";

function SideNavIconBrowse() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2" />
    </svg>
  );
}

function SideNavIconSaved() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M7 3.5h10a1 1 0 011 1V21l-6-3.5L6 21V4.5a1 1 0 011-1z" />
    </svg>
  );
}

function SideNavIconApplied() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M8 4h8a2 2 0 012 2v14l-6-3-6 3V6a2 2 0 012-2z" />
      <path d="M9 10h6M9 14h4" />
    </svg>
  );
}

function SideNavIconPost() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function SideNavIconMe() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 19.5c1.5-3 4-4.5 7-4.5s5.5 1.5 7 4.5" />
    </svg>
  );
}

function SideNavIconAcademy() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M5 10v5c0 1.5 3 3 7 3s7-1.5 7-3v-5" />
    </svg>
  );
}

function navItemClass(active, key) {
  return active === key ? "on" : "";
}

/** Left rail shared by board surfaces (jobs, companies, …). */
export function BoardSideNav({ locale, active = null }) {
  const t = text(locale);
  return (
    <aside className="home-board-nav" aria-label={t.browse}>
      <nav className="home-board-nav-list">
        <a
          href={hrefFor(locale)}
          className={navItemClass(active, "browse")}
          aria-current={active === "browse" ? "page" : undefined}
        >
          <SideNavIconBrowse />
          <span>{t.navBrowseJobs}</span>
        </a>
        <a
          href={hrefFor(locale, { mode: "saved" })}
          className={navItemClass(active, "saved")}
          aria-current={active === "saved" ? "page" : undefined}
        >
          <SideNavIconSaved />
          <span>{t.navSavedJobs}</span>
        </a>
        <a
          href={hrefFor(locale, { mode: "applications" })}
          className={navItemClass(active, "applications")}
          aria-current={active === "applications" ? "page" : undefined}
        >
          <SideNavIconApplied />
          <span>{t.navAppliedJobs}</span>
        </a>
        <a
          href={hrefFor(locale, { mode: "profile" })}
          className={navItemClass(active, "profile")}
          aria-current={active === "profile" ? "page" : undefined}
        >
          <SideNavIconMe />
          <span>{t.navMe}</span>
        </a>
      </nav>
      <div className="home-board-nav-employer">
        <a
          href={hrefFor(locale, { mode: "post" })}
          className={navItemClass(active, "post")}
          aria-current={active === "post" ? "page" : undefined}
        >
          <SideNavIconPost />
          <span>{t.navPostRole}</span>
        </a>
      </div>
      <a
        className="home-board-nav-academy"
        href={ingressUrl(locale)}
        rel="noopener noreferrer"
        target="_blank"
      >
        <span className="home-board-nav-academy-icon" aria-hidden="true">
          <SideNavIconAcademy />
        </span>
        <span className="home-board-nav-academy-text">
          <strong>{t.sideAcademyTitle}</strong>
          <span>{t.sideAcademyBody}</span>
          <span className="home-board-nav-academy-cta">{t.sideAcademyCta}</span>
        </span>
      </a>
    </aside>
  );
}

export function BoardAcademyPromo({ locale }) {
  const t = text(locale);
  return (
    <a
      className="home-board-hero-copy home-board-hero-copy--promo"
      href={ingressUrl(locale)}
      rel="noopener noreferrer"
      target="_blank"
    >
      <p className="home-board-eyebrow">{t.academyPromoEyebrow}</p>
      <p className="home-board-brand">{t.academyPromoTitle}</p>
      <p className="home-board-title">{t.academyPromoBody}</p>
      <p className="home-board-lede home-board-lede--cta">{t.academyPromoCta}</p>
    </a>
  );
}
