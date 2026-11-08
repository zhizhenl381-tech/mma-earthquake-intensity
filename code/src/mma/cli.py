"""Command-line entry points for replay, model processing and item aggregation."""
from pathlib import Path
import argparse,json,sys
from .io import write_json

def package_root():
    # The source archive is the canonical distribution; installed use accepts --root.
    return Path(__file__).resolve().parents[2]

def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(prog='mma',description='MMA reproducibility tools')
    parser.add_argument('--root',type=Path,default=package_root(),help='Code folder containing configs, prompts and schemas')
    sub=parser.add_subparsers(dest='command',required=True)
    replay=sub.add_parser('reproduce',help='Recompute and verify all final-data experiments')
    replay.add_argument('--data-dir',type=Path,required=True);replay.add_argument('--out',type=Path,default=Path('results'))
    replay.add_argument('--skip-saved-comparison',action='store_true',
                        help='Recompute historical inputs without requiring agreement with saved grades, weights and results; raw input consistency checks remain enabled')
    infer=sub.add_parser('infer',help='Run multimodal evidence and structured decision modules')
    infer.add_argument('--input',type=Path,required=True);infer.add_argument('--out',type=Path,required=True)
    infer.add_argument('--models',type=Path);infer.add_argument('--event',type=Path);infer.add_argument('--baseline',action='store_true')
    demo=sub.add_parser('example',help='Aggregate an external scored-item JSON file without model calls')
    demo.add_argument('--input',type=Path,required=True)
    demo.add_argument('--out',type=Path,default=Path('example_results.json'))
    validate=sub.add_parser('verify-sources',help='Check external workbook hashes against an external manifest')
    validate.add_argument('--data-dir',type=Path,required=True)
    validate.add_argument('--manifest',type=Path,required=True)
    release=sub.add_parser('zenodo-metadata',help='Create deposit metadata using an author-selected software license')
    release.add_argument('--license',required=True,help='Zenodo software-license identifier')
    release.add_argument('--doi');release.add_argument('--out',type=Path,default=Path('.zenodo.json'))
    args=parser.parse_args(argv);root=args.root
    if args.command=='reproduce':
        from .reproduce import reproduce
        method=json.loads((root/'configs/method.json').read_text(encoding='utf-8'))
        r=reproduce(args.data_dir,args.out,
                    verify=not args.skip_saved_comparison,method=method)
        print(json.dumps(r['verification'],ensure_ascii=False,indent=2))
    elif args.command=='infer':
        from .workflow import run_pipeline
        print(json.dumps(run_pipeline(args.input,args.out,root,args.models,args.event,baseline=args.baseline),ensure_ascii=False))
    elif args.command=='example':
        from .scoring import validate_numeric_items
        from .aggregation import aggregate
        from .weights import quality,location
        data=json.loads(args.input.read_text(encoding='utf-8'))
        codebook=json.loads((root/'configs/dyfi_items.json').read_text(encoding='utf-8'))
        q=[validate_numeric_items(p['scores'],codebook) for p in data['posts']]
        w=[quality(p['evidence_code'])[1]*location(p['radius_km']) for p in data['posts']]
        r=aggregate(q,w,data['seed'],mode='items',item_weights=[i['weight'] for i in codebook['items']])
        write_json(args.out,r);print(json.dumps(r,ensure_ascii=False,indent=2))
    elif args.command=='verify-sources':
        from .io import source_manifest
        current=source_manifest(args.data_dir)
        if not current:parser.error('No source workbooks found in --data-dir')
        expected=json.loads(args.manifest.read_text(encoding='utf-8'))['files']
        if current!=expected:raise SystemExit('Source manifest mismatch')
        print(f'Verified {len(current)} source workbooks')
    elif args.command=='zenodo-metadata':
        value=json.loads((root/'zenodo_metadata.template.json').read_text(encoding='utf-8'))
        value['license']=args.license
        if args.doi:value['doi']=args.doi
        write_json(args.out,value);print(str(args.out))
