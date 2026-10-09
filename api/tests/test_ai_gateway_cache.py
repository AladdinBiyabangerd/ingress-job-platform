"""ai_gateway cache must persist when callers close without commit."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai_gateway import complete_json, ensure_ai_tables


class AiGatewayCachePersistTests(unittest.TestCase):
    def test_cache_survives_reconnect_without_caller_commit(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"fit_summary": {"type": "string"}},
            "required": ["fit_summary"],
        }
        fake = {
            "data": {"fit_summary": "Cached role coach advice for this skill set."},
            "usage": {"prompt_tokens": 8, "completion_tokens": 12},
        }
        env = {
            "OPENAI_API_KEY": "sk-test",
            "AI_GATEWAY_ENABLED": "1",
            "AI_GATEWAY_DAILY_CALL_LIMIT": "100",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jobs.sqlite"
            conn1 = sqlite3.connect(path)
            try:
                ensure_ai_tables(conn1)
                with patch.dict(os.environ, env, clear=False):
                    with patch("app.ai_gateway.gateway._call_chat_json", return_value=fake):
                        first = complete_json(
                            purpose="role_coach",
                            prompt_version="role-coach-v1",
                            system="sys",
                            user="Role: Backend\nHaveSkills: [{\"name\":\"Java\"}]",
                            schema=schema,
                            schema_name="role_coach",
                            conn=conn1,
                        )
                conn1.close()
            finally:
                try:
                    conn1.close()
                except Exception:
                    pass

            self.assertTrue(first.ok)
            self.assertFalse(first.cached)

            conn2 = sqlite3.connect(path)
            try:
                with patch.dict(os.environ, env, clear=False):
                    with patch("app.ai_gateway.gateway._call_chat_json") as api:
                        second = complete_json(
                            purpose="role_coach",
                            prompt_version="role-coach-v1",
                            system="sys",
                            user="Role: Backend\nHaveSkills: [{\"name\":\"Java\"}]",
                            schema=schema,
                            schema_name="role_coach",
                            conn=conn2,
                        )
                    api.assert_not_called()
            finally:
                conn2.close()

            self.assertTrue(second.ok)
            self.assertTrue(second.cached)
            self.assertIn("Cached role coach", second.data["fit_summary"])


if __name__ == "__main__":
    unittest.main()
