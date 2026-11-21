from fastapi import APIRouter
from backend.api.v1.endpoints import system, policies, claims, documents

api_router = APIRouter()

api_router.include_router(system.router, tags=["System & Health"])
api_router.include_router(policies.router, prefix="/policies", tags=["Policies & Clauses"])
api_router.include_router(claims.router, prefix="/claims", tags=["Claims & Findings"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents & Chunks"])
