with open('src/api/templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
template_count = 0
for i, l in enumerate(lines):
    template_count += l.count('<template') - l.count('</template')

print(f"Final template count: {template_count}")
