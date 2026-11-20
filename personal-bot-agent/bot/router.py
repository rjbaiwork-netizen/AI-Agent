import json
from pathlib import Path
RULES=json.loads((Path(__file__).with_name('rules.json')).read_text(encoding='utf-8'))
def route(message):
 text=message.lower()
 for intent,words in RULES['intents'].items():
  if any(w in text for w in words):return intent
 return 'general'
