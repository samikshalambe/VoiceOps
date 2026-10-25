import os, sys, json, time, argparse
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from kb import KB
from agent import Agent
from voice import transcribe, synthesize

AUDIO = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"}
SORRY = "Sorry, I didn't catch that. Could you say it again?"
BUSY = "Sorry, I'm having trouble right now. Please try again in a moment."

def safe_respond(agent, text):
    for attempt in range(4):
        try:
            return agent.respond(text)
        except Exception as e:
            if "429" in str(e) or "503" in str(e):
                time.sleep(15 * (attempt + 1))
                continue
            print("  agent error:", str(e)[:100])
            break
    agent.last_decision = "clarify"
    return BUSY

def main():
    ap = argparse.ArgumentParser(description="Run the ZentroMart voice agent on a folder of audio files.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--lang", default="en-IN", help="Gnani language code, e.g. en-IN or hi-IN")
    ap.add_argument("--session", action="store_true", help="treat all files, sorted by name, as one conversation")
    a = ap.parse_args()
    out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
    kb = KB()
    shared = Agent(kb) if a.session else None
    results = []
    for f in sorted(p for p in Path(a.input).iterdir() if p.suffix.lower() in AUDIO):
        agent = shared or Agent(kb)
        rec = {"file": f.name}
        try:
            heard = transcribe(f, a.lang)
            rec["heard"] = heard
            reply = safe_respond(agent, heard) if heard.strip() else SORRY
            rec.update(reply=reply, decision=agent.last_decision, tool_calls=agent.turn_tools,
                       retrieved=[c["id"] for c in agent.last_chunks])
            synthesize(reply, out / f"{f.stem}_reply.wav", a.lang)
        except Exception as e:
            rec["error"] = repr(e)[:300]
            try:
                synthesize(SORRY, out / f"{f.stem}_reply.wav", a.lang)
            except Exception:
                pass
        results.append(rec)
        (out / f"{f.stem}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f.name, "->", rec.get("reply", rec.get("error")))
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()