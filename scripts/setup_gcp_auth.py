"""
GCP Authentication Setup for Unloader / ACL BigQuery Access
=============================================================

Sets up Application Default Credentials (ADC) so `bigquery.Client()`
calls in unloader_server.py, unloader_client.py, and sync_bigquery.py
"just work" without any code changes.

Usage:
    python scripts/setup_gcp_auth.py            # interactive full setup
    python scripts/setup_gcp_auth.py --check    # silent check only (used by RUN_*.bat)

Exit codes:
    0 = authenticated / setup succeeded
    1 = gcloud not installed
    2 = not authenticated (and --check was passed, so we didn't try to fix it)
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_gcloud() -> str | None:
    return shutil.which("gcloud") or shutil.which("gcloud.cmd")


def adc_credentials_path() -> Path:
    """Where ADC stores its credentials on this OS."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "gcloud" / "application_default_credentials.json"
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def has_valid_adc_file() -> bool:
    path = adc_credentials_path()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
        return bool(data.get("refresh_token") or data.get("type") == "service_account")
    except (json.JSONDecodeError, OSError):
        return False


def read_project_id_from_env() -> str | None:
    """Best-effort read of GCS_PROJECT_ID from .env without extra deps."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("GCS_PROJECT_ID="):
            return line.split("=", 1)[1].strip() or None
    return None


def run_login(gcloud: str) -> bool:
    print("\n[AUTH] Launching browser for Google login (ADC)...")
    result = subprocess.run([gcloud, "auth", "application-default", "login"])
    return result.returncode == 0


def set_quota_project(gcloud: str, project_id: str) -> None:
    print(f"[AUTH] Setting ADC quota project to '{project_id}'...")
    subprocess.run(
        [gcloud, "auth", "application-default", "set-quota-project", project_id],
        check=False,
    )


def main() -> int:
    check_only = "--check" in sys.argv

    gcloud = find_gcloud()
    if not gcloud:
        print("[ERROR] gcloud CLI not found on PATH.")
        print("        Install: https://cloud.google.com/sdk/docs/install")
        return 1

    if has_valid_adc_file():
        print("[OK] GCP Application Default Credentials already present.")
        return 0

    if check_only:
        print("[WARN] No GCP Application Default Credentials found.")
        print("       Run: python scripts\\setup_gcp_auth.py")
        return 2

    print("GCP Authentication Setup for Unloader / ACL System")
    print("=" * 60)
    print("No local ADC credentials found - starting login flow.")

    if not run_login(gcloud):
        print("[ERROR] gcloud login failed or was cancelled.")
        return 2

    project_id = read_project_id_from_env()
    if project_id:
        set_quota_project(gcloud, project_id)
    else:
        print("[INFO] No GCS_PROJECT_ID set in .env - skipping quota project step.")
        print("       You can set it later with:")
        print("       gcloud auth application-default set-quota-project <PROJECT_ID>")

    if has_valid_adc_file():
        print("\n[OK] GCP authentication complete. BigQuery calls should work now.")
        return 0

    print("\n[ERROR] Login appeared to succeed but no credentials file was found.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
