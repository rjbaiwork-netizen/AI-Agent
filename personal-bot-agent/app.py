from pathlib import Path
from flask import Flask,jsonify,request,send_from_directory
from agent.tools import append_note,read_notes
from bot.router import route
from agent.planner import make_plan
ROOT=Path(__file__).resolve().parent
app=Flask(__name__,static_folder='ui',static_url_path='')
@app.get('/')
def home(): return send_from_directory(ROOT/'ui','index.html')
@app.get('/api/health')
def health(): return jsonify(ok=True)
@app.get('/api/notes')
def notes(): return jsonify(notes=read_notes())
@app.post('/api/notes')
def add_note():
 d=request.get_json(silent=True) or {}; t=str(d.get('text','')).strip()
 if not t:return jsonify(error='Text required'),400
 return jsonify(note=append_note(t))
@app.post('/api/chat')
def chat():
 d=request.get_json(silent=True) or {}; m=str(d.get('message','')).strip()
 if not m or len(m)>8000:return jsonify(error='Message must contain 1-8000 characters'),400
 i=route(m); return jsonify(reply='\\n'.join(make_plan(m)) if i=='planning' else f'Intent: {i}. Local starter agent; no model provider configured.')
if __name__=='__main__': (ROOT/'logs').mkdir(exist_ok=True); app.run(host='127.0.0.1',port=5000,debug=False)
