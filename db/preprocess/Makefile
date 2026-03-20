INPUT_DIR  := ../../states
OUTPUT_DIR := ../data/output

.PHONY: run run-force clean setup

run:
	python3 src/src.py --input-dir $(INPUT_DIR) --output-dir $(OUTPUT_DIR) $(if $(STATE),--states $(STATE))

run-force:
	python3 src/src.py --input-dir $(INPUT_DIR) --output-dir $(OUTPUT_DIR) --force $(if $(STATE),--states $(STATE))

clean:
	rm -rf $(OUTPUT_DIR)/*/*.csv.gz

setup:
	mkdir -p $(INPUT_DIR) $(OUTPUT_DIR)
