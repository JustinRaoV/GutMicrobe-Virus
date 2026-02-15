# GMV v2 CFFF Direct-Run (Local Profile) Design

Date: 2026-02-15

## Goal

Make the refactored GutMicrobeVirus v2 repository clonable on an offline HPC server and runnable **directly** (no SLURM submission yet) using:

- `Snakemake` orchestration
- `Singularity`/`Apptainer` containers (`.sif`)
- User-provided databases and test FASTQ inputs under `/cpfs01/...`

Success criteria for this milestone:

- `make test-release` remains fast (unit + integration, offline) and passes.
- A server can run an optional smoke pipeline end-to-end using real containers and real DB paths via a provided example config.
- `test.sh` is updated to the v2 CLI and can optionally trigger the smoke run when the server paths are present.

## Delivered Interfaces

- Example configs for the CFFF server layout:
  - `config/examples/cfff/pipeline.local.yaml`
  - `config/examples/cfff/containers.yaml`
  - `config/examples/cfff/samples.tsv`
- CLI entrypoints (unchanged):
  - `gmv validate`
  - `gmv run`
  - `gmv report`
- Smoke execution via:
  - `bash test.sh` (auto-detects `/cpfs01/...` paths) or `make smoke-cfff`

## Design Choices

- Keep `test-release` lightweight: no real tool execution; only config/env validation and dry-run when Snakemake is installed.
- Provide a **server-only** example config that uses absolute paths to `.sif` and DB directories.
- Improve Snakemake container execution:
  - Auto-detect container runtime (`singularity` vs `apptainer`)
  - Support bind paths (optional config + safe auto-bind of inputs/db/work/results)
- Replace placeholder steps with real implementations in non-mock mode for:
  - BUSCO contamination filtering
  - vclust-based de-replication + seqkit representative extraction
  - CoverM contig quantification
  - PhaBox2 annotation (best-effort summary)

## Non-Goals (This Milestone)

- SLURM submission end-to-end validation (will be added later).
- Backwards-compatible v1 CLI semantics for `run_upstream.py`/`viruslib_pipeline.py`/`make.py`.

