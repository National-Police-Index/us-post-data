# vim: set ts=8 sts=0 sw=8 si fenc=utf-8 noet:
# vim: set fdm=marker fmr={{{,}}} fdl=0 foldcolumn=4:

dropbox_url_22 := https://www.dropbox.com/scl/fo/ersykuvzt32dd7d70xd7k/APVe23r1FRoScwu6xxV6NDc?rlkey=s5md5wk85b3r7bud0j3d4zkjt&st=sz64s1v7&dl=1

dropbox_url_24 := https://www.dropbox.com/scl/fo/h3ynxkhcbg32qmnoy336t/ADuo6rJ24eiXxS2qq5gHdgo?rlkey=k45k8hjf8h216v9wiz588bkdf&e=1&st=1cyqj6vp&dl=1

.PHONY: all clean

all: output/ks-2024-index.csv

clean:
	-rm -r output/*
	-rm -r input/*

output/ks-2024-index.csv: src/import.py output/downloaded-from-dropbox.done
	cd src && python import.py

output/downloaded-from-dropbox.done: input/ks_22.zip input/ks_24.zip
	mkdir -p output
	-rm -r input/24
	-rm -r input/22
	7zz x input/ks_22.zip -oinput/22
	7zz x input/ks_24.zip -oinput/24
	touch $@

input/ks_22.zip:
	mkdir -p input
	curl -L -o $@ "$(dropbox_url_22)"

input/ks_24.zip:
	mkdir -p input
	curl -L -o $@ "$(dropbox_url_24)"

# done.
