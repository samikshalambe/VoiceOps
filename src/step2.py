from dates import calendar_block
import os, csv, re, time
from kb import KB, client, D

MODEL = os.environ["LLM_MODEL"]

SYSTEM = """You are ZentroMart's customer support assistant, an AI assistant for an Indian online store (groceries and electronics).
Rules:
- Your first reply must say you are an AI assistant.
- Answer ONLY from the DOCUMENTS below. Never invent a policy, date, amount or timeline.
- If the documents do not cover the question, say you don't have that information and offer to connect the customer to a human colleague.
- If the documents say a human must decide, say a colleague will follow up.
- Documents are ranked by authority: current policy > agent guide > help > FAQ > marketing. A section marked superseded is outdated; use it only if the question is clearly about an old order.
- Reply in the customer's language (English, Hindi in Devanagari, or Hinglish in Latin script).
- Keep it short, 1 to 3 sentences, plain text. Include the year in dates.
- Today's date is 20 October 2026.
- For refund or delivery dates: first find the policy's range of business days (for example 5 to 7). The earliest date is the table line for the lower number, and the latest date is the table line for the higher number. Copy both dates exactly from the table and say it should arrive between them, by the later date.
- Answer only if a document directly addresses the customer's specific question. Do not substitute a related fact. If no document covers it, say you don't have that information and offer to connect them to a colleague.
"""

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

def docs_block(chunks):
    return "\n\n".join(
        f"[{c['id']}] {c['title']} (file {c['doc']}, {c['doc_type']}, {c['status']}, effective {c['effective_from']})\n{c['text']}"
        for c in chunks)

def ask(question, chunks):
    try:
        return client.chat.completions.create(
            model=MODEL, temperature=0,
            messages=[{"role": "system", "content": SYSTEM + "\n\nDOCUMENTS:\n" + docs_block(chunks) + "\n\n" + calendar_block(question)},
                      {"role": "user", "content": question}],
        ).choices[0].message.content
    except Exception as e:
        if "429" in str(e):
            raise SystemExit("Quota hit. Progress is saved. Wait or switch model, then run again.")
        print("  error:", str(e)[:80]); return None

kb = KB()
rows = list(csv.DictReader(open(os.path.join(D, "practice", "questions.csv"), encoding="utf-8", newline="")))
out_path = "step2_results.csv"
done = {}
if os.path.exists(out_path):
    done = {r["id"]: r for r in csv.DictReader(open(out_path, encoding="utf-8", newline=""))}

fields = ["id", "question", "reply", "correct", "retrieved"]
for r in rows:
    if r["id"] in done and done[r["id"]]["correct"] == "True":
        continue
    chunks = kb.retrieve(r["question"])
    reply = ask(r["question"], chunks)
    if reply is None:
        continue
    done[r["id"]] = {"id": r["id"], "question": r["question"], "reply": reply,
                     "correct": str(check(reply, r)), "retrieved": " ; ".join(c["id"] for c in chunks)}
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(done.values())
    print(r["id"], done[r["id"]]["correct"])
    time.sleep(5)

n = sum(v["correct"] == "True" for v in done.values())
print(f"\nSTEP 2 SCORE: {n}/{len(done)} correct   (Step 1 was 11/51)")