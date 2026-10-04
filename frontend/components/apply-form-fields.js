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
    <fieldset className="apply-fields">
      <legend>{t.formTitle}</legend>
      <p className="hint">{t.formLede}</p>
      {FLAGS.map(([key, label]) => (
        <div key={key} className="choices">
          <label className="inline">
            <input
              type="checkbox"
              checked={Boolean(value[key]?.enabled)}
              onChange={(event) => setFlag(key, { enabled: event.target.checked })}
            />
            <span>{t[label]}</span>
          </label>
          {value[key]?.enabled ? (
            <label className="inline">
              <input
                type="checkbox"
                checked={Boolean(value[key]?.required)}
                onChange={(event) => setFlag(key, { required: event.target.checked })}
              />
              <span>{t.fieldRequired}</span>
            </label>
          ) : null}
        </div>
      ))}
      {value.questions.map((question, index) => (
        <div key={`${question.id || "new"}-${index}`} className="question-line">
          <label>
            {t.formQuestion}
            <input
              type="text"
              value={question.text}
              maxLength={200}
              onChange={(event) => setQuestion(index, { text: event.target.value })}
            />
          </label>
          <div className="choices">
            <label className="inline">
              <input
                type="checkbox"
                checked={Boolean(question.required)}
                onChange={(event) => setQuestion(index, { required: event.target.checked })}
              />
              <span>{t.fieldRequired}</span>
            </label>
            <button
              type="button"
              className="btn red"
              onClick={() => onChange({ ...value, questions: value.questions.filter((_, itemIndex) => itemIndex !== index) })}
            >
              {t.formRemoveQuestion}
            </button>
          </div>
        </div>
      ))}
      {value.questions.length < 5 ? (
        <button
          type="button"
          className="btn red"
          onClick={() => onChange({ ...value, questions: [...value.questions, { id: "", text: "", required: false }] })}
        >
          {t.formAddQuestion}
        </button>
      ) : null}
    </fieldset>
  );
}
