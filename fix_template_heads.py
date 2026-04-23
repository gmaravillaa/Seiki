from pathlib import Path

files = [
    Path('templates/core/chat.html'),
    Path('templates/core/dashboard.html'),
]

for path in files:
    text = path.read_text(encoding='utf-8')
    if '<link rel="stylesheet" href="{% static' not in text:
        continue
    head_start = text.find('<head>')
    head_end = text.find('</head>', head_start)
    if head_start == -1 or head_end == -1:
        continue
    link_start = text.find('<link rel="stylesheet" href="{% static', head_start, head_end)
    if link_start == -1:
        continue
    link_end = text.find('>', link_start)
    if link_end == -1 or link_end >= head_end:
        continue
    if '  <link rel="stylesheet" href="{% static' in text[link_start:head_end]:
        new_head = text[:link_end+1] + '\n'
        new_head += text[head_end:]
        text = new_head
        path.write_text(text, encoding='utf-8')
        print(f'Fixed {path}')
