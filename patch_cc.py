import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

def inject_state(m):
    return m.group(1) + """
      data_sync: { market_data: { last_update: 'Never', status: 'Unknown' }, alternative_data: { last_update: 'Never', status: 'Unknown' } },
      schedule: { next_run: 'None', status: 'Idle', jobs: [] },
      system_health: { database: 'Unknown', api: 'Unknown', memory: '0MB' },
      logs: { recent: [] },
"""

text2 = re.sub(r'(function cc\(\)\{return\{)', inject_state, text, count=1)
if text != text2:
    with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
        f.write(text2)
    print("Patched successfully.")
else:
    print("Failed to patch.")
