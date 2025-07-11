# GutMicrobe-Virus Analysis Pipeline

一个高度模块化、结构清晰的肠道微生物病毒组分析流程，提供从原始测序数据到高质量病毒contigs鉴定、细菌污染过滤、功能注释和丰度分析的全套解决方案。

本流程结合了 https://github.com/li-bw18/iVirP 和 https://github.com/KennthShang/PhaBOX，支持多工具结果整合与灵活配置，并新增了丰度分析功能。

## 📋 目录
- [项目结构](#项目结构)
- [环境安装](#环境安装)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [结果解读](#结果解读)
- [数据库与配置](#数据库与配置)
- [下游分析](#下游分析)
- [贡献指南](#贡献指南)
- [许可协议](#许可协议)

## 🏗 项目结构

```
GutMicrobe-Virus/
├── core/                    # 核心系统模块（日志、配置、执行、监控）
│   ├── logger.py
│   ├── config_manager.py
│   ├── executor.py
│   └── monitor.py
├── utils/                   # 通用工具函数与路径管理
│   ├── tools.py
│   ├── paths.py
│   └── common.py           # 通用工具函数
├── modules/                 # 病毒分析与流程主模块
│   ├── filter.py           # 数据过滤与组装
│   ├── virus_detection.py  # 病毒检测工具
│   ├── virus_analysis.py   # 病毒分析流程
│   ├── virus_quality.py    # 质量评估
│   ├── virus_filter.py     # 病毒过滤
│   ├── viruslib.py         # 病毒库构建
│   └── abundance_analysis.py # 丰度分析
├── run_upstream.py          # 上游分析主程序
├── run_downstream.py        # 下游分析主程序
├── viruslib_pipeline.py     # 病毒库构建流程
├── config.ini               # 统一配置文件
├── requirements.txt         # Python依赖
├── submit.py               # 批量提交脚本
├── test.sh                 # 测试脚本
└── README.md                # 项目说明
```

## 🔬 分析流程概览

### 上游分析流程
1. **质量控制**（fastp）
2. **宿主去除**（Bowtie2，支持多宿主联合过滤）
3. **组装**（MEGAHIT）
4. **病毒序列筛选**
   - VSEARCH 过滤短contigs
   - CheckV 预过滤（增强逻辑：病毒基因计数更高的contig也保留）
   - VirSorter、DeepVirFinder、VIBRANT、BLASTn 多工具识别
   - 结果整合（支持所有工具结果合并及用户自定义选择）
5. **质量评估**（CheckV）
6. **高质量病毒输出**
7. **细菌污染过滤**（BUSCO，自动输出 `filtered_contigs.fa`）

### 下游分析流程
1. **病毒库构建**（vclust去冗余、基因注释、物种注释等）
2. **丰度分析**（coverm计算contig和基因丰度）

## ⚙ 环境安装

### Conda 部署
```bash
git clone https://github.com/raojun1023/GutMicrobe-Virus.git
cd GutMicrobe-Virus
conda env create -f envs/ivirp_env.yaml
# 其他依赖请参考各工具官方文档
```

### Python依赖
```bash
pip install -r requirements.txt
```

## 🗂 数据库与配置

### 统一配置管理

项目采用统一的配置管理方式，所有参数均在 `config.ini` 中配置：

- `[software]`：各软件路径
- `[parameters]`：各工具参数和阈值配置
- `[environment]`：conda环境与module操作
- `[database]`：数据库路径配置
- `[combination]`：自定义合并哪些工具的结果
- `[paths]`：路径配置

### 环境配置策略

项目采用**主环境 + 特殊工具环境**的策略：

1. **主环境** (`main_conda_activate`)：大部分工具使用此环境
   - fastp, bowtie2, megahit, vsearch, checkv, blastn, coverm 等
   - 默认：`source activate ivirp`

2. **特殊工具环境**：只有真正需要的工具才使用特殊环境
   - VirSorter2：需要特定的conda环境
   - DeepVirFinder：需要特定的conda环境  
   - VIBRANT：需要特定的conda环境
   - BUSCO：需要特定的conda环境
   - EggNOG：需要特定的conda环境

### 配置示例
```ini
[software]
fastp = fastp
bowtie2 = bowtie2
megahit = megahit
vsearch = vsearch
virsorter = virsorter
checkv = checkv
dvf = /path/to/dvf.py
vibrant = VIBRANT_run.py
coverm = coverm

[parameters]
fastp_params = -l 90 -q 20 -u 30 -y --trim_poly_g --detect_adapter_for_pe
megahit_params = --k-list 21,29,39,59,79,99,119
vsearch_params = --minseqlength 500 --maxseqlength -1
virsorter_params = --min-length 3000 --min-score 0.5 --include-groups dsDNAphage,NCLDV,RNA,ssDNA,lavidaviridae
coverm_params = --min-read-percent-identity 95 --min-read-aligned-percent 75 -m count --output-format dense

# 过滤阈值配置
filter_ratio_threshold = 0.05
dvf_score_threshold = 0.9
dvf_pvalue_threshold = 0.01

# CD-HIT 参数配置
cdhit_identity = 0.95
cdhit_word_length = 10

[environment]
# 主环境 - 大部分工具使用
main_conda_activate = source activate ivirp

# 特殊工具环境
virsorter_module_unload = module unload CentOS/7.9/Anaconda3/24.5.0
virsorter_conda_activate = source activate /path/to/virsorter2/env
dvf_module_unload = module unload CentOS/7.9/Anaconda3/24.5.0
dvf_conda_activate = source activate /path/to/dvf/env

[database]
dvf_models = /path/to/dvf/models
phabox2_db = /path/to/phabox_db_v2
genomad_db = /path/to/genomad_db
eggnog5 = /path/to/eggnog5

[combination]
# 选择合并哪些工具的结果
use_blastn = 1
use_virsorter = 1
use_dvf = 1
use_vibrant = 1
use_checkv_prefilter = 1
```

## 🚀 快速开始

### 上游分析
```bash
python run_upstream.py sample_1.fq.gz sample_2.fq.gz \
    --host hg38 \
    -t 32 \
    -o result/
```

### 下游分析
```bash
python run_downstream.py sample_1.fq.gz sample_2.fq.gz \
    --viruslib viruslib/viruslib_nr.fa \
    --genes viruslib/gene_cdhit.fq \
    -t 32 \
    -o result/
```

### 病毒库构建
```bash
python viruslib_pipeline.py \
    --busco_dir result/13.busco_filter \
    --threads 32 \
    --db /path/to/database
```

| 参数         | 说明                        |
| ------------ | --------------------------- |
| `--host`     | 宿主基因组列表（逗号分隔）  |
| `--viruslib` | 病毒库contig文件路径        |
| `--genes`    | 病毒库基因文件路径          |
| `-t`         | 计算线程数                  |
| `-o`         | 输出目录                    |
| `--db`       | 数据库目录                  |

## 📖 使用指南

- **输入文件**：双端测序数据，命名如 `*_1.fq.gz` 和 `*_2.fq.gz`
- **宿主索引文件**：需预先构建
- **输出目录结构**：自动生成
- **配置管理**：所有参数通过 `config.ini` 统一管理
- **模块化设计**：所有流程相关函数均可通过 `from modules import ...` 导入

## 📊 结果解读

### 上游分析结果
```
result/
├── 1.trimmed/           # 质控后reads
├── 2.host_removed/      # 去宿主后reads
├── 3.assembly/          # 组装结果
├── 4.vsearch/           # 长contig筛选
├── 5.checkv_prefilter/  # CheckV预过滤
│   └── {sample}/
│       └── filtered_contigs.fa
├── 6.virsorter/         # VirSorter病毒识别
├── 7.dvf/               # DeepVirFinder病毒识别
│   └── {sample}/
│       ├── *_dvfpred.txt
│       ├── virus_dvf.list
│       └── dvf.fasta
├── 8.vibrant/           # VIBRANT病毒识别
├── 9.blastn/            # 病毒数据库比对
├── 10.combination/      # 结果整合
├── 11.checkv/           # 质量评估
├── 12.high_quality/     # 高质量病毒contigs
├── 13.busco_filter/     # BUSCO细菌污染过滤
│   └── {sample}/
│       └── filtered_contigs.fa
└── logs/                # 日志
```

### 下游分析结果
```
result/
├── coverm_contig/       # Contig丰度分析
│   └── {sample}_coverm.tsv
├── coverm_gene/         # 基因丰度分析
│   └── {sample}_gene_coverm.tsv
└── logs/                # 日志
```

### 病毒库构建结果
```
viruslib/
├── viruslib_nr.fa       # 去冗余后的病毒contigs
├── gene_cdhit.fq        # 去冗余后的基因序列
├── proteins.faa         # 预测的蛋白质序列
└── logs/                # 日志
```

## 🔧 下游分析

### 丰度分析
使用coverm工具计算样本中病毒contigs和基因的丰度：

- **Contig丰度**：基于病毒库中的contigs计算相对丰度
- **基因丰度**：基于病毒库中的基因序列计算相对丰度
- **参数配置**：所有coverm参数可在 `config.ini` 中调整

### 病毒库构建
- **去冗余**：使用vclust进行contig去冗余
- **基因注释**：使用prodigal-gv进行基因预测
- **物种注释**：使用geNomad进行病毒物种注释
- **功能注释**：使用EggNOG进行功能注释

## 🦠 关键流程说明

- **CheckV 预过滤**：自动过滤包含过多宿主基因且宿主基因数量远高于病毒基因的contigs，同时保留病毒基因计数更高的contig。
- **结果整合**：支持所有工具结果合并，或通过 `[combination]` 配置自定义选择合并哪些工具结果。
- **BUSCO 过滤**：自动检测并去除含有细菌保守基因的contigs。
- **配置统一化**：所有阈值和参数均在配置文件中管理，便于调整和维护。

## 🔧 环境配置说明

- 支持服务器 module 环境与本地 conda 环境切换
- 环境名、路径等均可灵活配置
- 所有参数通过 `config.ini` 统一管理，无需修改代码

## 🤝 贡献指南
欢迎通过以下方式参与改进：
1. 提交 Issue 报告问题
2. Fork 仓库提交 Pull Request
3. 完善文档和测试案例

## 📜 许可协议
本项目采用 Apache 2.0 开源协议，详情见 [LICENSE](LICENSE) 文件。

---

如需更详细的参数说明或技术支持，请参考代码注释或联系作者。
