import { applyFormPayload } from "../apply-form";

export function adPayload(body) {
  const source = body && typeof body === "object" ? body : {};
  const payload = {
    title: source.title || "",
    company: source.company || "",
    city: source.city || "",
    remote: Boolean(source.remote),
    text: source.text || "",
    language: source.language || "",
    salary: source.salary || "",
    job_type: source.job_type || "",
  };
  if (source.form && typeof source.form === "object") {
    payload.form = applyFormPayload(source.form);
  }
  return payload;
}
