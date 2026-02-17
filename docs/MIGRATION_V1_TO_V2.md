# v3 破坏性变更声明

v3 是不兼容重构版本，重点是代码结构精简与维护成本控制。

## 保留命令

- `gmv validate`
- `gmv run`
- `gmv report`
- `gmv chat`

## 已移除命令

- `gmv profile`
- `gmv agent replay`
- `gmv agent harvest`
- `gmv agent chat`

## 迁移建议

1. 统一使用 `config/pipeline.yaml`。
2. 先执行 `gmv validate`。
3. 用 `gmv run --dry-run --stage all` 检查 DAG。
4. 通过 `gmv chat` 做对话式操作与审计。
