from kb import KB
from agent import Agent

a = Agent(KB())
while True:
    t = input("You: ").strip()
    if t.lower() in ("quit", "exit"):
        break
    r = a.respond(t)
    print("Bot:", r, f"   [{a.last_decision}; tools: {a.turn_tools}]")