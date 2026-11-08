"""Readers for the released final-data workbooks and JSON/CSV results."""
from pathlib import Path
from collections import defaultdict
import csv,hashlib,json,math
import openpyxl
from .weights import quality
from .spatial import parent_grid

def read_table(path):
    w=openpyxl.load_workbook(path,read_only=True,data_only=True)
    try:
        it=w.worksheets[0].iter_rows(values_only=True);headers=next(it)
        return [(i,dict(zip(headers,r))) for i,r in enumerate(it,2) if any(v is not None and v!='' for v in r)]
    finally:w.close()

def numeric(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

def require_close(a,b,label,tol=1e-8):
    if not numeric(a) or not numeric(b) or abs(a-b)>tol:
        raise ValueError(f"{label}: {a!r} != {b!r}")

def write_json(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def write_csv(path,records):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    if not records:return
    keys=list(dict.fromkeys(k for r in records for k in r))
    with p.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(records)

def load_final(source_dir,verify_saved_quality=True):
    """Load raw inputs; optionally compare cached grade/coefficient fields.

    Cached quality fields in the supplied workbooks use the historical mapping.
    Disabling that comparison does not disable code, CWS, location, ID or grid
    consistency checks. All new weights are computed from the defect codes.
    """
    src=Path(source_dir)
    p10={row:r for row,r in read_table(src/'Agent10km帖子计算.xlsx') if r.get('Post_ID')}
    if len({r['Post_ID'] for r in p10.values()})!=len(p10):
        raise ValueError('Duplicate 10km Post_ID')
    posts=[];weight_expected=[];seen=set()
    for row,r in read_table(src/'帖子与权重.xlsx'):
        if r.get('尺度_km') not in (1,10) or not r.get('UTM_Grid_ID'):continue
        scale=int(r['尺度_km']);original=p10[int(r['源工作表行号'])]
        code=str(r['Evidence_Code']).zfill(4);grade,q=quality(code)
        if verify_saved_quality:
            require_close(r['Quality_Score'],q,
                          'Saved Quality_Score differs from the active mapping; '
                          'use --skip-saved-comparison to recompute historical inputs')
            if grade!=r['质量等级']:
                raise ValueError('Saved quality grade differs from the active mapping')
        if str(original['Evidence_Code']).zfill(4)!=code:
            raise ValueError('Source quality code mismatch')
        post=dict(scale=scale,grid=r['UTM_Grid_ID'],parent=r['10km父格'],
                  post_id=original['Post_ID'],code=code,cws=float(r['CWS_固定']),
                  loc=float(r['定位系数']),radius=r.get('源定位半径_km'),
                  noise_u=float(r['固定噪声u']),noise_bit=int(r['翻转位号1至4']),
                  source_row=int(r['源工作表行号']),mode=r.get('帖子模态'),source_file=r['源文件'])
        if not math.isfinite(post['cws']) or not 0<=post['cws']<=42+1e-10:
            raise ValueError('Post CWS must be finite and in [0,42]')
        require_close(original['帖子CWS'],post['cws'],'Shared post CWS across scales')
        key=scale,post['post_id']
        if key in seen:raise ValueError(f'Duplicate post key: {key}')
        seen.add(key)
        if scale==10:
            if original['UTM_Grid_ID']!=post['grid']:raise ValueError('10km grid mismatch')
            require_close(original['帖子CWS'],post['cws'],'10km CWS')
            require_close(original['定位权重'],post['loc'],'10km location weight')
        elif parent_grid(post['grid'])!=post['parent']:raise ValueError('1km parent mismatch')
        posts.append(post);weight_expected.append(r)
    # The compact 1km file lacks IDs; match its numerical records as a multiset.
    compact=[r for _,r in read_table(src/'1kmAgent帖子数据整理.xlsx') if r.get('1km_Grid_ID')]
    combined=sorted([p for p in posts if p['scale']==1],key=lambda p:(p['grid'],p['code'],p['cws']))
    compact.sort(key=lambda r:(r['1km_Grid_ID'],str(r['Evidence_Code']).zfill(4),r['CWS_条目计算']))
    if len(compact)!=len(combined):raise ValueError('1km source count mismatch')
    for a,b in zip(compact,combined):
        if a['1km_Grid_ID']!=b['grid'] or str(a['Evidence_Code']).zfill(4)!=b['code']:
            raise ValueError('1km source record mismatch')
        require_close(a['CWS_条目计算'],b['cws'],'1km CWS')
        require_close(a['1km定位系数'],b['loc'],'1km location coefficient')
    grids={}
    for row,r in read_table(src/'网格与分组.xlsx'):
        if r.get('尺度_km') not in (1,10) or not r.get('UTM_Grid_ID'):continue
        key=int(r['尺度_km']),r['UTM_Grid_ID']
        if key in grids:raise ValueError(f'Duplicate grid: {key}')
        grids[key]=dict(scale=key[0],grid=key[1],parent=r['10km父格_ID'],model=bool(r['模型纳入']),
                        n=int(r['帖子数']) if numeric(r.get('帖子数')) else 0,
                        ref=min(9.,float(r['原DYFI_CDI'])) if numeric(r.get('原DYFI_CDI')) else None,
                        source_cdi=r.get('源Agent_CDI') if numeric(r.get('源Agent_CDI')) else None,
                        llm=r.get('源LLM_CDI') if numeric(r.get('源LLM_CDI')) else None,
                        shaking=r.get('强弱震区'),population=r.get('人口分组'),modality=r.get('主导模态'),
                        grouping_type=r.get('分组说明'),longitude=r.get('分组父格中心经度'),latitude=r.get('分组父格中心纬度'),
                        population_density=r.get('人口密度_人每km2'),high_low_sample=r.get('高低样本分组'))
    groups=defaultdict(list)
    for p in posts:groups[p['scale'],p['grid']].append(p)
    for key,pp in groups.items():
        if key not in grids or not grids[key]['model'] or grids[key]['n']!=len(pp):
            raise ValueError(f'Grid/post count mismatch: {key}')
        pp.sort(key=lambda p:p['post_id'])
    expected=[]
    for filename in ('消融逐网格.xlsx','噪声实验逐网格.xlsx'):
        expected.extend(r for _,r in read_table(src/filename) if r.get('尺度_km') in (1,10) and r.get('UTM_Grid_ID'))
    a0=[r for r in expected if r['实验设置']=='A0']
    calibration=[r for _,r in read_table(src/'校准实验.xlsx') if r.get('尺度_km') in (1,10)]
    if len(calibration)!=len(a0):raise ValueError('Calibration table length differs from A0')
    for r,a in zip(calibration,a0):
        if r['尺度_km']!=a['尺度_km'] or r['10km父格']!=a['10km父格'] or r['固定帖子数']!=a['固定帖子数']:
            raise ValueError('Calibration/A0 row alignment mismatch')
        r['UTM_Grid_ID']=a['UTM_Grid_ID'];expected.append(r)
    factors=[r for _,r in read_table(src/'校准因子.xlsx') if r.get('分组类别') in ('shaking','population','modality')]
    baseline={}
    for scale,filename,field in [(10,'10kmAgent数据整理.xlsx','CDI'),(1,'1kmAgent网格数据整理.xlsx','AgentCDI')]:
        baseline.update({(scale,r['UTM_Grid_ID']):r[field] for _,r in read_table(src/filename) if r.get('UTM_Grid_ID') and numeric(r.get(field))})
    for scale,filename,field in [(10,'USGS_CDI10km网格数据整理.xlsx','USGS_CDI'),(1,'1kmDYFI.xlsx','DYFI参照CDI')]:
        refs={(scale,r['UTM_Grid_ID']):min(9.,float(r[field])) for _,r in read_table(src/filename) if r.get('UTM_Grid_ID') and numeric(r.get(field))}
        metadata_refs={key:g['ref'] for key,g in grids.items() if key[0]==scale and g['ref'] is not None}
        if refs.keys()!=metadata_refs.keys():raise ValueError(f'{scale}km reference grid set mismatch')
        for key,value in refs.items():require_close(value,metadata_refs[key],f'{key} DYFI reference')
    for scale,filename,field in [(10,'LLM10km网格数据整理.xlsx','LLM_CDI'),(1,'1kmLLM网格.xlsx','LLMCDI')]:
        for _,r in read_table(src/filename):
            if r.get('UTM_Grid_ID') and numeric(r.get(field)):
                key=scale,r['UTM_Grid_ID']
                if key in grids and grids[key]['llm'] is not None:require_close(r[field],grids[key]['llm'],f'{key} LLM source')
    return dict(posts=posts,groups=groups,grids=grids,expected=expected,
                weight_expected=weight_expected,factor_expected=factors,baseline=baseline)

def source_manifest(source_dir):
    return [{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
            for p in sorted(Path(source_dir).glob('*.xlsx')) if not p.name.startswith('~')]
