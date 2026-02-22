# reports_api.py
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from reports_db import get_reports, delete_reports, REPORT_TYPE_AUTO, REPORT_TYPE_MANUAL
from userdb import get_user_by_token, get_allowed_files

router = APIRouter(prefix="/reports", tags=["Reports"])

security_scheme = HTTPBearer(auto_error=False)

async def get_current_user_or_throw(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    """
    Extract and return authenticated user.
    Used for any authenticated user (e.g., report submission).
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication credentials required.")
    user = await get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid or expired token.")
    return user


async def is_admin_or_master(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    """
    Dependency: Ensures request is made by an admin user or valid master key.
    Raises 401 if unauthenticated, 403 if unauthorized.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication credentials required.")

    # Check if it's a valid admin user
    user = await get_user_by_token(credentials.credentials)
    if user and user[3] == "admin":
        return user

    # Otherwise, check master key
    import os
    import toml
    import bcrypt

    SECRETS_PATH = os.path.expanduser("~/secrets.toml")
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r") as f:
                secrets_data = toml.load(f)
            stored_hash = secrets_data.get("access_token_hash")
            if stored_hash:
                if bcrypt.checkpw(credentials.credentials.encode("utf-8"), stored_hash.encode("utf-8")):
                    # Master key valid — return synthetic admin identity
                    return ("system", "master-key-user", None, "admin")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal error verifying master key: {e}")

    raise HTTPException(status_code=403, detail="Admin or master key required.")


@router.get("/get/auto", summary="Retrieve auto-generated reports", response_model=dict)
async def fetch_auto_reports(admin_user=Depends(is_admin_or_master)):
    """
    Returns all automatically generated reports (e.g., when no answer was returned from RAG).
    Access restricted to admin or master key holder.
    """
    reports = get_reports(report_type=REPORT_TYPE_AUTO)
    return {
        "status": "success",
        "message": f"Retrieved {len(reports)} auto-generated report(s).",
        "reports": reports
    }


@router.get("/get/manual", summary="Retrieve manually submitted reports", response_model=dict)
async def fetch_manual_reports(admin_user=Depends(is_admin_or_master)):
    """
    Returns all reports submitted manually by users via feedback.
    Access restricted to admin or master key holder.
    """
    reports = get_reports(report_type=REPORT_TYPE_MANUAL)
    return {
        "status": "success",
        "message": f"Retrieved {len(reports)} manual report(s).",
        "reports": reports
    }


@router.post("/submit/manual", summary="Submit a manual report", response_model=dict)
async def submit_manual_report(
    issue: str = Body(..., embed=True, description="User's description of the issue or feedback."),
    user=Depends(get_current_user_or_throw)
):
    """
    Allows any authenticated user to submit a manual report.
    The system logs their username and permitted files at time of submission.
    """
    username = user[1]
    try:
        permitted_files = await get_allowed_files(username)
        if permitted_files is None:
            permitted_files = []

        from reports_db import submit_report
        submit_report(
            user=username,
            permitted_files=permitted_files,
            issue=issue,
            report_type=REPORT_TYPE_MANUAL
        )
        return {"status": "success", "message": "Report submitted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit report: {str(e)}")


@router.delete("/clear/auto", summary="Clear all auto-generated reports", response_model=dict)
async def clear_auto_reports(admin_user=Depends(is_admin_or_master)):
    """
    Deletes all auto-generated reports from the database.
    Requires admin privileges or master key.
    """
    try:
        deleted_count = delete_reports(report_type=REPORT_TYPE_AUTO)
        return {
            "status": "success",
            "message": f"Deleted {deleted_count} auto-generated report(s).",
            "deleted": deleted_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete auto reports: {str(e)}")


@router.delete("/clear/manual", summary="Clear all manual reports", response_model=dict)
async def clear_manual_reports(admin_user=Depends(is_admin_or_master)):
    """
    Deletes all manually submitted reports from the database.
    Requires admin privileges or master key.
    """
    try:
        deleted_count = delete_reports(report_type=REPORT_TYPE_MANUAL)
        return {
            "status": "success",
            "message": f"Deleted {deleted_count} manual report(s).",
            "deleted": deleted_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete manual reports: {str(e)}")