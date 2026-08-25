import re

with open("src/api/templates/index.html", "r") as f:
    html = f.read()

# I need to insert the explicit block and modify row rendering
# I'll let the user do it or I'll just explain. Wait, the user said "yes", meaning I should apply it.
