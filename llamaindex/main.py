"""LlamaIndex RAG pipeline with TapPass governance.

Retrieval is local. LLM calls go through TapPass.
PII in documents is caught before reaching the model.
"""

import os
from tappass import Agent

from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.llms.openai import OpenAI as LlamaOpenAI

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

# --- Connect to TapPass ---

tp = Agent(TAPPASS_URL, TAPPASS_API_KEY)

llm = LlamaOpenAI(
    model="gpt-4o-mini",
    api_base=tp.gateway_url,
    api_key=tp.api_key,
)
Settings.llm = llm


# --- Create in-memory index ---

documents = [
    Document(text=(
        "The EU AI Act classifies AI systems into risk categories: "
        "unacceptable, high-risk, limited risk, and minimal risk. "
        "High-risk systems must comply with transparency, data governance, "
        "and human oversight requirements."
    )),
    Document(text=(
        "GDPR Article 22 gives individuals the right not to be subject to "
        "decisions based solely on automated processing. AI agents that "
        "make decisions about people must provide meaningful explanations."
    )),
]

index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()


# --- Query (governed) ---

response = query_engine.query("What does the EU AI Act require?")
print("Answer:", response)
