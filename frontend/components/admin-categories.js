"use client";

import { useEffect, useState } from "react";

const BASE = "/api/auth/admin/categories";

function splitList(value) {
  return String(value || "")
    .split(/[\n,]/)
    .map((x) => x.trim())
    .filter(Boolean);
}

async function call(url, method = "GET", body) {
  const res = await fetch(url, {
    method,
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
  return data;
}

function toForm(item) {
  return {
    name_az: item.name_az || "",
    name_en: item.name_en || "",
    name_ru: item.name_ru || "",
    priority: item.priority ?? 500,
    stack_rank: item.stack_rank ?? 500,
    title_pattern: item.title_pattern || "",
    aliases: (item.aliases || []).join(", "),
    stack_names: (item.stack_names || []).join(", "),
  };
}

function fromForm(form) {
  return {
    name_az: form.name_az,
    name_en: form.name_en,
    name_ru: form.name_ru,
    priority: Number(form.priority) || 0,
    stack_rank: Number(form.stack_rank) || 0,
    title_pattern: form.title_pattern,
    aliases: splitList(form.aliases),
    stack_names: splitList(form.stack_names),
  };
}

function Editor({ form, setForm, slugField }) {
  const field = (key, label, props = {}) => (
    <label className="field">
      <span>{label}</span>
      <input value={form[key] ?? ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })} {...props} />
    </label>
  );
  return (
    <div className="admin-cat-editor">
      {slugField}
      {field("name_az", "Ad (az)")}
      {field("name_en", "Name (en)")}
      {field("name_ru", "Название (ru)")}
      {field("priority", "Prioritet (kiçik qalib gəlir)", { type: "number" })}
      {field("stack_rank", "Stack prioriteti", { type: "number" })}
      <label className="field">
        <span>Başlıq regex-i (kiçik hərflə, | ilə ayır)</span>
        <textarea rows={3} value={form.title_pattern} onChange={(e) => setForm({ ...form, title_pattern: e.target.value })} />
      </label>
      <label className="field">
        <span>Mənbə kateqoriya adları (vergüllə)</span>
        <input value={form.aliases} onChange={(e) => setForm({ ...form, aliases: e.target.value })} />
      </label>
      <label className="field">
        <span>Texnologiyalar (stack, vergüllə)</span>
        <textarea rows={2} value={form.stack_names} onChange={(e) => setForm({ ...form, stack_names: e.target.value })} />
      </label>
    </div>
  );
}

export function AdminCategories() {
  const [items, setItems] = useState(null);
  const [editing, setEditing] = useState("");
  const [form, setForm] = useState(null);
  const [creating, setCreating] = useState(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const data = await call(BASE);
    setItems(Array.isArray(data.items) ? data.items : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  async function run(action, ok) {
    setBusy(true);
    setError("");
    setNote("");
    try {
      await action();
      await load();
      if (ok) setNote(ok);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const patch = (slug, body) => call(`${BASE}/item?slug=${encodeURIComponent(slug)}`, "PATCH", body);

  function move(index, delta) {
    const next = [...items];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    run(() => call(`${BASE}/order`, "PUT", { slugs: next.map((x) => x.slug) }));
  }

  if (items === null) return <p className="note">{error || "Yüklənir…"}</p>;

  return (
    <section className="h2-panel admin-categories">
      <div className="admin-mod-bulk">
        <button type="button" className="btn small primary" disabled={busy}
          onClick={() => setCreating({ slug: "", ...toForm({}) })}>
          Yeni kateqoriya
        </button>
        <button type="button" className="btn small" disabled={busy}
          onClick={() => run(async () => {
            const r = await call(`${BASE}/recategorise`, "POST");
            setNote(`Yoxlandı: ${r.scanned}, dəyişdi: ${r.changed}`);
          })}>
          Bütün elanları yenidən kateqoriyala
        </button>
      </div>
      <p className="note">
        Dəyişikliklər yeni crawl edilən elanlara dərhal (worker-in növbəti dövrəsində) tətbiq olunur. Mövcud elanlar üçün
        &quot;yenidən kateqoriyala&quot; düyməsini bas: yalnız kateqoriya dəyişir, status və tarix yox. Söndürülən kateqoriyanın
        elanları &quot;Other tech&quot;-ə (və ya uyğun digər kateqoriyaya) keçir.
      </p>
      {error ? <p className="note">{error}</p> : null}
      {note ? <p className="note">{note}</p> : null}
      {creating ? (
        <div className="h2-panel">
          <Editor
            form={creating}
            setForm={setCreating}
            slugField={
              <label className="field">
                <span>Açar (slug, sonra dəyişmir)</span>
                <input value={creating.slug} onChange={(e) => setCreating({ ...creating, slug: e.target.value })} />
              </label>
            }
          />
          <button type="button" className="btn small primary" disabled={busy}
            onClick={() => run(async () => {
              await call(BASE, "POST", { slug: creating.slug.trim(), ...fromForm(creating), sort_order: (items.length + 1) * 10 });
              setCreating(null);
            }, "Yaradıldı")}>
            Yarat
          </button>{" "}
          <button type="button" className="btn small" onClick={() => setCreating(null)}>Ləğv et</button>
        </div>
      ) : null}
      <div className="admin-mod-table-wrap">
        <table className="admin-mod-table">
          <thead>
            <tr>
              <th scope="col">Sıra</th>
              <th scope="col">Açar</th>
              <th scope="col">Ad (az / en / ru)</th>
              <th scope="col">Elan</th>
              <th scope="col">Status</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {items.map((item, index) => (
              <tr key={item.slug}>
                <td>
                  <button type="button" className="btn small" disabled={busy || index === 0} onClick={() => move(index, -1)}>↑</button>
                  <button type="button" className="btn small" disabled={busy || index === items.length - 1} onClick={() => move(index, 1)}>↓</button>
                </td>
                <td><code>{item.slug}</code></td>
                <td>
                  {editing === item.slug && form ? (
                    <>
                      <Editor form={form} setForm={setForm} />
                      <button type="button" className="btn small primary" disabled={busy}
                        onClick={() => run(async () => {
                          await patch(item.slug, fromForm(form));
                          setEditing("");
                        }, "Yadda saxlandı")}>
                        Yadda saxla
                      </button>{" "}
                      <button type="button" className="btn small" onClick={() => setEditing("")}>Ləğv et</button>
                    </>
                  ) : (
                    `${item.name_az} / ${item.name_en} / ${item.name_ru}`
                  )}
                </td>
                <td>{item.total}</td>
                <td>{item.active ? "Aktiv" : "Söndürülüb"}</td>
                <td>
                  <button type="button" className="btn small" disabled={busy}
                    onClick={() => { setEditing(item.slug); setForm(toForm(item)); }}>
                    Redaktə
                  </button>{" "}
                  {item.slug !== "Other tech" ? (
                    <button type="button" className="btn small" disabled={busy}
                      onClick={() => run(() => patch(item.slug, { active: !item.active }))}>
                      {item.active ? "Söndür" : "Aktiv et"}
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
