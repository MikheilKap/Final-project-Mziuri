import requests
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from config.settings import API_KEY
from services.markdown_utils import format_ai_response

router = APIRouter(prefix="/ai")
templates = Jinja2Templates(directory="templates")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


def ask_groq(prompt: str) -> str:
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API key is not configured. Add GROQ_API_KEY or API_KEY to your .env file.",
        )

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You help users cancel subscriptions. Reply in clean plain markdown: "
                    "use ## for section headings, numbered lists for steps, and **bold** "
                    "sparingly for UI labels. Do not use === underline dividers."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    try:
        response = requests.post(
            GROQ_URL,
            headers=headers,
            json=body,
            timeout=60,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Groq API: {exc}",
        ) from exc

    if not response.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Groq API error: {response.status_code}",
        )

    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Groq API returned an unexpected response.",
        ) from exc


@router.post("/ask")
async def ask_ai_assistant(request: Request, service_name: str = Form(...)):
    prompt = (
        f"Provide clear, step-by-step instructions on how to cancel a "
        f"{service_name} subscription quickly. Keep it structured and easy to read."
    )

    try:
        ai_response = ask_groq(prompt)
        formatted = format_ai_response(ai_response)
        return JSONResponse({"html": formatted, "success": True})
    except HTTPException as e:
        return JSONResponse(
            {"html": f"<p class='text-danger'>{e.detail}</p>", "success": False},
            status_code=e.status_code,
        )
    except Exception:
        return JSONResponse(
            {
                "html": (
                    "<p class='text-danger'>Unable to generate instructions. "
                    "Check your Groq API key in .env.</p>"
                ),
                "success": False,
            },
            status_code=500,
        )
