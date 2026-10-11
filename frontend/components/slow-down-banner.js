"use client";

/** Calm, benefit-framed pause notice (never ban/abuse language). */
export default function SlowDownBanner({ t, messageKey = "gentle", onRetry }) {
  const rl = t?.rateLimit || {};
  const text = rl[messageKey] || rl.gentle || "";
  if (!text) return null;
  return (
    <div
      className="slow-down-banner"
      role="status"
      style={{
        margin: "1rem 0",
        padding: "1rem 1.15rem",
        border: "1px solid rgba(26, 26, 26, 0.12)",
        background: "rgba(247, 245, 241, 0.95)",
        borderRadius: 4,
        maxWidth: "36rem",
      }}
    >
      <p style={{ margin: 0, fontSize: "0.95rem", lineHeight: 1.45 }}>{text}</p>
      {typeof onRetry === "function" ? (
        <button
          type="button"
          onClick={onRetry}
          style={{
            marginTop: "0.75rem",
            appearance: "none",
            border: "none",
            background: "transparent",
            padding: 0,
            font: "inherit",
            fontSize: "0.9rem",
            textDecoration: "underline",
            cursor: "pointer",
          }}
        >
          {rl.tryAgain || t.loadRetry || "Try again"}
        </button>
      ) : null}
    </div>
  );
}

/** Map API/BFF slow_down message_key → copy.rateLimit key. */
export function rateLimitMessageKey(payload) {
  const raw = payload?.message_key || "";
  if (raw.startsWith("rateLimit.")) return raw.slice("rateLimit.".length);
  return "gentle";
}

export function isSlowDownPayload(payload) {
  return payload?.error === "slow_down" || Boolean(payload?.message_key?.startsWith?.("rateLimit."));
}
