# Raw Input Layout

Place your sample sheet and raw inputs here.

## Required sample sheet

Path default: `raw/samples.tsv`

Columns:

- `sample`
- `mode` (`reads` or `contigs`)
- `input1`
- `input2` (required for reads)
- `host` (optional)

Example:

```tsv
sample	mode	input1	input2	host
S1	reads	/path/to/S1_R1.fastq.gz	/path/to/S1_R2.fastq.gz	human
S2	contigs	/path/to/S2_contigs.fa		
```
