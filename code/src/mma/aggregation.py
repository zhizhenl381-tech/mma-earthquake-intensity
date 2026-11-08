"""Weighted CWS/CDI aggregation, ESS and weighted bootstrap."""
import math
import numpy as np

def round_grade(value):
    """Nearest integer, with positive half values rounded upward."""
    return int(math.floor(float(value)+0.5))

def cdi_from_cws(cws, coefficient=3.4, intercept=-4.38, lower=2.0, upper=9.0):
    if not math.isfinite(cws) or cws < 0:
        raise ValueError("CWS must be finite and nonnegative")
    if cws == 0:
        return None
    return float(np.clip(coefficient*math.log(cws)+intercept,lower,upper))

def validate_weights(weights):
    w=np.asarray(weights,dtype=float)
    if w.ndim != 1 or not len(w) or not np.all(np.isfinite(w)) or np.any(w<0) or not np.any(w>0):
        raise ValueError("Weights must be a nonempty nonnegative vector with positive sum")
    return w

def effective_sample_size(weights):
    w=validate_weights(weights)
    return float(w.sum()**2/(w@w))

def item_means(values, weights):
    """Exclude unknown item responses separately for each of the eight items."""
    q=np.asarray(values,dtype=float);w=validate_weights(weights)
    if q.shape != (len(w),8) or np.any(np.isinf(q)):
        raise ValueError("Item matrix must be n×8, with NaN for unknown")
    known=np.isfinite(q);den=(known*w[:,None]).sum(axis=0)
    return np.divide(np.nansum(q*w[:,None],axis=0),den,out=np.full(8,np.nan),where=den>0)

def item_cws(values, weights, item_weights):
    q=np.asarray(values,dtype=float)
    maxima=np.array([1,5,5,1,1,1,1,3],dtype=float)
    if q.ndim!=2 or q.shape[1]!=8:
        raise ValueError("Item matrix must be n×8, with NaN for unknown")
    if np.any(np.isfinite(q)&((q<0)|(q>maxima))):
        raise ValueError("Item score exceeds its declared range")
    means=item_means(values,weights)
    r=np.asarray(item_weights,dtype=float)
    if r.shape!=(8,) or not np.all(np.isfinite(r)) or np.any(r<=0):
        raise ValueError("Eight positive item weights are required")
    # Items with no known responses contribute zero to the available-item sum.
    return float(np.nansum(means*r)) if np.any(np.isfinite(means)) else None

def aggregate(values, weights, seed, replicates=200, mode="cws", item_weights=None):
    """Sample with p=w/sum(w), then reapply the selected post weights."""
    w=validate_weights(weights);v=np.asarray(values,dtype=float)
    if mode=="cws":
        if v.shape!=w.shape or not np.all(np.isfinite(v)) or np.any(v<0) or np.any(v>42+1e-10):
            raise ValueError("CWS vector must match weights and contain finite values in [0,42]")
        cws=float(w@v/w.sum());weighted_sum=float(w@v)
    elif mode=="items":
        if item_weights is None:raise ValueError("Item weights are required")
        cws=item_cws(v,w,item_weights);weighted_sum=None
    else:raise ValueError("mode must be cws or items")
    if not isinstance(replicates,int) or replicates<1:raise ValueError("replicates must be positive")
    ess=effective_sample_size(w);n=max(5,round_grade(ess))
    ix=np.random.default_rng(seed).choice(len(w),size=(replicates,n),p=w/w.sum())
    if mode=="cws":
        scores=(w[ix]*v[ix]).sum(axis=1)/w[ix].sum(axis=1)
        draws=np.full(replicates,np.nan);positive=scores>0
        draws[positive]=np.clip(3.4*np.log(scores[positive])-4.38,2,9)
    else:
        draws=np.array([cdi_from_cws(s) if (s:=item_cws(v[i],w[i],item_weights)) is not None else np.nan for i in ix],dtype=float)
    valid=draws[np.isfinite(draws)]
    lo,hi=map(float,np.percentile(valid,[2.5,97.5])) if len(valid) else (None,None)
    cdi=cdi_from_cws(cws) if cws is not None else None
    return dict(n_posts=len(w),sum_weights=float(w.sum()),sum_squared_weights=float(w@w),
                sum_weighted_cws=weighted_sum,mean_cws=cws,
                raw_cdi=3.4*math.log(cws)-4.38 if cws is not None and cws>0 else None,
                cdi=cdi,ess=ess,ci_low=lo,ci_high=hi,ci_width=hi-lo if lo is not None else None,
                grade=round_grade(cdi) if cdi is not None else None,
                bootstrap_seed=int(seed),resample_n=n,valid_bootstrap=len(valid))
