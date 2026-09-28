# Public deployment

Falcon Finalysis is ready for Streamlit Community Cloud with `app.py` as the entrypoint.

1. Push this directory to a GitHub repository.
2. In Streamlit Community Cloud, select the repository, branch and `app.py`.
3. Open Advanced settings, select Python 3.12 and add this root-level secret:

```toml
FALCON_FINALYSIS_HOSTED = "true"
```

4. Deploy and verify the decision-support notice, demo, uploads and report downloads.

Hosted mode creates a separate temporary SQLite database for each browser session. Saved work may
disappear when the session or server restarts. Do not use the public prototype for confidential,
personal, regulated or production records.
