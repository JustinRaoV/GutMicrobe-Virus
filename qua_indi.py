import argparse
from software.down_software import *


def parameter_input():
    parser = argparse.ArgumentParser(description='Analysis one by one')
    parser.add_argument('-o', '--output', help='Path to output directory', default=f'{os.getcwd()}/result')
    parser.add_argument('-t', '--threads', type=int, help='Threads used to run this pipeline (default:1)', default=1)
    parser.add_argument('-k', '--keep_log', action='store_true',
                        help='This parameter allows you to continue a killed run, but please make sure you have not changed any files in the output directory.',
                        default=False)
    parser.add_argument('-sample', help='Sample name')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    db = "/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/db"  # please adjust db here
    args = parameter_input()
    threads = args.threads
    output = args.output
    sample = args.sample

    # check if the user is using "keep_log"
    if args.keep_log is False:
        with open(f"{output}/{sample}log2.txt", "w") as f:
            f.write("0\n")

    # get log info
    with open(f"{output}/{sample}log2.txt", "r") as f:
        log = int(f.readline()[0: -1])
    # assess quality of sequencing with fastqc

    if log < 1:
        run_coverm(output, threads, sample)
        log = 1
        with open(f"{output}/{sample}log2.txt", "w") as f:
            f.write(f"{log}\n")

    # if log < 2:
    #     run_salmon(output, threads, sample)
    #     log = 2
    #     with open(f"{output}/{sample}log2.txt", "w") as f:
    #         f.write(f"{log}\n")
