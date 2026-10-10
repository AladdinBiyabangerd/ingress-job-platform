const $ = (id) => document.getElementById(id);
const send = (m) => chrome.runtime.sendMessage(m);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function render() {
  const { recording = false, jobs = {}, lastResult } = await chrome.storage.local.get(["recording", "jobs", "lastResult"]);
  const list = Object.values(jobs);
  $("state").textContent = recording ? "qeyd gedir" : "dayandı";
  $("state").className = "pill" + (recording ? " on" : "");
  $("toggle").textContent = recording ? "Stop və göndər" : list.length ? "Start (davam et)" : "Start";
  $("toggle").classList.toggle("stop", recording);
  $("count").textContent = "Toplanan elan: " + list.length;
  $("list").innerHTML = list
    .map((j) => `<li><span>${esc(j.title)}<small>${esc(j.company || "—")} · ${esc(j.location || "—")}${j.apply_url ? " · xarici link" : ""}</small></span><button class="x" data-id="${esc(j.linkedin_id)}" title="Sil">✕</button></li>`)
    .join("");
  const box = $("result");
  if (lastResult && !recording && Date.now() - lastResult.at < 600000) {
    box.hidden = false;
    box.className = "result" + (lastResult.errors ? " err" : "");
    box.textContent = `Göndərildi: yaradıldı ${lastResult.created}, təkrar ${lastResult.duplicates}, xəta ${lastResult.errors}`;
  }
}

$("toggle").onclick = async () => {
  const { recording } = await chrome.storage.local.get("recording");
  if (!recording) {
    await chrome.storage.local.remove("lastResult");
    $("result").hidden = true;
    await send({ type: "start" });
  } else {
    $("toggle").disabled = true;
    const r = await send({ type: "stop" });
    $("toggle").disabled = false;
    const box = $("result");
    box.hidden = false;
    if (r.ok && r.empty) { box.className = "result"; box.textContent = "Göndəriləcək elan yoxdur."; }
    else if (r.ok) { box.className = "result" + (r.errors ? " err" : ""); box.textContent = `Göndərildi: yaradıldı ${r.created}, təkrar ${r.duplicates}, xəta ${r.errors}`; }
    else { box.className = "result err"; box.textContent = r.error || "Xəta"; }
  }
  render();
};
$("clear").onclick = async () => { await send({ type: "clear" }); render(); };
$("list").onclick = async (e) => { const id = e.target.dataset?.id; if (id) { await send({ type: "remove", id }); render(); } };
$("opts").onclick = (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); };
chrome.storage.onChanged.addListener(render);
render();
