import os, sys, csv, json
from dotenv import load_dotenv
load_dotenv()
D = os.environ["DATASET_DIR"]
sys.path.insert(0, D)

rows = list(csv.DictReader(open(os.path.join(D, "practice", "conversations.csv"), encoding="utf-8", newline="")))
shown = []
for r in rows:
    if r["conversation_id"] not in shown:
        shown.append(r["conversation_id"])
    if len(shown) > 2:
        break
    print(r["conversation_id"], "turn", r["turn"], "|", r["scenario"], "|", r["language"])
    print("  customer:", r["customer_message"])
    print("  expected:", r["expected_decision"], "| tools:", r["expected_tool_calls"])
    print("  must:", r["must_include"], "| not:", r["must_not_include"])
    print("  notes:", r["notes"])

from tools import lookup_order
oid = rows[0]["order_id"]
print("\nunverified lookup of", oid, "->", json.dumps(lookup_order(oid), indent=1, default=str)[:600])