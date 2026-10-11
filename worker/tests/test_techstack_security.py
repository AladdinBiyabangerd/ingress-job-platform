"""Cybersecurity stack extract coverage."""

from __future__ import annotations

import unittest

from worker.techstack import extract_stack


class CyberSecurityExtractTest(unittest.TestCase):
    def test_cyber_jd_extracts_security_tools(self):
        title = "Cybersecurity Engineer — AWS"
        text = (
            "Hands-on with AWS. Monitor alerts with SIEM and EDR. Manage WAF. "
            "Coordinate penetration testing and incident response. "
            "Vulnerability management and cloud security."
        )
        stack = extract_stack(text, None, title)
        for name in (
            "AWS",
            "SIEM",
            "EDR",
            "WAF",
            "Incident Response",
            "Penetration Testing",
        ):
            self.assertIn(name, stack, stack)
        self.assertLessEqual(len(stack), 12)


if __name__ == "__main__":
    unittest.main()
