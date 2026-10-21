"""Every AI flow is on by default when a key exists; env 0 or a staff row turns it off."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai_flags import FEATURE_ENV, FEATURES, feature_on, invalidate_flag_cache, set_flags


class FlagDefaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.tmp.name) / "f.sqlite")
        invalidate_flag_cache()
        base = {k: v for k, v in os.environ.items() if not k.endswith("_ENABLED")}
        base["OPENAI_API_KEY"] = "sk-test"
        self.env = patch.dict(os.environ, base, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        invalidate_flag_cache()
        self.conn.close()
        self.tmp.cleanup()

    def test_all_on_with_key(self):
        for name in FEATURES:
            self.assertTrue(feature_on(name, self.conn), name)

    def test_env_zero_turns_off(self):
        for name, env_name in FEATURE_ENV.items():
            with patch.dict(os.environ, {env_name: "0"}, clear=False):
                self.assertFalse(feature_on(name, self.conn), name)

    def test_job_tidy_env_name(self):
        self.assertEqual(FEATURE_ENV["job_tidy"], "AI_JOB_TIDY_ENABLED")

    def test_staff_row_turns_off(self):
        set_flags(self.conn, {"market_fit": False}, updated_by="test")
        self.assertFalse(feature_on("market_fit", self.conn))


if __name__ == "__main__":
    unittest.main()
