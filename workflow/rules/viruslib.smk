rule viruslib_merge:
    input:
        expand(f"{RESULTS_ROOT}/{RUN_ID}/upstream/{{sample}}/11.busco_filter/contigs.fa", sample=SAMPLES)
    output:
        f"{WORK_ROOT}/{RUN_ID}/viruslib/1.merge/all_contigs.fa"
    shell:
        "PYTHONPATH={workflow.basedir}/src python -m gmv.workflow.steps viruslib-merge --inputs {input} --out {output}"


rule viruslib_dedup:
    input:
        f"{WORK_ROOT}/{RUN_ID}/viruslib/1.merge/all_contigs.fa"
    output:
        fasta=f"{RESULTS_ROOT}/{RUN_ID}/viruslib/viruslib_nr.fa",
        clusters=f"{RESULTS_ROOT}/{RUN_ID}/viruslib/clusters.tsv"
    threads: DEFAULT_THREADS
    params:
        workdir=f"{WORK_ROOT}/{RUN_ID}/viruslib/2.vclust/_tmp",
        vclust_cmd=tool_cmd("vclust"),
        min_ident=config.get("tools", {}).get("params", {}).get("vclust_min_ident", 0.95),
        ani=config.get("tools", {}).get("params", {}).get("vclust_ani", 0.95),
        qcov=config.get("tools", {}).get("params", {}).get("vclust_qcov", 0.85),
    shell:
        (
            "PYTHONPATH={workflow.basedir}/src python -m gmv.workflow.steps viruslib-dedup "
            "--input {input} --out {output.fasta} --clusters {output.clusters} "
            "--workdir {params.workdir} --threads {threads} "
            "--vclust-cmd \"{params.vclust_cmd}\" --min-ident {params.min_ident} --ani {params.ani} --qcov {params.qcov} "
            + ("--mock" if MOCK_MODE else "")
        )


if TOOLS.get("phabox2", False):
    rule viruslib_annotation:
        input:
            f"{RESULTS_ROOT}/{RUN_ID}/viruslib/viruslib_nr.fa"
        output:
            f"{RESULTS_ROOT}/{RUN_ID}/viruslib/phabox2/summary.tsv"
        threads: DEFAULT_THREADS
        params:
            out_dir=f"{RESULTS_ROOT}/{RUN_ID}/viruslib/phabox2",
            db=str(Path(DB["phabox2"]).resolve()),
            phabox2_cmd=tool_cmd("phabox2"),
        shell:
            (
                "PYTHONPATH={workflow.basedir}/src python -m gmv.workflow.steps viruslib-annotate "
                "--input {input} --out-dir {params.out_dir} --db {params.db} --threads {threads} "
                "--phabox2-cmd \"{params.phabox2_cmd}\" "
                + ("--mock" if MOCK_MODE else "")
            )

