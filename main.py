"""
main.py — Taxyn API Entry Point
================================
Wires all components together using dependency injection.
"""

import structlog
import uuid
import random
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Response, APIRouter, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
from typing import Optional

# ── Core Components ────────────────────────────────────────
from agent.loop import AgentLoop
from agent.planner import Planner
from agent.context import Context, DocType
from skills.factory import SkillFactory
from memory.stores import SQLRepository, InMemoryRepository, SchemaStore, CorrectionStore, AuditStore, DocumentStore, UserStore, User
from output.serializer import ResponseSerializer
from output.hitl_queue import HITLQueue
from observability.tracer import Tracer
from api.channels.rest_adapter import RestAdapter
from config.settings import settings
from auth.manager import SecurityManager
from auth.mailer import Mailer

# ── Logging setup ──────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)

# ── Dependency Container ──────────────────────────────────
class Container:
    def __init__(self):
        if settings.DATABASE_URL and settings.DATABASE_URL.startswith("postgresql"):
            self.repo = SQLRepository(settings.DATABASE_URL)
        else:
            self.repo = SQLRepository("sqlite+aiosqlite:///./taxyn.db")

        self.user_store = UserStore(self.repo)
        self.schema_store = SchemaStore(self.repo)
        self.correction_store = CorrectionStore(self.repo)
        self.audit_store = AuditStore(self.repo)
        self.document_store = DocumentStore(self.repo)

        self.serializer = ResponseSerializer()
        self.hitl_queue = HITLQueue()
        self.tracer = Tracer(self.audit_store)
        skill_factory = SkillFactory()
        planner = Planner(skill_factory, self.schema_store)
        self.agent_loop = AgentLoop(planner, self.serializer, self.hitl_queue, self.tracer)
        self.rest_adapter = RestAdapter(self.schema_store)

container = Container()

# ── Auth Dependency ──────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    token_data = SecurityManager.decode_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    user = await container.user_store.get_by_id(token_data.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_optional_user(token: Optional[str] = Depends(oauth2_scheme_optional)) -> Optional[User]:
    if not token:
        return None
    token_data = SecurityManager.decode_token(token)
    if not token_data:
        return None
    return await container.user_store.get_by_id(token_data.user_id)

# ── App lifecycle ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    if isinstance(container.repo, SQLRepository):
        await container.repo.init_db()
    yield

app = FastAPI(title="Taxyn API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── AUTH ROUTES ───────────────────────────────────────────
auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@auth_router.post("/signup/initiate")
async def initiate_signup(email: str = Form(...)):
    existing = await container.user_store.get_by_email(email)
    if existing: raise HTTPException(status_code=400, detail="Email already registered")
    
    otp = str(random.randint(100000, 999999))
    await container.user_store.initiate_otp(email, otp)
    
    try:
        await Mailer.send_otp(email, otp)
    except Exception as e:
        logger.error("signup.email_failed", error=str(e))
        # For development, if email fails, we return the OTP in logs
        logger.info("DEV_MODE_OTP", email=email, otp=otp)
    
    return {"status": "success", "message": "OTP sent to email"}

@auth_router.post("/signup/verify")
async def verify_signup(email: str = Form(...), otp: str = Form(...), password: str = Form(...), full_name: str = Form(...)):
    is_valid = await container.user_store.verify_otp(email, otp)
    if not is_valid: raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    new_user = User(
        id=str(uuid.uuid4()),
        email=email,
        full_name=full_name,
        hashed_password=SecurityManager.hash_password(password)
    )
    await container.user_store.create_user(new_user)
    return {"status": "success", "message": "Account verified and created"}

@auth_router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await container.user_store.get_by_email(form_data.username)
    if not user or not SecurityManager.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = SecurityManager.create_access_token(data={"sub": user.id, "email": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.post("/google")
async def google_login(token: str = Form(...)):
    """
    Fetch user info from Google using Access Token and login/signup.
    """
    import httpx
    
    try:
        # 1. Use the Access Token to fetch user profile from Google
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code != 200:
                logger.error("google_auth.request_failed", status=response.status_code)
                raise HTTPException(status_code=400, detail="Failed to fetch Google user info")
            
            idinfo = response.json()
        
        email = idinfo['email']
        full_name = idinfo.get('name', 'Google User')

        # Check if user exists
        user = await container.user_store.get_by_email(email)
        
        if not user:
            # Create new user for first-time Google login
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                full_name=full_name,
                hashed_password=None # No password for Google users
            )
            await container.user_store.create_user(user)
            logger.info("google_auth.new_user_created", email=email)

        # Create Taxyn JWT
        access_token = SecurityManager.create_access_token(data={"sub": user.id, "email": user.email})
        return {"access_token": access_token, "token_type": "bearer"}

    except Exception as e:
        logger.error("google_auth.failed", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid Google Token")

@auth_router.get("/me")
async def get_profile(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "company_name": user.company_name, "gstin": user.gstin}

@auth_router.put("/profile")
async def update_profile(
    full_name: Optional[str] = Form(None), 
    company_name: Optional[str] = Form(None), 
    gstin: Optional[str] = Form(None),
    user: User = Depends(get_current_user)
):
    if full_name is not None:
        user.full_name = full_name
    if company_name is not None:
        user.company_name = company_name
    if gstin is not None:
        user.gstin = gstin
    
    await container.user_store.create_user(user) # merge update
    return {
        "status": "success",
        "message": "Profile updated",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "company_name": user.company_name,
            "gstin": user.gstin,
        },
    }

@auth_router.get("/history")
async def get_history(user: User = Depends(get_current_user)):
    return await container.audit_store.get_history(user.id)

@auth_router.get("/history/{request_id}")
async def get_history_item(request_id: str, user: User = Depends(get_current_user)):
    trace = await container.audit_store.get(user.id, request_id)
    if not trace:
        raise HTTPException(status_code=404, detail="History item not found")

    # Backward-compatible result extraction from stored trace
    extracted_data = trace.get("extracted_data") or {}
    if not extracted_data:
        for tool_result in trace.get("tool_results", []):
            if tool_result.get("tool") == "parser_tool":
                parser_fields = tool_result.get("data", {}).get("fields", {})
                if isinstance(parser_fields, dict):
                    extracted_data = parser_fields
                break
    
    # Backfill for older traces that did not persist extracted_data/tool payloads.
    if not extracted_data:
        try:
            content = await container.document_store.get(request_id)
            if content:
                doc_type_raw = str(trace.get("doc_type", "unknown")).replace("DocType.", "").lower()
                doc_type = DocType(doc_type_raw) if doc_type_raw in DocType._value2member_map_ else DocType.UNKNOWN
                schema = await container.schema_store.get_schema(user.id, doc_type_raw)

                replay_context = Context(
                    request_id=request_id,
                    tenant_id=user.id,
                    doc_type=doc_type,
                    raw_bytes=content,
                    filename=trace.get("filename", "document.pdf"),
                    extraction_schema=schema,
                )
                skill = await container.agent_loop._planner.plan(replay_context)
                await skill.run(replay_context)
                extracted_data = replay_context.extracted_data or {}
        except Exception as e:
            logger.error("history_item.backfill_failed", request_id=request_id, error=str(e))

    return {
        "request_id": trace.get("request_id", request_id),
        "filename": trace.get("filename", "document.pdf"),
        "doc_type": str(trace.get("doc_type", "unknown")).replace("DocType.", "").lower(),
        "status": trace.get("status", "completed"),
        "confidence": trace.get("confidence", trace.get("overall_confidence", 0.0)),
        "created_at": trace.get("created_at"),
        "compliance_flags": trace.get("compliance_flags", []),
        "extracted_data": extracted_data,
    }

# ── DOMAIN ROUTES ─────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}

@app.post("/api/v1/extract")
async def extract_document(
    file: UploadFile = File(...),
    tenant_id: Optional[str] = Form(default=None),
    doc_type: str = Form(default="unknown"),
    user: Optional[User] = Depends(get_optional_user)
):
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    resolved_tenant_id = user.id if user else (tenant_id or "public_demo")
    context = await container.rest_adapter.parse_request({"file": file, "tenant_id": resolved_tenant_id, "doc_type": doc_type})
    await container.document_store.save(context.request_id, context.raw_bytes)
    return await container.agent_loop.run(context)

@app.get("/api/v1/document/{request_id}")
async def get_document(request_id: str, user: Optional[User] = Depends(get_optional_user)):
    content = await container.document_store.get(request_id)
    if not content: raise HTTPException(status_code=404, detail="Not found")
    return Response(content=content, media_type="application/pdf")

@app.post("/api/v1/reconcile/upload-portal")
async def upload_portal_data(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    if not file.filename.endswith((".xlsx", ".xls")): raise HTTPException(status_code=400, detail="Excel only")
    from tools.portal_parser import PortalExcelParser
    records = PortalExcelParser().parse(await file.read())
    await container.schema_store.save_schema(user.id, "portal_data", {"records": records})
    return {"status": "success", "records": len(records)}

@app.get("/api/v1/review/pending")
async def pending_reviews():
    pending = await container.hitl_queue.get_pending()
    return {"pending_count": len(pending), "items": pending}

@app.post("/api/v1/review/{request_id}/resolve")
async def resolve_review(
    request_id: str,
    corrected_data: dict = Body(default={}),
    user: Optional[User] = Depends(get_optional_user)
):
    queue_items = await container.hitl_queue.get_pending()
    queued_item = next((item for item in queue_items if item.get("request_id") == request_id), None)
    if not queued_item:
        raise HTTPException(status_code=404, detail="Review item not found")

    tenant_id = queued_item.get("tenant_id") or (user.id if user else "public_demo")
    vendor_name = str(corrected_data.get("vendor_name", "unknown"))
    partial_data = queued_item.get("partial_data", {})
    for field, corrected_value in corrected_data.items():
        original_value = partial_data.get(field)
        if corrected_value != original_value:
            await container.correction_store.save_correction(
                tenant_id=tenant_id,
                request_id=request_id,
                vendor_name=vendor_name,
                field=field,
                original=original_value,
                corrected=corrected_value,
            )

    await container.hitl_queue.resolve(request_id, corrected_data)
    return {"status": "success", "message": "Review resolved"}

app.include_router(auth_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
