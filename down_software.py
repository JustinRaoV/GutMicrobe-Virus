import subprocess
import os
import sys


def run_phabox2(sample, output, threads, db, sample_name):
    print("Run phabox2")
    if os.path.exists(f"{output}/13.phabox2") is True:
        subprocess.call([f"rm -rf {output}/13.phabox2"], shell=True)

    subprocess.call([f"mkdir {output}/13.phabox2"], shell=True)
    print(f"phabox2 --task end_to_end --dbdir {db}/phabox/phabox_db_v2 --skip Y \
        --outpth  {output}/13.phabox2/{sample_name} \
        --contigs {sample} \
        --threads {threads}")

    ret = subprocess.call([f"phabox2 --task end_to_end --dbdir {db}/phabox/phabox_db_v2 --skip Y \
         --outpth  {output}/13.phabox2/{sample_name} \
         --contigs {sample} \
         --threads {threads}"], shell=True)
    if ret != 0:
        print("Warning: phabox2 error")
