"""LlamaIndex with TapPass governance.

Every LLM call goes through TapPass. We use SummaryIndex (no embeddings) so
the whole pipeline stays governed — TapPass routes chat completions, not
the embedding endpoint.
"""

import os

from llama_index.core import SummaryIndex, Document, Settings
from llama_index.llms.openai import OpenAI as LlamaOpenAI

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

llm = LlamaOpenAI(
    model="gpt-4o-mini",
    api_base=f"{TAPPASS_URL}/v1",
    api_key=TAPPASS_API_KEY,
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

index = SummaryIndex.from_documents(documents)
query_engine = index.as_query_engine()


# --- Query (governed) ---

response = query_engine.query("What does the EU AI Act require?")
print("Answer:", response)
