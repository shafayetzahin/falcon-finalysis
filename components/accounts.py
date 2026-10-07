"""Opt-in OIDC entry gate. Misconfiguration must never open a shared workspace."""
import os
import streamlit as st
from core.accounts import accounts_enabled, account_path


def require_account(show_controls: bool = True) -> None:
    if not accounts_enabled():
        return
    if not os.environ.get('FALCON_FINALYSIS_DATA_DIR'):
        st.error('Account storage is not configured. The administrator must attach a persistent volume.')
        st.stop()
    try:
        auth = st.secrets['auth']
        if not all(auth.get(key) for key in ('redirect_uri', 'cookie_secret', 'client_id',
                                             'client_secret', 'server_metadata_url')):
            raise ValueError('Incomplete provider settings')
    except (KeyError, FileNotFoundError, ValueError, TypeError, AttributeError):
        st.error('Sign-in setup is incomplete. Contact the administrator.')
        st.stop()
    if not st.user.get('is_logged_in', False):
        st.title('Welcome to Falcon Finalysis')
        st.write('Sign in to open your private saved projects and portfolios.')
        if st.button('Sign in', type='primary'):
            st.login()
        st.stop()
    try:
        path = account_path(os.environ['FALCON_FINALYSIS_DATA_DIR'], st.user.to_dict())
    except ValueError as exc:
        st.error(str(exc))
        if st.button('Sign out and try again'):
            st.session_state.clear()
            st.logout()
        st.stop()
    # Clear all previous workspace state on an identity change.
    if st.session_state.get('_account_identity') != str(path):
        st.session_state.clear()
        st.session_state['_account_identity'] = str(path)
    if show_controls:
        with st.sidebar:
            st.caption('Private account workspace')
            if st.button('Sign out'):
                st.session_state.clear()
                st.logout()
                st.stop()
