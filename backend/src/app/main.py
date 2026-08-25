from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.webui import find_webui_dir, mount_webui
from app.routers import (
    accounts,
    ai_settings,
    categories,
    contacts,
    dashboard,
    data_lifecycle,
    rules,
    settings,
    statements,
    transactions,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SG Expenditure Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(statements.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(contacts.router)
app.include_router(rules.router)
app.include_router(categories.router)
app.include_router(settings.router)
app.include_router(ai_settings.router)
app.include_router(data_lifecycle.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Must come after every router: the SPA fallback is a catch-all, so anything
# registered later would be unreachable. No-op when there's no build on disk
# (the dev-server case), which is why this isn't an error branch.
_webui_dir = find_webui_dir()
if _webui_dir is not None:
    mount_webui(app, _webui_dir)


def run():
    """Entry point for `expenditure-tracker` / `uvx expenditure-tracker`."""
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
