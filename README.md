# GutMicrobeVirus v3

破坏性精简重构版本。目标是把项目从“脚本集合”升级为“可维护的离线检测系统”：

- Offline-first：断网服务器可运行
- Snakemake + Singularity + SLURM
- ChatOps：对话驱动 `validate/run/report` 与 SLURM 查询
- 仅保留 4 个 CLI 主命令：`gmv validate | run | report | chat`

## 30 秒 Quickstart

```bash
PYTHONPATH=src python -m gmv.cli validate --config config/pipeline.yaml
PYTHONPATH=src python -m gmv.cli run --config config/pipeline.yaml --profile local --dry-run --stage all
```

## 文档入口

- 详细前端说明站点：[`docs/index.html`](docs/index.html)
- 文档导航：[`docs/README.md`](docs/README.md)
- 服务器运行手册：[`docs/SERVER_RUNBOOK.md`](docs/SERVER_RUNBOOK.md)
- 架构说明：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## 命令概览

```bash
gmv validate --config config/pipeline.yaml
gmv run --config config/pipeline.yaml --profile local --stage all --dry-run
gmv report --config config/pipeline.yaml
gmv chat --config config/pipeline.yaml
```

## ChatOps LLM 配置

1. 环境变量（推荐）

```bash
export GMV_API_KEY="..."
export GMV_BASE_URL="https://api.openai.com/v1"
export GMV_MODEL="gpt-4o-mini"
```

2. 用户配置文件（可选）

`~/.config/gmv/llm.yaml`

```yaml
base_url: "https://api.openai.com/v1"
model: "gpt-4o-mini"
api_key_env: "GMV_API_KEY"
timeout_s: 60
verify_tls: true
```

## 破坏性变更（v3）

以下命令已移除，不再兼容：

- `gmv profile`
- `gmv agent replay`
- `gmv agent harvest`
- `gmv agent chat`

## 测试

```bash
make test-release
```

## GitHub Pages

推荐使用仓库内置工作流自动部署：

1. 打开 `Settings -> Pages`
2. `Build and deployment -> Source` 选择 `GitHub Actions`
3. 推送 `main` 分支后自动发布

说明：
- 若你还在特性分支（非 `main`）开发，线上主站点 URL 不会立即反映最新内容。
- 仓库根目录已提供 `index.html` 重定向到文档站点，降低配置不一致导致的空白页问题。
