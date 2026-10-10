const DEFAULTS = { apiBase: "http://localhost:3010", token: "" };
const $ = (id) => document.getElementById(id);
const say = (text, kind) => { $("msg").textContent = text; $("msg").className = "msg " + (kind || ""); };

chrome.storage.local.get({ settings: DEFAULTS }).then(({ settings }) => {
  const s = { ...DEFAULTS, ...settings };
  $("apiBase").value = s.apiBase;
  $("token").value = s.token;
});

$("peek").onclick = () => {
  const show = $("token").type === "password";
  $("token").type = show ? "text" : "password";
  $("peek").textContent = show ? "Gizlət" : "Göstər";
  $("peek").setAttribute("aria-pressed", String(show));
};

$("form").onsubmit = async (e) => {
  e.preventDefault();
  $("apiBase").classList.remove("bad");
  const apiBase = $("apiBase").value.trim().replace(/\/+$/, "") || DEFAULTS.apiBase;
  const token = $("token").value.trim();
  let msg = "Saxlandı ✓";
  let kind = "ok";
  try {
    const origin = new URL(apiBase).origin + "/*";
    const ok = await chrome.permissions.request({ origins: [origin] });
    if (!ok) { msg = "Saxlandı, amma sayta icazə verilmədi (CORS ilə də işləyə bilər)."; kind = "warn"; }
  } catch (_) {
    $("apiBase").classList.add("bad");
    say("Ünvan yanlışdır.", "err");
    return;
  }
  if (!token) { msg = "Saxlandı, amma token boşdur."; kind = "warn"; }
  await chrome.storage.local.set({ settings: { apiBase, token } });
  say(msg, kind);
};
