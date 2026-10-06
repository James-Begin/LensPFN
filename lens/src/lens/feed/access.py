"""Verify and store TabPFN access outside the Lens project."""

import os
from pathlib import Path
import re
import tempfile


def _verify(token):
    from tabpfn.browser_auth import verify_token
    from tabpfn.settings import settings

    return verify_token(token, settings.tabpfn.auth_api_url)


def configure_token(token, path: Path):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_.=-]{20,4096}", token):
        raise ValueError("Paste a complete TabPFN access token without spaces.")
    valid = _verify(token)
    if valid is False:
        raise ValueError(
            "Prior Labs did not accept this token. Check the token in your account and try again."
        )
    if valid is not True:
        raise ValueError(
            "Prior Labs could not verify the token right now. Try again or start with similarity ranking."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, prefix=".lens-auth-", delete=False
        ) as file:
            temporary = Path(file.name)
            os.chmod(temporary, 0o600)
            file.write(token)
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    os.environ["TABPFN_TOKEN"] = token
