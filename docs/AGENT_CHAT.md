# GMV ChatOps（对话式 Agent）

GMV v2 提供 `gmv chat`，允许你通过对话执行 **白名单** 的本地任务与 SLURM 操作（OpenAI-Compatible）。

## 1. 配置 LLM（推荐）

1) 设置 API key（不落盘）：

```bash
export GMV_API_KEY="..."
```

2) 写入 `~/.config/gmv/llm.yaml`：

```yaml
base_url: "https://api.openai.com/v1"
model: "gpt-4o-mini"
api_key_env: "GMV_API_KEY"
timeout_s: 60
verify_tls: true
```

你也可以用环境变量覆盖：

- `GMV_BASE_URL`
- `GMV_MODEL`

## 2. 运行（CentOS7 + module）

```bash
module load CentOS/7.9/Anaconda3/24.5.0
module load CentOS/7.9/singularity/3.9.2
```

交互模式：

```bash
PYTHONPATH=src python -m gmv.cli chat --config config/examples/cfff/pipeline.local.yaml
```

单次消息模式：

```bash
PYTHONPATH=src python -m gmv.cli chat --config config/examples/cfff/pipeline.local.yaml --message "validate"
```

高风险动作（例如 `gmv run` 非 dry-run、`scancel`）默认需要确认；单次消息模式可用 `--auto-approve` 跳过确认：

```bash
PYTHONPATH=src python -m gmv.cli chat --config config/pipeline.yaml --message "提交 upstream 到 slurm" --auto-approve
```

## 3. 示例对话脚本

- `validate`
- `dry-run upstream`
- `提交 upstream 到 slurm`（高风险：默认需要确认或使用 `--auto-approve`）
- `查看队列里 GMV 相关 job`
- `查看 job 12345 的 sacct`

## 4. 审计日志

每次会话都会写入审计 JSONL：

- `results/<run_id>/agent/chat/chat.<timestamp>.jsonl`

其中包含 tool 调用、返回码、stdout/stderr 末尾以及 artifacts 文件路径。
