import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import schemas
from app.auth import require_permission, require_role
from app.db import get_db
from app.models import ImportIssue

from app.config import CSV_SCHEMAS

router = APIRouter(prefix="/imports", tags=["imports"])


def _issues(db: Session):
    return db.query(ImportIssue).order_by(ImportIssue.id).all()


@router.post("/upload", response_model=schemas.ImportReportOut)
def upload(
    files: list[UploadFile] | None = None,
    user=Depends(require_permission("import_run")),
    db: Session = Depends(get_db),
):
    """Import CSV files uploaded by the user.

    With files: validates extensions against the CSV schema whitelist, writes them
    to a scratch dir and runs the pipeline on exactly that pack (missing files of
    the full pack are skipped and reported as issues). With no files: re-runs the
    pipeline against the server-side dataset/ directory.
    """
    from engines.importer import run_import_all

    if files:
        with tempfile.TemporaryDirectory() as tmp:
            for f in files:
                name = Path(f.filename or "").name
                if not name or name not in CSV_SCHEMAS:
                    raise HTTPException(
                        400, f"unsupported file {name or '(unnamed)'} — expected one of {sorted(CSV_SCHEMAS)}")
                with open(Path(tmp) / name, "wb") as out:
                    shutil.copyfileobj(f.file, out)
            report = run_import_all(db, actor=user.username, data_dir=Path(tmp))
    else:
        report = run_import_all(db, actor=user.username)
    return schemas.ImportReportOut(
        run_ok=True,
        files_loaded=report["files_loaded"],
        rows_imported=report["rows_imported"],
        issues_by_code=report["issues_by_code"],
        reconciliation=schemas.ReconciliationOut(**report["reconciliation"]),
    )


@router.get("/reconciliation", response_model=schemas.ReconciliationOut)
def reconciliation(db: Session = Depends(get_db)):
    from engines.importer import reconciliation as funnel

    return schemas.ReconciliationOut(**funnel(db))


@router.get("/issues", response_model=list[schemas.ImportIssueOut])
def issues(db: Session = Depends(get_db)):
    return [schemas.ImportIssueOut.model_validate(i) for i in _issues(db)]


@router.post("/reset", response_model=schemas.ImportReportOut)
def reset(user=Depends(require_role("director")), db: Session = Depends(get_db)):
    """Full rebuild of the demo state (seed.py logic, audited)."""
    import seed as seed_mod

    report = seed_mod.rebuild_demo(db, verbose=False)
    return schemas.ImportReportOut(
        run_ok=True,
        files_loaded=report["files_loaded"],
        rows_imported=report["rows_imported"],
        issues_by_code=report["issues_by_code"],
        reconciliation=schemas.ReconciliationOut(**report["reconciliation"]),
    )
