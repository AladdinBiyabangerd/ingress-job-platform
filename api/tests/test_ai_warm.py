"""Background AI warm: skill-gap sibling locales."""

from __future__ import annotations

import sys
import time
import types
import unittest
from unittest.mock import Mock, patch

from app import ai_warm


class SkillGapSiblingWarmTests(unittest.TestCase):
    def setUp(self):
        with ai_warm._lock:
            ai_warm._inflight.clear()
            ai_warm._last_fail.clear()
            ai_warm._sibling_scheduled.clear()

    def test_schedules_other_locales_once(self):
        with patch.object(ai_warm, "schedule_skill_gap_ai_warm", return_value=True) as warm:
            ok = ai_warm.schedule_skill_gap_sibling_langs(
                user_id="u1",
                role="Java Developer",
                lang="az",
                top=10,
            )
        self.assertTrue(ok)
        langs = sorted(c.kwargs["lang"] for c in warm.call_args_list)
        self.assertEqual(langs, ["en", "ru"])
        for call in warm.call_args_list:
            self.assertFalse(call.kwargs["warm_siblings"])

        with patch.object(ai_warm, "schedule_skill_gap_ai_warm", return_value=True) as warm2:
            again = ai_warm.schedule_skill_gap_sibling_langs(
                user_id="u1",
                role="Java Developer",
                lang="az",
                top=10,
            )
        self.assertFalse(again)
        warm2.assert_not_called()

    def test_warm_success_triggers_siblings(self):
        conn = Mock()

        class _Lock:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        cabinet = types.ModuleType("app.cabinet_store")
        cabinet._LOCK = _Lock()
        cabinet._connect = lambda: conn
        skill_gap = types.ModuleType("app.skill_gap")
        skill_gap.skill_gap_payload = lambda *a, **k: {"ai_coach": True}

        with patch.dict(sys.modules, {"app.cabinet_store": cabinet, "app.skill_gap": skill_gap}):
            with patch.object(ai_warm, "_track", return_value=True):
                with patch.object(ai_warm, "_done"):
                    with patch.object(ai_warm, "recent_fail_code", return_value=None):
                        with patch.object(
                            ai_warm, "schedule_skill_gap_sibling_langs"
                        ) as siblings:
                            with patch("threading.Thread") as thread_cls:
                                started = []

                                class FakeThread:
                                    def __init__(self, target=None, **kwargs):
                                        self._target = target

                                    def start(self):
                                        started.append(1)
                                        if self._target:
                                            self._target()

                                thread_cls.side_effect = FakeThread
                                ok = ai_warm.schedule_skill_gap_ai_warm(
                                    user_id="u1",
                                    role="Java Developer",
                                    lang="en",
                                    top=8,
                                    warm_siblings=True,
                                )
        self.assertTrue(ok)
        self.assertEqual(started, [1])
        siblings.assert_called_once()
        self.assertEqual(siblings.call_args.kwargs["lang"], "en")
        conn.commit.assert_called_once()
        conn.close.assert_called_once()

    def test_sibling_cooldown_expires(self):
        with patch.object(ai_warm, "schedule_skill_gap_ai_warm", return_value=True):
            self.assertTrue(
                ai_warm.schedule_skill_gap_sibling_langs(
                    user_id="u1", role="R", lang="en", top=1
                )
            )
        with ai_warm._lock:
            key = ai_warm._siblings_key(user_id="u1", role="R", top=1)
            ai_warm._sibling_scheduled[key] = time.monotonic() - (
                ai_warm._SIBLING_COOLDOWN_SEC + 1
            )
        with patch.object(ai_warm, "schedule_skill_gap_ai_warm", return_value=True) as warm:
            self.assertTrue(
                ai_warm.schedule_skill_gap_sibling_langs(
                    user_id="u1", role="R", lang="en", top=1
                )
            )
        self.assertEqual(sorted(c.kwargs["lang"] for c in warm.call_args_list), ["az", "ru"])


if __name__ == "__main__":
    unittest.main()
