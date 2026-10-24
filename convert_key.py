# convert_key.py
import json

with open('credentials/service-account-key.json', 'r') as f:
    data = json.load(f)
    
# Convert to single line string
single_line = json.dumps(data, separators=(',', ':'))

print("Copy this into Railway as GS_CREDENTIALS_JSON:")
print(single_line)