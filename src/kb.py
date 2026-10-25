import os, re, csv, glob, json, time
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
def _find_dataset():
    for c in (os.environ.get("DATASET_DIR"), "./Capstone_Project_Dataset_FTTT_2026", "./dataset", "../Capstone_Project_Dataset_FTTT_2026"):
        if c and os.path.isdir(os.path.join(c, "kb")):
            return os.path.abspath(c)
    raise SystemExit("Dataset not found. Set DATASET_DIR in .env to the extracted dataset folder (the one containing kb/, data/ and tools/).")

D = _find_dataset()
EMBED_MODEL = os.environ.get("EMBED_MODEL", "gemini-embedding-001")
CACHE = "chunk_embeddings.json"
SECTION_RE = re.compile(r"^##\s*\[([^\]]+)\]\s*(.*)$", re.M)
SKU_RE = re.compile(r"\b[A-Z]{3}-\d{4}\b")
ALWAYS = ["KB-00.1", "KB-00.2", "KB-00.3", "ESC-1"]
PRIORITY = {"policy": 0, "agent_guide": 1, "catalog": 1, "help": 2, "faq": 3, "marketing": 4, "meta": 5}

client = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"],
                timeout=60, max_retries=2)

def meta(head, key):
    m = re.search(rf"^\W*{key}\s*[:=]\s*(.+?)\s*$", head, re.M | re.I)
    return m.group(1).strip().strip("\"'") if m else ""

def load_chunks():
    chunks = []
    for path in sorted(glob.glob(os.path.join(D, "kb", "*.md"))):
        text = open(path, encoding="utf-8").read()
        secs = list(SECTION_RE.finditer(text))
        head = text[: secs[0].start()] if secs else text
        status = meta(head, "status").lower() or "current"
        doc_type = meta(head, "doc_type") or "help"
        for i, s in enumerate(secs):
            end = secs[i + 1].start() if i + 1 < len(secs) else len(text)
            chunks.append({"id": s.group(1).strip(), "title": s.group(2).strip(),
                           "doc": os.path.basename(path), "doc_type": doc_type, "status": status,
                           "effective_from": meta(head, "effective_from"),
                           "text": text[s.end():end].strip()})
    with open(os.path.join(D, "data", "products.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            chunks.append({"id": "products.csv:" + r["sku"], "title": r["title"], "doc": "products.csv",
                           "doc_type": "catalog", "status": "current", "effective_from": "",
                           "text": "; ".join(f"{k}={v}" for k, v in r.items())})
    return chunks

_sent = []

def _throttle(n, limit=90):
    while True:
        now = time.time()
        while _sent and now - _sent[0] > 60:
            _sent.pop(0)
        if len(_sent) + n <= limit:
            break
        time.sleep(max(1, 61 - (now - _sent[0])))
    _sent.extend([time.time()] * n)

def embed(texts, batch=20):
    out = []
    for i in range(0, len(texts), batch):
        part = texts[i:i + batch]
        _throttle(len(part))
        for attempt in range(5):
            try:
                resp = client.embeddings.create(model=EMBED_MODEL, input=part)
                break
            except Exception as e:
                if "429" in str(e) and attempt < 4:
                    print("  rate limit, waiting 20s...")
                    time.sleep(20)
                else:
                    raise
        out += [d.embedding for d in resp.data]
    return np.array(out, dtype=np.float32)

class KB:
    def __init__(self):
        self.chunks = load_chunks()
        texts = [f"{c['title']}\n{c['text']}" for c in self.chunks]
        key = [c["id"] for c in self.chunks]
        if os.path.exists(CACHE):
            cached = json.load(open(CACHE))
            if cached["ids"] == key and cached["model"] == EMBED_MODEL:
                self.emb = np.array(cached["emb"], dtype=np.float32)
        if not hasattr(self, "emb"):
            print("Embedding chunks (one time)...")
            self.emb = embed(texts)
            json.dump({"ids": key, "model": EMBED_MODEL, "emb": self.emb.tolist()}, open(CACHE, "w"))
        self.emb /= np.linalg.norm(self.emb, axis=1, keepdims=True)
        self.prio = np.array([PRIORITY.get(c["doc_type"], 3) for c in self.chunks])
        self.penalty = np.array([0.0 if c["status"] == "current" else 0.05 for c in self.chunks])
        self.is_prod = np.array([c["doc"] == "products.csv" for c in self.chunks])
        self.idx = {c["id"]: i for i, c in enumerate(self.chunks)}

    def _scores(self, query):
        if not hasattr(self, "qcache"):
            self.qcache = json.load(open("query_cache.json")) if os.path.exists("query_cache.json") else {}
        if query not in self.qcache:
            self.qcache[query] = embed([query])[0].tolist()
            json.dump(self.qcache, open("query_cache.json", "w"))
        q = np.array(self.qcache[query], dtype=np.float32)
        q /= np.linalg.norm(q)
        return self.emb @ q - 0.01 * self.prio - self.penalty

    def retrieve(self, query, k_docs=8, k_prod=2):
        scores = self._scores(query)
        order = np.argsort(-scores)
        picked = []

        def add(cid):
            if cid in self.idx and cid not in picked:
                picked.append(cid)

        for sku in SKU_RE.findall(query.upper()):
            add("products.csv:" + sku)
        n = 0
        for i in order:
            if not self.is_prod[i] and n < k_docs:
                add(self.chunks[i]["id"]); n += 1
        n = 0
        for i in order:
            if self.is_prod[i] and n < k_prod:
                add(self.chunks[i]["id"]); n += 1
        for cid in ALWAYS:
            add(cid)
        return [dict(self.chunks[self.idx[c]], score=float(scores[self.idx[c]])) for c in picked]