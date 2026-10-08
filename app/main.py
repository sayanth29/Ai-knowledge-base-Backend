from fastapi import FastAPI

from app.core.database import engine
import app.models  # noqa: F401 — Register all SQLAlchemy models


app = FastAPI()


@app.get("/db-test")
async def db_test():
    try:
        async with engine.connect() as connection:
            return {"database": "connected"}
    except Exception as e:
        return {"database": "connection failed", "error": str(e)}


@app.get("/table")
def root():
    return {"message": "API is runningg"}
