"""Subgroup gains, paired bootstrap, and two-channel weight modulation."""
import math
import numpy as np

FAMILIES={'shaking':('Strong-shaking','Weak-shaking'),
          'population':('High-population-density','Low-population-density'),
          'modality':('Visual-dominant','Text-dominant','Balanced')}

def fit_factors(grids,results,seed=2026102020,replicates=50,kappa_min=.5,
                kappa_max=1.5,gamma=.5,eta_min=.8,eta_max=1.4,a=1.,b=.5):
    keys=sorted([key for key,g in grids.items() if key[0]==10 and g['model'] and g['ref'] is not None],key=lambda k:k[1])
    if not keys:raise ValueError('No 10km common grids for calibration')
    e0=np.array([abs(results[*k,'A0']['cdi']-grids[k]['ref']) for k in keys])
    e1=np.array([abs(results[*k,'A1']['cdi']-grids[k]['ref']) for k in keys]);gain=e1-e0
    global_gain=float(gain.mean())
    if abs(global_gain)<1e-12:raise ValueError('Global quality-weighting gain is zero')
    draws=np.random.default_rng(seed).integers(0,len(keys),size=(replicates,len(keys)))
    factors={}
    for family,labels in FAMILIES.items():
        for label in labels:
            mask=np.array([grids[k][family]==label for k in keys])
            if not mask.any():raise ValueError(f'Calibration group has no reference grids: {label}')
            rs=float(gain[mask].mean()/global_gain);dist=[]
            for ix in draws:
                selected=mask[ix];den=float(gain[ix].mean())
                dist.append(float(gain[ix][selected].mean()/den) if selected.any() and abs(den)>1e-12 else None)
            valid=[x for x in dist if x is not None]
            lo,hi=map(float,np.percentile(valid,[2.5,97.5])) if valid else (None,None)
            factors[label]=dict(group=label,family=family,n=int(mask.sum()),mae_a0=float(e0[mask].mean()),
                                mae_a1=float(e1[mask].mean()),subgroup_gain=float(gain[mask].mean()),
                                global_gain=global_gain,rs=rs,eta=float(np.clip(a+b*(rs-1),eta_min,eta_max)),
                                kappa=float(np.clip(1+gamma*(rs-1),kappa_min,kappa_max)),
                                ci_low=lo,ci_high=hi,bootstrap_values=dist,valid_bootstrap=len(valid))
    return factors

def combine_factors(grid,factors,family_weights=(1/3,1/3,1/3)):
    if len(family_weights)!=3 or min(family_weights)<0 or abs(sum(family_weights)-1)>1e-12:
        raise ValueError('Three nonnegative family weights summing to one are required')
    selected=[factors[grid[family]] for family in FAMILIES]
    return (math.exp(sum(w*math.log(f['eta']) for w,f in zip(family_weights,selected))),
            sum(w*f['kappa'] for w,f in zip(family_weights,selected)))
