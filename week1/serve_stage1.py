"""Stage 1 server — bare /ask with typed I/O and real token usage.

Run: uvicorn serve_stage1:app --port 8000 --reload
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parent / ".env")

app = FastAPI()


def get_client() -> OpenAI:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="XAI_API_KEY is not set")
    return OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")


class AskRequest(BaseModel):
    """Typed request body so bad input is rejected before we spend tokens."""

    question: str


class AskResponse(BaseModel):
    """Typed response so callers always get the same shape back."""

    answer: str
    tokens_used: int


@app.post("/ask")
def ask(body: AskRequest) -> AskResponse:
    """Answer one question and surface real token usage for cost visibility."""

    completion = get_client().chat.completions.create(
        model="grok-4.7",
        messages=[{"role": "user", "content": body.question}],
    )

    answer = completion.choices[0].message.content or ""
    tokens_used = completion.usage.total_tokens if completion.usage else 0

    return AskResponse(answer=answer, tokens_used=tokens_used)
