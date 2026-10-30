from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.auth import require_permission, require_role
from app.db import get_db
from app.models import ImportIssue

router = APIRouter(prefix="/imports", tags=["imports"])


def _issues(db: Session):
    return db.query(ImportIssue).order_by(ImportIssue.id).all()


@router.post("/upload", response_model=schemas.ImportReportOut)
def upload(user=Depends(require_permission("import_run")), db: Session = Depends(get_db)):
    """Run the full CSV import pipeline against the data pack directory."""
    from engines.importer import run_import_all

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
