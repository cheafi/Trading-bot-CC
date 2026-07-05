import re

with open("src/api/templates/index.html", "r") as f:
    html = f.read()

# I am going to replace the layout from line 1424 to 1560 with the new block.
# Since doing regex on 100+ lines of html is error prone, let's use a Python script with string replacement.
# Let's see the precise HTML snippet for the candidates loop.
