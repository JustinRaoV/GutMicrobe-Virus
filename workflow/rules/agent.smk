rule agent_decision_log:
    input:
        expand(f"{RESULTS_ROOT}/{RUN_ID}/upstream/{{sample}}/11.busco_filter/contigs.fa", sample=SAMPLES),
        f"{RESULTS_ROOT}/{RUN_ID}/viruslib/viruslib_nr.fa",
        expand(f"{RESULTS_ROOT}/{RUN_ID}/downstream/{{method}}/abundance.tsv", method=DOWNSTREAM_METHODS)
    output:
        f"{RESULTS_ROOT}/{RUN_ID}/agent/decisions.jsonl"
    params:
        steps="preprocess,host_removal,assembly,vsearch,detect,combine,checkv,high_quality,busco_filter,viruslib,downstream"
    shell:
        "PYTHONPATH={workflow.basedir}/src python -m gmv.workflow.steps agent --steps {params.steps} --out {output}"
