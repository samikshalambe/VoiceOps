import sys
from kb import KB

k = KB()
for c in k.chunks:
    if any(c["id"].startswith(p) for p in sys.argv[1:]):
        print(f"[{c['id']}] {c['title']} ({c['status']}, {c['effective_from']})")
        print(c["text"], "\n")
        