rule downstream_quant:
    input:
        viruslib=f"{RESULTS_ROOT}/{RUN_ID}/viruslib/viruslib_nr.fa"
    output:
        f"{RESULTS_ROOT}/{RUN_ID}/downstream/{{method}}/abundance.tsv"
    threads: DEFAULT_THREADS
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
