from __future__ import annotations

from supabase import Client, create_client

from app.config import settings


def create_service_role_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def create_user_client(access_token: str) -> Client:
    client = create_service_role_client()
    client.postgrest.auth(access_token)
    return client
