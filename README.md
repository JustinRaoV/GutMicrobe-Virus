# GutMicrobeVirus v4

Offline-ready gut virome detection system with `Snakemake + Singularity + SLURM + ChatOps`.

## 30-second Quickstart

```bash
git clone -b codex/v4-virome-system https://github.com/JustinRaoV/GutMicrobe-Virus.git
cd GutMicrobe-Virus
module load CentOS/7.9/Anaconda3/24.5.0
module load CentOS/7.9/singularity/3.9.2
./gmv validate --config config/examples/cfff/pipeline.local.yaml
./gmv run --config config/examples/cfff/pipeline.local.yaml --profile local --stage all --cores 8 --host hg38
```

If your cluster provides `apptainer` instead of `singularity`, set:

```yaml
execution:
  container_runtime: apptainer
```

## One Entry, Four Commands

- `gmv validate`
- `gmv run`
- `gmv report`
- `gmv chat`

## Input Style (Bioinformatics-friendly)

`gmv run` supports exactly one of:

- `--input-dir` (auto detect R1/R2 pairs)
- `--sample-sheet` (manual table)

Examples:

```bash
./gmv run --config config/examples/cfff/pipeline.local.yaml \
  --input-dir /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/workflow/data \
  --profile local --stage all --cores 8 --host hg38
```

```bash
./gmv run --config config/examples/cfff/pipeline.local.yaml \
  --sample-sheet config/examples/cfff/samples.tsv \
  --profile slurm --stage upstream --cores 128
```

## Workflow Design

- Upstream: per-sample parallel jobs
- Project stage: grouped single job (`viruslib + downstream + agent`)
- Detection strategy: balanced integration (`virsorter2 + genomad`), then quality filtering

## Paths in CFFF Example

- data: `/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/workflow/data`
- sif: `/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/sif`
- db: `/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/db`

## ChatOps

```bash
export GMV_API_KEY=your_key
cat > ~/.config/gmv/llm.yaml <<'YAML'
base_url: https://api.openai.com/v1
model: gpt-4o-mini
api_key_env: GMV_API_KEY
YAML

./gmv chat --config config/examples/cfff/pipeline.local.yaml
```

Offline mock mode:

```bash
GMV_CHAT_MOCK=1 ./gmv chat --config tests/fixtures/minimal/config/pipeline.yaml --message "validate"
```

## Docs Site

- Local file: `docs/index.html`
- GitHub Pages source: `main/docs`

Open docs locally:

```bash
open docs/index.html
```

## Test

```bash
make test-release
```
