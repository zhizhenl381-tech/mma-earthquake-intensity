"""Grid-level comparison with DYFI on common grid identifiers."""
import numpy as np
from .aggregation import round_grade

def evaluate(predicted,reference):
    pairs=[(float(v),min(9.0,float(reference[k]))) for k,v in predicted.items()
           if v is not None and k in reference and reference[k] is not None]
    if not pairs:return dict(n=0,mae=None,rmse=None,rate_ge1=None,rate_ge2=None,linear_kappa=None)
    a,b=np.array(pairs).T
    if np.any(~np.isfinite(a)) or np.any(~np.isfinite(b)) or np.any((a<2)|(a>9)|(b<2)|(b>9)):
        raise ValueError("CDI values must be finite and within [2,9]")
    ia=np.array([round_grade(v) for v in a]);ib=np.array([round_grade(v) for v in b]);gap=abs(ia-ib)
    counts=np.zeros((8,8));np.add.at(counts,(ia-2,ib-2),1);p=counts/len(a)
    weights=abs(np.arange(8)[:,None]-np.arange(8)[None,:])/7
    observed=float((p*weights).sum());expected=float((np.outer(p.sum(axis=1),p.sum(axis=0))*weights).sum())
    return dict(n=len(a),mae=float(np.mean(abs(a-b))),rmse=float(np.sqrt(np.mean((a-b)**2))),
                errors_ge1=int(sum(gap>=1)),rate_ge1=float(np.mean(gap>=1)),
                errors_ge2=int(sum(gap>=2)),rate_ge2=float(np.mean(gap>=2)),
                linear_kappa=1-observed/expected if expected>0 else None)
