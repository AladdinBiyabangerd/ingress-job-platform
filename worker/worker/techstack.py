"""Tech job filter, tech stack chips, and remote / relocation flags.

Everything here is a local keyword match. No site is fetched.

- ``is_tech_job`` keeps software, data, DevOps, QA, security, IT and
  product/design roles in tech. Sales, marketing, support, HR and similar
  roles are dropped unless the title is clearly an engineering role.
- ``extract_stack`` maps source tags (when an API gives them) and then the
  ad text onto a curated list of languages, frameworks, clouds, databases
  and tools. Unknown tags are ignored so the chips stay consistent.
- ``remote_flag`` / ``relocation_flag`` read the title, location and text.
  A negation right before a phrase ("no visa sponsorship") cancels it.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

MAX_STACK = 12

_L = r"(?<![A-Za-z0-9_+#.\-])"
_R = r"(?![A-Za-z0-9_+#])"


def _ci(body: str) -> re.Pattern[str]:
    return re.compile(_L + "(?:" + body + ")" + _R, re.IGNORECASE)


def _cs(body: str) -> re.Pattern[str]:
    return re.compile(_L + "(?:" + body + ")" + _R)


# canonical name -> (pattern for free text, extra lowercase tag aliases)
_TECH: list[tuple[str, re.Pattern[str], tuple[str, ...]]] = [
    # languages
    ("Python", _ci(r"python[23]?|pyspark"), ("py",)),
    ("Java", re.compile(_L + r"Java" + r"(?![A-Za-z0-9_+#]|\s*Script)"), ("java",)),
    ("Kotlin", _ci(r"kotlin"), ()),
    ("Scala", _cs(r"Scala"), ("scala",)),
    ("Go", re.compile(r"(?i:golang)|" + _L + r"Go(?=\s*(?:,|/|\)|\(|;|\s+(?:developer|engineer|backend|services|microservices|programming|language|or|and|&)\b))"), ("go", "golang")),
    ("Rust", _cs(r"Rust"), ("rust",)),
    ("TypeScript", _ci(r"typescript"), ("ts",)),
    ("JavaScript", _ci(r"javascript|ecmascript|es6"), ("js",)),
    ("PHP", _ci(r"php[5-8]?"), ()),
    ("Ruby", _ci(r"ruby(?!\s+on\s+rails)"), ()),
    ("C#", re.compile(_L + r"C#|(?i:csharp)"), ("c#", "csharp")),
    ("C++", re.compile(_L + r"C\+\+|(?i:cpp)" + _R), ("c++", "cpp")),
    ("C", re.compile(r"(?<![A-Za-z0-9_+#.\-/])C(?=\s*(?:/C\+\+|,\s*C\+\+|\s+and\s+C\+\+)|\s+programming\b)"), ("c",)),
    (".NET", re.compile(r"(?<![A-Za-z0-9_])(?:ASP)?\.NET(?:\s?Core)?\b|(?i:dotnet)" + _R), (".net", "dotnet", "asp.net", ".net core")),
    ("Swift", _cs(r"Swift|SwiftUI"), ("swift", "swiftui")),
    ("Objective-C", _ci(r"objective-c|obj-c"), ()),
    ("Dart", _cs(r"Dart"), ("dart",)),
    ("Elixir", _ci(r"elixir"), ()),
    ("Erlang", _ci(r"erlang"), ()),
    ("Haskell", _ci(r"haskell"), ()),
    ("Clojure", _ci(r"clojure(?:script)?"), ()),
    ("Solidity", _ci(r"solidity"), ()),
    ("SQL", _cs(r"SQL|T-SQL|PL/SQL"), ("sql",)),
    ("Bash", _cs(r"Bash|Shell scripting"), ("bash", "shell")),
    # front end / mobile
    ("React", re.compile(_L + r"React(?:\.?js|JS)?(?!\s*Native)" + _R + r"|(?i:reactjs|react\.js)"), ("react", "reactjs", "react.js")),
    ("React Native", _ci(r"react[\s-]native"), ()),
    ("Next.js", _ci(r"next\.?js"), ("nextjs", "next")),
    ("Vue.js", re.compile(_L + r"Vue(?:\.?js|JS)?" + _R + r"|(?i:vuejs|vue\.js)"), ("vue", "vuejs", "vue.js")),
    ("Nuxt", _ci(r"nuxt(?:\.?js)?"), ()),
    ("Angular", _cs(r"Angular(?:JS)?"), ("angular", "angularjs")),
    ("Svelte", _ci(r"svelte(?:kit)?"), ()),
    ("Redux", _cs(r"Redux"), ("redux",)),
    ("Tailwind", _ci(r"tailwind(?:\s?css)?"), ()),
    ("HTML", _cs(r"HTML5?"), ("html", "html5")),
    ("CSS", _cs(r"CSS3?|SCSS|Sass"), ("css", "css3", "scss", "sass")),
    ("Flutter", _ci(r"flutter"), ()),
    ("iOS", _cs(r"iOS"), ("ios",)),
    ("Android", _cs(r"Android"), ("android",)),
    # back end frameworks
    ("Node.js", _ci(r"node\.?js|node\s+js"), ("node", "nodejs", "node.js")),
    ("NestJS", _ci(r"nest\.?js"), ()),
    ("Express", re.compile(_L + r"Express(?:\.js|JS)" + _R + r"|(?i:expressjs)"), ("express", "expressjs")),
    ("Django", _ci(r"django"), ()),
    ("Flask", _cs(r"Flask"), ("flask",)),
    ("FastAPI", _ci(r"fastapi"), ()),
    ("Spring", re.compile(_L + r"Spring(?:\s?Boot|\s(?:Framework|Cloud|MVC|Data|Security))" + _R + r"|(?i:springboot)"), ("spring", "spring boot", "springboot")),
    ("Ruby on Rails", _ci(r"ruby\s+on\s+rails|rails|ror"), ("rails", "ror", "ruby on rails")),
    ("Laravel", _ci(r"laravel"), ()),
    ("Symfony", _ci(r"symfony"), ()),
    ("Phoenix", re.compile(_L + r"Phoenix(?=\s*(?:framework|LiveView|/|,\s*(?:Elixir|Ecto)))"), ("phoenix",)),
    ("GraphQL", _ci(r"graphql"), ()),
    ("gRPC", _ci(r"grpc"), ()),
    ("WordPress", _ci(r"wordpress"), ()),
    ("Shopify", _cs(r"Shopify"), ("shopify",)),
    # cloud / infra
    ("AWS", _ci(r"aws|amazon\s+web\s+services"), ()),
    ("GCP", re.compile(_L + r"GCP" + _R + r"|(?i:google\s+cloud(?:\s+platform)?)"), ("gcp", "google cloud")),
    ("Azure", _cs(r"Azure"), ("azure",)),
    ("Kubernetes", _ci(r"kubernetes|k8s|eks|gke|aks"), ()),
    ("Docker", _ci(r"docker"), ()),
    ("Terraform", _ci(r"terraform"), ()),
    ("Ansible", _ci(r"ansible"), ()),
    ("Helm", _cs(r"Helm"), ("helm",)),
    ("Linux", _ci(r"linux"), ()),
    ("CI/CD", _ci(r"ci/cd|ci\s?&\s?cd|continuous\s+integration"), ("ci/cd", "cicd")),
    ("Jenkins", _ci(r"jenkins"), ()),
    ("GitHub Actions", _ci(r"github\s+actions"), ()),
    ("Prometheus", _cs(r"Prometheus"), ("prometheus",)),
    ("Grafana", _ci(r"grafana"), ()),
    ("Datadog", _ci(r"datadog"), ()),
    ("Nginx", _ci(r"nginx"), ()),
    # data
    ("PostgreSQL", _ci(r"postgres(?:ql)?|psql"), ("postgres", "postgresql")),
    ("MySQL", _ci(r"mysql|mariadb"), ()),
    ("MongoDB", _ci(r"mongo(?:db)?"), ()),
    ("Redis", _ci(r"redis"), ()),
    ("Elasticsearch", _ci(r"elastic\s?search|opensearch"), ()),
    ("DynamoDB", _ci(r"dynamodb"), ()),
    ("Cassandra", _cs(r"Cassandra"), ("cassandra",)),
    ("ClickHouse", _ci(r"clickhouse"), ()),
    ("Kafka", _ci(r"kafka"), ()),
    ("RabbitMQ", _ci(r"rabbitmq"), ()),
    ("Spark", re.compile(_L + r"(?:Apache\s+)?Spark" + _R + r"|(?i:pyspark)"), ("spark", "apache spark")),
    ("Airflow", _ci(r"airflow"), ()),
    ("dbt", _cs(r"dbt"), ("dbt",)),
    ("Snowflake", _cs(r"Snowflake"), ("snowflake",)),
    ("BigQuery", _ci(r"bigquery"), ()),
    ("Databricks", _ci(r"databricks"), ()),
    ("Pandas", _cs(r"[Pp]andas"), ("pandas",)),
    # ML / AI
    ("PyTorch", _ci(r"pytorch"), ()),
    ("TensorFlow", _ci(r"tensorflow"), ()),
    ("scikit-learn", _ci(r"scikit-learn|sklearn"), ()),
    ("LLM", _cs(r"LLMs?"), ("llm", "llms")),
    # QA / design / web3
    ("Selenium", _ci(r"selenium"), ()),
    ("Cypress", _cs(r"Cypress"), ("cypress",)),
    ("Playwright", _ci(r"playwright"), ()),
    ("Jest", _cs(r"Jest"), ("jest",)),
    ("Figma", _ci(r"figma"), ()),
    ("Unity", _cs(r"Unity(?:3D)?"), ("unity", "unity3d")),
    ("Unreal Engine", _ci(r"unreal(?:\s+engine)?"), ()),
    ("Ethereum", _ci(r"ethereum|evm"), ()),
]

_ALIASES: dict[str, str] = {}
for _name, _pattern, _extra in _TECH:
    _ALIASES[_name.lower()] = _name
    for _alias in _extra:
        _ALIASES[_alias] = _name

TECH_NAMES = [name for name, _p, _e in _TECH]


def _split_tags(tags: object) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        raw = tags.strip()
        if raw.startswith("["):
            try:
                return _split_tags(json.loads(raw))
            except json.JSONDecodeError:
                pass
        return [part.strip() for part in re.split(r"[,;|]", raw) if part.strip()]
    if isinstance(tags, dict):
        return _split_tags(tags.get("name") or tags.get("label") or tags.get("value") or "")
    if isinstance(tags, Iterable):
        out: list[str] = []
        for item in tags:
            out.extend(_split_tags(item))
        return out
    return []


def _tag_name(tag: str) -> str | None:
    key = re.sub(r"\s+", " ", tag.strip().lower())
    if not key or len(key) > 40:
        return None
    if key in _ALIASES:
        return _ALIASES[key]
    for name, pattern, _extra in _TECH:
        found = re.compile(pattern.pattern, re.IGNORECASE).fullmatch(tag.strip())
        if found and name not in {"Go", "C", "SQL"}:
            return name
    return None


def extract_stack(text: str, tags: object = None, title: str = "") -> list[str]:
    """Curated tech names: tags first, then by how often the text names them."""
    found: list[str] = []
    for tag in _split_tags(tags):
        name = _tag_name(tag)
        if name and name not in found:
            found.append(name)
    sample = f"{title}\n{text or ''}"[:30000]
    scored: list[tuple[int, int, str]] = []
    for name, pattern, _extra in _TECH:
        if name in found:
            continue
        hits = list(pattern.finditer(sample))
        if hits:
            in_title = 1 if title and pattern.search(title) else 0
            scored.append((-(len(hits) + 5 * in_title), hits[0].start(), name))
    scored.sort()
    for _score, _pos, name in scored:
        if name not in found:
            found.append(name)
    # A JavaScript chip next to TypeScript or a framework adds little.
    return found[:MAX_STACK]


def dump_stack(stack: list[str]) -> str:
    return json.dumps(stack, ensure_ascii=False)


# ---- tech job filter -------------------------------------------------------

_TECH_TITLE = re.compile(
    r"engineer|engineering|developer|software development|programmer|software|coder\b|"
    r"devops|devsecops|mlops|\bsre\b|site reliability|sysadmin|system(?:s)? admin|"
    r"\bdba\b|database|data\s+(?:scien|analy|engineer|architect|platform|lead|manager)|"
    r"analytics engineer|\bbi\b|business intelligence|\betl\b|"
    r"machine learning|\bml\b|\bai\b|\bllm|\bnlp\b|computer vision|deep learning|"
    r"back[\s-]?end|front[\s-]?end|full[\s-]?stack|web\s?dev|mobile|\bios\b|android|"
    r"\bqa\b|quality assurance|\bsdet\b|\btest(?:er|ing)?\b|automation|"
    r"security|cyber|penetration|pentest|infosec|soc analyst|"
    r"\bcloud\b|platform|infrastructure|network(?:ing)? (?:engineer|admin)|"
    r"architect|tech(?:nical)? lead|\bcto\b|head of (?:engineering|technology|data|product)|"
    r"engineering manager|\bux\b|\bui\b|ui/ux|ux/ui|product design|interaction design|"
    r"web design|visual design|design engineer|design system|"
    r"product manager|product owner|technical product|technical project|it project|"
    r"scrum master|agile coach|\bit\b|helpdesk|help desk|technical support engineer|"
    r"blockchain|smart contract|web3|solidity|game (?:dev|programmer)|gameplay|"
    r"embedded|firmware|robotics|technical writer|developer (?:advocate|relations)|devrel|"
    r"python|java\b|javascript|typescript|golang|\bgo\b(?![\s-]+to\b)|ruby|\bphp\b|rust\b|elixir|"
    r"node|react|vue|angular|\.net|c\+\+|c#|kotlin|swift|flutter|django|laravel|rails|"
    r"kubernetes|\baws\b|salesforce developer|odoo",
    re.IGNORECASE,
)

_STRONG_TITLE = re.compile(
    r"engineer|developer|programmer|software|devops|\bsre\b|data scien|architect|"
    r"full[\s-]?stack|back[\s-]?end|front[\s-]?end|\bqa\b|\bsdet\b",
    re.IGNORECASE,
)

_NON_TECH_TITLE = re.compile(
    r"\bsales\b|account executive|account manager|business development|\bsdr\b|\bbdr\b|"
    r"recruit|talent acquisition|sourcer|\bhr\b|human resources|people partner|people ops|"
    r"marketing|\bseo\b|content (?:writer|creator|producer|strateg|manager)|copywriter|writer|"
    r"editor|journalist|customer (?:support|success|service|care|experience)|"
    r"support (?:agent|specialist|representative|associate)|call cent|"
    r"accountant|accounting|bookkeep|finance|financial|controller|payroll|tax\b|audit|"
    r"legal|counsel|lawyer|attorney|paralegal|compliance officer|"
    r"nurse|physician|doctor|medical|clinical|therap|pharma|dental|"
    r"teacher|tutor|instructor|professor|"
    r"driver|warehouse|cashier|chef|cook\b|barista|retail|store|"
    r"office manager|executive assistant|virtual assistant|administrative|receptionist|"
    r"social media|community manager|influencer|public relations|\bpr\b|"
    r"data entry|data collection|photo collection|annotat|transcri|translator|interpret|"
    r"operations (?:associate|specialist|coordinator)|logistics|procurement|"
    r"mechanical|civil engineer|chemical|structural|process engineer|maintenance|"
    r"field service|biomedical|manufacturing|hvac|construction|mining|petroleum|"
    r"interior design|fashion|graphic design|video editor|photographer|"
    r"study\b|survey\b|participant|rater\b|raters\b|evaluator|no experience required|\boperations\b|"
    r"chief of staff|\bceo\b|\bcoo\b|\bcfo\b|founder.?s associate|general manager|venture|supplier",
    re.IGNORECASE,
)

_TECH_CATEGORY = re.compile(
    r"engineer|develop|software|programming|devops|sysadmin|system admin|"
    r"data|\bqa\b|quality|security|\bit\b|tech|machine learning|\bai\b|"
    r"web|mobile|cloud|product|design|ux|\bui\b",
    re.IGNORECASE,
)

_NON_TECH_CATEGORY = re.compile(
    r"sales|marketing|customer|support|writing|copy|hr\b|human|recruit|finance|"
    r"accounting|legal|admin(?!istrat\w* (?:system|network|database))|education|"
    r"teaching|health|medical|business|management|operations|other|all others",
    re.IGNORECASE,
)


def is_tech_job(title: str, category: object = "", tags: object = None) -> bool:
    title = title or ""
    cats = " ".join(_split_tags(category))
    non_tech = bool(_NON_TECH_TITLE.search(title))
    strong = bool(_STRONG_TITLE.search(title))
    if non_tech and not strong:
        return False
    if non_tech and strong:
        # "Sales Engineer" or "Customer Support Engineer" stay out;
        # "Software Engineer, Payments" stays in.
        if re.search(r"(?i)sales engineer|support engineer|mechanical|civil|chemical|"
                     r"structural|process engineer|maintenance|field service|"
                     r"biomedical|manufacturing|hvac|construction|petroleum|supplier", title):
            return False
        return True
    if _TECH_TITLE.search(title):
        return True
    if cats and _TECH_CATEGORY.search(cats) and not _NON_TECH_CATEGORY.search(cats):
        return True
    stack = [_tag_name(tag) for tag in _split_tags(tags)]
    return sum(1 for name in stack if name) >= 2 and not cats


# ---- remote / relocation ---------------------------------------------------

_NEG = re.compile(
    r"(?:\bno\b|\bnot\b|\bnor\b|unable|cannot|can't|can not|won't|will not|don't|do not|"
    r"does not|doesn't|without|n't|unfortunately|isn't|aren't|neither|exclud)",
    re.IGNORECASE,
)

_REMOTE_PLACE = re.compile(
    r"\bremote\b|work from anywhere|anywhere|worldwide|world[\s-]?wide|telecommute|"
    r"\bwfh\b|distributed|global",
    re.IGNORECASE,
)

_REMOTE_TEXT = re.compile(
    r"fully[\s-]remote|100\s?% remote|remote[\s-]first|remote[\s-]only|"
    r"(?:this|the) (?:is a |role is |position is )?(?:fully )?remote (?:role|position|job)|"
    r"work from anywhere|"
    r"\bremote\s*(?:\(|-|–|:)\s*(?:worldwide|global|anywhere|eu|europe|emea|us|usa|uk|latam|apac)",
    re.IGNORECASE,
)

_HYBRID = re.compile(r"\bhybrid\b|on[\s-]?site|in[\s-]office|office[\s-]based", re.IGNORECASE)

_RELOCATION = re.compile(
    r"visa\s+sponsor\w*|sponsor\w*\s+(?:a\s+|your\s+|the\s+|work\s+|employment\s+)?visas?|"
    r"visa\s+(?:support|assistance|help|provided|available|is provided|and relocation|&\s*relocation)|"
    r"relocation(?:\s+(?:package|support|assistance|bonus|budget|allowance|help|stipend|"
    r"is provided|provided|available|offered|benefits?|costs?))?|"
    r"(?:help|support|assist)\w*\s+(?:you\s+)?(?:with\s+)?relocat\w*|"
    r"\bEU\s+Blue\s+Card\b|work\s+permit\s+(?:support|sponsorship|assistance)|"
    r"h-?1b\s+(?:sponsor\w*|transfer)|we\s+sponsor|sponsorship\s+(?:is\s+)?(?:available|provided|offered)",
    re.IGNORECASE,
)

_HN_VISA = re.compile(r"(?:^|\|)\s*(?:VISA|Visa sponsorship|Visa)\b(?!\s*(?:not|no)\b)")


def _positive(pattern: re.Pattern[str], text: str) -> bool:
    for match in pattern.finditer(text):
        before = text[max(0, match.start() - 60): match.start()]
        # Only look back inside the same sentence or bullet.
        before = re.split(r"[.!?\n•|]", before)[-1]
        after = text[match.end(): match.end() + 25]
        after = re.split(r"[.!?\n•|]", after)[0]
        if _NEG.search(before):
            continue
        if re.search(r"(?i)^\s*(?:is\s+)?(?:not|n/a|none|unavailable)\b", after):
            continue
        if re.search(r"(?i)^\s*:\s*no\b", after):
            continue
        return True
    return False


def remote_flag(title: str, place: str, text: str) -> bool:
    head = f"{title} | {place}"
    if _REMOTE_PLACE.search(place or "") and not _HYBRID.search(place or ""):
        return _positive(_REMOTE_PLACE, place)
    if re.search(r"(?i)\bremote\b", title or "") and not _HYBRID.search(head):
        return _positive(re.compile(r"\bremote\b", re.IGNORECASE), title)
    if _HYBRID.search(head):
        return False
    return _positive(_REMOTE_TEXT, (text or "")[:12000])


def relocation_flag(title: str, place: str, text: str) -> bool:
    sample = f"{title}\n{place}\n{(text or '')[:15000]}"
    if _positive(_RELOCATION, sample):
        return True
    return bool(_HN_VISA.search(title or ""))


def enrich(item: dict, *, remote_default: bool = False, relocation_default: bool = False) -> dict:
    """Add tech_stack, remote and relocation to a normalized item."""
    title = str(item.get("title") or "")
    place = str(item.get("city") or "")
    text = str(item.get("text") or "")
    item["tech_stack"] = extract_stack(text, item.get("tags"), title)
    remote = item.get("remote")
    if remote is None:
        remote = remote_default or remote_flag(title, place, text)
    item["remote"] = bool(remote)
    relocation = item.get("relocation")
    if not relocation:
        relocation = relocation_default or relocation_flag(title, place, text)
    item["relocation"] = bool(relocation)
    return item
