#!/usr/bin/env python3
"""Build role-taxonomy-v1.2.json from the skill dictionary (canonical names only)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT = ROOT / "docs" / "cv-ai" / "skill-dictionary-v1.json"
OUT_DOCS = ROOT / "docs" / "cv-ai" / "role-taxonomy-v1.json"
OUT_WORKER = ROOT / "worker" / "worker" / "role_taxonomy_v1.json"


def load_skills() -> set[str]:
    data = json.loads(DICT.read_text(encoding="utf-8"))
    return {str(s["canonical_name"]) for s in data["skills"]}


SKILLS = load_skills()


def s(name: str, weight: float, group: str | None = None) -> dict:
    if name not in SKILLS:
        raise SystemExit(f"unknown skill: {name!r}")
    item: dict = {"skill": name, "weight": weight}
    if group:
        item["group"] = group
    return item


def role(name: str, category: str, synonyms: list[str], skills: list[dict]) -> dict:
    return {
        "canonical_name": name,
        "category": category,
        "synonyms": synonyms,
        "signature_skills": skills,
    }


ROLES: list[dict] = [
    # ---- Backend ----
    role(
        "Java Developer",
        "Backend",
        [
            "Java Engineer",
            "Java Backend Developer",
            "Backend Java Developer",
            "Java Software Engineer",
            "Spring Boot Developer",
        ],
        [
            s("Java", 1.0),
            s("Spring", 0.85),
            s("SQL", 0.45),
            s("PostgreSQL", 0.4),
            s("Kafka", 0.4),
            s("Redis", 0.3),
            s("Docker", 0.3),
            s("Kubernetes", 0.25),
            s("gRPC", 0.25),
            s("AWS", 0.25),
        ],
    ),
    role(
        "Python Developer",
        "Backend",
        [
            "Python Engineer",
            "Python Backend Developer",
            "Backend Python Developer",
            "Python Software Engineer",
        ],
        [
            s("Python", 1.0),
            s("Django", 0.65, "fw"),
            s("FastAPI", 0.65, "fw"),
            s("Flask", 0.45, "fw"),
            s("SQL", 0.45),
            s("PostgreSQL", 0.4),
            s("Redis", 0.3),
            s("Docker", 0.3),
            s("AWS", 0.25),
            s("Kafka", 0.25),
        ],
    ),
    role(
        "Go Developer",
        "Backend",
        ["Golang Developer", "Go Engineer", "Golang Engineer", "Go Backend Developer"],
        [
            s("Go", 1.0),
            s("Kubernetes", 0.55),
            s("PostgreSQL", 0.45),
            s("gRPC", 0.45),
            s("Docker", 0.4),
            s("Kafka", 0.3),
            s("Redis", 0.3),
            s("AWS", 0.3),
            s("SQL", 0.25),
        ],
    ),
    role(
        ".NET Developer",
        "Backend",
        [
            "C# Developer",
            "ASP.NET Developer",
            ".NET Engineer",
            "C# Engineer",
            ".NET Backend Developer",
        ],
        [
            s(".NET", 1.0),
            s("C#", 0.95),
            s("SQL", 0.55),
            s("Azure", 0.5),
            s("PostgreSQL", 0.35),
            s("Redis", 0.25),
            s("Docker", 0.25),
            s("Kafka", 0.2),
        ],
    ),
    role(
        "Node.js Developer",
        "Backend",
        [
            "Node Developer",
            "Node Engineer",
            "NestJS Developer",
            "Node.js Backend Developer",
            "Express Developer",
        ],
        [
            s("Node.js", 1.0),
            s("TypeScript", 0.85),
            s("NestJS", 0.55, "fw"),
            s("Express", 0.45, "fw"),
            s("PostgreSQL", 0.4),
            s("MongoDB", 0.35),
            s("Redis", 0.3),
            s("GraphQL", 0.25),
            s("Docker", 0.25),
        ],
    ),
    role(
        "PHP Developer",
        "Backend",
        ["PHP Engineer", "PHP Backend Developer", "Backend PHP Developer", "Laravel Developer"],
        [
            s("PHP", 1.0),
            s("Laravel", 0.7, "fw"),
            s("Symfony", 0.55, "fw"),
            s("MySQL", 0.5),
            s("SQL", 0.45),
            s("PostgreSQL", 0.3),
            s("Redis", 0.25),
            s("Docker", 0.2),
        ],
    ),
    role(
        "Ruby Developer",
        "Backend",
        ["Ruby Engineer", "Ruby on Rails Developer", "Rails Developer", "RoR Developer"],
        [
            s("Ruby", 1.0),
            s("Ruby on Rails", 0.9),
            s("PostgreSQL", 0.5),
            s("SQL", 0.4),
            s("Redis", 0.35),
            s("Docker", 0.25),
            s("AWS", 0.2),
        ],
    ),
    role(
        "Rust Developer",
        "Backend",
        ["Rust Engineer", "Rust Backend Developer", "Systems Rust Developer"],
        [
            s("Rust", 1.0),
            s("PostgreSQL", 0.35),
            s("gRPC", 0.35),
            s("Docker", 0.3),
            s("Kubernetes", 0.3),
            s("Kafka", 0.25),
            s("AWS", 0.2),
            s("Redis", 0.2),
        ],
    ),
    role(
        "Scala Developer",
        "Backend",
        ["Scala Engineer", "Scala Backend Developer", "JVM Scala Developer"],
        [
            s("Scala", 1.0),
            s("Java", 0.4),
            s("Kafka", 0.5),
            s("Spark", 0.45),
            s("PostgreSQL", 0.35),
            s("Docker", 0.25),
            s("Kubernetes", 0.25),
            s("AWS", 0.25),
        ],
    ),
    role(
        "Kotlin Developer",
        "Backend",
        ["Kotlin Engineer", "Kotlin Backend Developer", "JVM Kotlin Developer"],
        [
            s("Kotlin", 1.0),
            s("Java", 0.45),
            s("Spring", 0.55),
            s("PostgreSQL", 0.4),
            s("SQL", 0.35),
            s("Kafka", 0.3),
            s("Docker", 0.25),
            s("gRPC", 0.25),
        ],
    ),
    role(
        "C++ Developer",
        "Backend",
        ["C++ Engineer", "CPP Developer", "C++ Software Engineer"],
        [
            s("C++", 1.0),
            s("C", 0.5),
            s("Linux", 0.45),
            s("Python", 0.25),
            s("SQL", 0.2),
            s("Docker", 0.2),
            s("gRPC", 0.2),
        ],
    ),
    role(
        "Elixir Developer",
        "Backend",
        ["Elixir Engineer", "Phoenix Developer", "Erlang Elixir Developer"],
        [
            s("Elixir", 1.0),
            s("Phoenix", 0.85),
            s("Erlang", 0.4),
            s("PostgreSQL", 0.4),
            s("Redis", 0.3),
            s("Docker", 0.25),
            s("AWS", 0.2),
        ],
    ),
    role(
        "Backend Engineer",
        "Backend",
        [
            "Backend Developer",
            "Server-side Engineer",
            "API Engineer",
            "Backend Software Engineer",
        ],
        [
            s("Java", 0.7, "lang"),
            s("Python", 0.7, "lang"),
            s("Go", 0.65, "lang"),
            s("Node.js", 0.65, "lang"),
            s(".NET", 0.6, "lang"),
            s("PHP", 0.5, "lang"),
            s("Ruby", 0.5, "lang"),
            s("Rust", 0.5, "lang"),
            s("SQL", 0.55),
            s("PostgreSQL", 0.45),
            s("Docker", 0.4),
            s("AWS", 0.4),
            s("Kafka", 0.35),
            s("Redis", 0.35),
            s("Kubernetes", 0.3),
        ],
    ),
    # ---- Frontend ----
    role(
        "React Developer",
        "Frontend",
        [
            "React Engineer",
            "React.js Developer",
            "React Frontend Developer",
            "React Software Engineer",
        ],
        [
            s("React", 1.0),
            s("TypeScript", 0.85),
            s("JavaScript", 0.65),
            s("Next.js", 0.5),
            s("Redux", 0.4),
            s("CSS", 0.4),
            s("HTML", 0.35),
            s("Tailwind", 0.35),
            s("Jest", 0.25),
            s("GraphQL", 0.25),
        ],
    ),
    role(
        "Angular Developer",
        "Frontend",
        ["Angular Engineer", "Angular Frontend Developer", "Angular Software Engineer"],
        [
            s("Angular", 1.0),
            s("TypeScript", 0.9),
            s("JavaScript", 0.5),
            s("CSS", 0.4),
            s("HTML", 0.35),
            s("Jest", 0.25),
            s("GraphQL", 0.2),
        ],
    ),
    role(
        "Vue.js Developer",
        "Frontend",
        ["Vue Developer", "Vue Engineer", "Nuxt Developer", "Vue Frontend Developer"],
        [
            s("Vue.js", 1.0),
            s("TypeScript", 0.7),
            s("JavaScript", 0.6),
            s("Nuxt", 0.55),
            s("CSS", 0.4),
            s("HTML", 0.35),
            s("Tailwind", 0.3),
            s("Jest", 0.2),
        ],
    ),
    role(
        "Next.js Developer",
        "Frontend",
        ["Next Developer", "Next.js Engineer", "Nextjs Developer"],
        [
            s("Next.js", 1.0),
            s("React", 0.9),
            s("TypeScript", 0.85),
            s("JavaScript", 0.5),
            s("Tailwind", 0.4),
            s("CSS", 0.35),
            s("HTML", 0.3),
            s("GraphQL", 0.25),
        ],
    ),
    role(
        "Svelte Developer",
        "Frontend",
        ["Svelte Engineer", "SvelteKit Developer"],
        [
            s("Svelte", 1.0),
            s("TypeScript", 0.75),
            s("JavaScript", 0.6),
            s("CSS", 0.4),
            s("HTML", 0.35),
            s("Tailwind", 0.3),
        ],
    ),
    role(
        "Frontend Engineer",
        "Frontend",
        [
            "Frontend Developer",
            "Front-end Engineer",
            "UI Engineer",
            "Web Developer",
            "Client-side Engineer",
        ],
        [
            s("React", 0.9, "framework"),
            s("Angular", 0.85, "framework"),
            s("Vue.js", 0.85, "framework"),
            s("Svelte", 0.7, "framework"),
            s("TypeScript", 0.8),
            s("JavaScript", 0.65),
            s("CSS", 0.55),
            s("HTML", 0.45),
            s("Tailwind", 0.35),
            s("Next.js", 0.35),
            s("Jest", 0.25),
        ],
    ),
    # ---- Full-stack ----
    role(
        "Full-stack JS Developer",
        "Full-stack",
        [
            "Full Stack JavaScript Developer",
            "MERN Developer",
            "React Node Developer",
            "MEAN Developer",
        ],
        [
            s("React", 1.0),
            s("Node.js", 0.9),
            s("TypeScript", 0.8),
            s("Next.js", 0.45),
            s("PostgreSQL", 0.45),
            s("MongoDB", 0.4),
            s("SQL", 0.4),
            s("Express", 0.35),
            s("Redis", 0.25),
        ],
    ),
    role(
        "Full-stack Python Developer",
        "Full-stack",
        [
            "Python Full Stack Developer",
            "Django Full Stack Developer",
            "Python React Developer",
        ],
        [
            s("Python", 1.0),
            s("React", 0.75),
            s("Django", 0.65, "fw"),
            s("FastAPI", 0.5, "fw"),
            s("SQL", 0.5),
            s("PostgreSQL", 0.45),
            s("TypeScript", 0.3),
            s("Docker", 0.25),
        ],
    ),
    role(
        "Full-stack PHP Developer",
        "Full-stack",
        ["PHP Full Stack Developer", "Laravel Full Stack Developer"],
        [
            s("PHP", 1.0),
            s("Laravel", 0.8),
            s("JavaScript", 0.55),
            s("MySQL", 0.55),
            s("SQL", 0.45),
            s("Vue.js", 0.4, "fe"),
            s("React", 0.4, "fe"),
            s("CSS", 0.3),
            s("HTML", 0.3),
        ],
    ),
    role(
        "Full-stack Engineer",
        "Full-stack",
        [
            "Full Stack Developer",
            "Fullstack Engineer",
            "Full-stack Developer",
            "Software Engineer Full Stack",
        ],
        [
            s("React", 0.8, "fe"),
            s("Angular", 0.7, "fe"),
            s("Vue.js", 0.7, "fe"),
            s("Node.js", 0.7, "be_lang"),
            s("Python", 0.7, "be_lang"),
            s("Java", 0.6, "be_lang"),
            s("PHP", 0.5, "be_lang"),
            s("TypeScript", 0.55),
            s("SQL", 0.5),
            s("PostgreSQL", 0.45),
            s("Docker", 0.35),
            s("AWS", 0.3),
        ],
    ),
    # ---- Mobile ----
    role(
        "Android Developer",
        "Mobile",
        ["Android Engineer", "Kotlin Android Developer", "Android Software Engineer"],
        [
            s("Android", 1.0),
            s("Kotlin", 0.9),
            s("Java", 0.45),
            s("SQL", 0.25),
            s("GraphQL", 0.2),
            s("CI/CD", 0.2),
        ],
    ),
    role(
        "iOS Developer",
        "Mobile",
        ["iOS Engineer", "Swift Developer", "Swift iOS Developer", "Apple iOS Developer"],
        [
            s("iOS", 1.0),
            s("Swift", 0.95),
            s("Objective-C", 0.35),
            s("CI/CD", 0.2),
            s("GraphQL", 0.15),
        ],
    ),
    role(
        "Flutter Developer",
        "Mobile",
        ["Flutter Engineer", "Dart Flutter Developer", "Flutter Mobile Developer"],
        [
            s("Flutter", 1.0),
            s("Dart", 0.9),
            s("Android", 0.35),
            s("iOS", 0.35),
            s("CI/CD", 0.2),
            s("SQL", 0.15),
        ],
    ),
    role(
        "React Native Developer",
        "Mobile",
        ["React Native Engineer", "RN Developer", "React Native Mobile Developer"],
        [
            s("React Native", 1.0),
            s("TypeScript", 0.75),
            s("React", 0.65),
            s("JavaScript", 0.55),
            s("CI/CD", 0.2),
            s("GraphQL", 0.2),
        ],
    ),
    role(
        "Mobile Engineer",
        "Mobile",
        ["Mobile Developer", "Mobile Software Engineer", "Cross-platform Mobile Developer"],
        [
            s("Kotlin", 0.7, "native"),
            s("Swift", 0.7, "native"),
            s("Flutter", 0.7, "xplat"),
            s("React Native", 0.7, "xplat"),
            s("Android", 0.5),
            s("iOS", 0.5),
            s("TypeScript", 0.3),
            s("CI/CD", 0.25),
        ],
    ),
    # ---- DevOps/Cloud ----
    role(
        "DevOps Engineer",
        "DevOps/Cloud",
        ["DevOps Developer", "DevOps Specialist", "DevOps SRE"],
        [
            s("Kubernetes", 1.0),
            s("CI/CD", 0.85),
            s("Terraform", 0.8),
            s("AWS", 0.7, "cloud"),
            s("GCP", 0.5, "cloud"),
            s("Azure", 0.5, "cloud"),
            s("Docker", 0.65),
            s("Helm", 0.4),
            s("Linux", 0.4),
            s("Python", 0.35),
            s("Ansible", 0.3),
            s("Prometheus", 0.25),
        ],
    ),
    role(
        "SRE",
        "DevOps/Cloud",
        ["Site Reliability Engineer", "Reliability Engineer", "Production Engineer"],
        [
            s("Kubernetes", 1.0),
            s("Prometheus", 0.75),
            s("Grafana", 0.65),
            s("Go", 0.5),
            s("AWS", 0.5),
            s("Terraform", 0.45),
            s("Python", 0.4),
            s("Datadog", 0.35),
            s("Linux", 0.35),
            s("Docker", 0.3),
        ],
    ),
    role(
        "Cloud Engineer",
        "DevOps/Cloud",
        [
            "Cloud Developer",
            "AWS Engineer",
            "Cloud Infrastructure Engineer",
            "GCP Engineer",
            "Azure Engineer",
        ],
        [
            s("AWS", 1.0, "cloud"),
            s("GCP", 0.7, "cloud"),
            s("Azure", 0.7, "cloud"),
            s("Terraform", 0.85),
            s("Kubernetes", 0.65),
            s("CI/CD", 0.45),
            s("Docker", 0.4),
            s("Python", 0.3),
            s("Linux", 0.3),
        ],
    ),
    role(
        "Platform Engineer",
        "DevOps/Cloud",
        [
            "Platform Developer",
            "Internal Platform Engineer",
            "Developer Platform Engineer",
        ],
        [
            s("Kubernetes", 1.0),
            s("Terraform", 0.75),
            s("CI/CD", 0.75),
            s("Go", 0.55),
            s("AWS", 0.5),
            s("Helm", 0.45),
            s("Docker", 0.4),
            s("GitHub Actions", 0.35),
            s("Python", 0.3),
        ],
    ),
    role(
        "System Administrator",
        "DevOps/Cloud",
        ["Sysadmin", "Systems Administrator", "Linux Administrator", "System Admin"],
        [
            s("Linux", 1.0),
            s("Bash", 0.7),
            s("Nginx", 0.5),
            s("Docker", 0.4),
            s("Ansible", 0.4),
            s("Python", 0.3),
            s("AWS", 0.3),
            s("MySQL", 0.25),
        ],
    ),
    role(
        "Network Engineer",
        "DevOps/Cloud",
        ["Network Administrator", "Network Specialist", "Infrastructure Network Engineer"],
        [
            s("Linux", 0.8),
            s("Bash", 0.5),
            s("Nginx", 0.45),
            s("AWS", 0.4),
            s("Python", 0.3),
            s("Terraform", 0.25),
            s("Docker", 0.2),
        ],
    ),
    # ---- Data/ML ----
    role(
        "Data Engineer",
        "Data/ML",
        ["ETL Engineer", "Data Platform Engineer", "Data Infrastructure Engineer"],
        [
            s("Python", 1.0),
            s("SQL", 0.9),
            s("Spark", 0.75),
            s("Airflow", 0.7),
            s("Kafka", 0.55),
            s("dbt", 0.5),
            s("AWS", 0.4),
            s("PostgreSQL", 0.35),
            s("Snowflake", 0.35),
            s("BigQuery", 0.3),
            s("Docker", 0.25),
        ],
    ),
    role(
        "Data Analyst",
        "Data/ML",
        ["Business Analyst Data", "BI Analyst", "Reporting Analyst", "Insights Analyst"],
        [
            s("SQL", 1.0),
            s("Python", 0.7),
            s("Pandas", 0.55),
            s("dbt", 0.4),
            s("BigQuery", 0.4),
            s("Snowflake", 0.3),
        ],
    ),
    role(
        "Analytics Engineer",
        "Data/ML",
        ["Analytics Engineering", "Data Analytics Engineer"],
        [
            s("SQL", 1.0),
            s("dbt", 0.9),
            s("Python", 0.6),
            s("Snowflake", 0.5),
            s("BigQuery", 0.5),
            s("Airflow", 0.35),
            s("Pandas", 0.3),
        ],
    ),
    role(
        "Database Administrator",
        "Data/ML",
        ["DBA", "PostgreSQL DBA", "Database Engineer", "SQL DBA"],
        [
            s("PostgreSQL", 1.0, "db"),
            s("MySQL", 0.8, "db"),
            s("SQL", 0.85),
            s("Linux", 0.45),
            s("Redis", 0.35),
            s("MongoDB", 0.3),
            s("Bash", 0.25),
            s("AWS", 0.25),
        ],
    ),
    role(
        "Data Scientist",
        "Data/ML",
        ["Applied Scientist", "Research Data Scientist", "Data Science Engineer"],
        [
            s("Python", 1.0),
            s("SQL", 0.75),
            s("scikit-learn", 0.7),
            s("Pandas", 0.6),
            s("PyTorch", 0.45),
            s("TensorFlow", 0.35),
            s("Spark", 0.3),
            s("LLM", 0.25),
        ],
    ),
    role(
        "ML Engineer",
        "Data/ML",
        [
            "Machine Learning Engineer",
            "AI Engineer",
            "Deep Learning Engineer",
            "Applied ML Engineer",
        ],
        [
            s("Python", 1.0),
            s("PyTorch", 0.85),
            s("TensorFlow", 0.55),
            s("LLM", 0.55),
            s("SQL", 0.35),
            s("Kubernetes", 0.35),
            s("Docker", 0.3),
            s("AWS", 0.3),
            s("scikit-learn", 0.3),
        ],
    ),
    role(
        "MLOps Engineer",
        "Data/ML",
        ["ML Platform Engineer", "ML Infrastructure Engineer", "AI Platform Engineer"],
        [
            s("Python", 0.9),
            s("Kubernetes", 0.85),
            s("AWS", 0.65),
            s("Docker", 0.55),
            s("CI/CD", 0.55),
            s("PyTorch", 0.45),
            s("Terraform", 0.45),
            s("Airflow", 0.35),
            s("GCP", 0.3),
        ],
    ),
    # ---- QA ----
    role(
        "QA Automation Engineer",
        "QA",
        [
            "Automation QA",
            "Test Automation Engineer",
            "QA Automation",
            "Automated Test Engineer",
        ],
        [
            s("Playwright", 0.9, "tool"),
            s("Selenium", 0.8, "tool"),
            s("Cypress", 0.75, "tool"),
            s("JavaScript", 0.55),
            s("TypeScript", 0.55),
            s("Python", 0.45),
            s("CI/CD", 0.45),
            s("Jest", 0.35),
            s("Jenkins", 0.3),
        ],
    ),
    role(
        "Manual QA",
        "QA",
        [
            "QA Tester",
            "Quality Assurance Tester",
            "Manual Tester",
            "QA Specialist",
            "Software Tester",
        ],
        [
            s("SQL", 0.55),
            s("JavaScript", 0.25),
            s("Playwright", 0.25),
            s("Selenium", 0.2),
            s("CI/CD", 0.15),
        ],
    ),
    role(
        "SDET",
        "QA",
        [
            "Software Development Engineer in Test",
            "Quality Engineer",
            "Test Engineer",
            "Software Test Engineer",
        ],
        [
            s("Playwright", 0.8, "tool"),
            s("Selenium", 0.7, "tool"),
            s("Java", 0.55, "lang"),
            s("Python", 0.55, "lang"),
            s("TypeScript", 0.45, "lang"),
            s("CI/CD", 0.55),
            s("Jenkins", 0.35),
            s("Docker", 0.3),
            s("SQL", 0.25),
        ],
    ),
    # ---- Security ----
    role(
        "AppSec Engineer",
        "Security",
        [
            "Application Security Engineer",
            "Product Security Engineer",
            "Penetration Tester",
            "Security Consultant AppSec",
        ],
        [
            s("Python", 0.75),
            s("Java", 0.5),
            s("AWS", 0.5),
            s("Kubernetes", 0.4),
            s("Go", 0.35),
            s("Docker", 0.35),
            s("Linux", 0.35),
            s("SQL", 0.25),
        ],
    ),
    role(
        "Security Engineer",
        "Security",
        [
            "Information Security Engineer",
            "Cybersecurity Engineer",
            "IT Security Engineer",
            "Cloud Security Engineer",
        ],
        [
            s("AWS", 0.75),
            s("Python", 0.65),
            s("Azure", 0.55),
            s("GCP", 0.45),
            s("Terraform", 0.45),
            s("Linux", 0.45),
            s("Kubernetes", 0.35),
            s("Bash", 0.3),
        ],
    ),
    role(
        "SOC Analyst",
        "Security",
        [
            "Security Operations Analyst",
            "Security Analyst",
            "SOC Engineer",
            "Cyber SOC Analyst",
        ],
        [
            s("Python", 0.55),
            s("Linux", 0.55),
            s("AWS", 0.4),
            s("Elasticsearch", 0.4),
            s("Bash", 0.35),
            s("Datadog", 0.25),
            s("SQL", 0.2),
        ],
    ),
    # ---- Design/UX ----
    role(
        "UI/UX Designer",
        "Design/UX",
        [
            "UX Designer",
            "UI Designer",
            "User Experience Designer",
            "Interaction Designer",
            "UX/UI Designer",
        ],
        [
            s("Figma", 1.0),
            s("HTML", 0.35),
            s("CSS", 0.35),
            s("JavaScript", 0.15),
        ],
    ),
    role(
        "Product Designer",
        "Design/UX",
        [
            "Senior Product Designer",
            "Digital Product Designer",
            "UX Product Designer",
        ],
        [
            s("Figma", 1.0),
            s("HTML", 0.25),
            s("CSS", 0.25),
            s("React", 0.2),
        ],
    ),
    # ---- Product ----
    role(
        "Product Manager",
        "Product",
        [
            "PM",
            "Digital Product Manager",
            "Technical Product Manager",
            "Associate Product Manager",
        ],
        [
            s("SQL", 0.6),
            s("Python", 0.25),
            s("LLM", 0.25),
            s("Figma", 0.15),
        ],
    ),
    role(
        "Product Owner",
        "Product",
        ["PO", "Technical Product Owner", "Agile Product Owner"],
        [
            s("SQL", 0.5),
            s("Python", 0.2),
            s("Figma", 0.15),
        ],
    ),
    role(
        "Project Manager",
        "Product",
        [
            "Technical Project Manager",
            "Delivery Manager",
            "Program Manager",
            "IT Project Manager",
        ],
        [
            s("SQL", 0.25),
            s("CI/CD", 0.25),
        ],
    ),
    role(
        "Scrum Master",
        "Product",
        ["Agile Coach", "Agile Scrum Master", "Delivery Scrum Master"],
        [
            s("CI/CD", 0.2),
            s("SQL", 0.15),
        ],
    ),
    # ---- IT Support ----
    role(
        "IT Support",
        "IT Support",
        [
            "Helpdesk",
            "Help Desk",
            "Desktop Support",
            "Service Desk",
            "IT Support Specialist",
            "IT Technician",
        ],
        [
            s("Linux", 0.7),
            s("Bash", 0.4),
            s("AWS", 0.25),
            s("SQL", 0.25),
        ],
    ),
    role(
        "Support Engineer",
        "IT Support",
        [
            "Technical Support Engineer",
            "Customer Support Engineer",
            "Product Support Engineer",
            "L2 Support Engineer",
        ],
        [
            s("Linux", 0.7),
            s("SQL", 0.55),
            s("Python", 0.45),
            s("AWS", 0.45),
            s("Bash", 0.35),
            s("Docker", 0.25),
            s("Kubernetes", 0.15),
        ],
    ),
    # ---- Other tech ----
    role(
        "Solutions Architect",
        "Other tech",
        [
            "Solution Architect",
            "Cloud Solutions Architect",
            "Systems Architect",
            "Enterprise Solutions Architect",
        ],
        [
            s("AWS", 0.9, "cloud"),
            s("Azure", 0.6, "cloud"),
            s("GCP", 0.6, "cloud"),
            s("Kubernetes", 0.55),
            s("Terraform", 0.5),
            s("Docker", 0.35),
            s("Java", 0.3, "lang"),
            s("Python", 0.3, "lang"),
            s("SQL", 0.25),
        ],
    ),
    role(
        "Blockchain Developer",
        "Other tech",
        [
            "Web3 Developer",
            "Smart Contract Developer",
            "Solidity Developer",
            "Crypto Developer",
        ],
        [
            s("Solidity", 1.0),
            s("Ethereum", 0.85),
            s("JavaScript", 0.5),
            s("TypeScript", 0.45),
            s("Node.js", 0.35),
            s("Go", 0.25),
            s("Rust", 0.25),
        ],
    ),
    role(
        "Game Developer",
        "Other tech",
        [
            "Unity Developer",
            "Unreal Developer",
            "Game Engineer",
            "Gameplay Programmer",
        ],
        [
            s("Unity", 0.95, "engine"),
            s("Unreal Engine", 0.95, "engine"),
            s("C++", 0.55),
            s("C#", 0.5),
            s("Python", 0.2),
        ],
    ),
    role(
        "WordPress Developer",
        "Other tech",
        ["WP Developer", "WordPress Engineer", "CMS WordPress Developer"],
        [
            s("WordPress", 1.0),
            s("PHP", 0.85),
            s("JavaScript", 0.5),
            s("CSS", 0.45),
            s("HTML", 0.4),
            s("MySQL", 0.4),
            s("SQL", 0.3),
        ],
    ),
    role(
        "Shopify Developer",
        "Other tech",
        ["Shopify Engineer", "Shopify Theme Developer", "Ecommerce Shopify Developer"],
        [
            s("Shopify", 1.0),
            s("JavaScript", 0.65),
            s("CSS", 0.45),
            s("HTML", 0.4),
            s("Node.js", 0.3),
            s("PHP", 0.2),
        ],
    ),
    role(
        "Embedded Engineer",
        "Other tech",
        [
            "Embedded Developer",
            "Firmware Engineer",
            "Embedded Systems Engineer",
            "IoT Embedded Engineer",
        ],
        [
            s("C", 1.0),
            s("C++", 0.85),
            s("Python", 0.35),
            s("Linux", 0.45),
            s("Bash", 0.25),
        ],
    ),
]


def main() -> None:
    cleaned = []
    names = set()
    for r in ROLES:
        skills = [x for x in r["signature_skills"] if float(x.get("weight") or 0) > 0]
        if not skills:
            raise SystemExit(f"no skills: {r['canonical_name']}")
        if r["canonical_name"] in names:
            raise SystemExit(f"duplicate role: {r['canonical_name']}")
        names.add(r["canonical_name"])
        cleaned.append({**r, "signature_skills": skills})

    payload = {
        "version": "1.2",
        "generated_at": "2026-10-05T12:00:00Z",
        "source": {
            "plan": "docs/ingress-job-cv-ai-plan.pdf §6.1",
            "categories": "worker/worker/techstack.py CATEGORIES",
            "skill_dictionary": "docs/cv-ai/skill-dictionary-v1.json",
            "note": (
                "v1.2: broader role coverage + denser signature skills/synonyms. "
                "Optional signature group = OR (max weight). Hand-weighted; later TF refresh from ads."
            ),
        },
        "roles": cleaned,
        "notes": [
            "Seed for role_taxonomy + role_skill_weight (Phase 0.3).",
            "Signature skill names must match skill_dictionary.canonical_name; unknown skills are skipped at seed.",
            "Optional signature field group: same group_key = OR (max weight); empty group = required AND.",
            "Soft-skill roles (Product, Design, Manual QA) stay lighter on tech weights; scorers dampen thin roles.",
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    OUT_DOCS.write_text(text, encoding="utf-8")
    OUT_WORKER.write_text(text, encoding="utf-8")
    print(f"wrote {len(cleaned)} roles -> {OUT_DOCS.relative_to(ROOT)} and worker copy")


if __name__ == "__main__":
    main()
