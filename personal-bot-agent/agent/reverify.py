import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; BRAIN=Path(__file__).with_name('brains'); OUT=ROOT/'data'/'brain_versions'
def verify():
 fs=sorted(BRAIN.glob('*.md'))
 if not fs:raise SystemExit('No brain files')
 m={'verified_at':datetime.now(timezone.utc).isoformat(),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in fs}}
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'latest.json').write_text(json.dumps(m,indent=2)+'\n'); print('Verified',len(fs),'brain files'); return m
if __name__=='__main__':verify()
