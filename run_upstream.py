import argparse
from software.up_software import *


def parameter_input():
    parser = argparse.ArgumentParser(description='iVirP (Integrative virome pipeline)')
    parser.add_argument('input1', help='Path to the fastq(.gz) file of read1')
    parser.add_argument('input2', help='Path to the fastq(.gz) file of read2')
    parser.add_argument('--host',
                        help='Name(s) of Bowtie2 index(es) (default: None, skip host removal)',
                        default=None)
    parser.add_argument('-a', '--adapter', type=int, choices=[0, 1, 2, 3],
                        help='Adapter file code for Trimmomatic (0:NexteraPE-PE, 1:TruSeq3-PE-2, 2:TruSeq3-PE, 3:TruSeq2-PE)',
                        default=0)
    parser.add_argument('-o', '--output', help='Output directory path', default=os.path.join(os.getcwd(), 'result'))
    parser.add_argument('-t', '--threads', type=int, help='Number of threads (default:1)', default=1)
    parser.add_argument('-r', '--remove_inter_result', action='store_true',
                        help='Remove intermediate results (keeps final contigs)',
                        default=False)
    parser.add_argument('-k', '--keep_log', action='store_true',
                        help='Resume interrupted run (do not modify output dir)',
                        default=False)
    parser.add_argument('--db', help='Path to database directory',
                        default="/cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/db")
    return parser.parse_args()


if __name__ == '__main__':
    args = parameter_input()
    threads = args.threads
    output = args.output
    db = args.db
    sample1 = get_sample_name(args.input1.split('/')[-1])
    sample2 = get_sample_name(args.input2.split('/')[-1])
    sample = sample1[0: -2]

    # create the output directory if it does not exist
    create_output_file(output)

    log_path = os.path.join(output, "logs", f"{sample}log.txt")
    if not args.keep_log:
        with open(log_path, "w") as f:
            f.write("0\n")

    with open(log_path, "r") as f:
        log = int(f.readline().strip())

    # 步骤1: FastQC质量评估
    if log < 1:
        run_fastqc(output, args.input1, args.input2, threads)
        log = 1
        with open(log_path, "w") as f:
            f.write(f"{log}\n")

    # 步骤2: Trimmomatic去接头
    if log < 2:
        adapter_map = {
            1: "TruSeq3-PE-2.fa",
            2: "TruSeq3-PE.fa",
            3: "TruSeq2-PE.fa",
        }
        adapter_file = adapter_map.get(args.adapter, "NexteraPE-PE.fa")
        adapter_path = os.path.join(db, "adapters", adapter_file)
        run_trim(output, threads, args.input1, args.input2, sample1, sample2, adapter_path)
        log = 2
        with open(log_path, "w") as f:
            f.write(f"{log}\n")

    # 步骤3: Bowtie2去宿主序列
    if log < 3:
        if args.host:
            host_list = args.host.split(',')
            index_path = [os.path.join(db, "bowtie2_index", na, na) for na in host_list]
            run_bowtie2(output, threads, sample1, sample2, index_path, sample)
        else:
            print("Skipping host removal: No host index provided.")
        log = 3
        with open(log_path, "w") as f:
            f.write(f"{log}\n")

    # 步骤4: assemble contigs with spades
    if log < 4:
        run_spades(output, threads, sample1, sample2, sample)
        log = 4
        with open(log_path, "w") as f:
            f.write(f"{log}\n")

    # 步骤5: trim short contigs with vsearch
    if log < 5:
        run_vsearch_1(output, sample, threads)
        log = 5
        with open(log_path, "w") as f:
            f.write(f"{log}\n")

    # 步骤6: find viral contigs with virsorter
    if log < 6:
        run_virsorter(output, threads, sample, db)
        log = 6
        with open(log_path, "w") as f:
            f.write(f"{log}\n")

    # 步骤7: blastn比对
    if log < 7:
        run_blastn(output, threads, sample, db)  # 添加db参数
        log = 7
        with open(log_path, "w") as f:
            f.write(f"{log}\n")

    # 步骤8: 结果整合
    if log < 8:
        run_combination(output, sample)
        log = 8
        with open(log_path, "w") as f:
            f.write(f"{log}\n")

            # 步骤9: checkv质量评估
    if log < 9:
        run_checkv(output, threads, sample, db)
        log = 9
        with open(log_path, "w") as f:
            f.write(f"{log}\n")

    if log < 10:
        high_quality_output(output, sample)
        log = 10
        with open(log_path, "w") as f:
            f.write(f"{log}\n")

    # cluster contigs and get final non-redundant contigs
    # if log < 11:
    #     run_vsearch_2(output, threads, sample)
    #     log = 11
    #     with open(log_path, "w") as f:
    #         f.write(f"{log}\n")

    print("all steps finished")
    if args.remove_inter_result:
        remove_inter_result(output)
    print("Pipeline finished successfully.")
