"""The read model behind the frontend's startup update check. The GitHub
call itself, and everything said about why the app makes one at all, lives
in app/updates.py.
"""

from fastapi import APIRouter

from app.models import VersionOut
from app.updates import get_version_status

router = APIRouter(prefix="/api/version", tags=["version"])


@router.get("", response_model=VersionOut)
def get_version():
    return get_version_status()
