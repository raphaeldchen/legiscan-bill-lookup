import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
import database

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool()
    yield

app = FastAPI(lifespan=lifespan)
