const FLAGS = ["message", "cv", "phone", "email"];

function flag(value, enabled, required) {
  if (!value || typeof value !== "object") return { enabled, required };
  const on = Boolean(value.enabled);
  return { enabled: on, required: on && Boolean(value.required) };
}

export function defaultApplyForm() {
  return {
    message: { enabled: true, required: true },
    cv: { enabled: true, required: false },
    phone: { enabled: false, required: false },
    email: { enabled: false, required: false },
    questions: [],
  };
}

export function applyFormFromJob(job) {
  const form = job && job.form && typeof job.form === "object" ? job.form : null;
  if (!form) return defaultApplyForm();
  return {
    message: flag(form.message, true, true),
    cv: flag(form.cv, true, false),
    phone: flag(form.phone, false, false),
    email: flag(form.email, false, false),
    questions: Array.isArray(form.questions)
      ? form.questions.slice(0, 5).map((item) => ({
          id: typeof item?.id === "string" ? item.id : "",
          text: typeof item?.text === "string" ? item.text : "",
          required: Boolean(item?.required),
        }))
      : [],
  };
}

export function applyFormPayload(form) {
  const source = form || defaultApplyForm();
  return {
    message: flag(source.message, false, false),
    cv: flag(source.cv, false, false),
    phone: flag(source.phone, false, false),
    email: flag(source.email, false, false),
    questions: (source.questions || []).slice(0, 5).map((item) => ({
      id: item.id || "",
      text: item.text || "",
      required: Boolean(item.required),
    })),
  };
}

export function applyFormReady(form) {
  const questions = form?.questions || [];
  const any = FLAGS.some((key) => form?.[key]?.enabled) || questions.some((item) => String(item.text || "").trim());
  const blankQuestion = questions.some((item) => !String(item.text || "").trim());
  return { any, blankQuestion };
}
