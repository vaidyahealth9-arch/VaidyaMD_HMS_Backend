"""
VaidyaMD HMS — Database Environment Resolver
Resolves database connection strings and async engines for 'local', 'dev', and 'prod' targets.
"""

import os
import sys
import subprocess
import logging
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logger = logging.getLogger("vaidyamd.db_env")


LOCAL_DEFAULT_URL = "postgresql+asyncpg://vaidya_md_admin:vaidya_md_secret_2026@localhost:5432/vaidya_md_db"


def _get_gcp_secret(secret_name: str, project_id: str) -> str | None:
    """Attempt to fetch a secret via gcloud CLI if available."""
    try:
        bin_name = "gcloud.cmd" if sys.platform == "win32" else "gcloud"
        cmd = [bin_name, "secrets", "versions", "access", "latest", f"--secret={secret_name}", f"--project={project_id}"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return None


def resolve_database_url(env_name: str = "local", explicit_url: str | None = None, auto_confirm: bool = False) -> str:
    """
    Resolves the async database connection string based on the target environment.
    Supported environments: 'local', 'dev', 'prod'.
    """
    if explicit_url:
        url = explicit_url
    else:
        env_lower = (env_name or "local").lower().strip()

        if env_lower in ["local", "development"]:
            url = os.environ.get("LOCAL_DATABASE_URL") or os.environ.get("DATABASE_URL") or LOCAL_DEFAULT_URL

        elif env_lower in ["dev", "vaidya-hms-dev"]:
            url = os.environ.get("DEV_DATABASE_URL")
            if not url:
                # Cloud SQL Proxy local port 5433
                password = _get_gcp_secret("hms-db-password", "vaidya-hms-dev") or "vaidya_md_secret_2026"
                url = f"postgresql+asyncpg://vaidya_md_admin:{password}@127.0.0.1:5433/vaidya_md_db"

        elif env_lower in ["prod", "production", "vaidya-hms-prod"]:
            if not auto_confirm and sys.stdin.isatty():
                print("\n" + "=" * 70)
                print("🚨 CAUTION: You are targeting PRODUCTION (vaidya-hms-prod)!")
                print("=" * 70)
                confirm = input("Type 'PROD' to confirm execution against production database: ")
                if confirm.strip() != "PROD":
                    print("❌ Operation aborted by user.")
                    sys.exit(1)

            url = os.environ.get("PROD_DATABASE_URL")
            if not url:
                # Cloud SQL Proxy local port 5434
                password = _get_gcp_secret("hms-db-password", "vaidya-hms-prod") or "vaidya_md_prod_secret_DuT9xNYMITQLcE2WSQUE3g"
                url = f"postgresql+asyncpg://vaidya_md_admin:{password}@127.0.0.1:5434/vaidya_md_db"

        else:
            raise ValueError(f"Unknown environment '{env_name}'. Choose from: 'local', 'dev', 'prod'.")

    # Ensure asyncpg driver prefix
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    return url


def create_env_engine(env_name: str = "local", explicit_url: str | None = None, auto_confirm: bool = False) -> AsyncEngine:
    """Creates a SQLAlchemy async engine targeting the selected environment."""
    url = resolve_database_url(env_name=env_name, explicit_url=explicit_url, auto_confirm=auto_confirm)
    return create_async_engine(url, echo=False, pool_pre_ping=True)
