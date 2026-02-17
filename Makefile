PYTHON ?= python
PYTHONPATH := src
MINIMAL_CONFIG := tests/fixtures/minimal/config/pipeline.yaml
MINIMAL_INPUT := tests/fixtures/minimal/data

.PHONY: test validate dry-run test-release

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest

validate:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m gmv.cli validate --config $(MINIMAL_CONFIG) --input-dir $(MINIMAL_INPUT) --strict

dry-run:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m gmv.cli run --config $(MINIMAL_CONFIG) --input-dir $(MINIMAL_INPUT) --profile local --stage all --cores 2 --dry-run

test-release: validate test dry-run
	@echo "[GMV] v4 test-release completed"
