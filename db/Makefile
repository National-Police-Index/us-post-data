# Top-level pipeline Makefile
# Usage:
#   make preprocess STATE=GA        — preprocess one state
#   make preprocess                 — preprocess all states
#   make dry-run STATE=GA           — validate upload without writing to Firebase
#   make upload STATE=GA            — live upload one state
#   make upload                     — live upload all states
#   make force-upload STATE=GA      — re-upload, deleting existing data first
#   make delete                     — delete ALL data from Firestore db_launch
#   make delete STATE=GA            — delete only GA data from Firestore

STATE :=

.PHONY: preprocess dry-run upload force-upload delete

preprocess:
	$(MAKE) -C preprocess run $(if $(STATE),STATE=$(STATE))

dry-run: preprocess
	$(MAKE) -C upload dry-run $(if $(STATE),STATE=$(STATE))

upload: preprocess
	$(MAKE) -C upload run $(if $(STATE),STATE=$(STATE))

force-upload: preprocess
	$(MAKE) -C upload run-force $(if $(STATE),STATE=$(STATE))

delete:
	$(MAKE) -C delete run $(if $(STATE),STATE=$(STATE))
