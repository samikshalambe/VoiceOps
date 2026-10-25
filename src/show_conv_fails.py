import os, csv
from dotenv import load_dotenv
load_dotenv()
D = os.environ["DATASET_DIR"]

exp = {(r["conversation_id"], r["turn"]): r for r in csv.DictReader(
    open(os.path.join(D, "practice", "conversations.csv"), encoding="utf-8", newline=""))}
for r in csv.DictReader(open("conv_results.csv", encoding="utf-8", newline="")):
    if r["all"] == "False":
        g = exp[(r["conv"], r["turn"])]
        print(f"{r['conv']} turn {r['turn']} | {g['scenario']}")
        print("  CUSTOMER:", r["customer"])
        print("  BOT:     ", r["reply"], f"[{r['decision']}, expected {r['expected']}]")
        print("  NEED:    ", g["must_include"], "| NOT:", g["must_not_include"], "| TOOLS:", g["expected_tool_calls"])
        print("  NOTES:   ", g["notes"])
        print()