rule preprocess:
    input:
        r1=lambda wc: raw_input1(wc.sample),
        r2=lambda wc: raw_input2(wc.sample)
    output:
        r1=f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/1.trimmed/{{sample}}_R1.fastq",
        r2=f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/1.trimmed/{{sample}}_R2.fastq"
    threads: threads_for("fastp")
    resources:
        mem_mb=lambda wc, input, threads: mem_mb_for("fastp", size_mb=RAW_INPUT_MB.get(wc.sample, 0.0)),
        runtime=lambda wc, input, threads: runtime_for("fastp", size_mb=RAW_INPUT_MB.get(wc.sample, 0.0)),
        fastp=1
    params:
        fastp_cmd=tool_cmd("fastp"),
        fastp_params=config.get("tools", {}).get("params", {}).get("fastp", "")
    shell:
        (
            "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps preprocess "
            "--r1-in {input.r1} --r2-in {input.r2} --r1-out {output.r1} --r2-out {output.r2} "
            "--threads {threads} --fastp-cmd \"{params.fastp_cmd}\" --fastp-params \"{params.fastp_params}\" "
            + ("--mock" if MOCK_MODE else "")
        )


rule host_removal:
    input:
        r1=f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/1.trimmed/{{sample}}_R1.fastq",
        r2=f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/1.trimmed/{{sample}}_R2.fastq"
    output:
        r1=f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/2.host_removed/{{sample}}_R1.fastq",
        r2=f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/2.host_removed/{{sample}}_R2.fastq"
    threads: threads_for("bowtie2")
    resources:
        mem_mb=lambda wc, input, threads: mem_mb_for("bowtie2", size_mb=RAW_INPUT_MB.get(wc.sample, 0.0)),
        runtime=lambda wc, input, threads: runtime_for("bowtie2", size_mb=RAW_INPUT_MB.get(wc.sample, 0.0)),
        bowtie2=1
    params:
        host=lambda wc: host_name(wc.sample),
        host_index=lambda wc: (
            str(Path(DB["bowtie2_index"]).resolve() / host_name(wc.sample) / host_name(wc.sample))
            if host_name(wc.sample)
            else ""
        ),
        prefix=lambda wc: f"{WORK_ROOT}/{RUN_ID}/upstream/{wc.sample}/2.host_removed/{wc.sample}",
        bowtie2_cmd=tool_cmd("bowtie2")
    shell:
        (
            "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps host-removal "
            "--r1-in {input.r1} --r2-in {input.r2} --r1-out {output.r1} --r2-out {output.r2} "
            "--host \"{params.host}\" --host-index \"{params.host_index}\" --prefix \"{params.prefix}\" "
            "--threads {threads} --bowtie2-cmd \"{params.bowtie2_cmd}\" "
            + ("--mock" if MOCK_MODE else "")
        )


rule assembly:
    input:
        input1=lambda wc: raw_input1(wc.sample) if sample_mode(wc.sample) == "contigs" else f"{WORK_ROOT}/{RUN_ID}/upstream/{wc.sample}/2.host_removed/{wc.sample}_R1.fastq",
        input2=lambda wc: raw_input2(wc.sample) if sample_mode(wc.sample) == "contigs" else f"{WORK_ROOT}/{RUN_ID}/upstream/{wc.sample}/2.host_removed/{wc.sample}_R2.fastq"
    output:
        out=f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/3.assembly/final.contigs.fa"
    threads: threads_for("megahit")
    resources:
        mem_mb=lambda wc, input, threads: mem_mb_for("megahit", size_mb=RAW_INPUT_MB.get(wc.sample, 0.0)),
        runtime=lambda wc, input, threads: runtime_for("megahit", size_mb=RAW_INPUT_MB.get(wc.sample, 0.0)),
        megahit=1
    params:
        mode=lambda wc: sample_mode(wc.sample),
        sample=lambda wc: wc.sample,
        megahit_cmd=tool_cmd("megahit"),
        megahit_params=config.get("tools", {}).get("params", {}).get("megahit", "")
    shell:
        (
            "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps assembly "
            "--mode {params.mode} --sample {params.sample} --input1 {input.input1} --input2 {input.input2} --out {output.out} "
            "--threads {threads} --megahit-cmd \"{params.megahit_cmd}\" --megahit-params \"{params.megahit_params}\" "
            + ("--mock" if MOCK_MODE else "")
        )


rule vsearch:
    input:
        f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/3.assembly/final.contigs.fa"
    output:
        f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/4.vsearch/contigs.fa"
    threads: threads_for("vsearch")
    resources:
        mem_mb=lambda wc, input, threads: mem_mb_for("vsearch", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
        runtime=lambda wc, input, threads: runtime_for("vsearch", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
        vsearch=1
    params:
        vsearch_cmd=tool_cmd("vsearch"),
        vsearch_min_len=config.get("tools", {}).get("params", {}).get("vsearch_min_len", 1500)
    shell:
        (
            "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps vsearch "
            "--input {input} --out {output} --vsearch-cmd \"{params.vsearch_cmd}\" --min-len {params.vsearch_min_len} "
            + ("--mock" if MOCK_MODE else "")
        )


if TOOLS.get("virsorter", False):
    rule detect_virsorter:
        input:
            f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/4.vsearch/contigs.fa"
        output:
            f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/5.virsorter/contigs.fa"
        threads: threads_for("virsorter")
        resources:
            mem_mb=lambda wc, input, threads: mem_mb_for("virsorter", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
            runtime=lambda wc, input, threads: runtime_for("virsorter", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
            virsorter=1
        params:
            db=str(Path(DB["virsorter"]).resolve()),
            wd=lambda wc: f"{WORK_ROOT}/{RUN_ID}/upstream/{wc.sample}/5.virsorter/_tmp",
            tool_cmd=tool_cmd("virsorter")
        shell:
            (
                "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps detect --tool virsorter "
                "--tool-cmd \"{params.tool_cmd}\" --db {params.db} --input {input} --workdir {params.wd} --out {output} --threads {threads} "
                + ("--mock" if MOCK_MODE else "")
            )

if TOOLS.get("genomad", False):
    rule detect_genomad:
        input:
            f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/4.vsearch/contigs.fa"
        output:
            f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/6.genomad/contigs.fa"
        threads: threads_for("genomad")
        resources:
            mem_mb=lambda wc, input, threads: mem_mb_for("genomad", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
            runtime=lambda wc, input, threads: runtime_for("genomad", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
            genomad=1
        params:
            db=str(Path(DB["genomad"]).resolve()),
            wd=lambda wc: f"{WORK_ROOT}/{RUN_ID}/upstream/{wc.sample}/6.genomad/_tmp",
            tool_cmd=tool_cmd("genomad")
        shell:
            (
                "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps detect --tool genomad "
                "--tool-cmd \"{params.tool_cmd}\" --db {params.db} --input {input} --workdir {params.wd} --out {output} --threads {threads} "
                + ("--mock" if MOCK_MODE else "")
            )


rule combine:
    input:
        lambda wc: detect_outputs(wc.sample)
    output:
        f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/7.combination/contigs.fa"
    threads: 1
    resources:
        mem_mb=lambda wc, input, threads: mem_mb_for("gmv", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
        runtime=lambda wc, input, threads: runtime_for("gmv", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
        gmv=1
    shell:
        "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps combine --inputs {input} --out {output}"


rule checkv:
    input:
        f"{WORK_ROOT}/{RUN_ID}/upstream/{{sample}}/7.combination/contigs.fa"
    output:
        summary=f"{RESULTS_ROOT}/{RUN_ID}/upstream/{{sample}}/8.checkv/quality_summary.tsv",
        contigs=f"{RESULTS_ROOT}/{RUN_ID}/upstream/{{sample}}/8.checkv/contigs.fa"
    threads: threads_for("checkv")
    resources:
        mem_mb=lambda wc, input, threads: mem_mb_for("checkv", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
        runtime=lambda wc, input, threads: runtime_for("checkv", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
        checkv=1
    params:
        out_dir=lambda wc: f"{RESULTS_ROOT}/{RUN_ID}/upstream/{wc.sample}/8.checkv",
        db=str(Path(DB["checkv"]).resolve()),
        checkv_cmd=tool_cmd("checkv")
    shell:
        (
            "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps checkv "
            "--input {input} --out-dir {params.out_dir} --db {params.db} --checkv-cmd \"{params.checkv_cmd}\" --threads {threads} "
            + ("--mock" if MOCK_MODE else "")
        )


rule high_quality:
    input:
        fasta=f"{RESULTS_ROOT}/{RUN_ID}/upstream/{{sample}}/8.checkv/contigs.fa",
        summary=f"{RESULTS_ROOT}/{RUN_ID}/upstream/{{sample}}/8.checkv/quality_summary.tsv"
    output:
        f"{RESULTS_ROOT}/{RUN_ID}/upstream/{{sample}}/9.high_quality/contigs.fa"
    threads: 1
    resources:
        mem_mb=lambda wc, input, threads: mem_mb_for("gmv", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
        runtime=lambda wc, input, threads: runtime_for("gmv", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
        gmv=1
    shell:
        "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps high-quality --input {input.fasta} --summary {input.summary} --out {output}"


rule busco_filter:
    input:
        f"{RESULTS_ROOT}/{RUN_ID}/upstream/{{sample}}/9.high_quality/contigs.fa"
    output:
        f"{RESULTS_ROOT}/{RUN_ID}/upstream/{{sample}}/11.busco_filter/contigs.fa"
    threads: threads_for("busco")
    resources:
        mem_mb=lambda wc, input, threads: mem_mb_for("busco", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
        runtime=lambda wc, input, threads: runtime_for("busco", size_mb=_safe_input_size_mb(input) or RAW_INPUT_MB.get(wc.sample, 0.0)),
        busco=1
    params:
        sample=lambda wc: wc.sample,
        busco_cmd=tool_cmd("busco"),
        busco_db=str(Path(DB["busco"]).resolve()),
        ratio_threshold=config.get("tools", {}).get("params", {}).get("busco_ratio_threshold", 0.05),
    shell:
        (
            "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps busco "
            "--input {input} --out {output} --sample {params.sample} --threads {threads} "
            "--busco-cmd \"{params.busco_cmd}\" --busco-db \"{params.busco_db}\" "
            "--ratio-threshold {params.ratio_threshold} "
            + ("--mock" if MOCK_MODE else "")
        )
