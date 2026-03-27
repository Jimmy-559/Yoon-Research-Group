#!/usr/bin/env python3
"""
update_publications.py  —  Pure RSS → publications.html
기능: Altmetric 배지 / Open Access 배지 / 공동제1저자 † / 연도별 논문 수
"""

import re, sys, requests
from bs4 import BeautifulSoup
from collections import defaultdict

RSS_URL = (
    "https://pure.uos.ac.kr/en/persons/jinhwan-yoon/publications/"
    "?format=rss&pageSize=500"
)
PUBLICATIONS_HTML = "publications.html"
START_MARKER = "<!-- PUB_AUTO_START -->"
END_MARKER   = "<!-- PUB_AUTO_END -->"
ALTMETRIC_SCRIPT = (
    '<script type="text/javascript" '
    'src="https://d1bxh8uas1mnw7.cloudfront.net/assets/embed.js"></script>'
)

# ── 1. RSS 파싱 ───────────────────────────────────────────────────────────────

def fetch_rss(url):
    print(f"Fetching: {url}")
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "lxml-xml")
    items = soup.find_all("item")
    print(f"  {len(items)} items")
    return [p for p in (parse_item(i) for i in items) if p]


def parse_item(item):
    title_tag = item.find("title")
    if not title_tag:
        return None

    title = title_tag.get_text(strip=True)
    link  = item.find("link").get_text(strip=True) if item.find("link") else ""

    year = ""
    pd = item.find("pubDate")
    if pd:
        m = re.search(r"\b(20\d\d|19\d\d)\b", pd.get_text())
        if m: year = m.group(1)

    authors = journal = volume = pages = article_num = doi = ""
    is_oa = False
    co_first_authors = set()

    desc_tag = item.find("description")
    if desc_tag:
        ds = BeautifulSoup(desc_tag.get_text(), "html.parser")

        # Open Access
        if ds.find(class_=re.compile(r"open.?access", re.I)):
            is_oa = True

        # 저자 파싱: 공동제1저자 †
        # Pure는 공동제1저자 이름 앞 텍스트에 † 를 넣음
        person_tags = ds.find_all("a", rel="Person")
        names = []
        for i, p in enumerate(person_tags):
            name = p.get_text(strip=True)
            # 직전 텍스트에 † 포함 여부 확인
            prev_sib = p.previous_sibling
            prev_text = str(prev_sib) if prev_sib else ""
            is_dagger = ("†" in prev_text or "&#8224;" in prev_text or
                         (i == 0 and "†" in ds.get_text()[:200]))
            dagger = "†" if is_dagger else ""
            star   = "*" if re.search(r"Yoon", name) else ""
            names.append(f"{name}{star}{dagger}")
        authors = ", ".join(names) if names else ""

        # Journal
        j = ds.find("a", rel="Journal") or ds.find("span", class_="link journal")
        if j: journal = j.get_text(strip=True)

        # Volume / pages / article number
        v  = ds.find("span", class_="volume")
        pg = ds.find("span", class_="pages")
        an = ds.find("span", class_="articlenumber")
        if v:  volume      = v.get_text(strip=True)
        if pg: pages       = pg.get_text(strip=True)
        if an: article_num = an.get_text(strip=True)

        # DOI
        for a in ds.find_all("a", href=True):
            if "doi.org" in a["href"]:
                doi = a["href"]; break

    return dict(title=title, link=link, year=year or "0000",
                authors=authors, journal=journal, volume=volume,
                pages=pages, article_num=article_num, doi=doi, is_oa=is_oa)


# ── 2. HTML 생성 ──────────────────────────────────────────────────────────────

def doi_id(doi_url):
    m = re.search(r"(10\.\S+)", doi_url)
    return m.group(1) if m else ""


def format_item(pub, number):
    ref = ", ".join(filter(None, [pub["volume"],
                                   pub["article_num"] or pub["pages"]]))
    ref_str = (ref + ".") if ref else "."

    link_html = ""
    if pub["doi"]:
        link_html = f' <a href="{pub["doi"]}" class="pub-link" target="_blank">link</a>'
    elif pub["link"]:
        link_html = f' <a href="{pub["link"]}" class="pub-link" target="_blank">link</a>'

    oa_badge = (' <span class="pub-tag pub-oa">Open Access</span>'
                if pub["is_oa"] else "")

    altmetric = ""
    if pub["doi"]:
        did = doi_id(pub["doi"])
        if did:
            altmetric = (
                f' <span class="altmetric-wrap">'
                f'<div data-badge-type="donut" data-doi="{did}" '
                f'data-badge-popover="left" data-hide-no-mentions="true" '
                f'class="altmetric-embed"></div></span>'
            )

    return (
        f'      <li class="pub-item">'
        f'<span class="pub-num">[{number}]</span> '
        f'{pub["authors"] or "—"}, &ldquo;{pub["title"]},&rdquo; '
        f'<span class="pub-journal">{pub["journal"]}</span> '
        f'{pub["year"]}, {ref_str}'
        f'{link_html}{oa_badge}{altmetric}</li>'
    )


def build_section(pubs):
    by_year = defaultdict(list)
    for p in pubs: by_year[p["year"]].append(p)

    counter = len(pubs)
    lines   = []
    for year in sorted(by_year.keys(), reverse=True):
        lines += [
            f'  <div class="pub-year-block">',
            f'    <div class="pub-year-hdr">{year}</div>',
            f'    <ul class="pub-list">',
        ]
        for pub in by_year[year]:
            lines.append(format_item(pub, counter))
            counter -= 1
        lines += [f'    </ul>', f'  </div>', ""]
    return "\n".join(lines)


# ── 3. publications.html 업데이트 ────────────────────────────────────────────

def update_html(pubs, path):
    content = open(path, encoding="utf-8").read()
    if START_MARKER not in content or END_MARKER not in content:
        print("ERROR: markers not found"); sys.exit(1)

    updated = re.sub(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        START_MARKER + "\n" + build_section(pubs) + END_MARKER,
        content, flags=re.DOTALL,
    )

    # Altmetric 스크립트 삽입 (없을 때만)
    if "embed.js" not in updated:
        updated = updated.replace("</body>", ALTMETRIC_SCRIPT + "\n</body>")

    open(path, "w", encoding="utf-8").write(updated)
    print(f"Written {len(pubs)} pubs to {path}")


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pubs = fetch_rss(RSS_URL)
    if not pubs: sys.exit("No pubs fetched")
    update_html(pubs, PUBLICATIONS_HTML)
    print("Done.")
