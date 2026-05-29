def build_cancel_prompt(service_name, steps):

    formatted_steps = "\n".join(
        [f"{i+1}. {step}" for i, step in enumerate(steps)]
    )

    prompt = f"""
You are a subscription cancellation assistant.

ONLY explain the provided steps.
Do not invent information.

Service: {service_name}

Cancellation Steps:
{formatted_steps}

Explain these steps clearly for a normal user.
"""

    return prompt