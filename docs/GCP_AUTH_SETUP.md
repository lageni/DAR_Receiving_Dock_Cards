# GCP Authentication Setup (Local ADC)

The Unloader app (`unloader_server.py`, `unloader_client.py`) authenticates to
Google BigQuery using **Application Default Credentials (ADC)** — your own
Walmart Google identity, logged in locally via `gcloud`. There is no service
account involved; each developer/machine logs in for themselves.

(The archived ACL app's `sync_bigquery.py` - see `archive/old_acl_app/` - uses
the same auth setup.)

## One-Time Setup

1. **Install the Google Cloud SDK** (if `gcloud` isn't already on PATH):
   https://cloud.google.com/sdk/docs/install

2. **Run the setup script** from the `CodePuppyDAR` folder:
   ```bash
   python scripts\setup_gcp_auth.py
   ```
   This will:
   - Verify `gcloud` is installed
   - Check whether ADC credentials already exist
   - If missing, open a browser window for you to log in with your
     Walmart Google account
   - Optionally set the ADC "quota project" from `GCS_PROJECT_ID` in your `.env`

3. **Done.** `bigquery.Client()` calls anywhere in the codebase will now pick up
   your credentials automatically — no code changes, no env vars to export by
   hand.

## Where Credentials Live

- **Windows:** `%APPDATA%\gcloud\application_default_credentials.json`
- **Mac/Linux:** `~/.config/gcloud/application_default_credentials.json`

These are personal, machine-local, and **never committed to git** (they're not
even inside the repo).

## Automatic Checks

`RUN_UNLOADER.bat` and `RUN_UNLOADER_CLIENT.bat` both run a quick,
non-interactive check (`python scripts\setup_gcp_auth.py --check`) before
starting their server/client. If credentials are missing, they'll automatically
kick off the interactive login flow for you — you shouldn't need to remember to
run this manually.

## Manual gcloud Equivalent

If you'd rather do it by hand instead of using the script:
```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project <YOUR_PROJECT_ID>
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `gcloud: command not found` | Install Google Cloud SDK, restart terminal |
| `DefaultCredentialsError` in Python | Run `python scripts\setup_gcp_auth.py` |
| `Project was not passed and could not be determined from the environment` | Set `GCS_PROJECT_ID` in `.env`. Under the hood, personal ADC logins (`authorized_user` credentials) normally rely on the `gcloud` CLI being installed *and on PATH* to auto-detect the active project at runtime - if `gcloud` goes missing/uninstalled on the machine later, that detection silently fails even though your ADC file and `gcloud config` still look correct. `scripts/bq_client.py` sidesteps this by passing `GCS_PROJECT_ID` to `bigquery.Client()` explicitly, so it no longer depends on `gcloud` being present after initial login. |
| Login works but BigQuery still 403s | Ask a BigQuery dataset owner to grant your account `roles/bigquery.dataViewer` (or use the `bq-ad-group-locater` process to get added to the right AD group) |
| Credentials expired | Re-run `python scripts\setup_gcp_auth.py` — it detects and re-runs login if the file is missing/invalid |
