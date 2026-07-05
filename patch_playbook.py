with open("src/api/routers/playbook.py", "r") as f:
    text = f.read()

text = text.replace('logger.warning("Ranked playbook fallback: %s", e)', 'import traceback; traceback.print_exc(); logger.warning("Ranked playbook fallback: %s", e)')

with open("src/api/routers/playbook.py", "w") as f:
    f.write(text)
