python run_upstream.py     /public/group_share_data/TonyWuLab/rj/data/test_virus/SRR10983056_1.fastq.gz     /public/group_share_data/TonyWuLab/rj/data/test_virus/SRR10983056_2.fastq.gz     -t 8     --host hg38      -k     -o /public/group_share_data/TonyWuLab/rj/testoutput

#!/bin/bash

module load CentOS/7.9/Anaconda3/24.5.0
cd /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/workflow/GutMicrobe-Virus-dev

source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/phabox2
python ./run_all_downstream.py -t 64  -o output