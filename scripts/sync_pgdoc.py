#!/usr/bin/env python3
"""Import all changed Chinese manuals from pgsty/pgdoc's main branch."""

import argparse
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from . import import_pgdoc

VERSIONS = ("devel", "19", "18", "17")


def sync_all(source: Path, refresh: bool = False, postgres_source: Path = None):
    branch = subprocess.run(
        ["git", "-C", str(source), "branch", "--show-current"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if branch != import_pgdoc.BRANCH:
        raise ValueError(f"pgdoc checkout is on {branch or 'detached HEAD'}, expected {import_pgdoc.BRANCH}")
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    revisions = (json.loads(import_pgdoc.REVISIONS.read_text(encoding="utf-8"))
                 if import_pgdoc.REVISIONS.is_file() else {})
    for version in VERSIONS:
        site = import_pgdoc.SITE
        cached = all((site / path).is_file() for path in (
            f"content/zh/postgresql/{version}/_index.html",
            f"data/manual_nav/zh/{version}.json",
            f"static/zh/manual-nav/{version}.json",
        ))
        if not refresh and cached and revisions.get(version) == revision:
            print(f"Using imported pgdoc {version} manual from {revision[:12]}", flush=True)
            continue
        print(f"Importing pgdoc {version} manual from {revision[:12]}", flush=True)
        import_pgdoc.import_pgdoc(source, version, postgres_source=postgres_source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source_options = parser.add_mutually_exclusive_group()
    source_options.add_argument("--source", type=Path, help="local pgdoc main checkout")
    source_options.add_argument("--remote", default=import_pgdoc.REMOTE, help="pgdoc Git remote")
    parser.add_argument("--refresh", action="store_true", help="rebuild even if the revision is unchanged")
    parser.add_argument("--postgres-source", type=Path, help="local PostgreSQL Git checkout")
    args = parser.parse_args()
    try:
        postgres_source = args.postgres_source.resolve() if args.postgres_source else None
        if args.source:
            sync_all(args.source.resolve(), args.refresh, postgres_source)
        else:
            with TemporaryDirectory(prefix="pgdoc-main-") as temporary:
                source = Path(temporary) / "pgdoc"
                import_pgdoc.fetch_pgdoc(args.remote, source)
                sync_all(source, args.refresh, postgres_source)
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Chinese manual sync failed: {error}\n")


if __name__ == "__main__":
    main()
