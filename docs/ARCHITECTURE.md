# GutMicrobeVirus v3 架构说明

## 架构目标

- 破坏性精简：删除旧兼容层，收敛到单入口 `gmv`
- 离线优先：断网服务器可运行
- 成本可控：上游并发 + 项目级集中执行
- 可审计：ChatOps 所有动作写入 JSONL

## 模块结构

- `src/gmv/cli.py`：唯一 CLI 入口（4 命令）
- `src/gmv/config.py`：pipeline + llm 配置统一加载
- `src/gmv/chat/`：LLM client、工具白名单、会话执行
- `src/gmv/workflow/runner.py`：Snakemake 启动与 stage 控制
- `src/gmv/workflow/steps/`：`upstream / project / agent` 步骤实现
- `src/gmv/reporting/`：报告与图表生成

## CLI 合约（v3）

- `gmv validate`
- `gmv run`
- `gmv report`
- `gmv chat`

## 数据分层

- `raw/` 原始输入
- `work/` 中间过程产物
- `cache/` 可选缓存
- `results/` 最终结果与 agent 审计
- `reports/` 报告与图表

## 并发策略

- 上游：按样本并发
- 项目级：viruslib + downstream + agent 汇总
- 资源：按输入规模估算 `mem_mb/runtime`，支持 `fudge/overrides`

## ChatOps 安全边界

- 仅白名单工具
- 非 dry-run 的 `gmv run` 与 `slurm_scancel` 为高风险
- 默认要求确认（`--auto-approve` 可关闭）
- 审计日志：`results/<run_id>/agent/chat/chat.<timestamp>.jsonl`
