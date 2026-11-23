import os
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
import subprocess
from unittest.mock import patch

from scripts import import_pgdoc, import_postgres_html, sync_pgdoc, sync_postgres, sync_versions


class ImportTests(unittest.TestCase):
    def test_import_preserves_chunk_urls_and_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            source.mkdir()
            (source / "index.html").write_text(
                '<html><head><title>PostgreSQL 99 Documentation</title></head>'
                '<body><a href="intro.html">Intro</a><img src="diagram.svg"></body></html>',
                encoding="utf-8",
            )
            (source / "intro.html").write_text(
                '<html><head><title>Introduction</title></head><body><h1>Intro</h1>'
                '<pre>two  spaces\n*literal* [not markdown](page.html)</pre></body></html>',
                encoding="utf-8",
            )
            (source / "diagram.svg").write_text('<svg/>', encoding="utf-8")
            previous = root / "content/en/postgresql/99/intro.md"
            previous.parent.mkdir(parents=True)
            previous.write_text(import_postgres_html.MARKER + "\nold generated page", encoding="utf-8")
            user_page = previous.parent / "notes.md"
            user_page.write_text("User maintained notes", encoding="utf-8")
            with patch.object(import_postgres_html, "SITE", root):
                import_postgres_html.import_docs(source, "99")
            index = (root / "content/en/postgresql/99/_index.html").read_text(encoding="utf-8")
            intro = (root / "content/en/postgresql/99/intro.html").read_text(encoding="utf-8")
            self.assertIn('href="intro.html"', index)
            self.assertIn('weight = 1', index)
            self.assertIn('url = "/postgresql/99/intro.html"', intro)
            self.assertIn('<pre>two  spaces\n*literal* [not markdown](page.html)</pre>', intro)
            self.assertFalse(previous.exists())
            self.assertTrue(user_page.exists())
            self.assertTrue((root / "static/postgresql/99/diagram.svg").is_file())
            self.assertEqual((root / "data/manual_nav/99.json").read_bytes(),
                             (root / "static/manual-nav/99.json").read_bytes())

    def test_navigation_follows_part_chapter_and_section(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "index.html").write_text(
                '<div class="toc"><dl><dt><a href="tutorial.html">I. Tutorial</a></dt>'
                '<dd><dl><dt><a href="tutorial-start.html">1. Getting Started</a></dt></dl></dd>'
                '</dl></div>', encoding="utf-8",
            )
            (source / "tutorial-start.html").write_text(
                '<div class="toc"><dl><dt><a href="tutorial-install.html">1.1. Installation</a></dt>'
                '</dl></div>', encoding="utf-8",
            )
            (source / "tutorial-install.html").write_text('<html></html>', encoding="utf-8")
            navigation = import_postgres_html.build_navigation(source, list(source.glob("*.html")))
            self.assertEqual(navigation["sections"][0]["title"], "I. Tutorial")
            self.assertEqual(navigation["sections"][0]["children"][0]["children"][0]["page"], "tutorial-install.html")
            self.assertEqual(navigation["parents"]["tutorial-install.html"], ["tutorial.html", "tutorial-start.html"])

    def test_imports_pgdoc_to_chinese_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "pgdoc"
            (source / "zh/18/html").mkdir(parents=True)
            (source / "zh/18/html/index.html").write_text(
                '<html><head><title>PostgreSQL 18 中文文档</title></head>'
                '<body><a href="intro.html">简介</a><img src="diagram.svg"></body></html>',
                encoding="utf-8",
            )
            (source / "zh/18/html/intro.html").write_text(
                '<html><head><title>简介</title></head><body><h1>简介</h1></body></html>',
                encoding="utf-8",
            )
            (source / "zh/18/html/diagram.svg").write_text('<svg/>', encoding="utf-8")
            with (patch.object(import_postgres_html, "SITE", root),
                  patch.object(import_pgdoc, "SITE", root),
                  patch.object(import_pgdoc, "REVISIONS", root / "data/manual-sources-zh.json")):
                import_pgdoc.import_pgdoc(source, "18", source / "zh/18/html")
            intro = (root / "content/zh/postgresql/18/intro.html").read_text(encoding="utf-8")
            self.assertIn('url = "/zh/postgresql/18/intro.html"', intro)
            self.assertTrue((root / "static/zh/postgresql/18/diagram.svg").is_file())
            self.assertEqual((root / "data/manual_nav/zh/18.json").read_bytes(),
                             (root / "static/zh/manual-nav/18.json").read_bytes())

    def test_pgdoc_fetch_uses_main_branch(self):
        with patch.object(import_pgdoc.subprocess, "run") as run:
            import_pgdoc.fetch_pgdoc("https://github.com/pgsty/pgdoc.git", Path("/tmp/pgdoc"))
        self.assertIn("main", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["check"], True)

    def test_pgdoc_sync_skips_matching_snapshots_and_refreshes_all(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            revisions = root / "data/manual-sources-zh.json"
            revisions.parent.mkdir()
            revisions.write_text('{"17":"abc123","18":"abc123","19":"abc123","devel":"abc123"}',
                                 encoding="utf-8")
            (revisions.parent / "manual-sources.json").write_text(revisions.read_text(), encoding="utf-8")
            for version in sync_pgdoc.VERSIONS:
                for path in (f"content/zh/postgresql/{version}/_index.html",
                             f"data/manual_nav/zh/{version}.json",
                             f"static/zh/manual-nav/{version}.json"):
                    target = root / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("cached", encoding="utf-8")

            def git(command, **kwargs):
                value = "main" if "branch" in command else "abc123"
                return CompletedProcess(command, 0, value + "\n", "")

            with (patch.object(sync_pgdoc.import_pgdoc, "SITE", root),
                  patch.object(sync_pgdoc.import_pgdoc, "REVISIONS", revisions),
                  patch.object(sync_pgdoc.subprocess, "run", side_effect=git),
                  patch.object(sync_pgdoc.import_pgdoc, "import_pgdoc") as importer):
                sync_pgdoc.sync_all(root)
                importer.assert_not_called()
                sync_pgdoc.sync_all(root, refresh=True, postgres_source=root)
                self.assertEqual([call.args[1] for call in importer.call_args_list],
                                 list(sync_pgdoc.VERSIONS))

    def test_pgdoc_fetches_recorded_postgres_commit_for_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "upstream"
            upstream.mkdir()
            subprocess.run(["git", "init", "--quiet", str(upstream)], check=True)
            (upstream / "configure.ac").write_text("PostgreSQL source", encoding="utf-8")
            subprocess.run(["git", "-C", str(upstream), "add", "configure.ac"], check=True)
            subprocess.run(["git", "-C", str(upstream), "-c", "user.name=Test",
                            "-c", "user.email=test@example.com", "commit", "--quiet", "-m", "source"], check=True)
            commit = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD"],
                                    capture_output=True, text=True, check=True).stdout.strip()
            destination = root / "fetched"
            import_pgdoc.fetch_postgres_commits(str(upstream), destination, {"devel": commit})
            staged = root / "staged"
            subprocess.run(["git", "clone", "--shared", "--no-checkout", "--quiet",
                            str(destination), str(staged)], check=True)
            subprocess.run(["git", "-C", str(staged), "checkout", "--detach", "--quiet", commit], check=True)
            self.assertEqual((staged / "configure.ac").read_text(encoding="utf-8"), "PostgreSQL source")

    def test_pgdoc_selects_new_pg20_baseline_when_snapshot_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "postgres"
            subprocess.run(["git", "init", "--quiet", "--initial-branch=master", str(upstream)], check=True)
            commits = []
            for day in (16, 17, 18):
                subprocess.run(
                    ["git", "-C", str(upstream), "-c", "user.name=Test", "-c", "user.email=test@example.com",
                     "commit", "--quiet", "--allow-empty", "-m", f"source {day}"],
                    check=True,
                    env={**os.environ, "GIT_AUTHOR_DATE": f"2026-10-{day}T08:00:00Z",
                         "GIT_COMMITTER_DATE": f"2026-10-{day}T08:00:00Z"},
                )
                commits.append(subprocess.check_output(
                    ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True,
                ).strip())

            makefile = root / "zh/20/Makefile"
            makefile.parent.mkdir(parents=True)
            (root / "data").mkdir()
            (root / "data/manual-sources.json").write_text(
                f'{{"devel":"{commits[2]}","18":"{commits[2]}"}}', encoding="utf-8",
            )
            with patch.object(import_pgdoc, "SITE", root):
                for day, sha, expected in ((16, "a", commits[0]), (17, "b", commits[1])):
                    with self.subTest(day=day):
                        makefile.write_text(
                            f"# PG20 baseline (snapshot {day}-Oct-2026 08:22 UTC).\n"
                            f"PGDOC_SOURCE_SHA256 ?= {sha * 64}\n", encoding="utf-8",
                        )
                        _, selected = import_pgdoc.prepare_postgres_sources(
                            root, ("devel", "18"), None, upstream.as_uri(), root / f"fetched-{day}",
                        )
                        self.assertEqual(selected, {"devel": expected, "18": commits[2]})

    def test_pgdoc_sync_fetches_only_needed_postgres_commits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").mkdir()
            (root / "data/manual-sources.json").write_text('{"devel":"pinned"}', encoding="utf-8")
            revisions = root / "data/manual-sources-zh.json"
            revisions.write_text('{"19":"latest","18":"latest","17":"latest"}', encoding="utf-8")
            for version in ("19", "18", "17"):
                for path in (f"content/zh/postgresql/{version}/_index.html",
                             f"data/manual_nav/zh/{version}.json",
                             f"static/zh/manual-nav/{version}.json"):
                    target = root / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("cached", encoding="utf-8")

            def git(command, **kwargs):
                value = "main" if "branch" in command else "latest"
                return CompletedProcess(command, 0, value + "\n", "")

            with (patch.object(sync_pgdoc.import_pgdoc, "SITE", root),
                  patch.object(sync_pgdoc.import_pgdoc, "REVISIONS", revisions),
                  patch.object(sync_pgdoc.subprocess, "run", side_effect=git),
                  patch.object(sync_pgdoc.import_pgdoc, "fetch_postgres_commits") as fetch,
                  patch.object(sync_pgdoc.import_pgdoc, "import_pgdoc") as importer):
                sync_pgdoc.sync_all(root, postgres_remote="local-mirror")
                self.assertEqual(fetch.call_args.args[0], "local-mirror")
                self.assertEqual(fetch.call_args.args[2], {"devel": "pinned"})
                self.assertEqual(importer.call_args.args[1], "devel")
                self.assertEqual(importer.call_args.kwargs["postgres_source"], fetch.call_args.args[1])

    def test_pgdoc_build_stages_read_only_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "pgdoc"
            postgres_source = root / "postgres"
            postgres_source.mkdir()
            (root / "data").mkdir()
            (root / "data/manual-sources.json").write_text('{"18":"abc123"}', encoding="utf-8")
            for name in ("zh/18", "bin", "deps"):
                (source / name).mkdir(parents=True)
            (source / "zh/18/Makefile").write_text("html:\n", encoding="utf-8")
            (source / "bin/build_standalone_docsrc.sh").write_text("#!/bin/sh\n", encoding="utf-8")

            def run(command, **kwargs):
                if command[:2] == ["git", "clone"]:
                    Path(command[-1]).mkdir()
                if command[0] == "make":
                    built_html = Path(command[2]) / "html"
                    self.assertNotEqual(Path(command[2]), source / "zh/18")
                    self.assertNotEqual(kwargs["env"]["PGDOC_SOURCE_DIR"], str(postgres_source))
                    self.assertTrue(Path(kwargs["env"]["PGDOC_SOURCE_DIR"]).is_dir())
                    self.assertEqual(kwargs["env"]["PGDOC_SOURCE_COMMIT"], "abc123")
                    built_html.mkdir()
                    (built_html / "index.html").write_text(
                        '<html><head><title>中文手册</title></head><body>正文</body></html>',
                        encoding="utf-8",
                    )
                return CompletedProcess(command, 1, "", "")

            with (patch.object(import_postgres_html, "SITE", root),
                  patch.object(import_pgdoc, "SITE", root),
                  patch.object(import_pgdoc.subprocess, "run", side_effect=run)):
                import_pgdoc.import_pgdoc(source, "18", postgres_source=postgres_source)
            self.assertFalse((source / "zh/18/html").exists())
            self.assertTrue((root / "content/zh/postgresql/18/_index.html").is_file())

    def test_rejects_unsafe_version(self):
        with self.assertRaises(ValueError):
            import_postgres_html.import_docs(Path("."), "../../bad")

    def test_build_reuses_imported_pages_for_same_source_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cached_index = root / "content/en/postgresql/devel/_index.html"
            cached_index.parent.mkdir(parents=True)
            cached_index.write_text("cached manual", encoding="utf-8")
            revisions = root / "data/manual-sources.json"
            revisions.parent.mkdir()
            revisions.write_text('{"devel": "abc123"}', encoding="utf-8")
            navigation = root / "data/manual_nav/devel.json"
            navigation.parent.mkdir()
            navigation.write_text('{"sections":[],"parents":{}}', encoding="utf-8")
            public_navigation = root / "static/manual-nav/devel.json"
            public_navigation.parent.mkdir(parents=True)
            public_navigation.write_text('{"sections":[],"parents":{}}', encoding="utf-8")
            with (patch.object(sync_postgres, "SITE", root),
                  patch.object(sync_postgres, "REVISIONS", revisions),
                  patch.object(sync_postgres, "git_revision", return_value="abc123"),
                  patch.object(sync_postgres, "source_is_dirty", return_value=False),
                  patch.object(sync_postgres, "build_html") as build):
                sync_postgres.sync_manual(root, root / "build", root / "build/doc/src/sgml/html", "devel")
                build.assert_not_called()

    def test_rejects_mislabeled_source_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "configure.ac").write_text("AC_INIT([PostgreSQL], [20devel], [bugs])", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requested manual version is 18"):
                sync_postgres.validate_version(source, "18")

    def test_distinguishes_pre_10_major_versions(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "configure.ac").write_text("AC_INIT([PostgreSQL], [9.5.25], [bugs])", encoding="utf-8")
            sync_postgres.validate_version(source, "9.5")
            with self.assertRaisesRegex(ValueError, "requested manual version is 9.6"):
                sync_postgres.validate_version(source, "9.6")

    def test_accepts_release_candidate_for_major_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "configure.ac").write_text("AC_INIT([PostgreSQL], [19rc1], [bugs])", encoding="utf-8")
            sync_postgres.validate_version(source, "19")

    def test_release_sync_reuses_matching_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in ("content/en/postgresql/19/_index.html", "data/manual_nav/19.json",
                             "static/manual-nav/19.json"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("cached", encoding="utf-8")
            with (patch.object(sync_versions, "SITE", root),
                  patch.object(sync_versions, "ref_revision", return_value="abc123"),
                  patch.object(sync_versions, "read_revisions", return_value={"19": "abc123"}),
                  patch.object(sync_versions, "export_ref") as export):
                sync_versions.sync_release(root, root / ".build", "19")
                export.assert_not_called()

    def test_build_can_keep_pinned_manual_when_upstream_moves(self):
        with (patch.object(sync_versions, "has_import", return_value=True),
              patch.object(sync_versions, "read_revisions", return_value={"devel": "old", "19": "old", "18": "old", "17": "old"}),
              patch.object(sync_versions, "git_revision", return_value="new"),
              patch.object(sync_versions, "ref_revision", return_value="new"),
              patch.object(sync_versions, "sync_manual") as build_devel,
              patch.object(sync_versions, "export_ref") as export,
              patch.object(sync_versions, "sync_release", wraps=sync_versions.sync_release) as releases):
            sync_versions.sync_all(Path("/unused"), Path("/unused/build"), pin_cached=True)
            build_devel.assert_not_called()
            export.assert_not_called()
            self.assertEqual(releases.call_count, 3)


if __name__ == "__main__":
    unittest.main()
