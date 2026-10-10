"""Enable parked product surfaces for the API unit suite."""

import os

os.environ.setdefault("PRODUCT_RECOMMENDATIONS_ENABLED", "1")
os.environ.setdefault("PRODUCT_ROADMAP_ENABLED", "1")
