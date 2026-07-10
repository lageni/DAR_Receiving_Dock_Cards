# CodePuppyDAR - Dependencies Log

**Last Sync**: 2026-07-10 | **Source**: Walmart Artifactory  
**Total Packages**: 58 (88 resolved with transitive deps)  
**Python Version**: 3.9+  

---

## Installation Source

All dependencies are installed from **Walmart Artifactory** (NOT public PyPI):
```
Index URL: https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple
Allow Insecure Host: pypi.ci.artifacts.walmart.com
```

This is configured in `pyproject.toml` under `[tool.uv]`

---

## Direct Dependencies

### Web Framework
- **fastapi** >=0.104.0 → v0.136.3
- **uvicorn[standard]** >=0.24.0 → v0.49.0
- **httpx** >=0.24.0 → v0.28.1

### Configuration & Data Handling
- **python-dotenv** >=1.0.0 → v1.2.2
- **pydantic** >=2.0.0 → v2.13.4

### PDF Generation
- **fpdf2** >=2.7.0 → v2.8.7
- **PyPDF2** >=3.0.0 → v3.0.1

### Database
- **pyodbc** >=5.0.0 → v5.3.0

### Google Cloud (BigQuery & Storage)
- **google-cloud-bigquery** >=3.11.0 → v3.42.2
- **google-auth** >=2.20.0 → v2.55.2
- **google-auth-oauthlib** >=1.0.0 → v1.4.0
- **google-auth-httplib2** >=0.2.0 → v0.4.0
- **google-cloud-storage** >=2.10.0 → v3.12.1

---

## Transitive Dependencies (Automatically Installed)

### FastAPI/Starlette Stack
- starlette==1.2.1
- typing-extensions==4.15.0
- typing-inspection==0.4.2
- h11==0.16.0
- httpcore==1.0.9
- httptools==0.8.0
- watchfiles==1.2.0
- websockets==16.0

### Pydantic Stack
- pydantic-core==2.46.4
- annotated-types==0.7.0
- annotated-doc==0.0.4

### PDF Stack
- pillow==12.2.0
- fonttools==4.63.0

### Google Cloud Stack
- google-api-core==2.31.0
- google-cloud-core==2.6.0
- googleapis-common-protos==1.75.0
- grpcio==1.82.1
- grpcio-status==1.82.1
- protobuf==7.35.1
- proto-plus==1.28.1
- google-crc32c==1.8.0
- google-resumable-media==2.10.0
- requests==2.34.2
- requests-oauthlib==2.0.0
- oauthlib==3.3.1

### Network & Security
- certifi==2026.5.20
- charset-normalizer==3.4.9
- idna==3.18
- urllib3==2.7.0
- cryptography==49.0.0
- cffi==2.1.0
- pycparser==3.0
- pyasn1==0.6.4
- pyasn1-modules==0.4.2

### Utilities
- click==8.4.1
- colorama==0.4.6
- defusedxml==0.7.1
- packaging==26.2
- pyparsing==3.3.2
- python-dateutil==2.9.0.post0
- pyyaml==6.0.3
- six==1.17.0
- anyio==4.13.0
- httplib2==0.32.0

---

## Installation Commands

### Initial Setup (via RUN.bat)
```batch
uv sync
```

### Manual Installation (if needed)
```bash
# Using uv (recommended)
uv sync

# Or using pip with Walmart Artifactory
pip install \
  --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple \
  --allow-insecure-host pypi.ci.artifacts.walmart.com \
  -r <(uv pip compile pyproject.toml)
```

---

## Notes

1. **No PyPI Fallback**: All packages come from Walmart Artifactory. If a package is unavailable, the build will fail.
2. **Google Cloud Auth**: Requires valid GCP credentials in `.env` (GCS_PROJECT_ID, GCS_DATASET_ID, etc.)
3. **VPN Requirement**: Walmart VPN or Eagle WiFi required to access Artifactory
4. **BigQuery Access**: Configured in `gcs_sync.py`
   - Default Project: `wmt-ambient-centeng`
   - Default Dataset: `6068_Engineering`
   - Default Table: `ACL_READ_RATE`

---

## Last Sync Output

```
Resolved 88 packages in 21.64s
Prepared 30 packages in 9.37s
Installed 58 packages in 1.11s
```

**Key Additions This Session**:
- google-cloud-bigquery==3.42.2
- google-cloud-storage==3.12.1
- google-auth and friends (oauth, httplib2)
- All transitive Google Cloud deps (protobuf, grpcio, cryptography, etc.)
