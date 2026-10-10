// LinkedIn DOM oxuyucu. Elanlar arası keçmir, Apply basmır.
// Yalnız təsvir kəsilməsin deyə "Show more / Daha fazla" düyməsini bir dəfə aça bilər.
(() => {
  let recording = false;
  let timer = null;
  const sent = new Map();
  const expanded = new Set();
  console.info("[Ingress Job] content script aktiv", location.href, "IJExtract=", typeof IJExtract);
  chrome.runtime.sendMessage({ type: "content_hello", href: location.href }).catch(() => {});

  function tryExpandDescription(jobId) {
    if (!jobId || expanded.has(jobId) || !IJExtract.findShowMore) return false;
    const btn = IJExtract.findShowMore(document);
    if (!btn) return false;
    expanded.add(jobId);
    try {
      btn.click();
      console.info("[Ingress Job] Show more açıldı", jobId);
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
      const opened = tryExpandDescription(id);
      const job = IJExtract.extract(document, location.href);
      if (!job) {
        console.warn("[Ingress Job] extract null", { href: location.href, id });
        if (opened) schedule();
        return;
      }
      const sig = [job.title, job.company, job.description.length, job.apply_url, job.location].join("|");
      if (sent.get(job.linkedin_id) !== sig) {
        sent.set(job.linkedin_id, sig);
        chrome.runtime.sendMessage({ type: "capture", job }).then((r) => {
          if (r && r.ok) console.info("[Ingress Job] tutuldu:", job.title, job.linkedin_id, "desc", job.description.length);
          else console.warn("[Ingress Job] capture rədd:", r);
        }).catch((e) => {
          console.error("[Ingress Job] sendMessage:", e.message || e, "— LinkedIn tabını yeniləyin (extension reload sonrası).");
        });
      }
      // Açandan sonra DOM yenilənəndə daha uzun təsviri yenidən tut (background merge uzunu saxlayır).
      if (opened) schedule();
    } catch (e) {
      console.error("[Ingress Job] extract exception:", e);
    }
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(run, 1200);
  }

  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", schedule);

  chrome.storage.local.get({ recording: false }).then((s) => {
    recording = !!s.recording;
    console.info("[Ingress Job] recording=", recording);
    if (recording) schedule();
  });
  chrome.storage.onChanged.addListener((ch) => {
    if (ch.recording) {
      recording = !!ch.recording.newValue;
      console.info("[Ingress Job] recording →", recording);
      if (recording) {
        sent.clear();
        expanded.clear();
        schedule();
      }
    }
  });
})();
