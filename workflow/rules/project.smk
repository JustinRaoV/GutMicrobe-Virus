from pathlib import Path


USE_COVERM = int(bool(CFG.get("tools", {}).get("enabled", {}).get("coverm", True)))
COVERM_PARAMS = CFG.get("tools", {}).get("params", {}).get("coverm", "")


rule viruslib_merge:
    input:
        UPSTREAM_FINAL,
    output:
        merged=str((WORK_ROOT / "project" / "1.viruslib" / "all_contigs.fa").resolve()),
    threads: 1
    resources:
        mem_mb=mem_for("project"),
        runtime=runtime_for("project"),
    group: "project"
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps merge_contigs \
          --inputs {input} \
          --out-fa {output.merged}
        """


rule viruslib_dedup:
    input:
        merged=rules.viruslib_merge.output.merged,
    output:
        nr=str((RESULTS_ROOT / "viruslib" / "viruslib_nr.fa").resolve()),
        clusters=str((RESULTS_ROOT / "viruslib" / "clusters.tsv").resolve()),
    threads: threads_for("vclust")
    resources:
        mem_mb=mem_for("project"),
        runtime=runtime_for("project"),
    group: "project"
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps dedup \
          --in-fa {input.merged} \
          --out-fa {output.nr} \
          --clusters-tsv {output.clusters}
        """


rule downstream_quant:
    input:
        viruslib=rules.viruslib_dedup.output.nr,
        sample_sheet=str(SAMPLE_SHEET),
    output:
        abundance=str((RESULTS_ROOT / "downstream" / "abundance.tsv").resolve()),
    threads: threads_for("coverm")
    resources:
        mem_mb=mem_for_coverm,
        runtime=runtime_for_coverm,
    params:
        enabled=USE_COVERM,
        coverm_cmd=tool_cmd("coverm"),
        coverm_params=COVERM_PARAMS,
    group: "project"
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps downstream_quant \
          --viruslib-fa {input.viruslib} \
          --sample-sheet {input.sample_sheet} \
          --abundance-out {output.abundance} \
          --threads {threads} \
          --coverm-cmd "{params.coverm_cmd}" \
          --coverm-params "{params.coverm_params}" \
          --enabled {params.enabled}
        """


rule agent_decision_log:
    input:
        abundance=rules.downstream_quant.output.abundance,
    output:
        decisions=str((RESULTS_ROOT / "agent" / "decisions.jsonl").resolve()),
        report=str((RESULTS_ROOT / "agent" / "summary_zh.md").resolve()),
    threads: 1
    resources:
        mem_mb=mem_for("project"),
        runtime=runtime_for("project"),
    group: "project"
    shell:
        """
        {PYTHON_CMD} -m gmv.workflow.steps agent_decision_log \
          --run-id {RUN_ID} \
          --sample-sheet {SAMPLE_SHEET} \
          --work-root {WORK_ROOT} \
          --results-root {RESULTS_ROOT} \
          --out-jsonl {output.decisions} \
          --out-report {output.report}
        """
