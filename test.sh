#!/bin/bash

module load CentOS/7.9/Anaconda3/24.5.0
cd /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/testflow/GutMicrobe-Virus

source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/ivirp
python run_upstream.py \
    /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/zlq_23212030027/raw_data/AS/fastq/AS_taixing/TXAS01_1.fq.gz \
    /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/zlq_23212030027/raw_data/AS/fastq/AS_taixing/TXAS01_2.fq.gz \
    -t 64 \
    --host hg38 \
    -a 0 -k \
    -o output