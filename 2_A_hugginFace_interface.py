import os
from openai import OpenAI

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ["HF_TOKEN"],
)

completion = client.chat.completions.create(
    model="openai/gpt-oss-20b:groq",
    messages=[
        {
            "role": "user",
        
            "content": "write about AI-driven threat intelligence",

        },
        {
            "role": "system",
            "content": "respon in rude and sarcastic manner"
        }
    ],
)

print(completion.choices[0].message)