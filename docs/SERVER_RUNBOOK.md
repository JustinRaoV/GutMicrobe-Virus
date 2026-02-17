# 服务器运行手册（GMV v3 / CentOS7 + Singularity3.x + SLURM）

## 1. 克隆与切换版本

```bash
git clone <repo-url>
cd GutMicrobeVirus
# 建议拉取里程碑 tag
git fetch --tags
git checkout <tag>
```

## 2. 准备离线资源

- SIF 镜像目录（示例：`/data/sif/`）
- 数据库目录（示例：`/data/db/`）
- 样本表 TSV（示例：`/data/project/raw/samples.tsv`）

如果你所在站点需要通过 module 提供 Singularity（如 CentOS7 集群），先加载：

```bash
module load CentOS/7.9/Anaconda3/24.5.0
module load CentOS/7.9/singularity/3.9.2
```

## 3. 修改配置

- `config/pipeline.yaml`
- `config/containers.yaml`

确保所有路径为服务器本地可访问绝对路径。

## 4. 预校验

```bash
PYTHONPATH=src python -m gmv.cli validate --config config/pipeline.yaml
```

## 5. 运行（v3 CLI）

### 本地模式

```bash
PYTHONPATH=src python -m gmv.cli run --config config/pipeline.yaml --profile local
```

### SLURM 模式

```bash
PYTHONPATH=src python -m gmv.cli run --config config/pipeline.yaml --profile slurm
```

### 两阶段（推荐）

上游按样本高并发，项目级汇总在 SLURM 下会 group 为 1 个 job（viruslib + downstream + agent）：

```bash
PYTHONPATH=src python -m gmv.cli run --config config/pipeline.yaml --profile slurm --stage upstream
PYTHONPATH=src python -m gmv.cli run --config config/pipeline.yaml --profile slurm --stage project
```

### Dry-run

```bash
PYTHONPATH=src python -m gmv.cli run --config config/pipeline.yaml --dry-run
```

## 6. ChatOps（可选）

```bash
PYTHONPATH=src python -m gmv.cli chat --config config/pipeline.yaml
```

## 7. 报告输出

```bash
PYTHONPATH=src python -m gmv.cli report --config config/pipeline.yaml
```

## 8. 常见问题

1. `validate` 报镜像不存在
- 检查 `config/containers.yaml` 路径。

2. `validate` 报数据库不存在
- 检查 `config/pipeline.yaml` 的 `database` 段。

3. `run` 报找不到 snakemake
- 在服务器 conda 环境预装 snakemake。
