import os
from voice import synthesize

os.makedirs("conv_audio", exist_ok=True)
clips = {
    "c1": "Hello, I need help with my order.",
    "c2": "My order number is eight nine seven eight two eight three seven.",
    "c3": "The last four digits are four five three three.",
    "c4": "My TV arrived damaged. Can you approve the replacement right now?",
}
for name, text in clips.items():
    synthesize(text, f"conv_audio/{name}.wav")
    print("made", name)