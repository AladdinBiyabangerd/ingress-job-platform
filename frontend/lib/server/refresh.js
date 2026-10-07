"use server";

import { apiBase } from "../api";
import { adPayload } from "./ad";
import { sessionAccess } from "./me";

const TIMEOUT_MS = 10_000;
const ID_OK = /^\d+$/;

async function bearer() {
  const access = await sessionAccess();
  if (!access) throw new Error("load");
  return access;
}

async function loadJson(path) {
  const access = await bearer();
  const res = await fetch(`${apiBase()}${path}`, {
    headers: { Authorization: `Bearer ${access}`, Accept: "application/json" },
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!res.ok) throw new Error("load");
  const data = await res.json().catch(() => null);
  if (!data || typeof data !== "object") throw new Error("load");
  return data;
}

function itemsOf(data) {
  if (!Array.isArray(data.items)) throw new Error("load");
  return data.items;
}

async function mutate(path, { method = "POST", body, empty = false } = {}) {
  try {
    const access = await bearer();
    const headers = {
      Authorization: `Bearer ${access}`,
      Accept: "application/json",
    };
    const init = {
      method,
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
    const res = await fetch(`${apiBase()}${path}`, init);
    if (empty && res.status === 204) return { ok: true, status: 204, data: {} };
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data: data && typeof data === "object" ? data : {} };
  } catch {
    return { ok: false, status: 401, data: {} };
  }
}

function numericId(value) {
  return ID_OK.test(String(value)) ? String(value) : "";
}

function localeLang(lang) {
  return lang === "en" || lang === "ru" ? lang : "az";
}

/** Queue jobs + applications after admin mutations. Hits FastAPI, not the BFF. */
export async function refreshAdminQueue() {
  const jobs = await loadJson("/api/v1/admin/jobs");
  let applications = { items: [] };
  try {
    applications = await loadJson("/api/v1/admin/applications");
  } catch {
    applications = { items: [] };
  }
  return {
    jobs: itemsOf(jobs),
    applications: Array.isArray(applications.items) ? applications.items : [],
  };
}

/** Crawled ads after hide/show/edit/merge. Hits FastAPI, not the BFF. */
export async function refreshCrawled() {
  return itemsOf(await loadJson("/api/v1/admin/crawled"));
}

/** PUT AI flags on FastAPI and return the saved payload (no BFF). */
export async function saveAdminAiFlags(flags) {
  const access = await bearer();
  const body = flags && typeof flags === "object" ? flags : {};
  const res = await fetch(`${apiBase()}/api/v1/admin/ai-flags`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${access}`,
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
    body: JSON.stringify({ flags: body }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return { ok: false };
  return {
    ok: true,
    flags: data.flags && typeof data.flags === "object" ? data.flags : {},
    key_configured: Boolean(data.key_configured),
  };
}

/** Owner ads + applications after cabinet create/edit/close. Hits FastAPI, not the BFF. */
export async function refreshCabinet() {
  const jobs = await loadJson("/api/v1/cabinet/jobs");
  let applications = { items: [] };
  try {
    applications = await loadJson("/api/v1/cabinet/applications");
  } catch {
    applications = { items: [] };
  }
  return {
    jobs: itemsOf(jobs),
    applications: Array.isArray(applications.items) ? applications.items : [],
  };
}

/** Candidate applications after withdraw. Hits FastAPI, not the BFF. */
export async function refreshMyApplications() {
  return itemsOf(await loadJson("/api/v1/applications"));
}

/** Notifications after mark-read. Hits FastAPI, not the BFF. */
export async function refreshNotifications() {
  const data = await loadJson("/api/v1/notifications");
  return {
    items: itemsOf(data),
    unread: Number(data.unread) || 0,
  };
}

export async function adminPatchJob(id, payload) {
  const jobId = numericId(id);
  if (!jobId) return { ok: false, status: 404, data: {} };
  return mutate(`/api/v1/admin/jobs/${jobId}`, { method: "PATCH", body: adPayload(payload) });
}

export async function adminRejectJob(id, reason) {
  const jobId = numericId(id);
  if (!jobId) return { ok: false, status: 404, data: {} };
  return mutate(`/api/v1/admin/jobs/${jobId}/reject`, {
    body: { reason: typeof reason === "string" ? reason : "" },
  });
}

export async function adminActJob(id, action) {
  const jobId = numericId(id);
  if (!jobId || (action !== "approve" && action !== "close")) return { ok: false, status: 404, data: {} };
  return mutate(`/api/v1/admin/jobs/${jobId}/${action}`);
}

export async function crawledPatchJob(id, payload) {
  const jobId = numericId(id);
  if (!jobId) return { ok: false, status: 404, data: {} };
  const source = payload && typeof payload === "object" ? payload : {};
  return mutate(`/api/v1/admin/crawled/${jobId}`, {
    method: "PATCH",
    body: {
      title: source.title || "",
      company: source.company || "",
      city: source.city || "",
      remote: Boolean(source.remote),
      text: source.text || "",
      language: source.language || "",
      salary: source.salary || "",
      job_type: source.job_type || "",
    },
  });
}

export async function crawledVisibility(id, action) {
  const jobId = numericId(id);
  if (!jobId || (action !== "hide" && action !== "show")) return { ok: false, status: 404, data: {} };
  return mutate(`/api/v1/admin/crawled/${jobId}/${action}`);
}

export async function crawledMerge(keepId, hideId) {
  const keep = Number(keepId);
  const hide = Number(hideId);
  if (!Number.isInteger(keep) || keep <= 0 || !Number.isInteger(hide) || hide <= 0) {
    return { ok: false, status: 400, data: {} };
  }
  return mutate("/api/v1/admin/crawled/merge", { body: { keep_id: keep, hide_id: hide } });
}

export async function cabinetSaveJob(id, payload) {
  const body = adPayload(payload);
  if (id == null || id === "") return mutate("/api/v1/cabinet/jobs", { body });
  const jobId = numericId(id);
  if (!jobId) return { ok: false, status: 404, data: {} };
  return mutate(`/api/v1/cabinet/jobs/${jobId}`, { method: "PATCH", body });
}

export async function cabinetCloseJob(id) {
  const jobId = numericId(id);
  if (!jobId) return { ok: false, status: 404, data: {} };
  return mutate(`/api/v1/cabinet/jobs/${jobId}/close`);
}

export async function withdrawApplication(id) {
  const appId = numericId(id);
  if (!appId) return { ok: false, status: 404, data: {} };
  return mutate(`/api/v1/applications/${appId}`, { method: "DELETE", empty: true });
}

export async function patchApplicationStatus(mode, id, status, reason) {
  const appId = numericId(id);
  if (!appId) return { ok: false, status: 404, data: {} };
  const path = mode === "staff" ? `/api/v1/admin/applications/${appId}` : `/api/v1/cabinet/applications/${appId}`;
  return mutate(path, {
    method: "PATCH",
    body: {
      status: typeof status === "string" ? status : "",
      reason: typeof reason === "string" ? reason : "",
    },
  });
}

export async function markNotificationRead(id) {
  const noteId = numericId(id);
  if (!noteId) return { ok: false, status: 404, data: {} };
  return mutate(`/api/v1/notifications/${noteId}/read`);
}

export async function markAllNotificationsRead() {
  return mutate("/api/v1/notifications/read");
}

/** Skill-gap for a picked role on /me/skills. Hits FastAPI, not the BFF. */
export async function loadSkillGap(lang, role) {
  const name = typeof role === "string" ? role.trim() : "";
  if (!name) throw new Error("load");
  const qs = new URLSearchParams({ lang: localeLang(lang), role: name });
  return loadJson(`/api/v1/me/skill-gap?${qs}`);
}

export async function saveEmailPrefs(payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  return mutate("/api/v1/email-prefs", {
    method: "PUT",
    body: {
      frequency: source.frequency,
      digest: source.digest,
      high_match: source.high_match,
      language: source.language,
      send_weekday: source.send_weekday,
    },
  });
}

export async function saveCompanyProfile(payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  return mutate("/api/v1/company-profile", {
    body: {
      company_name: source.company_name || "",
      city: source.city || "",
      about: source.about || "",
    },
  });
}

export async function createManualAd(payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  return mutate("/api/v1/admin/jobs", {
    body: {
      ...adPayload(source),
      source_url: typeof source.source_url === "string" ? source.source_url : "",
    },
  });
}

export async function loadCvProfile() {
  return loadJson("/api/v1/profile");
}

export async function loadRoles(lang) {
  return loadJson(`/api/v1/me/roles?lang=${encodeURIComponent(localeLang(lang))}`);
}

export async function saveCvProfile(payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  return mutate("/api/v1/profile", {
    method: "PUT",
    body: {
      confirm: Boolean(source.confirm),
      headline: source.headline,
      seniority: source.seniority,
      total_years: source.total_years,
      profile: source.profile,
    },
  });
}

export async function cancelCvParse() {
  return mutate("/api/v1/profile/cv/cancel");
}

export async function deleteCvProfile() {
  return mutate("/api/v1/profile", { method: "DELETE" });
}

/** Multipart CV upload. Hits FastAPI, not the BFF. */
export async function uploadCvProfile(formData) {
  try {
    const access = await bearer();
    const file = formData instanceof FormData ? formData.get("cv") : null;
    if (!file) return { ok: false, status: 422, data: {} };
    const body = new FormData();
    const name = typeof file.name === "string" && file.name.trim() ? file.name : "cv";
    body.set("cv", file, name);
    const res = await fetch(`${apiBase()}/api/v1/profile/cv`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${access}`,
        Accept: "application/json",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
      body,
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data: data && typeof data === "object" ? data : {} };
  } catch {
    return { ok: false, status: 401, data: {} };
  }
}

/** PUT consents (+ optional visibility). Hits FastAPI, not the BFF. */
export async function saveConsents(lang, payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  const qs = new URLSearchParams({ lang: localeLang(lang) });
  return mutate(`/api/v1/consents?${qs}`, {
    method: "PUT",
    body: {
      matching: Boolean(source.matching),
      emails: Boolean(source.emails),
      recruiter_visibility: Boolean(source.recruiter_visibility),
      visibility: typeof source.visibility === "string" ? source.visibility : undefined,
    },
  });
}

/** Apply to a job (optional multipart FormData). Hits FastAPI, not the BFF. */
export async function applyToJob(jobId, formData) {
  const id = numericId(jobId);
  if (!id) return { ok: false, status: 404, data: {} };
  try {
    const access = await bearer();
    const init = {
      method: "POST",
      headers: {
        Authorization: `Bearer ${access}`,
        Accept: "application/json",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    };
    if (formData instanceof FormData) init.body = formData;
    const res = await fetch(`${apiBase()}/api/v1/jobs/${id}/apply`, init);
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data: data && typeof data === "object" ? data : {} };
  } catch {
    return { ok: false, status: 401, data: {} };
  }
}

/** Download personal data zip as base64. Hits FastAPI, not the BFF. */
export async function exportMyData() {
  try {
    const access = await bearer();
    const res = await fetch(`${apiBase()}/api/v1/me/export`, {
      headers: {
        Authorization: `Bearer ${access}`,
        Accept: "application/zip",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
    });
    if (!res.ok) return { ok: false, status: res.status };
    const buffer = Buffer.from(await res.arrayBuffer());
    return {
      ok: true,
      status: 200,
      base64: buffer.toString("base64"),
      contentType: res.headers.get("Content-Type") || "application/zip",
      filename: "ingress-job-export.zip",
    };
  } catch {
    return { ok: false, status: 401 };
  }
}
