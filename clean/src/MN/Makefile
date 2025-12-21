# vim: set ts=8 sts=0 sw=8 si fenc=utf-8 noet:
# vim: set fdm=marker fmr={{{,}}} fdl=0 foldcolumn=4:

.PHONY: all clean

# MN data updated 2025-01-21
db_url := https://www.dropbox.com/scl/fi/z2q8txhgobvv4mzyz2ity/PUBLIC-NOW-WITH-MIDDLE-NAME-Officer-with-Agency-Data-Public-Only-2025-01-21-09-16-56-2.xlsx?rlkey=i56hh2cqkzjbq0xng27wua666&st=ikg3dbuq&dl=1

all: output/mn-2025-01-21.csv

clean:
	-rm -r output/*

input/mn-2025-01-21.xlsx:
	mkdir -p input
	curl -L -o $@ "$(db_url)"

output/mn-2025-01-21.csv: src/import-mn.py input/mn-2025-01-21.xlsx
	mkdir -p output
	python $< --input=input/mn-2025-01-21.xlsx --output=$@

# done.
