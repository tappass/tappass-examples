"""FastAPI microservice with TapPass governance.

Every LLM call goes through the governance pipeline.
Policy violations return structured 403 responses.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from tappass import AsyncAgent, PolicyBlockError, TapPassConnectionError

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

agent: AsyncAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = AsyncAgent(TAPPASS_URL, api_key=TAPPASS_API_KEY, model="gpt-4o-mini")
    yield
    await agent.aclose()


app = FastAPI(title="Governed AI Service", lifespan=lifespan)


class AnalyzeRequest(BaseModel):
    text: str
    question: str = "Summarize this text."


class AnalyzeResponse(BaseModel):
    answer: str
    model: str
    classification: str
    tokens_used: int


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """Analyze text with a governed LLM call."""
    try:
        response = await agent.chat(
            f"Context: {req.text}\n\nQuestion: {req.question}",
        )
    except PolicyBlockError as e:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Blocked by governance policy",
                "blocked_by": e.blocked_by,
                "classification": e.classification,
                "reason": e.reason,
            },
        )
    except TapPassConnectionError:
        raise HTTPException(503, "Governance service unavailable")

    return AnalyzeResponse(
        answer=response.content,
        model=response.model,
        classification=response.pipeline.classification,
        tokens_used=response.usage.total_tokens,
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "governed": True}
