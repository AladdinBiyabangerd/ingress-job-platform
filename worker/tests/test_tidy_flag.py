"""Job tidy respects the staff job_tidy flag."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.ai_flags import set_flags
from worker.db import Store
from worker.tidy import tidy_pending


class TidyFlagTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_flag_off_skips_with_key(self):
        set_flags(self.store.conn, {"job_tidy": False}, updated_by="test")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            with patch("worker.tidy._submit") as submit:
                saved, queued = tidy_pending(self.store.conn)
        submit.assert_not_called()
        self.assertEqual((saved, queued), (0, 0))


if __name__ == "__main__":
    unittest.main()
