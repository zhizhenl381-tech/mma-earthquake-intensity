"""Static MMA workflow: evidence → quality/items → deterministic grid estimates."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import hashlib,json,re
from .models import ModelClient,local_media
from .validation import validate_output,check_input_metadata
from .scoring import score_items
from .weights import quality,location
from .spatial import assign_location
from .aggregation import aggregate
from .io import write_json,write_csv

REGISTRY={'representation':{'prompt':'representation','schema':'representation'},
          'quality':{'prompt':'quality','schema':'quality'},
          'items':{'prompt':'items','schema':'items'},
          'baseline':{'prompt':'baseline','schema':'baseline'}}

def render_prompt(template,fields):
    """Replace named placeholders in one pass; leave JSON braces intact."""
    names=set(re.findall(r'\{([A-Z][A-Z0-9_]*)\}',template))
    missing=names-fields.keys()
    if missing:raise ValueError(f'Missing prompt fields: {sorted(missing)}')
    return re.sub(r'\{([A-Z][A-Z0-9_]*)\}',lambda m:str(fields[m.group(1)]),template)

def load_json(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def select_post(post,event):
    if post.get('preliminary_include') is False:return False
    if not event.get('start_time') and not event.get('end_time'):return True
    t=datetime.fromisoformat(post['post_time'].replace('Z','+00:00'))
    if t.tzinfo is None:raise ValueError('Post timestamps must include a UTC offset')
    for field,op in [('start_time',lambda a,b:a<b),('end_time',lambda a,b:a>b)]:
        if event.get(field):
            edge=datetime.fromisoformat(event[field].replace('Z','+00:00'))
            if edge.tzinfo is None:raise ValueError('Event timestamps must include a UTC offset')
            if op(t,edge):return False
    return True

def run_pipeline(input_path,output_dir,root,model_config=None,event_config=None,client=None,baseline=False):
    root=Path(root);out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    models=load_json(model_config or root/'configs/models.json')
    event=load_json(event_config or root/'configs/event.json')
    codebook=load_json(root/'configs/dyfi_items.json');client=client or ModelClient(out/'model_calls')
    raw=[json.loads(line) for line in Path(input_path).read_text(encoding='utf-8').splitlines() if line.strip()]
    import jsonschema
    raw_schema=load_json(root/'schemas/raw_post.schema.json')
    ids=set();results=[];groups=defaultdict(list);filtered=[]
    for post in raw:
        jsonschema.Draft202012Validator(raw_schema,format_checker=jsonschema.FormatChecker()).validate(post)
        check_input_metadata(post.get('metadata',{}))
        pid=post['post_id']
        if pid in ids:raise ValueError(f'Duplicate Post_ID: {pid}')
        ids.add(pid)
        if not select_post(post,event):filtered.append(pid);continue
        fields={'POST_ID':pid,'POST_TIME':post['post_time'],
                'METADATA':json.dumps(post.get('metadata',{}),ensure_ascii=False),'POST_TEXT':post.get('text',''),
                'VISUAL_INPUTS':json.dumps([m.get('id',m.get('path',m.get('file_uri'))) for m in post.get('media',[]) if m['mime_type'].startswith(('image/','video/'))]),
                'AUDIO_INPUTS':json.dumps([m.get('id',m.get('path',m.get('file_uri'))) for m in post.get('media',[]) if m['mime_type'].startswith(('audio/','video/'))]),
                'OCR_INPUT':json.dumps(post.get('ocr',[]),ensure_ascii=False),'ASR_INPUT':json.dumps(post.get('asr',[]),ensure_ascii=False),
                'TARGET_EVENT_REGION':event['region'],'TARGET_EVENT_TIME_WINDOW':event['time_window'],
                'DYFI_ITEM_SCHEMA':json.dumps(codebook,ensure_ascii=False)}
        def invoke(module,evidence=None):
            stage=REGISTRY[module];base=root/'prompts'
            system=(base/(stage['prompt']+'.system.txt')).read_text(encoding='utf-8')
            template=(base/(stage['prompt']+'.user.txt')).read_text(encoding='utf-8')
            user=render_prompt(template,fields)
            validator=lambda v:validate_output(stage['schema'],v,root,pid,evidence,codebook)
            media=local_media(post.get('media',[]),Path(input_path).parent) if module=='representation' else []
            return client.call(module,models[module],system,user,validator,media)
        evidence=invoke('representation')
        fields['EVIDENCE_JSON']=json.dumps(evidence,ensure_ascii=False)
        labels=invoke('quality',evidence);items=invoke('items',evidence);scores=score_items(items,codebook)
        code=labels['quality_labels']['four_bit_vector'];grade,q=quality(code)
        assignments=assign_location(post.get('geolocation'))
        record=dict(post_id=pid,evidence=evidence,quality=labels,items=items,scores=scores,assignments=assignments)
        if baseline:
            fields['EVIDENCE_JSON_OR_GRID_SUMMARY']=fields['EVIDENCE_JSON'];fields['ID']=pid
            record['baseline']=invoke('baseline',evidence)
        for a in assignments:
            groups[a['scale_km'],a['grid_id']].append((pid,scores['item_vector'],q*location(a['radius_km'])))
        results.append(record)
    grid_results=[]
    for (scale,key),pp in sorted(groups.items(),key=lambda x:(str(x[0][0]),x[0][1])):
        pp.sort(key=lambda x:x[0]);seed=int.from_bytes(hashlib.sha256(f'{scale}|{key}'.encode()).digest()[:4],'big')
        r=aggregate([p[1] for p in pp],[p[2] for p in pp],seed,mode='items',item_weights=[s['weight'] for s in codebook['items']])
        r.update(scale_km=scale,grid_id=key,aggregation_mode='items');grid_results.append(r)
    write_json(out/'post_outputs.json',results);write_csv(out/'grid_results.csv',grid_results)
    write_json(out/'run_manifest.json',{'input_sha256':hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
               'model_config':models,'event':event,'accepted_posts':len(results),'filtered_posts':filtered,
               'prompt_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'prompts').glob('*.txt')}})
    return dict(posts=len(results),grids=len(grid_results))
