#!/bin/bash

# 加载模块并激活上游环境
module load CentOS/7.9/Anaconda3/24.5.0
source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/ivirp

# 进入工作目录
cd /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/testflow/GutMicrobe-Virus

/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/ivirp/bin/python run_upstream.py     ../data/testR1.fq.gz     ../data/testR2.fq.gz     -t 32     --host hg38      -k     -o /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/testflow/GutMicrobe-Virus/result --db /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/db

# 激活phadown环境并测试viruslib_pipeline
source activate activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/phabox2

/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/phabox2/bin/python viruslib_pipeline.py -t 32 -o /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/testflow/GutMicrobe-Virus/libresult --log-level INFO

# 激活phadown环境并测试run_downstream.py
# 使用原始fastq文件提取样本名称，自动找到host_removed文件和viruslib的contig和gene文件

/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/phabox2/bin/python run_downstream.py \
    ../data/testR1.fq.gz \
    ../data/testR2.fq.gz \
    --upstream-result /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/testflow/GutMicrobe-Virus/result \
    --viruslib-result /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/testflow/GutMicrobe-Virus/libresult \
    -t 32 \
    -o /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/testflow/GutMicrobe-Virus/downstream_test_out \
    --log-level INFO