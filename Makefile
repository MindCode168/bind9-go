GO ?= go
export GOTOOLCHAIN := local
export GOCACHE := $(CURDIR)/.cache/build

.PHONY: test vet fuzz inventory oracle test-report release-check
test:
	$(GO) test -race ./...

vet:
	$(GO) vet ./...

fuzz:
	$(GO) test ./internal/serial -run '^$$' -fuzz FuzzCompare -fuzztime 5s -parallel 2
	$(GO) test ./internal/ttl -run '^$$' -fuzz FuzzRoundTrip -fuzztime 5s -parallel 2
	$(GO) test ./internal/ttl -run '^$$' -fuzz FuzzParse -fuzztime 5s -parallel 2

inventory:
	python3 tools/inventory.py upstream/bind-9.20.27 docs/source-inventory-fresh.json

oracle:
	python3 tools/serial_oracle.py upstream/bind-9.20.27 internal/serial/testdata/upstream.txt
	python3 tools/ttl_oracle.py upstream/bind-9.20.27 internal/ttl/testdata/upstream.json

test-report:
	python3 tools/run_validation.py --go "$(GO)"

release-check:
	python3 tools/run_validation.py --go "$(GO)" --require-complete
