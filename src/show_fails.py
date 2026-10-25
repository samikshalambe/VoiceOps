import os, csv
from dotenv import load_dotenv
load_dotenv()
D = os.environ["DATASET_DIR"]

q = {r["id"]: r for r in csv.DictReader(open(os.path.join(D, "practice", "questions.csv"), encoding="utf-8", newline=""))}
for r in csv.DictReader(open("step2_results.csv", encoding="utf-8", newline="")):
    if r["correct"] == "False":
        g = q[r["id"]]
        print(r["id"], "|", r["question"])
        print("  BOT:      ", r["reply"])
        print("  EXPECTED: ", g["reference_answer"])
        print("  MUST HAVE:", g["must_include"], "| NOT:", g["must_not_include"])
        print()