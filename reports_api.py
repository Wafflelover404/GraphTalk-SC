from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
from reports_db import get_reports
from userdb import get_user_by_token

router = APIRouter()
security_scheme = HTTPBearer(auto_error=False)

# Helper to check admin or master key
def is_admin_or_master(user, credentials: HTTPAuthorizationCredentials):
    if user and user[3] == "admin":
        return True
    return False


# Responds with reports submitted automatically when access is denied 
@router.get("/reports/get/auto", tags=["reports"])
async def fetch_auto_reports(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials.")
    user = await get_user_by_token(credentials.credentials)
    if not is_admin_or_master(user, credentials):
        raise HTTPException(status_code=403, detail="Admin or master key required.")
    reports = get_reports(report_type='auto')
    return {"reports": reports}

# Responds with reports submitted by users manually
@router.get("/reports/get/manual", tags=["reports"])
async def fetch_manual_reports(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials.")
    user = await get_user_by_token(credentials.credentials)
    if not is_admin_or_master(user, credentials):
        raise HTTPException(status_code=403, detail="Admin or master key required.")
    reports = get_reports(report_type='manual')
    return {"reports": reports}

from fastapi import Body
@router.post("/reports/submit/manual", tags=["reports"])
async def submit_report_endpoint(
    issue: str = Body(..., embed=True, description="User's report/problem description."),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
):
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials.")
    user = await get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=403, detail="Valid user required to submit reports.")
    try:
        from reports_db import submit_report, REPORT_TYPE_MANUAL
        from userdb import get_allowed_files
        permitted_files = await get_allowed_files(user[1])
        if permitted_files is None:
            permitted_files = []
        submit_report(
            user=user[1],
            permitted_files=permitted_files,
            issue=issue,
            report_type=REPORT_TYPE_MANUAL
        )
        return {"status": "Report submitted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit report: {e}")