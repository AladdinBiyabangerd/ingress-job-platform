// Service worker: yadda saxlama + Stop zamı toplu göndərmə.
// LinkedIn-ə heç bir sorğu göndərilmir; yalnız platformanın API-sinə.
const DEFAULTS = { apiBase: "http://localhost:3010", token: "" };

async function getState() {
  const s = await chrome.storage.local.get({ recording: false, jobs: {}, settings: DEFAULTS, contentSeenAt: 0 });
  return { recording: s.recording, jobs: s.jobs, settings: { ...DEFAULTS, ...s.settings }, contentSeenAt: s.contentSeenAt || 0 };
}

function badge(count, recording) {
  chrome.action.setBadgeBackgroundColor({ color: recording ? "#d93025" : "#5f6368" });
  chrome.action.setBadgeText({ text: recording || count ? String(count) : "" });
}

async function refreshBadge() {
  const { recording, jobs } = await getState();
  badge(Object.keys(jobs).length, recording);
}

function merge(old, next) {
  const out = { ...old };
  for (const [k, v] of Object.entries(next)) {
    if (v !== "" && v !== null && v !== undefined && (!out[k] || String(v).length >= String(out[k]).length)) out[k] = v;
  }
  return out;
}

async function capture(job) {
  const st = await getState();
  if (!st.recording || !job || !job.linkedin_id) return { ok: false };
  const jobs = st.jobs;
  jobs[job.linkedin_id] = merge(jobs[job.linkedin_id] || {}, job);
  await chrome.storage.local.set({ jobs });
  badge(Object.keys(jobs).length, true);
  return { ok: true };
}

async function stopAndSend() {
  const st = await getState();
  await chrome.storage.local.set({ recording: false });
  const list = Object.values(st.jobs);
  badge(list.length, false);
  if (!list.length) return { ok: true, empty: true, created: 0, duplicates: 0, errors: 0 };
  const base = st.settings.apiBase.replace(/\/+$/, "");
  if (!st.settings.token) return { ok: false, error: "Token yazılmayıb (Ayarlar)." };
  try {
    const res = await fetch(base + "/api/v1/import/linkedin-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Import-Token": st.settings.token },
      body: JSON.stringify({ jobs: list.slice(0, 200) })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}: ${data.detail || ""}` };
    // Uğurlu göndərişdən sonra siyahını təmizlə (200-dən çoxu qalıbsa saxla).
    const rest = {};
    list.slice(200).forEach((j) => (rest[j.linkedin_id] = j));
    await chrome.storage.local.set({ jobs: rest, lastResult: { ...data, at: Date.now() } });
    badge(Object.keys(rest).length, false);
    return { ok: true, ...data };
  } catch (e) {
    return { ok: false, error: "Əlaqə xətası: " + e.message };
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  (async () => {
    if (msg.type === "content_hello") {
      await chrome.storage.local.set({ contentSeenAt: Date.now(), contentHref: msg.href || "" });
      return reply({ ok: true });
    }
    if (msg.type === "capture") return reply(await capture(msg.job));
    if (msg.type === "start") {
      await chrome.storage.local.set({ recording: true });
      await refreshBadge();
      return reply({ ok: true });
    }
    if (msg.type === "stop") return reply(await stopAndSend());
    if (msg.type === "clear") {
      await chrome.storage.local.set({ jobs: {} });
      await refreshBadge();
      return reply({ ok: true });
    }
    if (msg.type === "remove") {
      const { jobs } = await getState();
      delete jobs[msg.id];
      await chrome.storage.local.set({ jobs });
      await refreshBadge();
      return reply({ ok: true });
    }
    reply({ ok: false });
  })();
  return true;
});

chrome.runtime.onStartup.addListener(refreshBadge);
chrome.runtime.onInstalled.addListener(refreshBadge);
