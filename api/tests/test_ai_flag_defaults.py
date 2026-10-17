"""Non-core AI flows are opt-in; core flows follow the gateway."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai_flags import (
    FEATURE_ENV,
    FEATURES,
    OPT_IN_FEATURES,
    feature_on,
    invalidate_flag_cache,
    set_flags,
)

CORE = {"gateway", "cv_fallback", "embeddings", "rerank", "llm_rerank", "match_why", "digest_intro"}
EXPECTED_OPT_IN = {
    "job_tidy",
    "market_fit",
    "engagement_copy",
    "role_coach",
    "learning_roadmap",
    "job_analyze",
    "job_apply_draft",
    "job_tailored_cv",
}


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

    def test_opt_in_set(self):
        self.assertEqual(set(OPT_IN_FEATURES) & set(FEATURES), EXPECTED_OPT_IN & set(FEATURES))

    def test_core_on_opt_in_off_with_key_only(self):
        for name in FEATURES:
            if name in OPT_IN_FEATURES:
                self.assertFalse(feature_on(name, self.conn), name)
            elif name in CORE:
                self.assertTrue(feature_on(name, self.conn), name)

    def test_env_true_enables_opt_in(self):
        for name in sorted(set(OPT_IN_FEATURES) & set(FEATURES)):
            env_name = FEATURE_ENV[name]
            with patch.dict(os.environ, {env_name: "1"}, clear=False):
                self.assertTrue(feature_on(name, self.conn), name)

    def test_job_tidy_env_name(self):
        self.assertEqual(FEATURE_ENV["job_tidy"], "AI_JOB_TIDY_ENABLED")

    def test_staff_row_enables_opt_in(self):
        set_flags(self.conn, {"market_fit": True}, updated_by="test")
        self.assertTrue(feature_on("market_fit", self.conn))

    def test_env_false_still_hard_off(self):
        set_flags(self.conn, {"market_fit": True}, updated_by="test")
        with patch.dict(os.environ, {"AI_MARKET_FIT_ENABLED": "0"}, clear=False):
            self.assertFalse(feature_on("market_fit", self.conn))


if __name__ == "__main__":
    unittest.main()
