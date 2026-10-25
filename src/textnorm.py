import re

_DIGITS = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
           "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
_MULT = {"double": 2, "triple": 3}

def normalize_spoken_numbers(text):
    out, run, mult = [], [], 1

    def flush():
        nonlocal run
        if len(run) >= 2:
            out.append("".join(d for d, _ in run))
        else:
            out.extend(o for _, o in run)
        run = []

    for t in text.split():
        w = re.sub(r"[^\w]", "", t.lower())
        if w in _MULT:
            mult = _MULT[w]; continue
        if w in _DIGITS and (w != "oh" or run):
            run.append((_DIGITS[w] * mult, t)); mult = 1
        else:
            mult = 1
            flush(); out.append(t)
    flush()
    return " ".join(out)