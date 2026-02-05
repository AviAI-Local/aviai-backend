from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from account.view import router as account_router
from auth.view import router as auth_router
from scenario.view import router as scenario_router
from handlers.document_process.view import router as documents_router
from agent.session.view import router as session_router

app = FastAPI(title="Cognitive Interview API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router, prefix="/api/v1/account", tags=["account"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(documents_router, prefix="/api/v1/document", tags=["documents"])
app.include_router(scenario_router, prefix="/api/v1/scenario", tags=["scenario"])
app.include_router(session_router, prefix="/api/v1/session", tags=["session"]) 
