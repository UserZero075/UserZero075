"""Build a self-hosted profile card from public GitHub data (stdlib only)."""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen


USERNAME = "UserZero075"
ROOT = Path(__file__).resolve().parents[1]
COLORS = ("#202636", "#164e63", "#0e7490", "#22a6b3", "#67e8f9")


def fetch(url):
    headers = {"User-Agent": f"{USERNAME}-profile-activity"}
    token = os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return response.read().decode("utf-8")


class CalendarParser(HTMLParser):
    """Read dated calendar cells and their accessible contribution tooltips."""

    def __init__(self):
        super().__init__()
        self.cells = {}
        self.counts = {}
        self.target = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-date" in attrs and "data-level" in attrs:
            self.cells[attrs["id"]] = (
                date.fromisoformat(attrs["data-date"]),
                int(attrs["data-level"]),
            )
        if tag == "tool-tip":
            self.target = attrs.get("for")
            self.text = []

    def handle_data(self, data):
        if self.target:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.target:
            text = "".join(self.text).strip()
            match = re.match(r"([\d,]+) contributions?\b", text)
            if match:
                self.counts[self.target] = int(match[1].replace(",", ""))
            elif text.startswith("No contributions"):
                self.counts[self.target] = 0
            self.target = None

    def days(self):
        if len(self.cells) < 350 or self.cells.keys() - self.counts.keys():
            raise ValueError("GitHub calendar is incomplete; keeping the existing card.")
        days = sorted(
            (day, level, self.counts[cell])
            for cell, (day, level) in self.cells.items()
        )
        if any(not 0 <= level <= 4 for _, level, _ in days):
            raise ValueError("Unexpected contribution intensity.")
        return days


def text(x, y, content, size=13, color="#94a3b8", extra=""):
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" {extra}>'
        f"{escape(str(content))}</text>"
    )


def render(days, repos):
    total = sum(count for _, _, count in days)
    active = sum(count > 0 for _, _, count in days)
    own = [repo for repo in repos if not repo["fork"]]
    stars = sum(repo["stargazers_count"] for repo in own)
    languages = Counter(repo["language"] for repo in own if repo["language"])
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="410" '
        'viewBox="0 0 1000 410" role="img" aria-labelledby="title desc">',
        '<title id="title">Actividad de UserZero075 en GitHub</title>',
        f'<desc id="desc">{total} contribuciones visibles, {active} días activos, '
        f'{len(repos)} repositorios públicos y {stars} estrellas en repositorios propios. '
        f'Actualizado: {updated}.</desc>',
        '<rect x="1" y="1" width="998" height="408" rx="16" fill="#0d1117" stroke="#303047"/>',
        '<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">',
        text(34, 35, "ACTIVIDAD / GITHUB", 13, "#67e8f9", 'letter-spacing="2"'),
        text(966, 35, "Últimos 12 meses", extra='text-anchor="end"'),
    ]
    metrics = [(total, "Contribuciones visibles"), (active, "Días activos"),
               (len(repos), "Repositorios públicos"), (stars, "Estrellas · repos propios")]
    for index, (value, label) in enumerate(metrics):
        x = 34 + index * 237
        parts.append(f'<rect x="{x}" y="56" width="221" height="81" rx="10" fill="#161b27"/>')
        parts.append(text(x + 16, 93, f"{value:,}".replace(",", "."), 29, "#f0f6fc", 'font-weight="700"'))
        parts.append(text(x + 16, 117, label, 12))

    start = days[0][0]
    start -= timedelta(days=(start.weekday() + 1) % 7)
    last_month = None
    months = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    for day, level, count in days:
        week, weekday = divmod((day - start).days, 7)
        x, y = 69 + week * 16, 179 + weekday * 16
        if day.month != last_month:
            if day.day <= 7:
                parts.append(text(x, 165, months[day.month - 1], 11))
            last_month = day.month
        parts.append(
            f'<rect x="{x}" y="{y}" width="12" height="12" rx="3" fill="{COLORS[level]}">'
            f'<title>{day.isoformat()}: {count} contribuciones</title></rect>'
        )
    for label, row in [("lun", 1), ("mié", 3), ("vie", 5)]:
        parts.append(text(34, 189 + row * 16, label, 11))
    parts.append(text(778, 314, "Menos", 11))
    for index, color in enumerate(COLORS):
        parts.append(f'<rect x="{821 + index * 17}" y="303" width="12" height="12" rx="3" fill="{color}"/>')
    parts.append(text(913, 314, "Más", 11))
    parts.append(text(34, 314, "Lenguaje principal · repos propios", 11))
    parts.append(text(34, 345, "  /  ".join(f"{language} {count}" for language, count in languages.most_common(5)), 13, "#c4b5fd"))
    parts.append('<path d="M34 365H966" stroke="#303047"/>')
    parts.append(text(34, 389, "Datos de GitHub · Sin tarjetas de terceros", 11))
    parts.append(text(966, 389, updated, 11, extra='text-anchor="end"'))
    parts.append("</g></svg>\n")
    return "\n".join(parts)


def main():
    parser = CalendarParser()
    parser.feed(fetch(f"https://github.com/users/{USERNAME}/contributions"))
    days = parser.days()
    repos = []
    page = 1
    while True:
        batch = json.loads(fetch(
            f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}"
        ))
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    svg = render(days, repos)
    output = ROOT / "assets" / "activity.svg"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(svg, encoding="utf-8")
    temporary.replace(output)
    print(f"Updated {output.relative_to(ROOT)}: {len(days)} days, {len(repos)} repositories")


if __name__ == "__main__":
    main()
