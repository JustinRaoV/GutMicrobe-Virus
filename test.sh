#!/bin/bash

module load CentOS/7.9/Anaconda3/24.5.0
source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/ivirp

cd /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/testflow/GutMicrobe-Virus
python ./run.py ../data/TXAS01_1.fq.gz ../data/TXAS01_2.fq.gz -t 32 --host hg38  -a 0 -o output