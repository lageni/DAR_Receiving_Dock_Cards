"""Shared BigQuery client factory for the Unloader server and client.

Why this exists
----------------
`bigquery.Client()` with no arguments relies on `google.auth.default()` to
figure out *which* GCP project to bill/query against. For personal ADC
logins (`gcloud auth application-default login`, i.e. `authorized_user`
credentials - not a service account), that project lookup is done by
shelling out to the `gcloud` CLI binary at runtime. If `gcloud` isn't
installed or isn't on PATH on the machine actually running the server,
that lookup silently fails and you get:

    Project was not passed and could not be determined from the environment.

...even when `.env`, the ADC file, and `gcloud config` all correctly have
the project set. `gcloud` not being available is an environment problem
we can't fully control - so instead we pass the project explicitly, which
sidesteps the gcloud-shellout dependency entirely.

Both `unloader_server.py` and `unloader_client.py` import from here instead
of each rolling their own `bigquery.Client()` call.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Cached singleton - avoids re-authenticating on every single cache cycle /
# request. Reset to None if you ever need to force a fresh client.
_client = None


def _resolve_project_id() -> str | None:
    """Best-effort project id resolution, explicit env vars first.

    Checked in order:
    1. GCS_PROJECT_ID   - this project's own .env convention
    2. GOOGLE_CLOUD_PROJECT / GCLOUD_PROJECT - standard GCP env vars, in
       case someone's running this in a context where those are already set
       (e.g. Cloud Run, a CI runner, another dev's machine setup)
    """
    return (
        os.getenv("GCS_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
    )


def get_bigquery_client():
    """Get a cached, authenticated BigQuery client with an explicit project.

    Returns None (and logs why) instead of raising, so callers can degrade
    gracefully the way they already do today.
    """
    global _client
    if _client is not None:
        return _client

    project_id = _resolve_project_id()
    if not project_id:
        logger.error(
            "[BQ-ERROR] No project id found. Set GCS_PROJECT_ID in .env "
            "(see docs/GCP_AUTH_SETUP.md)."
        )
        return None

    try:
        from google.cloud import bigquery

        _client = bigquery.Client(project=project_id)
        logger.info(f"[BQ] BigQuery client initialized for project '{project_id}'")
        return _client
    except Exception as e:
        logger.error(f"[BQ-ERROR] Failed to initialize BigQuery client: {e}")
        return None
