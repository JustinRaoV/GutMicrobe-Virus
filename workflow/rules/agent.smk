rule agent_decision_log:
    input:
        expand(f"results/{RUN_ID}/upstream/{{sample}}/11.busco_filter/contigs.fa", sample=SAMPLES),
        f"results/{RUN_ID}/viruslib/viruslib_nr.fa",
        expand(f"results/{RUN_ID}/downstream/{{method}}/abundance.tsv", method=DOWNSTREAM_METHODS)
    output:
        f"results/{RUN_ID}/agent/decisions.jsonl"
    params:
        steps="preprocess,host_removal,assembly,vsearch,detect,combine,checkv,high_quality,busco_filter,viruslib,downstream"
    shell:
        "PYTHONPATH={workflow.basedir}/src python -m gmv.workflow.steps agent --steps {params.steps} --out {output}"
