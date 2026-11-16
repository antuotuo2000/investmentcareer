#!/usr/bin/env python3
"""Precompute report metadata and search text; never ship complete reports to the homepage."""
import hashlib
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())
SKIP = {'script', 'style', 'noscript', 'svg'}


def compact(text):
    return re.sub(r'\s+', ' ', text).strip()


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return compact(' '.join(c.text() if isinstance(c, Node) else c for c in self.children))

    def walk(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()

    def lines(self):
        lines = []
        for child in self.children:
            if isinstance(child, Node):
                lines.extend(child.lines())
            elif compact(child):
                lines.append(compact(child))
        return lines


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.skipped = []

    def handle_starttag(self, tag, attrs):
        if self.skipped:
            if tag in SKIP:
                self.skipped.append(tag)
            return
        if tag in SKIP:
            self.skipped.append(tag)
            return
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.skipped:
            if tag == self.skipped[-1]:
                self.skipped.pop()
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if not self.skipped:
            self.stack[-1].children.append(data)


def summarize(path):
    stat = path.stat()
    raw = path.read_text(encoding='utf-8-sig', errors='replace')
    parser = ReportParser()
    parser.feed(raw)
    nodes = list(parser.root.walk())
    title = next((n.text() for n in nodes if n.tag == 'title'), path.stem)
    body = next((n for n in nodes if n.tag == 'body'), parser.root)
    main = next((n for n in nodes if n.tag == 'main'), body)
    aside = next((n for n in nodes if n.tag == 'aside'), None)
    headings = list(dict.fromkeys(n.text() for n in main.walk() if n.tag in {'h1','h2','h3'} and 2 < len(n.text()) < 90))
    paras = [n.text() for n in main.walk() if n.tag == 'p' and 35 <= len(n.text()) <= 280]
    thesis = paras[0] if paras else title
    ticker, exchange = path.stem.upper(), 'NASDAQ'
    match = re.search(r'\(\s*(NASDAQ|NYSE|HKEX|TYO|OTCMKTS|TSE|SSE|SZSE)\s*[:：]\s*([A-Za-z0-9._-]+)\s*\)',title,re.I)
    if match:
        exchange, ticker = match[1].upper(), match[2].upper()
    else:
        hk = re.search(r'\(\s*(\d{4,5}\.HK)\s*\)', title, re.I)
        if hk:
            exchange, ticker = 'HKEX', hk[1].upper()
    name = re.split(r'[（(]', title)[0].split('深度研究报告')[0].strip()
    chinese = ''.join(re.findall(r'[\u4e00-\u9fa5]+',name))
    english = compact(re.sub(r'[\u4e00-\u9fa5]+',' ',name))
    cn_name, en_name = (chinese, english or ticker) if chinese else (name[:18] or path.stem, name or ticker)
    kpis = []
    for node in main.walk():
        if set((node.attrs.get('class') or '').split()) & {'report-card','metric-card','kpi-card','glass-card'}:
            lines = node.lines()
            if 2 <= len(lines) <= 8 and any(re.search(r'[\$€¥\d]+',t) for t in lines[:4]):
                kpis.append(lines[:4])
                if len(kpis) == 4:
                    break
    metrics = []
    if aside:
        for node in aside.walk():
            spans = [c for c in node.children if isinstance(c,Node) and c.tag == 'span']
            if node.tag == 'div' and len(spans) == 2:
                k,v = (c.text() for c in spans)
                if k and v and len(k)<36 and len(v)<55:
                    metrics.append([k,v])
    if not metrics:
        metrics = [[k[0], k[1] + (' ('+k[2]+')' if len(k)>2 and k[2] else '')] for k in kpis]
    text = body.text()
    meta = dict(ticker=ticker,exchange=exchange,fileName=path.name,cnName=cn_name,enName=en_name,
                fileSize=stat.st_size,cleanBytes=stat.st_size,modifiedTime=datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                fullTitle=title,coreThesis=thesis,pillars=(headings+['核心财务表现与盈利能力拆解']*3)[:3],
                keywords=[ticker,cn_name],finMetrics=metrics[:3] or [['文件状态','已自动解析收录']],kpis=kpis,headings=headings[:8],
                isCustomAdded=True,hasPythonWrapper=False)
    meta['preloadVersion'] = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return dict(fileName=path.name,meta=meta,plainText=text,lastModified=stat.st_mtime*1000)


def build_snapshot():
    components = ROOT / 'docs' / 'Components'
    entries = [summarize(p) for p in sorted(components.iterdir(), key=lambda p:p.name.casefold())
               if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.html','.htm')]
    # Separate lazy documents: these are never part of the initial homepage payload.
    cache = ROOT / 'docs' / '.report-cache'
    cache.mkdir(exist_ok=True)
    for entry in entries:
        path = components / entry['fileName']
        raw = path.read_text(encoding='utf-8-sig', errors='replace')
        version = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        # Retry the build if a report was being saved while we scanned it.
        if version != entry['meta']['preloadVersion']:
            raise OSError('财报保存中，请稍后重试：' + entry['fileName'])
        data = json.dumps(dict(version=version, html=raw),ensure_ascii=False,separators=(',',':'))
        content = 'window.REPORT_PRELOAD_CACHE = window.REPORT_PRELOAD_CACHE || {};\nwindow.REPORT_PRELOAD_CACHE[' + json.dumps(entry['fileName'],ensure_ascii=False) + '] = ' + data + ';\n'
        output = cache / (entry['fileName'] + '.js')
        if not output.exists() or output.read_text(encoding='utf-8') != content:
            temp = output.with_suffix('.js.tmp')
            temp.write_text(content,encoding='utf-8')
            temp.replace(output)
    payload = json.dumps(entries,ensure_ascii=False,separators=(',',':'))
    version = hashlib.sha256(payload.encode()).hexdigest()
    content = '// Generated by build_snapshot.py. Do not edit manually.\nwindow.COMPONENT_SNAPSHOT_VERSION = '+json.dumps(version)+';\nwindow.COMPONENT_SNAPSHOT = '+payload+';\n'
    output = ROOT/'docs'/'components-snapshot.js'
    if not output.exists() or output.read_text(encoding='utf-8') != content:
        temp = output.with_suffix('.js.tmp')
        temp.write_text(content,encoding='utf-8')
        temp.replace(output)
    version_output = ROOT / 'docs' / 'components-version.js'
    version_content = 'window.COMPONENT_AVAILABLE_VERSION = ' + json.dumps(version) + ';\n'
    if not version_output.exists() or version_output.read_text(encoding='utf-8') != version_content:
        temp = version_output.with_suffix('.js.tmp')
        temp.write_text(version_content, encoding='utf-8')
        temp.replace(version_output)
    return len(entries)


if __name__ == '__main__':
    print('已更新本地首页索引：'+str(build_snapshot())+' 份财报')
