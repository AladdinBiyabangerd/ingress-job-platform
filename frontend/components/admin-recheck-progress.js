"use client";

/**
 * Progress strip for async staff AI jobs (market-fit recheck, job tidy).
 * Stop only halts remaining work — already-written results stay.
 */
export function AdminRecheckProgress({
  t,
  progress,
  onStop,
  stopping = false,
  formatProgress,
}) {
  if (!progress) return null;
  const total = Number(progress.total) || 0;
  const done = Number(progress.done) || 0;
  const remaining =
    progress.remaining != null && progress.remaining !== ""
      ? Number(progress.remaining) || 0
      : Math.max(0, total - done);
  const pct = total ? Math.min(100, Math.round((100 * done) / total)) : 0;
  const label =
    typeof formatProgress === "function"
      ? formatProgress(total, done, remaining)
      : t.adminRecheckProgress(total, done, remaining);

  return (
    <div className="admin-mod-progress" role="status" aria-live="polite">
      <div className="admin-mod-progress-row">
        <div className="admin-mod-progress-label">{label}</div>
        {typeof onStop === "function" ? (
          <button
            type="button"
            className="btn small admin-mod-progress-stop"
            disabled={stopping}
            onClick={onStop}
          >
            {stopping ? t.adminRecheckStopping : t.adminRecheckStop}
          </button>
        ) : null}
      </div>
      <div className="admin-mod-progress-track">
        <div className="admin-mod-progress-bar" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
