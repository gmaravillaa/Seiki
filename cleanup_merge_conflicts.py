from pathlib import Path

paths = [Path('SEIKI/settings.py'), Path('SEIKI/views.py')]

for path in paths:
    text = path.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines(True)
    out_lines = []
    state = 'keep'
    for line in lines:
        if line.startswith('<<<<<<< HEAD'):
            state = 'head'
            continue
        if line.startswith('=======') and state == 'head':
            state = 'other'
            continue
        if line.startswith('>>>>>>>') and state == 'other':
            state = 'keep'
            continue
        if state != 'other':
            out_lines.append(line)
    path.write_text(''.join(out_lines), encoding='utf-8')
    print(f'cleaned {path}')
