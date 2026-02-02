from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from account.view import router as account_router
from auth.view import router as auth_router
from scenario.view import router as scenario_router
from handlers.document_process.view import router as documents_router

app = FastAPI(title="Cognitive Interview API")

app.include_router(account_router, prefix="/api/v1/account", tags=["account"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(scenario_router, prefix="/api/v1/scenario", tags=["scenario"]) 
app.include_router(documents_router, prefix="/api/v1/document", tags=["documents"])
