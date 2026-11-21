"""Scarica i calendari iCal di Airbnb e Booking e scrive availability.json.

Gli indirizzi iCal NON stanno nel repo: arrivano dalle variabili d'ambiente
ICAL_AIRBNB e ICAL_BOOKING (GitHub Actions > Secrets). Nel file pubblico
finiscono solo gli intervalli di date occupate, senza nomi o dettagli.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "availability.json")
SOURCES = ["ICAL_AIRBNB", "ICAL_BOOKING"]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (calendar-sync)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse(text):
    text = re.sub(r"\r?\n[ \t]", "", text)  # righe spezzate (RFC 5545)
    out = []
    for ev in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        s = re.search(r"^DTSTART[^:\r\n]*:(\d{8})", ev, re.M)
        if not s:
            continue
        e = re.search(r"^DTEND[^:\r\n]*:(\d{8})", ev, re.M)
        a = dt.datetime.strptime(s.group(1), "%Y%m%d").date()
        b = dt.datetime.strptime(e.group(1), "%Y%m%d").date() if e else a + dt.timedelta(days=1)
        if b <= a:
            b = a + dt.timedelta(days=1)
        out.append((a, b))
    return out


def main():
    urls = [os.environ.get(k, "").strip() for k in SOURCES]
    urls = [u for u in urls if u]
    if not urls:
        print("Nessun calendario configurato: niente da fare.")
        return
    ranges = []
    for u in urls:
        ranges += parse(fetch(u))  # se un download fallisce lo script si ferma e il file resta com'è
    today = dt.date.today()
    ranges = sorted(r for r in ranges if r[1] > today)
    merged = []
    for a, b in ranges:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    data = {"booked": [[a.isoformat(), b.isoformat()] for a, b in merged]}
    new = json.dumps(data, separators=(", ", ": ")) + "\n"
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    if new != old:
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write(new)
        print(f"Aggiornato: {len(merged)} periodi occupati.")
    else:
        print("Nessuna modifica.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"Errore: {exc}", file=sys.stderr)
        sys.exit(1)
