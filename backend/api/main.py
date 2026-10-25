"""FastAPI app (Feature 004): CORS, error handlers, routers, start-up.

    cd backend && uvicorn api.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import db, errors, settings, solver
from api.routers import auth, meta, profile
from tripwise import data

ROUTERS = [meta, auth, profile]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    data.default()                 # load the dataset once
    db.create_schema()             # idempotent
    solver.start()
    yield
    solver.stop()
    db.close()


def create_app() -> FastAPI:
    s = settings.get()
    app = FastAPI(title="Tripwise API", version="1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])
    errors.install(app)
    for r in ROUTERS:
        app.include_router(r.router)
    return app


app = create_app()
