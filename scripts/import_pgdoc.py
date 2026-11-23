#!/usr/bin/env python3
"""Build and import a Chinese manual from pgsty/pgdoc's zh/ tree."""

import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from .import_postgres_html import SITE, VERSION, import_docs

REVISIONS = SITE / "data" / "manual-sources-zh.json"
REMOTE = "https://github.com/pgsty/pgdoc.git"
BRANCH = "main"
POSTGRES_REMOTE = "https://github.com/postgres/postgres.git"


def recorded_postgres_commits(versions):
    revisions = SITE / "data" / "manual-sources.json"
    recorded = json.loads(revisions.read_text(encoding="utf-8")) if revisions.is_file() else {}
    commits = {version: recorded.get(version) for version in versions}
    missing = [version for version, commit in commits.items() if not commit]
    if missing:
        raise ValueError(f"PostgreSQL source commit is required for {', '.join(missing)}")
    return commits


def pg20_snapshot(source: Path):
    makefile = source / "zh" / "20" / "Makefile"
    if not makefile.is_file():
        return None
    text = makefile.read_text(encoding="utf-8")
    if not re.search(r"^PGDOC_SOURCE_SHA256\s*[?:]?=", text, re.MULTILINE):
        return None
    match = re.search(r"^#.*\(snapshot ([^)]+)\)", text, re.MULTILINE)
    if not match:
        raise ValueError("pgdoc PG20 declares a source archive without a snapshot timestamp; use PG_COMMIT")
    # pgdoc writes dates such as "16-Oct-2026 08:22 UTC".
    try:
        snapshot = parsedate_to_datetime(match[1].replace("-", " ", 2).replace(" UTC", " +0000"))
        if snapshot.tzinfo is None:
            raise ValueError("timestamp is missing a timezone")
    except ValueError as error:
        raise ValueError(f"Invalid pgdoc PG20 snapshot timestamp {match[1]!r}; use PG_COMMIT") from error
    return snapshot.astimezone(timezone.utc)


def pg20_snapshot_commit(repository: Path, snapshot: datetime):
    for ref in ("refs/remotes/origin/master", "refs/heads/master"):
        result = subprocess.run(
            ["git", "-C", str(repository), "rev-list", "--first-parent", "-1",
             f"--before={snapshot.isoformat()}", ref],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise ValueError(f"PostgreSQL master history has no commit for pgdoc PG20 snapshot {snapshot.isoformat()}")


def prepare_postgres_sources(source: Path, versions, postgres_source: Path,
                             postgres_remote: str, destination: Path):
    snapshot = pg20_snapshot(source) if "devel" in versions else None
    recorded = [version for version in versions if version != "devel" or snapshot is None]
    commits = recorded_postgres_commits(recorded) if recorded else {}
    if postgres_source is None:
        postgres_source = destination
        fetch_postgres_commits(postgres_remote, postgres_source, commits)
        if snapshot:
            # Fetch history on both sides of the cutoff without cloning the full repository.
            since = (snapshot - timedelta(days=30)).isoformat()
            subprocess.run(
                ["git", "-C", str(postgres_source), "fetch", "--quiet", "--no-tags",
                 f"--shallow-since={since}", "origin", "+refs/heads/master:refs/remotes/origin/master"],
                check=True,
            )
    if snapshot:
        commits["devel"] = pg20_snapshot_commit(postgres_source, snapshot)
        print(f"Using PostgreSQL {commits['devel'][:12]} for pgdoc PG20 snapshot {snapshot.isoformat()}",
              flush=True)
    return postgres_source, commits


def fetch_postgres_commits(remote: str, destination: Path, commits):
    """Fetch only the PostgreSQL revisions needed by the Chinese manuals."""
    subprocess.run(["git", "init", "--quiet", str(destination)], check=True)
    subprocess.run(["git", "-C", str(destination), "remote", "add", "origin", remote], check=True)
    for version, commit in commits.items():
        subprocess.run(
            ["git", "-C", str(destination), "fetch", "--quiet", "--no-tags", "--depth", "1",
             "origin", f"+{commit}:refs/heads/pgdoc-{version}"],
            check=True,
        )


def fetch_pgdoc(remote: str, destination: Path):
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", "--no-tags",
         "--branch", BRANCH, remote, str(destination)],
        check=True,
    )


def import_pgdoc(source: Path, version: str, html_dir: Path = None,
                 postgres_source: Path = None, postgres_commit: str = None):
    if not VERSION.fullmatch(version):
        raise ValueError("Version must be 'devel' or a PostgreSQL major version")
    major = "20" if version == "devel" else version
    branch = subprocess.run(
        ["git", "-C", str(source), "branch", "--show-current"],
        capture_output=True, text=True, check=False,
    )
    if branch.returncode == 0 and branch.stdout.strip() not in ("", BRANCH):
        raise ValueError(f"pgdoc checkout is on {branch.stdout.strip()}, expected {BRANCH}")
    manual_dir = source / "zh" / major
    if not manual_dir.is_dir():
        raise FileNotFoundError(f"pgdoc translation directory not found: {manual_dir}")
    if postgres_commit and not postgres_source:
        raise ValueError("PostgreSQL source is required with a source commit")
    if html_dir is None:
        # pgdoc's Makefile writes generated files and caches beside its sources.
        # Stage the needed version so a read-only checkout remains untouched.
        with TemporaryDirectory(prefix="pgdoc-build-") as temporary:
            staged = Path(temporary) / "pgdoc"
            staged_manual = staged / "zh" / major
            staged_manual.parent.mkdir(parents=True)
            shutil.copytree(manual_dir, staged_manual, ignore=shutil.ignore_patterns("html"))
            shutil.copytree(source / "bin", staged / "bin")
            shutil.copytree(source / "deps", staged / "deps")
            build_script = staged / "bin" / "build_standalone_docsrc.sh"
            script = build_script.read_text(encoding="utf-8")
            # The upstream probe uses head under pipefail. GNU Make can receive
            # SIGPIPE after head exits, causing a false "GNU Make is required".
            fragile_probe = 'if ! "${MAKE_CMD}" --version 2>/dev/null | head -n 1 | grep -q "GNU Make"; then'
            robust_probe = 'if [[ "$("${MAKE_CMD}" --version 2>/dev/null)" != GNU\\ Make* ]]; then'
            if fragile_probe in script:
                build_script.write_text(script.replace(fragile_probe, robust_probe), encoding="utf-8")
            build_env = os.environ.copy()
            if postgres_source:
                if not postgres_commit:
                    snapshot = pg20_snapshot(source) if version == "devel" else None
                    postgres_commit = (pg20_snapshot_commit(postgres_source, snapshot) if snapshot
                                       else recorded_postgres_commits((version,))[version])
                staged_postgres = Path(temporary) / "postgres"
                subprocess.run(
                    ["git", "clone", "--shared", "--no-checkout", "--quiet",
                     str(postgres_source.resolve()), str(staged_postgres)],
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", str(staged_postgres), "checkout", "--detach", "--quiet", postgres_commit],
                    check=True,
                )
                build_env["PGDOC_SOURCE_DIR"] = str(staged_postgres)
                build_env["PGDOC_SOURCE_COMMIT"] = postgres_commit
            subprocess.run(["make", "-C", str(staged_manual), "html"], check=True, env=build_env)
            built_html = staged_manual / "html"
            if not (built_html / "index.html").is_file():
                raise FileNotFoundError(f"Chinese HTML manual not found: {built_html / 'index.html'}")
            import_docs(built_html, version, language="zh")
    else:
        if not (html_dir / "index.html").is_file():
            raise FileNotFoundError(f"Chinese HTML manual not found: {html_dir / 'index.html'}")
        import_docs(html_dir, version, language="zh")
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if revision.returncode == 0:
        revisions = json.loads(REVISIONS.read_text(encoding="utf-8")) if REVISIONS.is_file() else {}
        revisions[version] = revision.stdout.strip()
        REVISIONS.parent.mkdir(parents=True, exist_ok=True)
        REVISIONS.write_text(json.dumps(revisions, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source_options = parser.add_mutually_exclusive_group()
    source_options.add_argument("--source", type=Path, help="local pgsty/pgdoc main checkout")
    source_options.add_argument("--remote", default=REMOTE, help="pgsty/pgdoc Git remote")
    parser.add_argument("--version", required=True, help="major version or devel (pgdoc zh/20)")
    parser.add_argument("--html-dir", type=Path, help="already built chunked HTML directory")
    parser.add_argument("--postgres-source", type=Path, help="local PostgreSQL Git checkout for offline build")
    parser.add_argument("--postgres-commit", help="override the PostgreSQL commit used for the Chinese build")
    parser.add_argument("--postgres-remote", default=POSTGRES_REMOTE, help="PostgreSQL Git remote for automatic source fetch")
    args = parser.parse_args()
    try:
        if not VERSION.fullmatch(args.version):
            raise ValueError("Version must be 'devel' or a PostgreSQL major version")
        html_dir = args.html_dir.resolve() if args.html_dir else None
        postgres_source = args.postgres_source.resolve() if args.postgres_source else None
        with TemporaryDirectory(prefix="pgdoc-import-") as temporary:
            if args.source:
                source = args.source.resolve()
            else:
                source = Path(temporary) / "pgdoc"
                fetch_pgdoc(args.remote, source)
            commit = args.postgres_commit
            if html_dir is None:
                if not commit:
                    postgres_source, commits = prepare_postgres_sources(
                        source, (args.version,), postgres_source, args.postgres_remote,
                        Path(temporary) / "postgres",
                    )
                    commit = commits[args.version]
                elif postgres_source is None:
                    postgres_source = Path(temporary) / "postgres"
                    fetch_postgres_commits(args.postgres_remote, postgres_source, {args.version: commit})
            import_pgdoc(source, args.version, html_dir, postgres_source, commit)
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Chinese manual import failed: {error}\n")


if __name__ == "__main__":
    main()
