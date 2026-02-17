rule downstream_quant:
    input:
        viruslib=f"{RESULTS_ROOT}/{RUN_ID}/viruslib/viruslib_nr.fa"
    output:
        f"{RESULTS_ROOT}/{RUN_ID}/downstream/{{method}}/abundance.tsv"
    group: "project"
    threads: threads_for("coverm")
    resources:
        mem_mb=lambda wc, input, threads: mem_mb_for("coverm", size_mb=TOTAL_READS_MB),
        runtime=lambda wc, input, threads: runtime_for("coverm", size_mb=TOTAL_READS_MB),
        coverm=1
    params:
        sample_sheet=str(sample_sheet),
        coverm_cmd=tool_cmd("coverm"),
        coverm_params=config.get("tools", {}).get("params", {}).get("coverm", ""),
    wildcard_constraints:
        method="|".join(DOWNSTREAM_METHODS)
    shell:
        (
            "PYTHONPATH={GMV_PYTHONPATH} python -m gmv.workflow.steps downstream "
            "--samples {params.sample_sheet} --method {wildcards.method} --viruslib {input.viruslib} "
            "--out {output} --threads {threads} "
            "--coverm-cmd \"{params.coverm_cmd}\" --coverm-params \"{params.coverm_params}\" "
            + ("--mock" if MOCK_MODE else "")
        )
