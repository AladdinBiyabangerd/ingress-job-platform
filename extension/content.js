// LinkedIn DOM oxuyucu. Elanlar arası keçmir, Apply basmır.
// Təsvir tam açılsın deyə "… more / Show more" düymələrini açır; açılana qədər capture etmir.
(() => {
  let recording = false;
  let timer = null;
  const sent = new Map();
  const expandCount = new Map(); // linkedin_id -> neçə dəfə expand klikləndi
  const MAX_EXPAND = 6;
  console.info("[Ingress Job] content script aktiv", location.href, "IJExtract=", typeof IJExtract);
  chrome.runtime.sendMessage({ type: "content_hello", href: location.href }).catch(() => {});

  function schedule(ms) {
    clearTimeout(timer);
    timer = setTimeout(run, ms == null ? 1200 : ms);
  }

  /** Expand qalıbsa klikləyir və true qaytarır (capture gözləməlidir). */
  function tryExpandDescription(jobId) {
    if (!jobId || !IJExtract.findShowMore) return false;
    const btn = IJExtract.findShowMore(document);
    if (!btn) return false;
    const n = expandCount.get(jobId) || 0;
    if (n >= MAX_EXPAND) {
      console.warn("[Ingress Job] Show more limit", jobId);
      return false;
    }
    expandCount.set(jobId, n + 1);
    try {
      btn.click();
      console.info("[Ingress Job] Show more açıldı", jobId, n + 1, (btn.innerText || btn.textContent || "").trim());
      return true;
    } catch (e) {
      console.warn("[Ingress Job] Show more click:", e.message || e);
      return false;
    }
  }

  function run() {
    if (!recording) return;
    try {
      if (typeof IJExtract === "undefined" || !IJExtract.extract) {
        console.error("[Ingress Job] extract.js yüklənməyib — extension-i Reload edib LinkedIn səhifəsini yeniləyin.");
        return;
      }
      const id = IJExtract.jobIdFromUrl(location.href);
      // Əvvəlcə bütün "… more" açılsın — kəsilmiş mətni saxlamırıq.
      if (tryExpandDescription(id)) {
        schedule(700);
        return;
      }
      const job = IJExtract.extract(document, location.href);
      if (!job) {
        console.warn("[Ingress Job] extract null", { href: location.href, id });
        return;
      }
      const sig = [job.title, job.company, job.description.length, job.apply_url, job.location].join("|");
      if (sent.get(job.linkedin_id) === sig) return;
      sent.set(job.linkedin_id, sig);
      chrome.runtime.sendMessage({ type: "capture", job }).then((r) => {
        if (r && r.ok) console.info("[Ingress Job] tutuldu:", job.title, job.linkedin_id, "desc", job.description.length);
        else console.warn("[Ingress Job] capture rədd:", r);
      }).catch((e) => {
        console.error("[Ingress Job] sendMessage:", e.message || e, "— LinkedIn tabını yeniləyin (extension reload sonrası).");
      });
    } catch (e) {
      console.error("[Ingress Job] extract exception:", e);
    }
  }

  new MutationObserver(() => schedule(1200)).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", () => schedule(1200));

  chrome.storage.local.get({ recording: false }).then((s) => {
    recording = !!s.recording;
    console.info("[Ingress Job] recording=", recording);
    if (recording) schedule(400);
  });
  chrome.storage.onChanged.addListener((ch) => {
    if (ch.recording) {
      recording = !!ch.recording.newValue;
      console.info("[Ingress Job] recording →", recording);
      if (recording) {
        sent.clear();
        expandCount.clear();
        schedule(400);
      }
    }
  });
})();
