import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  clampDays,
  notifKindLabel,
  notifReasonLabel,
  notificationLogQuery,
  statusTone,
  weekdayLabel,
} from "./admin-notification-log.js";
import { copy } from "./copy.js";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");

test("notification log query: trims user, clamps days to 1..90", () => {
  assert.equal(notificationLogQuery({ user: "  a@b.az ", days: 30 }), "user=a%40b.az&days=30");
  assert.equal(notificationLogQuery({ user: "", days: 500 }), "days=90");
  assert.equal(notificationLogQuery({}), "days=30");
  assert.equal(clampDays("x"), 30);
  assert.equal(clampDays(0), 1);
});

test("status tone: sent ok, failed bad, sending wait, rest muted", () => {
  assert.equal(statusTone("sent"), "ok");
  assert.equal(statusTone("failed"), "bad");
  assert.equal(statusTone("sending"), "wait");
  assert.equal(statusTone("skipped"), "muted");
});

test("kind / reason / weekday labels in az, en, ru", () => {
  for (const locale of ["az", "en", "ru"]) {
    const t = copy[locale];
    assert.ok(t.notifLogTab && t.notifLogTitle && t.notifLogLede, locale);
    assert.equal(typeof t.notifLogDaysOption, "function");
    assert.equal(t.notifLogWeekdays.length, 7);
    assert.ok(t.notifLogKinds.digest && t.notifLogKinds.profile_nudge && t.notifLogKinds.high_match);
    assert.ok(t.notifLogReasons.daily_limit && t.notifLogReasons.send_failed && t.notifLogReasons.empty);
  }
  const az = copy.az;
  assert.equal(notifKindLabel(az, "digest"), "Dayjest");
  assert.equal(notifKindLabel(az, "profile_nudge_email"), "Profil xatırlatması · email");
  assert.equal(notifReasonLabel(copy.en, "send_failed:smtp_error:SMTPException"), "SMTP could not send (smtp_error:SMTPException)");
  assert.equal(notifReasonLabel(copy.en, "daily_limit"), copy.en.notifLogReasons.daily_limit);
  assert.equal(notifReasonLabel(copy.en, "weird_reason"), "weird_reason");
  assert.equal(weekdayLabel(copy.en, 0), "Mon");
});

test("admin has a staff «notifs» tab wired to the notification log component and proxy", () => {
  const admin = read("../components/admin.js");
  assert.match(admin, /"notifs",\n\]\);/);
  assert.match(admin, /selectTab\("notifs"\)/);
  assert.match(admin, /<AdminNotificationLog locale=\{locale\} \/>/);
  const comp = read("../components/admin-notification-log.js");
  assert.match(comp, /\/api\/auth\/admin\/notification-log\?/);
  const route = read("../app/api/auth/admin/notification-log/route.js");
  assert.match(route, /\/api\/v1\/admin\/notification-log\?/);
  assert.match(route, /authorizedApi/);
});
