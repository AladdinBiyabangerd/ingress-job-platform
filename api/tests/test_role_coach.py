"""Role skill coach AI + skill-gap wiring."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.role_coach import PROMPT_VERSION, _skill_card, _validate_coach, build_role_coach


class RoleCoachSkillCardTests(unittest.TestCase):
    def test_includes_rounded_share_and_growth(self):
        cards = _skill_card(
            [
                {"name": "Java", "weight": 1.0, "share": 0.42004, "growth": 0.12345, "years": 3},
                {"name": "Kafka", "weight": 0.9, "share": 0.11},
            ]
        )
        self.assertEqual(
            cards,
            [
                {"name": "Java", "weight": 1.0, "years": 3, "share": 0.42, "growth": 0.1235},
                {"name": "Kafka", "weight": 0.9, "share": 0.11},
            ],
        )

    def test_stable_sort_ignores_trend_display_order(self):
        """UI may rank by share; card order stays weight×name (metrics still embedded)."""
        cards = _skill_card(
            [
                {"name": "ZooKeeper", "weight": 0.5, "share": 0.99},
                {"name": "Kafka", "weight": 0.9, "share": 0.01},
                {"name": "Java", "weight": 1.0, "share": 0.5},
            ]
        )
        self.assertEqual([c["name"] for c in cards], ["Java", "Kafka", "ZooKeeper"])
        self.assertEqual(cards[0]["share"], 0.5)

    def test_different_roles_build_different_user_prompts(self):
        from app.role_coach import _build_user

        common = dict(
            lang="en",
            have=[{"name": "Java", "weight": 1.0}],
            missing=[{"name": "Kafka", "weight": 0.9}],
            profile={"seniority": "middle", "skills": [{"name": "Java"}, {"name": "SQL"}]},
        )
        backend = _build_user(role_name="Backend Engineer", **common)
        frontend = _build_user(role_name="Frontend Engineer", **common)
        self.assertIn("Role: Backend Engineer", backend)
        self.assertIn("Role: Frontend Engineer", frontend)
        self.assertNotEqual(backend, frontend)
        # TopSkills sorted — list order in profile must not matter.
        shuffled = _build_user(
            role_name="Backend Engineer",
            lang="en",
            have=[{"name": "Java", "weight": 1.0}],
            missing=[{"name": "Kafka", "weight": 0.9}],
            profile={"seniority": "middle", "skills": [{"name": "SQL"}, {"name": "Java"}]},
        )
        self.assertEqual(backend, shuffled)

    def test_azerbaijani_prompt_requires_orthography(self):
        from app.role_coach import _build_user

        az = _build_user(
            lang="az",
            role_name="Java Developer",
            have=[{"name": "Java", "weight": 1.0}],
            missing=[{"name": "Kafka", "weight": 0.9}],
            profile={"seniority": "middle", "skills": [{"name": "Java"}]},
        )
        en = _build_user(
            lang="en",
            role_name="Java Developer",
            have=[{"name": "Java", "weight": 1.0}],
            missing=[{"name": "Kafka", "weight": 0.9}],
            profile={"seniority": "middle", "skills": [{"name": "Java"}]},
        )
        self.assertIn("tələblərə", az)
        self.assertIn("Language: Azerbaijani", az)
        self.assertNotIn("tələblərə", en)


class RoleCoachValidateTests(unittest.TestCase):
    def setUp(self):
        self.have = [
            {"name": "Java", "weight": 1.0},
            {"name": "Spring", "weight": 0.8},
        ]
        self.missing = [
            {"name": "Kafka", "weight": 0.9},
            {"name": "Kubernetes", "weight": 0.7},
        ]

    def test_keeps_taxonomy_skills_only(self):
        data = {
            "fit_summary": "You are strong on Java and Spring for this backend role.",
            "must_learn": [
                {"skill": "Kafka", "why": "Core for event-driven services", "priority": 1},
                {"skill": "Invented", "why": "Nope", "priority": 1},
                {"skill": "kubernetes", "why": "Deployments", "priority": 2},
            ],
            "already_strong": ["Java", "Teleportation", "Spring"],
            "transferable": [
                {"from": "Spring", "to": "Kafka", "note": "Messaging patterns transfer"},
                {"from": "Java", "to": "Haskell", "note": "drop"},
            ],
        }
        out = _validate_coach(data, have=self.have, missing=self.missing)
        self.assertIsNotNone(out)
        self.assertEqual([x["skill"] for x in out["must_learn"]], ["Kafka", "Kubernetes"])
        self.assertEqual(out["already_strong"], ["Java", "Spring"])
        self.assertEqual(len(out["transferable"]), 1)
        self.assertEqual(out["transferable"][0]["to"], "Kafka")

    def test_short_summary_rejects(self):
        data = {
            "fit_summary": "Too short",
            "must_learn": [],
            "already_strong": [],
            "transferable": [],
        }
        self.assertIsNone(_validate_coach(data, have=self.have, missing=self.missing))


class RoleCoachBuildTests(unittest.TestCase):
    def test_flag_off(self):
        with patch.dict(os.environ, {"AI_ROLE_COACH_ENABLED": "0"}, clear=False):
            coach, err = build_role_coach(
                None,
                role_name="Java Backend",
                have=[{"name": "Java"}],
                missing=[{"name": "Kafka"}],
                profile={"seniority": "middle"},
                lang="en",
            )
        self.assertIsNone(coach)
        self.assertEqual(err, "role_coach_disabled")

    def test_applies_when_flag_on(self):
        from app.ai_gateway.gateway import GatewayResult

        fake = GatewayResult(
            ok=True,
            data={
                "fit_summary": "Solid Java base; add Kafka next for event streaming roles.",
                "must_learn": [
                    {"skill": "Kafka", "why": "Common in backend ads", "priority": 1},
                ],
                "already_strong": ["Java"],
                "transferable": [
                    {"from": "Java", "to": "Kafka", "note": "Same runtime ecosystem"},
                ],
            },
        )
        with patch.dict(os.environ, {"AI_ROLE_COACH_ENABLED": "1"}, clear=False):
            with patch("app.role_coach.complete_json", return_value=fake) as api:
                coach, err = build_role_coach(
                    None,
                    role_name="Java Backend",
                    have=[{"name": "Java", "weight": 1}],
                    missing=[{"name": "Kafka", "weight": 0.9}],
                    profile={"seniority": "middle", "skills": [{"name": "Java"}]},
                    lang="en",
                )
        self.assertEqual(err, "")
        self.assertIsNotNone(coach)
        self.assertIn("Solid Java", coach["fit_summary"])
        self.assertEqual(coach["must_learn"][0]["skill"], "Kafka")
        self.assertEqual(api.call_args.kwargs["prompt_version"], PROMPT_VERSION)

    def test_soft_fail(self):
        from app.ai_gateway.gateway import GatewayResult

        with patch.dict(os.environ, {"AI_ROLE_COACH_ENABLED": "1"}, clear=False):
            with patch(
                "app.role_coach.complete_json",
                return_value=GatewayResult(ok=False, error="ai_provider_error"),
            ):
                coach, err = build_role_coach(
                    None,
                    role_name="Java Backend",
                    have=[{"name": "Java"}],
                    missing=[{"name": "Kafka"}],
                    profile={},
                    lang="az",
                )
        self.assertIsNone(coach)
        self.assertEqual(err, "ai_provider_error")


class SkillGapCoachWireTests(unittest.TestCase):
    def test_payload_adds_coach_fields(self):
        from app.skill_gap import skill_gap_payload

        fake_coach = {
            "fit_summary": "You cover core Java well; learn Kafka next.",
            "must_learn": [{"skill": "Kafka", "why": "Events", "priority": 1}],
            "already_strong": ["Java"],
            "transferable": [],
        }

        class FakeConn:
            def execute(self, *a, **k):
                raise AssertionError("should be mocked before SQL")

        with patch("app.skill_gap.ensure_profile_tables"):
          with patch("app.skill_gap._matching_granted", return_value=True):
            with patch(
                "app.skill_gap._profile_payload",
                return_value={
                    "exists": True,
                    "status": "ready",
                    "profile": {
                        "seniority": "middle",
                        "skills": [{"name": "Java", "years": 3}],
                    },
                },
            ):
                with patch(
                    "app.skill_gap.resolve_taxonomy_role",
                    return_value={
                        "id": 1,
                        "canonical_name": "Java Backend Developer",
                        "category": "Backend",
                        "academy_career_path_id": "",
                    },
                ):
                    with patch(
                        "app.skill_gap._role_target_skills",
                        return_value=[
                            {
                                "skill_id": 10,
                                "name": "Java",
                                "weight": 1.0,
                                "share": None,
                                "growth": None,
                                "academy_courses": [],
                                "group_key": "",
                            },
                            {
                                "skill_id": 11,
                                "name": "Kafka",
                                "weight": 0.9,
                                "share": None,
                                "growth": None,
                                "academy_courses": [],
                                "group_key": "",
                            },
                        ],
                    ):
                        with patch("app.trends.trend_metrics_for_skills", return_value={}):
                          with patch("app.trends.best_pair_share_for_missing", return_value={}):
                            with patch(
                                "app.skill_gap._candidate_skills",
                                return_value={10: {"years": 3}},
                            ):
                                with patch(
                                    "app.skill_gap._build_skill_lookup",
                                    return_value={},
                                ):
                                    with patch(
                                        "app.role_coach.build_role_coach",
                                        return_value=(fake_coach, ""),
                                    ):
                                        with patch(
                                            "app.ai_warm.schedule_skill_gap_sibling_langs"
                                        ) as siblings:
                                            with patch.dict(
                                                os.environ,
                                                {"AI_ROLE_COACH_ENABLED": "1"},
                                                clear=False,
                                            ):
                                                out = skill_gap_payload(
                                                    FakeConn(),
                                                    user_id="u1",
                                                    role="Java Backend Developer",
                                                    lang="en",
                                                )
        self.assertTrue(out["ai_coach"])
        self.assertEqual(out["coach_error"], "")
        self.assertEqual(out["coach"]["fit_summary"], fake_coach["fit_summary"])
        self.assertIn("+role_coach", out["source"])
        self.assertEqual(out["have"][0]["name"], "Java")
        self.assertEqual(out["missing"][0]["name"], "Kafka")
        siblings.assert_called_once()
        self.assertEqual(siblings.call_args.kwargs["lang"], "en")
        self.assertEqual(siblings.call_args.kwargs["user_id"], "u1")

    def test_payload_surfaces_coach_error(self):
        from app.skill_gap import skill_gap_payload

        class FakeConn:
            def execute(self, *a, **k):
                raise AssertionError("should be mocked before SQL")

        with patch("app.skill_gap.ensure_profile_tables"):
          with patch("app.skill_gap._matching_granted", return_value=True):
            with patch(
                "app.skill_gap._profile_payload",
                return_value={
                    "exists": True,
                    "status": "ready",
                    "profile": {"skills": [{"name": "Java"}]},
                },
            ):
                with patch(
                    "app.skill_gap.resolve_taxonomy_role",
                    return_value={
                        "id": 1,
                        "canonical_name": "Java Backend Developer",
                        "category": "Backend",
                        "academy_career_path_id": "",
                    },
                ):
                    with patch(
                        "app.skill_gap._role_target_skills",
                        return_value=[
                            {
                                "skill_id": 10,
                                "name": "Java",
                                "weight": 1.0,
                                "share": None,
                                "growth": None,
                                "academy_courses": [],
                                "group_key": "",
                            },
                        ],
                    ):
                        with patch("app.trends.trend_metrics_for_skills", return_value={}):
                            with patch(
                                "app.skill_gap._candidate_skills",
                                return_value={10: {"years": 3}},
                            ):
                                with patch(
                                    "app.skill_gap._build_skill_lookup",
                                    return_value={},
                                ):
                                    with patch(
                                        "app.role_coach.build_role_coach",
                                        return_value=(None, "ai_no_key"),
                                    ):
                                        out = skill_gap_payload(
                                            FakeConn(),
                                            user_id="u1",
                                            role="Java Backend Developer",
                                            lang="en",
                                        )
        self.assertFalse(out["ai_coach"])
        self.assertIsNone(out["coach"])
        self.assertEqual(out["coach_error"], "ai_no_key")

    def test_payload_schedules_warm_on_ai_pending(self):
        from app.skill_gap import skill_gap_payload

        class FakeConn:
            def execute(self, *a, **k):
                raise AssertionError("should be mocked before SQL")

        with patch("app.skill_gap.ensure_profile_tables"):
          with patch("app.skill_gap._matching_granted", return_value=True):
            with patch(
                "app.skill_gap._profile_payload",
                return_value={
                    "exists": True,
                    "status": "ready",
                    "profile": {"skills": [{"name": "Java"}]},
                },
            ):
                with patch(
                    "app.skill_gap.resolve_taxonomy_role",
                    return_value={
                        "id": 1,
                        "canonical_name": "Java Backend Developer",
                        "category": "Backend",
                        "academy_career_path_id": "",
                    },
                ):
                    with patch(
                        "app.skill_gap._role_target_skills",
                        return_value=[
                            {
                                "skill_id": 10,
                                "name": "Java",
                                "weight": 1.0,
                                "share": None,
                                "growth": None,
                                "academy_courses": [],
                                "group_key": "",
                            },
                        ],
                    ):
                        with patch("app.trends.trend_metrics_for_skills", return_value={}):
                            with patch(
                                "app.skill_gap._candidate_skills",
                                return_value={10: {"years": 3}},
                            ):
                                with patch(
                                    "app.skill_gap._build_skill_lookup",
                                    return_value={},
                                ):
                                    with patch(
                                        "app.role_coach.build_role_coach",
                                        return_value=(None, "ai_pending"),
                                    ):
                                        with patch(
                                            "app.ai_warm.skill_gap_warm_fail_code",
                                            return_value=None,
                                        ):
                                            with patch(
                                                "app.ai_warm.schedule_skill_gap_ai_warm"
                                            ) as warm:
                                                out = skill_gap_payload(
                                                    FakeConn(),
                                                    user_id="u1",
                                                    role="Java Backend Developer",
                                                    lang="en",
                                                )
        self.assertEqual(out["coach_error"], "ai_pending")
        warm.assert_called_once()
        self.assertEqual(warm.call_args.kwargs["user_id"], "u1")
        self.assertEqual(warm.call_args.kwargs["role"], "Java Backend Developer")


if __name__ == "__main__":
    unittest.main()
