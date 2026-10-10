const DEFAULTS = { apiBase: "http://localhost:3010", token: "" };
chrome.storage.local.get({ settings: DEFAULTS }).then(({ settings }) => {
  const s = { ...DEFAULTS, ...settings };
  document.getElementById("apiBase").value = s.apiBase;
  document.getElementById("token").value = s.token;
});
document.getElementById("save").onclick = async () => {
  const apiBase = document.getElementById("apiBase").value.trim().replace(/\/+$/, "") || DEFAULTS.apiBase;
  const token = document.getElementById("token").value.trim();
  let msg = "Saxlandı ✓";
  try {
    const origin = new URL(apiBase).origin + "/*";
    const ok = await chrome.permissions.request({ origins: [origin] });
    if (!ok) msg = "Saxlandı, amma sayta icazə verilmədi (CORS ilə də işləyə bilər).";
  } catch (_) {
    msg = "Ünvan yanlışdır.";
  }
  await chrome.storage.local.set({ settings: { apiBase, token } });
  document.getElementById("msg").textContent = msg;
};
