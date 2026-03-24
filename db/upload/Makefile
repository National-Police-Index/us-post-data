INPUT_DIR := ../data/output
DELAY     := 5
STATE     :=

.PHONY: dry-run run run-force

# Default: dry run (safe — no Firebase credentials needed)
dry-run:
	python3 src/src.py --input-dir $(INPUT_DIR) --dry-run $(if $(STATE),--states $(STATE))

# Live upload (skips states already in Firebase)
run:
	python3 src/src.py --input-dir $(INPUT_DIR) --delay $(DELAY) $(if $(STATE),--states $(STATE))

# Force re-upload (deletes existing state data first)
run-force:
	python3 src/src.py --input-dir $(INPUT_DIR) --delay $(DELAY) --force $(if $(STATE),--states $(STATE))
