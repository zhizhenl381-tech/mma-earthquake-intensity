"""Closed-world DYFI answer validation and score mapping."""
import math
import numpy as np

def score_items(output, codebook):
    specs={s['item_id']:s for s in codebook['items']}
    entries=output['dyfi_items']
    ids=[x['item_id'] for x in entries]
    if len(ids)!=8 or len(set(ids))!=8 or set(ids)!=set(specs):
        raise ValueError("Each of the eight DYFI items must occur exactly once")
    result={}
    for item in entries:
        spec=specs[item['item_id']];answer=item['answer']
        if answer=='unknown':result[item['item_id']]=None;continue
        if answer not in spec['answers']:raise ValueError(f"Invalid answer for {item['item_id']}: {answer}")
        if not item.get('evidence_pointers'):raise ValueError("Known answers require evidence pointers")
        result[item['item_id']]=float(spec['answers'][answer]['score'])
    vector=[result[s['item_id']] for s in codebook['items']]
    cws=sum(s['weight']*q for s,q in zip(codebook['items'],vector) if q is not None)
    return {'post_id':output['post_id'],'item_scores':result,'item_vector':vector,
            'available_item_cws':cws if any(v is not None for v in vector) else None,
            'known_items':sum(v is not None for v in vector)}

def validate_numeric_items(values, codebook):
    if len(values)!=8:raise ValueError("Eight item scores are required")
    for v,spec in zip(values,codebook['items']):
        if v is None:continue
        allowed=[a['score'] for a in spec['answers'].values()]
        if isinstance(v,bool) or not math.isfinite(v) or not any(abs(v-a)<1e-10 for a in allowed):
            raise ValueError(f"Invalid numeric score for {spec['item_id']}")
    return np.array([np.nan if v is None else v for v in values],dtype=float)
