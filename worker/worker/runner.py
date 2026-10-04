"""One pass over the enabled connectors, or the same pass every hour."""

from __future__ import annotations

import fcntl
import os
import time
from pathlib import Path

from worker.observability import capture_exception, flush, init_observability, span
from worker.connectors.boss import BossConnector
from worker.connectors.busy import BusyConnector
from worker.connectors.djinni import DjinniConnector
from worker.connectors.ejob import EjobConnector
from worker.connectors.glorri import GlorriConnector
from worker.connectors.hellojob import HelloJobConnector
from worker.connectors.hh1 import Hh1Connector
from worker.connectors.hrx import HrxConnector
from worker.connectors.jobsearch import JobSearchConnector
from worker.connectors.remoteok import RemoteOkConnector
from worker.connectors.wellfound import WellfoundConnector
from worker.connectors.weworkremotely import WeWorkRemotelyConnector
from worker.connectors.workaz import WorkAzConnector
from worker.db import Store
from worker.tidy import tidy_pending
from worker.http import Disallowed, NotFound, PoliteClient, SourceBlocked, SourceFailed

CAP = 30
INTERVAL_SECONDS = 3600
LOCK_PATH = Path(__file__).resolve().parents[1] / "data" / "schedule.lock"
NOT_CONNECTORS = "LinkedIn, Indeed, Tap.az, gloria.az, job.az"

BUILDERS = {
    "Busy.az": BusyConnector,
    "Boss.az": BossConnector,
    "HelloJob": HelloJobConnector,
    "We Work Remotely": WeWorkRemotelyConnector,
    "Remote OK": RemoteOkConnector,
    "Glorri": GlorriConnector,
    "JobSearch.az": JobSearchConnector,
    "HRX": HrxConnector,
    "Work.az": WorkAzConnector,
    "eJob.az": EjobConnector,
    "hh1.az": Hh1Connector,
    "Djinni": DjinniConnector,
    "Wellfound": WellfoundConnector,
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
    if len(argv) > 2 or (len(argv) == 2 and argv[1] not in {"list", "schedule"}):
        print("usage: python -m worker [list|schedule]", flush=True)
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
            _run_source(store, client, builder(client, store), int(row["id"]))
    finally:
        client.close()
    saved, queued = tidy_pending(store.conn)
    if saved or queued:
        print(f"tidy: saved={saved} queued={queued}", flush=True)
    return 0


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
                item = connector.normalize(raw, url)
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


def _print_jobs(store: Store) -> None:
    rows = store.list_jobs()
    print(f"jobs={len(rows)}", flush=True)
    for row in rows:
        print(f"{row['title']} | {row['company']} | {row['city']} | {row['source']}", flush=True)
