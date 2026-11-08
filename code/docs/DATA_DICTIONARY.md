# Data dictionary

## External workbook interface

This code package does not contain data workbooks or a dataset manifest. Supply a complete workbook directory with `reproduce --data-dir`. The following names describe the loader interface; each workbook must retain the machine-readable fields required by `src/mma/io.py`. Presentation tables with deleted columns may not satisfy that interface. A separately supplied source manifest records filenames, byte sizes and SHA256 hashes and can be checked using `verify-sources --data-dir ... --manifest ...`.

| Workbook | Contents |
| --- | --- |
| `Agent10km帖子计算.xlsx` | 10-km post identifiers, quality codes, location coefficients and CWS values |
| `1kmAgent帖子数据整理.xlsx` | 1-km post records |
| `10kmAgent数据整理.xlsx` | 10-km Agent grid values |
| `1kmAgent网格数据整理.xlsx` | 1-km Agent grid values |
| `LLM10km网格数据整理.xlsx`, `1kmLLM网格.xlsx` | LLM grid values |
| `USGS_CDI10km网格数据整理.xlsx`, `1kmDYFI.xlsx` | DYFI reference values |
| `帖子与权重.xlsx` | Scale-specific post records and experiment weights |
| `网格与分组.xlsx` | Grid metadata, references and subgroup labels |
| `消融逐网格.xlsx` | Ablation grid-setting records |
| `噪声实验逐网格.xlsx` | Quality-noise grid-setting records |
| `校准实验.xlsx` | Calibration grid records |
| `校准因子.xlsx` | Seven subgroup factors and bootstrap intervals |

The main replay reads the fourteen workbooks above. Supplementary external four-event tables use the following conventions; the main `reproduce` command does not recompute them:

| Workbook | Contents |
| --- | --- |
| `新增四事件逐贴.xlsx` | Post records with eight item scores and weights |
| `新增四事件MMA网格聚合.xlsx` | Event-grid aggregation records |
| `新增四事件逐网格表.xlsx` | Event-grid predictions, references and covariates |

## Record keys

`源工作表行号` in `帖子与权重.xlsx` links to the Post_ID in `Agent10km帖子计算.xlsx`. Posts represented at both resolutions share identifiers and matching CWS values; rows at different resolutions are scale-specific records. The compact 1-km table is checked as a multiset of grid, quality code, CWS and location coefficient.

Grid metadata use resolution and grid identifier as the key. Evaluation uses the intersection of model predictions and references at each resolution. Missing reference values remain null and do not enter metric denominators.

The calibration table follows the A0 grid order. The importer checks scale, parent grid and post count before assigning the corresponding grid identifiers. Four-event tables use the event-grid key, formed from the event identifier and UTM grid identifier.

## Input fields

| Field | Meaning |
| --- | --- |
| `scale` | Resolution in kilometres |
| `post_id` | Post identifier |
| `grid`, `parent` | Grid and 10-km parent identifiers |
| `code` | Four-character quality defect code |
| `loc`, `radius` | Location coefficient and radius in kilometres |
| `cws` | Post-level weighted sum of item scores |
| `source_row` | Row link to the post workbook |
| `noise_u`, `noise_bit` | Uniform draw and bit number used in quality-noise experiments |
| `mode` | Text, visual or mixed modality label |
| `q1合法分数` through `q8合法分数` | Numeric item scores in the four-event post table |
| `η`, `κ`, `最终权重` | Grid calibration factors and resulting post weight |

## Output fields

`sum_weights`, `sum_squared_weights` and `sum_weighted_cws` are aggregation statistics. `mean_cws`, `raw_cdi` and `cdi` are the grid score, uncapped conversion and capped intensity. `ess` is effective sample size. `ci_low`, `ci_high` and `ci_width` are bootstrap interval statistics. `bootstrap_seed` and `resample_n` identify the random calculation.

`ref_cdi`, `absolute_error`, `integer_gap`, `error_ge1` and `error_ge2` are comparison fields. `eta` and `kappa` are populated for C_FULLFIT. Generated results are written to the `--out` directory selected for the run. No precomputed results or historical verification records are included in this package.
