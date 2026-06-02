INPUT_DIR := ../download/data/output
OUTPUT_DIR := data/output

.PHONY: run
run:
	python3 src/src.py --input-dir $(INPUT_DIR) --output-dir $(OUTPUT_DIR)

# Force reprocessing of all files
.PHONY: run-force
run-force:
	python3 src/src.py --input-dir $(INPUT_DIR) --output-dir $(OUTPUT_DIR) --force

.PHONY: clean
clean:
	rm -rf $(OUTPUT_DIR)/*/*.csv.gz

.PHONY: setup
setup:
	mkdir -p $(INPUT_DIR) $(OUTPUT_DIR)
