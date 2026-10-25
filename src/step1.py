import os, csv, re, time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"],
                timeout=60, max_retries=0)

SYSTEM = (
    "You are ZentroMart's customer support assistant, an AI assistant for an Indian "
    "online store selling groceries and electronics. Your first reply must tell the "
    "customer you are an AI assistant. Keep answers short, 1 to 3 sentences. "
    "Do not invent policies, dates or amounts."
)

def norm(s):
    s = s.lower().replace("₹", " ")
    s = re.sub(r"(?<=\d),(?=\d)", "", s)
    return re.sub(r"\s+", " ", s)

def has_fact(reply, fact):
    return any(norm(alt).strip() in norm(reply) for alt in fact.split(" / "))

def check(reply, r):
    inc = all(has_fact(reply, f) for f in r["must_include"].split(" ; ") if f.strip())
    bad = any(norm(p).strip() in norm(reply) for p in r["must_not_include"].split(" ; ") if p.strip())
    return inc and not bad

def ask(question):
    try:
        return client.chat.completions.create(
            model=os.environ["LLM_MODEL"],
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": question}],
        ).choices[0].message.content
    except Exception as e:
        if "429" in str(e):
            raise SystemExit("Quota hit. Progress is saved. Wait or switch model, then run again.")
        print("  error:", str(e)[:80]); return None

path = os.path.join(os.environ["DATASET_DIR"], "practice", "questions.csv")
with open(path, encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

out_path = "step1_results.csv"
done = {}
if os.path.exists(out_path):
    with open(out_path, encoding="utf-8", newline="") as f:
        done = {r["id"]: r for r in csv.DictReader(f)}

fields = ["id", "question", "reply", "correct"]
for r in rows:
    if r["id"] in done:
        continue
    reply = ask(r["question"])
    if reply is None:
        continue
    done[r["id"]] = {"id": r["id"], "question": r["question"], "reply": reply, "correct": str(check(reply, r))}
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(done.values())
    print(r["id"], done[r["id"]]["correct"])
    time.sleep(5)

n = sum(v["correct"] == "True" for v in done.values())
print(f"\nSTEP 1 SCORE: {n}/{len(done)} correct")