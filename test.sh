#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "[GMV] v2 test-release (fast, offline)"
make test-release

SMOKE_CONFIG_DEFAULT="config/examples/cfff/pipeline.local.yaml"
SMOKE_CONFIG="${GMV_SMOKE_CONFIG:-$SMOKE_CONFIG_DEFAULT}"
SMOKE_CORES="${GMV_SMOKE_CORES:-8}"

run_smoke="${GMV_RUN_SMOKE:-}"
if [[ -z "$run_smoke" ]]; then
  # Auto-enable on the known CFFF server layout.
  if [[ -d "/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/sif" ]]; then
    run_smoke="1"
  fi
fi

if [[ "$run_smoke" != "1" ]]; then
  echo ""
  echo "[GMV] smoke run skipped."
  echo "Set GMV_RUN_SMOKE=1 to run the real pipeline, e.g.:"
  echo "  GMV_RUN_SMOKE=1 GMV_SMOKE_CORES=8 bash test.sh"
  echo "Or select a config:"
  echo "  GMV_RUN_SMOKE=1 GMV_SMOKE_CONFIG=/path/to/pipeline.yaml bash test.sh"
  exit 0
fi

if ! command -v snakemake >/dev/null 2>&1; then
  echo "[GMV] ERROR: snakemake not found in PATH (required for smoke run)."
  exit 2
fi

echo ""
echo "[GMV] smoke run (direct/local profile)"
echo "  config: $SMOKE_CONFIG"
echo "  cores:  $SMOKE_CORES"

PYTHONPATH=src python -m gmv.cli validate --config "$SMOKE_CONFIG"
PYTHONPATH=src python -m gmv.cli run --config "$SMOKE_CONFIG" --profile local --cores "$SMOKE_CORES"
PYTHONPATH=src python -m gmv.cli report --config "$SMOKE_CONFIG"

echo ""
echo "[GMV] smoke outputs:"
ls -la results || true
ls -la reports/manuscript 2>/dev/null || true

