from fastapi import APIRouter
from pydantic import BaseModel

from services.prompt_service import build_cancel_prompt
from services.groq_service import ask_groq
from services.formatter import format_response

router = APIRouter()


class CancelRequest(BaseModel):
    service: str
    steps: list[str]


@router.post("/ai/explain-cancel")
def explain_cancel(req: CancelRequest):

    prompt = build_cancel_prompt(
        req.service,
        req.steps
    )

    ai_response = ask_groq(prompt)

    final_response = format_response(
        req.service,
        ai_response,
        req.steps
    )

    return final_response