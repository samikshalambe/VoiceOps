# ZentroMart VoiceOps agent

A voice customer-support agent: Gnani STT -> LLM + RAG + tools -> Gnani TTS.

## Setup
```
python -m venv .venv
.venv\Scripts\activate        (Windows)   or   source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        (then fill in your keys)
```
Extract the dataset and set `DATASET_DIR` in `.env` to the folder containing `kb/`, `data/` and `tools/`.
The dataset is not included in this repo.

## Run (batch)
```
python run.py --input path\to\audio_folder --output out_folder
```
For every audio file it saves `<name>.json` (heard text, reply text, decision, tool calls, retrieved section IDs),
`<name>_reply.wav`, and `results.json`. Add `--lang hi-IN` for Hindi audio, and `--session` to treat the
files (sorted by name) as one conversation. The first run embeds the knowledge base (about 2 minutes) and caches it.

## Evaluate
```
python src\step1.py            # Step 1: no documents
python src\step2.py            # Step 2: RAG
python src\eval_conv.py        # Step 3: conversations
```

## How it works
- `src/kb.py`: section-level chunks with IDs, exact SKU lookup, separate policy/product search.
- `src/agent.py`: conversation state, identity check before any order details, tools only through code,
  tickets confirmed only when `created=True`.
- `src/dates.py`: business-day and calendar-day tables computed in code, not by the LLM.
- `src/voice.py`: Gnani STT/TTS only.