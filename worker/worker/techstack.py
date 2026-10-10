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
- ``az_market_relevant`` drops remote ads geo-locked to a foreign country
  (e.g. "Remote, Canada") because the board targets Azerbaijan. Worldwide /
  EMEA / AZ-open remote and relocation stay.
"""

from __future__ import annotations

import html
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


# canonical name -> (pattern for free text, extra lowercase tag aliases, category)
_TECH: list[tuple[str, re.Pattern[str], tuple[str, ...], str]] = [
    # languages
    ("Python", _ci(r"python[23]?|pyspark"), ("py", "python3", "python2"), "language"),
    ("Java", re.compile(_L + r"Java" + r"(?![A-Za-z0-9_+#]|\s*Script)"), ("java",), "language"),
    ("Kotlin", _ci(r"kotlin"), (), "language"),
    ("Scala", _cs(r"Scala"), ("scala",), "language"),
    ("Go", re.compile(r"(?i:golang)|" + _L + r"Go(?=\s*(?:,|/|\)|\(|;|\s+(?:developer|engineer|backend|services|microservices|programming|language|or|and|&)\b))"), ("go", "golang"), "language"),
    ("Rust", _cs(r"Rust"), ("rust",), "language"),
    ("TypeScript", _ci(r"typescript"), ("ts",), "language"),
    ("JavaScript", _ci(r"javascript|ecmascript|es6"), ("js", "es6", "ecmascript"), "language"),
    ("PHP", _ci(r"php[5-8]?"), (), "language"),
    ("Ruby", _ci(r"ruby(?!\s+on\s+rails)"), (), "language"),
    ("C#", re.compile(_L + r"C#|(?i:csharp)"), ("c#", "csharp"), "language"),
    ("C++", re.compile(_L + r"C\+\+|(?i:cpp)" + _R), ("c++", "cpp"), "language"),
    ("C", re.compile(r"(?<![A-Za-z0-9_+#.\-/])C(?=\s*(?:/C\+\+|,\s*C\+\+|\s+and\s+C\+\+)|\s+programming\b)"), ("c",), "language"),
    (".NET", re.compile(r"(?<![A-Za-z0-9_])(?:ASP)?\.NET(?:\s?Core)?\b|(?i:dotnet)" + _R), (".net", "dotnet", "asp.net", ".net core", "aspnet"), "language"),
    ("Swift", _cs(r"Swift|SwiftUI"), ("swift", "swiftui"), "language"),
    ("Objective-C", _ci(r"objective-c|obj-c"), ("objc", "obj-c"), "language"),
    ("Dart", _cs(r"Dart"), ("dart",), "language"),
    ("Elixir", _ci(r"elixir"), (), "language"),
    ("Erlang", _ci(r"erlang"), (), "language"),
    ("Haskell", _ci(r"haskell"), (), "language"),
    ("Clojure", _ci(r"clojure(?:script)?"), ("clojurescript", "cljs"), "language"),
    ("Solidity", _ci(r"solidity"), (), "language"),
    ("SQL", _cs(r"SQL|T-SQL|PL/SQL"), ("sql", "t-sql", "pl/sql", "plsql"), "language"),
    ("Bash", _cs(r"Bash|Shell scripting"), ("bash", "shell", "shell scripting"), "language"),
    ("Perl", _ci(r"perl"), (), "language"),
    ("Groovy", _ci(r"groovy"), (), "language"),
    ("Lua", _cs(r"Lua"), ("lua",), "language"),
    ("Julia", _cs(r"Julia"), ("julia",), "language"),
    ("F#", re.compile(_L + r"F#|(?i:fsharp)" + _R), ("f#", "fsharp"), "language"),
    ("MATLAB", _ci(r"matlab"), (), "language"),
    ("PowerShell", _ci(r"powershell|pwsh"), ("pwsh",), "language"),
    ("R", re.compile(_L + r"R(?=\s+(?:programming|language|studio|stats?|statistics)\b)|(?:tidyverse|ggplot2?|shiny\s+r)\b", re.IGNORECASE), ("r programming", "rstudio"), "language"),
    # front end / mobile
    ("React", re.compile(_L + r"React(?:\.?js|JS)?(?!\s*Native)" + _R + r"|(?i:reactjs|react\.js)"), ("react", "reactjs", "react.js"), "frontend"),
    ("React Native", _ci(r"react[\s-]native"), ("rn",), "mobile"),
    ("Next.js", _ci(r"next\.?js"), ("nextjs", "next"), "frontend"),
    ("Vue.js", re.compile(_L + r"Vue(?:\.?js|JS)?" + _R + r"|(?i:vuejs|vue\.js)"), ("vue", "vuejs", "vue.js"), "frontend"),
    ("Nuxt", _ci(r"nuxt(?:\.?js)?"), ("nuxtjs", "nuxt.js"), "frontend"),
    ("Angular", _cs(r"Angular(?:JS)?"), ("angular", "angularjs"), "frontend"),
    ("Svelte", _ci(r"svelte(?:kit)?"), ("sveltekit",), "frontend"),
    ("Redux", _cs(r"Redux"), ("redux", "redux toolkit", "rtk"), "frontend"),
    ("Tailwind", _ci(r"tailwind(?:\s?css)?"), ("tailwindcss", "tailwind css"), "frontend"),
    ("HTML", _cs(r"HTML5?"), ("html", "html5"), "frontend"),
    ("CSS", _cs(r"CSS3?|SCSS|Sass"), ("css", "css3", "scss", "sass"), "frontend"),
    ("jQuery", _ci(r"jquery"), (), "frontend"),
    ("Bootstrap", _ci(r"bootstrap"), (), "frontend"),
    ("Vite", _cs(r"Vite"), ("vite",), "frontend"),
    ("Webpack", _ci(r"webpack"), (), "frontend"),
    ("Remix", re.compile(_L + r"Remix(?:\.js)?" + _R), ("remix.js", "remixjs"), "frontend"),
    ("Astro", _cs(r"Astro"), ("astro",), "frontend"),
    ("Gatsby", _ci(r"gatsby"), (), "frontend"),
    ("Ember", _ci(r"ember(?:\.?js)?"), ("emberjs", "ember.js"), "frontend"),
    ("Material UI", _ci(r"material[\s-]?ui|\bmui\b"), ("mui", "material-ui"), "frontend"),
    ("Storybook", _ci(r"storybook"), (), "frontend"),
    ("Three.js", _ci(r"three\.?js"), ("threejs",), "frontend"),
    ("D3.js", _ci(r"d3\.?js"), ("d3", "d3js"), "frontend"),
    ("RxJS", _ci(r"rxjs"), (), "frontend"),
    ("Flutter", _ci(r"flutter"), (), "mobile"),
    ("iOS", _cs(r"iOS"), ("ios",), "mobile"),
    ("Android", _cs(r"Android"), ("android",), "mobile"),
    ("Jetpack Compose", _ci(r"jetpack\s+compose|\bandroid\s+compose\b"), (), "mobile"),
    ("Xamarin", _ci(r"xamarin"), (), "mobile"),
    ("Ionic", _ci(r"ionic"), (), "mobile"),
    ("Capacitor", _ci(r"capacitor"), (), "mobile"),
    # back end frameworks
    ("Node.js", _ci(r"node\.?js|node\s+js"), ("node", "nodejs", "node.js"), "backend"),
    ("NestJS", _ci(r"nest\.?js"), ("nestjs", "nest.js"), "backend"),
    ("Express", re.compile(_L + r"Express(?:\.js|JS)" + _R + r"|(?i:expressjs)"), ("express", "expressjs", "express.js"), "backend"),
    ("Fastify", _ci(r"fastify"), (), "backend"),
    ("Django", _ci(r"django"), (), "backend"),
    ("Flask", _cs(r"Flask"), ("flask",), "backend"),
    ("FastAPI", _ci(r"fastapi"), (), "backend"),
    ("Spring", re.compile(_L + r"Spring(?:\s?Boot|\s(?:Framework|Cloud|MVC|Data|Security))" + _R + r"|(?i:springboot)"), ("spring", "spring boot", "springboot"), "backend"),
    ("Hibernate", _ci(r"hibernate"), (), "backend"),
    ("JPA", _cs(r"JPA"), ("jpa",), "backend"),
    ("JWT", _cs(r"JWT"), ("jwt", "json web token"), "backend"),
    ("Quarkus", _ci(r"quarkus"), (), "backend"),
    ("Micronaut", _ci(r"micronaut"), (), "backend"),
    ("Ktor", _cs(r"Ktor"), ("ktor",), "backend"),
    ("Celery", _cs(r"Celery"), ("celery",), "backend"),
    ("Prisma", _cs(r"Prisma"), ("prisma",), "backend"),
    ("TypeORM", _ci(r"typeorm"), (), "backend"),
    ("Sequelize", _ci(r"sequelize"), (), "backend"),
    ("Entity Framework", _ci(r"entity\s+framework|\bef\s?core\b"), ("ef core", "efcore"), "backend"),
    ("Blazor", _ci(r"blazor"), (), "backend"),
    ("Oracle", _ci(r"oracle"), (), "data"),
    ("Git", re.compile(_L + r"Git(?!\s*Hub|\s*Lab)" + _R, re.IGNORECASE), ("git",), "devops"),
    ("Ruby on Rails", _ci(r"ruby\s+on\s+rails|rails|ror"), ("rails", "ror", "ruby on rails"), "backend"),
    ("Laravel", _ci(r"laravel"), (), "backend"),
    ("Symfony", _ci(r"symfony"), (), "backend"),
    ("Phoenix", re.compile(_L + r"Phoenix(?=\s*(?:framework|LiveView|/|,\s*(?:Elixir|Ecto)))"), ("phoenix", "phoenix framework"), "backend"),
    ("GraphQL", _ci(r"graphql"), (), "backend"),
    ("gRPC", _ci(r"grpc"), (), "backend"),
    ("WordPress", _ci(r"wordpress"), ("wp",), "backend"),
    ("Shopify", _cs(r"Shopify"), ("shopify",), "backend"),
    ("Salesforce", _ci(r"salesforce"), ("sfdc",), "backend"),
    ("Odoo", _ci(r"odoo"), (), "backend"),
    # cloud / infra
    ("AWS", _ci(r"aws|amazon\s+web\s+services"), ("amazon web services",), "cloud"),
    ("GCP", re.compile(_L + r"GCP" + _R + r"|(?i:google\s+cloud(?:\s+platform)?)"), ("gcp", "google cloud", "google cloud platform"), "cloud"),
    ("Azure", _cs(r"Azure"), ("azure",), "cloud"),
    ("Kubernetes", _ci(r"kubernetes|k8s|eks|gke|aks"), ("k8s", "eks", "gke", "aks"), "devops"),
    ("Docker", _ci(r"docker"), ("docker-compose", "docker compose"), "devops"),
    ("Terraform", _ci(r"terraform"), (), "devops"),
    ("Ansible", _ci(r"ansible"), (), "devops"),
    ("Helm", _cs(r"Helm"), ("helm",), "devops"),
    ("Linux", _ci(r"linux"), (), "devops"),
    ("CI/CD", _ci(r"ci/cd|ci\s?&\s?cd|continuous\s+integration"), ("ci/cd", "cicd", "continuous integration", "continuous delivery"), "devops"),
    ("Jenkins", _ci(r"jenkins"), (), "devops"),
    ("GitHub Actions", _ci(r"github\s+actions"), ("gha",), "devops"),
    ("GitLab CI", _ci(r"gitlab\s+ci(?:/cd)?"), ("gitlab-ci",), "devops"),
    ("GitLab", re.compile(_L + r"GitLab(?!\s+CI)" + _R, re.IGNORECASE), ("gitlab",), "devops"),
    ("CircleCI", _ci(r"circle\s?ci"), ("circle ci",), "devops"),
    ("Argo CD", _ci(r"argo\s?cd|argocd"), ("argocd", "argo-cd"), "devops"),
    ("Istio", _ci(r"istio"), (), "devops"),
    ("OpenShift", _ci(r"openshift"), (), "cloud"),
    ("Pulumi", _ci(r"pulumi"), (), "devops"),
    ("CloudFormation", _ci(r"cloudformation"), ("cfn",), "cloud"),
    ("Cloudflare", _ci(r"cloudflare"), (), "cloud"),
    ("Vercel", _ci(r"vercel"), (), "cloud"),
    ("Netlify", _ci(r"netlify"), (), "cloud"),
    ("Heroku", _ci(r"heroku"), (), "cloud"),
    ("DigitalOcean", _ci(r"digital\s?ocean"), ("digital ocean",), "cloud"),
    ("Prometheus", _cs(r"Prometheus"), ("prometheus",), "devops"),
    ("Grafana", _ci(r"grafana"), (), "devops"),
    ("Datadog", _ci(r"datadog"), (), "devops"),
    ("New Relic", _ci(r"new\s+relic"), ("newrelic",), "devops"),
    ("Sentry", _cs(r"Sentry"), ("sentry",), "devops"),
    ("OpenTelemetry", _ci(r"open\s?telemetry|\botel\b"), ("otel",), "devops"),
    ("Splunk", _cs(r"Splunk"), ("splunk",), "devops"),
    ("Nginx", _ci(r"nginx"), (), "devops"),
    ("Traefik", _ci(r"traefik"), (), "devops"),
    ("HAProxy", _ci(r"haproxy"), (), "devops"),
    ("Consul", _cs(r"Consul"), ("consul",), "devops"),
    ("HashiCorp Vault", _ci(r"hashicorp\s+vault|(?<![A-Za-z])vault(?:\s+(?:secrets?|kv|transit))\b"), ("vault", "hashicorp vault"), "devops"),
    # data
    ("PostgreSQL", _ci(r"postgres(?:ql)?|psql"), ("postgres", "postgresql", "psql"), "data"),
    ("MySQL", _ci(r"mysql"), (), "data"),
    ("MariaDB", _ci(r"mariadb"), (), "data"),
    ("SQL Server", _ci(r"(?:microsoft\s+)?sql\s+server|\bmssql\b"), ("mssql", "microsoft sql server"), "data"),
    ("SQLite", _ci(r"sqlite"), (), "data"),
    ("MongoDB", _ci(r"mongo(?:db)?"), ("mongo",), "data"),
    ("Redis", _ci(r"redis"), (), "data"),
    ("Elasticsearch", _ci(r"elastic\s?search|opensearch"), ("opensearch", "elastic search"), "data"),
    ("DynamoDB", _ci(r"dynamodb"), ("dynamo",), "data"),
    ("Cassandra", _cs(r"Cassandra"), ("cassandra",), "data"),
    ("ClickHouse", _ci(r"clickhouse"), (), "data"),
    ("Neo4j", _ci(r"neo4j"), (), "data"),
    ("Couchbase", _ci(r"couchbase"), (), "data"),
    ("InfluxDB", _ci(r"influx(?:db)?"), (), "data"),
    ("Redshift", _ci(r"redshift"), (), "data"),
    ("Kafka", _ci(r"kafka"), (), "data"),
    ("RabbitMQ", _ci(r"rabbitmq"), (), "data"),
    ("Spark", re.compile(_L + r"(?:Apache\s+)?Spark" + _R + r"|(?i:pyspark)"), ("spark", "apache spark", "pyspark"), "data"),
    ("Flink", _ci(r"(?:apache\s+)?flink"), ("apache flink",), "data"),
    ("Hadoop", _ci(r"hadoop"), (), "data"),
    ("Hive", _ci(r"(?:apache\s+)?hive(?:ql)?"), ("apache hive", "hiveql"), "data"),
    ("Trino", _cs(r"Trino"), ("trino",), "data"),
    ("Airflow", _ci(r"airflow"), ("apache airflow",), "data"),
    ("dbt", _cs(r"dbt"), ("dbt",), "data"),
    ("Snowflake", _cs(r"Snowflake"), ("snowflake",), "data"),
    ("BigQuery", _ci(r"bigquery"), ("big query",), "data"),
    ("Databricks", _ci(r"databricks"), (), "data"),
    ("Pandas", _cs(r"[Pp]andas"), ("pandas",), "data"),
    ("NumPy", _ci(r"numpy"), (), "data"),
    ("Tableau", _cs(r"Tableau"), ("tableau",), "data"),
    ("Power BI", _ci(r"power\s?bi"), ("powerbi",), "data"),
    ("Looker", _cs(r"Looker"), ("looker",), "data"),
    # ML / AI
    ("PyTorch", _ci(r"pytorch"), (), "ml"),
    ("TensorFlow", _ci(r"tensorflow"), (), "ml"),
    ("Keras", _ci(r"keras"), (), "ml"),
    ("scikit-learn", _ci(r"scikit-learn|sklearn"), ("sklearn",), "ml"),
    ("Hugging Face", _ci(r"hugging\s?face|\bhf\s+transformers\b"), ("huggingface",), "ml"),
    ("LangChain", _ci(r"langchain"), (), "ml"),
    ("OpenAI", _ci(r"openai"), (), "ml"),
    ("CUDA", _cs(r"CUDA"), ("cuda",), "ml"),
    ("MLflow", _ci(r"mlflow"), (), "ml"),
    ("LLM", _cs(r"LLMs?"), ("llm", "llms", "large language model"), "ml"),
    ("NLP", _cs(r"NLP"), ("nlp", "natural language processing"), "ml"),
    ("Computer Vision", _ci(r"computer\s+vision"), (), "ml"),
    ("RAG", _ci(r"\brag\b|retrieval[\s-]augmented"), ("retrieval augmented generation",), "ml"),
    # QA / design / web3 / product tools
    ("Selenium", _ci(r"selenium"), (), "qa"),
    ("Cypress", _cs(r"Cypress"), ("cypress",), "qa"),
    ("Playwright", _ci(r"playwright"), (), "qa"),
    ("Jest", _cs(r"Jest"), ("jest",), "qa"),
    ("pytest", _ci(r"pytest"), (), "qa"),
    ("JUnit", _cs(r"JUnit"), ("junit",), "qa"),
    ("TestNG", _ci(r"testng"), (), "qa"),
    ("Postman", _cs(r"Postman"), ("postman",), "qa"),
    ("JMeter", _ci(r"jmeter"), (), "qa"),
    ("k6", _ci(r"\bk6\b"), (), "qa"),
    ("Appium", _ci(r"appium"), (), "qa"),
    ("Mocha", _cs(r"Mocha"), ("mocha",), "qa"),
    ("Vitest", _ci(r"vitest"), (), "qa"),
    ("Cucumber", _cs(r"Cucumber"), ("cucumber", "gherkin"), "qa"),
    ("Figma", _ci(r"figma"), (), "design"),
    ("Jira", _cs(r"Jira"), ("jira",), "other"),
    ("Unity", _cs(r"Unity(?:3D)?"), ("unity", "unity3d"), "gamedev"),
    ("Unreal Engine", _ci(r"unreal(?:\s+engine)?"), ("unreal", "ue5", "ue4"), "gamedev"),
    ("Ethereum", _ci(r"ethereum|evm"), ("evm",), "web3"),
    ("OWASP", _cs(r"OWASP"), ("owasp",), "security"),
]

_ALIASES: dict[str, str] = {}
for _name, _pattern, _extra, _cat in _TECH:
    _ALIASES[_name.lower()] = _name
    for _alias in _extra:
        _ALIASES[_alias] = _name

TECH_NAMES = [name for name, _p, _e, _c in _TECH]
TECH_CATEGORY = {name: cat for name, _p, _e, cat in _TECH}


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
    for name, pattern, _extra, _cat in _TECH:
        found = re.compile(pattern.pattern, re.IGNORECASE).fullmatch(tag.strip())
        if found and name not in {"Go", "C", "SQL"}:
            return name
    return None


# When the source's own tags/stack fields name at least this many curated
# technologies, the ad text is not scanned at all.
TAGS_ENOUGH = 3


def stack_from_tags(tags: object) -> list[str]:
    found: list[str] = []
    for tag in _split_tags(tags):
        name = _tag_name(tag)
        if name and name not in found:
            found.append(name)
    return found


def find_stack(text: str, *, limit: int | None = None) -> list[str]:
    """All curated tech names found in free text, first-occurrence order.

    Used by the CV rules parser (no ad-tag short-circuit, optional higher cap).
    ``limit=None`` keeps every match; job ads still use ``extract_stack``.
    """
    sample = (text or "")[:50000]
    scored: list[tuple[int, str]] = []
    for name, pattern, _extra, _cat in _TECH:
        hit = pattern.search(sample)
        if hit:
            scored.append((hit.start(), name))
    scored.sort()
    names = [name for _pos, name in scored]
    if limit is not None:
        return names[:limit]
    return names


def extract_stack(text: str, tags: object = None, title: str = "") -> list[str]:
    """Curated tech names. The source's tags/stack fields come first; keyword
    matching on the title and text only fills in when the source gave fewer
    than TAGS_ENOUGH known technologies."""
    found = stack_from_tags(tags)
    if len(found) >= TAGS_ENOUGH:
        return found[:MAX_STACK]
    sample = f"{title}\n{text or ''}"[:30000]
    scored: list[tuple[int, int, str]] = []
    for name, pattern, _extra, _cat in _TECH:
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
    r"kubernetes|\baws\b|salesforce developer|odoo|"
    r"proqramç|proqramlaşdırma|разработчик|программист|тестировщик|девопс",
    re.IGNORECASE,
)

_STRONG_TITLE = re.compile(
    r"engineer|developer|programmer|software|devops|\bsre\b|data scien|architect|"
    r"full[\s-]?stack|back[\s-]?end|front[\s-]?end|\bqa\b|\bsdet\b",
    re.IGNORECASE,
)

_NON_TECH_TITLE = re.compile(
    r"\bsales\b|account executive|account manager|business development|partnerships?\b|\bsdr\b|\bbdr\b|"
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

def _clean_cat(value: str) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"[-_/]+", " ", value)
    return re.sub(r"\s+", " ", value).strip().lower()


# Words in a source category that mean a tech role.
_SRC_TECH = re.compile(
    r"engineer|engineering|develop|software|programming|programmer|coding|\bdev\b|\beng\b|"
    r"devops|devsecops|sysadmin|system(?:s)? admin\w*|network admin\w*|database|\bdba\b|"
    r"\bdata\b|analytics|scien|machine learning|\bml\b|\bai\b|\bllm|"
    r"\bqa\b|quality assurance|\btest(?:ing|er|s)?\b|secur|cyber|"
    r"\bit\b|\btech\b|technolog|technical|cloud|infrastructure|platform|\bsre\b|"
    r"web|mobile|\bios\b|android|front ?end|back ?end|full ?stack|"
    r"product|design|\bux\b|\bui\b|blockchain|web3|smart contract|embedded|firmware|"
    r"python|\bjava\b|javascript|typescript|\bphp\b|ruby|golang|\bgo\b|scala|rust|elixir|"
    r"c\+\+|c#|\.net|node|react|angular|vue|flutter|kotlin|swift|unity|gamedev|game dev"
)

# Phrases that hold a non-tech word but are tech ("Technical Support",
# "System Administration"). Removed before the non-tech test.
_SRC_TECH_PHRASE = re.compile(
    r"technical support|tech support|it support|help ?desk|service desk|desktop support|sys ?admin\w*|"
    r"system(?:s)? administration|network administration|database administration|"
    r"product management|engineering management|technical writ\w*|technical account"
)

# Words that mean a non-tech role.
_SRC_NON = re.compile(
    r"sales|marketing|customer|support|success|writing|writer|copy|content|"
    r"\bhr\b|human|people|recruit|talent|finance|financial|accounting|legal|compliance|"
    r"admin\w*|assistan|education|teaching|health|medical|business|management|"
    r"operations|commercial|go to market|g ?& ?a\b|revenue|partnership|account|media|"
    r"\bseo\b|social|community|consult\w*|\bothers?\b|all other|hospitality|retail|"
    r"logistics|manufacturing|creative|lead generation|\bceo\b|executive|office"
)

# Categories that decide nothing on their own: the title decides.
_SRC_NEUTRAL = re.compile(r"project|program(?:me)? manag|business analy|delivery manag")

# Categories that are never tech, even with a tech-looking word in them.
_SRC_FORCE_NON = re.compile(
    r"business development|go to market|graphic design|interior design|fashion|"
    r"non tech|annotat|data entry|trading|trader|"
    r"customer (?:success|support|service|experience)(?! engineer)"
)

# Titles that are engineering but not IT. These stay out whatever the
# source category says ("Mechanical Design Engineer" under "Engineering").
_PHYSICAL_TITLE = re.compile(
    r"mechanical|civil engineer|chemical|structural|process engineer|maintenance|"
    r"field service|biomedical|manufacturing|hvac|construction|petroleum|supplier|"
    r"avionics|electrical engineer|sales engineer|architectural|estimator|landscape|"
    r"equipment technician|"
    r"propellant|propulsion|composite engineer|thermal engineer|quality control engineer|"
    r"production engineer.{0,30}\buav\b|"
    r"insurance|(?<!re)liability|underwrit|"
    r"trust\s*(?:&|and)\s*safety|growth\s*(?:&|and)\s*operations",
    re.IGNORECASE,
)


def _value_verdict(value: str) -> bool | None:
    """One source category value: True tech, False non-tech, None unclear."""
    if not value:
        return None
    if _SRC_FORCE_NON.search(value):
        return False
    if _SRC_NEUTRAL.search(value):
        return None
    tech = bool(_SRC_TECH.search(value))
    non = bool(_SRC_NON.search(_SRC_TECH_PHRASE.sub(" ", value)))
    if tech and not non:
        return True
    if non and not tech:
        return False
    return None


def source_category_verdict(category: object) -> bool | None:
    """The source's own category, when it says clearly tech or non-tech.

    Values that match nothing (company names, "Remote", "Propulsion") are
    skipped. Mixed or unclear categories return None so the title decides.
    """
    votes: list[bool | None] = []
    for raw in _split_tags(category):
        value = _clean_cat(raw)
        if not (_SRC_TECH.search(value) or _SRC_NON.search(value) or _SRC_NEUTRAL.search(value)
                or _SRC_FORCE_NON.search(value)):
            continue
        votes.append(_value_verdict(value))
    if True in votes and False not in votes:
        return True
    if False in votes and True not in votes and None not in votes:
        return False
    return None


def is_tech_job(title: str, category: object = "", tags: object = None) -> bool:
    """The source category wins when it is clear; otherwise the title decides."""
    title = title or ""
    if _PHYSICAL_TITLE.search(title):
        return False
    non_tech = bool(_NON_TECH_TITLE.search(title))
    strong = bool(_STRONG_TITLE.search(title))
    verdict = source_category_verdict(category)
    if verdict is False:
        return False
    if verdict is True:
        # A specific source category ("Backend", "QA", "Python") wins outright.
        # A broad one ("Engineering", "Tech", "Development") still drops a title
        # that is plainly non-tech, such as "Head of Sales" under "Engineering".
        specific = any(_match_category(raw) for raw in _split_tags(category))
        return specific or not (non_tech and not strong)
    cats = " ".join(_split_tags(category))
    if non_tech and not strong:
        return False
    if non_tech and strong:
        # "Sales Engineer" or "Customer Support Engineer" stay out;
        # "Software Engineer, Payments" stays in.
        return not re.search(r"(?i)support engineer", title)
    if _TECH_TITLE.search(title):
        return True
    return len(stack_from_tags(tags)) >= 2 and not cats


# ---- normalized category ----------------------------------------------------

CATEGORIES = (
    "Backend", "Frontend", "Full-stack", "Mobile", "DevOps/Cloud", "Data/ML",
    "QA", "Security", "Design/UX", "Product", "IT Support", "Other tech",
)

# Priority order breaks ties when two rules match at the same position.
_CATEGORY_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("Full-stack", re.compile(r"full ?stack")),
    ("QA", re.compile(r"\bqa\b|quality assurance|\bsdet\b|\btest(?:er|ers|ing)?\b|"
                      r"software quality|quality engineer|automation (?:qa|test)")),
    ("Security", re.compile(r"secur|cyber|pen ?test|penetration|infosec|\bsoc\b|appsec")),
    ("Mobile", re.compile(r"mobile|\bios\b|android|flutter|react native|\bswift\b|xamarin")),
    ("Data/ML", re.compile(r"\bdata\b|machine learning|\bml\b|mlops|\bai\b|artificial intelligence|"
                           r"\bllms?\b|\bnlp\b|computer vision|deep learning|analytics|\bbi\b|"
                           r"business intelligence|\betl\b|database|\bdba\b|scientist|data science")),
    ("DevOps/Cloud", re.compile(r"devops|\bsre\b|site reliability|infrastructure|platform|cloud|"
                                r"sys ?admin|system(?:s)? admin\w*|kubernetes|network (?:engineer|admin\w*)|"
                                r"release engineer|build engineer|\bops\b")),
    ("Frontend", re.compile(r"front ?end|\bui (?:engineer|developer)|web develop|javascript|typescript|"
                            r"react(?! native)|\bvue|angular|svelte|next\.? ?js")),
    ("Backend", re.compile(r"back ?end|server side|\bapi\b|python|\bjava\b|\bphp\b|ruby|golang|"
                           r"\bgo (?:developer|engineer)|\.net|dotnet|c#|node|scala|\brust\b|elixir|"
                           r"erlang|c\+\+|django|spring|laravel|rails|microservice")),
    ("Design/UX", re.compile(r"\bux\b|\bui\b|user experience|user interface|product design|"
                             r"interaction design|visual design|web design|design system|designer|"
                             r"\bdesign\b(?! engineer)")),
    ("Product", re.compile(r"^products?$|product (?:manag|owner|lead|director|analyst|ops|strateg)|"
                           r"head of product|vp product|chief product|project manag|program manag|"
                           r"scrum|agile coach|delivery manag|technical project")),
    ("IT Support", re.compile(r"it support|technical support|tech support|help ?desk|service desk|"
                              r"desktop support|it (?:technician|specialist|administrator|admin)|"
                              r"support engineer")),
]
_PRIORITY = {label: index for index, (label, _p) in enumerate(_CATEGORY_RULES)}

_STACK_GROUPS = {
    "Mobile": {"React Native", "Flutter", "iOS", "Android", "Swift", "Objective-C", "Dart",
               "Jetpack Compose", "Xamarin", "Ionic", "Capacitor"},
    "Frontend": {"React", "Next.js", "Vue.js", "Nuxt", "Angular", "Svelte", "Redux", "Tailwind",
                 "jQuery", "Bootstrap", "Vite", "Webpack", "Remix", "Astro", "Gatsby", "Ember",
                 "Material UI", "Storybook"},
    "Backend": {"Python", "Java", "Scala", "Go", "Rust", "PHP", "Ruby", "C#", ".NET", "Elixir",
                "Erlang", "Node.js", "NestJS", "Express", "Django", "Flask", "FastAPI", "Spring",
                "Ruby on Rails", "Laravel", "Symfony", "Phoenix", "Kotlin", "Fastify", "Quarkus",
                "Micronaut", "Ktor", "Blazor"},
    "Data/ML": {"Spark", "Airflow", "dbt", "Snowflake", "BigQuery", "Databricks", "Pandas",
                "PyTorch", "TensorFlow", "scikit-learn", "LLM", "Keras", "Hugging Face",
                "LangChain", "MLflow", "NLP", "Tableau", "Power BI"},
    "DevOps/Cloud": {"Kubernetes", "Terraform", "Ansible", "Helm", "Jenkins", "Prometheus", "Grafana",
                     "Argo CD", "GitHub Actions", "GitLab CI", "Pulumi", "Istio", "OpenShift"},
    "QA": {"Selenium", "Cypress", "Playwright", "pytest", "JUnit", "Postman", "Appium"},
    "Design/UX": {"Figma"},
}


def _match_category(text: str) -> str:
    text = _clean_cat(text)
    best: tuple[int, int, str] | None = None
    for label, pattern in _CATEGORY_RULES:
        found = pattern.search(text)
        if found:
            key = (found.start(), _PRIORITY[label], label)
            if best is None or key < best:
                best = key
    return best[2] if best else ""


def _category_from_stack(stack: list[str]) -> str:
    top = stack[:5]
    if any(name in _STACK_GROUPS["Mobile"] for name in top[:3]):
        return "Mobile"
    counts = {label: sum(1 for name in top if name in names) for label, names in _STACK_GROUPS.items()}
    if counts["Frontend"] and counts["Backend"]:
        return "Full-stack"
    label, count = max(counts.items(), key=lambda pair: pair[1])
    return label if count else ""


_QA_TITLE = re.compile(r"\bqa\b|quality assurance|\bsdet\b|\btesters?\b|test automation", re.IGNORECASE)


def classify_category(category: object, title: str = "", stack: list[str] | None = None) -> str:
    """One of CATEGORIES. The source's own category first (values that clearly
    say non-tech are skipped), then the title, then the tech stack."""
    from_title = _match_category(title or "")
    if from_title == "QA" and _QA_TITLE.search(title or ""):
        # "QA Engineer" is QA whatever the source board or stack says
        # (Azure, DevOps, security boards must not move it).
        return "QA"
    for raw in _split_tags(category):
        if _value_verdict(_clean_cat(raw)) is False:
            continue
        label = _match_category(raw)
        if not label:
            continue
        if label in {"Design/UX", "Product"} and from_title in {"Design/UX", "Product"}:
            # A shared "Product & Design" board: the title says which one.
            return from_title
        if (
            label in {"Design/UX", "Product"}
            and from_title not in {"Design/UX", "Product"}
            and _STRONG_TITLE.search(title or "")
        ):
            # An engineer filed under the source's "Design" or "Product" board
            # ("Senior Research Engineer" in WWR Design) is not a designer.
            break
        return label
    if from_title:
        return from_title
    return _category_from_stack(list(stack or [])) or "Other tech"


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


# ---- Azerbaijan market geo gate --------------------------------------------
# Ingress Job is an Azerbaijan-first board. True worldwide remote is welcome;
# "remote, but only in Canada / US / UK / …" is not.

_FOREIGN_GEO = (
    r"united\s+states|u\.?s\.?a\.?\b|\bu\.?s\.?\b|canada|united\s+kingdom|\buk\b|"
    r"england|scotland|wales|ireland|\beu\b|european\s+union|\beurope\b|"
    r"germany|france|netherlands|spain|italy|portugal|poland|sweden|norway|"
    r"denmark|finland|switzerland|austria|belgium|australia|new\s+zealand|"
    r"japan|south\s+korea|korea|singapore|india|brazil|brasil|mexico|méxico|argentina|chile|"
    r"colombia|per[uú]|uruguay|ecuador|paraguay|bolivia|"
    r"israel|tel\s*aviv|dubai|uae|united\s+arab\s+emirates|saudi|riyadh|"
    r"malta|sliema|latam|latin\s+america|am[eé]rica\s+latina|"
    r"apac|north\s+america|south\s+america|"
    r"california|texas|florida|ontario|british\s+columbia|quebec|"
    r"london|toronto|vancouver|montreal|berlin|munich|münchen|hamburg|"
    r"amsterdam|dublin|paris|stockholm|oslo|copenhagen|sydney|melbourne|"
    r"tokyo|bangalore|bengaluru|são\s+paulo|sao\s+paulo|mexico\s+city|"
    r"deutschland|cambridge|karlsruhe|nantes|barcelona"
)

# Bare "worldwide" in company blurbs ("orgs worldwide") must NOT open the gate.
_OPEN_MARKET = re.compile(
    r"work from anywhere|anywhere in the world|from anywhere|"
    r"location[\s-]?independent|no location restrict|"
    r"remote\s*(?:\(|-|–|:)\s*(?:worldwide|world[\s-]?wide|global|anywhere)|"
    r"(?:hiring|candidates?|applicants?|role|position|job)\s+"
    r"[^\n.]{0,40}(?:worldwide|world[\s-]?wide|global(?:ly)?)\b|"
    r"(?:worldwide|world[\s-]?wide|global)\s+"
    r"(?:remote|candidates?|applicants?|hiring)\b|"
    r"azerbaijan|azərbaycan|azerbaycan|\bbaku\b|\bbakı\b|"
    r"\beméa\b|\bemea\b|\bcis\b|caucasus|central\s+asia",
    re.IGNORECASE,
)

# US/CA state-style pins often appear as "Remote - MA" / "Remote, NY".
_US_STATE_PIN = (
    r"A[LKZR]|C[AOT]|D[EC]|F[LM]|G[AU]|HI|I[DLNA]|K[SY]|L[A]|M[EDAINSOT]|"
    r"N[EVHJMY]|O[HKR]|P[ARW]|RI|S[CD]|T[NX]|UT|V[AIT]|W[AVIY]"
)

_REMOTE_FOREIGN_PAIR = re.compile(
    rf"(?i)(?:\bremote\b.{{0,48}}(?:{_FOREIGN_GEO}|\bCA\b|\b(?:{_US_STATE_PIN})\b)|"
    rf"(?:{_FOREIGN_GEO}|\bCA\b|\b(?:{_US_STATE_PIN})\b).{{0,48}}\bremote\b)"
)

_FOREIGN_GEO_RE = re.compile(rf"(?i)\b(?:{_FOREIGN_GEO})\b")

_RESIDENCY_LOCK = re.compile(
    rf"(?i)(?:"
    rf"(?:must|should|need to|required to|only)\s+(?:be\s+)?"
    rf"(?:located|based|living|reside|residing)\s+in\b|"
    rf"(?:only|exclusively)\s+(?:open|available|hiring)\s+(?:to|in|for)\b|"
    rf"(?:candidates?|applicants?)\s+must\s+(?:be|have|live)\b|"
    # "Engineer, based in Latin America" / "evaluators based in South Korea"
    rf"(?:candidates?|applicants?|engineers?|developers?|talent|evaluators?|"
    rf"contractors?|looking for|we need|hiring)\s+[^\n.]{{0,80}}?"
    rf"\bbased\s+in\s+(?:the\s+)?(?:{_FOREIGN_GEO})\b|"
    rf",\s*based\s+in\s+(?:the\s+)?(?:{_FOREIGN_GEO})\b|"
    rf"\bbased\s+in\s+(?:latin\s+america|am[eé]rica\s+latina|latam)\b|"
    # Spanish/Portuguese residency + nationality pins (Chile/LATAM boards).
    rf"(?:deben|debe|deber[aá]n?|tienen que|requisito)\s+"
    rf"(?:los\s+candidatos\s+)?residir\s+en\b|"
    rf"\bresidir\s+en\s+(?:el\s+)?(?:{_FOREIGN_GEO})\b|"
    rf"\bnacionalidad\s+(?:chilena|argentina|colombiana|mexicana|brasile[nñ]a|"
    rf"peruana|uruguaya)\b|"
    rf"(?:right|authorization|authorisation|eligibility|eligible)\s+to\s+work\s+in\b|"
    rf"remote\s+(?:within|across|from|in)\s+(?:the\s+)?(?:{_FOREIGN_GEO})\b|"
    # Avoid benefits like "401k match (US only)".
    rf"(?:remote|candidates?|applicants?|hiring|roles?|positions?|openings?)"
    rf"[^\n.]{{0,40}}\b(?:us|usa|uk|canada|eu|europe)[\s-]+only\b|"
    rf"\b(?:us|usa|uk|canada|eu|europe)[\s-]+only\b(?!\s*\))|"
    rf"\bonly\s+(?:in\s+)?(?:the\s+)?(?:{_FOREIGN_GEO})\b"
    rf")"
)

# Explicit location line / LATAM labour pins when city field is empty.
_BODY_GEO_LOCK = re.compile(
    rf"(?i)(?:"
    rf"location\s*:\s*(?:the\s+)?(?:{_FOREIGN_GEO})\b|"
    rf"currently\s+residing\s+in\s+(?:the\s+)?(?:{_FOREIGN_GEO})\b|"
    rf"(?:feriados|horario|calendario\s+laboral)\s+de\s+chile\b|"
    rf"horarios?\s+de\s+oficina\s+[^\n.]{{0,40}}\bchile\b|"
    rf"(?:connection|overlap|available)\s+during\s+latam\b|"
    rf"top\s*talent\s+from\s+latam\b|"
    rf"t[ií]tulo\s+profesional[^\n.]{{0,60}}\bchile\b|"
    # Hard timezone band that excludes AZ (UTC+4), e.g. "REMOTE (CET ±2h)".
    rf"(?:remote|fully\s+remote|hybrid)\s+[^\n.]{{0,40}}"
    rf"\b(?:CET|CEST|GMT|UTC)\s*[±+\-]\s*\d|"
    rf"\b(?:within|inside)\s+(?:the\s+)?(?:CET|CEST)\s*[±+\-]\s*\d|"
    # India-local stipend (Rs / INR) on remote ads.
    rf"(?:stipend|salary|compensation|pay)\s*:?\s*Rs\.?\s*[\d,]+|"
    rf"\bRs\.?\s*[\d,]+\s*per\s+month\b"
    rf")"
)

# US-only remote often says "US based" / clearance without "must be located in".
# Skip compensation boilerplate: "For US-based employees, the cash compensation…".
_US_MARKET_LOCK = re.compile(
    r"(?i)(?:"
    r"(?<!\bfor\s)\bus[\s-]?based\b(?!\s+employees?\b)|"
    r"(?<!\bfor\s)\bu\.?s\.?a?\.?\s*based\b(?!\s+employees?\b)|"
    r"locations?\s*\(\s*us\s+based\s*\)|"
    r"(?:candidates?|applicants?|consider(?:ed|ing)?)\s+[^\n.]{0,60}\bus\s+based\b|"
    r"(?:right|authorized|authorised|eligible)\s+to\s+work\s+in\s+the\s+u\.?s|"
    r"must\s+reside\s+in\s+(?:the\s+)?u\.?s|"
    r"u\.?s\.?\s+gov(?:ernment)?\s+(?:secret\s+)?clearance|"
    r"(?:active|current)\s+(?:or\s+current\s+)?u\.?s\.?\s+gov|"
    r"(?:secret|top[\s-]?secret)\s+clearance|"
    r"must\s+have\s+[^\n.]{0,40}clearance"
    r")"
)

# "Remote (Germany-wide)" / country-scoped remote without worldwide wording.
_COUNTRY_REMOTE_LOCK = re.compile(
    rf"(?i)(?:"
    rf"germany[\s-]?wide|deutschlandweit|"
    rf"(?:uk|u\.?s\.?a?|us|canada|france|germany|deutschland|netherlands|"
    rf"spain|italy|poland|sweden|norway|denmark|finland|switzerland|"
    rf"austria|belgium|ireland|australia|india|japan)[\s-]?wide|"
    rf"(?:work\s+)?remote(?:ly)?\s*"
    rf"(?:\(|-|–|:|,)?\s*(?:only\s+)?(?:in\s+|within\s+)?"
    rf"(?:the\s+)?(?:{_FOREIGN_GEO})\b|"
    rf"remote(?:ly)?\s+within\s+(?:the\s+)?(?:{_FOREIGN_GEO})\b|"
    rf"offices?\s+in\s+[^\n.]{{0,80}}(?:hamburg|berlin|münchen|munich|"
    rf"london|paris|amsterdam|dublin|toronto|tokyo|tel\s*aviv)"
    rf")"
)

_PLACE_NOISE = re.compile(
    r"(?i)\b(?:remote|hybrid|onsite|on[\s-]?site|wfh|distributed|telecommute|"
    r"full[\s-]?time|part[\s-]?time|contract|possible|mövcud|mümkün)\b"
)

_LOCAL_OK_PLACE = re.compile(
    r"(?i)\b(?:azerbaijan|azərbaycan|azerbaycan|\bbaku\b|\bbakı\b)\b"
)

_PLACE_OPEN_WORDS = re.compile(
    r"(?i)\b(?:remote|anywhere|worldwide|world[\s-]?wide|global|emea|cis|"
    r"caucasus|central\s+asia|home\s*based|homebased)\b"
)

# "Americas" / AMER-only remote is not AZ-reachable (EMEA alone is OK).
_AMERICAS_LOCK = re.compile(
    r"(?i)\b(?:americas?|latam|north\s+america|south\s+america|AMER)\b"
)

# Hybrid / travel / customer-site work is not AZ-reachable "remote".
# Do not match casual "travel to meet colleagues at sprints".
_ONSITE_HEAVY = re.compile(
    r"(?i)(?:"
    r"\bon[\s-]?site\b|"
    r"customer\s+sites?|"
    r"at\s+(?:the\s+)?customer\s+sites?|"
    r"physical\s+installation|"
    r"\bwiring\b|"
    r"(?:must|required|willingness)\s+to\s+travel|"
    r"travel\s+(?:required|expectations)|"
    r"remote\s*/\s*office|"
    r"office\s+phases?"
    r")"
)


def _sample_head(title: str, place: str, text: str) -> str:
    return f"{title}\n{place}\n{(text or '')[:8000]}"


def _garbage_place(place: str) -> bool:
    """Mojibake / undecoded location strings from broken feed encodings."""
    raw = place or ""
    if not raw.strip():
        return False
    if "\ufffd" in raw or re.search(r"Ù.|Ø.|Ã.|Â.|ð.|ñ\x83", raw):
        return True
    letters = re.findall(r"[A-Za-zÀ-ÿƏəİıĞğŞşÇçÖöÜü]", raw)
    if len(raw) >= 10 and len(letters) < max(3, int(len(raw) * 0.25)):
        return True
    return False


def _named_foreign_place(place: str) -> bool:
    """True when location names a concrete place abroad (e.g. Cincinnati, Tel Aviv).

    Pure \"Remote\" / worldwide / EMEA is not a named foreign place.
    \"Remote Roles - EMEA; Sliema, Malta\" still counts (city remains).
    """
    raw = (place or "").strip()
    if not raw or _LOCAL_OK_PLACE.search(raw):
        return False
    if _garbage_place(raw):
        return True
    if _REMOTE_FOREIGN_PAIR.search(raw):
        return True
    # Strip open-market + noise; leftover geo/city ⇒ foreign pin.
    stripped = _PLACE_OPEN_WORDS.sub(" ", raw)
    stripped = _PLACE_NOISE.sub(" ", stripped)
    stripped = re.sub(r"(?i)\broles?\b", " ", stripped)
    stripped = re.sub(r"[\s,;|/–\-:()·]+", " ", stripped).strip()
    if not stripped:
        return False
    if _FOREIGN_GEO_RE.search(stripped):
        return True
    if re.search(rf"(?i)^\b(?:{_US_STATE_PIN})\b$", stripped):
        return True
    if len(stripped) >= 3 and re.search(r"[A-Za-zÀ-ÿ]{3,}", stripped):
        return True
    return False


def _place_foreign_remote_lock(place: str) -> bool:
    """True when the location field pins remote work to a foreign geo."""
    return _named_foreign_place(place)


def _place_fully_open(place: str) -> bool:
    """True when place is only open-market wording (Remote / EMEA / worldwide)."""
    raw = (place or "").strip()
    if not raw or not _OPEN_MARKET.search(raw):
        return False
    return not _named_foreign_place(raw)


def foreign_locked_remote(title: str, place: str, text: str) -> bool:
    """Remote role restricted to a foreign country/region (not AZ-reachable)."""
    head = f"{title} | {place}"
    if _garbage_place(place):
        return True
    # Pure Remote EMEA / worldwide opens; EMEA + Malta city does not.
    if _place_fully_open(place):
        return False
    if _place_foreign_remote_lock(place):
        return True
    if _REMOTE_FOREIGN_PAIR.search(head):
        return True

    sample = _sample_head(title, place, text)
    if _US_MARKET_LOCK.search(sample):
        return True
    if _COUNTRY_REMOTE_LOCK.search(sample):
        return True
    if _BODY_GEO_LOCK.search(sample):
        return True
    # Americas/AMER pin in place or title (e.g. "Engineer (AMER)").
    if _AMERICAS_LOCK.search(place or "") and not re.search(
        r"(?i)\beméa\b|\bemea\b|worldwide|anywhere", place or ""
    ):
        return True
    if re.search(
        r"(?i)\(\s*AMER\s*\)|(?:^|[\s\-–/])AMER(?:\s|$|\))|"
        # Trailing " - NA" / "(NA)" region pin (not the word CANADA).
        r"(?:^|[\s\-–/])NA(?:\s*$|\s*[)\]])|"
        r"\bmiddle\s+east\b|\bMENA\b|\bAPAC\b|\bLATAM\b|"
        r"\ben\s+brasil\b|\bin\s+brazil\b",
        title or "",
    ):
        if not _place_fully_open(place) and not re.search(
            r"(?i)\beméa\b|\bemea\b|worldwide|anywhere", place or ""
        ):
            return True
    if _positive(_RESIDENCY_LOCK, sample) and _FOREIGN_GEO_RE.search(sample):
        return True
    # "Remote possible" + on-site/customer travel is not worldwide remote.
    if _ONSITE_HEAVY.search(sample) and not _OPEN_MARKET.search(f"{place}\n{text[:4000]}"):
        return True
    # Body/title open (worldwide / work from anywhere) only when place is not pinned.
    if _OPEN_MARKET.search(sample):
        return False
    return False


_INTL_RELOC = re.compile(
    r"(?i)(?:"
    r"visa\s+sponsor\w*|sponsor\w*\s+(?:a\s+|your\s+|the\s+|work\s+|employment\s+)?visas?|"
    r"visa\s+(?:support|assistance|help|provided|available|sponsorship)|"
    r"work\s+(?:permit|visa)\s+(?:support|sponsorship|assistance)|"
    r"\bEU\s+Blue\s+Card\b|"
    r"flight\s+(?:ticket|support|allowance)|"
    r"relocati(?:on|ng|e)\s+from\s+(?:abroad|overseas)|"
    r"international\s+relocation|"
    r"overseas\s+candidates?|"
    r"candidates?\s+from\s+(?:abroad|overseas)|"
    r"japan\s+relocation|"
    r"relocation\s+(?:package|support|bonus|budget|allowance|offer)|"
    r"full\s+relocation|"
    r"\brelocati(?:on|ng)\s+offer\b"
    r")"
)


def international_reloc_offer(title: str, place: str, text: str) -> bool:
    """True visa / international relocation — not domestic 'relocation assistance' alone."""
    sample = f"{title}\n{place}\n{(text or '')[:15000]}"
    if _HN_VISA.search(title or ""):
        return True
    if not _positive(_INTL_RELOC, sample):
        return False
    # H-1B / green card on a US-remote pin is work-auth for the US, not AZ reloc.
    if foreign_locked_remote(title, place, text) and re.search(
        r"(?i)\bh-?1b\b|green\s+card|ead\s+holders?", sample
    ):
        return False
    return True


def foreign_office_without_offer(title: str, place: str, text: str) -> bool:
    """Onsite/hybrid abroad with no remote or relocation/visa keywords.

    These must not reach AI (and must not be kept): e.g. Tel Aviv + #LI-Hybrid.
    """
    if international_reloc_offer(title, place, text):
        return False
    if remote_flag(title, place, text) and not _named_foreign_place(place):
        return False
    head = f"{title}\n{place}"
    sample = f"{head}\n{(text or '')[:4000]}"
    hybrid = bool(_HYBRID.search(head) or re.search(r"(?i)#\s*LI\s*-?\s*Hybrid\b", sample))
    foreign_place = _named_foreign_place(place)
    if foreign_place and (
        hybrid
        or not re.search(r"(?i)\bremote\b", place or "")
        or _ONSITE_HEAVY.search(sample)
    ):
        return True
    return False


def az_market_relevant(
    title: str,
    place: str,
    text: str,
    *,
    remote: bool,
    relocation: bool,
) -> bool:
    """Keep ads useful for Azerbaijan candidates.

    Geo-locked remote (US/UK/Germany/Canada/…) is always dropped — even when a
    noisy relocation/visa keyword exists (e.g. H-1B on a US-remote ad).
    Foreign office/hybrid keeps only with clear international visa/reloc offer.
    """
    if remote and foreign_locked_remote(title, place, text):
        return False

    named_office = _named_foreign_place(place) and not re.search(
        r"(?i)\bremote\b", place or ""
    )
    if named_office:
        return international_reloc_offer(title, place, text)

    if foreign_office_without_offer(title, place, text):
        return False
    if remote:
        return True
    if relocation and international_reloc_offer(title, place, text):
        return True
    return False


def enrich(item: dict, *, remote_default: bool = False, relocation_default: bool = False) -> dict:
    """Add tech_stack, job_category, remote and relocation to a normalized item."""
    title = str(item.get("title") or "")
    place = str(item.get("city") or "")
    text = str(item.get("text") or "")
    item["tech_stack"] = extract_stack(text, item.get("tags"), title)
    # Normalized label; item["category"] keeps the source's raw value.
    item["job_category"] = classify_category(item.get("category"), title, item["tech_stack"])
    remote = item.get("remote")
    if remote is None:
        remote = remote_default or remote_flag(title, place, text)
    item["remote"] = bool(remote)
    relocation = item.get("relocation")
    if not relocation:
        relocation = relocation_default or relocation_flag(title, place, text)
    item["relocation"] = bool(relocation)
    return item
