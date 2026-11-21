"""Developer-facing endpoints consumed with API keys.

* ``GET /api/v1/example`` – connectivity check for a key (``read``)
* ``/api/v1/records`` – a small JSON document store per account so every key
  permission (read / write / delete) maps to a real operation.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import Principal, require_access, require_api_key
from ..models import UserRecord
from ..responses import AppError, not_found, ok, validation
from ..schemas import RecordIn, RecordUpdate

router = APIRouter(prefix="/api/v1", tags=["developer-api"])
MAX_RECORDS = 1000


@router.get("/example")
def example(request: Request, principal: Principal = Depends(require_api_key("read"))):
    key = principal.api_key
    return ok({
        "message": "Hello from Ayaka Sync API. Your API key is valid.",
        "key": {"name": key.name, "prefix": key.key_prefix, "environment": key.environment,
                "permissions": sorted(key.permissions)},
        "account": {"username": principal.user.username},
        "request_id": request.state.request_id,
    }, "API key verified")


def _ser(r: UserRecord) -> dict:
    return {"id": str(r.id), "collection": r.collection, "data": r.data,
            "created_at": r.created_at, "updated_at": r.updated_at}


def _get(db: Session, principal: Principal, record_id: str) -> UserRecord:
    try:
        rid = uuid.UUID(record_id)
    except ValueError:
        raise not_found("Record not found")
    r = db.execute(select(UserRecord).where(UserRecord.id == rid, UserRecord.user_id == principal.user.id)
                   ).scalar_one_or_none()
    if r is None:
        raise not_found("Record not found")
    return r


@router.get("/records")
def list_records(collection: str | None = Query(None, pattern=r"^[a-z0-9_-]{1,64}$"),
                 page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
                 principal: Principal = Depends(require_access("read")), db: Session = Depends(get_db)):
    conds = [UserRecord.user_id == principal.user.id]
    if collection:
        conds.append(UserRecord.collection == collection)
    total = db.execute(select(func.count()).select_from(UserRecord).where(*conds)).scalar_one()
    rows = db.execute(select(UserRecord).where(*conds).order_by(UserRecord.created_at.desc())
                      .offset((page - 1) * per_page).limit(per_page)).scalars().all()
    return ok([_ser(r) for r in rows], meta={"page": page, "per_page": per_page, "total": total,
                                              "total_pages": max(1, math.ceil(total / per_page))})


@router.post("/records", status_code=201)
def create_record(payload: RecordIn, principal: Principal = Depends(require_access("write")),
                  db: Session = Depends(get_db)):
    count = db.execute(select(func.count()).select_from(UserRecord)
                       .where(UserRecord.user_id == principal.user.id)).scalar_one()
    if count >= MAX_RECORDS:
        raise validation(f"Record quota of {MAX_RECORDS} reached")
    r = UserRecord(user_id=principal.user.id, collection=payload.collection, data=payload.data)
    db.add(r)
    db.flush()
    db.refresh(r)
    db.commit()
    return ok(_ser(r), "Record created", status_code=201)


@router.get("/records/{record_id}")
def get_record(record_id: str, principal: Principal = Depends(require_access("read")),
               db: Session = Depends(get_db)):
    return ok(_ser(_get(db, principal, record_id)))


@router.patch("/records/{record_id}")
def update_record(record_id: str, payload: RecordUpdate, principal: Principal = Depends(require_access("write")),
                  db: Session = Depends(get_db)):
    r = _get(db, principal, record_id)
    r.data = payload.data
    r.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok(_ser(r), "Record updated")


@router.delete("/records/{record_id}")
def delete_record(record_id: str, principal: Principal = Depends(require_access("delete")),
                  db: Session = Depends(get_db)):
    r = _get(db, principal, record_id)
    db.delete(r)
    db.commit()
    return ok({"id": record_id}, "Record deleted")


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def unknown(path: str):
    raise AppError(404, "RESOURCE_NOT_FOUND", f"Unknown endpoint /api/v1/{path}")
