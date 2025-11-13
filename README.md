# GutMicrobe-Virus 病毒组分析流程

现代化、模块化的病毒组分析流程，支持从测序数据到病毒库构建的完整工作流。

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Singularity](https://img.shields.io/badge/Singularity-Supported-orange.svg)](https://sylabs.io/)

## 特性

- 🔬 **多工具病毒检测**: 整合 VirSorter2, DeepVirFinder, VIBRANT, BLASTN, CheckV
- 🧬 **灵活的输入模式**: 支持从测序文件或组装文件开始
- 🐳 **Singularity 支持**: 无需本地安装软件，使用容器化部署
- 📊 **智能依赖管理**: 自动检测步骤依赖，前置步骤更新自动触发后续重跑
- 🔧 **高度可配置**: YAML 配置文件，灵活调整参数和工具
- 📦 **批量处理**: 一键生成多样本分析脚本
- 🧪 **病毒库构建**: vclust 去冗余 + PhaBox2 功能预测

## 项目结构

```
GutMicrobe-Virus/
├── config/
│   └── config.yaml              # YAML配置文件
├── src/
│   ├── config.py                # 配置加载
│   ├── logger.py                # 日志系统
│   ├── utils.py                 # 工具函数
│   └── pipeline/
│       ├── preprocessing.py     # 预处理步骤
│       ├── virus_detection.py   # 病毒检测(多工具)
│       └── quality.py           # 质量评估
├── run_upstream.py              # 上游分析主流程
├── run_downstream.py            # 下游丰度分析
├── viruslib_pipeline.py         # 病毒库构建
├── make.py                      # 批量脚本生成
├── test.sh                      # 测试脚本
└── docs/                        # 文档目录
```

## 安装

### 方式1: Conda 环境

```bash
pip install -r requirements.txt
conda install -c bioconda fastp megahit vsearch checkv virsorter2 ...
```

### 方式2: Singularity 容器 (推荐)

无需本地安装软件，使用预构建的容器：

```bash
# 1. 准备 SIF 文件
mkdir -p ~/sif
# 将所有 .sif 文件放到 ~/sif/ 目录

# 2. 启用 Singularity
vim config/config.yaml
# 设置 singularity.enabled: true

# 3. 直接运行
python run_upstream.py R1.fq.gz R2.fq.gz
```

详见: [Singularity 使用文档](docs/SINGULARITY.md)

## 配置

编辑 `config/config.yaml`:

```yaml
# 启用/禁用病毒检测工具
virus_detection:
  enable_checkv_prefilter: true
  enable_virsorter: true
  enable_dvf: false         # 禁用某个工具
  enable_vibrant: true
  enable_blastn: true
```

## 使用

### 单样本分析

**从测序文件开始:**
```bash
python run_upstream.py R1.fq.gz R2.fq.gz --start-from reads --host hg38 -t 32 -o result/
```

**从组装文件开始:**
```bash
python run_upstream.py contigs.fa --start-from contigs -t 32 -o result/
```

### 批量分析

**从测序文件批量分析:**
```bash
# 生成脚本
python make.py /path/to/reads_dir --mode reads --host hg38 -t 32 -o result/

# 运行所有样本
bash result/submit_all.sh

# 或单独运行某个样本
bash result/scripts/run_001_sample1.sh
```

**从contigs文件批量分析:**
```bash
# 生成脚本
python make.py /path/to/contigs_dir --mode contigs -t 32 -o result/

# 运行所有样本
bash result/submit_all.sh
```

### 病毒库构建

从所有样本的高质量病毒序列构建非冗余病毒库：

```bash
# 从上游分析结果构建
python viruslib_pipeline.py -t 32 -o viruslib_result

# 从指定目录构建
python viruslib_pipeline.py -i /path/to/contigs_dir -t 32 -o viruslib_result
```

详见: [病毒库构建文档](docs/VIRUSLIB_USAGE.md)

### 下游分析

使用构建的病毒库进行丰度分析：

```bash
python run_downstream.py sample_R1.fq.gz sample_R2.fq.gz \
    --viruslib viruslib_result/2.vclust_dedup/viruslib_nr.fa \
    -o downstream_result
```

## 高级功能

### 步骤依赖管理

流程自动检测步骤间的依赖关系。当前置步骤重新运行时，后续依赖步骤会自动触发：

```bash
# 例如：重新运行 BLASTN
python run_upstream.py ... --force  # 或手动删除 .status 文件

# 自动检测到 BLASTN 更新，会重跑：
# - combination (依赖 blastn)
# - checkv (依赖 combination)
# - high_quality (依赖 checkv)
# - busco_filter (依赖 high_quality)
```

### 断点续跑

流程支持断点续跑，已完成步骤自动跳过：

```bash
# 第一次运行（中途失败）
python run_upstream.py sample_R1.fq.gz sample_R2.fq.gz --host hg38 -o results

# 修复问题后，直接重新运行相同命令
python run_upstream.py sample_R1.fq.gz sample_R2.fq.gz --host hg38 -o results
# 已完成的步骤会自动跳过

# 强制重跑所有步骤
python run_upstream.py sample_R1.fq.gz sample_R2.fq.gz --host hg38 -o results --force
```

### BLASTN 多数据库过滤

BLASTN 模块对 5 个病毒数据库进行比对并应用三重过滤：

- **pident ≥ 50%**: 序列一致性
- **evalue ≤ 1e-10**: E-value 阈值
- **qcovs ≥ 80%**: 查询覆盖度

可在 `config/config.yaml` 中调整阈值。详见: [BLASTN 过滤文档](docs/BLASTN_FILTER.md)

## 输出结果

### 上游分析结果

```
results/
├── sample/
│   ├── 1.trimmed/              # 质控后数据
│   ├── 2.host_removed/         # 去宿主后数据
│   ├── 3.assembly/             # 组装结果
│   ├── 4.vsearch/              # 长度过滤结果
│   ├── 5.checkv_prefilter/     # CheckV预过滤
│   ├── 6.virsorter/            # VirSorter2结果
│   ├── 7.dvf/                  # DeepVirFinder结果
│   ├── 8.vibrant/              # VIBRANT结果
│   ├── 9.blastn/               # BLASTN结果
│   │   ├── blastn_virus.list   # 通过过滤的contig列表
│   │   └── blastn_filtered.tsv # 详细过滤结果
│   ├── 10.combination/         # 多工具整合结果
│   ├── 11.checkv/              # CheckV质控
│   ├── 12.high_quality/        # 高质量病毒序列
│   └── 13.busco_filter/        # BUSCO过滤后最终结果 ⭐
└── .status/                    # 步骤状态文件
```

### 病毒库结果

```
viruslib_result/
├── 1.merge_contigs/
│   └── all_contigs.fa          # 合并的所有序列
├── 2.vclust_dedup/
│   ├── clusters.tsv            # 聚类结果
│   └── viruslib_nr.fa          # 非冗余病毒库 ⭐
└── 3.phabox2/                  # 功能预测结果
```

## 测试

运行测试脚本验证安装：

```bash
bash test.sh
```

## 文档

- [Singularity 使用指南](docs/SINGULARITY.md)
- [病毒库构建文档](docs/VIRUSLIB_USAGE.md)
- [BLASTN 过滤逻辑](docs/BLASTN_FILTER.md)
- [完整使用指南](USAGE.md)

## 依赖软件

### 核心工具
- fastp (质控)
- bowtie2 (去宿主)
- MEGAHIT (组装)
- vsearch (长度过滤)
- CheckV (质控和预过滤)
- VirSorter2 (病毒检测)
- DeepVirFinder (病毒检测)
- VIBRANT (病毒检测)
- BLASTN (病毒数据库比对)
- seqkit (序列处理)

### 病毒库构建
- vclust (去冗余)
- PhaBox2 (功能预测)

### 下游分析
- CoverM (丰度定量)

## 引用

如果使用本流程，请引用相关工具：

- VirSorter2: Guo et al. (2021) Microbiome
- CheckV: Nayfach et al. (2021) Nature Biotechnology
- DeepVirFinder: Ren et al. (2020) Quantitative Biology
- VIBRANT: Kieft et al. (2020) Microbiome
- vclust: Kristensen et al. (2021) bioRxiv
- PhaBox2: ...

## 许可证

MIT License

## 联系方式

- GitHub: [JustinRaoV](https://github.com/JustinRaoV)
- 问题反馈: [Issues](https://github.com/JustinRaoV/GutMicrobe-Virus/issues)

## 更新日志

### v1.0.0 (2025-11-10)
- ✅ 完整的上游分析流程
- ✅ Singularity 容器支持
- ✅ 多工具病毒检测 (VirSorter2, DVF, VIBRANT, BLASTN)
- ✅ BLASTN 完整过滤逻辑
- ✅ 步骤依赖关系自动管理
- ✅ 病毒库构建流程 (vclust + PhaBox2)
- ✅ 批量脚本生成工具
- ✅ 支持从 reads 或 contigs 起始

## 工作流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     上游分析 (run_upstream.py)                   │
└─────────────────────────────────────────────────────────────────┘
    测序数据 (FASTQ) 或 组装文件 (FASTA)
           ↓
    1. 质控 (fastp)
           ↓
    2. 去宿主 (bowtie2)
           ↓
    3. 组装 (MEGAHIT)
           ↓
    4. 长度过滤 (vsearch ≥500bp)
           ↓
    5. CheckV预过滤 (去除宿主污染)
           ↓
    ┌────────────────────────────────┐
    │  6. 多工具病毒检测（并行）      │
    │  - VirSorter2 (三步走)          │
    │  - DeepVirFinder                │
    │  - VIBRANT                      │
    │  - BLASTN (5个数据库)           │
    └────────────────────────────────┘
           ↓
    7. 结果整合 (多工具共识)
           ↓
    8. CheckV质控
           ↓
    9. 高质量筛选
           ↓
    10. BUSCO过滤 (去细菌污染)
           ↓
    高质量病毒序列

┌─────────────────────────────────────────────────────────────────┐
│                  病毒库构建 (viruslib_pipeline.py)                │
└─────────────────────────────────────────────────────────────────┘
    多样本病毒序列
           ↓
    1. 合并并重命名 (vOTU1-vOTUn)
           ↓
    2. vclust去冗余 (ANI≥95%, qcov≥85%)
           ↓
    3. 提取代表序列
           ↓
    4. PhaBox2功能预测
           ↓
    非冗余病毒库 (vOTU库)

┌─────────────────────────────────────────────────────────────────┐
│                  下游分析 (run_downstream.py)                     │
└─────────────────────────────────────────────────────────────────┘
    病毒库 + 测序数据
           ↓
    CoverM 丰度定量
           ↓
    病毒丰度表
```

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/JustinRaoV/GutMicrobe-Virus.git
cd GutMicrobe-Virus
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置文件

编辑 `config/config.yaml` 选择使用的工具和参数：

```yaml
# 病毒检测工具选择
virus_detection:
  enable_checkv_prefilter: true
  enable_virsorter: true
  enable_dvf: true
  enable_vibrant: true
  enable_blastn: true
  min_tools_required: 1  # 最少几个工具检测到才认为是病毒

# BLASTN过滤阈值
parameters:
  blastn_pident: 50        # 序列一致性 ≥ 50%
  blastn_evalue: 1e-10     # E-value ≤ 1e-10
  blastn_qcovs: 80         # 查询覆盖度 ≥ 80%
```

### 4. 运行分析

```bash
# 单样本分析
python run_upstream.py sample_R1.fq.gz sample_R2.fq.gz \
    --start-from reads --host hg38 -t 32 -o results

# 查看结果
ls results/*/13.busco_filter/*/contigs.fa
```
