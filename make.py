import os
import configparser


def get_read_pairs(reads_dir):
    files = sorted(
        [
            f
            for f in os.listdir(reads_dir)
            if f.endswith(".fq.gz") or f.endswith(".fastq.gz")
        ]
    )
    pairs = []
    for f in files:
        if f.endswith("1.fq.gz") or f.endswith("1.fastq.gz"):
            r1 = os.path.join(reads_dir, f)
            r2 = r1.replace("1.fq.gz", "2.fq.gz").replace("1.fastq.gz", "2.fastq.gz")
            if os.path.exists(r2):
                pairs.append((r1, r2))
    return pairs


def main():
    config = configparser.ConfigParser()
    config.read("config.ini")
    batch = config["batch"]
    reads_dir = batch["reads_dir"]
    work_dir = batch["work_dir"]
    main_conda = batch["main_conda_activate"]
    main_module = batch["main_module_load"]
    down_conda = batch["down_conda_activate"]
    db = batch["db"]
    upstream_result = batch["upstream_result"]
    viruslib_result = batch["viruslib_result"]
    downstream_result = batch["downstream_result"]
    host = batch["host"]
    threads = batch["threads"]
    submit_cmd = batch.get("submit_cmd", "bash")
    submit_cpu_cores = batch.get("submit_cpu_cores", "32")
    submit_memory = batch.get("submit_memory", "200G")

    # 1. 生成 up_script
    os.makedirs("up_script", exist_ok=True)
    read_pairs = get_read_pairs(reads_dir)
    for i, (r1, r2) in enumerate(read_pairs):
        script_path = os.path.join("up_script", f"up_{i+1}.sh")
        with open(script_path, "w") as f:
            f.write(
                f"""#!/bin/bash

# 加载模块并激活上游环境
{main_module}
{main_conda}

# 进入工作目录
cd {work_dir}

{main_conda.split()[-1]}/bin/python run_upstream.py \
    {r1} \
    {r2} \
    -t {threads} \
    --host {host} \
    -k \
    -o {upstream_result} \
    --db {db}
"""
            )

    # 2. 生成 viruslib.sh
    with open("viruslib.sh", "w") as f:
        f.write(
            f"""#!/bin/bash

# 加载模块并激活上游环境
{main_module}
{down_conda}

# 进入工作目录
cd {work_dir}

{down_conda.split()[-1]}/bin/python viruslib_pipeline.py -t {threads} -o {viruslib_result} --log-level INFO --db {db}
"""
        )

    # 3. 生成 down_script
    os.makedirs("down_script", exist_ok=True)
    for i, (r1, r2) in enumerate(read_pairs):
        script_path = os.path.join("down_script", f"down_{i+1}.sh")
        with open(script_path, "w") as f:
            f.write(
                f"""#!/bin/bash
# 加载模块并激活上游环境
{main_module}
{down_conda}

# 进入工作目录
cd {work_dir}

{down_conda.split()[-1]}/bin/python run_downstream.py \
    {r1} \
    {r2} \
    --upstream-result {upstream_result} \
    --viruslib-result {viruslib_result} \
    -t {threads} \
    -o {downstream_result} \
    --log-level INFO
"""
            )

    # 4. 生成 up_submit.txt
    with open("up_submit.txt", "w") as f:
        for script in sorted(os.listdir("up_script")):
            if script.endswith(".sh"):
                abs_path = os.path.abspath(os.path.join("up_script", script))
                if submit_cmd == "sbatch":
                    f.write(
                        f"sbatch -n {submit_cpu_cores} --mem={submit_memory} {abs_path}\n"
                    )
                elif submit_cmd == "qsub":
                    f.write(
                        f"qsub -l nodes=1:ppn={submit_cpu_cores},mem={submit_memory} {abs_path}\n"
                    )
                else:
                    f.write(f"{submit_cmd} {abs_path}\n")
    # 5. 生成 down_submit.txt
    with open("down_submit.txt", "w") as f:
        for script in sorted(os.listdir("down_script")):
            if script.endswith(".sh"):
                abs_path = os.path.abspath(os.path.join("down_script", script))
                if submit_cmd == "sbatch":
                    f.write(
                        f"sbatch -n {submit_cpu_cores} --mem={submit_memory} {abs_path}\n"
                    )
                elif submit_cmd == "qsub":
                    f.write(
                        f"qsub -l nodes=1:ppn={submit_cpu_cores},mem={submit_memory} {abs_path}\n"
                    )
                else:
                    f.write(f"{submit_cmd} {abs_path}\n")


if __name__ == "__main__":
    main()
