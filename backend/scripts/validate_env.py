#!/usr/bin/env python3
"""Validate environment configuration."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.config import settings


def validate_config():
    """Validate all required config values are set."""
    errors = []
    warnings = []

    # Required settings
    if not settings.database_url:
        errors.append("DATABASE_URL not set")

    if settings.jwt_secret_key == "your-secret-key-change-in-production":
        warnings.append("JWT_SECRET_KEY still using default value (change for production!)")

    if not settings.openai_api_key:
        warnings.append("OPENAI_API_KEY not set (required for OpenAI features)")

    # Vector database check
    if not settings.pinecone_api_key and not settings.qdrant_url:
        warnings.append("Neither PINECONE_API_KEY nor QDRANT_URL is set (vector storage needed for RAG)")

    # Check embedding dimensions match
    if settings.embedding_dimensions != 3072 and settings.embedding_model == "text-embedding-3-large":
        errors.append(f"EMBEDDING_DIMENSIONS ({settings.embedding_dimensions}) doesn't match text-embedding-3-large (3072)")

    # Print results
    if errors:
        print("❌ Configuration validation failed:\n")
        for error in errors:
            print(f"  ERROR: {error}")
        print()

    if warnings:
        print("⚠️  Configuration warnings:\n")
        for warning in warnings:
            print(f"  WARNING: {warning}")
        print()

    if not errors and not warnings:
        print("✅ Configuration validation passed")
        return 0
    elif not errors:
        print("✅ Configuration validation passed (with warnings)")
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit_code = validate_config()
    sys.exit(exit_code)
