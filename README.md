# GutMicrobe-Virus Analysis Pipeline

一个集成的病毒组分析流程，提供从原始测序数据到高质量病毒contigs鉴定，再到功能注释的全套解决方案。

本流程结合了https://github.com/li-bw18/iVirP 和https://github.com/KennthShang/PhaBOX，并进行了一些改进

## 📋 目录
• [功能特性](#-功能特性)
• [流程架构](#-流程架构)
• [环境安装](#-环境安装)
• [快速开始](#-快速开始)
• [使用指南](#-使用指南)
• [结果解读](#-结果解读)
• [数据库配置](#-数据库配置)
• [贡献指南](#-贡献指南)
• [许可协议](#-许可协议)

## 🌟 功能特性
• **全自动化分析**：一站式处理双端测序数据
• **严格质控体系**：
  • FastQC + Trimmomatic 数据清洗
  • 多宿主基因组过滤（支持hg38等）
  • ViromeQC质量报告
• **智能组装优化**：
  • SPAdes混合组装策略
  • VSearch长度过滤（≥1kb）
• **精准病毒鉴定**：
  • VirSorter2病毒特征识别
  • 多数据库Blastn验证（NCBI、GVD等）
• **质量评估体系**：
  • CheckV完整性评估
  • 97%相似度去冗余
• **下游功能分析**：
  • PHABOX2噬菌体注释
  • 耐药基因/毒力因子预测

## 🏗 流程架构
```ascii
原始数据 → 质量控制 → 宿主去除 → 宏基因组组装 → 病毒筛选 → 质量评估 → 功能注释
    │          │           │            │             │            │          │
    │          │           │            │             │            │          └─ PHABOX2分析
    │          │           │            │             │            └─ CheckV质量报告
    │          │           │            │             └─ 多数据库Blastn验证
    │          │           │            └─ VirSorter2分类
    │          │           └─ Bowtie2宿主过滤
    │          └─ Trimmomatic接头修剪
    └─ FastQC质控报告
```

## ⚙ 环境安装

### 通过Conda部署
```bash
git clone https://github.com/raojun1023/GutMicrobe-Virus.git
cd GutMicrobe-Virus
conda env create -f envs/ivirp_env.yaml
conda activate ivirp
```

### 数据库配置
1. 下载预编译数据库包
2. 修改`config/db_path.conf`：
```ini
[BOWTIE2_INDEX]
hg38 = /path/to/hg38_index

[VIRSORTER_DB]
v2 = /path/to/virsorter2_db

[PHABOX_DB]
v2 = /path/to/phabox_db
```

## 🚀 快速开始
### 单样本分析
```bash
# 上游分析
python run_upstream.py sample_1.fq.gz sample_2.fq.gz \
    --host hg38 \
    -t 32 \
    -o results/

# 下游注释
python run_downstream.py \
    -contigs results/12.final_non_dup/sample/final.fasta \
    -t 32 \
    -o annotations/
```

### 批量分析
```bash
# 生成任务脚本
bash scripts/generate_scripts.sh /path/to/input_data

# 提交集群任务
python scripts/generate_submit.py script/
```

## 📖 使用指南
### 输入文件要求
• 双端测序数据：`*_1.fq.gz`和`*_2.fq.gz`
• 宿主索引文件需预先构建

### 关键参数说明
| 参数             | 说明                          |
| ---------------- | ----------------------------- |
| `--host`         | 宿主基因组列表（逗号分隔）    |
| `-a`             | 接头类型（0-3对应不同试剂盒） |
| `-t`             | 计算线程数（推荐≥32）         |
| `--remove_inter` | 清理中间文件                  |

## 📊 结果解读
```
results/
├── 1.fastqc/            # 原始数据质量报告
├── 4.viromeQC/          # 质控后统计信息
├── 9.final-contigs/     # 候选病毒contigs
├── 10.checkv/           # 基因组完整性评估
├── 12.final_non_dup/    # 非冗余病毒基因组
└── 13.phabox2/          # 功能注释结果
```

## 🤝 贡献指南
欢迎通过以下方式参与改进：
1. 提交Issue报告问题
2. Fork仓库提交Pull Request
3. 完善文档和测试案例

## 📜 许可协议
本项目采用Apache 2.0开源协议，详情见[LICENSE](LICENSE)文件。
