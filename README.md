# GutMicrobe-Virus 高度自动化病毒组分析流程

一个面向大规模肠道微生物病毒组的全自动分析平台，支持从原始测序数据到高质量病毒contig鉴定、细菌污染过滤、功能注释和丰度分析的全流程，全部参数集中配置，批量任务一键生成与自动提交，适配服务器/集群环境。

## 📋 目录
- [项目结构](#项目结构)
- [环境安装](#环境安装)
- [快速开始](#快速开始)
- [批量任务与自动提交](#批量任务与自动提交)
- [配置文件说明](#配置文件说明)
- [分析流程概览](#分析流程概览)
- [结果解读](#结果解读)
- [贡献指南](#贡献指南)
- [许可协议](#许可协议)

## 🏗 项目结构
```
GutMicrobe-Virus/
├── core/                    # 核心模块（日志、配置、监控）
├── utils/                   # 通用工具函数
├── modules/                 # 分析主模块
├── run_upstream.py          # 上游分析主程序
├── run_downstream.py        # 下游分析主程序
├── viruslib_pipeline.py     # 病毒库构建流程
├── make.py                  # 批量脚本自动生成
├── config.ini               # 统一配置文件
├── requirements.txt         # Python依赖
├── test.sh                  # 测试脚本
└── README.md                # 项目说明
```

## ⚙ 环境安装

### Conda 环境
```bash
git clone https://github.com/raojun1023/GutMicrobe-Virus.git
cd GutMicrobe-Virus
# 建议根据实际需求手动创建和激活各分析所需conda环境
pip install -r requirements.txt
```

## 🚀 快速开始

### 单样本分析
#### 上游分析
```bash
python run_upstream.py sample_1.fq.gz sample_2.fq.gz --host hg38 -t 32 -o result/
```
#### 下游分析
```bash
python run_downstream.py sample_1.fq.gz sample_2.fq.gz --upstream-result result/ --viruslib-result libresult/ -t 32 -o downstream_out/
```
#### 病毒库构建
```bash
python viruslib_pipeline.py -t 32 -o libresult/ --db /path/to/db
```

### 项目清理

清理临时文件和无用目录：

```bash
# 查看将要清理的内容（试运行）
python cleanup.py --dry-run

# 执行实际清理
python cleanup.py

# 清理指定目录
python cleanup.py --project-dir /path/to/project
```

## 🗂 批量任务与自动提交

### 一键批量脚本生成
1. 配置 `config.ini` 的 `[batch]` 区块，指定 reads_dir、work_dir、环境激活命令、数据库路径、线程数、提交方式等。
2. 运行：
```bash
python make.py
```
3. 自动生成：
   - `up_script/`、`down_script/` 目录下每对reads生成独立shell脚本
   - `viruslib.sh`：病毒库构建脚本
   - `up_submit.txt`、`down_submit.txt`：批量提交命令（支持bash/qsub/sbatch）

### 提交任务
```bash
bash up_script/up_1.sh   # 或 sbatch/qsub ...
bash viruslib.sh
bash down_script/down_1.sh
```
或直接批量提交：
```bash
bash up_submit.txt
bash down_submit.txt
```

## 📝 配置文件说明

所有参数集中在 `config.ini`，无需修改代码。主要区块：
- `[batch]`：批量任务相关配置（工作目录、环境、reads目录、数据库、提交方式等）
- `[software]`：各软件路径
- `[parameters]`：各工具参数和阈值
- `[environment]`：conda环境与module操作
- `[database]`：数据库路径
- `[combination]`：多工具结果整合与命中阈值
- `[paths]`：结果路径

**示例（部分）：**
```ini
[batch]
work_dir = /abs/path/to/workdir
main_conda_activate = source activate /abs/path/to/conda_env
main_module_load = module load CentOS/7.9/Anaconda3/24.5.0
down_conda_activate = source activate /abs/path/to/conda_env2
reads_dir = ../data
db = /abs/path/to/db
threads = 32
submit_cmd = sbatch
submit_cpu_cores = 32
submit_memory = 200G

[parameters]
fastp_params = -l 90 -q 20 -u 30 -y --trim_poly_g --detect_adapter_for_pe
megahit_params = --k-list 21,29,39,59,79,99,119
...

[combination]
# 病毒识别工具选择配置 - 节省计算资源
use_blastn = 1        # 1=执行BLASTN，0=跳过执行
use_virsorter = 0     # 1=执行VirSorter，0=跳过执行
use_dvf = 1           # 1=执行DeepVirFinder，0=跳过执行
use_vibrant = 0       # 1=执行VIBRANT，0=跳过执行
use_checkv_prefilter = 1  # 1=执行CheckV预过滤，0=跳过执行
min_tools_hit = 2     # 至少需要多少个工具检测到才认为是病毒
```

### 🚀 智能工具选择功能

**节省计算资源的关键特性：**
- 通过 `[combination]` 配置段中的 `use_*` 开关控制是否执行特定的病毒检测工具
- 设置为 `0` 的工具将完全跳过执行，大幅节省计算时间和资源
- 系统会自动创建占位符文件，确保后续分析步骤正常运行
- 支持灵活的工具组合，可根据数据类型和分析需求定制流程

**使用示例：**
```ini
# 快速分析模式：只使用BLASTN和CheckV预过滤
use_blastn = 1
use_virsorter = 0
use_dvf = 0
use_vibrant = 0
use_checkv_prefilter = 1
min_tools_hit = 1

# 高精度模式：使用所有工具
use_blastn = 1
use_virsorter = 1
use_dvf = 1
use_vibrant = 1
use_checkv_prefilter = 1
min_tools_hit = 2
```

## 🔬 分析流程概览

### 上游分析
1. 质量控制（fastp）
2. 宿主去除（Bowtie2，支持多宿主）
3. 组装（MEGAHIT）
4. 病毒序列筛选（VSEARCH、CheckV预过滤、多工具识别、结果整合）
5. 质量评估（CheckV）
6. 高质量病毒输出
7. 细菌污染过滤（BUSCO）

### 下游分析
1. 病毒库构建（去冗余、注释等）
2. 丰度分析（coverm）

## 📊 结果解读

### 上游分析结果
```
result/
├── 1.trimmed/           # 质控后reads
├── 2.host_removed/      # 去宿主后reads
├── 3.assembly/          # 组装结果
├── ...
├── 13.busco_filter/     # BUSCO细菌污染过滤
└── logs/                # 日志
```

### 下游分析结果
```
result/
├── coverm_contig/       # Contig丰度分析
├── coverm_gene/         # 基因丰度分析
└── logs/
```

### 病毒库构建结果
```
viruslib/
├── viruslib_nr.fa       # 去冗余病毒contigs
├── gene_cdhit.fq        # 去冗余基因序列
└── logs/
```

## 🤝 贡献指南
欢迎通过以下方式参与改进：
1. 提交 Issue 报告问题
2. Fork 仓库提交 Pull Request
3. 完善文档和测试案例

## 📜 许可协议
本项目采用 Apache 2.0 开源协议，详情见 LICENSE 文件。
