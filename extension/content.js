// Passiv oxuyucu: yalnız ekranda artıq olan DOM-u oxuyur.
// Heç bir əlavə sorğu göndərmir, səhifələrə avtomatik keçmir, klikləmir.
// Heç bir elanı süzmür: nə görürsə olduğu kimi saxlayır (qaydaları platforma tətbiq edir).
(() => {
  let recording = false;
  let timer = null;
  const sent = new Map();

  function run() {
    if (!recording) return;
    const job = IJExtract.extract(document, location.href);
    if (!job) return;
    const sig = [job.title, job.company, job.description.length, job.apply_url, job.location].join("|");
    if (sent.get(job.linkedin_id) === sig) return;
    sent.set(job.linkedin_id, sig);
    chrome.runtime.sendMessage({ type: "capture", job }).catch(() => {});
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(run, 1200);
  }

  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", schedule);

  chrome.storage.local.get({ recording: false }).then((s) => {
    recording = !!s.recording;
    if (recording) schedule();
  });
  chrome.storage.onChanged.addListener((ch) => {
    if (ch.recording) {
      recording = !!ch.recording.newValue;
      if (recording) {
        sent.clear();
        schedule();
      }
    }
  });
})();
