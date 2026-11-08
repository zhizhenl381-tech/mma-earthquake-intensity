"""Gemini generateContent and OpenAI Chat Completions adapters."""
from pathlib import Path
from datetime import datetime,timezone
import base64,hashlib,json,os,time

class ModelCallError(RuntimeError):
    pass

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def make_request(config,system,user,media=()):
    if config['provider']=='openai':
        if media:raise ValueError('OpenAI decision modules accept the structured evidence representation')
        if config.get('reasoning_effort')!='none' and ('temperature' in config or 'top_p' in config):
            raise ValueError('GPT-5.2 sampling parameters require reasoning_effort=none')
        payload={'model':config['model'],'messages':[{'role':'system','content':system},{'role':'user','content':user}],
                 'temperature':config['temperature'],'top_p':config['top_p'],
                 'max_completion_tokens':config['max_tokens'],'reasoning_effort':config['reasoning_effort'],
                 'response_format':{'type':'json_object'}}
        return config['base_url'].rstrip('/')+'/chat/completions',payload
    if config['provider']=='gemini':
        parts=[{'text':user}]
        for item in media:
            if 'inline_data' in item:parts.append({'inline_data':item['inline_data']})
            elif 'file_data' in item:parts.append({'file_data':item['file_data']})
            else:raise ValueError('Media must supply inline_data or file_data')
        payload={'system_instruction':{'parts':[{'text':system}]},'contents':[{'role':'user','parts':parts}],
                 'generationConfig':{'temperature':config['temperature'],'topP':config['top_p'],
                                     'maxOutputTokens':config['max_tokens'],'responseMimeType':'application/json'}}
        return config['base_url'].rstrip('/')+'/models/'+config['model']+':generateContent',payload
    raise ValueError('provider must be openai or gemini')

def response_text(config,response):
    if config['provider']=='openai':
        choice=response['choices'][0]
        if choice.get('finish_reason')!='stop':raise ModelCallError('OpenAI completion did not finish normally')
        if choice['message'].get('refusal'):raise ModelCallError('OpenAI completion was refused')
        return choice['message']['content']
    candidate=response['candidates'][0]
    if candidate.get('finishReason')!='STOP':raise ModelCallError('Gemini completion did not finish normally')
    return ''.join(p.get('text','') for p in candidate['content']['parts'] if not p.get('thought'))

def local_media(items,base_dir):
    result=[]
    for item in items:
        if 'path' in item:
            p=(Path(base_dir)/item['path']).resolve();raw=p.read_bytes()
            result.append({'inline_data':{'mime_type':item['mime_type'],'data':base64.b64encode(raw).decode()}})
        elif 'file_uri' in item:
            result.append({'file_data':{'mime_type':item['mime_type'],'file_uri':item['file_uri']}})
        else:raise ValueError('Media requires a local path or Gemini file_uri')
    return result

class ModelClient:
    def __init__(self,run_dir,transport=None):
        self.run_dir=Path(run_dir);self.run_dir.mkdir(parents=True,exist_ok=True)
        self.transport=transport

    def _send(self,config,url,payload):
        if self.transport is not None:return self.transport(config,url,payload)
        import httpx
        key=os.environ.get(config['api_key_env'])
        if not key:raise ModelCallError(f"Set {config['api_key_env']}")
        headers={'Content-Type':'application/json'}
        headers['Authorization' if config['provider']=='openai' else 'x-goog-api-key']=('Bearer '+key if config['provider']=='openai' else key)
        with httpx.Client(timeout=config.get('timeout_seconds',180)) as client:
            response=client.post(url,json=payload,headers=headers)
            if response.status_code>=400:raise ModelCallError(f'Provider HTTP {response.status_code}')
            return response.json()

    def call(self,module,config,system,user,validator,media=()):
        config=dict(config)
        if config.get('model_env') and os.environ.get(config['model_env']):
            config['model']=os.environ[config['model_env']]
        url,payload=make_request(config,system,user,media)
        key=digest({'module':module,'url':url,'request':payload});cache=self.run_dir/(key+'.json')
        if cache.exists():return validator(json.loads(cache.read_text(encoding='utf-8')))
        last=None
        for attempt in range(config['retry_limit']+1):
            record={'module':module,'cache_key':key,'attempt':attempt+1,
                    'time_utc':datetime.now(timezone.utc).isoformat(),'url':url,'request':payload}
            try:
                response=self._send(config,url,payload);record['response']=response
                result=validator(json.loads(response_text(config,response)))
                record['status']='accepted'
                cache.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
                return result
            except (KeyError,IndexError,TypeError,ValueError,ModelCallError) as exc:
                record.update(status='retry' if attempt<config['retry_limit'] else 'failed',error=str(exc));last=exc
            except Exception as exc:
                # Connection and schema failures use the same finite retry policy.
                record.update(status='retry' if attempt<config['retry_limit'] else 'failed',error=type(exc).__name__);last=exc
            finally:
                with (self.run_dir/'calls.jsonl').open('a',encoding='utf-8') as log:
                    log.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
            if attempt<config['retry_limit']:time.sleep(min(2**attempt,8)*config.get('retry_delay_scale',1))
        raise ModelCallError(f'{module} failed after {config["retry_limit"]+1} attempts') from last
