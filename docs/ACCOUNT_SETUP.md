# Accounts and durable storage setup

Account mode is opt-in and currently inactive on the public prototype. Choose an
OIDC identity provider and a host with a persistent, encrypted volume first.
Streamlit Community Cloud's ephemeral filesystem is not durable account storage.

## Deployment

1. Deploy one app instance with Python 3.12 and `requirements.txt`. This initial
   implementation uses one SQLite database per account on a local mounted volume;
   it is not intended for multiple replicas or a shared network filesystem.
2. Attach an encrypted persistent volume outside the source checkout and public
   static directories. Restrict its filesystem permissions to the application user.
3. Register an OIDC application with your provider, with the exact callback
   `https://YOUR_DOMAIN/oauth2callback`. Configure one default provider as documented
   at https://docs.streamlit.io/develop/api-reference/user/st.login.
4. Store the following in the host's secret manager / `.streamlit/secrets.toml`:

   ```toml
   [auth]
   redirect_uri = "https://YOUR_DOMAIN/oauth2callback"
   cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
   client_id = "PROVIDER_CLIENT_ID"
   client_secret = "PROVIDER_CLIENT_SECRET"
   server_metadata_url = "PROVIDER_OPENID_CONFIGURATION_URL"
   ```

   Never commit real secrets. The provider must supply `iss`, `sub` and `exp` claims.
   Restrict eligible pilot users in the provider; application-level organization
   roles, paid-plan entitlements and invitation controls are not implemented.
5. Set environment variables:

   ```text
   FALCON_FINALYSIS_HOSTED=true
   FALCON_FINALYSIS_ACCOUNTS=true
   FALCON_FINALYSIS_DATA_DIR=/absolute/persistent/volume/falcon
   ```

   On Windows use an absolute Windows volume path. The data directory alone does
   not make storage durable; validate the host's mounted-volume configuration.
6. Test two accounts: save a project in each, sign out, sign in again, and verify
   isolation. Restart the application/container and verify both accounts retain
   their own data. Check that expired sessions and signed-out page links are blocked.

## Backup and restore

Projects & Data provides JSON recovery for company setup, financial inputs and
source references. Restore always creates a separate saved project. It does not
restore scenarios, portfolios, credit cases or original documents.

Local Governance provides a consistent SQLite workspace backup including all
saved tables. This file is unencrypted; protect it with encrypted backup storage.
For a full operator restore, stop the app, preserve the current volume, check the
backup with SQLite `PRAGMA integrity_check`, then restore it to the correct account's
workspace.db path. Restart and verify project counts, portfolios and credit cases.
Never load an arbitrary database upload into a running user's workspace.

Configure encrypted, off-host volume snapshots and a retention policy with the
hosting provider. Automatic backup scheduling is not implemented in the app.
Rehearse restoration in staging before activating real accounts. Account paths
depend on the provider issuer and subject, so changing providers requires an
explicit, verified migration; matching email addresses is not sufficient.

## Activation status

The code provides sign-in gating, account-separated storage and manual recovery.
It does not provision hosting, identity-provider accounts, encryption keys, backup
jobs, password recovery policies or monitoring. Complete those steps and a security
review before using confidential customer records.
