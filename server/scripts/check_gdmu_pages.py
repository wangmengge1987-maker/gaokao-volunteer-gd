import urllib.request, re, ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

base = 'https://zs.gdmu.edu.cn'
pages = {
    '2767': '广东省普通类',
    '2757': '联合学士学位',
    '2747': '省外',
    '2737': '订单定向医学生',
}

for pid, pname in pages.items():
    req = urllib.request.Request(base + f'/info/1017/{pid}.htm',
                                 headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=10, context=ctx)
    html = resp.read().decode('gbk', errors='replace')
    imgs = re.findall(r'<img[^>]*src=["\']([^"\']+)["\']', html)
    print(f'{pname}: {len(imgs)} images')
    for img in imgs:
        if any(x in img.lower() for x in ['.png', '.jpg', '.jpeg', '.gif', 'local', 'vsl']):
            print(f'  {img}')
    tables = re.findall(r'<table.*?</table>', html, re.DOTALL)
    if tables:
        for i, tbl in enumerate(tables):
            if '<tr' in tbl:
                cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tbl, re.DOTALL)
                texts = [re.sub(r'<[^>]+>', '', c).strip() for c in cells if c.strip()]
                texts = [t for t in texts if t and t != '&nbsp;']
                if texts:
                    print(f'  Table {i}: {len(texts)} cells, first: {texts[0][:50]}')
    print()

print('=== WeChat article ===')
url = 'https://mp.weixin.qq.com/s/tx6UMI_9LbtKw0IQntoRHQ'
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    html = resp.read().decode('utf-8', errors='replace')
    body = re.search(r'<div[^>]*class=["\']rich_media_content["\'][^>]*>(.*?)</div>', html, re.DOTALL)
    if body:
        text = re.sub(r'<[^>]+>', '\n', body.group(1))
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        print(text[:1000])
    else:
        print('No rich_media_content found')
        for m in re.finditer(r'<div[^>]*id=["\']js_content["\'][^>]*>', html):
            print(f'Found js_content')
            inner = html[m.start():m.start()+2000]
            print(inner[:500])
except Exception as e:
    import traceback
    print(f'Error: {e}')
    traceback.print_exc()
