/**
 * Single-row page chrome: optional back link + title + count + actions.
 * Replaces multi-line breadcrumbs / tall heroes for nested routes.
 */
export function PageChrome({
  backHref,
  backLabel,
  title,
  count,
  actions,
  children,
  className = "",
}) {
  return (
    <header className={`page-chrome ${className}`.trim()}>
      <div className="page-chrome-main">
        {backHref ? (
          <a className="page-chrome-back" href={backHref}>
            <span aria-hidden="true">←</span>
            <span>{backLabel}</span>
          </a>
        ) : null}
        <div className="page-chrome-title-row">
          {title ? <h1 className="page-chrome-title">{title}</h1> : null}
          {count != null && count !== "" ? <span className="page-chrome-count">{count}</span> : null}
        </div>
        {children ? <div className="page-chrome-extra">{children}</div> : null}
      </div>
      {actions ? <div className="page-chrome-actions">{actions}</div> : null}
    </header>
  );
}
