# GutMicrobeVirus v2 架构说明

## 1. 总体架构

- 编排层：Snakemake
- 执行层：Singularity（离线镜像）
- 调度层：SLURM profile / local profile
- 控制层：`gmv` 统一 CLI
- 决策层：离线 Agent（分级自治）
- 报告层：中文方法说明 + 英文图表

## 2. 数据分层

- `raw/` 原始输入
- `work/` 中间过程产物
- `cache/` 缓存
- `results/` 最终结果
- `reports/` 报告与图表

## 3. Snakemake DAG

主要阶段：

1. preprocess
2. host_removal
3. assembly
4. vsearch
5. virus_detection (virsorter/genomad)
6. combination
7. checkv
8. high_quality
9. busco_filter
10. viruslib (merge + dedup + annotation)
11. downstream (coverm / bowtie2_samtools)
12. agent decision log

## 4. Agent 机制

- 输入信号：步骤状态、错误类型、重试次数、产量
- 低风险动作（自动）：资源上调、普通重试
- 高风险动作（建议）：阈值放宽、流程策略调整
- 输出：`results/<run_id>/agent/decisions.jsonl`

## 5. 配置协议

主配置：`config/pipeline.yaml`

关键段：

- `execution`
- `containers`
- `tools`
- `agent`
- `reporting`
- `resources`
- `database`
