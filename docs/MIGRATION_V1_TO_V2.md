# v1 -> v2 迁移指南

## 变更性质

v2 为破坏式重构，不保留 v1 入口脚本兼容层。

## 已退役入口

- `run_upstream.py`
- `make.py`
- `viruslib_pipeline.py`

## 新入口

统一使用 `gmv` CLI：

- `gmv validate`
- `gmv profile`
- `gmv run`
- `gmv report`
- `gmv agent replay`

## 迁移步骤

1. 将旧配置迁移到 `config/pipeline.yaml` 和 `config/containers.yaml`。
2. 将批量脚本逻辑迁移到 `sample_sheet` + `profile`（local/slurm）。
3. 使用 `gmv validate` 先做环境体检。
4. 用 `gmv run --dry-run` 确认 DAG。
5. 正式运行并用 `gmv report` 生成报告。
