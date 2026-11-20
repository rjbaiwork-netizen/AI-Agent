from agent.tools import append_note,read_notes
def execute(intent,payload):
 if intent=='notes':return {'ok':True,'note':append_note(str(payload.get('message','')).strip())}
 if intent=='note_list':return {'ok':True,'notes':read_notes()}
 return {'ok':True,'intent':intent}
