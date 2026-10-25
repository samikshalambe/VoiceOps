import os, re, csv, glob
from dotenv import load_dotenv

load_dotenv()
D = os.environ["DATASET_DIR"]
SECTION_RE = re.compile(r"^##\s*\[([^\]]+)\]\s*(.*)$", re.M)

def meta(head, key):
    m = re.search(rf"^\W*{key}\s*[:=]\s*(.+?)\s*$", head, re.M | re.I)
    return m.group(1).strip().strip("\"'") if m else ""

chunks, skipped = [], []
for path in sorted(glob.glob(os.path.join(D, "kb", "*.md"))):
    text = open(path, encoding="utf-8").read()
    secs = list(SECTION_RE.finditer(text))
    head = text[: secs[0].start()] if secs else text
    status = meta(head, "status").lower() or "MISSING"
    doc_type = meta(head, "doc_type") or "MISSING"
    name = os.path.basename(path)
    if status != "current":
        skipped.append((name, status))
        continue
    for i, s in enumerate(secs):
        end = secs[i + 1].start() if i + 1 < len(secs) else len(text)
        chunks.append({"id": s.group(1).strip(), "title": s.group(2).strip(),
                       "doc": name, "doc_type": doc_type,
                       "text": text[s.end():end].strip()})

with open(os.path.join(D, "data", "products.csv"), encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        chunks.append({"id": "products.csv:" + r["sku"], "title": r["title"], "doc": "products.csv",
                       "doc_type": "catalog", "text": "; ".join(f"{k}={v}" for k, v in r.items())})

print("Chunks:", len(chunks))
print("Skipped (not current):", skipped)
print("Doc types:", sorted({c["doc_type"] for c in chunks}))
for c in chunks[:6]:
    print("-", c["id"], "|", c["title"], "|", c["doc"], "|", len(c["text"]), "chars")