"use client";

import { text } from "../lib/copy";

const FLAGS = [
  ["message", "applyMessage"],
  ["cv", "applyCv"],
  ["phone", "applyPhone"],
  ["email", "applyEmail"],
];

export function ApplyFormFields({ locale, value, onChange }) {
  const t = text(locale);

  function setFlag(key, patch) {
    const next = { ...value[key], ...patch };
    if (!next.enabled) next.required = false;
    onChange({ ...value, [key]: next });
  }

  function setQuestion(index, patch) {
    const questions = value.questions.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item));
    onChange({ ...value, questions });
  }

  return (
    <fieldset className="apply-fields" title={t.formLede}>
      <legend>{t.formTitle}</legend>
      <div className="apply-field-list">
        {FLAGS.map(([key, label]) => {
          const enabled = Boolean(value[key]?.enabled);
          const required = Boolean(value[key]?.required);
          return (
            <div key={key} className={`apply-field-row${enabled ? " is-on" : ""}`}>
              <label className="apply-field-main">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(event) => setFlag(key, { enabled: event.target.checked })}
                />
                <span>{t[label]}</span>
              </label>
              {enabled ? (
                <button
                  type="button"
                  className={`apply-req-chip${required ? " is-on" : ""}`}
                  aria-pressed={required}
                  onClick={() => setFlag(key, { required: !required })}
                >
                  {required ? t.fieldRequired : t.adOptional}
                </button>
              ) : null}
            </div>
          );
        })}
      </div>
      {value.questions.length ? (
        <div className="apply-question-list">
          {value.questions.map((question, index) => (
            <div key={`${question.id || "new"}-${index}`} className="apply-question-row">
              <label className="apply-question-field">
                <span className="apply-question-label">{t.formQuestion}</span>
                <input
                  type="text"
                  value={question.text}
                  maxLength={200}
                  onChange={(event) => setQuestion(index, { text: event.target.value })}
                />
              </label>
              <div className="apply-question-tools">
                <button
                  type="button"
                  className={`apply-req-chip${question.required ? " is-on" : ""}`}
                  aria-pressed={Boolean(question.required)}
                  onClick={() => setQuestion(index, { required: !question.required })}
                >
                  {question.required ? t.fieldRequired : t.adOptional}
                </button>
                <button
                  type="button"
                  className="apply-question-remove"
                  onClick={() => onChange({ ...value, questions: value.questions.filter((_, itemIndex) => itemIndex !== index) })}
                >
                  {t.formRemoveQuestion}
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {value.questions.length < 5 ? (
        <button
          type="button"
          className="apply-add-question"
          onClick={() => onChange({ ...value, questions: [...value.questions, { id: "", text: "", required: false }] })}
        >
          {t.formAddQuestion}
        </button>
      ) : null}
    </fieldset>
  );
}
