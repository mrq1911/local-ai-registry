import datetime, hashlib, json, pathlib, sys, time
sys.path.insert(0,'/mnt/nvme/muse-glimmer')
import lab
out=pathlib.Path('/mnt/nvme/muse-glimmer/evidence')
original=lab.call
counter=0
raw=(out/'gates-http.jsonl').open('w',buffering=1)
def traced(endpoint,path,body=None,**kwargs):
 global counter
 counter+=1
 print('request',counter,path,flush=True)
 result,elapsed=original(endpoint,path,body,**kwargs)
 raw.write(json.dumps({'path':path,'request':body,'response':result,'seconds':elapsed})+'\n')
 print('completed',counter,'seconds',round(elapsed,2),flush=True)
 return result,elapsed
lab.call=traced
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
passed,proof,evidence=lab.gates('http://127.0.0.1:8080',{'ctx':262144})
result={'started_at':start,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':passed,'proof':proof,'evidence':evidence,'engine_commit':'d81235049384534c167caea52b85a694f6103d14','gpu':'NVIDIA GeForce RTX 3090','context':262144}
raw.close()
result['http_log_sha256']=hashlib.sha256((out/'gates-http.jsonl').read_bytes()).hexdigest()
(out/'gates-summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
