def format_response(service: str, ai_response: str, steps: list[str]) -> dict:
    return {
        "service": service,
        "explanation": ai_response,
        "steps": steps,
    }
