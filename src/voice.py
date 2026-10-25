from dotenv import load_dotenv
load_dotenv()
import os, re
from gnani.stt import GnaniSTTClient
from gnani.tts import GnaniTTSClient

TTS_MODEL, TTS_VOICE = "timbre-v2.5", "Kaveri"   # always name the model
_stt = _tts = None

def _clients():
    global _stt, _tts
    if _stt is None:
        _stt, _tts = GnaniSTTClient(), GnaniTTSClient()   # reads GNANI_API_KEY
    return _stt, _tts

def speakable(text):
    """Make the reply easy to hear: short ticket IDs, grouped long numbers, no symbols."""
    text = re.sub(r"(?:ticket\s*(?:number|id)?\s*(?:is|:)?\s*)?TKT([0-9a-f]{8,})",
                  lambda m: "ticket number ending " + ", ".join(m.group(1)[-4:]), text, flags=re.I)
    text = text.replace("₹", "rupees ")
    text = re.sub(r"\b\d{7,}\b", lambda m: " ".join(m.group(0)[i:i + 4] for i in range(0, len(m.group(0)), 4)), text)
    return re.sub(r"[*_#`]", "", text)

def transcribe(audio_path, lang="en-IN"):
    stt, _ = _clients()
    return stt.transcribe(str(audio_path), language_code=lang)["transcript"]

def synthesize(text, out_wav, lang="en-IN"):
    _, tts = _clients()
    tts.synthesize(speakable(text), voice=TTS_VOICE, model=TTS_MODEL, language=lang, output_file=str(out_wav))