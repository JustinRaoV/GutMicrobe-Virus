rule viruslib_merge:
    input:
        expand(f"results/{RUN_ID}/upstream/{{sample}}/11.busco_filter/contigs.fa", sample=SAMPLES)
    output:
        f"work/{RUN_ID}/viruslib/1.merge/all_contigs.fa"
    shell:
        "PYTHONPATH={workflow.basedir}/src python -m gmv.workflow.steps viruslib-merge --inputs {input} --out {output}"


rule viruslib_dedup:
    input:
        f"work/{RUN_ID}/viruslib/1.merge/all_contigs.fa"
    output:
        fasta=f"results/{RUN_ID}/viruslib/viruslib_nr.fa",
        clusters=f"results/{RUN_ID}/viruslib/clusters.tsv"
    shell:
        "PYTHONPATH={workflow.basedir}/src python -m gmv.workflow.steps viruslib-dedup --input {input} --out {output.fasta} --clusters {output.clusters}"


rule viruslib_annotation:
    input:
        f"results/{RUN_ID}/viruslib/viruslib_nr.fa"
    output:
        f"results/{RUN_ID}/viruslib/phabox2/summary.tsv"
    shell:
        "mkdir -p $(dirname {output}) && printf 'votu\tannotation\n' > {output}"
