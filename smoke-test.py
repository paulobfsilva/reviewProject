import os
from openai import OpenAI

# Load API key from environment
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")

client = OpenAI(api_key=api_key)
resp = client.chat.completions.create(
  model="ft:gpt-4o-mini-2024-07-18:personal:pe-sermons-v1:Bwc5Ziyc",
  messages=[
    {"role":"user","content":
     "SRC: He was coming down the road.\nRAW: Ele vinha descendo a estrada."}],
  temperature=0)
print(resp.choices[0].message.content)
