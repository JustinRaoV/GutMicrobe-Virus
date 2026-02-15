# GutMicrobeVirus v2

离线优先的病毒组全链路流程，采用 **Snakemake + Singularity + SLURM**，支持 300+ 样本规模批处理，并内置分级自治 Agent 与论文导向报告产物。

## v2 核心特性

- 主编排统一为 Snakemake DAG。
- 面向断网服务器：镜像与数据库均使用本地路径。
- 统一 CLI：`gmv run / validate / profile / report / agent replay`。
- 多工具并存：VirSorter、geNomad、CoverM、Bowtie2+Samtools 等由统一配置启停。
- Agent 分级自治：低风险动作自动执行，高风险仅建议并记录。
- 报告输出策略：中文说明 + 英文图表。

## 目录结构

```text
.
├── config/
│   ├── pipeline.yaml
│   └── containers.yaml
├── workflow/
│   ├── Snakefile
│   └── rules/
├── profiles/
│   ├── local/
│   └── slurm/
├── src/gmv/
│   ├── cli.py
│   ├── config_schema.py
│   ├── validation.py
│   ├── agent/
│   ├── reporting/
│   └── workflow/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/minimal/
├── docs/
└── Makefile
```

## 快速开始

### 1. 环境准备

- Python 3.9+
- Snakemake（服务器执行建议使用 conda/mamba 预装）
- Singularity 3.x（或 Apptainer）
- 本地可访问的 `.sif` 镜像与数据库目录

### 2. 配置文件

1. 修改 `config/pipeline.yaml`：
- `execution.sample_sheet`
- `database.*`
- `execution.profile`（`local` 或 `slurm`）

2. 修改 `config/containers.yaml`：
- 各工具镜像路径

### CFFF 服务器示例（直跑）

如果你的服务器路径与示例一致（`/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/...`），可直接使用示例配置（默认关闭 `phabox2` 以加快 smoke）：

```bash
PYTHONPATH=src python -m gmv.cli validate --config config/examples/cfff/pipeline.local.yaml
PYTHONPATH=src python -m gmv.cli run --config config/examples/cfff/pipeline.local.yaml --profile local --cores 8
PYTHONPATH=src python -m gmv.cli report --config config/examples/cfff/pipeline.local.yaml
```

### 3. 配置验证

```bash
PYTHONPATH=src python -m gmv.cli validate --config config/pipeline.yaml
```

### 4. 运行流程

本地：

```bash
PYTHONPATH=src python -m gmv.cli run --config config/pipeline.yaml --profile local
```

SLURM：

```bash
PYTHONPATH=src python -m gmv.cli run --config config/pipeline.yaml --profile slurm
```

Dry-run：

```bash
PYTHONPATH=src python -m gmv.cli run --config config/pipeline.yaml --dry-run
```

### 5. 生成报告

```bash
PYTHONPATH=src python -m gmv.cli report --config config/pipeline.yaml
```

产物目录：

- `reports/manuscript/methods_zh.md`
- `reports/manuscript/figures/*.svg`（英文图表）
- `reports/manuscript/tables/*.tsv`

## Agent 回放

```bash
PYTHONPATH=src python -m gmv.cli agent replay --file results/<run_id>/agent/decisions.jsonl
```

## 一键发布验收

使用最小模拟数据（离线）：

```bash
make test-release
```

包含：

- 配置校验
- 单元测试
- 集成测试
- Snakemake dry-run（若环境未安装 snakemake 会提示跳过）

## 输入样本表格式

`sample_sheet` 为 TSV，至少包含以下列：

- `sample`
- `mode`：`reads` 或 `contigs`
- `input1`
- `input2`（`reads` 模式需要）
- `host`（可选）

示例见：`tests/fixtures/minimal/raw/samples.tsv`

## v1 迁移说明

v2 为破坏式重构，不保留旧入口脚本兼容层。请参考：

- `docs/MIGRATION_V1_TO_V2.md`

## 文档

- `docs/ARCHITECTURE.md`
- `docs/SERVER_RUNBOOK.md`
- `docs/MIGRATION_V1_TO_V2.md`
- `docs/RELEASE_MILESTONES.md`
