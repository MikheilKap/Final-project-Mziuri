import requests
from fastapi import HTTPException

from config.settings import API_KEY

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


def ask_groq(prompt: str) -> str:
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_KEY არ არის კონფიგურირებული. დაამატეთ ის .env ფაილში.",
        )

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
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
            detail=f"Groq API-თან კავშირი ვერ დამყარდა: {exc}",
        ) from exc

    if not response.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Groq API შეცდომა: {response.status_code}",
        )

    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Groq API-მა მოულოდელო პასუხი დააბრუნა.",
        ) from exc