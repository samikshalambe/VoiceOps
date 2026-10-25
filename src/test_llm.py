import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"])
r = client.chat.completions.create(
       model=os.environ["LLM_MODEL"],
       messages=[{"role": "user", "content": "Say hello in one short sentence."}],
)
print(r.choices[0].message.content)