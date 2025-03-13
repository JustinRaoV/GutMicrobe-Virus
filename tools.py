import subprocess
import os
import sys
import pandas as pd


def get_sample_name(file):
    if file[-6:] == '.fq.gz' or file[-6:] == '.fastq':
        return file[0: -6]
    elif file[-3:] == '.fq':
        return file[0: -3]
    elif file[-9:] == '.fastq.gz':
        return file[0: -9]


def create_output_file(output):
    if os.path.exists(output) is False:
        subprocess.call([f"mkdir {output}"], shell=True)
