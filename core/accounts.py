"""Provider-authenticated workspace identities; never accept identity from form input."""
import hashlib
import json
import math
import os
from pathlib import Path
import time


def accounts_enabled() -> bool:
    return os.environ.get('FALCON_FINALYSIS_ACCOUNTS', '').lower() in {'1', 'true', 'yes', 'on'}


def account_path(root: str, claims: dict, now: float | None = None) -> Path:
    if not root or not Path(root).is_absolute():
        raise ValueError('Account storage requires an absolute persistent-volume path.')
    issuer, subject = claims.get('iss'), claims.get('sub')
    if claims.get('is_logged_in') is not True or not all(
            isinstance(v, str) and v.strip() for v in (issuer, subject)):
        raise ValueError('Sign in with a provider that supplies issuer and subject identifiers.')
    try:
        expires = float(claims['exp'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('The sign-in session has no valid expiry. Sign in again.') from None
    if not math.isfinite(expires) or expires <= (time.time() if now is None else now):
        raise ValueError('Your sign-in session expired. Sign in again.')
    identity = hashlib.sha256(json.dumps([issuer, subject]).encode()).hexdigest()
    return Path(root).resolve() / identity / 'workspace.db'
