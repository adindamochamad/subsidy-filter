PYTHON ?= python3
export PYTHONPATH := $(CURDIR)

.PHONY: all extract extract-coverage classify dashboard film-play film-mp4

# Rebuild charts and the dashboard from committed CSVs.
# No BigQuery credentials. No network required for the build.
all: classify dashboard

# Refresh data/raw/*.csv from BigQuery. Requires gcloud ADC
# on project tessera-496904. Dry-runs every query first and
# refuses anything estimated above 50 GB.
extract:
	$(PYTHON) -m extract.run

extract-coverage:
	$(PYTHON) -m extract.run --only burst_coverage.sql

classify:
	$(PYTHON) -m classify.run

dashboard:
	$(PYTHON) -m dashboard.build

film-play:
	open "$(CURDIR)/film/index.html"

film-mp4:
	cd film && npm install && npx playwright install chromium && npm run film
