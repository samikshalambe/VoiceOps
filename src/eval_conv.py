import os, sys, csv, re, time
from collections import defaultdict
from kb import KB, D
from agent import Agent

OUT = "conv_results.csv"
FIELDS = ["conv", "turn", "customer", "reply", "decision", "expected", "tools",
          "ok_decision", "ok_include", "ok_not", "ok_tools", "all"]

def norm(s):
    s = s.lower().replace("₹", " ")
    s = re.sub(r"(?<=\d),(?=\d)", "", s)
    return re.sub(r"\s+", " ", s)

def has_fact(reply, fact):
    return any(norm(a).strip() in norm(reply) for a in fact.split(" / "))

def call_keys(spec):
    keys = set()
    for m in re.finditer(r"(lookup_order|create_ticket)\(([^)]*)\)", spec or ""):
        name, args = m.groups()
        if name == "create_ticket":
            keys.add("create_ticket")
        else:
            o = re.search(r"order_id=['\"]?(\d+)", args); v = re.search(r"verification_value=['\"]?(\d+)", args)
            keys.add(f"lookup_order|{o[1] if o else ''}|{v[1] if v else ''}")
    return keys

def save(rows):
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)

src = list(csv.DictReader(open(os.path.join(D, "practice", "conversations.csv"), encoding="utf-8", newline="")))
groups = defaultdict(list)
for r in src:
    groups[r["conversation_id"]].append(r)

want = sys.argv[1:]
saved = list(csv.DictReader(open(OUT, encoding="utf-8", newline=""))) if os.path.exists(OUT) else []
if want:
    saved = [r for r in saved if r["conv"] not in want]          # rerun the ones you named
have = defaultdict(int)
for r in saved:
    have[r["conv"]] += 1
todo = [c for c in groups if (c in want if want else have[c] < len(groups[c]))]
saved = [r for r in saved if r["conv"] not in todo]               # drop partial runs

kb = KB()
for cid in todo:
    turns = sorted(groups[cid], key=lambda r: int(r["turn"]))
    ag, new = Agent(kb), []
    try:
        for r in turns:
            reply = ag.respond(r["customer_message"])
            ok = {
                "decision": ag.last_decision == r["expected_decision"],
                "include": all(has_fact(reply, f) for f in r["must_include"].split(" ; ") if f.strip()),
                "not": not any(norm(p).strip() in norm(reply) for p in r["must_not_include"].split(" ; ") if p.strip()),
                "tools": call_keys(r["expected_tool_calls"]) <= call_keys(" ".join(ag.turn_tools)),
            }
            allok = all(ok.values())
            new.append({"conv": cid, "turn": r["turn"], "customer": r["customer_message"], "reply": reply,
                        "decision": ag.last_decision, "expected": r["expected_decision"],
                        "tools": " | ".join(ag.turn_tools), "ok_decision": ok["decision"],
                        "ok_include": ok["include"], "ok_not": ok["not"], "ok_tools": ok["tools"], "all": allok})
            print(cid, r["turn"], "OK" if allok else "FAIL " + ",".join(k for k, v in ok.items() if not v))
            time.sleep(4)
    except Exception as e:
        save(saved)
        if "429" in str(e):
            raise SystemExit(f"Quota hit during {cid}. Finished conversations are saved. Wait, then run again.")
        raise
    saved += new
    save(saved)

n = len(saved)
good = sum(str(r["all"]) == "True" for r in saved)
print(f"\nSTEP 3 (in {OUT}): {good}/{n} turns fully correct")