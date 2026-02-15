PYTHON ?= python
CONFIG ?= tests/fixtures/minimal/config/pipeline.yaml
SMOKE_CONFIG ?= config/examples/cfff/pipeline.local.yaml
CORES ?= 8

.PHONY: validate test-unit test-integration test dryrun-local test-release smoke-cfff

validate:
	PYTHONPATH=src $(PYTHON) -m gmv.cli validate --config $(CONFIG)

test-unit:
	$(PYTHON) -m unittest discover -s tests/unit -p 'test_*.py'

test-integration:
	$(PYTHON) -m unittest discover -s tests/integration -p 'test_*.py'

test: test-unit test-integration

dryrun-local:
	@if command -v snakemake >/dev/null 2>&1; then \
		PYTHONPATH=src $(PYTHON) -m gmv.cli run --config $(CONFIG) --profile local --dry-run; \
	else \
		echo "WARNING: snakemake 未安装，跳过 dry-run"; \
	fi

test-release: validate test dryrun-local
	@echo "test-release 完成"

smoke-cfff:
	PYTHONPATH=src $(PYTHON) -m gmv.cli validate --config $(SMOKE_CONFIG)
	PYTHONPATH=src $(PYTHON) -m gmv.cli run --config $(SMOKE_CONFIG) --profile local --cores $(CORES)
	PYTHONPATH=src $(PYTHON) -m gmv.cli report --config $(SMOKE_CONFIG)
