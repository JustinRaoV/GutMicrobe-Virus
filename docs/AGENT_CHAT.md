# GMV ChatOps

## 配置

```bash
export GMV_API_KEY=your_key
mkdir -p ~/.config/gmv
cat > ~/.config/gmv/llm.yaml <<'YAML'
base_url: https://api.openai.com/v1
model: gpt-4o-mini
api_key_env: GMV_API_KEY
timeout_s: 60
verify_tls: true
YAML
```

## 启动

```bash
./gmv chat --config config/examples/cfff/pipeline.local.yaml
```

## 常见指令

- `先 validate 配置`
- `dry-run upstream`
- `提交 project 到 slurm`
- `查看队列`
- `查看最新 snakemake 日志`

## 离线测试

```bash
GMV_CHAT_MOCK=1 ./gmv chat --config tests/fixtures/minimal/config/pipeline.yaml --message "validate"
```

## 审计日志

- `results/<run_id>/agent/chat/chat.<timestamp>.jsonl`
