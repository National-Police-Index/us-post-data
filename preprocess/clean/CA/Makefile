# Authors: LB
# Maintainers: LB, TS
# Copyright:   2025, HRDAG, GPL v2 or later
# =========================================
# us-post-data/preprocess/clean/CA/Make

raw-leo-data := input/leo-2024-with-sep-reason.xlsx
raw-corrections-data := input/PDSQ118B-C_CDCR-Appts-Seps-2005-2023_Final.xlsx

leo-url := "https://www.dropbox.com/scl/fi/uyrdi2iu9byls6h3tiias/CPRA_R000301-011425__ADHOC-809.xlsx?rlkey=nt9v6s1b2l24efwt9y711al8u&st=jqxwd2gg&dl=1"
corrections-url := "https://www.dropbox.com/scl/fi/wi29v2g8puc447wod9f2v/PDSQ118B-C_CDCR-Appts-Seps-2005-2023_Final.xlsx?rlkey=ujf7s1c2ox2w7m2rto1p1wg0r&st=ywlgwqrp&dl=1"

.PHONY: all
all: output/poca_df.csv output/ca-index.csv

.PHONY: clean
clean:
	-rm -r output/*

.PHONY: all
output/poca_df.csv: src/scraper.py
	mkdir -p output
	cd src && python scraper.py

.PHONY: all
output/ca-index.csv: \
	src/concat-cleaned.py \
	output/ca-leo-processed.csv \
	output/ca-corrections-processed.csv
	mkdir -p output
	python $< output/ca-leo-processed.csv output/ca-corrections-processed.csv $@

.PHONY: all
output/ca-leo-processed.csv: src/clean-leo-2024-with-sep-reason.py input/leo-2024-with-sep-reason.xlsx
	mkdir -p output
	python $< --input=input/leo-2024-with-sep-reason.xlsx --output=$@

.PHONY: all
output/ca-corrections-processed.csv: src/clean-corrections.py output/ca-23-corrections-raw.csv
	mkdir -p output
	python $< \
		--input=output/ca-23-corrections-raw.csv \
		--output=$@

.PHONY: all
output/ca-23-corrections-raw.csv: input/PDSQ118B-C_CDCR-Appts-Seps-2005-2023_Final.xlsx src/xl2csv.py
	mkdir -p output
	python src/xl2csv.py \
		--input=$< \
		--header=6 \
		--output=$@

.PHONY: all
$(raw-leo-data):
	mkdir -p input
	curl -o $(raw-leo-data) -L $(leo-url)

.PHONY: all
$(raw-corrections-data):
	mkdir -p input
	curl -o $(raw-corrections-data) -L $(corrections-url)

# Done
