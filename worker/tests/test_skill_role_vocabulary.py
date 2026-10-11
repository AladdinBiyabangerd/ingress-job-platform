"""Expanded skill dictionary + role taxonomy: coverage, ambiguity, sync."""

from __future__ import annotations

import json
import re
import unittest
from collections import defaultdict
from pathlib import Path

from worker.roles import load_seed as load_roles
from worker.skills import load_seed as load_skills
from worker.techstack import (
    _TECH,
    CATEGORIES,
    TECH_NAMES,
    extract_stack,
    find_stack,
    is_tech_job,
    stack_from_tags,
)

ROOT = Path(__file__).resolve().parents[2]


class SkillCoverageTest(unittest.TestCase):
    def test_new_skills_extracted(self):
        text = (
            "Stack: FastAPI, SQLAlchemy, Pydantic, AWS Lambda, Amazon S3, SQS, Terraform, "
            "Burp Suite, SAST, STM32, FreeRTOS, I2C, Zustand, React Query, HTMX, Power BI, "
            "SAP S/4HANA, Azure Data Factory, Snyk, DuckDB, LangGraph, vLLM, Allure, TestRail, "
            "Hardhat, Solana, WCAG, Kafka, Agile, Scrum."
        )
        found = set(find_stack(text))
        for name in (
            "FastAPI", "SQLAlchemy", "Pydantic", "AWS Lambda", "Amazon S3", "Amazon SQS",
            "Burp Suite", "SAST", "STM32", "RTOS", "I2C/SPI/UART", "Zustand", "React Query",
            "HTMX", "Power BI", "SAP", "Azure Data Factory", "Snyk", "DuckDB", "LangGraph",
            "vLLM", "Allure", "TestRail", "Hardhat", "Solana", "WCAG", "Agile", "Scrum",
        ):
            self.assertIn(name, found, name)

    def test_ambiguous_words_do_not_match(self):
        noise = (
            "We go to the Zig zag; the chef cooked in the express lane. Spring is here. "
            "Swift response, r and c, ML, CIS. Ray of light. Notion of fun. Sketch of a plan. "
            "Apex predator. Excel at teamwork. Vector graphics. Nomad lifestyle. Envoy to the UN. "
            "Yarn and wool. Babel tower. Locust swarm. Tornado warning. Puppet show. "
            "Packer in a warehouse. Expo 2020. kali. burp. snort laugh. bluetooth speaker. "
            "rest of the day. state of the art. windows and doors."
        )
        found = set(find_stack(noise)) - {"Swift", "Design Systems"}  # Swift: pre-existing rule
        self.assertEqual(found, set(), found)

    def test_context_forms_still_match(self):
        text = (
            "Advanced Excel, Notion, Babel/Webpack, Puppet, HashiCorp Packer, Expo Router, "
            "Kali Linux, Bluetooth Low Energy, Apex code, Yarn workspaces, Zig language"
        )
        found = set(find_stack(text))
        for name in ("Excel", "Notion", "Babel", "Puppet", "Packer", "Expo", "Kali Linux",
                     "Bluetooth Low Energy", "Apex", "Yarn", "Zig"):
            self.assertIn(name, found, name)

    def test_security_acronyms_need_uppercase(self):
        self.assertIn("EDR", find_stack("Tune EDR and SIEM rules"))
        self.assertNotIn("EDR", find_stack("the Edr family"))
        self.assertNotIn("WAF", find_stack("a waf of cloth"))
        self.assertIn("WAF", find_stack("Manage WAF policies"))
        self.assertNotIn("SIEM", find_stack("Siemens engineers"))

    def test_vocabulary_categories_not_job_chips(self):
        stack = extract_stack("We use Agile, Scrum and REST API microservices with Python.", None, "Engineer")
        self.assertIn("Python", stack)
        for generic in ("Agile", "Scrum", "REST API", "Microservices"):
            self.assertNotIn(generic, stack)
        # ...but they are still extracted from CVs
        cv = set(find_stack("Agile Scrum REST API microservices Python"))
        self.assertTrue({"Agile", "Scrum", "REST API", "Microservices", "Python"} <= cv)

    def test_tags_map_to_canonical(self):
        self.assertEqual(stack_from_tags(["ec2", "vitest", "htmx"]), ["Amazon EC2", "Vitest", "HTMX"])
        self.assertEqual(stack_from_tags(["ml", "cis", "ai", "rest of"]), [])

    def test_dictionary_in_sync_and_unique(self):
        names = [n for n, _p, _a, _c in _TECH]
        self.assertEqual(len(names), len(set(names)))
        owner: dict[str, set[str]] = defaultdict(set)
        for name, _p, aliases, _c in _TECH:
            for key in (name.lower(), *aliases):
                owner[key].add(name)
        self.assertEqual({k: v for k, v in owner.items() if len(v) > 1}, {})
        docs = json.loads((ROOT / "docs/cv-ai/skill-dictionary-v1.json").read_text(encoding="utf-8"))
        packaged = load_skills()
        self.assertEqual(
            sorted(s["canonical_name"] for s in docs["skills"]),
            sorted(s["canonical_name"] for s in packaged),
        )
        self.assertEqual(sorted(TECH_NAMES), sorted(s["canonical_name"] for s in packaged))
        self.assertGreaterEqual(len(packaged), 2000)

    def test_non_it_titles_still_rejected(self):
        for title in (
            "Sales Engineer", "Customer Support Engineer", "Head of Sales", "Marketing Manager",
            "Mechanical Engineer", "Civil Engineer", "Accountant", "Recruiter", "Warehouse Operator",
            "Head of Crypto", "Content Writer", "Nurse",
        ):
            self.assertFalse(is_tech_job(title), title)


class BatchTwoGuardTest(unittest.TestCase):
    def test_new_batch_extracts(self):
        text = (
            "Stack: Spring WebFlux, Hibernate ORM, Flyway migrations are not needed; Zod, Pinia, Vuetify, "
            "Recharts, Alamofire, Jetpack Navigation Component, Riverpod, Axum, Tokio, Diesel ORM, "
            "Terraform, Amazon EKS, AWS GuardDuty, CloudTrail, Azure Key Vault, Azure Data Explorer, "
            "BigQuery, Dataproc, Cloud Composer, AlloyDB, Camunda, MuleSoft, Dagster, DuckDB, "
            "Hasura, Playwright, Testcontainers, WireMock, Qdrant, XGBoost, spaCy, LlamaIndex."
        )
        found = set(find_stack(text))
        for name in ("Pinia", "Vuetify", "Recharts", "Alamofire", "Riverpod", "AWS GuardDuty",
                     "AWS CloudTrail", "Azure Key Vault", "Google Dataproc", "Google Composer",
                     "Google AlloyDB", "Camunda", "MuleSoft", "Dagster", "DuckDB", "Hasura",
                     "Testcontainers", "WireMock", "Pinecone", "XGBoost", "spaCy", "LlamaIndex"):
            self.assertIn(name, found, name)

    def test_common_words_and_short_names_do_not_match(self):
        noise = (
            "Document processing of customer requests and responses. The h3 tag. Analog circuits. "
            "Nerves of steel. Rack layouts and cooling. Member of the ACM and the ACR. "
            "Go-to-market (GTM) with KPI dashboards under CCPA. Tier 1 teams and L1 support. "
            "Mentoring juniors. Concurrency constructs. Amplify impact. Click here. Black and white. "
            "Shared workspaces. Solution design workshop. Platform roadmap. Core Data Services. "
            "Cuts of kernel development; kernel drivers; the analog dash panel; a rich temporal view."
        )
        self.assertEqual(find_stack(noise), [])

    def test_aliases_work_as_tags_but_not_free_text(self):
        self.assertEqual(stack_from_tags(["cloudtrail", "gce", "adf"]),
                         ["AWS CloudTrail", "Google Compute Engine", "Azure Data Factory"])
        self.assertNotIn("Google Compute Engine", find_stack("the gce team"))
        self.assertNotIn("Apache Druid", find_stack("a druid in a game"))

    def test_prefilter_matches_brute_force(self):
        from worker import techstack as t

        sample = (
            "Senior engineer: C++17, Go, .NET Core, AWS, Next.js, k6, I2C, Kubernetes (EKS), "
            "Azure DevOps, CI/CD, Terraform, Amazon S3, Spring Boot, PostgreSQL, SAP S/4HANA."
        )

        def brute(text):
            hits = sorted((p.search(text).start(), n) for n, p, _a, _c in t._TECH if p.search(text))
            return [n for _pos, n in hits]

        self.assertEqual(brute(sample), find_stack(sample))
        self.assertGreater(len(find_stack(sample)), 10)

    def test_dictionary_size_and_alias_total(self):
        skills = load_skills()
        self.assertGreaterEqual(len(skills), 2300)
        self.assertGreaterEqual(sum(len(s["synonyms"]) for s in skills), 800)


class RoleTaxonomyTest(unittest.TestCase):
    def test_roles_valid(self):
        roles = load_roles()
        docs = json.loads((ROOT / "docs/cv-ai/role-taxonomy-v1.json").read_text(encoding="utf-8"))["roles"]
        self.assertEqual([r["canonical_name"] for r in roles], [r["canonical_name"] for r in docs])
        self.assertGreaterEqual(len(roles), 150)
        skills = {s["canonical_name"] for s in load_skills()}
        owner: dict[str, str] = {}
        for role in roles:
            self.assertIn(role["category"], CATEGORIES, role["canonical_name"])
            self.assertTrue(role["signature_skills"], role["canonical_name"])
            for sig in role["signature_skills"]:
                self.assertIn(sig["skill"], skills, role["canonical_name"])
            for phrase in [role["canonical_name"], *role["synonyms"]]:
                key = phrase.lower()
                self.assertEqual(owner.setdefault(key, role["canonical_name"]), role["canonical_name"], key)
                self.assertNotIn(key, {"go", "swift", "rust", "r", "c"})

    def test_multilingual_and_new_roles_present(self):
        names = {r["canonical_name"]: set(map(str.lower, r["synonyms"])) for r in load_roles()}
        for role in ("Penetration Tester", "BI Developer", "AI Engineer", "Embedded Software Engineer",
                     "Solidity Developer", "Technical Writer", "Cloud Architect", "Engineering Manager"):
            self.assertIn(role, names)
        self.assertIn("тестировщик", names["QA Engineer"])
        self.assertIn("layihə meneceri", names["Technical Project Manager"])
        self.assertIn("ingeniero de datos", names["Data Engineer"])

    def test_english_engineer_synonyms_are_accepted_titles(self):
        pat = re.compile(r"(?i)\b(?:engineer|developer)\b")
        for role in load_roles():
            for syn in role["synonyms"]:
                if pat.search(syn) and re.fullmatch(r"[A-Za-z0-9 .+#/&()\-]+", syn) \
                        and not re.search(r"(?i)sales|support|customer|pre-?sales|solutions? consult", syn):
                    self.assertTrue(is_tech_job(syn), syn)


if __name__ == "__main__":
    unittest.main()
