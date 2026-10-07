"""Provider-authenticated workspace identities; never accept identity from form input."""
import hashlib
import json
import math
import os
from pathlib import Path
import time


def accounts_enabled() -> bool:
    # An unrecognized flag must not silently bypass the account gate.
    return os.environ.get('FALCON_FINALYSIS_ACCOUNTS', '').strip().lower() not in {
        '', '0', 'false', 'no', 'off'}


def account_path(root: str, claims: dict, now: float | None = None) -> Path:
    if not root or not Path(root).is_absolute():
        raise ValueError('Account storage requires an absolute persistent-volume path.')
    if not isinstance(claims, dict):
        raise ValueError('Sign in with a provider that supplies valid identity claims.')
    issuer, subject = claims.get('iss'), claims.get('sub')
    if claims.get('is_logged_in') is not True or not all(
            isinstance(v, str) and v.strip() for v in (issuer, subject)):
        raise ValueError('Sign in with a provider that supplies issuer and subject identifiers.')
    try:
        if isinstance(claims.get('exp'), bool):
            raise ValueError('Invalid expiry')
        expires = float(claims['exp'])
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError('The sign-in session has no valid expiry. Sign in again.') from None
    current_time = time.time() if now is None else now
    if not math.isfinite(current_time) or not math.isfinite(expires) or expires <= current_time:
        raise ValueError('Your sign-in session expired. Sign in again.')
    identity = hashlib.sha256(json.dumps([issuer, subject]).encode()).hexdigest()
    storage = Path(root).resolve()
    expected = storage / identity / 'workspace.db'
    path = expected.resolve()
    if path != expected:
        raise ValueError('Account storage contains an unexpected redirected workspace path.')
    return path
