# vim: set ts=8 sts=0 sw=8 si fenc=utf-8 noet:
# vim: set fdm=marker fmr={{{,}}} fdl=0 foldcolumn=4:

dropbox_url := https://www.dropbox.com/scl/fo/cap9q2zjts5z27qglmozi/AMgkPc1oa0UvFBdfc_0lAnE?rlkey=hy8kgejy5hxgmxvs2maqjyirp&st=1ao5ebnb&dl=0

.PHONY: all clean

all: output/wa-2024-npi-index.csv

clean:
	-rm -r output/*

output/downloaded-from-dropbox.done: input/wa.zip
	mkdir -p output
	7zz x input/wa.zip -oinput
	touch $@

input/wa.zip:
	mkdir -p input
	curl -L -o input/wa.zip "$(dropbox_url)"

output/wa-2024-npi-index.csv: output/downloaded-from-dropbox.done
	mkdir -p output
	Rscript --vanilla src/process.R

# done.
