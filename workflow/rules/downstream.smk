rule downstream_quant:
    input:
        viruslib=f"results/{RUN_ID}/viruslib/viruslib_nr.fa"
    output:
        f"results/{RUN_ID}/downstream/{{method}}/abundance.tsv"
    params:
        sample_sheet=str(sample_sheet)
    wildcard_constraints:
        method="|".join(DOWNSTREAM_METHODS)
    shell:
        "PYTHONPATH={workflow.basedir}/src python -m gmv.workflow.steps downstream --samples {params.sample_sheet} --method {wildcards.method} --out {output}"
