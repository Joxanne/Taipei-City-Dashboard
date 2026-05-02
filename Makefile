.PHONY: all fe be
all: fe be

fe:
	cd docker && docker compose restart dashboard-fe
be:
	cd docker && docker compose restart dashboard-be
