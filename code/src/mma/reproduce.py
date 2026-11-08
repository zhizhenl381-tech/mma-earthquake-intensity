"""Recompute released final-data experiments and compare each saved result."""
from pathlib import Path
import math
from .aggregation import aggregate,round_grade
from .calibration import fit_factors,combine_factors
from .io import load_final,source_manifest,require_close,write_csv,write_json,numeric
from .metrics import evaluate
from .weights import SCENARIOS,post_weight,altered_code,PENALTY_PRIORITY,QUALITY_MAPPING

def reproduce(source_dir,output_dir,verify=True,method=None):
    data=load_final(source_dir,verify_saved_quality=verify);grids=data['grids'];groups=data['groups']
    cfg=method or {};seed=cfg.get('seed',2026102017);replicates=cfg.get('bootstrap_replicates',200)
    ordered=sorted(groups,key=lambda k:(-k[0],k[1]));results={};factors=None;weight_checks=[]
    print(f'Loaded {len(data["posts"])} scale-specific post records and {len(ordered)} model grids',flush=True)
    for setting in SCENARIOS:
        if setting=='C_FULLFIT':
            factors=fit_factors(grids,results,seed=seed+3,replicates=cfg.get('rs_bootstrap_replicates',50),**cfg.get('calibration',{}))
        for j,key in enumerate(ordered):
            pp=groups[key];g=grids[key]
            eta,kappa=combine_factors(g,factors,cfg.get('family_weights',(1/3,1/3,1/3))) if factors else (1.,1.)
            weights=[post_weight(p['code'],p['loc'],setting,p['noise_u'],p['noise_bit'],eta,kappa) for p in pp]
            r=aggregate([p['cws'] for p in pp],weights,seed+100000+SCENARIOS.index(setting)*1000+j,replicates)
            r.update(scale=key[0],grid_id=key[1],parent=g['parent'],setting=setting,
                     ref_cdi=g['ref'],eta=eta if setting=='C_FULLFIT' else None,
                     kappa=kappa if setting=='C_FULLFIT' else None,
                     shaking=g['shaking'],population=g['population'],modality=g['modality'])
            if g['ref'] is not None:
                gap=abs(r['grade']-round_grade(g['ref']))
                r.update(absolute_error=abs(r['cdi']-g['ref']),integer_gap=gap,error_ge1=int(gap>=1),error_ge2=int(gap>=2),reference_grade=round_grade(g['ref']))
            else:r.update(absolute_error=None,integer_gap=None,error_ge1=None,error_ge2=None,reference_grade=None)
            if setting.startswith('A4') or setting=='C_FULLFIT':
                a0=results[*key,'A0'];r.update(a0_cdi=a0['cdi'],delta_cdi=r['cdi']-a0['cdi'],
                  delta_absolute_error=r['absolute_error']-a0['absolute_error'] if g['ref'] is not None else None)
            if setting.startswith('A4'):
                probability={'A4_05':.05,'A4_10':.1,'A4_20':.2}[setting]
                count=sum(p['noise_u']<probability for p in pp)
                r.update(noise_probability=probability,flipped_posts=count,flip_rate=count/len(pp),high_low_sample=g['high_low_sample'])
            if setting=='C_FULLFIT':
                r.update(rs_shaking=factors[g['shaking']]['rs'],rs_population=factors[g['population']]['rs'],rs_modality=factors[g['modality']]['rs'])
            results[*key,setting]=r
        print(f'Computed {setting}',flush=True)
    checks={'saved_result_comparison':'requested' if verify else 'skipped_for_historical_snapshots',
            'raw_input_consistency':'passed','quality_mapping':QUALITY_MAPPING}
    maximum=0.;checked=0
    aliases={'权重合计':'sum_weights','权重平方合计':'sum_squared_weights','加权CWS合计':'sum_weighted_cws',
             '平均CWS':'mean_cws','截断前CDI':'raw_cdi','CDI':'cdi','ESS':'ess',
             'CI下限':'ci_low','CI下限_快照':'ci_low','CI上限':'ci_high','CI上限_快照':'ci_high',
             'CI宽度':'ci_width','CI宽度_快照':'ci_width','Bootstrap种子':'bootstrap_seed','每次抽样数':'resample_n',
             '综合η':'eta','综合κ':'kappa','绝对误差':'absolute_error','整数等级':'grade','参照整数等级':'reference_grade',
             '名义噪声概率':'noise_probability','翻转帖数':'flipped_posts','翻转比例':'flip_rate',
             'A0_CDI':'a0_cdi','校准前CDI':'a0_cdi','CDI相对A0变化':'delta_cdi','CDI变化':'delta_cdi',
             '绝对误差相对A0变化':'delta_absolute_error','强弱组Rs':'rs_shaking','人口组Rs':'rs_population','Rs':'rs_modality'}
    if verify:
        for row in data['expected']:
            key=int(row['尺度_km']),row['UTM_Grid_ID'],row['实验设置'];r=results[key]
            for source,target in aliases.items():
                if source in row and numeric(row[source]):
                    require_close(row[source],r[target],f'{key} {source}',1e-8)
                    maximum=max(maximum,abs(row[source]-r[target]));checked+=1
        for k,target in data['baseline'].items():require_close(results[*k,'A0']['cdi'],target,f'{k} baseline')
        for p,expected in zip(data['posts'],data['weight_expected']):
            g=grids[p['scale'],p['grid']];eta,kappa=combine_factors(g,factors,cfg.get('family_weights',(1/3,1/3,1/3)))
            for setting in SCENARIOS:
                field='w_校准_分组' if setting=='C_FULLFIT' else 'w_'+setting
                actual=post_weight(p['code'],p['loc'],setting,p['noise_u'],p['noise_bit'],eta,kappa)
                require_close(actual,expected[field],f'{p["post_id"]} {field}',1e-10)
                if setting.startswith(('A2','A3','A4')):
                    changed=altered_code(p['code'],setting,p['noise_u'],p['noise_bit'])
                    code_field={'A4_05':'噪声5%编码','A4_10':'噪声10%编码','A4_20':'噪声20%编码'}.get(setting,setting+'编码')
                    if str(expected[code_field]).zfill(4)!=changed:raise ValueError(f'Altered code mismatch: {code_field}')
        for row in data['factor_expected']:
            f=factors[row['分组']]
            for source,target in [('Rs','rs'),('η','eta'),('κ','kappa'),('Rs区间下限_快照','ci_low'),('Rs区间上限_快照','ci_high')]:
                require_close(row[source],f[target],f'{row["分组"]} {source}')
        checks.update(verified_grid_records=len(data['expected']),verified_numeric_cells=checked,
                      max_saved_cell_difference=maximum,baseline_grid_values=len(data['baseline']),
                      verified_post_weights=len(data['posts'])*len(SCENARIOS),verified_factors=len(factors))
        checks['saved_result_comparison']='passed'
    baseline_differences=[abs(results[*key,'A0']['cdi']-value)
                          for key,value in data['baseline'].items() if (*key,'A0') in results]
    checks['comparison_to_saved_A0']={
        'compared_grids':len(baseline_differences),
        'changed_grids':sum(delta>1e-8 for delta in baseline_differences),
        'max_absolute_cdi_change':max(baseline_differences,default=0.)}
    summaries=[]
    for scale in (10,1):
        refs={key[1]:g['ref'] for key,g in grids.items() if key[0]==scale and g['ref'] is not None}
        for setting in SCENARIOS:
            pred={key[1]:r['cdi'] for key,r in results.items() if key[0]==scale and key[2]==setting}
            summaries.append(dict(scale_km=scale,setting=setting,model_grids=len(pred),**evaluate(pred,refs)))
    out=Path(output_dir);records=list(results.values())
    for name,selected in [('ablation',[r for r in records if r['setting'].startswith(('A0','A1','A2','A3'))]),
                          ('noise',[r for r in records if r['setting'].startswith('A4')]),
                          ('calibration',[r for r in records if r['setting']=='C_FULLFIT'])]:
        write_csv(out/(name+'_grids.csv'),selected)
    write_csv(out/'metrics.csv',summaries);write_json(out/'calibration_factors.json',list(factors.values()))
    report=dict(verification=checks,source_manifest=source_manifest(source_dir),
                quality_mapping=QUALITY_MAPPING,penalty_priority=list(PENALTY_PRIORITY),
                saved_result_comparison_enabled=verify,
                total_grid_records=len(records),post_records=len(data['posts']),
                bootstrap_replicates=len(records)*replicates,metrics=summaries)
    write_json(out/'verification.json',report)
    return report
