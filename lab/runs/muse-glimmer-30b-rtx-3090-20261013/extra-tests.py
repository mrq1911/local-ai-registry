import base64, hashlib, json, struct, time, urllib.request, zlib
from pathlib import Path
endpoint='http://127.0.0.1:8080'
out=Path('/mnt/nvme/muse-glimmer/evidence'); out.mkdir(exist_ok=True)
def call(body,name):
 request=urllib.request.Request(endpoint+'/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 start=time.monotonic()
 with urllib.request.urlopen(request,timeout=900) as r: result=json.load(r)
 record={'request':body,'response':result,'seconds':time.monotonic()-start}
 (out/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
 print(name,json.dumps({'message':result['choices'][0]['message'],'usage':result.get('usage'),'timings':result.get('timings'),'seconds':record['seconds']}),flush=True)
 return record
with urllib.request.urlopen(endpoint+'/v1/models') as r: model=json.load(r)['data'][0]['id']
def chunk(tag,data):return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
w=h=256
pixels=b''.join(b'\0'+b''.join(bytes((255,0,0) if 64<=x<192 and 64<=y<192 else (255,255,255)) for x in range(w)) for y in range(h))
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')
vision=call({'model':model,'messages':[{'role':'user','content':[{'type':'text','text':'What color and shape is in the center of this image? Answer briefly.'},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(png).decode()}}]}],'max_tokens':512,'temperature':0},'vision')
answer=vision['response']['choices'][0]['message'].get('content','').lower()
summary={'vision':{'passed':'red' in answer and 'square' in answer,'answer':answer},'benchmarks':[]}
for i in range(3):
 r=call({'model':model,'messages':[{'role':'user','content':f'Experiment {i+1}: Write a detailed 1000-word explanation of how computers evolved from mechanical calculators to modern processors.'}],'max_tokens':512,'temperature':1.0,'top_p':0.95,'top_k':64,'cache_prompt':False},f'benchmark-{i+1}')
 summary['benchmarks'].append({'usage':r['response'].get('usage'),'timings':r['response'].get('timings'),'seconds':r['seconds']})
(out/'extra-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
