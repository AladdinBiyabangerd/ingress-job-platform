"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import styles from "./ai-fit-popover.module.css";

const APPROVE = 85;
const MANUAL = 60;
const GAP = 6;
const MARGIN = 12;

function band(score) {
  if (score == null) return "none";
  if (score >= APPROVE) return "approve";
  if (score >= MANUAL) return "manual";
  return "low";
}

function checkedAt(value, locale, tz) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const tag = locale === "en" ? "en-GB" : locale === "ru" ? "ru-RU" : "az-Latn-AZ";
  try {
    return `${d.toLocaleString(tag, {
      timeZone: "Asia/Baku",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    })} (${tz})`;
  } catch {
    return d.toISOString().slice(0, 16).replace("T", " ");
  }
}

function InfoIcon() {
  return (
    <svg className={styles.icon} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M4.5 6.25 8 9.75l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * "AI %" cell: a pill button that opens a small popover with the stored market-fit
 * result (job.market_fit_detail from worker.market_fit.fit_detail). Not a modal:
 * closes on outside click / Esc / scroll-out, keeps focus order, bottom sheet on phones.
 */
export function AiFitCell({ value, detail, reason, copy, locale }) {
  const t = copy;
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState(null);
  const triggerRef = useRef(null);
  const popRef = useRef(null);
  const id = useId();
  const titleId = `${id}-title`;
  const score = value == null || value === "" ? null : Number(value);
  const tone = band(Number.isFinite(score) ? score : null);

  const place = useCallback(() => {
    const trigger = triggerRef.current;
    const pop = popRef.current;
    if (!trigger || !pop) return;
    const r = trigger.getBoundingClientRect();
    const w = pop.offsetWidth;
    const h = pop.offsetHeight;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let left = Math.min(Math.max(MARGIN, r.right - w), vw - w - MARGIN);
    let top = r.bottom + GAP;
    if (top + h > vh - MARGIN && r.top - GAP - h >= MARGIN) top = r.top - GAP - h;
    top = Math.max(MARGIN, Math.min(top, vh - h - MARGIN));
    left = Math.max(MARGIN, left);
    setPos({ top, left });
  }, []);

  const close = useCallback((refocus = true) => {
    setOpen(false);
    setPos(null);
    if (refocus) triggerRef.current?.focus();
  }, []);

  useLayoutEffect(() => {
    if (open) place();
  }, [open, place]);

  useEffect(() => {
    if (!open) return undefined;
    popRef.current?.focus({ preventScroll: true });
    function onDown(event) {
      const target = event.target;
      if (popRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      close(false);
    }
    function onKey(event) {
      if (event.key === "Escape") {
        event.stopPropagation();
        close(true);
      }
    }
    function onMove() {
      const r = triggerRef.current?.getBoundingClientRect();
      if (!r || r.bottom < 0 || r.top > window.innerHeight) {
        close(false);
        return;
      }
      place();
    }
    document.addEventListener("pointerdown", onDown, true);
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("resize", onMove);
    window.addEventListener("scroll", onMove, true);
    return () => {
      document.removeEventListener("pointerdown", onDown, true);
      document.removeEventListener("keydown", onKey, true);
      window.removeEventListener("resize", onMove);
      window.removeEventListener("scroll", onMove, true);
    };
  }, [open, close, place]);

  const label = score == null ? "—" : `${score}%`;
  const hasDetail = detail && typeof detail === "object";
  const legacyReason = !hasDetail && reason && String(reason).startsWith("AI: ") ? String(reason) : "";
  const ruleReason = !hasDetail && reason && !legacyReason ? String(reason) : "";
  const capped = hasDetail && detail.cap != null && detail.ai_score != null && Number(detail.cap) < Number(detail.ai_score);

  return (
    <span className={styles.wrap}>
      <button
        ref={triggerRef}
        type="button"
        className={`${styles.pill} ${styles[tone]}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-label={`${label} — ${t.show}`}
        title={t.show}
        onClick={() => (open ? close(true) : setOpen(true))}
      >
        <span className={styles.value}>{label}</span>
        <InfoIcon />
      </button>
      {open ? (
        <div
          ref={popRef}
          id={id}
          role="dialog"
          aria-modal="false"
          aria-labelledby={titleId}
          tabIndex={-1}
          className={styles.pop}
          style={pos ? { "--pop-top": `${pos.top}px`, "--pop-left": `${pos.left}px` } : { visibility: "hidden" }}
        >
          <div className={styles.head}>
            <div>
              <p id={titleId} className={styles.title}>{t.title}</p>
              {score != null ? (
                <p className={styles.scoreRow}>
                  <span className={`${styles.score} ${styles[`${tone}Text`]}`}>{score}%</span>
                  <span className={`${styles.badge} ${styles[tone]}`}>
                    {tone === "approve" ? t.bandApprove : tone === "manual" ? t.bandManual : t.bandLow}
                  </span>
                </p>
              ) : null}
            </div>
            <button type="button" className={styles.close} onClick={() => close(true)} aria-label={t.close} title={t.close}>
              <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          <div className={styles.body}>
            {hasDetail ? (
              <>
                <dl className={styles.facts}>
                  <div>
                    <dt>{t.rule}</dt>
                    <dd>{(t.routes && t.routes[detail.route]) || detail.route || "—"}</dd>
                  </div>
                  {capped ? (
                    <div>
                      <dt>{t.cap}</dt>
                      <dd>
                        {t.capLine(detail.ai_score, detail.cap)}
                        {detail.eligibility ? <span className={styles.subtle}>{detail.eligibility}</span> : null}
                      </dd>
                    </div>
                  ) : null}
                </dl>
                {detail.hard_reject ? <p className={styles.warn}>{t.hardReject}</p> : null}
                {detail.conflict ? <p className={styles.warn}>{t.conflict}</p> : null}

                {!detail.hard_reject ? (
                  <section className={styles.section}>
                    <h3 className={styles.h}>{t.flags}</h3>
                    {detail.flags && detail.flags.length ? (
                      <ul className={styles.flags}>
                        {detail.flags.map((f) => (
                          <li key={f.name} className={styles.flag}>
                            <span className={styles.flagLabel}>{f.label || f.name}</span>
                            <code className={styles.flagKey}>{f.name}</code>
                            {(f.quotes || []).map((q, i) => (
                              <q key={i} className={styles.quote}>{q}</q>
                            ))}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className={styles.subtle}>{t.noFlags}</p>
                    )}
                  </section>
                ) : detail.eligibility ? (
                  <p className={styles.text}>{detail.eligibility}</p>
                ) : null}

                {detail.notes && detail.notes.length ? (
                  <section className={styles.section}>
                    <h3 className={styles.h}>{t.notes}</h3>
                    <ul className={styles.notes}>
                      {detail.notes.map((n, i) => (
                        <li key={i}>{n}</li>
                      ))}
                    </ul>
                  </section>
                ) : null}

                {detail.reason_az ? (
                  <section className={styles.section}>
                    <h3 className={styles.h}>{t.reason}</h3>
                    <p className={styles.text}>{detail.reason_az}</p>
                  </section>
                ) : null}
              </>
            ) : legacyReason ? (
              <>
                <p className={styles.subtle}>{t.legacy}</p>
                <p className={styles.text}>{legacyReason}</p>
              </>
            ) : (
              <>
                <p className={styles.text}>{t.none}</p>
                <p className={styles.subtle}>{t.noneHint}</p>
                {ruleReason ? <p className={styles.text}>{ruleReason}</p> : null}
              </>
            )}
          </div>

          {hasDetail ? (
            <p className={styles.meta}>
              <span>
                {t.prompt}: <code>{detail.prompt_version || "—"}</code>
              </span>
              {detail.checked_at ? (
                <span>
                  {t.checked}: {checkedAt(detail.checked_at, locale, t.tz)}
                </span>
              ) : null}
            </p>
          ) : null}
        </div>
      ) : null}
    </span>
  );
}
