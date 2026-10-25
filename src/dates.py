import os, re, csv
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()
D = os.environ["DATASET_DIR"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]

with open(os.path.join(D, "data", "holidays.csv"), encoding="utf-8", newline="") as f:
    HOLIDAYS = {date.fromisoformat(r["date"]): r["name"] for r in csv.DictReader(f)}

def is_business_day(d):
    return d.weekday() != 6 and d not in HOLIDAYS   # Mon-Sat, not a holiday

def add_business_days(start, n):
    d = start
    while n > 0:
        d += timedelta(days=1)
        if is_business_day(d):
            n -= 1
    return d

def fmt(d):
    return f"{d.day} {MONTHS[d.month - 1].title()} {d.year} ({d.strftime('%A')})"

def find_dates(text):
    found = []
    for m in re.finditer(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})\b", text, re.I):
        found.append(date(int(m[3]), MONTHS.index(m[2].lower()) + 1, int(m[1])))
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
        found.append(date(int(m[1]), int(m[2]), int(m[3])))
    return list(dict.fromkeys(found))

def calendar_block(text, nmax=10):
    ds = find_dates(text)
    if not ds:
        return ""
    lines = ["BUSINESS-DAY TABLE (computed by code; counts Monday to Saturday, skips Sundays and holidays; "
             "business day 1 is the first business day AFTER the start date). "
             "Never count days yourself: copy dates from this table exactly.",
             "Holidays: " + ", ".join(f"{fmt(d)} {n}" for d, n in sorted(HOLIDAYS.items()))]
    for d in ds:
        lines.append(f"\nRefund or event start: {fmt(d)}")
        for n in range(1, nmax + 1):
            lines.append(f"  business day {n} -> {fmt(add_business_days(d, n))}")
    return "\n".join(lines)

if __name__ == "__main__":
    print(calendar_block("refund started 17 October 2026"))