INPUT_DIR  := ../../states
OUTPUT_DIR := ../data/output

STATE :=
YEAR  :=

.PHONY: run run-force clean setup

run:
	python3 src/src.py --input-dir $(INPUT_DIR) --output-dir $(OUTPUT_DIR) \
		$(if $(STATE),--states $(STATE)) $(if $(YEAR),--year $(YEAR))

run-force:
	python3 src/src.py --input-dir $(INPUT_DIR) --output-dir $(OUTPUT_DIR) --force \
		$(if $(STATE),--states $(STATE)) $(if $(YEAR),--year $(YEAR))

clean:
	rm -rf $(OUTPUT_DIR)/*/*.csv.gz

setup:
	mkdir -p $(INPUT_DIR) $(OUTPUT_DIR)
