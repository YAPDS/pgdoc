HUGO ?= $(or $(shell command -v hugo 2>/dev/null),$(wildcard .build/hugo),hugo)
PYTHON ?= python3
PG_REMOTE ?= https://github.com/postgres/postgres.git
VERSION ?=
HTML_DIR ?=
PGDOC_DIR ?=
PGDOC_REMOTE ?= https://github.com/pgsty/pgdoc.git
PG_SOURCE ?=
PG_COMMIT ?=

.PHONY: sync refresh sync-pgdoc refresh-pgdoc build serve import-postgres import-pgdoc check

sync:
	$(PYTHON) -m scripts.fetch_postgres --remote "$(PG_REMOTE)"

refresh:
	$(PYTHON) -m scripts.fetch_postgres --remote "$(PG_REMOTE)" --refresh

sync-pgdoc:
	$(PYTHON) -m scripts.sync_pgdoc $(if $(PGDOC_DIR),--source "$(PGDOC_DIR)",--remote "$(PGDOC_REMOTE)") $(if $(PG_SOURCE),--postgres-source "$(PG_SOURCE)")

refresh-pgdoc:
	$(PYTHON) -m scripts.sync_pgdoc $(if $(PGDOC_DIR),--source "$(PGDOC_DIR)",--remote "$(PGDOC_REMOTE)") $(if $(PG_SOURCE),--postgres-source "$(PG_SOURCE)") --refresh

build: sync sync-pgdoc
	$(HUGO) --cleanDestinationDir --minify

serve: 
	$(HUGO) server --buildDrafts --bind 0.0.0.0

import-postgres:
	$(PYTHON) -m scripts.import_postgres_html --version "$(VERSION)" --source "$(HTML_DIR)"

import-pgdoc:
	$(PYTHON) -m scripts.import_pgdoc $(if $(PGDOC_DIR),--source "$(PGDOC_DIR)",--remote "$(PGDOC_REMOTE)") --version "$(VERSION)" $(if $(HTML_DIR),--html-dir "$(HTML_DIR)") $(if $(PG_SOURCE),--postgres-source "$(PG_SOURCE)") $(if $(PG_COMMIT),--postgres-commit "$(PG_COMMIT)")

check:
	$(PYTHON) -m unittest discover -s tests -v
