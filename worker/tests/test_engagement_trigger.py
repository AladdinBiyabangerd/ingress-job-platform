"""Worker engagement trigger helper."""

import json
import unittest
from unittest.mock import MagicMock, patch

from worker.engagement import trigger_engagement_jobs


class EngagementTriggerTests(unittest.TestCase):
    def test_skips_without_token(self):
        with patch.dict("os.environ", {"INTERNAL_JOB_TOKEN": ""}, clear=False):
            result = trigger_engagement_jobs()
        self.assertTrue(result.get("skipped"))

    def test_posts_with_token(self):
        payload = {"match_new": 1, "match_near": 0, "users": 2}
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with (
            patch.dict(
                "os.environ",
                {"INTERNAL_JOB_TOKEN": "secret", "JOB_API_BASE_URL": "http://api.test"},
                clear=False,
            ),
            patch("urllib.request.urlopen", return_value=response) as opener,
        ):
            result = trigger_engagement_jobs()
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("match_new"), 1)
        req = opener.call_args[0][0]
        self.assertEqual(req.full_url, "http://api.test/api/v1/internal/engagement-jobs")
        self.assertEqual(req.get_header("X-internal-token"), "secret")


if __name__ == "__main__":
    unittest.main()
