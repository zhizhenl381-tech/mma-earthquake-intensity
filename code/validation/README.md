# Code checks

This folder contains validation code only. Research inputs, evidence examples,
precomputed results and historical check records are not included.

Run the offline tests and CLI check, writing new records outside the code package:

```sh
python -B validation/run_checks.py --out /path/to/check_results
```

The tests construct minimal synthetic responses in memory and use temporary files.
They do not call live model APIs. To also replay external workbooks:

```sh
python -B validation/run_checks.py --out /path/to/check_results \
  --data-dir /path/to/input_workbooks \
  --manifest /path/to/source_manifest.json \
  --skip-saved-comparison
```

`--manifest` is optional and requires `--data-dir`. Use
`--skip-saved-comparison` only when cached historical fields use a different quality
mapping; raw input consistency checks remain enabled. An optional `--scored-items`
argument runs deterministic aggregation on an external scored-item JSON file.
`--extra-deps` can supply an existing local Python dependency directory.

To compare quality mappings, explicitly supply every input and output path:

```sh
python -B validation/compare_mapping.py \
  --data-dir /path/to/input_workbooks \
  --legacy-weights /path/to/historical/weights.py \
  --current-grids /path/to/current/ablation_grids.csv \
  --out /path/to/mapping_comparison.json
```

No sibling code package or bundled study dataset is assumed. Numerical
reproduction of a study requires its complete external workbook inputs.
