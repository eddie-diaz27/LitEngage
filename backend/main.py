"""FastAPI application entry point for LitEngage."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.logging_config import setup_logging
from backend.routers import books, chat, recommendations, students

# Initialize logging
setup_logging(
    log_level=settings.log_level,
    log_format=settings.log_format,
    log_file=settings.log_file,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LitEngage - Library Book Recommendation API",
    description="AI-powered book recommendation system for school libraries",
    version="0.1.0",
    docs_url=f"{settings.api_prefix}/docs" if settings.enable_api_docs else None,
    redoc_url=f"{settings.api_prefix}/redoc" if settings.enable_api_docs else None,
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

# CORS middleware for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(books.router, prefix=settings.api_prefix)
app.include_router(students.router, prefix=settings.api_prefix)
app.include_router(recommendations.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)


@app.get(f"{settings.api_prefix}/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.environment,
    }


@app.on_event("startup")
async def startup_event():
    logger.info(
        "LitEngage API started",
        extra={
            "environment": settings.environment,
            "model": settings.gemini_model,
        },
    )
