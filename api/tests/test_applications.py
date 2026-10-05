"""On-site applications stay with the ad. Crawled ads still return the original URL."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.main import app
from app.profiles import save_profile


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.cvs = root / "cvs"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.cv_patch = patch("app.applications.CV_ROOT", self.cvs)
        self.drain_patch = patch("app.applications.schedule_parse_cv_drain")
        self.path_patch.start()
        self.cv_patch.start()
        self.drain_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        save_profile("apply-employer", "Ingress MMC", "Baki", "Aciq vakansiyalar.")

    def tearDown(self):
        self.drain_patch.stop()
        self.cv_patch.stop()
        self.path_patch.stop()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _ad(self, **extra):
        body = {
            "title": "Backend muhendisi",
            "company": "Ingress MMC",
            "city": "Baki",
            "remote": False,
            "text": "Komanda ucun aciq rol.",
            "language": "az",
            "salary": "",
            "job_type": "ofis",
        }
        body.update(extra)
        return body

    def _published_company_ad(self):
        with self._auth("job:employer", "apply-employer"):
            created = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(),
            )
            self.assertEqual(created.status_code, 201, created.text)
            ad_id = created.json()["id"]
        with self._auth("job:staff", "apply-staff"):
            approved = self.client.post(
                f"/api/v1/admin/jobs/{ad_id}/approve",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
        return ad_id

    def test_candidate_applies_onsite_and_cv_is_private(self):
        ad_id = self._published_company_ad()
        public = self.client.get(f"/api/v1/jobs/{ad_id}")
        self.assertEqual(public.json()["form"]["message"], {"enabled": True, "required": True})
        self.assertEqual(public.json()["form"]["cv"], {"enabled": True, "required": False})
        self.assertEqual(public.json()["form"]["questions"], [])
        self.assertNotIn("apply_form", public.json())
        self.assertNotIn("owner_subject", public.json())
        marker = b"%PDF-1.4 private-cv-marker"
        with self._auth("job:employer", "apply-employer"):
            denied = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                json={"message": "Men ishgorenem"},
            )
            self.assertEqual(denied.status_code, 403)
            self.assertNotIn("private-cv-marker", denied.text)

        guest = self.client.post(f"/api/v1/jobs/{ad_id}/apply", json={"message": "Salam"})
        self.assertEqual(guest.status_code, 401)

        with self._auth("job:candidate", "apply-candidate"):
            empty = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(empty.status_code, 422)
            created = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                data={"message": "Bu rol mene uygundur."},
                files={"cv": ("cv.pdf", marker, "application/pdf")},
            )
            self.assertEqual(created.status_code, 200, created.text)
            body = created.json()
            self.assertEqual(body["job_id"], ad_id)
            self.assertTrue(body["has_cv"])
            self.assertEqual(body["cv_name"], "cv.pdf")
            self.assertNotIn("cv_stored", body)
            self.assertNotIn("private-cv-marker", created.text)
            self.assertNotIn("url", body)
            self.assertEqual(body["status"], "submitted")
            self.assertNotIn("reason", body)
            self.assertNotIn("decision_reason", created.text)
            self.assertNotIn("candidate_subject", body)
            with sqlite3.connect(self.db) as conn:
                queued = conn.execute(
                    """
                    SELECT user_id, status, application_id, cv_file_key
                    FROM parse_cv_queue WHERE application_id = ?
                    """,
                    (body["id"],),
                ).fetchone()
                self.assertIsNotNone(queued)
                self.assertEqual(queued[0], "apply-candidate")
                self.assertEqual(queued[1], "pending")
                self.assertTrue(str(queued[3]).endswith(".pdf"))
            again = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                json={"message": "Ikinci"},
            )
            self.assertEqual(again.status_code, 409)
            mine = self.client.get("/api/v1/applications", headers={"Authorization": "Bearer test"})
            self.assertEqual(mine.status_code, 200, mine.text)
            self.assertEqual([item["id"] for item in mine.json()["items"]], [body["id"]])
            downloaded = self.client.get(
                f"/api/v1/applications/{body['id']}/cv",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(downloaded.status_code, 200, downloaded.text)
            self.assertEqual(downloaded.content, marker)

        with self._auth("job:candidate", "other-candidate"):
            hidden = self.client.get("/api/v1/applications", headers={"Authorization": "Bearer test"})
            self.assertEqual(hidden.json()["items"], [])
            blocked = self.client.get(
                f"/api/v1/applications/{body['id']}/cv",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(blocked.status_code, 403)
            self.assertNotIn(b"private-cv-marker", blocked.content)

        with self._auth("job:employer", "apply-stranger"):
            blocked = self.client.get(
                f"/api/v1/applications/{body['id']}/cv",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(blocked.status_code, 403)
            self.assertNotIn(b"private-cv-marker", blocked.content)

        with self._auth("job:employer", "apply-employer"):
            owned = self.client.get(
                "/api/v1/cabinet/applications",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(owned.status_code, 200, owned.text)
            self.assertEqual(owned.json()["items"][0]["message"], "Bu rol mene uygundur.")
            self.assertNotIn("private-cv-marker", owned.text)
            opened = self.client.get(
                f"/api/v1/applications/{body['id']}/cv",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(opened.status_code, 200)
            self.assertEqual(opened.content, marker)

        with self._auth("job:staff", "apply-staff"):
            all_rows = self.client.get(
                "/api/v1/admin/applications",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(all_rows.status_code, 200, all_rows.text)
            self.assertEqual(all_rows.json()["items"][0]["candidate_subject"], "apply-candidate")
            self.assertNotIn("private-cv-marker", all_rows.text)
            opened = self.client.get(
                f"/api/v1/applications/{body['id']}/cv",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(opened.content, marker)

        stored = list(self.cvs.iterdir())
        self.assertEqual(len(stored), 1)
        self.assertTrue(stored[0].name.endswith(".pdf"))
        self.assertNotIn("cv.pdf", stored[0].name)

    def test_crawled_apply_still_returns_the_original_url(self):
        conn = sqlite3.connect(self.db)
        cur = conn.execute(
            """
            INSERT INTO jobs (title, company, city, text, status, created_at, norm_key, owner_subject)
            VALUES ('Kohne', 'Busy', 'Baki', 'Metn', 'published', '2026-10-04T12:00:00+04:00', 'crawl-apply', '')
            """
        )
        job_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO job_sources (job_id, source_name, source_url, external_id, last_seen)
            VALUES (?, 'busy.az', 'https://busy.example/jobs/9', '', '2026-10-04T12:00:00+04:00')
            """,
            (job_id,),
        )
        conn.commit()
        conn.close()
        with self._auth("job:candidate", "apply-candidate"):
            applied = self.client.post(
                f"/api/v1/jobs/{job_id}/apply",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(applied.status_code, 200, applied.text)
            self.assertEqual(applied.json()["url"], "https://busy.example/jobs/9")
        conn = sqlite3.connect(self.db)
        count = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)
        public = self.client.get(f"/api/v1/jobs/{job_id}")
        self.assertFalse(public.json()["onsite"])
        self.assertIsNone(public.json()["form"])
        self.assertNotIn("busy.example", public.text)


    def _form(self, **overrides):
        form = {
            "message": {"enabled": False, "required": False},
            "cv": {"enabled": False, "required": False},
            "phone": {"enabled": False, "required": False},
            "email": {"enabled": False, "required": False},
            "questions": [],
        }
        form.update(overrides)
        return form

    def test_form_status_reason_and_withdraw(self):
        too_many = self._form(questions=[{"text": f"Sual {index}", "required": False} for index in range(6)])
        with self._auth("job:employer", "apply-employer"):
            capped = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(form=too_many),
            )
            self.assertEqual(capped.status_code, 422, capped.text)
            self.assertEqual(capped.json()["detail"], "Ən çox 5 sual ola bilər")
            empty = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(form=self._form()),
            )
            self.assertEqual(empty.status_code, 422, empty.text)
            self.assertEqual(empty.json()["detail"], "Müraciət formasında ən azı bir sahə seçilməlidir")
            blank = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(form=self._form(questions=[{"text": "  ", "required": True}])),
            )
            self.assertEqual(blank.status_code, 422, blank.text)
            self.assertEqual(blank.json()["detail"], "Sual yazılmalıdır")

        chosen = self._form(
            cv={"enabled": True, "required": False},
            phone={"enabled": True, "required": True},
            email={"enabled": True, "required": False},
            questions=[{"text": "Nece eshitdiniz?", "required": True}],
        )
        with self._auth("job:employer", "apply-employer"):
            created = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(form=chosen),
            )
            self.assertEqual(created.status_code, 201, created.text)
            ad_id = created.json()["id"]
            question_id = created.json()["form"]["questions"][0]["id"]
            self.assertRegex(question_id, r"^q[a-f0-9]{8}$")
        with self._auth("job:staff", "apply-staff"):
            approved = self.client.post(
                f"/api/v1/admin/jobs/{ad_id}/approve",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
        public = self.client.get(f"/api/v1/jobs/{ad_id}")
        self.assertEqual(public.json()["form"]["questions"][0]["text"], "Nece eshitdiniz?")
        self.assertNotIn("owner_subject", public.text)

        marker = b"%PDF-1.4 form-cv"
        with self._auth("job:candidate", "apply-candidate"):
            missing = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                json={"answers": [{"id": question_id, "answer": "Dostdan"}]},
            )
            self.assertEqual(missing.status_code, 422, missing.text)
            bad_phone = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                json={"phone": "abc", "answers": [{"id": question_id, "answer": "Dostdan"}]},
            )
            self.assertEqual(bad_phone.status_code, 422, bad_phone.text)
            extra = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                json={
                    "message": "Bu sahe secilmeyib",
                    "phone": "0501112233",
                    "answers": [{"id": question_id, "answer": "Dostdan"}],
                },
            )
            self.assertEqual(extra.status_code, 422, extra.text)
            applied = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                data={
                    "phone": "0501112233",
                    "answers": '[{"id": "%s", "answer": "Dostdan"}]' % question_id,
                },
                files={"cv": ("cv.pdf", marker, "application/pdf")},
            )
            self.assertEqual(applied.status_code, 200, applied.text)
            body = applied.json()
            self.assertEqual(body["status"], "submitted")
            self.assertEqual(body["phone"], "0501112233")
            self.assertEqual(body["email"], "")
            self.assertEqual(body["message"], "")
            self.assertEqual(body["answers"], [{"question": "Nece eshitdiniz?", "answer": "Dostdan"}])
            self.assertNotIn("reason", body)
            self.assertTrue(body["has_cv"])
            again = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                json={"phone": "0501112233", "answers": [{"id": question_id, "answer": "Dostdan"}]},
            )
            self.assertEqual(again.status_code, 409, again.text)

        conn = sqlite3.connect(self.db)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0], 1)
        conn.close()

        with self._auth("job:employer", "apply-employer"):
            quiet = self.client.patch(
                f"/api/v1/cabinet/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
                json={"status": "rejected", "reason": "   "},
            )
            self.assertEqual(quiet.status_code, 200, quiet.text)
            self.assertEqual(quiet.json()["status"], "rejected")
            self.assertNotIn("reason", quiet.json())
        with self._auth("job:candidate", "apply-candidate"):
            mine = self.client.get("/api/v1/applications", headers={"Authorization": "Bearer test"})
            self.assertEqual(mine.json()["items"][0]["status"], "rejected")
            self.assertNotIn("reason", mine.json()["items"][0])
            self.assertNotIn("candidate_subject", mine.json()["items"][0])
        with self._auth("job:employer", "apply-employer"):
            told = self.client.patch(
                f"/api/v1/cabinet/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
                json={"status": "rejected", "reason": "Uyğun deyil"},
            )
            self.assertEqual(told.status_code, 200, told.text)
            self.assertEqual(told.json()["reason"], "Uyğun deyil")
        with self._auth("job:candidate", "apply-candidate"):
            mine = self.client.get("/api/v1/applications", headers={"Authorization": "Bearer test"})
            self.assertEqual(mine.json()["items"][0]["reason"], "Uyğun deyil")
            timeline = mine.json()["items"][0]["timeline"]
            self.assertEqual(timeline[0]["status"], "submitted")
            self.assertTrue(timeline[0].get("at"))
            rejected_steps = [step for step in timeline if step["status"] == "rejected"]
            self.assertTrue(rejected_steps)
            self.assertEqual(rejected_steps[-1]["note"], "Uyğun deyil")
            blocked = self.client.patch(
                f"/api/v1/cabinet/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
                json={"status": "seen"},
            )
            self.assertEqual(blocked.status_code, 403, blocked.text)

        save_profile("apply-stranger", "Basqa MMC", "Baki", "Basqa sirket.")
        with self._auth("job:employer", "apply-stranger"):
            denied = self.client.patch(
                f"/api/v1/cabinet/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
                json={"status": "seen"},
            )
            self.assertEqual(denied.status_code, 403, denied.text)
        with self._auth("job:staff", "apply-staff"):
            not_owner = self.client.patch(
                f"/api/v1/cabinet/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
                json={"status": "seen"},
            )
            self.assertEqual(not_owner.status_code, 403, not_owner.text)
            interview = self.client.patch(
                f"/api/v1/admin/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
                json={"status": "interview", "reason": ""},
            )
            self.assertEqual(interview.status_code, 422, interview.text)
            self.assertNotIn("interview", interview.text)
            long_reason = self.client.patch(
                f"/api/v1/admin/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
                json={"status": "rejected", "reason": "x" * 401},
            )
            self.assertEqual(long_reason.status_code, 422, long_reason.text)
            self.assertEqual(long_reason.json()["detail"], "Rədd səbəbi çox uzundur")
            seen = self.client.patch(
                f"/api/v1/admin/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
                json={"status": "seen"},
            )
            self.assertEqual(seen.status_code, 200, seen.text)
            self.assertEqual(seen.json()["status"], "seen")
            self.assertNotIn("reason", seen.json())
        with self._auth("job:candidate", "apply-candidate"):
            mine = self.client.get("/api/v1/applications", headers={"Authorization": "Bearer test"})
            self.assertEqual(mine.json()["items"][0]["status"], "seen")
            self.assertNotIn("reason", mine.json()["items"][0])
            self.assertEqual(mine.json()["items"][0]["answers"][0]["question"], "Nece eshitdiniz?")

        revised = self._form(questions=[{"id": question_id, "text": "Yeni sual", "required": True}])
        with self._auth("job:employer", "apply-employer"):
            edited = self.client.patch(
                f"/api/v1/cabinet/jobs/{ad_id}",
                headers={"Authorization": "Bearer test"},
                json=self._ad(form=revised),
            )
            self.assertEqual(edited.status_code, 200, edited.text)
            self.assertEqual(edited.json()["status"], "published")
            self.assertEqual(edited.json()["form"]["questions"][0]["text"], "Yeni sual")
            self.assertFalse(edited.json()["form"]["phone"]["enabled"])
        with self._auth("job:candidate", "apply-candidate"):
            kept = self.client.get("/api/v1/applications", headers={"Authorization": "Bearer test"})
            self.assertEqual(kept.json()["items"][0]["phone"], "0501112233")
            self.assertEqual(kept.json()["items"][0]["answers"], [{"question": "Nece eshitdiniz?", "answer": "Dostdan"}])
            self.assertTrue(kept.json()["items"][0]["has_cv"])
        with self._auth("job:candidate", "other-candidate"):
            stale = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                json={"phone": "0509998877", "answers": [{"id": question_id, "answer": "Elan"}]},
            )
            self.assertEqual(stale.status_code, 422, stale.text)
            fresh = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                json={"answers": [{"id": question_id, "answer": "Elan"}]},
            )
            self.assertEqual(fresh.status_code, 200, fresh.text)
            self.assertEqual(fresh.json()["answers"], [{"question": "Yeni sual", "answer": "Elan"}])
            self.assertEqual(fresh.json()["phone"], "")
            self.assertEqual(fresh.json()["status"], "submitted")

        with self._auth("job:employer", "apply-employer"):
            cannot = self.client.delete(
                f"/api/v1/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(cannot.status_code, 403, cannot.text)
        with self._auth("job:staff", "apply-staff"):
            cannot = self.client.delete(
                f"/api/v1/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(cannot.status_code, 403, cannot.text)
        with self._auth("job:candidate", "apply-candidate"):
            gone = self.client.delete(
                f"/api/v1/applications/{body['id']}",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(gone.status_code, 204, gone.text)
            self.assertEqual(gone.content, b"")
            missing_cv = self.client.get(
                f"/api/v1/applications/{body['id']}/cv",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(missing_cv.status_code, 404)
            self.assertNotIn(b"form-cv", missing_cv.content)
            mine = self.client.get("/api/v1/applications", headers={"Authorization": "Bearer test"})
            self.assertEqual(mine.json()["items"], [])
            returned = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                json={"answers": [{"id": question_id, "answer": "Yeniden"}]},
            )
            self.assertEqual(returned.status_code, 200, returned.text)
            self.assertNotEqual(returned.json()["id"], body["id"])
            self.assertEqual(returned.json()["status"], "submitted")
            self.assertEqual(returned.json()["answers"][0]["question"], "Yeni sual")
            duplicate = self.client.post(
                f"/api/v1/jobs/{ad_id}/apply",
                headers={"Authorization": "Bearer test"},
                json={"answers": [{"id": question_id, "answer": "Yeniden"}]},
            )
            self.assertEqual(duplicate.status_code, 409, duplicate.text)

        with self._auth("job:employer", "apply-employer"):
            owned = self.client.get("/api/v1/cabinet/applications", headers={"Authorization": "Bearer test"})
            subjects = {item["candidate_subject"] for item in owned.json()["items"]}
            self.assertNotIn("apply-candidate-old", subjects)
            self.assertIn("apply-candidate", subjects)
            self.assertIn("other-candidate", subjects)
        conn = sqlite3.connect(self.db)
        statuses = {row[0] for row in conn.execute("SELECT status FROM applications")}
        conn.close()
        self.assertTrue(statuses <= {"submitted", "seen", "rejected"})
        self.assertFalse(statuses & {"interview"})
        stored = list(self.cvs.iterdir()) if self.cvs.exists() else []
        self.assertEqual(stored, [])



if __name__ == "__main__":
    unittest.main()
