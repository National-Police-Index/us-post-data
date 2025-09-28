ak-emp-2017-url := "https://www.dropbox.com/scl/fi/gyfknquraawpxmxgjfvs5/Alaska-Police-Officers-20170125.xlsx?rlkey=nlu3679gqj7c2doyc39wbl0mn&st=snornend&dl=1"
ak-active-2023-url := "https://www.dropbox.com/scl/fi/87nfe687bld9br4qjnl6d/APSC-Current-Officers-Grace-Manthey.csv?rlkey=5tqcrt6u0btip4xb66kpqi27e&st=9l1inh7g&dl=1"
ak-changes-2023-url := "https://www.dropbox.com/scl/fi/vbgee206m2n7ysaw5ffd3/APSC-Employment-Status-Changes-since-2017-Grace-Manthey.csv?rlkey=brw7uxeeosby3tvqbcfyxc67f&st=zq86h5kz&dl=1"

.PHONY: all

all: output/ak-processed.csv

output/ak-processed.csv: src/process-ak.R \
	input/ak-raw.xlsx \
	input/ak-active-2023.csv \
	input/ak-changes-2023.csv
	mkdir -p output
	Rscript $< \
		--ak-employment-2017=input/ak-raw.xlsx \
		--ak-active-2023=input/ak-active-2023.csv \
		--ak-changes-2023=input/ak-changes-2023.csv \
		--output=$@

input/ak-raw.xlsx:
	mkdir -p input
	wget $(ak-emp-2017-url) -O $@
	
input/ak-active-2023.csv:
	mkdir -p input
	wget $(ak-active-2023-url) -O $@

input/ak-changes-2023.csv:
	mkdir -p input
	wget $(ak-changes-2023-url) -O $@
