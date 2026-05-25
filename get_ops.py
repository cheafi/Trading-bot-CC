import re
text = open("src/api/templates/index.html", encoding="utf-8").read()
# Find the div section that is marked by x-show="tab==='ops'"
ops_start = text.find('x-show="tab===\'ops')
if ops_start != -1:
    # Just grab 2500 chars around it
    print(text[ops_start:ops_start+2500])
