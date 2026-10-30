PYTHON ?= python3
BASE_URL ?= http://localhost:8080
CA_FILE ?=
ACTION_SCRIPT ?=
TLS_ARGS = $(if $(CA_FILE),--ca-file "$(CA_FILE)",)

.PHONY: help check validate test load

help:
	@echo "check: offline structure; validate: full OpenAPI (requirements-dev.txt); test: running API; load: synthetic writes"

check:
	$(PYTHON) scripts/check_contract.py

validate:
	$(PYTHON) scripts/validate_openapi.py

test:
	$(PYTHON) tests/smoke.py --base-url "$(BASE_URL)" $(TLS_ARGS)

load:
	$(PYTHON) tests/load.py --base-url "$(BASE_URL)" $(TLS_ARGS)

.PHONY: test-own test-all verify-docker run
DOTNET ?= dotnet
run:
	$(DOTNET) run --project src/Messenger

test-own:
	$(PYTHON) tests_own/test_api.py --base-url "$(BASE_URL)"

test-all: check test test-own

verify-docker:
	$(PYTHON) scripts/verify_docker.py
