#!/usr/bin/env python3
"""Build PostgreSQL's HTML manual when needed, then import it into Hugo."""

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from .import_postgres_html import SITE, VERSION, import_docs

REVISIONS = SITE / "data" / "manual-sources.json"


def git_revision(source):
    if not source.is_dir():
        return None
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def source_is_dirty(source):
    result = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def source_version(source):
    configure_ac = source / "configure.ac"
    if not configure_ac.is_file():
        return None
    match = re.search(r"AC_INIT\(\[PostgreSQL\],\s*\[([^]]+)\]", configure_ac.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def validate_version(source, version):
    found = source_version(source)
    if found is None:
        return
    major_match = re.match(r"[0-9]+", found)
    major = major_match.group(0) if major_match else ""
    if version == "devel":
        valid = found.endswith("devel")
    else:
        tree = ".".join(found.split(".")[:2]) if major and int(major) < 10 else major
        valid = not found.endswith("devel") and tree == version
    if not valid:
        raise ValueError(f"PostgreSQL source is {found}, but requested manual version is {version}")


def read_revisions():
    if REVISIONS.is_file():
        return json.loads(REVISIONS.read_text(encoding="utf-8"))
    return {}


def write_revision(version, revision):
    if not revision:
        return
    revisions = read_revisions()
    revisions[version] = revision
    REVISIONS.parent.mkdir(parents=True, exist_ok=True)
    REVISIONS.write_text(json.dumps(revisions, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_html(source, build_dir, force=False):
    missing = [tool for tool in ("bison", "flex", "xmllint", "xsltproc") if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(
            "Cannot build PostgreSQL HTML: missing " + ", ".join(missing)
            + ". Install PostgreSQL's documentation build dependencies "
            + "(bison, flex, libxml2-utils, xsltproc, docbook-xml, docbook-xsl), "
            + "or set HTML_DIR to an already built doc/src/sgml/html directory."
        )
    if not (source / "configure").is_file():
        raise FileNotFoundError(f"PostgreSQL configure script not found: {source / 'configure'}")
    build_dir.mkdir(parents=True, exist_ok=True)
    if not (build_dir / "config.status").is_file():
        print(f"Configuring PostgreSQL documentation build in {build_dir}", flush=True)
        subprocess.run(
            [str((source / "configure").resolve()), "--without-readline", "--without-zlib", "--without-icu"],
            cwd=build_dir, check=True,
        )
    command = ["make"]
    if force:
        command.append("-B")
    command += ["-C", str(build_dir / "doc" / "src" / "sgml"), "html", "STYLE=website"]
    subprocess.run(command, check=True)


def sync_manual(source, build_dir, html_dir, version, refresh=False):
    if not VERSION.fullmatch(version):
        raise ValueError("Version must be 'devel' or a PostgreSQL major version")
    source = source.resolve()
    build_dir = build_dir.resolve()
    html_dir = html_dir.resolve()
    cached_index = SITE / "content" / "en" / "postgresql" / version / "_index.html"
    cached_navigation = SITE / "data" / "manual_nav" / f"{version}.json"
    public_navigation = SITE / "static" / "manual-nav" / f"{version}.json"
    revision = git_revision(source)
    revisions = read_revisions()
    default_html_dir = build_dir / "doc" / "src" / "sgml" / "html"

    if html_dir != default_html_dir:
        if not (html_dir / "index.html").is_file():
            raise FileNotFoundError(f"HTML_DIR has no index.html: {html_dir}")
        validate_version(source, version)
        import_docs(html_dir, version)
        write_revision(version, revision)
        return

    if (not refresh and cached_index.is_file() and cached_navigation.is_file() and public_navigation.is_file() and revision
            and revisions.get(version) == revision and not source_is_dirty(source)):
        print(f"Using imported PostgreSQL {version} manual from source commit {revision[:12]}")
        return

    if (not refresh and cached_index.is_file() and cached_navigation.is_file() and public_navigation.is_file()
            and revision is None and version in revisions):
        print(f"Using imported PostgreSQL {version} manual; PostgreSQL source checkout is unavailable")
        return

    validate_version(source, version)
    build_html(source, build_dir, refresh)
    import_docs(html_dir, version)
    write_revision(version, revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--html-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    try:
        sync_manual(args.source, args.build_dir, args.html_dir, args.version, args.refresh)
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Manual sync failed: {error}\n")


if __name__ == "__main__":
    main()
