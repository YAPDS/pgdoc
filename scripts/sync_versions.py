#!/usr/bin/env python3
"""Import the devel manual and PostgreSQL 19, 18, and 17 release manuals."""

import argparse
from pathlib import Path
import subprocess
import tarfile

from .import_postgres_html import SITE, import_docs
from .sync_postgres import (build_html, git_revision, read_revisions,
                            sync_manual, validate_version, write_revision)

RELEASES = ("19", "18", "17")


def ref_revision(repository: Path, ref: str):
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--verify", f"{ref}^{{commit}}"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def has_import(version: str):
    return all(path.is_file() for path in (
        SITE / "content" / "en" / "postgresql" / version / "_index.html",
        SITE / "data" / "manual_nav" / f"{version}.json",
        SITE / "static" / "manual-nav" / f"{version}.json",
    ))


def export_ref(repository: Path, ref: str, destination: Path):
    marker = destination / ".export-complete"
    if marker.is_file():
        return
    destination.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        ["git", "-C", str(repository), "archive", "--format=tar", ref],
        stdout=subprocess.PIPE,
    )
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                path = Path(member.name)
                if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                    raise ValueError(f"Unsafe path in {ref}: {member.name}")
                archive.extract(member, destination)
        if process.wait() != 0:
            raise RuntimeError(f"Could not export {ref} from {repository}")
        marker.write_text(ref + "\n", encoding="utf-8")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()


def sync_release(repository: Path, build_root: Path, version: str, refresh=False, pin_cached=False):
    ref = f"refs/remotes/origin/REL_{version}_STABLE"
    revision = ref_revision(repository, ref)
    cached = has_import(version)
    recorded = read_revisions().get(version)
    if not refresh and cached and recorded and (pin_cached or revision is None or revision == recorded):
        print(f"Using imported PostgreSQL {version} manual from source commit {recorded[:12]}", flush=True)
        if revision and revision != recorded:
            print(f"PostgreSQL {version} upstream is at {revision[:12]}; run make refresh to update", flush=True)
        return
    if not revision:
        raise RuntimeError(f"Cannot generate PostgreSQL {version}: local Git ref {ref} is unavailable")
    source = build_root / "sources" / f"postgres-{version}-{revision[:12]}"
    build_dir = build_root / f"postgres-{version}-{revision[:12]}"
    print(f"Exporting PostgreSQL {version} source from {revision[:12]}", flush=True)
    export_ref(repository, ref, source)
    validate_version(source, version)
    build_html(source, build_dir, refresh)
    import_docs(build_dir / "doc" / "src" / "sgml" / "html", version)
    write_revision(version, revision)


def sync_all(repository: Path, build_root: Path, refresh=False, pin_cached=False):
    if pin_cached and has_import("devel") and read_revisions().get("devel"):
        recorded = read_revisions()["devel"]
        revision = git_revision(repository)
        print(f"Using imported PostgreSQL devel manual from source commit {recorded[:12]}", flush=True)
        if revision and revision != recorded:
            print(f"PostgreSQL devel upstream is at {revision[:12]}; run make refresh to update", flush=True)
    else:
        sync_manual(repository, build_root / "postgres", build_root / "postgres" / "doc" / "src" / "sgml" / "html", "devel", refresh)
    for version in RELEASES:
        sync_release(repository, build_root, version, refresh, pin_cached)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="explicit PostgreSQL Git checkout")
    parser.add_argument("--build-root", type=Path, default=SITE / ".build")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    try:
        sync_all(args.source.resolve(), args.build_root.resolve(), args.refresh)
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Manual sync failed: {error}\n")


if __name__ == "__main__":
    main()
