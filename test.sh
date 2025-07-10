#!/bin/bash

# 加载模块并激活上游环境
module load CentOS/7.9/Anaconda3/24.5.0
source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/ivirp

# 进入工作目录
cd /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/testflow/GutMicrobe-Virus

/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/ivirp/bin/python run_upstream.py     ../data/testR1.fq.gz     ../data/testR2.fq.gz     -t 32     --host hg38      -k     -o /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/testflow/GutMicrobe-Virus/result --db /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/db