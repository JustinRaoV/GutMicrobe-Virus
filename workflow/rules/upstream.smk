USE_VIRSORTER = int(bool(CFG.get("tools", {}).get("enabled", {}).get("virsorter", True)))
USE_GENOMAD = int(bool(CFG.get("tools", {}).get("enabled", {}).get("genomad", True)))

VSEARCH_MIN_LEN = int(CFG.get("tools", {}).get("params", {}).get("vsearch_min_len", 1500))
BUSCO_RATIO_THRESHOLD = float(CFG.get("tools", {}).get("params", {}).get("busco_ratio_threshold", 0.05))

DB_BOWTIE2 = CFG.get("database", {}).get("bowtie2_index", "")
DB_VIRSORTER = CFG.get("database", {}).get("virsorter", "")
DB_GENOMAD = CFG.get("database", {}).get("genomad", "")
DB_CHECKV = CFG.get("database", {}).get("checkv", "")


def up_wild(step: str, file_name: str) -> str:
    return str((WORK_ROOT / "upstream" / "{sample}" / step / file_name).resolve())


rule preprocess:
    input:
        r1=lambda wc: sample_r1(wc.sample),
        r2=lambda wc: sample_r2(wc.sample),
    output:
        r1=up_wild("1.preprocess", "{sample}_R1.fastq.gz"),
        r2=up_wild("1.preprocess", "{sample}_R2.fastq.gz"),
    threads: threads_for("fastp")
    resources:
        mem_mb=mem_for("fastp"),
        runtime=runtime_for("fastp"),
    params:
        fastp_cmd=tool_cmd("fastp"),
        fastp_params=CFG.get("tools", {}).get("params", {}).get("fastp", ""),
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps preprocess \
          --r1-in {input.r1} \
          --r2-in {input.r2} \
          --r1-out {output.r1} \
          --r2-out {output.r2} \
          --threads {threads} \
          --fastp-cmd "{params.fastp_cmd}" \
          --fastp-params "{params.fastp_params}"
        """


rule host_removal:
    input:
        r1=rules.preprocess.output.r1,
        r2=rules.preprocess.output.r2,
    output:
        r1=up_wild("2.host_removed", "{sample}_R1.fastq.gz"),
        r2=up_wild("2.host_removed", "{sample}_R2.fastq.gz"),
    threads: threads_for("bowtie2")
    resources:
        mem_mb=mem_for("bowtie2"),
        runtime=runtime_for("bowtie2"),
    params:
        bowtie2_cmd=tool_cmd("bowtie2"),
        index_prefix=DB_BOWTIE2,
        host=lambda wc: (SAMPLE_MAP[wc.sample].get("host", "") or "").strip(),
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps host_removal \
          --r1-in {input.r1} \
          --r2-in {input.r2} \
          --r1-out {output.r1} \
          --r2-out {output.r2} \
          --threads {threads} \
          --bowtie2-cmd "{params.bowtie2_cmd}" \
          --index-prefix "{params.index_prefix}" \
          --host "{params.host}"
        """


rule assembly:
    input:
        r1=rules.host_removal.output.r1,
        r2=rules.host_removal.output.r2,
    output:
        contigs=up_wild("3.assembly", "contigs.fa"),
    threads: threads_for("megahit")
    resources:
        mem_mb=mem_for("megahit"),
        runtime=runtime_for("megahit"),
    params:
        megahit_cmd=tool_cmd("megahit"),
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps assembly \
          --r1-in {input.r1} \
          --r2-in {input.r2} \
          --contigs-out {output.contigs} \
          --threads {threads} \
          --megahit-cmd "{params.megahit_cmd}"
        """


rule vsearch_filter:
    input:
        contigs=rules.assembly.output.contigs,
    output:
        contigs=up_wild("4.vsearch", "contigs.fa"),
    threads: threads_for("vsearch")
    resources:
        mem_mb=mem_for("vsearch"),
        runtime=runtime_for("vsearch"),
    params:
        min_len=VSEARCH_MIN_LEN,
        vsearch_cmd=tool_cmd("vsearch"),
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps vsearch_filter \
          --contigs-in {input.contigs} \
          --contigs-out {output.contigs} \
          --min-len {params.min_len} \
          --vsearch-cmd "{params.vsearch_cmd}"
        """


rule detect_virsorter:
    input:
        contigs=rules.vsearch_filter.output.contigs,
    output:
        contigs=up_wild("5.virsorter", "contigs.fa"),
    threads: threads_for("virsorter")
    resources:
        mem_mb=mem_for("virsorter"),
        runtime=runtime_for("virsorter"),
        virsorter=1,
    params:
        enabled=USE_VIRSORTER,
        cmd=tool_cmd("virsorter"),
        db=DB_VIRSORTER,
        work_dir=up_wild("5.virsorter", "_run"),
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps detect_virsorter \
          --contigs-in {input.contigs} \
          --out-fa {output.contigs} \
          --work-dir {params.work_dir} \
          --threads {threads} \
          --virsorter-cmd "{params.cmd}" \
          --db "{params.db}" \
          --enabled {params.enabled}
        """


rule detect_genomad:
    input:
        contigs=rules.vsearch_filter.output.contigs,
    output:
        contigs=up_wild("6.genomad", "contigs.fa"),
    threads: threads_for("genomad")
    resources:
        mem_mb=mem_for("genomad"),
        runtime=runtime_for("genomad"),
    params:
        enabled=USE_GENOMAD,
        cmd=tool_cmd("genomad"),
        db=DB_GENOMAD,
        work_dir=up_wild("6.genomad", "_run"),
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps detect_genomad \
          --contigs-in {input.contigs} \
          --out-fa {output.contigs} \
          --work-dir {params.work_dir} \
          --threads {threads} \
          --genomad-cmd "{params.cmd}" \
          --db "{params.db}" \
          --enabled {params.enabled}
        """


rule combine:
    input:
        virsorter=rules.detect_virsorter.output.contigs,
        genomad=rules.detect_genomad.output.contigs,
        fallback=rules.vsearch_filter.output.contigs,
    output:
        contigs=up_wild("7.combine", "contigs.fa"),
        info=up_wild("7.combine", "info.tsv"),
    threads: 1
    resources:
        mem_mb=mem_for("project"),
        runtime=runtime_for("project"),
    params:
        use_virsorter=USE_VIRSORTER,
        use_genomad=USE_GENOMAD,
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps combine \
          --virsorter-fa {input.virsorter} \
          --genomad-fa {input.genomad} \
          --fallback-fa {input.fallback} \
          --out-fa {output.contigs} \
          --info-tsv {output.info} \
          --use-virsorter {params.use_virsorter} \
          --use-genomad {params.use_genomad}
        """


rule checkv:
    input:
        contigs=rules.combine.output.contigs,
    output:
        quality=up_wild("8.checkv", "quality_summary.tsv"),
        contigs=up_wild("8.checkv", "contigs.fa"),
    threads: threads_for("checkv")
    resources:
        mem_mb=mem_for("checkv"),
        runtime=runtime_for("checkv"),
        checkv=1,
    params:
        cmd=tool_cmd("checkv"),
        db=DB_CHECKV,
        work_dir=up_wild("8.checkv", "_run"),
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps checkv \
          --contigs-in {input.contigs} \
          --quality-tsv {output.quality} \
          --out-fa {output.contigs} \
          --work-dir {params.work_dir} \
          --threads {threads} \
          --checkv-cmd "{params.cmd}" \
          --db "{params.db}"
        """


rule high_quality:
    input:
        contigs=rules.checkv.output.contigs,
        quality=rules.checkv.output.quality,
    output:
        contigs=up_wild("9.high_quality", "contigs.fa"),
    threads: 1
    resources:
        mem_mb=mem_for("project"),
        runtime=runtime_for("project"),
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps high_quality \
          --contigs-in {input.contigs} \
          --quality-tsv {input.quality} \
          --out-fa {output.contigs}
        """


rule busco_filter:
    input:
        contigs=rules.high_quality.output.contigs,
    output:
        contigs=up_wild("10.busco_filter", "contigs.fa"),
        metrics=up_wild("10.busco_filter", "metrics.json"),
    threads: 1
    resources:
        mem_mb=mem_for("project"),
        runtime=runtime_for("project"),
        busco=1,
    params:
        threshold=BUSCO_RATIO_THRESHOLD,
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps busco_filter \
          --contigs-in {input.contigs} \
          --out-fa {output.contigs} \
          --metrics-json {output.metrics} \
          --threshold {params.threshold}
        """
