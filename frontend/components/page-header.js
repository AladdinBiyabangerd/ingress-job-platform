/**
 * Compact page header shared by the job list and the companies directory:
 * a small title with a count pill, an optional one-line subtitle, and an
 * inline tools slot (sort, window). No hooks, so it renders the same on the
 * server and the client.
 */
export function PageHeader({ title, count, lede, className = "", children }) {
  return (
    <section className={`hero ${className}`.trim()}>
      <div className="hero-head">
        <div className="hero-title-row">
          <h1>{title}</h1>
          {count ? <span className="hero-count">{count}</span> : null}
        </div>
        {lede ? <p className="lede">{lede}</p> : null}
      </div>
      {children ? <div className="hero-tools">{children}</div> : null}
    </section>
  );
}
