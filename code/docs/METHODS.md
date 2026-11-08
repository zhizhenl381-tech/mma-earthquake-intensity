# MMA methods

## 1. Evidence processing

The workflow uses a fixed registry of processing modules. A multimodal representation module extracts text, speech, visual observations, audio events and location information. A quality module assigns four binary defect indicators. An item-extraction module selects answers from a closed candidate set. Deterministic rules map those answers to scores and aggregate the scores into grid-level intensity.

Each known answer must refer to an evidence pointer in the intermediate representation. Unsupported answers are coded as `unknown`. Schema validation checks output structure, and task-specific validation checks identifiers, candidate answers, four-bit consistency and evidence pointers. Invalid outputs follow the configured retry policy.

## 2. Quality coefficients

The defect-bit order is INRE, INRY, LOCY and INAY. A bit of one indicates a defect. Penalty priority is INAY > INRE > INRY > LOCY; bit positions are identifiers, not importance weights. The corrected ordered quality codes and coefficients are:

| Grade L | Code | Coefficient C |
| ---: | --- | ---: |
| 1 | 0000 | 1 |
| 2 | 0010 | 0.9375 |
| 3 | 0100 | 0.875 |
| 4 | 1000 | 0.8125 |
| 5 | 0110 | 0.75 |
| 6 | 1010 | 0.6875 |
| 7 | 1100 | 0.625 |
| 8 | 1110 | 0.5625 |
| 9 | 0001 | 0.5 |
| 10 | 0011 | 0.4375 |
| 11 | 0101 | 0.375 |
| 12 | 1001 | 0.3125 |
| 13 | 0111 | 0.25 |
| 14 | 1011 | 0.1875 |
| 15 | 1101 | 0.125 |
| 16 | 1111 | 0.0625 |

The coefficient is C=(17-L)/16. Codes retain all four characters, including leading zeros.

Workbooks are supplied externally. If they retain cached coefficients and results from the historical mapping, recompute with `reproduce --data-dir /path/to/input_workbooks --skip-saved-comparison` to apply the corrected mapping to the defect codes. This option skips comparisons to cached quality grades, coefficients, weights and numerical results, while retaining raw code, CWS, location, identifier and grid consistency checks. No claim of unchanged manuscript results follows from this code correction.

## 3. Geolocation and spatial assignment

For an equivalent location uncertainty radius sigma in kilometres:

- g(sigma)=1 for 0<=sigma<=0.5;
- g(sigma)=0.5 for 0.5<sigma<=5;
- g(sigma)=0.2 for sigma>5.

The baseline post weight is w_j=C_j*g(sigma_j).

Coordinates are projected from WGS84 longitude and latitude to the selected WGS84 UTM zone. For grid size s metres, lower-left coordinates are floor(E/s)*s and floor(N/s)*s. The metric origin is (0,0), and cells are half-open at their upper edges. High-precision posts enter a 1-km cell and its 10-km parent. Medium-precision posts enter the 10-km cell. Lower-precision posts retain their supplied community identifier. A 1-km cell uses the `_S1000` identifier suffix.

## 4. Closed-world item scoring

The eight item coefficients are r=[5,1,1,2,5,2,3,5], corresponding to felt, shaking, reaction, standing or walking, shelf objects, pictures, furniture and building damage. Their maximum scores are [1,5,5,1,1,1,1,3], giving a maximum complete-item CWS of 42.

The operational answer codebook defines each candidate label and numeric score. Shaking and reaction use ordered scores 0-5; standing, shelf objects, pictures and furniture use binary indices; building damage uses 0-3; felt also permits 0.33 and 0.66. The codebook is included in item-extraction prompts and response validation. Unknown answers map to null and are excluded separately for each item.

## 5. Weighted aggregation

For item i and grid A, let K_i,A contain posts with a known response. The weighted item mean is:

qbar_i,A = sum(j in K_i,A, w_j*q_i,j) / sum(j in K_i,A, w_j).

The grid score is CWS_A=sum(i, r_i*qbar_i,A). An item with no known responses has a null mean and is omitted from the available-item sum. A grid with no known responses has null CWS and CDI.

For a vector of post-level CWS values, aggregation is:

CWS_A = sum(j, w_j*CWS_j) / sum(j, w_j).

The two aggregation forms are equivalent when every item uses the same contributing posts and denominators. Item-specific denominators are required when unknown-response masks differ.

## 6. Intensity and effective sample size

For positive CWS:

CDI = max(2, min(9, 3.40*ln(CWS)-4.38)).

Zero CWS produces null CDI. Effective sample size is:

ESS = (sum(j, w_j))^2 / sum(j, w_j^2).

Weights must be finite and nonnegative, with a positive sum. CWS inputs must be finite and within [0,42].

## 7. Weighted bootstrap

Normalize post weights into sampling probabilities p_j=w_j/sum(w). For each replicate, draw n=max(5,floor(ESS+0.5)) posts with replacement. Reapply the selected post weights and repeat the aggregation and CDI conversion. Use the 2.5th and 97.5th percentiles of valid replicate CDI values as the interval limits. The default number of replicates is 200.

For deterministic experiment ordering, sort grids by descending scale and then grid identifier, and sort posts by Post_ID within a grid. The bootstrap seed is 2026102017+100000+1000*setting_index+grid_index, with zero-based indices. New-post processing derives each grid seed from the first four bytes of SHA256(`scale|grid_id`).

## 8. Ablation and quality-label noise

A0 uses C*g. A1 assigns unit weight. A2 retains only the selected defect bit, while A3 sets the selected bit to zero and retains the others. The quality grade is recomputed from the complete code table after each bit change.

A4 uses a uniform draw u in [0,1) and a selected bit number. Exactly one bit is flipped when u<p, for p=0.05, 0.10 or 0.20. Reusing the same draw and bit across rates gives nested perturbations. CWS and spatial membership remain fixed while quality weights are recalculated.

## 9. Subgroup calibration

The grouping families are shaking level, population density and dominant modality. For subgroup s:

Delta_s = MAE_A1,s - MAE_A0,s;
Delta_all = MAE_A1 - MAE_A0;
Rs = Delta_s / Delta_all.

Rs requires a nonzero global gain. Paired grid bootstrap resamples recompute subgroup and global gains on the same draw. The default uses 50 replicates and seed 2026102020.

kappa_s = clip(1+0.5*(Rs-1),0.5,1.5).
eta_s = clip(1+0.5*(Rs-1),0.8,1.4).

Combine family eta values by a weighted geometric mean and kappa values by a weighted arithmetic mean. The default family weights are each 1/3. The adjusted post weight is:

w'_j = eta_A * clip(w_j^kappa_A,0,1).

Eta is constant within a grid and cancels in normalized CWS, ESS and sampling probabilities. Kappa changes the relative weights of posts. Parameter fitting uses reference-matched 10-km grids; 1-km cells inherit their parent-grid grouping.

## 10. Evaluation

Join predictions and references by resolution and grid identifier. Evaluate only matched pairs, weighting each grid equally. Reference values above 9 are capped at 9. Integer grades use floor(CDI+0.5).

MAE is the mean absolute continuous CDI difference. RMSE is the square root of the mean squared difference. Rate>=1 and Rate>=2 are the fractions of pairs whose absolute integer-grade gaps meet the corresponding threshold. Linear weighted Cohen's kappa uses grades 2-9 and disagreement weights abs(i-j)/7, with kappa=1-observed_disagreement/expected_disagreement.
