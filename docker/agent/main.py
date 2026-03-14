"""Example agent running alongside TapPass in Docker."""

import os
from fastapi import FastAPI
from openai import OpenAI

app = FastAPI()

# Reads OPENAI_BASE_URL and OPENAI_API_KEY from environment
# These point at the TapPass container (set in docker-compose.yml)
client = OpenAI()


@app.post("/ask")
async def ask(question: str):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": question}],
    )
    return {"answer": response.choices[0].message.content}


@app.get("/health")
async def health():
    return {"status": "ok"}
