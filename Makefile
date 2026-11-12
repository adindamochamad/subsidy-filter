PYTHON ?= python3
export PYTHONPATH := $(CURDIR)

.PHONY: all extract classify dashboard

# Rebuild charts and the dashboard from committed CSVs.
# No BigQuery credentials. No network required for the build.
all: classify dashboard

# Refresh data/raw/*.csv from BigQuery. Requires gcloud ADC
# on project tessera-496904. Dry-runs every query first and
# refuses anything estimated above 50 GB.
extract:
	$(PYTHON) -m extract.run

classify:
	$(PYTHON) -m classify.run

dashboard:
	$(PYTHON) -m dashboard.build
