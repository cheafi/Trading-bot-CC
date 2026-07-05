with open('src/api/templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

ops_start = text.find("tab==='ops'")
end = text.find("tab==='catalog'")
sub = text[ops_start:end]

lines = sub.split('\n')
div_count = 0
for i, l in enumerate(lines):
    div_count += l.count('<div') - l.count('</div')
    print(f"{i}: {div_count} | {l.strip()}")
