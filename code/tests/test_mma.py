"""Numerical, spatial, schema and workflow regression tests."""
from pathlib import Path
import json,math,sys,tempfile,unittest
import numpy as np
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mma.weights import CODES,quality,location,altered_code,post_weight,PENALTY_PRIORITY
from mma.aggregation import aggregate,effective_sample_size,item_means,round_grade
from mma.metrics import evaluate
from mma.spatial import grid_id,grid_center,parent_grid,eligible_scales
from mma.scoring import score_items,validate_numeric_items
from mma.models import ModelClient,ModelCallError,make_request
from mma.validation import validate_output,check_input_metadata
from mma.workflow import render_prompt,run_pipeline,select_post

class NumericalTests(unittest.TestCase):
    def test_corrected_quality_codebook(self):
        # Fixed expectations independent of the ordering in the implementation.
        expected={'0000':1,'0010':15/16,'0100':14/16,'1000':13/16,
                  '0110':12/16,'1010':11/16,'1100':10/16,'1110':9/16,
                  '0001':8/16,'0011':7/16,'0101':6/16,'1001':5/16,
                  '0111':4/16,'1011':3/16,'1101':2/16,'1111':1/16}
        self.assertEqual(set(CODES),set(expected))
        for code,coefficient in expected.items():
            self.assertEqual(quality(code)[1],coefficient,code)
        self.assertEqual(PENALTY_PRIORITY,('INAY','INRE','INRY','LOCY'))
        self.assertLess(quality('0001')[1],quality('1000')[1])
        self.assertLess(quality('1000')[1],quality('0100')[1])
        self.assertLess(quality('0100')[1],quality('0010')[1])

    def test_adding_a_defect_never_increases_weight(self):
        for code in CODES:
            for bit in range(4):
                if code[bit]=='0':
                    changed=code[:bit]+'1'+code[bit+1:]
                    self.assertLess(quality(changed)[1],quality(code)[1],(code,changed))
        self.assertEqual(post_weight('1000',.5),13/32)
        self.assertEqual(post_weight('0010',.5),15/32)

    def test_all_quality_grades(self):
        for i,c in enumerate(CODES,1):self.assertEqual(quality(c),(i,(17-i)/16))
        for c in ('100','01000','0020',1000):
            with self.assertRaises(ValueError):quality(c)

    def test_location_boundaries(self):
        self.assertEqual([location(r) for r in [0,.5,.500001,5,5.000001]],[1,1,.5,.5,.2])
        for r in [-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):location(r)

    def test_ablation_and_noise(self):
        self.assertEqual(altered_code('1101','A2_INRY'),'0100')
        self.assertEqual(altered_code('1101','A3_INAY'),'1100')
        self.assertEqual(altered_code('0100','A4_05',.04,3),'0110')
        self.assertEqual(altered_code('0100','A4_05',.05,3),'0100')
        self.assertEqual(post_weight('1111',.2,'A1'),1)

    def test_cws_ess_and_eta(self):
        a=aggregate([10.,20.],[.5,.25],14)
        self.assertAlmostEqual(a['mean_cws'],40/3)
        self.assertAlmostEqual(a['ess'],1.8)
        self.assertAlmostEqual(a['cdi'],3.4*math.log(40/3)-4.38)
        b=aggregate([10.,20.],[.9,.45],14)
        for k in ['mean_cws','ess','cdi','ci_low','ci_high']:self.assertAlmostEqual(a[k],b[k])

    def test_unknown_denominators(self):
        q=np.array([[1,np.nan,0,0,0,0,0,0],[np.nan,5,1,1,1,1,1,3]])
        means=item_means(q,[1,3]);self.assertEqual(means[0],1);self.assertEqual(means[1],5)
        self.assertEqual(means[2],.75)
        r=aggregate(np.full((2,8),np.nan),[1,1],3,mode='items',item_weights=[5,1,1,2,5,2,3,5])
        self.assertIsNone(r['cdi']);self.assertIsNone(r['ci_low'])
        self.assertEqual(r['valid_bootstrap'],0)

    def test_bootstrap_seed_and_singleton(self):
        a=aggregate([8,25,40],[1,.5,.25],2026);b=aggregate([8,25,40],[1,.5,.25],2026)
        self.assertEqual(a,b)
        c=aggregate([17],[.03125],6);self.assertEqual(c['ess'],1);self.assertEqual(c['ci_width'],0)

    def test_bootstrap_weighted_draws(self):
        w=np.array([1,.5,.125]);v=np.array([8,21,40]);seed=102
        ess=w.sum()**2/(w@w);n=max(5,math.floor(ess+.5))
        ix=np.random.default_rng(seed).choice(3,(200,n),p=w/w.sum())
        draws=[min(9,max(2,3.4*math.log(sum(w[j]*v[j] for j in row)/sum(w[j] for j in row))-4.38)) for row in ix]
        lo,hi=np.percentile(draws,[2.5,97.5]);actual=aggregate(v,w,seed)
        self.assertAlmostEqual(actual['ci_low'],lo);self.assertAlmostEqual(actual['ci_high'],hi)

    def test_clipping_zero_and_rounding(self):
        with self.assertRaises(ValueError):aggregate([100],[1],1)
        self.assertEqual(aggregate([1],[1],1)['cdi'],2)
        self.assertIsNone(aggregate([0],[1],1)['cdi'])
        self.assertEqual(round_grade(4.5),5)
        with self.assertRaises(ValueError):aggregate([1],[0],1)

    def test_metrics_common_grids(self):
        r=evaluate({'a':4.5,'b':4.1,'c':9},{'a':4.4,'b':4.2,'outside':7})
        self.assertEqual(r['n'],2);self.assertAlmostEqual(r['mae'],.1)
        self.assertEqual(r['rate_ge1'],.5)
        perfect=evaluate({'a':2,'b':9},{'a':2,'b':9});self.assertEqual(perfect['linear_kappa'],1)

class SpatialTests(unittest.TestCase):
    def test_center_roundtrip(self):
        for key in ['46N_E470000_N2280000','47N_E330000_N2410000_S1000','55S_E320000_N5800000']:
            center=grid_center(key);size=1000 if key.endswith('S1000') else 10000
            zone=int(key.split('N_')[0]) if 'N_' in key else 55
            self.assertEqual(grid_id(**center,size_m=size,zone=zone),key)
        self.assertEqual(parent_grid('46N_E473000_N2285000_S1000'),'46N_E470000_N2280000')

    def test_radius_membership(self):
        self.assertEqual(eligible_scales(.5),(1,10));self.assertEqual(eligible_scales(5),(10,));self.assertEqual(eligible_scales(6),())

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        # Minimal synthetic responses keep offline tests independent of research data.
        self.evidence={'post_id':'EXAMPLE_001',
                       'text':{'original_or_translated_text':'Test shaking and shelf observations.',
                               'earthquake_related_terms':[{'evidence_pointer':'text_span:4-27'},
                                                           {'evidence_pointer':'text_span:41-64'}]},
                       'asr':[],'ocr':[],'image_captions':[],'video_captions':[],'audio_events':[],
                       'location_evidence':{'place_names':[],'explicit_coordinates':None,
                                            'location_uncertainty_description':'Synthetic test'},
                       'time_evidence':{'posting_time':'2000-01-01T00:00:00Z',
                                        'event_time_reference_in_post':None},'uncertainties':[]}
        self.codebook=json.loads((ROOT/'configs/dyfi_items.json').read_text(encoding='utf-8'))
        self.labels={'post_id':'EXAMPLE_001','quality_labels':dict(INRE=0,INRY=0,LOCY=0,INAY=0,four_bit_vector='0000'),
                     'evidence_pointers':{d:[] for d in ['INRE','INRY','LOCY','INAY']},'rationale':{d:'Evidence reviewed' for d in ['INRE','INRY','LOCY','INAY']}}
        self.items={'post_id':'EXAMPLE_001','dyfi_items':[{'item_id':s['item_id'],'item_name':s['name'],'answer':'unknown',
                      'evidence_pointers':[],'rationale':'No direct item evidence'} for s in self.codebook['items']],
                    'quality_flags_for_item_extraction':{'insufficient_evidence_items':[],'ambiguous_evidence_items':[]}}
        self.items['dyfi_items'][0].update(answer='felt',evidence_pointers=['text_span:4-27'])
        self.items['dyfi_items'][4].update(answer='yes',evidence_pointers=['text_span:41-64'])
        self.baseline={'estimate_type':'LLM_CDI_baseline','post_or_grid_id':'EXAMPLE_001','estimated_cdi':5,
                       'confidence':'medium','evidence_pointers':['text_span:4-27'],'rationale':'Shaking evidence'}

    def test_prompt_substitution(self):
        self.assertEqual(render_prompt('{"id":"{POST_ID}"}',{'POST_ID':'p'}),'{"id":"p"}')
        # Placeholder-like text in evidence is preserved, not substituted again.
        self.assertEqual(render_prompt('{EVIDENCE_JSON}',{'EVIDENCE_JSON':'{POST_ID}','POST_ID':'p'}),'{POST_ID}')

    def test_quality_and_pointer_validation(self):
        validate_output('quality',self.labels,ROOT,'EXAMPLE_001',self.evidence,self.codebook)
        self.labels['quality_labels']['four_bit_vector']='1000'
        with self.assertRaises(ValueError):validate_output('quality',self.labels,ROOT,'EXAMPLE_001',self.evidence,self.codebook)
        self.items['dyfi_items'][0]['evidence_pointers']=['nonexistent_frame']
        with self.assertRaises(ValueError):validate_output('items',self.items,ROOT,'EXAMPLE_001',self.evidence,self.codebook)

    def test_scoring_and_duplicate_items(self):
        scored=score_items(self.items,self.codebook);self.assertEqual(scored['available_item_cws'],10)
        self.assertEqual(scored['known_items'],2)
        self.items['dyfi_items'][-1]=self.items['dyfi_items'][0]
        with self.assertRaises(ValueError):score_items(self.items,self.codebook)
        with self.assertRaises(ValueError):validate_numeric_items([1,8,0,0,0,0,0,0],self.codebook)

    def test_request_contracts(self):
        configs=json.loads((ROOT/'configs/models.json').read_text(encoding='utf-8'))
        url,payload=make_request(configs['quality'],'system','user')
        self.assertTrue(url.endswith('/chat/completions'));self.assertEqual(payload['reasoning_effort'],'none')
        self.assertEqual(payload['temperature'],0);self.assertEqual(payload['max_completion_tokens'],1024)
        _,g=make_request(configs['representation'],'system','user',[{'inline_data':{'mime_type':'image/png','data':'AA=='}}])
        self.assertEqual(g['contents'][0]['parts'][1]['inline_data']['data'],'AA==')

    def test_retry_limit_and_log(self):
        config=json.loads((ROOT/'configs/models.json').read_text(encoding='utf-8'))['quality'];config['retry_delay_scale']=0
        with tempfile.TemporaryDirectory() as d:
            attempts=[]
            def transport(*args):attempts.append(1);return {'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}
            client=ModelClient(d,transport)
            with self.assertRaises(ModelCallError):client.call('quality',config,'sys','user',lambda v:validate_output('quality',v,ROOT,'p'))
            self.assertEqual(len(attempts),3)
            records=[json.loads(x) for x in (Path(d)/'calls.jsonl').read_text().splitlines()]
            self.assertEqual(records[-1]['status'],'failed');self.assertNotIn('Authorization',str(records))

    def test_pipeline_and_cache(self):
        seen=[]
        fixtures=iter([self.evidence,self.labels,self.items,self.baseline])
        def transport(cfg,url,payload):
            seen.append(payload);result=next(fixtures)
            if cfg['provider']=='gemini':return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(result)}]}}]}
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]}
        with tempfile.TemporaryDirectory() as d:
            client=ModelClient(Path(d)/'calls',transport)
            input_path=Path(d)/'test_posts.jsonl'
            post={'post_id':'EXAMPLE_001','post_time':'2000-01-01T00:00:00Z',
                  'text':'Synthetic workflow test.','metadata':{},'media':[],
                  'geolocation':{'longitude':0.,'latitude':0.,'radius_km':.3}}
            input_path.write_text(json.dumps(post)+'\n',encoding='utf-8')
            r=run_pipeline(input_path,Path(d)/'out',ROOT,client=client,baseline=True)
            self.assertEqual(r,{'posts':1,'grids':2});self.assertEqual(len(seen),4)
            run_pipeline(input_path,Path(d)/'out2',ROOT,client=client,baseline=True)
            self.assertEqual(len(seen),4)

    def test_time_window_filter(self):
        event={'start_time':'2025-03-28T15:00:00+06:30','end_time':'2025-03-28T16:00:00+06:30'}
        self.assertTrue(select_post({'post_time':'2025-03-28T15:30:00+06:30'},event))
        self.assertFalse(select_post({'post_time':'2025-03-28T16:01:00+06:30'},event))

    def test_reference_metadata_separation(self):
        check_input_metadata({'platform':'public_post','location':{'place':'Mandalay'}})
        with self.assertRaises(ValueError):check_input_metadata({'event':{'DYFI_CDI':6}})

class ReplayCommandTests(unittest.TestCase):
    def test_historical_recompute_requires_explicit_option(self):
        from mma.cli import main
        with tempfile.TemporaryDirectory() as out:
            with patch('mma.reproduce.reproduce',return_value={'verification':{}}) as replay:
                main(['reproduce','--data-dir',out,'--skip-saved-comparison','--out',out])
                self.assertFalse(replay.call_args.kwargs['verify'])

    def test_default_replay_keeps_strict_comparison(self):
        from mma.cli import main
        with tempfile.TemporaryDirectory() as out:
            with patch('mma.reproduce.reproduce',return_value={'verification':{}}) as replay:
                main(['reproduce','--data-dir',out,'--out',out])
                self.assertTrue(replay.call_args.kwargs['verify'])

if __name__=='__main__':unittest.main()
