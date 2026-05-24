import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
import database
from routers import auth as auth_router
from routers import categories as categories_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool()
    yield
    if database._pool is not None:
        database._pool.closeall()

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router.router)
app.include_router(categories_router.router)
