from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from account.view import router as account_router
from auth.view import router as auth_router
from note.view import router as note_router

app = FastAPI(title="Cognitive Interview API")

app.include_router(account_router, prefix="/api/v1/account", tags=["account"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(note_router, prefix="/api/v1/note", tags=["note"])
