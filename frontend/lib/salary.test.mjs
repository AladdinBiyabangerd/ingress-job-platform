import assert from "node:assert/strict";
import test from "node:test";
import { salaryAmounts, salaryCurrency, salaryJsonLd, salaryPeriod } from "./salary.js";

test("Reed range keeps GBP and the yearly period", () => {
  assert.deepEqual(salaryJsonLd("45,000–55,000 GBP per annum"), {
    "@type": "MonetaryAmount",
    currency: "GBP",
    value: { "@type": "QuantitativeValue", unitText: "YEAR", minValue: 45000, maxValue: 55000 },
  });
});

test("hourly, monthly and symbol forms", () => {
  assert.deepEqual(salaryJsonLd("78 GBP per hour").value, { "@type": "QuantitativeValue", unitText: "HOUR", value: 78 });
  assert.equal(salaryJsonLd("1500-2000 AZN aylıq").currency, "AZN");
  assert.equal(salaryJsonLd("1500-2000 AZN aylıq").value.unitText, "MONTH");
  assert.deepEqual(salaryJsonLd("€60k–€70k a year").value, { "@type": "QuantitativeValue", unitText: "YEAR", minValue: 60000, maxValue: 70000 });
  assert.equal(salaryJsonLd("£500 per day").value.unitText, "DAY");
  assert.equal(salaryJsonLd("US$120,000 / year").currency, "USD");
  assert.equal(salaryJsonLd("1.234,50 EUR monthly").value.value, 1234.5);
});

test("unsure means no salary claim", () => {
  assert.equal(salaryJsonLd(""), undefined);
  assert.equal(salaryJsonLd("1500 AZN"), undefined); // no period
  assert.equal(salaryJsonLd("$120k a year"), undefined); // bare $ is ambiguous
  assert.equal(salaryJsonLd("Competitive salary"), undefined);
  assert.equal(salaryJsonLd("50,000 GBP or 60,000 EUR per year"), undefined); // two currencies
  assert.equal(salaryJsonLd("50,000 GBP per year or 30 GBP per hour"), undefined); // two periods
  assert.equal(salaryJsonLd("1000 / 2000 / 3000 AZN monthly"), undefined); // not a range
});

test("helpers", () => {
  assert.equal(salaryCurrency("1 500 ₼"), "AZN");
  assert.equal(salaryPeriod("per annum"), "YEAR");
  assert.deepEqual(salaryAmounts("1 500 - 2 000"), [1500, 2000]);
});
