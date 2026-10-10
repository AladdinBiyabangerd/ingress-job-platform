const $ = (id) => document.getElementById(id);
const send = (m) => chrome.runtime.sendMessage(m);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let busy = false;

function isExternal(j) {
  return !!j.apply_url && !/(^|\.)linkedin\.com$/.test(new URL(j.apply_url).hostname);
}

function showResult(r) {
  const box = $("result");
  box.hidden = false;
  if (!r.ok) {
    box.className = "result err";
    box.innerHTML = `<h2>Göndərilmədi</h2>${esc(r.error || "Xəta")}`;
    return;
  }
  if (r.empty) {
    box.className = "result info";
    box.innerHTML = "<h2>Göndəriləcək elan yoxdur</h2>Qeyd zamanı elan açılmayıb.";
    return;
  }
  const state = r.errors ? "err" : r.created ? "" : "warn";
  const title = r.errors ? "Göndərildi, xətalarla" : r.created ? "Uğurla göndərildi" : "Yeni elan yaranmadı";
  box.className = "result " + state;
  box.innerHTML =
    `<h2>${title}</h2><div class="stats">` +
    `<div class="stat"><b>${r.created || 0}</b><span>yaradıldı</span></div>` +
    `<div class="stat"><b>${r.duplicates || 0}</b><span>təkrar</span></div>` +
    `<div class="stat"><b>${r.rejected || 0}</b><span>uyğun deyil</span></div>` +
    `<div class="stat"><b>${r.errors || 0}</b><span>xəta</span></div></div>`;
}

async function render() {
  const { recording = false, jobs = {}, lastResult, contentSeenAt = 0 } = await chrome.storage.local.get([
    "recording", "jobs", "lastResult", "contentSeenAt",
  ]);
  const list = Object.values(jobs);
  $("state").textContent = recording ? "qeyd gedir" : "dayandı";
  $("state").className = "pill" + (recording ? " on" : "");
  if (!busy) {
    $("toggle").textContent = recording ? "Stop və göndər" : list.length ? "Start (davam et)" : "Start";
    $("toggle").className = "btn main " + (recording ? "stop" : "primary");
  }
  $("num").textContent = list.length;
  $("count").textContent = "Toplanan elan: " + list.length;
  $("hint").hidden = recording || list.length > 0;
  $("empty").hidden = list.length > 0;
  // Content script son 2 dəqiqədə salam göndərməyibsə LinkedIn tabını yeniləmək lazımdır.
  const scriptOk = contentSeenAt && Date.now() - contentSeenAt < 120000;
  const scriptEl = $("script");
  if (recording && !scriptOk) {
    scriptEl.hidden = false;
    scriptEl.textContent = "LinkedIn tabında script yoxdur — chrome://extensions → Reload, sonra LinkedIn səhifəsini yeniləyin.";
  } else if (scriptOk) {
    scriptEl.hidden = false;
    scriptEl.textContent = "LinkedIn script aktiv.";
  } else {
    scriptEl.hidden = true;
  }
  $("list").innerHTML = list
    .map((j) => {
      const ext = isExternal(j);
      return `<li class="job"><div><div class="t">${esc(j.title)}</div><div class="m">${esc(j.company || "—")} · ${esc(j.location || "—")}</div>` +
        `<span class="badge ${ext ? "ext" : "easy"}">${ext ? "Xarici link" : "Easy Apply"}</span></div>` +
        `<button class="x" data-id="${esc(j.linkedin_id)}" title="Sil" aria-label="Sil">✕</button></li>`;
    })
    .join("");
  if (lastResult && !recording && !busy && Date.now() - lastResult.at < 600000) showResult({ ok: true, ...lastResult });
}

$("toggle").onclick = async () => {
  const { recording } = await chrome.storage.local.get("recording");
  if (!recording) {
    await chrome.storage.local.remove("lastResult");
    $("result").hidden = true;
    await send({ type: "start" });
  } else {
    busy = true;
    $("toggle").disabled = true;
    $("toggle").innerHTML = '<span class="spinner"></span> Göndərilir…';
    const r = await send({ type: "stop" });
    busy = false;
    $("toggle").disabled = false;
    showResult(r);
  }
  render();
};
$("clear").onclick = async () => { await send({ type: "clear" }); $("result").hidden = true; render(); };
$("list").onclick = async (e) => { const id = e.target.dataset?.id; if (id) { await send({ type: "remove", id }); render(); } };
$("opts").onclick = (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); };
chrome.storage.onChanged.addListener(render);
render();
