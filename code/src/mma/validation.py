"""JSON Schema checks and cross-field evidence validation."""
import json
import re
from pathlib import Path
from .scoring import score_items
from .weights import DIMENSIONS

def pointer_set(value):
    found=set()
    if isinstance(value,dict):
        for k,v in value.items():
            if k=='evidence_pointer' and isinstance(v,str):found.add(v)
            elif k=='evidence_pointers' and isinstance(v,list):found.update(x for x in v if isinstance(x,str))
            else:found.update(pointer_set(v))
    elif isinstance(value,list):
        for v in value:found.update(pointer_set(v))
    return found

def validate_output(module,value,root,post_id,evidence=None,codebook=None):
    import jsonschema
    schema=json.loads((Path(root)/'schemas'/f'{module}.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator(schema).validate(value)
    if module!='baseline' and value['post_id']!=post_id:raise ValueError('Response post_id mismatch')
    if module=='baseline' and value['post_or_grid_id']!=post_id:raise ValueError('Baseline ID mismatch')
    if module=='quality':
        labels=value['quality_labels'];code=''.join(str(labels[d]) for d in DIMENSIONS)
        if labels['four_bit_vector']!=code:raise ValueError('Quality vector and individual labels disagree')
    if module=='items':score_items(value,codebook)
    if evidence is not None and module in ('quality','items','baseline'):
        allowed=pointer_set(evidence)
        if not pointer_set(value)<=allowed:
            raise ValueError('Response cites an evidence pointer absent from the input')
    return value

def check_input_metadata(value):
    """Keep reference products in the evaluation input, outside model evidence."""
    forbidden={'dyfi','dyfi_cdi','usgs_cdi','reference_cdi','ref_cdi','shakemap','pga','pgv','magnitude'}
    if isinstance(value,dict):
        for k,v in value.items():
            if str(k).casefold() in forbidden:raise ValueError(f'Reference field in model metadata: {k}')
            check_input_metadata(v)
    elif isinstance(value,list):
        for v in value:check_input_metadata(v)
