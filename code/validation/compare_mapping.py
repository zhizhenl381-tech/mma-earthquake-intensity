"""Compare A0 mappings using explicitly supplied external inputs and results."""
from pathlib import Path
import argparse,ast,csv,json,math,sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--legacy-weights',type=Path,required=True,help='Historical weights.py containing CODES')
    parser.add_argument('--current-grids',type=Path,required=True,help='Current ablation_grids.csv containing A0')
    parser.add_argument('--out',type=Path,required=True,help='Output JSON report')
    parser.add_argument('--extra-deps',type=Path)
    args=parser.parse_args()
    sys.dont_write_bytecode=True
    if args.extra_deps:sys.path.insert(0,str(args.extra_deps.resolve()))
    sys.path.insert(0,str(ROOT/'src'))
    from mma.io import load_final,write_json
    from mma.aggregation import cdi_from_cws
    tree=ast.parse(args.legacy_weights.read_text(encoding='utf-8'))
    legacy=next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CODES' for t in node.targets))
    if (not isinstance(legacy,(tuple,list)) or len(legacy)!=16
            or set(legacy)!={format(i,'04b') for i in range(16)}):
        parser.error('Historical CODES must contain each four-bit code exactly once')
    data=load_final(args.data_dir,verify_saved_quality=False)
    with args.current_grids.open(encoding='utf-8-sig',newline='') as stream:
        current={(int(r['scale']),r['grid_id']):float(r['cdi'])
                 for r in csv.DictReader(stream) if r['setting']=='A0'}
    old={}
    for key,posts in data['groups'].items():
        weights=[(16-legacy.index(p['code']))/16*p['loc'] for p in posts]
        cws=math.fsum(w*p['cws'] for w,p in zip(weights,posts))/math.fsum(weights)
        old[key]=cdi_from_cws(cws)
    if current.keys()!=old.keys():parser.error('Current A0 grid set differs from external input grids')
    deltas=[abs(current[k]-v) for k,v in old.items()]
    saved=[abs(old[k]-v) for k,v in data['baseline'].items() if k in old]
    report={'original_mapping_source':str(args.legacy_weights.resolve()),
            'all_model_grids_compared':len(deltas),
            'grids_changed_by_mapping':sum(v>1e-8 for v in deltas),
            'max_cdi_change_due_to_mapping':max(deltas,default=0.),
            'saved_baselines_compared':len(saved),
            'saved_baselines_inconsistent_with_original_mapping':sum(v>1e-8 for v in saved),
            'max_original_mapping_vs_saved_baseline_difference':max(saved,default=0.),
            'scope':'A0 only. Same raw codes, CWS and locations; only the quality lookup changes.'}
    write_json(args.out,report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
