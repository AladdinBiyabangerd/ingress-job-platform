"""job_categories: public list, staff CRUD, recategorise only touches category."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import job_categories
from app.auth_oidc import VerifiedAccess
from app.cabinet_store import _connect, ensure_schema
from app.main import app

H = {"Authorization": "Bearer test"}


def user(scopes: str) -> VerifiedAccess:
    return VerifiedAccess(subject="staff-1", scopes=frozenset(scopes.split()))


class JobCategoriesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        job_categories.invalidate()
        self.client = TestClient(app)
        conn = _connect()
        conn.execute(
            "INSERT INTO jobs (title, company, city, text, status, created_at, norm_key, category,"
            " tech_stack, updated_at) VALUES ('Senior Python Developer', 'A', '', 'x', 'published',"
            " '2026-10-01T00:00:00+04:00', 'k1', 'Backend', '[]', 'U0')"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.path_patch.stop()
        job_categories.invalidate()
        job_categories.wcat.set_rules(None)
        self.tmp.cleanup()

    def staff(self):
        return patch("app.account.verify_access_token", return_value=user("job:staff"))

    def test_public_list(self):
        res = self.client.get("/api/v1/categories")
        self.assertEqual(res.status_code, 200, res.text)
        items = res.json()["items"]
        self.assertEqual(items[0]["name"], "Backend")
        self.assertEqual(items[0]["total"], 1)
        self.assertEqual(items[0]["labels"]["az"], "Backend")

    def test_staff_only(self):
        with patch("app.account.verify_access_token", return_value=user("job:candidate")):
            self.assertEqual(self.client.get("/api/v1/admin/categories", headers=H).status_code, 403)

    def test_crud_and_recategorise(self):
        with self.staff():
            res = self.client.post("/api/v1/admin/categories", headers=H, json={
                "slug": "Python Land", "name_az": "Python", "name_en": "Python", "name_ru": "Python",
                "title_pattern": "python", "priority": 1, "sort_order": 5})
            self.assertEqual(res.status_code, 200, res.text)
            bad = self.client.patch("/api/v1/admin/categories/Backend", headers=H, json={"title_pattern": "("})
            self.assertEqual(bad.status_code, 422)
            res = self.client.post("/api/v1/admin/categories/recategorise", headers=H)
            self.assertEqual(res.json()["changed"], 1, res.text)
            res = self.client.patch("/api/v1/admin/categories/Python%20Land", headers=H, json={"active": False})
            self.assertEqual(res.status_code, 200, res.text)
            res = self.client.patch("/api/v1/admin/categories/DevOps/Cloud", headers=H, json={"name_az": "DevOps"})
            self.assertEqual(res.json()["name_az"], "DevOps")
        conn = _connect()
        row = conn.execute("SELECT category, status, updated_at FROM jobs").fetchone()
        conn.close()
        self.assertEqual(tuple(row), ("Backend", "published", "U0"))


if __name__ == "__main__":
    unittest.main()
