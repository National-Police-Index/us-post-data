.PHONY: all clean

all: output/indiana_index.csv

clean:
	-rm -r output/*

output/indiana_index.csv: src/clean.py input/officer-employment-history-7.25.24.xlsx
	mkdir -p output
	python src/clean.py

input/officer-employment-history-7.25.24.xlsx:
	mkdir -p input
	curl -o $@ -L https://www.dropbox.com/scl/fi/ofe9igsjiadybqydi0zox/officer-employment-history-7.25.24.xlsx?rlkey=q7pm1atyctssfclbvx531hdu0&st=jarlut57&dl=1
