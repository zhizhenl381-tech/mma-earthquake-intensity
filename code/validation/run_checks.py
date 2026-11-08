"""Offline code checks, with optional explicitly supplied external data."""
from pathlib import Path
import argparse,hashlib,importlib.metadata,io,json,os,platform,subprocess,sys,unittest

ROOT=Path(__file__).resolve().parents[1]


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True,help='Directory for newly generated check records')
    parser.add_argument('--data-dir',type=Path,help='Optional external workbook directory for replay')
    parser.add_argument('--manifest',type=Path,help='Optional external manifest, requires --data-dir')
    parser.add_argument('--scored-items',type=Path,help='Optional external scored-item JSON file')
    parser.add_argument('--skip-saved-comparison',action='store_true')
    parser.add_argument('--extra-deps',type=Path)
    args=parser.parse_args()
    if args.manifest and not args.data_dir:parser.error('--manifest requires --data-dir')
    if args.data_dir and not args.data_dir.is_dir():parser.error('--data-dir must be an existing directory')
    out=args.out.resolve()
    if out==ROOT or ROOT in out.parents:parser.error('--out must be outside the code package')
    if args.data_dir:
        source=args.data_dir.resolve()
        if out==source or source in out.parents:parser.error('--out must be outside the input directory')
    sys.dont_write_bytecode=True
    env=os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONIOENCODING']='utf-8'
    if args.extra_deps:
        sys.path.insert(0,str(args.extra_deps.resolve()))
        env['PYTHONPATH']=str(args.extra_deps.resolve())+os.pathsep+env.get('PYTHONPATH','')
    out.mkdir(parents=True,exist_ok=True)
    inputs_before=hashes(args.data_dir) if args.data_dir else None
    versions={}
    for name in ['numpy','openpyxl','httpx','jsonschema','pyproj']:
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    write_json(out/'environment.json',{'python':sys.version,'executable':sys.executable,
               'platform':platform.platform(),'dependencies':versions,'model_tests':'offline fixtures'})
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'unit_tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    summary={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
             'successful':result.wasSuccessful()}
    write_json(out/'unit_tests_summary.json',summary)
    if not result.wasSuccessful():
        print(stream.getvalue());raise SystemExit('Unit tests failed')

    def run(name,arguments):
        process=subprocess.run([sys.executable,'-B',str(ROOT/'run.py'),*arguments],cwd=ROOT,
                               env=env,capture_output=True,text=True,encoding='utf-8')
        (out/name).write_text(process.stdout+process.stderr,encoding='utf-8')
        if process.returncode:
            print(process.stdout+process.stderr);raise SystemExit(name+' failed')

    run('cli_help.txt',['--help'])
    if args.scored_items:
        run('item_aggregation.txt',['example','--input',str(args.scored_items.resolve()),
                                    '--out',str(out/'item_aggregation.json')])
    if args.data_dir:
        if args.manifest:
            run('source_checks.txt',['verify-sources','--data-dir',str(args.data_dir.resolve()),
                                     '--manifest',str(args.manifest.resolve())])
        arguments=['reproduce','--data-dir',str(args.data_dir.resolve()),'--out',str(out/'recomputed')]
        if args.skip_saved_comparison:arguments.append('--skip-saved-comparison')
        run('data_replay.txt',arguments)
        if inputs_before!=hashes(args.data_dir):raise SystemExit('External input files changed')
    summary.update({'external_replay_run':bool(args.data_dir),
                    'source_manifest_checked':bool(args.manifest),
                    'external_item_aggregation_run':bool(args.scored_items)})
    write_json(out/'package_checks.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
