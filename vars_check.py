import re
from bs4 import BeautifulSoup
with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

soup = BeautifulSoup(text, 'html.parser')
vars_used = set()
for el in soup.find_all(attrs={"x-text": True}):
    vars_used.add(el["x-text"])
for el in soup.find_all(attrs={"x-for": True}):
    vars_used.add(el["x-for"])
for el in soup.find_all(attrs={"x-model": True}):
    vars_used.add(el["x-model"])

print("Some vars used in x-text:")
for v in list(vars_used)[:20]:
    print(v)
