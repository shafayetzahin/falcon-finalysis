"""Local privacy, retention, audit and deployment-readiness controls."""
from pathlib import Path

import pandas as pd
import streamlit as st

from components.ui import header, repository


header("Local Governance", "Record local operating settings, inspect the audit trail and prepare for controlled deployment.")
repo = repository()
saved = repo.settings()

st.warning("Managed sign-in and account storage require administrator configuration. Without them, public hosted mode uses a temporary session database. Encryption at rest and automatic backups must be provided by the host before confidential records are used.")

with st.form("local_governance"):
    organization = st.text_input("Organization or pilot name", saved.get("organization", ""))
    reviewer_role = st.text_input("Required reviewer role", saved.get("reviewer_role", "Credit reviewer"))
    retention_days = st.number_input("Target document retention (days)", min_value=1, max_value=3650,
                                     value=int(saved.get("retention_days", "365")))
    purpose = st.text_area("Approved local-use purpose", saved.get(
        "purpose", "Internal analytical review with human confirmation"))
    submitted = st.form_submit_button("Save local governance settings", type="primary")
if submitted:
    repo.save_settings({"organization": organization.strip(), "reviewer_role": reviewer_role.strip(),
                        "retention_days": str(retention_days), "purpose": purpose.strip()})
    st.success("Local governance settings saved and recorded in the audit trail.")

st.subheader("Deployment readiness")
checks = pd.DataFrame([
    ("Localhost-only binding", "Implemented", "The packaged start command binds to 127.0.0.1."),
    ("Decision-support disclaimer", "Implemented", "Shown at the beginning of each browser session."),
    ("Human credit-decision record", "Implemented", "CredGrid stores reviewer, rationale and overrides."),
    ("Versioned CredGrid model", "Implemented", "Saved cases record the model version."),
    ("User authentication and roles", "Required for deployment", "Use an identity provider and enforce least privilege."),
    ("Encryption at rest and key management", "Required for deployment", "Protect statements, database and backups."),
    ("Automated retention and consent withdrawal", "Required for deployment", "Define policy before deleting applicant data."),
    ("Legal, privacy and fair-lending validation", "Required for deployment", "Complete for the intended entity and product."),
    ("Model calibration and outcome monitoring", "Required for deployment", "Validate against representative observed outcomes."),
], columns=["Control", "Status", "Evidence or next action"])
st.dataframe(checks, hide_index=True, width="stretch")

st.subheader("Local audit trail")
events = repo.audit_events()
if events:
    st.dataframe(pd.DataFrame(events), hide_index=True, width="stretch")
else:
    st.info("The audit trail will record project, portfolio, credit-case and governance saves.")

database_path = Path(repo.path)
if database_path.exists():
    st.download_button("Download workspace database backup", repo.backup_bytes(),
                       file_name="Falcon_Finalysis_local_backup.db",
                       mime="application/octet-stream", width="stretch")
    st.caption("The downloaded SQLite backup is not encrypted by Falcon Finalysis. Store it only in an approved encrypted location.")
