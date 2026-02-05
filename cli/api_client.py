"""Convenience wrapper for the API client for easier import."""

from cli.api.client import BackendClient, APIError, get_client

__all__ = ["BackendClient", "APIError", "get_client"]
