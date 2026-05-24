import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
import database
from routers import auth as auth_router
from routers import categories as categories_router
from routers import fetch as fetch_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router.router)
app.include_router(categories_router.router)
app.include_router(fetch_router.router)
