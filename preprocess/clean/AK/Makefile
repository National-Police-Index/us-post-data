ak-url := "https://www.dropbox.com/scl/fi/gyfknquraawpxmxgjfvs5/Alaska-Police-Officers-20170125.xlsx?rlkey=nlu3679gqj7c2doyc39wbl0mn&st=snornend&dl=1"

.PHONY: all

all: output/ak-processed.csv

output/ak-processed.csv: src/process-ak.R input/ak-raw.xlsx
	mkdir -p output
	Rscript $< --input=input/ak-raw.xlsx --output=$@

input/ak-raw.xlsx:
	mkdir -p input
	wget $(ak-url) -O $@
	
