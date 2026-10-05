"""One pass over the enabled connectors, the same pass every hour, or a dry probe."""

from __future__ import annotations

import fcntl
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from worker.observability import capture_exception, flush, init_observability, span
from worker.connectors.apis import (
    ArbeitnowConnector,
    FourDayWeekConnector,
    HimalayasConnector,
    HnWhoIsHiringConnector,
    JobicyConnector,
    WorkingNomadsConnector,
)
from worker.connectors.ats import (
    GreenhouseAmericasConnector,
    GreenhouseAsiaConnector,
    GreenhouseEuropeConnector,
    LeverAsiaConnector,
    LeverGlobalConnector,
    PersonioConnector,
    RecruiteeConnector,
    TeamtailorConnector,
    WorkableConnector,
)
from worker.connectors.boards import JapanDevConnector, RelocateMeConnector, RemoteFirstJobsConnector
from worker.connectors.djinni import DjinniConnector
from worker.connectors.regional import (
    GetOnBoardConnector,
    HasjobConnector,
    JobTechSwedenConnector,
    RemotePythonConnector,
    WordPressJobsConnector,
)
from worker.connectors.remoteok import RemoteOkConnector
from worker.connectors.rssboards import (
    BerlinStartupJobsConnector,
    CryptoJobsListConnector,
    ElixirJobsConnector,
    GolangProjectsConnector,
    JobspressoConnector,
    PythonOrgJobsConnector,
    RealWorkFromAnywhereConnector,
)
from worker.connectors.wellfound import WellfoundConnector
from worker.connectors.weworkremotely import WeWorkRemotelyConnector
from worker.db import Store
from worker.techstack import enrich, is_tech_job
from worker.tidy import tidy_pending
from worker.http import Disallowed, NotFound, PoliteClient, SourceBlocked, SourceFailed

CAP = 30
INTERVAL_SECONDS = 3600
LOCK_PATH = Path(__file__).resolve().parents[1] / "data" / "schedule.lock"
NOT_CONNECTORS = "LinkedIn, Indeed, Tap.az, gloria.az, job.az"

BUILDERS = {
    "We Work Remotely": WeWorkRemotelyConnector,
    "Remote OK": RemoteOkConnector,
    "Djinni": DjinniConnector,
    "Wellfound": WellfoundConnector,
    "Arbeitnow": ArbeitnowConnector,
    "Himalayas": HimalayasConnector,
    "Jobicy": JobicyConnector,
    "Working Nomads": WorkingNomadsConnector,
    "4 Day Week": FourDayWeekConnector,
    "HN Who is hiring": HnWhoIsHiringConnector,
    "Python.org Jobs": PythonOrgJobsConnector,
    "Crypto Jobs List": CryptoJobsListConnector,
    "Real Work From Anywhere": RealWorkFromAnywhereConnector,
    "Berlin Startup Jobs": BerlinStartupJobsConnector,
    "Golang Projects": GolangProjectsConnector,
    "Elixir Jobs": ElixirJobsConnector,
    "Jobspresso": JobspressoConnector,
    "Relocate.me": RelocateMeConnector,
    "Japan Dev": JapanDevConnector,
    "Remote First Jobs": RemoteFirstJobsConnector,
    "Greenhouse boards (Europe)": GreenhouseEuropeConnector,
    "Greenhouse boards (North America)": GreenhouseAmericasConnector,
    "Greenhouse boards (Asia-Pacific & Middle East)": GreenhouseAsiaConnector,
    "Lever boards (Americas & Europe)": LeverGlobalConnector,
    "Lever boards (Asia-Pacific)": LeverAsiaConnector,
    "Workable boards (Europe)": WorkableConnector,
    "Teamtailor boards (Nordics)": TeamtailorConnector,
    "Recruitee boards (Netherlands)": RecruiteeConnector,
    "Personio boards (Germany)": PersonioConnector,
    "JobTech Platsbanken (Sweden)": JobTechSwedenConnector,
    "Get on Board (Latin America)": GetOnBoardConnector,
    "Hasjob (India)": HasjobConnector,
    "WordPress Jobs": WordPressJobsConnector,
    "Remote Python": RemotePythonConnector,
}


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if not key:
            continue
        # Empty value in .env clears a shell-exported key (e.g. local OPENAI_API_KEY=).
        if value == "":
            os.environ.pop(key, None)
        else:
            os.environ.setdefault(key, value)


def main(argv: list[str]) -> int:
    here = Path(__file__).resolve()
    _load_env(here.parents[2] / ".env")
    _load_env(here.parents[1] / ".env")
    init_observability("ingress-job-worker")
    try:
        return _main(argv)
    finally:
        flush()


def _main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "probe":
        return _probe(argv[2:])
    if len(argv) > 2 or (len(argv) == 2 and argv[1] not in {"list", "schedule"}):
        print('usage: python -m worker [list|schedule|probe ["Source name" ...]]', flush=True)
        return 2
    if len(argv) == 2 and argv[1] == "schedule":
        return _schedule()
    store = Store()
    try:
        if len(argv) == 2:
            _print_jobs(store)
            return 0
        return _run(store)
    finally:
        store.close()


def _schedule() -> int:
    """Repeat the one-pass collect and tidy every hour. One process only."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_PATH.open("a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("scheduled: already running, every 1 hour", flush=True)
        return 0
    print("scheduled: every 1 hour", flush=True)
    while True:
        started = time.monotonic()
        store = Store()
        try:
            _run(store)
        except Exception as exc:
            capture_exception()
            print(f"pass failed: {type(exc).__name__}", flush=True)
        finally:
            store.close()
        wait = INTERVAL_SECONDS - (time.monotonic() - started)
        if wait < 0:
            wait = 0
        print(f"next pass in {int(wait)}s", flush=True)
        time.sleep(wait)


def _run(store: Store) -> int:
    with span("worker.pass"):
        return _run_pass(store)


def _run_pass(store: Store) -> int:
    print("not connectors: " + NOT_CONNECTORS, flush=True)
    for row in store.disabled_sources():
        env_name = row["api_key_env"]
        if env_name:
            if os.environ.get(env_name):
                print(f"{row['name']}: off (key present, HTML is not collected)", flush=True)
            else:
                print(f"{row['name']}: off, {env_name} not set", flush=True)
        else:
            print(f"{row['name']}: off", flush=True)
    client = PoliteClient()
    try:
        for name, builder in BUILDERS.items():
            row = store.source_by_name(name)
            if not row["enabled"] or row["go_decision"] != "go":
                print(f"{name}: skipped, not enabled", flush=True)
                continue
            connector = builder(client, store)
            if _too_soon(store, connector, int(row["id"])):
                continue
            _run_source(store, client, connector, int(row["id"]))
    finally:
        client.close()
    try:
        filled = store.backfill_derived()
        if filled:
            print(f"tech stack backfill: {filled}", flush=True)
    except Exception:
        capture_exception()
    saved, queued = tidy_pending(store.conn)
    if saved or queued:
        print(f"tidy: saved={saved} queued={queued}", flush=True)
    return 0


def _too_soon(store: Store, connector, source_id: int) -> bool:
    """Sources that publish a polling limit are read no more often than that."""
    hours = float(getattr(connector, "min_interval_hours", 0) or 0)
    if hours <= 0:
        return False
    last = store.last_ok_run(source_id)
    if not last:
        return False
    try:
        started = datetime.fromisoformat(last)
    except ValueError:
        return False
    if started.tzinfo is None:
        started = started.astimezone()
    age = datetime.now(timezone.utc) - started
    if age < timedelta(hours=hours):
        print(f"{connector.name}: skipped, read less than {hours:g}h ago", flush=True)
        return True
    return False


def finish_item(connector, item: dict | None) -> dict | None:
    """Tech roles only (the source category decides first). Adds tech_stack,
    job_category, remote and relocation."""
    if not item:
        return None
    if not is_tech_job(str(item.get("title") or ""), item.get("category"), item.get("tags")):
        return None
    enrich(
        item,
        remote_default=bool(getattr(connector, "remote_default", False)),
        relocation_default=bool(getattr(connector, "relocation_default", False)),
    )
    if getattr(connector, "require_remote_or_relocation", False):
        if not (item.get("remote") or item.get("relocation")):
            return None
    credit = getattr(connector, "credit_note", "")
    if credit and not item.get("credit_note"):
        item["credit_note"] = credit
    return item


def _run_source(store: Store, client: PoliteClient, connector, source_id: int) -> None:
    del client
    run_id = store.start_run(source_id)
    found = created = updated = 0
    status = "ok"
    error = None
    try:
        urls = connector.discover()
        found = len(urls)
        for url in urls:
            if created >= CAP:
                break
            try:
                raw = connector.fetch(url)
                item = finish_item(connector, connector.normalize(raw, url))
                if not item:
                    continue
                item["source_name"] = connector.name
                kind = connector.upsert(item)
                if kind == "created":
                    created += 1
                else:
                    updated += 1
            except (Disallowed, NotFound):
                continue
            except (SourceBlocked, SourceFailed):
                raise
            except Exception:
                continue
    except (SourceBlocked, SourceFailed, Disallowed) as exc:
        status = "error"
        error = str(exc)[:500]
    store.finish_run(
        run_id,
        status=status,
        found=found,
        created=created,
        updated=updated,
        error=error,
    )
    print(
        f"{connector.name}: status={status} found={found} created={created} "
        f"updated={updated} error={error or '-'}",
        flush=True,
    )


def _probe(names: list[str]) -> int:
    """Fetch and parse real ads from the named sources (all enabled ones when no
    name is given) into a throw-away SQLite file. The jobs database is not
    touched, even when DATABASE_URL is set. At most 3 ads per source are read."""
    import json
    import tempfile

    wanted = names or list(BUILDERS)
    unknown = [name for name in wanted if name not in BUILDERS]
    if unknown:
        print("unknown source: " + ", ".join(unknown), flush=True)
        return 2
    with tempfile.TemporaryDirectory(prefix="ingress-probe-") as tmp:
        store = Store(Path(tmp) / "probe.sqlite", sqlite_only=True)
        client = PoliteClient()
        try:
            for name in wanted:
                connector = BUILDERS[name](client, store)
                kept = 0
                try:
                    urls = connector.discover()
                    for url in urls:
                        if kept >= 3:
                            break
                        try:
                            item = finish_item(connector, connector.normalize(connector.fetch(url), url))
                        except (Disallowed, NotFound):
                            continue
                        if not item:
                            continue
                        kept += 1
                        print(
                            json.dumps(
                                {
                                    "source": name,
                                    "title": item["title"],
                                    "company": item.get("company"),
                                    "city": item.get("city"),
                                    "remote": item.get("remote"),
                                    "relocation": item.get("relocation"),
                                    "category": item.get("job_category"),
                                    "source_category": item.get("category"),
                                    "tech_stack": item.get("tech_stack"),
                                    "text_chars": len(item.get("text") or ""),
                                    "url": url,
                                },
                                ensure_ascii=False,
                            ),
                            flush=True,
                        )
                    print(f"PROBE {name}: candidates={len(urls)} parsed={kept} status=ok", flush=True)
                except (SourceBlocked, SourceFailed, Disallowed, NotFound) as exc:
                    print(f"PROBE {name}: status=error {str(exc)[:200]}", flush=True)
        finally:
            client.close()
            store.close()
    return 0


def _print_jobs(store: Store) -> None:
    rows = store.list_jobs()
    print(f"jobs={len(rows)}", flush=True)
    for row in rows:
        print(f"{row['title']} | {row['company']} | {row['city']} | {row['source']}", flush=True)
