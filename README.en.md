# PostgreSQL Documentation Site

This project is a Hugo site for PostgreSQL documentation in English and Chinese. It imports upstream chunked HTML as version-controlled page snapshots and provides version and language switching, a chapter navigation tree, and site search. The resulting site can be deployed to any static host. This repository stores documentation snapshots, not complete PostgreSQL or pgdoc Git repositories.

## Documentation sources

| Language | Upstream | Version source | Local snapshot |
| --- | --- | --- | --- |
| English | [postgres/postgres](https://github.com/postgres/postgres) | `master` (`devel` on this site), `REL_19_STABLE`, `REL_18_STABLE`, `REL_17_STABLE` | `content/en/postgresql/` |
| Chinese | [pgsty/pgdoc](https://github.com/pgsty/pgdoc) | `zh/20/`, `zh/19/`, `zh/18/`, and `zh/17/` on the `main` branch; `zh/20/` maps to `devel` on this site | `content/zh/postgresql/` |

The English manuals are built from PostgreSQL source. The Chinese manuals are built from pgdoc's `zh/` source files; translations are not imported from pgdoc's `docs/` directory. The upstream commits used for the current snapshots are recorded in `data/manual-sources.json` and `data/manual-sources-zh.json`, respectively.

The importer preserves the original `*.html` chapter URLs and relative links. Chapter navigation data lives in `data/manual_nav/` and `static/manual-nav/`. Images and other assets live in `static/postgresql/` and `static/zh/postgresql/`. Site templates, styles, and interaction code live in `layouts/`, `static/css/`, and `static/js/`, respectively.

## Set up the environment

- Hugo **0.144.2** builds and previews the site. Install it in your `PATH`, or place the executable at `.build/hugo`.
- Python 3, Git, and GNU Make fetch and import the manuals.
- Building manuals from upstream source also requires a C compiler, Bison, Flex, `xmllint`, `xsltproc`, DocBook XML/XSL, and `rsync`. Sync commands need access to the corresponding Git remotes. A pgdoc build may also download a PostgreSQL source archive.

On Debian or Ubuntu, install the documentation build dependencies with:

```bash
sudo apt-get update
sudo apt-get install -y curl git python3 make build-essential bison flex \
  libxml2-utils xsltproc docbook-xml docbook-xsl rsync
```

On Linux, download the binary for your architecture from the [Hugo 0.144.2 release](https://github.com/gohugoio/hugo/releases/tag/v0.144.2) and put it at `.build/hugo` in this repository. For example, on ARM64:

```bash
mkdir -p .build
curl -fL https://github.com/gohugoio/hugo/releases/download/v0.144.2/hugo_0.144.2_linux-arm64.tar.gz \
  | tar -xz -C .build hugo
.build/hugo version
```

For x86-64, replace `linux-arm64` with `linux-amd64` in the download URL. You can also install Hugo in your `PATH`. If you only preview or build the site from committed snapshots, you do not need the DocBook build dependencies or upstream access.

## Preview and build locally

Run these commands from the repository root:

```bash
make serve                              # Preview existing snapshots at http://localhost:1313/
hugo --cleanDestinationDir --minify     # Render existing snapshots to public/
make build                              # Fetch upstreams, sync Chinese docs as needed, and build public/
make check                              # Run import and version handling tests
```

`make build` temporarily fetches the four PostgreSQL branches listed above and pgdoc's `main` branch. By default, it uses the committed English snapshots and reports any newer upstream commits without importing them. It reimports Chinese manuals when the pgdoc commit changes or a local snapshot is missing. Temporary source and build directories are removed when the command finishes; `public/` is an ignored output directory. Set `PG_REMOTE` or `PGDOC_REMOTE` to use a Git mirror, for example `make build PG_REMOTE=file:///path/to/postgres.git`.

If Hugo is installed only at `.build/hugo`, use `.build/hugo` in place of the direct `hugo` command above. `make` finds that path automatically.

## Update or import manuals

```bash
make refresh                     # Rebuild all four English versions and update source commits
make sync-pgdoc                  # Update the four Chinese versions when pgdoc main changes
make refresh-pgdoc               # Force a rebuild of all four Chinese versions
make import-pgdoc VERSION=18     # Import Chinese version 18 only
make import-postgres VERSION=18 HTML_DIR=/absolute/path/to/html
```

`VERSION=devel` maps to pgdoc's `zh/20/`. For a Chinese import, set `PGDOC_DIR=/absolute/path/to/pgdoc` to use a local checkout of `main`; update that checkout yourself. If chunked Chinese HTML has already been built, pass `HTML_DIR=/absolute/path/to/html` to `make import-pgdoc` to skip the pgdoc build. If pgdoc cannot download its PostgreSQL source archive, pass `PG_SOURCE=/absolute/path/to/postgres` pointing to a local repository that contains the required commit. A single-version import also accepts `PG_COMMIT`; otherwise, it uses the English source commit recorded by this site.

After updating, commit `content/en/`, `content/zh/`, `data/manual_nav/`, `static/manual-nav/`, `static/postgresql/`, `static/zh/postgresql/`, and both source-commit records together. The manual pages are generated by scripts; edit the upstream source documents and reimport them instead of editing generated pages.

## Deployment

`.github/workflows/pages.yml` runs `make refresh`, `make sync-pgdoc`, and a Hugo build every day at **00:00 UTC**. After a successful build, it pushes changed manual snapshots, assets, navigation data, and source-commit records to the branch that triggered the workflow, then deploys to GitHub Pages. It skips the commit when nothing has changed. You can also trigger it manually from the Actions tab. The workflow sets Hugo's `baseURL` to the URL provided by GitHub Pages. For the first deployment, set **Settings → Pages → Build and deployment → Source** to **GitHub Actions** and allow the workflow's `GITHUB_TOKEN` to write to the repository.

You can also publish `public/` to another static host. For Netlify, see `netlify.toml`: use this repository as the site root, `make build` as the build command, and `public` as the publish directory.

## Google Analytics

The shared page template now includes Hugo's built-in GA4 template. For GitHub Pages builds, set `GA_MEASUREMENT_ID` (in the form `G-...`) under **Settings → Secrets and variables → Actions → Variables**. No analytics code is emitted when the variable is unset. A GA4 measurement ID is visible in the generated page source, so a regular repository variable is sufficient.

For a local build, supply the ID temporarily, for example `HUGO_SERVICES_GOOGLEANALYTICS_ID=G-XXXXXXXXXX .build/hugo --minify`. After deployment, verify it with Google Tag Assistant or the GA4 Realtime report.
