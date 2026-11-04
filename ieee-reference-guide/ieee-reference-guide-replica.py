"""Generate ieee-reference-guide-replica-pages.tex from the PDF of the IEEE Reference Guide.

Every line of text and every rule is placed at its original position; each example
reference is replaced by \\bibentry{<key>}, set in a box as wide as in the guide.
The keys are found by comparing the examples with the guide texts in ieee-reference-guide.tex.

Usage (requires PyMuPDF):
  python3 ieee-reference-guide-replica.py IEEE_Reference_Guide.pdf ieee-reference-guide.tex ieee-reference-guide-replica-pages.tex
"""
import re, sys, difflib
import pymupdf


def dump(path):
    pages = []
    for page in pymupdf.open(path):
        lines = []
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0: continue  # the IEEE logo
            for l in b["lines"]:
                sp = [dict(t=s["text"], f=s["font"].split('+')[-1], s=round(s["size"], 2), c=s["color"],
                           x=round(s["origin"][0], 2), y=round(s["origin"][1], 2), x1=round(s["bbox"][2], 2))
                      for s in l["spans"] if s["text"]]
                if sp: lines.append(sp)
        draws = []
        for d in page.get_drawings():
            items = []
            for it in d["items"]:
                if it[0] == 'l': items.append(['l', it[1].x, it[1].y, it[2].x, it[2].y])
                elif it[0] == 're': r = it[1]; items.append(['re', r.x0, r.y0, r.x1, r.y1])
            draws.append(dict(fill=d.get("fill"), color=d.get("color"), w=d.get("width"), type=d["type"], items=items))
        pages.append(dict(lines=lines, draws=draws))
    return pages


pages = dump(sys.argv[1])
guide_tex = open(sys.argv[2]).read()
out = open(sys.argv[3], 'w')

def norm(t):
    t = re.sub(r'\\url\{([^}]*)\}', r'\1', t)
    t = re.sub(r'\\[a-zA-Z]+', '', t)
    return re.sub(r'[^a-z0-9]', '', t.lower())

known = [(m.group(1), norm(m.group(2)))
         for m in re.finditer(r'\\guide\{([^}]*)\}\{(.*)\}\s*$', guide_tex, re.M)]

def match(text):
    n = norm(text)
    return max(((difflib.SequenceMatcher(None, n, g).ratio(), k) for k, g in known))

def esc(t):
    t = t.replace('\u200b', '').replace('\xa0', ' ').replace('\\', '\\textbackslash{}')
    for a, b in [('&', '\\&'), ('%', '\\%'), ('#', '\\#'), ('_', '\\_'), ('$', '\\$'),
                 ('{', '\\{'), ('}', '\\}'),
                 ('~', '\\textasciitilde{}'), ('^', '\\textasciicircum{}'), ('●', '\\textbullet{}')]:
        t = t.replace(a, b)
    return t

def font(f):
    fam = 'S' if f.startswith(('Arial', 'Calibri')) else 'R'
    bold = 'Bold' in f
    ital = 'Italic' in f
    return fam + ('B' if bold else '') + ('I' if ital else '')

colors = set()
def col(c):
    h = '%06X' % c
    colors.add(h)
    return 'c' + h

def text_of(line):
    return ''.join(s['t'] for s in line).replace('\u200b', '').strip()

def is_bullet(line):
    return line[0]['t'].startswith('●')

def kind(line):
    sp = [s for s in line if s['t'].replace('\u200b', '').strip() and not s['t'].startswith('●')]
    if not sp: return 'empty'
    s = sp[0]
    t = text_of(sp)
    if s['s'] >= 14: return 'heading'
    if 'Bold' in s['f'] and s['s'] >= 11: return 'heading'
    if 'Italic' in s['f'] and re.match(r'(Basic Format|Examples?)\b', t): return 'label'
    return 'text'

# Example blocks: bullet items after an "Example(s):" label, and paragraphs matching an example
def blocks_of(lines):
    blocks, cur = [], None
    for i, l in enumerate(lines):
        k = kind(l)
        y = l[0]['y']
        if k == 'empty' and not is_bullet(l):
            cur = None; continue
        if is_bullet(l):
            if cur and cur['open_bullet'] and abs(y - cur['y']) <= 3:
                pass
            cur = dict(kind='item', idx=[i], y=y, open_bullet=(text_of(l[1:]) == ''))
            blocks.append(cur); continue
        if cur and cur['open_bullet'] and abs(y - cur['y']) <= 3:
            cur['idx'].append(i); cur['open_bullet'] = False; continue
        if k == 'text' and text_of(l).startswith('NOTE:'):
            cur = dict(kind='note', idx=[i], y=y, open_bullet=False); blocks.append(cur); continue
        if k in ('heading', 'label'):
            cur = dict(kind=k, idx=[i], y=y, open_bullet=False, text=text_of(l)); blocks.append(cur); cur = None; continue
        if cur and cur['kind'] in ('item', 'para') and -3 <= y - cur['y'] <= 16:
            cur['idx'].append(i); cur['y'] = max(y, cur['y']); continue
        cur = dict(kind='para', idx=[i], y=y, open_bullet=False); blocks.append(cur)
    return blocks

out.write("% Generated from the PDF of the IEEE Reference Guide, V 3.28.2025, by ieee-reference-guide-replica.py.\n% Do not edit; regenerate instead.\n")
body = []
matched = []

# Pass 1: blocks of all pages; a page that starts with a continuation joins the last item
allb = []
for pno, page in enumerate(pages, 1):
    bs = [b for b in blocks_of(page['lines']) if not re.fullmatch(r'\d+', text_of(page['lines'][b['idx'][0]]))]
    for b in bs: b['parts'] = [(pno, b['idx'])]
    if bs and bs[0]['kind'] == 'para' and allb and allb[-1]['kind'] == 'item' \
            and page['lines'][bs[0]['idx'][0]][0]['x'] >= 90:
        allb[-1]['parts'].append((pno, bs[0]['idx'])); bs = bs[1:]
    allb.extend(bs)

def txt_lines_of(pno, idx):
    ls = [[s for s in pages[pno - 1]['lines'][i] if not s['t'].startswith('●') and s['t'].replace('​', '').strip()] for i in idx]
    return [l for l in ls if l]

# Pass 2: find the examples
areas = {}  # pno -> [(top, bottom)] of examples
replaced = {}  # (pno, line index) -> tex ('' drops the line)
in_examples = False
for b in allb:
    if b['kind'] == 'label':
        in_examples = b['text'].startswith('Example'); continue
    if b['kind'] == 'heading':
        in_examples = False; continue
    if b['kind'] == 'note': continue
    spans = [s for pno, idx in b['parts'] for i in idx for s in pages[pno - 1]['lines'][i] if not s['t'].startswith('●')]
    cut = next((j for j, s in enumerate(spans) if '***' in s['t']), len(spans))
    ref, note = spans[:cut], spans[cut:]
    if cut < len(spans) and spans[cut]['t'].split('***')[0].strip():
        head, tail = spans[cut]['t'].split('***', 1)
        ref = ref + [dict(spans[cut], t=head)]
        note = [dict(spans[cut], t='***' + tail)] + note
    text = ''.join(s['t'] for s in ref)
    if not text.strip(): continue
    r, key = max(match(text), match(''.join(s['t'] for s in spans)))
    if not (b['kind'] == 'item' and in_examples and r > 0.75 or r > 0.9): continue
    matched.append((b['parts'][0][0], key, r))
    parts = [(pno, txt_lines_of(pno, idx)) for pno, idx in b['parts']]
    all_lines = [l for _, ls in parts for l in ls]
    first = all_lines[0][0]
    left = min([first['x']] + [l[0]['x'] for l in all_lines[1:]])
    right = max([540] + [l[-1]['x1'] for l in all_lines])
    bases = sorted({round(l[0]['y']) for l in parts[0][1]})
    skip = (bases[-1] - bases[0]) / (len(bases) - 1) if len(bases) > 1 else 13.8
    notetex = ''
    if note:
        notetex = ' ' + ''.join(('\\textit{%s}' % esc(s['t'])) if 'Italic' in s['f'] else esc(s['t']) for s in note).strip()
    args = '{%.2f}{%%.2f}{%.2f}{%.2f}{%.2f}{%s}{%s}' % (left, right - left, first['x'] - left, skip, key, notetex)
    if len(parts) == 1:
        tex = ['\\gE' + args % first['y']]
    else:
        # split over two pages: the full entry on both, clipped to each page's lines
        n1 = len(bases)
        y2 = parts[1][1][0][0]['y']
        tex = ['\\gEC{0}{%.2f}' % (bases[-1] + 4) + args % first['y'],
               '\\gEC{%.2f}{792}' % (y2 - 10) + args % (y2 - n1 * skip)]
    for pno, ls in parts:
        ys = [l[0]['y'] for l in ls]
        areas.setdefault(pno, []).append((min(ys) - 10, max(ys) + 4))
    for (pno, idx), t in zip(b['parts'], tex):
        replaced[(pno, idx[0])] = t
        for i in idx[1:]: replaced[(pno, i)] = ''

for pno, page in enumerate(pages, 1):
    lines = page['lines']
    body.append('\\begin{guidepage}%% page %d' % pno)
    for d in page['draws']:
        if tuple(d['fill'] or ()) == (1.0, 1.0, 1.0) and d['type'] == 'f': continue
        for it in d['items']:
            if d['type'] in ('f', 'fs') and d['fill'] and it[0] == 're':
                body.append('\\gF{%s}{%.2f}{%.2f}{%.2f}{%.2f}' % (col(int(''.join('%02X' % round(v * 255) for v in d['fill']), 16)), *it[1:]))
            if d['type'] in ('s', 'fs') and d['color'] and not any(
                    top <= it[2] <= bottom for top, bottom in areas.get(pno, [])):
                c = col(int(''.join('%02X' % round(v * 255) for v in d['color']), 16))
                cmd = '\\gL' if it[0] == 'l' else '\\gR'
                body.append('%s{%s}{%.2f}{%.2f}{%.2f}{%.2f}{%.2f}' % (cmd, c, d['w'] or 0.75, *it[1:]))
    for i, l in enumerate(lines):
        for sp in l:
            if sp['t'].startswith('●'):
                body.append('\\gB{%.2f}{%.2f}' % (sp['x'], sp['y']))
        if (pno, i) in replaced:
            if replaced[(pno, i)]: body.append(replaced[(pno, i)])
            continue
        segs = [sp for sp in l if not sp['t'].startswith('●') and sp['t'].replace('\u200b', '')]
        while segs and not segs[0]['t'].replace('\u200b', '').strip(): segs = segs[1:]
        while segs and not segs[-1]['t'].replace('\u200b', '').strip(): segs = segs[:-1]
        if not segs: continue
        tex = ''
        for j, sp in enumerate(segs):
            prev = segs[j - 1] if j else None
            if prev and sp['x'] - prev['x1'] > 1.5 and not prev['t'].endswith(' ') and not sp['t'].startswith(' '):
                tex += '\\hspace*{%.2fbp}' % (sp['x'] - prev['x1'])  # separated by position only
            tex += '\\gS{%s}{%g}{%s}{%s}' % (font(sp['f']), sp['s'], col(sp['c']), esc(sp['t']))
        body.append('\\gT{%.2f}{%.2f}{%s}' % (segs[0]['x'], segs[0]['y'], tex))
    body.append('\\end{guidepage}')
for h in sorted(colors):
    out.write('\\definecolor{c%s}{HTML}{%s}\n' % (h, h))
out.write('\n'.join(body) + '\n')
keys = [k for _, k, _ in matched]
print('examples', len(matched), 'distinct', len(set(keys)), 'low', [m for m in matched if m[2] < 0.95], file=sys.stderr)
print('unused', sorted({k for k, _ in known} - set(keys)), file=sys.stderr)
