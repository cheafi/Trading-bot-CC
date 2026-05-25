with open('src/api/templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
div_count = 0
for i, l in enumerate(lines):
    div_count += l.count('<div') - l.count('</div')

print(f"Final div count: {div_count}")
