import json,shutil
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; NOTES=DATA/'notes.json'
def read_notes():
 try:
  v=json.loads(NOTES.read_text(encoding='utf-8')); return v if isinstance(v,list) else []
 except (OSError,json.JSONDecodeError):return []
def append_note(text):
 item={'text':text[:2000],'created_at':datetime.now(timezone.utc).isoformat()}; notes=read_notes(); notes.append(item); NOTES.parent.mkdir(parents=True,exist_ok=True); NOTES.write_text(json.dumps(notes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return item
def backup_data():
 dest=DATA/'backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); dest.mkdir(parents=True,exist_ok=True)
 if NOTES.exists():shutil.copy2(NOTES,dest/'notes.json')
 return str(dest.relative_to(ROOT))
