"""Job categories: one table (job_categories), shared by worker, API and admin.

The worker's classify_category() reads the active rules from this table
(cached per process; reload_rules() refreshes it). When the table is missing
or empty the built-in SEED is used, so classification never breaks.

Columns
  slug            stable key stored in jobs.category (never renamed)
  name_az/en/ru   labels shown on the site
  sort_order      display order in filters
  priority        tie-break when two title rules match at the same position
                  (lower wins); also the order source categories are tried in
  stack_rank      tie-break for the tech-stack fallback (lower wins)
  active          0 = hidden; its jobs fall to "Other tech" on recategorise
  title_pattern   regex (case-insensitive) matched against title and the
                  source's own category
  aliases         JSON list of extra source-category values (exact, lowercased)
  stack_names     JSON list of curated tech names for the stack fallback
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime

OTHER = "Other tech"

TABLE = """
CREATE TABLE IF NOT EXISTS job_categories (
    slug TEXT PRIMARY KEY,
    name_az TEXT NOT NULL DEFAULT '',
    name_en TEXT NOT NULL DEFAULT '',
    name_ru TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 100,
    priority INTEGER NOT NULL DEFAULT 100,
    stack_rank INTEGER NOT NULL DEFAULT 100,
    active INTEGER NOT NULL DEFAULT 1,
    title_pattern TEXT NOT NULL DEFAULT '',
    aliases TEXT NOT NULL DEFAULT '[]',
    stack_names TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT ''
)
"""


def _c(slug, az, en, ru, sort, priority, stack_rank, pattern, stack=(), aliases=()):
    return {
        "slug": slug, "name_az": az, "name_en": en, "name_ru": ru,
        "sort_order": sort, "priority": priority, "stack_rank": stack_rank, "active": 1,
        "title_pattern": pattern, "aliases": list(aliases), "stack_names": list(stack),
    }


# The original 12 (identical rules to the pre-table code).
BASE_SEED = [
    _c("Backend", "Backend", "Backend", "Backend", 10, 70, 3,
       r"back ?end|server side|\bapi\b|python|\bjava\b|\bphp\b|ruby|golang|"
       r"\bgo (?:developer|engineer)|\.net|dotnet|c#|node|scala|\brust\b|elixir|"
       r"erlang|c\+\+|django|spring|laravel|rails|microservice",
       ["Python", "Java", "Scala", "Go", "Rust", "PHP", "Ruby", "C#", ".NET", "Elixir",
        "Erlang", "Node.js", "NestJS", "Express", "Django", "Flask", "FastAPI", "Spring",
        "Ruby on Rails", "Laravel", "Symfony", "Phoenix", "Kotlin", "Fastify", "Quarkus",
        "Micronaut", "Ktor", "Blazor"]),
    _c("Frontend", "Frontend", "Frontend", "Frontend", 20, 60, 2,
       r"front ?end|\bui (?:engineer|developer)|web develop|javascript|typescript|"
       r"react(?! native)|\bvue|angular|svelte|next\.? ?js",
       ["React", "Next.js", "Vue.js", "Nuxt", "Angular", "Svelte", "Redux", "Tailwind",
        "jQuery", "Bootstrap", "Vite", "Webpack", "Remix", "Astro", "Gatsby", "Ember",
        "Material UI", "Storybook"]),
    _c("Full-stack", "Full-stack", "Full-stack", "Full-stack", 30, 0, 100, r"full ?stack"),
    _c("Mobile", "Mobil", "Mobile", "Мобильная разработка", 40, 30, 1,
       r"mobile(?! traffic)|\bios\b|android|flutter|react native|\bswift\b|xamarin",
       ["React Native", "Flutter", "iOS", "Android", "Swift", "Objective-C", "Dart",
        "Jetpack Compose", "Xamarin", "Ionic", "Capacitor"]),
    _c("DevOps/Cloud", "DevOps / Bulud", "DevOps / Cloud", "DevOps / Облако", 50, 50, 5,
       r"devops|\bsre\b|site reliability|infrastructure|platform|cloud|"
       r"sys ?admin|system(?:s)? admin\w*|kubernetes|network (?:engineer|admin\w*)|"
       r"release engineer|build engineer|\bops\b",
       ["Kubernetes", "Terraform", "Ansible", "Helm", "Jenkins", "Prometheus", "Grafana",
        "Argo CD", "GitHub Actions", "GitLab CI", "Pulumi", "Istio", "OpenShift"]),
    _c("Data/ML", "Data / ML", "Data / ML", "Data / ML", 60, 40, 4,
       r"\bdata\b|machine learning|\bml\b|mlops|\bai\b|artificial intelligence|"
       r"\bllms?\b|\bnlp\b|computer vision|deep learning|analytics|\bbi\b|"
       r"business intelligence|\betl\b|database|\bdba\b|scientist|data science",
       ["Spark", "Airflow", "dbt", "Snowflake", "BigQuery", "Databricks", "Pandas",
        "PyTorch", "TensorFlow", "scikit-learn", "LLM", "Keras", "Hugging Face",
        "LangChain", "MLflow", "NLP", "Tableau", "Power BI"]),
    _c("QA", "QA / Test", "QA / Testing", "QA / Тестирование", 70, 10, 6,
       r"\bqa\b|quality assurance|\bsdet\b|\btest(?:er|ers|ing)?\b|"
       r"software quality|quality engineer|automation (?:qa|test)",
       ["Selenium", "Cypress", "Playwright", "pytest", "JUnit", "Postman", "Appium"]),
    _c("Security", "Təhlükəsizlik", "Security", "Безопасность", 80, 20, 100,
       r"secur|seguridad|cyber|pen ?test|penetration|infosec|\bsoc\b|appsec"),
    _c("Design/UX", "Dizayn / UX", "Design / UX", "Дизайн / UX", 90, 80, 7,
       r"\bux\b|\bui\b|user experience|user interface|product design|"
       r"interaction design|visual design|web design|design system|designer|"
       r"\bdesign\b(?! engineer)",
       ["Figma"]),
    _c("Product", "Məhsul / Layihə", "Product / Project", "Продукт / Проект", 100, 90, 100,
       r"^products?$|product (?:manag|owner|lead|director|analyst|ops|strateg)|"
       r"head of product|vp product|chief product|project manag|program manag|"
       r"scrum|agile coach|delivery manag|technical project"),
    _c("IT Support", "IT dəstək", "IT support", "IT-поддержка", 110, 100, 100,
       r"it support|technical support|tech support|help ?desk|service desk|"
       r"desktop support|it (?:technician|specialist|administrator|admin)|"
       r"support engineer"),
    _c(OTHER, "Digər IT", "Other tech", "Другое IT", 1000, 1000, 1000, ""),
]

# Added 2026-10-13. Lower priority numbers than the broad base rules, so at the
# same match position the specific category wins ("Data Engineer" → Data
# Engineering, not Data/ML). Their stack groups rank after the base groups, so
# the stack fallback only picks them when they clearly outnumber the others.
# Cloud Architecture, Network Engineering and Technical Writing were tried and
# had no visible jobs in the local database (2026-10-13); staff can add them.
EXTRA_SEED: list[dict] = [
    _c("Engineering Management", "Mühəndislik rəhbərliyi", "Engineering management",
       "Руководство разработкой", 105, 1, 100,
       r"engineering manager|head of (?:engineering|development|software)|director of engineering|"
       r"engineering director|vp,? (?:of )?engineering|\bcto\b|chief technology officer|"
       r"development manager|software development manager"),
    _c("Embedded/IoT", "Embedded / IoT", "Embedded / IoT", "Embedded / IoT", 45, 2, 20,
       r"embedded|firmware|\biot\b|\bfpga\b|\brtos\b|microcontroller|hardware engineer|"
       r"flight software|\badas\b|\becu\b|autosar|device driver|\bbsp\b|robotics software",
       ["Arduino", "STM32", "RTOS", "Embedded Linux", "MQTT", "Verilog", "VHDL"]),
    _c("Game Development", "Oyun hazırlanması", "Game development", "Разработка игр", 47, 3, 21,
       r"\bgames?\b|gameplay|unity (?:developer|engineer)|unreal",
       ["Unity", "Unreal Engine", "Godot"]),
    _c("Blockchain/Web3", "Blokçeyn / Web3", "Blockchain / Web3", "Блокчейн / Web3", 48, 4, 22,
       r"blockchain|web ?3|solidity|smart contract|crypto(?!graph)|\bdefi\b|\bnfts?\b|ethereum|solana",
       ["Solidity", "Ethereum", "Web3.js", "Solana", "Hardhat"]),
    _c("AI/LLM", "Süni intellekt / LLM", "AI / LLM engineering", "ИИ / LLM", 62, 5, 23,
       r"\bllms?\b|generative ai|gen ?ai|\bai (?:engineer|developer|researcher|architect|"
       r"specialist|lead|agents?|platform|product engineer)|applied ai|prompt engineer|"
       r"ai/ml engineer|\bagentic\b|\brag\b",
       ["LLM", "LangChain", "OpenAI", "LlamaIndex", "RAG", "Hugging Face"]),
    _c("Data Engineering", "Data mühəndisliyi", "Data engineering", "Data-инжиниринг", 64, 6, 24,
       r"data engineer|data platform|\betl\b|data pipeline|analytics engineer|big data|"
       r"data warehouse|database (?:engineer|developer|administrator)|\bdba\b",
       ["Airflow", "dbt", "Spark", "Snowflake", "Databricks", "Kafka"]),
    _c("Data Analytics/BI", "Data analitika / BI", "Data analytics / BI", "Аналитика данных / BI",
       66, 7, 25,
       r"data analyst|\bbi\b|business intelligence|analytics(?! engineer)|power bi|tableau|"
       r"looker|reporting analyst|insights analyst",
       ["Tableau", "Power BI", "Looker", "Metabase", "Qlik"]),
    _c("SRE/Platform", "SRE / Platforma", "SRE / Platform", "SRE / Платформа", 52, 8, 100,
       r"\bsre\b|site reliability|reliability engineer|platform (?:engineer|developer|lead|"
       r"architect|team)"),
    _c("System Administration", "Sistem administrasiyası", "System administration",
       "Системное администрирование", 58, 12, 100,
       r"sys ?admin|system(?:s)? admin\w*|(?:linux|windows|unix) (?:admin\w*|engineer)|"
       r"администратор|адміністратор"),
    _c("ERP/CRM", "ERP / CRM", "ERP / CRM", "ERP / CRM", 85, 13, 26,
       r"\bsap\b|salesforce|dynamics 365|\bd365\b|\bodoo\b|\berp\b|\bcrm\b|servicenow|\b1c\b|"
       r"netsuite|oracle (?:ebs|fusion|apps)|workday",
       ["SAP", "Salesforce", "Apex", "Odoo", "ServiceNow"]),
    _c("Solutions Engineering", "Solutions / Pre-sales", "Solutions / Pre-sales",
       "Solutions / Pre-sales", 107, 15, 100,
       r"solutions? (?:engineer|architect|consultant)|pre-?sales|sales engineer|customer engineer|"
       r"forward deployed|implementation engineer|integration engineer|technical account manager|"
       r"customer success engineer"),
]

SEED = BASE_SEED + EXTRA_SEED


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value]
    try:
        loaded = json.loads(str(value or "[]"))
    except (TypeError, ValueError):
        return []
    return [str(x) for x in loaded] if isinstance(loaded, list) else []


def ensure_categories(conn, seed: list[dict] | None = None) -> int:
    """Create the table and insert missing seed rows (existing rows untouched).
    Returns rows inserted. The caller commits."""
    conn.execute(TABLE)
    have = {str(row[0]) for row in conn.execute("SELECT slug FROM job_categories").fetchall()}
    added = 0
    for item in seed if seed is not None else SEED:
        if item["slug"] in have:
            continue
        conn.execute(
            """
            INSERT INTO job_categories (slug, name_az, name_en, name_ru, sort_order, priority,
                stack_rank, active, title_pattern, aliases, stack_names, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (slug) DO NOTHING
            """,
            (
                item["slug"], item["name_az"], item["name_en"], item["name_ru"],
                int(item["sort_order"]), int(item["priority"]), int(item["stack_rank"]),
                int(item.get("active", 1)), item["title_pattern"],
                json.dumps(item.get("aliases") or [], ensure_ascii=False),
                json.dumps(item.get("stack_names") or [], ensure_ascii=False),
                _now(),
            ),
        )
        added += 1
    return added


def row_dict(row) -> dict:
    return {
        "slug": str(row["slug"]),
        "name_az": str(row["name_az"] or ""),
        "name_en": str(row["name_en"] or ""),
        "name_ru": str(row["name_ru"] or ""),
        "sort_order": int(row["sort_order"] or 0),
        "priority": int(row["priority"] or 0),
        "stack_rank": int(row["stack_rank"] or 0),
        "active": bool(int(row["active"] or 0)),
        "title_pattern": str(row["title_pattern"] or ""),
        "aliases": _json_list(row["aliases"]),
        "stack_names": _json_list(row["stack_names"]),
    }


def read_categories(conn, *, active_only: bool = False) -> list[dict]:
    """All rows (or active only) by sort_order. [] when the table is missing."""
    try:
        rows = conn.execute(
            "SELECT * FROM job_categories ORDER BY sort_order, slug"
        ).fetchall()
    except Exception:  # noqa: BLE001 - missing table on an old database
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return []
    items = [row_dict(row) for row in rows]
    return [i for i in items if i["active"]] if active_only else items


class Rules:
    """Compiled, immutable snapshot of the active categories."""

    def __init__(self, items: list[dict]) -> None:
        active = [dict(i) for i in items if i.get("active", 1)]
        if not any(i["slug"] == OTHER for i in active):
            active.append(next(dict(i) for i in BASE_SEED if i["slug"] == OTHER))
        self.items = sorted(active, key=lambda i: (int(i["sort_order"]), i["slug"]))
        self.slugs = tuple(i["slug"] for i in self.items)
        self.active = frozenset(self.slugs)
        by_priority = sorted(active, key=lambda i: (int(i["priority"]), i["slug"]))
        self.title_rules: list[tuple[str, re.Pattern[str]]] = []
        for item in by_priority:
            pattern = str(item.get("title_pattern") or "").strip()
            if not pattern or item["slug"] == OTHER:
                continue
            try:
                self.title_rules.append((item["slug"], re.compile(pattern)))
            except re.error:
                continue
        self.priority = {slug: n for n, (slug, _p) in enumerate(self.title_rules)}
        self.aliases = {
            alias.strip().lower(): item["slug"]
            for item in by_priority
            for alias in item.get("aliases") or []
            if alias.strip()
        }
        by_stack = sorted(active, key=lambda i: (int(i["stack_rank"]), i["slug"]))
        self.stack_groups: dict[str, frozenset[str]] = {
            item["slug"]: frozenset(item.get("stack_names") or [])
            for item in by_stack
            if item.get("stack_names") and item["slug"] != OTHER
        }


_LOCK = threading.Lock()
_RULES: Rules | None = None


def rules() -> Rules:
    global _RULES
    current = _RULES
    if current is None:
        with _LOCK:
            if _RULES is None:
                _RULES = Rules(SEED)
            current = _RULES
    return current


def set_rules(items: list[dict] | None) -> Rules:
    """Install rules from table rows; empty/None → built-in SEED."""
    global _RULES
    compiled = Rules(items if items else SEED)
    with _LOCK:
        _RULES = compiled
    return compiled


def reload_rules(conn) -> Rules:
    return set_rules(read_categories(conn))


def validate_pattern(pattern: str) -> str:
    """'' when the regex compiles, else the error text."""
    try:
        re.compile(pattern or "")
    except re.error as exc:
        return str(exc)
    return ""


RECATEGORISE_STEP = "recategorise-extra-categories-2026-10-13"


def recategorise(conn, current: Rules | None = None, *, only: str | None = None) -> dict:
    """Re-run classification on collected rows with `current` rules.

    Only jobs.category is written (status, hidden, updated_at untouched).
    The source board's category is not stored, so a row is changed only when
    the current rules answer differently from the built-in 12 rules for the
    same title/stack (the change comes from a category edit), or when its
    stored category is inactive or not one of the built-in 12. The caller
    commits.
    """
    from worker.techstack import classify_category

    current = current or rules()
    base = Rules(BASE_SEED)
    base_slugs = set(base.slugs)
    sql = """
        SELECT id, title, COALESCE(tech_stack, '') AS tech_stack, COALESCE(category, '') AS category
        FROM jobs WHERE COALESCE(owner_subject, '') = '' AND COALESCE(category, '') NOT IN ('', '-')
    """
    params: list = []
    if only:
        sql += " AND category = ?"
        params.append(only)
    scanned = changed = 0
    moves: dict[str, int] = {}
    for row in conn.execute(sql, params).fetchall():
        scanned += 1
        try:
            stack = json.loads(row["tech_stack"] or "[]")
        except (TypeError, ValueError):
            stack = []
        stack = [str(x) for x in stack] if isinstance(stack, list) else []
        title = str(row["title"] or "")
        stored = str(row["category"])
        new = classify_category("", title, stack, rules=current)
        if stored not in current.active or stored not in base_slugs:
            target = new
        else:
            target = new if new != classify_category("", title, stack, rules=base) else stored
        if target != stored:
            conn.execute("UPDATE jobs SET category = ? WHERE id = ?", (target, row["id"]))
            changed += 1
            key = f"{stored} -> {target}"
            moves[key] = moves.get(key, 0) + 1
    return {"scanned": scanned, "changed": changed, "moves": moves}


def recategorise_once(conn) -> int:
    """One-shot recategorise after the extra categories were seeded."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS maintenance_steps (name TEXT PRIMARY KEY, done_at TEXT NOT NULL)"
    )
    if conn.execute(
        "SELECT 1 FROM maintenance_steps WHERE name = ?", (RECATEGORISE_STEP,)
    ).fetchone():
        return 0
    result = recategorise(conn)
    conn.execute(
        "INSERT INTO maintenance_steps (name, done_at) VALUES (?, ?) ON CONFLICT (name) DO NOTHING",
        (RECATEGORISE_STEP, _now()),
    )
    return int(result["changed"])
