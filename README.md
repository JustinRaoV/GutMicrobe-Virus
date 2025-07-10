# GutMicrobe-Virus Analysis Pipeline

一个高度模块化、结构清晰的肠道微生物病毒组分析流程，提供从原始测序数据到高质量病毒contigs鉴定、细菌污染过滤、功能注释的全套解决方案。

本流程结合了 https://github.com/li-bw18/iVirP 和 https://github.com/KennthShang/PhaBOX，支持多工具结果整合与灵活配置。

## 📋 目录
- [项目结构](#项目结构)
- [环境安装](#环境安装)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [结果解读](#结果解读)
- [数据库与配置](#数据库与配置)
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
│   └── paths.py
├── modules/                 # 病毒分析与流程主模块（所有分析流程相关代码均在此）
│   ├── virus_filter.py
│   ├── virus_detection.py
│   ├── virus_analysis.py
│   └── virus_quality.py
├── run_upstream.py          # 主程序入口
├── config.ini               # 配置文件
├── requirements.txt         # Python依赖
└── README.md                # 项目说明
```

> 详细结构与各模块说明请参考 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)。

## 🔬 分析流程概览

1. **质量控制**（fastp）
2. **宿主去除**（Bowtie2，支持多宿主联合过滤）
3. **组装**（MEGAHIT）
4. **病毒序列筛选**
   - VSEARCH 过滤短contigs
   - CheckV 预过滤（增强逻辑：病毒基因计数更高的contig也保留）
   - VirSorter、DeepVirFinder、VIBRANT、BLASTn 多工具识别
   - 结果整合（支持所有工具结果合并及用户自定义选择，详见 [config.ini] 的 [combination] 配置）
5. **质量评估**（CheckV）
6. **高质量病毒输出**
7. **细菌污染过滤**（BUSCO，自动输出 `filtered_contigs.fa`）
8. **（可选）去冗余、功能注释等下游分析**

## ⚙ 环境安装

### Conda 部署
```bash
git clone https://github.com/raojun1023/GutMicrobe-Virus.git
cd GutMicrobe-Virus
conda env create -f envs/ivirp_env.yaml
# 其他依赖请参考各工具官方文档
```

## 🗂 数据库与配置

- 下载所需数据库，修改 `config.ini`：
  - `[software]`：各软件路径
  - `[parameters]`：各工具参数
  - `[environment]`：conda环境与module操作（主环境 + 特殊工具环境）
  - `[combination]`：自定义合并哪些工具的结果
- 也可通过 `--db` 命令行参数指定数据库路径

### 环境配置策略

项目采用**主环境 + 特殊工具环境**的策略：

1. **主环境** (`main_conda_activate`)：大部分工具使用此环境
   - fastp, bowtie2, megahit, vsearch, checkv, blastn 等
   - 默认：`source activate ivirp`

2. **特殊工具环境**：只有真正需要的工具才使用特殊环境
   - VirSorter2：需要特定的conda环境
   - DeepVirFinder：需要特定的conda环境  
   - VIBRANT：需要特定的conda环境
   - BUSCO：需要特定的conda环境

### 配置示例
```ini
[software]
fastp = /path/to/fastp
bowtie2 = /path/to/bowtie2
megahit = /path/to/megahit
vsearch = /path/to/vsearch
virsorter = /path/to/virsorter
checkv = checkv
dvf = /path/to/dvf/bin/dvf.py
vibrant = VIBRANT_run.py

[parameters]
fastp_params = -l 90 -q 20 -u 30 -y --trim_poly_g
megahit_params = --k-list 21,29,39,59,79,99,119
vsearch_params = --sortbylength --minseqlength 500 --maxseqlength -1
virsorter_params = --min-length 3000 --min-score 0.5 --include-groups dsDNAphage,NCLDV,RNA,ssDNA,lavidaviridae

[environment]
# 主环境 - 大部分工具使用
main_conda_activate = source activate ivirp

# 特殊工具环境 - 只有真正需要的工具才配置
virsorter_module_unload = module unload CentOS/7.9/Anaconda3/24.5.0
virsorter_conda_activate = source activate /path/to/virsorter2/env
dvf_module_unload = module unload CentOS/7.9/Anaconda3/24.5.0
dvf_conda_activate = source activate /path/to/dvf/env
vibrant_module_unload = module unload CentOS/7.9/Anaconda3/24.5.0
vibrant_conda_activate = source activate /path/to/vibrant/env
busco_module_unload = module unload CentOS/7.9/Anaconda3/24.5.0
busco_conda_activate = source activate /path/to/busco/env

[combination]
# 选择合并哪些工具的结果，如 virsorter, dvf, vibrant, blastn
use_tools = virsorter,dvf,vibrant,blastn
```

## 🚀 快速开始

```bash
python run_upstream.py sample_1.fq.gz sample_2.fq.gz \
    --host hg38 \
    -t 32 \
    -o result/
```

| 参数         | 说明                        |
| ------------ | --------------------------- |
| `--host`     | 宿主基因组列表（逗号分隔）  |
| `-t`         | 计算线程数                  |
| `-o`         | 输出目录（如 result/）       |
| `--db`       | 数据库目录                  |

## 📖 使用指南

- 输入文件：双端测序数据，命名如 `*_1.fq.gz` 和 `*_2.fq.gz`
- 宿主索引文件需预先构建
- 输出目录结构自动生成
- 所有流程相关函数均可通过 `from modules import ...` 导入

## 📊 结果解读

```
result/
├── 1.trimmed/           # 质控后reads
├── 2.host_removed/      # 去宿主后reads
├── 3.assembly/          # 组装结果
├── 4.vsearch/           # 长contig筛选
├── 5.checkv_prefilter/  # CheckV预过滤（增强逻辑）
│   └── {sample}/
│       └── filtered_contigs.fa
├── 6.virsorter/         # VirSorter病毒识别
├── 7.dvf/               # DeepVirFinder病毒识别
│   └── {sample}/
│       ├── *_dvfpred.txt
│       ├── virus_dvf.list
│       └── dvf.fasta
├── 8.vibrant/           # VIBRANT病毒识别
│   └── {sample}/
│       └── VIBRANT_*
├── 9.blastn/            # 病毒数据库比对
├── 10.combination/      # 结果整合（支持自定义合并）
├── 11.checkv/           # 质量评估
├── 12.high_quality/     # 高质量病毒contigs
├── 13.busco_filter/     # BUSCO细菌污染过滤
│   └── {sample}/
│       └── filtered_contigs.fa
└── logs/                # 日志
```

- `13.busco_filter/{sample}/filtered_contigs.fa`：去除细菌污染后的高置信度病毒contigs

## 🦠 关键流程说明

- **CheckV 预过滤**：自动过滤包含过多宿主基因且宿主基因数量远高于病毒基因的contigs，同时保留病毒基因计数更高的contig。
- **结果整合**：支持所有工具结果合并，或通过 `[combination]` 配置自定义选择合并哪些工具结果。
- **BUSCO 过滤**：自动检测并去除含有细菌保守基因的contigs。

## 🔧 环境配置说明

- 支持服务器 module 环境与本地 conda 环境切换，详见 `config.ini` 示例。
- 环境名、路径等均可灵活配置。

## 🤝 贡献指南
欢迎通过以下方式参与改进：
1. 提交 Issue 报告问题
2. Fork 仓库提交 Pull Request
3. 完善文档和测试案例

## 📜 许可协议
本项目采用 Apache 2.0 开源协议，详情见 [LICENSE](LICENSE) 文件。

---

如需更详细的参数说明或下游分析脚本，请参考代码注释、[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) 或联系作者。
