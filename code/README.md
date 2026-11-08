# MMA code and Agent framework

Python implementation accompanying *AI-Agent- and Social Media–Based Earthquake Intensity Assessment: A Case Study of the Myanmar Earthquake*.

This package contains the MMA source code, Agent workflow, prompt templates, JSON schemas, configurations and documentation. Supply input data in a separate directory.

Quality weighting uses the defect-bit order INRE, INRY, LOCY, INAY and the penalty priority **INAY > INRE > INRY > LOCY**. The sixteen quality coefficients are defined in [the methods](docs/METHODS.md#2-quality-coefficients).

The framework provides multimodal model adapters, a static processing workflow, Appendix D prompts, four-bit quality weighting, geolocation weighting, closed-world DYFI scoring, UTM aggregation, effective sample size, weighted bootstrap, and ablation, noise and calibration calculations.

## Installation

Python 3.11 or later is required. From this folder:

```sh
python -m venv .venv
```

Activate the environment, then install:

```sh
python -m pip install -r requirements.txt
python -m pip install --no-deps .
```

`requirements-tested.txt` provides pinned dependency versions. Commands below run directly from this source folder. An installed `mma` command accepts `--root /path/to/code_package` to locate configurations, prompts and schemas.

## Recompute external workbook inputs

Prepare the complete machine-input workbooks described in [the data dictionary](docs/DATA_DICTIONARY.md), then provide their directory explicitly:

```sh
python run.py reproduce --data-dir "/path/to/input_workbooks" --out "/path/to/results"
```

By default, replay compares stored quality grades, coefficients, weights and results with computed values. To calculate outputs without comparing these stored derived fields, add `--skip-saved-comparison`:

```sh
python run.py reproduce --data-dir "/path/to/input_workbooks" --skip-saved-comparison --out "/path/to/results"
```

Raw input checks remain enabled, including defect codes, CWS values, location coefficients and post-to-grid relationships. Weights and grid results are computed from the supplied inputs and the configured rules.

The replay recomputes all 14 settings at both resolutions. Output files are:

| File | Contents |
| --- | --- |
| `ablation_grids.csv` | A0, A1, four A2 settings and four A3 settings |
| `noise_grids.csv` | A4_05, A4_10 and A4_20 |
| `calibration_grids.csv` | C_FULLFIT |
| `metrics.csv` | Common-grid MAE, RMSE, integer-grade errors and linear weighted kappa |
| `calibration_factors.json` | Seven subgroup factors and their bootstrap draws |
| `verification.json` | Numerical comparisons and source-file checksums |

To verify external workbooks against a separately maintained manifest:

```sh
python run.py verify-sources --data-dir "/path/to/input_workbooks" --manifest "/path/to/source_manifest.json"
```

The manifest uses a JSON object with a `files` member containing workbook filenames, byte sizes and SHA256 hashes. This package does not include a dataset manifest. The main replay reads the fourteen main-experiment workbooks; supplementary four-event tables are outside that replay.

## Aggregate external item scores

```sh
python run.py example --input "/path/to/scored_items.json" --out "/path/to/item_results.json"
```

The input JSON contains `seed` and `posts`; each post supplies `scores` (eight numeric scores or nulls), `evidence_code` and `radius_km`. This entry point exercises item-specific unknown masks, weighted item means, CWS, CDI, ESS and weighted bootstrap without a model request. No scored-item dataset is bundled.

## Process new posts

Set `OPENAI_API_KEY` and `GEMINI_API_KEY` in the execution environment. Configure model IDs in `configs/models.json`, or set `MMA_GEMINI_MODEL` and `MMA_OPENAI_MODEL` explicitly. Set the intended event context and time filters in `configs/event.json` or supply `--event`.

```sh
python run.py infer --input "/path/to/raw_posts.jsonl" --out "/path/to/model_run"
```

Add `--baseline` to execute the direct LLM baseline. The fixed registry executes:

1. Gemini intermediate evidence representation.
2. GPT quality assessment.
3. GPT closed-world DYFI item extraction.
4. Deterministic answer-to-score mapping and spatial assignment.
5. Item-specific grid aggregation, CDI, ESS and bootstrap.

Each input line is a JSON object following `schemas/raw_post.schema.json`. Local image, audio and video files are passed to Gemini as typed inline media. Existing Gemini file URIs can also be supplied. Resolved coordinates and location radius are carried in `geolocation`; `mma.geocoding` provides an offline place-table reader and a Google Maps adapter. Google Maps results use the maximum center-to-bounds-corner distance as the equivalent radius.

The inference folder contains `post_outputs.json`, `grid_results.csv`, `run_manifest.json` and `model_calls/calls.jsonl`. Model requests contain the instantiated system and user prompts. Their response bodies, settings, validation status and retry number are recorded per attempt. API keys are read from environment variables and are excluded from these records.

`configs/models.json` defines the model settings: Gemini 3 Pro representation, temperature 1.0, top-p 1.0 and 8192 output tokens; GPT-5.2 quality/items/baseline, temperature 0, top-p 1.0 and 1024/2048/1024 tokens. The OpenAI adapter sets `reasoning_effort=none` for these sampling parameters. Set `MMA_GEMINI_MODEL` to an available Gemini endpoint before inference. Each request records the selected endpoint and parameters.

## File organization

| Location | Purpose |
| --- | --- |
| `src/mma/models.py` | Gemini and OpenAI REST requests, retries, cache and request records |
| `src/mma/workflow.py` | Static module registry and complete evidence-to-grid workflow |
| `src/mma/validation.py` | JSON Schema, four-bit consistency and evidence-pointer checks |
| `src/mma/scoring.py` | Closed-world item answers and numeric score validation |
| `src/mma/weights.py` | Table 2 quality grades, location coefficients, ablation and noise |
| `src/mma/geocoding.py` | Place lookup and Google Maps geocoding |
| `src/mma/spatial.py` | WGS84/UTM projection, grid IDs and parent-grid relationships |
| `src/mma/aggregation.py` | Item/CWS aggregation, CDI, ESS and weighted bootstrap |
| `src/mma/calibration.py` | Subgroup gains, Rs intervals, eta and kappa |
| `src/mma/metrics.py` | Common-grid evaluation |
| `src/mma/io.py` | External workbook readers and field checks |
| `src/mma/reproduce.py` | Experiment replay and comparisons using external inputs |
| `prompts/` | Appendix D1–D4 system/user prompts and source hashes |
| `schemas/` | Machine-readable input and output contracts |
| `configs/` | Model, scoring, spatial, event and experiment settings |
| `tests/` | Offline code and workflow tests |
| `validation/` | Offline checks and numerical validation tools |

## Tests and checks

```sh
python -m unittest discover -s tests -v
python run.py --help
python validation/run_checks.py --out "/path/to/check_results"
```

The test suite covers an explicit 16-entry expected codebook, penalty priority, monotone down-weighting, location boundaries, missing item responses, CDI bounds, weighted bootstrap, UTM assignment, common-grid metrics, request structures, validation retries and an offline workflow. Tests construct their own fixtures and do not require research workbooks or network requests.

Optional external inputs for `validation/run_checks.py` are `--data-dir`, `--manifest` (with `--data-dir`) and `--scored-items`. Use `--skip-saved-comparison` to run workbook calculations without checking stored derived fields. Set `--out` to a directory outside the code package for the check reports.

## Input conventions

Method definitions follow Manuscript section 3.2, Table 2 and Appendix A/C/D. The prompt files are transcribed from Appendix D1–D4. `prompts/provenance.json` records their source sections and checksums.

Workbook replay starts from external post-level CWS values; item-level processing starts from explicit eight-item responses. `docs/METHODS.md` defines these two aggregation inputs and their handling of unknown values. The input workbooks must retain the machine-readable fields required by the loaders; compact presentation tables alone may omit required fields.

## Citation and metadata

The software is distributed under the [MIT License](LICENSE). `CITATION.cff` contains the software citation, and `zenodo_metadata.template.json` defines the deposit metadata. Generate a metadata file with:

```sh
python run.py zenodo-metadata --license mit --out .zenodo.json
```

Use `--doi` to include a reserved DOI. `MANIFEST.sha256` lists the code-package file hashes.

## References

- USGS DYFI Scientific Background, Appendix I: <https://earthquake.usgs.gov/data/dyfi/background.php>
- OpenAI GPT-5.2 parameter compatibility: <https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.2>
- OpenAI Chat Completions API: <https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create>
- Gemini generateContent API: <https://ai.google.dev/api/generate-content>
- Gemini 3 Pro model record: <https://ai.google.dev/gemini-api/docs/models/gemini-3-pro-preview>

See [calculation definitions](docs/METHODS.md).
