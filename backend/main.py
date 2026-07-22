from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend.database import Base, engine
from backend import models  # noqa: F401 — register models with Base
from backend.routers import meeting

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Meeting Assist", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meeting.router, prefix="/api/meetings", tags=["meetings"])


@app.get("/health")
def health():
    return {"status": "ok"}
