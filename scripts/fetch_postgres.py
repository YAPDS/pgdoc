#!/usr/bin/env python3
"""Fetch PostgreSQL source for a build, sync manuals, then discard the checkout."""

import argparse
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from .sync_versions import RELEASES, sync_all

DEFAULT_REMOTE = "https://github.com/postgres/postgres.git"


def fetch_source(remote: str, destination: Path):
    print(f"Fetching PostgreSQL source from {remote}", flush=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", "--no-tags",
         "--branch", "master", remote, str(destination)],
        check=True,
    )
    refspecs = [
        f"+refs/heads/REL_{version}_STABLE:refs/remotes/origin/REL_{version}_STABLE"
        for version in RELEASES
    ]
    subprocess.run(
        ["git", "-C", str(destination), "fetch", "--depth", "1", "--no-tags", "origin", *refspecs],
        check=True,
    )


def fetch_and_sync(remote: str, refresh=False):
    with TemporaryDirectory(prefix="postgres-manual-build-") as temporary:
        root = Path(temporary)
        source = root / "postgres"
        fetch_source(remote, source)
        sync_all(source, root / "build", refresh, pin_cached=not refresh)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default=DEFAULT_REMOTE, help="PostgreSQL Git remote URL")
    parser.add_argument("--refresh", action="store_true", help="regenerate all manuals")
    args = parser.parse_args()
    try:
        fetch_and_sync(args.remote, args.refresh)
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Manual fetch failed: {error}\n")


if __name__ == "__main__":
    main()
