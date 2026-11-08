# Quality mapping correction

The corrected penalty priority is INAY > INRE > INRY > LOCY. The bit positions
remain INRE, INRY, LOCY, INAY. A value of one denotes a defect. Grade L increases
as quality decreases, and the aggregation coefficient is (17-L)/16.

| L | Code | Defects | Coefficient |
|---:|:---:|---|---:|
| 1 | 0000 | None | 1 |
| 2 | 0010 | LOCY | 15/16 |
| 3 | 0100 | INRY | 14/16 |
| 4 | 1000 | INRE | 13/16 |
| 5 | 0110 | INRY, LOCY | 12/16 |
| 6 | 1010 | INRE, LOCY | 11/16 |
| 7 | 1100 | INRE, INRY | 10/16 |
| 8 | 1110 | INRE, INRY, LOCY | 9/16 |
| 9 | 0001 | INAY | 8/16 |
| 10 | 0011 | LOCY, INAY | 7/16 |
| 11 | 0101 | INRY, INAY | 6/16 |
| 12 | 1001 | INRE, INAY | 5/16 |
| 13 | 0111 | INRY, LOCY, INAY | 4/16 |
| 14 | 1011 | INRE, LOCY, INAY | 3/16 |
| 15 | 1101 | INRE, INRY, INAY | 2/16 |
| 16 | 1111 | All four | 1/16 |

This changes eight of the sixteen historical code-to-coefficient entries.
New-post processing and every ablation/noise/calibration weight call use the same
corrected function. Prompt text, bit definitions, DYFI item scoring, location
coefficients and CDI conversion are unchanged. Recalculation preserves the raw
defect codes, CWS and location fields in externally supplied inputs.

## External inputs and verification

Research workbooks, cached results and historical verification records are not
included in this code package. Supply an external workbook directory. If its
cached grades, coefficients, post weights and grid estimates use the historical
mapping, use:

```sh
python run.py verify-sources --data-dir "/path/to/input_workbooks" --manifest "/path/to/source_manifest.json"
python run.py reproduce --data-dir "/path/to/input_workbooks" --skip-saved-comparison --out "/path/to/results"
```

The explicit option prevents a comparison to historical derived fields from being
mistaken for a successful validation of the corrected mapping. Raw input
consistency checks remain enabled. Omitting the option retains strict comparison
and reports a mismatch when old values differ from the active mapping.

The manifest is supplied separately. Offline tests are in `tests`; scripts in
`validation` write new check outputs to an explicitly selected external output
directory. The main replay does not recompute supplementary four-event workbooks.

This software change does not establish that manuscript results are unchanged.
The new `verification.json` reports the number and maximum magnitude of A0 grid
differences from externally supplied saved values. Manuscript results and their
interpretation require validation against the corresponding research inputs.

## Compare mappings on external inputs

To compare A0 while holding raw defect codes, post CWS and location coefficients
fixed, supply the workbook directory, the earlier weights implementation and the
current replay export explicitly:

```sh
python validation/compare_mapping.py --data-dir "/path/to/input_workbooks" --legacy-weights "/path/to/legacy_weights.py" --current-grids "/path/to/results/ablation_grids.csv" --out "/path/to/mapping_comparison.json"
```

The generated report measures grid-level differences for those inputs. The
mapping definition alone does not determine their size or establish that saved
results used the corrected mapping.
