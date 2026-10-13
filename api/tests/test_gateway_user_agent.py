import json
import unittest
from unittest import mock

from app.ai_gateway.gateway import USER_AGENT, _http_json


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps({"ok": True}).encode()


class UserAgentTest(unittest.TestCase):
    def _capture(self, headers):
        seen = {}

        def fake(req, timeout=None):
            seen["ua"] = req.get_header("User-agent")
            return _Resp()

        with mock.patch("urllib.request.urlopen", side_effect=fake):
            self.assertEqual(_http_json("https://api.groq.com/x", body={}, headers=headers, timeout=1), {"ok": True})
        return seen["ua"]

    def test_default_user_agent_sent(self):
        ua = self._capture({"Authorization": "Bearer x"})
        self.assertEqual(ua, USER_AGENT)
        self.assertNotIn("Python-urllib", ua)

    def test_explicit_user_agent_kept(self):
        self.assertEqual(self._capture({"user-agent": "custom/2"}), "custom/2")


if __name__ == "__main__":
    unittest.main()
