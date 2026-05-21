from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(
    prefix="/qf-proxy/content/adfn87dssf/data", tags=["qf-proxy-content"]
)

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def _safe_resolve(requested_path: str) -> Path:
    target = (STATIC_DIR / requested_path).resolve()
    if not str(target).startswith(str(STATIC_DIR.resolve())):
        raise HTTPException(status_code=404, detail="File not found")
    return target


@router.get("")
@router.get("/")
async def get_root_content():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists() and index_file.is_file():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="File not found")


@router.get("/{path:path}")
async def get_static_content(path: str):
    target = _safe_resolve(path)
    if target.is_dir():
        index_file = target / "index.html"
        if index_file.exists() and index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="File not found")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)
