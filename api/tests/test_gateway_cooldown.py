import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import app.ai_gateway.gateway as gw


def P(name):
    return SimpleNamespace(name=name, model=name + "-m", key="k", base_url="u")


class CooldownTest(unittest.TestCase):
    def setUp(self):
        gw._cooldown_reset()

    def tearDown(self):
        gw._cooldown_reset()

    def _run(self, providers, behaviour):
        calls = []

        def fake_chat(*, provider, **kw):
            calls.append(provider.name)
            r = behaviour.get(provider.name)
            if isinstance(r, BaseException):
                raise r
            return {"ok": True}

        with mock.patch.object(gw, "_chat_providers", return_value=providers), \
                mock.patch.object(gw, "_chat_json", side_effect=fake_chat):
            try:
                out = gw._call_chat_json(system="s", user="u", schema={}, schema_name="x", timeout=1)
            except RuntimeError:
                out = None
        return calls, out

    def test_403_skipped_on_next_call_order_kept(self):
        provs = [P("gemini"), P("groq"), P("openai")]
        beh = {"groq": gw.ProviderHTTPError("HTTP 403", 403)}
        calls, out = self._run(provs, beh)
        self.assertEqual(calls, ["gemini"])  # gemini ok, groq not reached
        beh["gemini"] = gw.ProviderHTTPError("HTTP 401", 401)
        calls, _ = self._run(provs, beh)
        self.assertEqual(calls, ["gemini", "groq", "openai"])
        calls, out = self._run(provs, beh)
        self.assertEqual(calls, ["openai"])
        self.assertEqual(out["provider"], "openai")

    def test_auth_cooldown_is_long_transient_short(self):
        self.assertEqual(gw._cooldown_seconds(gw.ProviderHTTPError("x", 403)), gw.AUTH_COOLDOWN_S)
        self.assertEqual(gw._cooldown_seconds(gw.ProviderHTTPError("x", 429)), gw.TRANSIENT_COOLDOWN_S)
        self.assertEqual(gw._cooldown_seconds(gw.ProviderHTTPError("x", 503, 42.0)), 42.0)
        self.assertEqual(gw._cooldown_seconds(TimeoutError("timed out")), gw.TRANSIENT_COOLDOWN_S)
        self.assertIsNone(gw._cooldown_seconds(gw.ProviderHTTPError("x", 400)))
        self.assertEqual(gw._parse_retry_after("120"), 120.0)
        self.assertEqual(gw._parse_retry_after("999999"), gw.MAX_RETRY_AFTER_S)
        self.assertIsNone(gw._parse_retry_after("garbage"))

    def test_cooldown_expires(self):
        provs = [P("groq"), P("openai")]
        t = [1000.0]
        with mock.patch.object(gw.time, "monotonic", side_effect=lambda: t[0]):
            gw._cooldown_note("chat", "groq", gw.ProviderHTTPError("x", 429, 10.0))
            self.assertEqual([p.name for p in gw._cooldown_filter("chat", provs)], ["openai"])
            t[0] += 11
            self.assertEqual([p.name for p in gw._cooldown_filter("chat", provs)], ["groq", "openai"])

    def test_all_cooling_tries_least_recently_failed(self):
        provs = [P("gemini"), P("groq"), P("openai")]
        t = [1000.0]
        with mock.patch.object(gw.time, "monotonic", side_effect=lambda: t[0]):
            gw._cooldown_note("chat", "groq", gw.ProviderHTTPError("x", 403)); t[0] += 1
            gw._cooldown_note("chat", "openai", gw.ProviderHTTPError("x", 403)); t[0] += 1
            gw._cooldown_note("chat", "gemini", gw.ProviderHTTPError("x", 429)); t[0] += 1
            self.assertEqual([p.name for p in gw._cooldown_filter("chat", provs)], ["groq"])

    def test_chat_and_embed_independent(self):
        gw._cooldown_note("chat", "openai", gw.ProviderHTTPError("x", 403))
        self.assertEqual([p.name for p in gw._cooldown_filter("embed", [P("openai")])], ["openai"])

    def test_logs_once_per_cooldown(self):
        with self.assertLogs(gw.log, level="WARNING") as cm:
            for _ in range(3):
                gw._cooldown_note("chat", "groq", gw.ProviderHTTPError("x", 403))
        self.assertEqual(sum("cooling down" in m for m in cm.output), 1)

    def test_thread_safe(self):
        def work():
            for _ in range(200):
                gw._cooldown_note("chat", "groq", gw.ProviderHTTPError("x", 429))
                gw._cooldown_filter("chat", [P("groq"), P("openai")])
                gw._cooldown_clear("chat", "groq")
        ts = [threading.Thread(target=work) for _ in range(8)]
        [t.start() for t in ts]; [t.join() for t in ts]


if __name__ == "__main__":
    unittest.main()
