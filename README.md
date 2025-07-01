# GutMicrobe-Virus Analysis Pipeline

一个集成的病毒组分析流程，提供从原始测序数据到高质量病毒contigs鉴定，再到功能注释的全套解决方案。

本流程结合了https://github.com/li-bw18/iVirP 和https://github.com/KennthShang/PhaBOX

在down_tools里提供了一系列下游分析代码，可以直接使用。
## 📋 目录
- [流程架构](#-流程架构)
- [环境安装](#-环境安装)
- [快速开始](#-快速开始)
- [使用指南](#-使用指南)
- [结果解读](#-结果解读)
- [数据库配置](#-数据库配置)
-  [贡献指南](#-贡献指南)
-  [许可协议](#-许可协议)


## 🏗 流程架构
1. **质量控制**
   - FastQC: 原始测序数据质量评估
   - Trimmomatic: 去除测序接头序列（支持Nextera/TruSeq系列接头）

2. **宿主序列去除**
   - Bowtie2: 基于预建索引过滤宿主序列（支持多宿主联合过滤）

3. **序列组装**
   - SPAdes: 对clean reads进行宏基因组组装

4. **病毒序列筛选**
   - VSEARCH: 过滤短contigs（<1.5kbp）
   - VirSorter: 基于序列特征预测病毒contigs
   - BLASTn: 比对病毒数据库筛选候选序列
   - 结果整合: 综合VirSorter和BLASTn预测结果

5. **质量评估与去冗余**
   - CheckV: 评估病毒contigs完整性与质量
   - VSEARCH: 聚类生成非冗余contigs（97%相似度阈值）

6. **数据整合与去冗余**
   - CD-HIT: 聚类生成非冗余contigs
   - phabox2: 全部下游步骤：宿主预测，活性预测，物种注释
7. **基因功能分析**
   - prodigal: 发现基因序列
   - eggnog：注释基因
8. **基因功能分析**
   - coverm: 统计contigs丰度
   - salmon：统计基因丰度
## ⚙ 环境安装

### 通过Conda部署
```bash
git clone https://github.com/raojun1023/GutMicrobe-Virus.git
cd GutMicrobe-Virus
conda env create -f envs/ivirp_env.yaml
conda env create -n phabox2 phabox2 coverm salmon cdhit
```

### 数据库配置
1. 下载预编译数据库包
2. 修改全局变量`db`：
```ini
db = '~/home/db'
```

## 🚀 快速开始
### 单样本分析
```bash
# 上游分析
python run_upstream.py sample_1.fq.gz sample_2.fq.gz \
    --host hg38 \
    -t 32 \
    -o results/

# 整体下游注释，需要在同一个results文件夹下完成
python run_downstream.py \
    -t 32 \
    -o results/

# 单样本逐个分析
python qua_indi.py \
    - sample sample
    -t 32 \
    -o results/

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
