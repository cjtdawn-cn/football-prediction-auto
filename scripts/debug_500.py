import re
with open('D:/github/football-prediction-auto/data/500_raw.html', 'rb') as f:
    raw = f.read()
html = raw.decode('gbk', errors='replace')
m = re.search(r'<tr[^>]*data-matchid="757"[^>]*>(.*?)</tr>', html, re.DOTALL)
if m:
    row = m.group(1)
    tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
    for i, td in enumerate(tds):
        clean = re.sub(r'<[^>]+>', ' ', td).strip()
        clean = re.sub(r'\s+', ' ', clean)
        print(f'  td[{i}]: {clean[:150]}')
