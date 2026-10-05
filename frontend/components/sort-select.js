"use client";

/** Sort select that submits its GET form on change. Without JS the form's button does it. */
export function SortSelect({ name, value, options, label, id }) {
  return (
    <select
      id={id}
      name={name}
      defaultValue={value}
      aria-label={label}
      onChange={(event) => event.currentTarget.form?.requestSubmit()}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
