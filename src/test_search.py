import os, csv
from kb import KB, D

kb = KB()
rows = list(csv.DictReader(open(os.path.join(D, "practice", "questions.csv"), encoding="utf-8", newline="")))
hit_all = hit_any = n = 0
for r in rows:
    gold = [g for g in r["gold_evidence"].split(" ; ") if g]
    if not gold:
        continue
    got = {c["id"] for c in kb.retrieve(r["question"])}
    n += 1
    ok_all = all(g in got for g in gold)
    hit_all += ok_all
    hit_any += any(g in got for g in gold)
    if not ok_all:
        print(r["id"], "| wanted", gold, "| got", sorted(got))
print(f"\nAll gold sections in top 5: {hit_all}/{n} | at least one: {hit_any}/{n}")