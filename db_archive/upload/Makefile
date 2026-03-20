INPUT_DIR := ../preprocess/data/output
DELAY := 5
FORCE_STATES :=

PYTHON = python3

SCRIPT = src/src.py

# Normal run
.PHONY: run
run:
	$(PYTHON) $(SCRIPT) --input-dir $(INPUT_DIR) --delay $(DELAY) $(if $(FORCE_STATES),--force-states $(FORCE_STATES))

# Force all states
.PHONY: run-all
run-all:
	$(PYTHON) $(SCRIPT) --input-dir $(INPUT_DIR) --delay $(DELAY) --force-all
