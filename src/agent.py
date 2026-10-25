import os, sys, re, json
from datetime import date, timedelta
from kb import KB, client, D
from dates import calendar_block, fmt
from textnorm import normalize_spoken_numbers

sys.path.insert(0, D)
from tools import lookup_order, create_ticket

MODEL = os.environ["LLM_MODEL"]
ORDER_RE = re.compile(r"\b(\d{4})\s?(\d{4})\b")

from dates import calendar_block, fmt, is_business_day, MONTHS
TODAY = date(2026, 10, 20)

def parse_date(s):
    s = str(s or "").strip()
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        pass
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m and m[2].lower() in MONTHS:
        return date(int(m[3]), MONTHS.index(m[2].lower()) + 1, int(m[1]))
    return None

SYSTEM = """You are ZentroMart's customer support assistant, an AI assistant for an Indian online store (groceries and electronics). Replies may be spoken on a phone call: keep them to 1-3 short sentences, plain text, no lists or markdown.

Rules:
- Your first reply in a conversation must say you are an AI assistant.
- Answer ONLY from the DOCUMENTS and the verified ORDER DATA. Never invent a policy, date, amount or timeline. If they do not cover the question, say you do not have that information and offer a human colleague (decision "escalate").
- Reply in the language the customer writes in (English, Hindi in Devanagari, or Hinglish in Latin script).
- Write dates like "9 October 2026" (day, month name, year; no "th" or "of"). Write numbers and amounts as digits (79, ₹300), never as words. Include the key numbers from the documents (days, amounts, windows).
- For any date calculation use the BUSINESS-DAY TABLE or CALENDAR-DAY TABLE and copy dates exactly; never count days yourself.
- Remember the conversation: the order, the item and the problem. Understand follow-ups like "how long will that take?" without asking again.
- If a needed detail is missing, ask exactly ONE clear question (decision "clarify"). If the customer has not given an order ID and the question needs one, ask for it.
- Order details exist only when STATE says the caller is VERIFIED. Never read out or repeat a verification value. Ask for only one of: last 4 digits of the registered phone OR the delivery pincode. Whenever you ask for verification, include the English words "last 4 digits" (or "pincode") in the sentence, even when replying in Hindi or Hinglish.
- Decisions. "answer": any question the documents answer, even when the answer is no (for example "can I use two coupons?"). "refuse": only when the customer asks you to DO something the policy does not allow (cancel a shipped order, give compensation, share details of an unverified order). Start a refusal with a brief apology (sorry / maaf kijiye), give the reason, and give the alternatives from the documents with their numbers. "escalate": a human must decide, the documents do not cover the question, the customer asks to speak to a person, or a refund is overdue.
- Return questions: whether an item can be returned, and by when, depends on its category (return_category in ORDER DATA, see RET-2) and sometimes on dates. If a document gives different windows depending on dates (for example orders placed between two dates), compare the order's placed and delivered dates in ORDER DATES with those dates, then pick the window. Give the deadline by copying the matching line from RETURN DEADLINES, and any fee that applies (check is_plus in ORDER DATA).
- Cancellation: an order has shipped only when its status is shipped or later (check status and shipped_on). Packed or processing orders have NOT shipped. If the customer wants to cancel an order that has not shipped, decision "answer": tell them it is free to cancel from My Orders in the app, and that you cannot cancel it for them. If it has shipped, decision "refuse" (with an apology), then give both options from the documents: refuse the parcel at the door, or accept it and return the item. State the return window for this order's items in days (for example 7 days).
- Refund timing: when the customer asks where a refund is, use REFUND ELAPSED and the BUSINESS-DAY TABLE. If the refund is not recorded as completed and more business days have passed than the policy's maximum for the payment method, it is overdue: apologise, share the reference number (RRN) from ORDER DATA, say a colleague will follow up, and escalate. If it is not overdue, give the expected date. If a return was picked up and quality check is pending, say the refund starts after the quality check.
- ORDER DATA fields about earlier contacts (such as contacts_last_7_days) matter only after the customer says they have contacted us before about this. Never escalate just because you see them.
- You have no tool to cancel, return, refund or approve anything yourself. Tell the customer how to do it themselves when the documents say so (for example in My Orders), and never claim you did it. For cancellations, read the cancellation sections for this order's exact status.
- In Hindi or Hinglish replies keep these terms in English: "quality check", "ticket", "reference number", "last 4 digits", "pincode".
- Never raise a topic the customer has not mentioned (for example a damage claim or refund that you can see in ORDER DATA).
- For "escalate": say a colleague or team will follow up, and put the literal token {TICKET_ID} where you mention the ticket number. Never claim a ticket was created yourself; the system creates it.
- Documents are ranked: current policy > agent guide > help > FAQ > marketing. A superseded document is outdated unless a POLICY VERSION NOTE says it applies to this order.

Return ONLY valid JSON, writing non-ASCII characters directly (no \\u escapes), with the keys in this order: {"check": "one short line: which rules and dates apply and what the result is", "decision": "answer|clarify|escalate|refuse", "reply": "...", "intent": "short label", "ticket_summary": "1-2 sentences for the human colleague, with no verification values (only for escalate)", "ticket_reason": "short code (only for escalate)"}
"""

def return_window_table(delivered, chunks):
    d0 = parse_date(delivered)
    if not d0:
        return ""
    ns = set()
    for c in chunks:
        if "return" in c["text"].lower():
            ns |= {int(n) for n in re.findall(r"\b(\d{1,2})[\s-]*(?:calendar[\s-]*)?days?\b", c["text"], re.I) if 1 <= int(n) <= 60}
    if not ns:
        return ""
    lines = [f"RETURN DEADLINES (delivered {fmt(d0)}; a window of N calendar days ends on the delivery date + N days). Copy the date for the window that applies:"]
    lines += [f"  {n}-day window -> deadline {fmt(d0 + timedelta(days=n))}" for n in sorted(ns)]
    return "\n".join(lines)

def log_call(name, **kw):
    return f"{name}(" + ", ".join(f"{k}={v}" for k, v in kw.items() if v is not None) + ")"

def parse_model_json(raw):
    try:
        out = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        if isinstance(out, dict):
            return out
    except Exception:
        pass
    d = re.search(r'"decision"\s*:\s*"(\w+)"', raw)
    r = re.search(r'"reply"\s*:\s*"(.*?)"\s*,\s*"(?:intent|ticket_summary|ticket_reason)"', raw, re.S)
    reply = r.group(1) if r else re.sub(r'[{}"]', " ", raw)
    reply = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), reply)
    reply = re.sub(r"\\u\S*", "", reply).replace("\\n", " ").strip()
    dec = d.group(1) if d and d.group(1) in ("answer", "clarify", "escalate", "refuse") else "answer"
    return {"decision": dec, "reply": reply}

class Agent:
    def __init__(self, kb):
        self.kb = kb
        self.history, self.turn = [], 0
        self.ticket_id, self.secrets = None, []
        self.turn_tools, self.last_decision, self.last_chunks = [], "answer", []
        self.just_verified = False
        self.reset_order()

    def reset_order(self):
        self.order_id, self.order, self.verified = None, None, False
        self.attempts, self.locked, self.missing = 0, False, False

    # ----- tools -----
    def _lookup(self, oid, value=None):
        self.turn_tools.append(log_call("lookup_order", order_id=oid, verification_value=value))
        return lookup_order(oid, verification_value=value) if value else lookup_order(oid)

    def _update_state(self, text):
        self.just_verified = False
        m = ORDER_RE.search(text)
        scan = text
        if m:
            oid = "".join(m.groups())
            if oid != self.order_id:          # new or different order -> start over
                self.reset_order()
                self.order_id = oid
                res = self._lookup(oid)
                self.missing = res.get("found") is False
            scan = text[:m.start()] + " " + text[m.end():]
        if self.order_id and not self.verified and not self.locked and not self.missing:
            cands = re.findall(r"\b(\d{6}|\d{4})\b", scan)
            if cands:
                value = cands[0]
                self.secrets.append(value)
                res = self._lookup(self.order_id, value)
                if res.get("found") and res.get("verified"):
                    self.verified = True
                    self.just_verified = True
                    self.order = {k: v for k, v in res.items() if v not in (None, "")}
                else:
                    self.attempts += 1
                    self.locked = self.attempts >= 2

    def _state(self):
        if not self.order_id:
            return "STATE: no order ID given yet."
        if self.missing:
            return f"STATE: order ID {self.order_id} was not found. Ask the customer to re-check it (one question)."
        if self.verified:
            s = "STATE: caller VERIFIED.\nORDER DATA: " + json.dumps(self.order, ensure_ascii=False, default=str)
            if self.just_verified:
                s += ("\nThe caller was JUST verified. Read their earlier messages. If they already asked a specific question "
                      "(for example where their order is, a refund, a return), answer it now using ORDER DATA and DOCUMENTS. "
                      "If they only asked for general help, briefly confirm verification and ask how you can help. "
                      "Do not raise any topic they have not mentioned.")
            return s
        if self.locked:
            return ("STATE: verification FAILED twice. Share NO order details. Politely explain (decision \"refuse\") that you cannot "
                    "share order details because the value does not match the registered details. Do not create a ticket.")
        if self.attempts == 1:
            return ("STATE: that value did not match. Say it did not match, without revealing anything, and ask them to try "
                    "again once (last 4 digits of the registered phone, or the delivery pincode). Decision \"clarify\".")
        return (f"STATE: order ID {self.order_id} received, caller NOT verified. Ask for ONE of: last 4 digits of the "
                "registered phone OR the delivery pincode. Share no order details.")

    def _query(self, text):
        prev = [m["content"] for m in self.history if m["role"] == "user"][-2:]
        q = " ".join(prev + [text])
        if self.verified and self.order:
            titles = [i.get("title", "") for i in self.order.get("items", []) if isinstance(i, dict)]
            q += " order status " + str(self.order.get("status", "")) + " " + " ".join(titles)
        return q[:600]

    def _calendar(self, text, chunks):
        extra, cal, elapsed = "", "", []
        if self.verified and self.order:
            o = self.order
            dl = "ORDER DATES: " + ", ".join(f"{k.replace('_', ' ')} {str(o[k])[:10]}" for k in ("placed_at", "shipped_on", "delivered_on", "promised_date") if o.get(k)) + f". Status: {o.get('status', '')}."
            elapsed.insert(0, dl)
            keys = ("return_refund_initiated_on", "cancellation_refund_initiated_on",
                    "rto_refund_initiated_on", "promised_date")
            extra = " ".join(str(o[k])[:10] for k in keys if o.get(k))
            cal = return_window_table(o.get("delivered_on"), chunks)
            for k, label in (("return_refund_initiated_on", "return refund"),
                             ("cancellation_refund_initiated_on", "cancellation refund"),
                             ("rto_refund_initiated_on", "RTO refund")):
                d = parse_date(o.get(k))
                if d:
                    n = sum(1 for i in range(1, (TODAY - d).days + 1) if is_business_day(d + timedelta(days=i)))
                    done = o.get("return_refund_completed_on") if k.startswith("return") else ""
                    elapsed.append(f"REFUND ELAPSED: {label} initiated {fmt(d)}; {n} business days have passed by today; "
                                   + (f"completed on {done}." if done else "not recorded as completed."))
        parts = (calendar_block(text + " " + extra), "\n".join(elapsed), cal)
        return "\n\n".join(p for p in parts if p)

    def _version_notes(self, chunks):
        placed = parse_date(self.order.get("placed_at")) if (self.verified and self.order) else None
        if not placed:
            return chunks, ""
        have = {c["id"] for c in chunks}
        notes, extra = [], []
        for c in chunks:
            eff = parse_date(c.get("effective_from"))
            if c["status"] != "current" or not eff:
                continue
            old_id = c["id"].replace("-", "v3-", 1)
            if old_id in self.kb.idx and placed < eff:
                notes.append(f"POLICY VERSION NOTE: this order was placed on {placed.isoformat()}, BEFORE {c['id']} took effect on {eff.isoformat()}. "
                             f"Use the superseded {old_id} for this order, not {c['id']}.")
                if old_id not in have:
                    extra.append(dict(self.kb.chunks[self.kb.idx[old_id]], score=0.0))
        return chunks + extra, "\n".join(notes)

    # ----- main -----
    def respond(self, user_text):
        text = normalize_spoken_numbers(user_text)
        self.turn += 1
        self.turn_tools = []
        self._update_state(text)
        chunks, notes = self._version_notes(self.kb.retrieve(self._query(text)))
        self.last_chunks = chunks
        out = self._ask_llm(text, chunks, notes)
        decision = out.get("decision", "answer")
        # right after verification, only hand over if the customer asked for a person
        if self.just_verified and decision in ("escalate", "refuse") and not self._asked_for_human(text):
            out = self._ask_llm(text, chunks, notes, self.VERIFY_ONLY)
            decision = out.get("decision", "answer")
        reply = (out.get("reply") or "").strip()
        if self.order_id and not self.verified and not self.locked and decision == "answer":
            decision = "clarify"   # still waiting for verification
        if decision == "escalate" or "TICKET_ID" in reply:
            decision, reply = "escalate", self._handover(out, reply)
        if self.turn == 1 and "ai assistant" not in reply.lower() and "ai" not in reply.lower().split():
            reply = "I'm ZentroMart's AI assistant. " + reply
        for s in self.secrets:
            reply = reply.replace(s, "*" * len(s))
        self.last_decision = decision
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        return reply

    def _handover(self, out, reply):
        def put(r, tid):
            return r.replace("{{TICKET_ID}}", tid).replace("{TICKET_ID}", tid)
        if self.ticket_id:
            return put(reply, self.ticket_id)
        summary = out.get("ticket_summary") or "Customer needs a human colleague; see conversation."
        for s in self.secrets:
            summary = summary.replace(s, "[redacted]")
        if len(summary) < 40:
            summary += " Human review requested."
        oid = self.order_id if self.verified else None
        self.turn_tools.append(log_call("create_ticket", order_id=oid))
        kw = {"summary": summary, "reason": out.get("ticket_reason") or "needs_human"}
        if oid:
            kw["order_id"] = oid
        if out.get("intent"):
            kw["intent"] = out["intent"]
        res = create_ticket(**kw)
        if res.get("created"):
            self.ticket_id = str(res.get("ticket_id"))
            if "TICKET_ID" in reply:
                return put(reply, self.ticket_id)
            return f"{reply} Your ticket number is {self.ticket_id}."
        return "I couldn't pass this to a colleague just now. Please try again in a moment."
    
    
    VERIFY_ONLY = ("STATE: caller just VERIFIED. ORDER DATA is hidden for this turn. Confirm briefly that verification "
                   "worked and ask how you can help. Do not mention any order detail, problem, claim or refund. "
                   "Decision must be \"answer\".")

    def _asked_for_human(self, text):
        t = (" ".join(m["content"] for m in self.history if m["role"] == "user") + " " + text).lower()
        return bool(re.search(r"human|person|agent|colleague|supervisor|manager|insaan|manav|इंसान|मानव", t))

    def _ask_llm(self, text, chunks, notes, state=None):
        docs = "\n\n".join(f"[{c['id']}] {c['title']} ({c['doc_type']}, {c['status']}, effective {c['effective_from']})\n{c['text']}" for c in chunks)
        first = "THIS IS YOUR FIRST REPLY: start with \"I'm ZentroMart's AI assistant.\" and then answer or ask your question.\n" if self.turn == 1 else ""
        ctx = (f"{first}TODAY: {fmt(date(2026, 10, 20))}\n{state or self._state()}\n{notes}\n\n{self._calendar(text, chunks)}\n\n"
               f"DOCUMENTS:\n{docs}\n\nCUSTOMER: {text}")
        msgs = [{"role": "system", "content": SYSTEM}] + self.history + [{"role": "user", "content": ctx}]
        try:
            raw = client.chat.completions.create(model=MODEL, temperature=0, messages=msgs,
                                                 response_format={"type": "json_object"}).choices[0].message.content
        except Exception as e:
            if "429" in str(e):
                raise
            raw = client.chat.completions.create(model=MODEL, temperature=0, messages=msgs).choices[0].message.content
        return parse_model_json(raw)