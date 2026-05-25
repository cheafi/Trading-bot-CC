with open("src/engines/confidence_engine.py", "r") as f:
    text = f.read()

import re
text = re.sub(r'                raw = 0.35 \* cb\.thesis \+ 0.30 \* cb\.timing \+ 0\.20 \* cb\.execution \n\+ 0\.15 \* cb\.data',
              '        raw = 0.35 * cb.thesis + 0.30 * cb.timing + 0.20 * cb.execution + 0.15 * cb.data', 
              text)

with open("src/engines/confidence_engine.py", "w") as f:
    f.write(text)
