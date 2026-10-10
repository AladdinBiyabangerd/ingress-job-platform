"""Parked recommendations / roadmap product gates."""

import os
import unittest
from unittest.mock import patch


class ProductFeaturesTests(unittest.TestCase):
    def test_default_off(self):
        with patch.dict(os.environ, {}, clear=True):
            # Re-import helpers under emptied env (module functions read env live).
            from app.product_features import recommendations_enabled, roadmap_enabled

            self.assertFalse(recommendations_enabled())
            self.assertFalse(roadmap_enabled())

    def test_env_on(self):
        with patch.dict(
            os.environ,
            {
                "PRODUCT_RECOMMENDATIONS_ENABLED": "1",
                "PRODUCT_ROADMAP_ENABLED": "true",
            },
            clear=False,
        ):
            from app.product_features import recommendations_enabled, roadmap_enabled

            self.assertTrue(recommendations_enabled())
            self.assertTrue(roadmap_enabled())

    def test_env_hard_off(self):
        with patch.dict(
            os.environ,
            {
                "PRODUCT_RECOMMENDATIONS_ENABLED": "0",
                "PRODUCT_ROADMAP_ENABLED": "off",
            },
            clear=False,
        ):
            from app.product_features import recommendations_enabled, roadmap_enabled

            self.assertFalse(recommendations_enabled())
            self.assertFalse(roadmap_enabled())
