from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db as db_mod
from app.routers import auth as auth_router, imports as imports_router
from app.routers import participants as participants_router
from app.routers import contingents as contingents_router
from app.routers import accommodation as accommodation_router
from app.routers import schedule as schedule_router
from app.routers import inventory as inventory_router
from app.routers import vendors as vendors_router
from app.routers import disruptions as disruptions_router
from app.routers import control as control_router
from app.routers import chatbot as chatbot_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    db_mod.Base.metadata.create_all(db_mod.engine)
    yield


app = FastAPI(title="FestOS", version="0.2.0",
              description="Epinoia 2026 — Aarohan internal control portal (backend)",
              lifespan=lifespan)

# The frontend (Vite dev server on :5173 or any built copy) needs this.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(imports_router.router)
app.include_router(participants_router.router)
app.include_router(contingents_router.router)
app.include_router(accommodation_router.router)
app.include_router(schedule_router.router)
app.include_router(inventory_router.router)
app.include_router(vendors_router.router)
app.include_router(disruptions_router.router)
app.include_router(control_router.router)
app.include_router(chatbot_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}
