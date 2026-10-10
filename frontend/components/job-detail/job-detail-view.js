"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchMe } from "../../lib/me-client";
import { useInitialMe } from "../me-seed";
import { JobDetailAnalyzePanel } from "./job-detail-analyze-panel";
import { JobDetailApplyDraftPanel } from "./job-detail-apply-draft-panel";
import { JobDetailApplyForm } from "./job-detail-apply-form";
import { JobDetailCompanySidebar } from "./job-detail-company-sidebar";
import { JobDetailDescription } from "./job-detail-description";
import { JobDetailGuestGate } from "./job-detail-guest-gate";
import { JobDetailHeader } from "./job-detail-header";
import { JobDetailMobileSticky } from "./job-detail-mobile-sticky";
import { JobDetailSkills } from "./job-detail-skills";

export function JobDetailView({ locale, model: baseModel }) {
  const preview = Boolean(baseModel.preview);
  const initialMe = useInitialMe();
  const [me, setMe] = useState(() => {
    if (preview) return { authenticated: baseModel.authState === "signed_in" };
    if (initialMe && typeof initialMe === "object") return initialMe;
    return undefined;
  });
  const [formOpen, setFormOpen] = useState(false);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [applyDraftOpen, setApplyDraftOpen] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");

  useEffect(() => {
    if (preview) {
      setMe({ authenticated: baseModel.authState === "signed_in" });
      return undefined;
    }
    if (initialMe && typeof initialMe === "object") {
      setMe(initialMe);
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch(() => {
        if (!cancelled) setMe({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, [preview, baseModel.authState, initialMe]);

  const model = useMemo(() => {
    if (preview) return baseModel;
    if (me === undefined) return baseModel;
    return {
      ...baseModel,
      authState: me?.authenticated ? "signed_in" : "guest",
    };
  }, [baseModel, preview, me]);

  const showInlineGate = model.authState === "guest";
  const showApplyForm =
    !preview && model.listingType === "company_posted" && model.authState === "signed_in";

  function revealForm() {
    setFormOpen(true);
    if (typeof document !== "undefined") {
      window.requestAnimationFrame(() => {
        document.getElementById("jd-apply-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }

  function revealAnalyze() {
    setAnalyzeOpen(true);
    if (typeof document !== "undefined") {
      window.requestAnimationFrame(() => {
        document.getElementById("jd-analyze-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }

  function revealApplyDraft() {
    setApplyDraftOpen(true);
    if (typeof document !== "undefined") {
      window.requestAnimationFrame(() => {
        document.getElementById("jd-apply-draft-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }

  const onDraftMessage = useCallback(
    (msg) => {
      const text = String(msg || "").trim();
      if (!text) return;
      setDraftMessage(text);
      if (model.listingType === "company_posted") {
        setFormOpen(true);
        if (typeof document !== "undefined") {
          window.requestAnimationFrame(() => {
            document.getElementById("jd-apply-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
          });
        }
      }
    },
    [model.listingType],
  );

  useEffect(() => {
    setFormOpen(false);
    setAnalyzeOpen(false);
    setApplyDraftOpen(false);
    setDraftMessage("");
  }, [model.jobId, model.listingType, model.authState]);

  return (
    <div className={`jd-page${preview ? " jd-page-preview" : ""}`}>
      <div className="jd-container">
        <div className="jd-grid">
          <div className="jd-main">
            <JobDetailHeader
              locale={locale}
              model={model}
              onRevealForm={revealForm}
              onRevealAnalyze={revealAnalyze}
              onRevealApplyDraft={revealApplyDraft}
              formOpen={formOpen}
              analyzeOpen={analyzeOpen}
              applyDraftOpen={applyDraftOpen}
              preview={preview}
            />

            {showInlineGate ? (
              <JobDetailGuestGate locale={locale} returnTo={model.returnTo} className="jd-guest-gate-inline" />
            ) : null}

            <JobDetailSkills locale={locale} skills={model.skills} />
            <JobDetailDescription
              sections={model.sections}
              benefits={model.benefits}
              benefitsTitle={model.benefitsTitle}
            />

            {showApplyForm ? (
              <JobDetailApplyForm
                locale={locale}
                jobId={model.jobId}
                returnTo={model.returnTo}
                form={model.form}
                open={formOpen}
                draftMessage={draftMessage}
              />
            ) : null}
          </div>

          <aside className="jd-aside">
            <JobDetailCompanySidebar
              locale={locale}
              model={model}
              onRevealForm={revealForm}
              formOpen={formOpen}
              preview={preview}
            />

            <JobDetailAnalyzePanel
              locale={locale}
              jobId={model.jobId}
              returnTo={model.returnTo}
              open={analyzeOpen}
              preview={preview}
            />

            <JobDetailApplyDraftPanel
              locale={locale}
              jobId={model.jobId}
              returnTo={model.returnTo}
              listingType={model.listingType}
              open={applyDraftOpen}
              preview={preview}
              onMessage={onDraftMessage}
            />
          </aside>
        </div>
      </div>

      <JobDetailMobileSticky
        locale={locale}
        model={model}
        onRevealForm={revealForm}
        onRevealAnalyze={revealAnalyze}
        onRevealApplyDraft={revealApplyDraft}
        formOpen={formOpen}
        analyzeOpen={analyzeOpen}
        applyDraftOpen={applyDraftOpen}
        preview={preview}
      />
    </div>
  );
}
