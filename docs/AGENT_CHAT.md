# GMV ChatOps 使用说明

## 1. 配置

推荐将 API key 放到环境变量：

```bash
export GMV_API_KEY="..."
```

可选用户配置文件：`~/.config/gmv/llm.yaml`

```yaml
base_url: "https://api.openai.com/v1"
model: "gpt-4o-mini"
api_key_env: "GMV_API_KEY"
timeout_s: 60
verify_tls: true
```

## 2. 运行

交互模式：

```bash
PYTHONPATH=src python -m gmv.cli chat --config config/pipeline.yaml
```

单次消息：

```bash
PYTHONPATH=src python -m gmv.cli chat --config config/pipeline.yaml --message "validate"
```

## 3. 安全规则

- 白名单工具执行，不开放任意 shell
- 高风险动作默认确认：
  - `gmv_run(dry_run=false)`
  - `slurm_scancel`
- 如需跳过确认：`--auto-approve`

## 4. 审计日志

路径：

- `results/<run_id>/agent/chat/chat.<timestamp>.jsonl`

字段包含：`role/content/tool_name/tool_args/returncode/stdout_tail/stderr_tail/artifact_paths`。
