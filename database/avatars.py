AVATARS = {
    "fox": {"file": "fox.png", "color": "#e65100", "label": "Fox"},
    "cat": {"file": "cat.png", "color": "#7b1fa2", "label": "Cat"},
    "dog": {"file": "dog.png", "color": "#1565c0", "label": "Dog"},
    "bear": {"file": "bear.png", "color": "#5d4037", "label": "Bear"},
    "panda": {"file": "panda.png", "color": "#424242", "label": "Panda"},
    "owl": {"file": "owl.png", "color": "#6a1b9a", "label": "Owl"},
    "rabbit": {"file": "rabbit.png", "color": "#ec407a", "label": "Rabbit"},
    "robot": {"file": "robot.png", "color": "#546e7a", "label": "Robot"},
}


def get_avatar_info(avatar_id: str | None) -> dict:
    if avatar_id and avatar_id in AVATARS:
        return {"id": avatar_id, **AVATARS[avatar_id]}
    return {"id": "fox", **AVATARS["fox"]}
