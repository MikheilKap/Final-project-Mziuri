from fastapi import FastAPI
from routes.ai_routes import router

app = FastAPI()

app.include_router(router)