"""
main.py — Taxyn API Entry Point
================================
Wires all components together using dependency injection.
"""

import structlog
import asyncio
import uuid
import random
import io # Added for pypdf
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Response, APIRouter, Body, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
from typing import Optional, List, Union # Added List, Union for return type
from sqlalchemy import select, func, delete

# ── Core Components ────────────────────────────────────────
from agent.loop import AgentLoop
from agent.planner import Planner
from agent.context import Context, DocType, ProcessingStatus
from skills.factory import SkillFactory
from memory.stores import SQLRepository, InMemoryRepository, SchemaStore, CorrectionStore, AuditStore, DocumentStore, ProcessingJobStore, UserStore, User, StoreItem, DocumentBlob
from output.serializer import ResponseSerializer
from output.hitl_queue import HITLQueue
from observability.tracer import Tracer
from api.channels.rest_adapter import RestAdapter
from config.settings import settings
from auth.manager import SecurityManager
from auth.mailer import Mailer
from auth.rate_limiter import RateLimiter, RateLimitExceeded
from tools.splitter_tool import SplitterTool # Import the new splitter tool

# ── Logging setup ──────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)
processing_tasks: set[asyncio.Task] = set()

# ── Dependency Container ──────────────────────────────────
class Container:
    def __init__(self):
        self.repo = self._build_repository()

        self.user_store = UserStore(self.repo)
        self.schema_store = SchemaStore(self.repo)
        self.correction_store = CorrectionStore(self.repo)
        self.audit_store = AuditStore(self.repo)
        self.job_store = ProcessingJobStore(self.repo)
        self.document_store = DocumentStore(
            self.repo,
            storage_mode=settings.DOCUMENT_STORAGE_MODE,
            storage_path=settings.DOCUMENT_STORAGE_PATH,
        )

        self.serializer = ResponseSerializer()
        self.hitl_queue = HITLQueue(self.repo)
        self.tracer = Tracer(self.audit_store)
        self.rate_limiter = RateLimiter(self.repo)
        skill_factory = SkillFactory(correction_store=self.correction_store)
        planner = Planner(skill_factory, self.schema_store)
        self.agent_loop = AgentLoop(planner, self.serializer, self.hitl_queue, self.tracer)
        self.rest_adapter = RestAdapter(self.schema_store)
        self.splitter_tool = SplitterTool()

    def _build_repository(self):
        db_url = (settings.DATABASE_URL or "").strip()
        try:
            if db_url:
                if db_url.startswith("postgres://"):
                    db_url = "postgresql+asyncpg://" + db_url[len("postgres://"):]
                elif db_url.startswith("postgresql://"):
                    db_url = "postgresql+asyncpg://" + db_url[len("postgresql://"):]

                if db_url.startswith("postgresql+asyncpg://"):
                    parsed = urlparse(db_url)
                    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
                    if "sslmode" in query and "ssl" not in query:
                        query["ssl"] = query.pop("sslmode")
                    query.pop("channel_binding", None)
                    query.pop("gssencmode", None)
                    query.pop("target_session_attrs", None)
                    db_url = urlunparse(parsed._replace(query=urlencode(query)))
                return SQLRepository(db_url)
            return SQLRepository("sqlite+aiosqlite:///./taxyn.db")
        except Exception as e:
            logger.error("container.repository_init_failed", error=str(e))
            return InMemoryRepository()

container = Container()

PROFILE_EXTRA_FIELDS = (
    "contact_phone",
    "designation",
    "company_pan",
    "address_line1",
    "city",
    "state",
    "pincode",
)

ADMIN_EMAIL_SET = {email.strip().lower() for email in (settings.ADMIN_EMAILS or "").split(",") if email.strip()}


def _is_admin_user(user: User) -> bool:
    user_email = (getattr(user, "email", "") or "").lower()
    return bool(getattr(user, "is_admin", False)) or (user_email in ADMIN_EMAIL_SET)

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
    # Auto-promote configured admin emails to is_admin for existing users.
    if user.email and user.email.lower() in ADMIN_EMAIL_SET and not bool(getattr(user, "is_admin", False)):
        user.is_admin = True
        await container.user_store.create_user(user)
    return user

async def get_optional_user(token: Optional[str] = Depends(oauth2_scheme_optional)) -> Optional[User]:
    if not token:
        return None
    token_data = SecurityManager.decode_token(token)
    if not token_data:
        return None
    return await container.user_store.get_by_id(token_data.user_id)


async def get_user_from_query_token(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    token_data = SecurityManager.decode_token(token)
    if not token_data:
        return None
    return await container.user_store.get_by_id(token_data.user_id)


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if _is_admin_user(user):
        return user
    raise HTTPException(status_code=403, detail="Admin access required")


async def _get_profile_extra(user_id: str) -> dict:
    profile = await container.repo.get(f"user_profile:{user_id}")
    if isinstance(profile, dict):
        return profile
    return {}


def _db_profile_fields(user: User) -> dict:
    return {field: getattr(user, field, "") or "" for field in PROFILE_EXTRA_FIELDS}


def _extract_persisted_data(trace: dict) -> dict:
    if not isinstance(trace, dict):
        return {}
    candidates = [
        trace.get("extracted_data"),
        trace.get("partial_data"),
        (trace.get("result") or {}).get("extracted_data") if isinstance(trace.get("result"), dict) else None,
        (trace.get("response") or {}).get("extracted_data") if isinstance(trace.get("response"), dict) else None,
        (trace.get("metadata") or {}).get("extracted_data") if isinstance(trace.get("metadata"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return candidate
    for tool_result in trace.get("tool_results", []) if isinstance(trace.get("tool_results"), list) else []:
        if not isinstance(tool_result, dict):
            continue
        data = tool_result.get("data")
        if isinstance(data, dict):
            parser_fields = data.get("fields")
            if isinstance(parser_fields, dict) and parser_fields:
                return parser_fields
    return {}


def _request_actor(request: Request, user: Optional[User] = None, fallback: str = "anonymous") -> str:
    if user and getattr(user, "id", None):
        return user.id
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return fallback


async def _enforce_rate_limit(scope: str, actor: str, limit: int, window_seconds: int) -> None:
    try:
        await container.rate_limiter.check(scope, actor, limit=limit, window_seconds=window_seconds)
    except RateLimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))


async def _collect_runtime_metrics() -> dict[str, int | str]:
    pending_reviews = await container.hitl_queue.get_pending()
    processing_jobs = await container.repo.get_by_tag("processing_job") if hasattr(container.repo, "get_by_tag") else []
    document_meta = await container.repo.get_by_tag("document_meta") if hasattr(container.repo, "get_by_tag") else []
    feedback_items = await container.repo.get_by_tag("feedback") if hasattr(container.repo, "get_by_tag") else []

    queued_jobs = 0
    active_jobs = 0
    completed_jobs = 0
    failed_jobs = 0
    for item in processing_jobs:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if status == "queued":
            queued_jobs += 1
        elif status == "processing":
            active_jobs += 1
        elif status == "completed":
            completed_jobs += 1
        elif status == "failed":
            failed_jobs += 1

    open_feedback = sum(
        1 for item in feedback_items
        if isinstance(item, dict) and item.get("status", "open") != "resolved"
    )

    return {
        "storage_mode": settings.DOCUMENT_STORAGE_MODE,
        "async_processing": "1" if settings.ENABLE_ASYNC_PROCESSING else "0",
        "pending_reviews": len(pending_reviews),
        "queued_jobs": queued_jobs,
        "active_jobs": active_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "document_meta_records": len(document_meta),
        "open_feedback": open_feedback,
        "in_process_tasks": len(processing_tasks),
    }


async def _build_contexts(
    *,
    raw_bytes: bytes,
    filename: str,
    resolved_tenant_id: str,
    doc_type: DocType,
    request_id: str,
) -> list[Context]:
    if doc_type in [DocType.INVOICE, DocType.UNKNOWN]:
        split_documents = container.splitter_tool.split_document(raw_bytes, filename)
        if len(split_documents) > 1:
            contexts: list[Context] = []
            for i, split_doc in enumerate(split_documents):
                part_request_id = f"{request_id}-{i}"
                context = await container.rest_adapter.parse_request(
                    {
                        "file_bytes": split_doc["raw_bytes"],
                        "tenant_id": resolved_tenant_id,
                        "doc_type": doc_type.value,
                        "filename": split_doc["filename"],
                        "request_id": part_request_id,
                    }
                )
                contexts.append(context)
            return contexts

    context = await container.rest_adapter.parse_request(
        {
            "file_bytes": raw_bytes,
            "tenant_id": resolved_tenant_id,
            "doc_type": doc_type.value,
            "filename": filename,
            "request_id": request_id,
        }
    )
    return [context]


async def _process_contexts(contexts: list[Context]) -> Union[dict, List[dict]]:
    results = []
    for context in contexts:
        await container.document_store.save(
            context.request_id,
            context.raw_bytes,
            tenant_id=context.tenant_id,
            filename=context.filename,
        )
        processing_result = await container.agent_loop.run(context)
        results.append(processing_result)
    return results[0] if len(results) == 1 else results


async def _process_job(request_id: str, contexts: list[Context]) -> None:
    await container.job_store.update_job(
        request_id,
        {"status": "processing", "started_at": datetime.utcnow().isoformat()},
    )
    try:
        result = await _process_contexts(contexts)
        await container.job_store.update_job(
            request_id,
            {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "result": result,
            },
        )
    except Exception as e:
        logger.error("background_processing.failed", request_id=request_id, error=str(e), exc_info=True)
        await container.job_store.update_job(
            request_id,
            {
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat(),
                "error": str(e),
            },
        )


def _schedule_background_job(request_id: str, contexts: list[Context]) -> None:
    task = asyncio.create_task(_process_job(request_id, contexts))
    processing_tasks.add(task)
    task.add_done_callback(processing_tasks.discard)

# ── App lifecycle ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    if isinstance(container.repo, SQLRepository):
        await container.repo.init_db()
    yield

app = FastAPI(title="Taxyn API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── AUTH ROUTES ───────────────────────────────────────────
auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@auth_router.post("/signup/initiate")
async def initiate_signup(request: Request, email: str = Form(...)):
    await _enforce_rate_limit("signup_initiate", _request_actor(request, fallback=email.lower()), limit=5, window_seconds=600)
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
async def verify_signup(request: Request, email: str = Form(...), otp: str = Form(...), password: str = Form(...), full_name: str = Form(...)):
    await _enforce_rate_limit("signup_verify", _request_actor(request, fallback=email.lower()), limit=10, window_seconds=600)
    is_valid = await container.user_store.verify_otp(email, otp)
    if not is_valid: raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    new_user = User(
        id=str(uuid.uuid4()),
        email=email,
        full_name=full_name,
        hashed_password=SecurityManager.hash_password(password),
        is_admin=email.lower() in ADMIN_EMAIL_SET,
    )
    await container.user_store.create_user(new_user)
    return {"status": "success", "message": "Account verified and created"}

@auth_router.post("/login")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    await _enforce_rate_limit("login", _request_actor(request, fallback=form_data.username.lower()), limit=15, window_seconds=900)
    user = await container.user_store.get_by_email(form_data.username)
    if not user or not SecurityManager.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = SecurityManager.create_access_token(data={"sub": user.id, "email": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.post("/google")
async def google_login(request: Request, token: str = Form(...)):
    """
    Fetch user info from Google using Access Token and login/signup.
    """
    import httpx
    await _enforce_rate_limit("google_login", _request_actor(request), limit=15, window_seconds=900)
    
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
                hashed_password=None, # No password for Google users
                is_admin=email.lower() in ADMIN_EMAIL_SET,
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
    profile_extra = _db_profile_fields(user)
    # Backward compatibility for users whose profile extras are still in KV storage.
    if not any(profile_extra.values()):
        kv_profile_extra = await _get_profile_extra(user.id)
        for field in PROFILE_EXTRA_FIELDS:
            if kv_profile_extra.get(field):
                profile_extra[field] = kv_profile_extra[field]
    response = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "company_name": user.company_name,
        "gstin": user.gstin,
        "is_admin": _is_admin_user(user),
    }
    for field in PROFILE_EXTRA_FIELDS:
        response[field] = profile_extra.get(field, "")
    return response

@auth_router.put("/profile")
async def update_profile(
    full_name: Optional[str] = Form(None), 
    company_name: Optional[str] = Form(None), 
    gstin: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    designation: Optional[str] = Form(None),
    company_pan: Optional[str] = Form(None),
    address_line1: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    pincode: Optional[str] = Form(None),
    user: User = Depends(get_current_user)
):
    if full_name is not None:
        user.full_name = full_name
    if company_name is not None:
        user.company_name = company_name
    if gstin is not None:
        user.gstin = gstin

    incoming_profile = {
        "contact_phone": contact_phone,
        "designation": designation,
        "company_pan": company_pan,
        "address_line1": address_line1,
        "city": city,
        "state": state,
        "pincode": pincode,
    }
    for key, value in incoming_profile.items():
        if value is not None:
            setattr(user, key, value)

    await container.user_store.create_user(user) # merge update
    profile_extra = _db_profile_fields(user)

    return {
        "status": "success",
        "message": "Profile updated",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "company_name": user.company_name,
            "gstin": user.gstin,
            "is_admin": _is_admin_user(user),
            **profile_extra,
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

    extracted_data = _extract_persisted_data(trace)

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


@app.post("/api/v1/contact")
async def submit_contact_message(
    request: Request,
    subject: str = Form(...),
    message: str = Form(...),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    user: Optional[User] = Depends(get_optional_user),
):
    await _enforce_rate_limit("contact", _request_actor(request, user=user, fallback=(email or "").lower()), limit=10, window_seconds=3600)
    final_name = (name or (user.full_name if user else "") or "").strip()
    final_email = (email or (user.email if user else "") or "").strip()
    final_subject = subject.strip()
    final_message = message.strip()

    if not final_email:
        raise HTTPException(status_code=400, detail="Email is required")
    if not final_subject:
        raise HTTPException(status_code=400, detail="Subject is required")
    if not final_message:
        raise HTTPException(status_code=400, detail="Message is required")

    feedback_id = str(uuid.uuid4())
    feedback_payload = {
        "feedback_id": feedback_id,
        "user_id": user.id if user else "",
        "name": final_name or "Taxyn User",
        "email": final_email,
        "subject": final_subject,
        "message": final_message,
        "status": "open",
        "created_at": datetime.utcnow().isoformat(),
    }
    await container.repo.set(f"feedback:{feedback_id}", feedback_payload, tags="feedback")

    try:
        await Mailer.send_contact_message(
            sender_email=final_email,
            sender_name=final_name or "Taxyn User",
            subject=final_subject,
            message_text=final_message,
            user_id=user.id if user else "",
        )
    except Exception as e:
        logger.error("contact.submit_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to send message")

    return {"status": "success", "message": "Your message has been sent", "feedback_id": feedback_id}


admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _serialize_user_admin(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "company_name": user.company_name,
        "gstin": user.gstin,
        "contact_phone": getattr(user, "contact_phone", "") or "",
        "designation": getattr(user, "designation", "") or "",
        "company_pan": getattr(user, "company_pan", "") or "",
        "address_line1": getattr(user, "address_line1", "") or "",
        "city": getattr(user, "city", "") or "",
        "state": getattr(user, "state", "") or "",
        "pincode": getattr(user, "pincode", "") or "",
        "is_active": bool(getattr(user, "is_active", True)),
        "is_admin": _is_admin_user(user),
        "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
    }


@admin_router.get("/overview")
async def admin_overview(_: User = Depends(get_admin_user)):
    if not isinstance(container.repo, SQLRepository):
        raise HTTPException(status_code=500, detail="Admin panel requires SQL repository")

    async with container.repo.async_session() as session:
        total_users = await session.scalar(select(func.count()).select_from(User))
        active_users = await session.scalar(select(func.count()).select_from(User).where(User.is_active == True))
        total_documents = await session.scalar(select(func.count()).select_from(DocumentBlob))
        total_audits = await session.scalar(
            select(func.count()).select_from(StoreItem).where(StoreItem.key.like("audit:%"))
        )

    feedback_items = await container.repo.get_by_tag("feedback")
    open_feedback = sum(1 for item in feedback_items if isinstance(item, dict) and item.get("status", "open") != "resolved")

    return {
        "total_users": int(total_users or 0),
        "active_users": int(active_users or 0),
        "total_documents": int(total_documents or 0),
        "total_processed": int(total_audits or 0),
        "open_feedback": int(open_feedback),
    }


@admin_router.get("/users")
async def admin_list_users(_: User = Depends(get_admin_user)):
    if not isinstance(container.repo, SQLRepository):
        raise HTTPException(status_code=500, detail="Admin panel requires SQL repository")

    async with container.repo.async_session() as session:
        users = (await session.execute(select(User).order_by(User.created_at.desc()))).scalars().all()

        rows = []
        for user in users:
            processed = await session.scalar(
                select(func.count())
                .select_from(StoreItem)
                .where(StoreItem.key.like(f"audit:{user.id}:%"))
            )
            payload = _serialize_user_admin(user)
            payload["documents_processed"] = int(processed or 0)
            rows.append(payload)

    return rows


@admin_router.put("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    payload: dict = Body(default={}),
    admin_user: User = Depends(get_admin_user),
):
    allowed_fields = {
        "full_name",
        "company_name",
        "gstin",
        "contact_phone",
        "designation",
        "company_pan",
        "address_line1",
        "city",
        "state",
        "pincode",
        "is_active",
        "is_admin",
    }
    updates = {k: v for k, v in payload.items() if k in allowed_fields}

    if not isinstance(container.repo, SQLRepository):
        user = await container.user_store.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        for key, value in updates.items():
            setattr(user, key, value)
        if user.id == admin_user.id and updates.get("is_admin") is False:
            raise HTTPException(status_code=400, detail="You cannot remove your own admin access")
        await container.user_store.create_user(user)
        return {"status": "success", "user": _serialize_user_admin(user)}

    async with container.repo.async_session() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.id == admin_user.id and updates.get("is_admin") is False:
            raise HTTPException(status_code=400, detail="You cannot remove your own admin access")
        for key, value in updates.items():
            setattr(user, key, value)
        await session.commit()
        await session.refresh(user)
        return {"status": "success", "user": _serialize_user_admin(user)}


@admin_router.delete("/users/{user_id}")
async def admin_delete_user(user_id: str, admin_user: User = Depends(get_admin_user)):
    if user_id == admin_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own admin user")
    if not isinstance(container.repo, SQLRepository):
        raise HTTPException(status_code=500, detail="Admin panel requires SQL repository")

    async with container.repo.async_session() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        audit_items = (
            await session.execute(select(StoreItem).where(StoreItem.key.like(f"audit:{user_id}:%")))
        ).scalars().all()
        for item in audit_items:
            request_id = item.key.split(":")[-1]
            await session.execute(delete(DocumentBlob).where(DocumentBlob.request_id == request_id))
            await session.delete(item)

        await session.delete(user)
        await session.commit()

    return {"status": "success", "message": "User deleted"}


@admin_router.get("/users/{user_id}/history")
async def admin_user_history(user_id: str, _: User = Depends(get_admin_user)):
    if not isinstance(container.repo, SQLRepository):
        raise HTTPException(status_code=500, detail="Admin panel requires SQL repository")

    async with container.repo.async_session() as session:
        result = await session.execute(
            select(StoreItem)
            .where(StoreItem.key.like(f"audit:{user_id}:%"))
            .order_by(StoreItem.updated_at.desc())
            .limit(100)
        )
        rows = []
        for item in result.scalars().all():
            value = dict(item.value or {})
            value["request_id"] = value.get("request_id") or item.key.split(":")[-1]
            if "created_at" not in value and item.updated_at:
                value["created_at"] = item.updated_at.isoformat()
            rows.append(value)
    return rows


@admin_router.get("/users/{user_id}/history/{request_id}")
async def admin_user_history_item(user_id: str, request_id: str, _: User = Depends(get_admin_user)):
    trace = await container.audit_store.get(user_id, request_id)
    if not trace:
        raise HTTPException(status_code=404, detail="History item not found")

    extracted_data = _extract_persisted_data(trace)

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


@admin_router.get("/feedback")
async def admin_feedback(_: User = Depends(get_admin_user)):
    rows = await container.repo.get_by_tag("feedback")
    normalized = [item for item in rows if isinstance(item, dict)]
    normalized.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return normalized


@admin_router.put("/feedback/{feedback_id}/status")
async def admin_update_feedback_status(
    feedback_id: str,
    status: str = Form(...),
    _: User = Depends(get_admin_user),
):
    key = f"feedback:{feedback_id}"
    payload = await container.repo.get(key)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=404, detail="Feedback not found")
    payload["status"] = status
    payload["updated_at"] = datetime.utcnow().isoformat()
    await container.repo.set(key, payload, tags="feedback")
    return {"status": "success", "feedback": payload}

# ── DOMAIN ROUTES ─────────────────────────────────────────

@app.get("/health")
async def health():
    runtime_metrics = await _collect_runtime_metrics()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        **runtime_metrics,
    }


@app.get("/metrics")
async def metrics():
    runtime_metrics = await _collect_runtime_metrics()
    lines = [
        "# HELP taxyn_pending_reviews Current number of pending review items",
        "# TYPE taxyn_pending_reviews gauge",
        f"taxyn_pending_reviews {runtime_metrics['pending_reviews']}",
        "# HELP taxyn_jobs_queued Current number of queued processing jobs",
        "# TYPE taxyn_jobs_queued gauge",
        f"taxyn_jobs_queued {runtime_metrics['queued_jobs']}",
        "# HELP taxyn_jobs_processing Current number of active processing jobs",
        "# TYPE taxyn_jobs_processing gauge",
        f"taxyn_jobs_processing {runtime_metrics['active_jobs']}",
        "# HELP taxyn_jobs_completed Completed processing jobs recorded in the store",
        "# TYPE taxyn_jobs_completed gauge",
        f"taxyn_jobs_completed {runtime_metrics['completed_jobs']}",
        "# HELP taxyn_jobs_failed Failed processing jobs recorded in the store",
        "# TYPE taxyn_jobs_failed gauge",
        f"taxyn_jobs_failed {runtime_metrics['failed_jobs']}",
        "# HELP taxyn_document_meta_records Number of document metadata records tracked",
        "# TYPE taxyn_document_meta_records gauge",
        f"taxyn_document_meta_records {runtime_metrics['document_meta_records']}",
        "# HELP taxyn_feedback_open Open feedback items",
        "# TYPE taxyn_feedback_open gauge",
        f"taxyn_feedback_open {runtime_metrics['open_feedback']}",
        "# HELP taxyn_in_process_tasks In-process asyncio background tasks",
        "# TYPE taxyn_in_process_tasks gauge",
        f"taxyn_in_process_tasks {runtime_metrics['in_process_tasks']}",
        "# HELP taxyn_async_processing_enabled Whether async processing is enabled",
        "# TYPE taxyn_async_processing_enabled gauge",
        f"taxyn_async_processing_enabled {runtime_metrics['async_processing']}",
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

@app.post("/api/v1/extract")
async def extract_document(
    request: Request,
    file: UploadFile = File(...),
    tenant_id: Optional[str] = Form(default=None),
    doc_type: DocType = Form(default=DocType.UNKNOWN), # Changed default to DocType.UNKNOWN
    user: Optional[User] = Depends(get_optional_user),
    request_id: Optional[str] = Form(default=None), # Added request_id
    async_mode: bool = Form(default=False),
) -> Union[dict, List[dict]]: # Changed return type hint
    if not user and not settings.ALLOW_PUBLIC_DEMO:
        raise HTTPException(status_code=401, detail="Authentication required")
    await _enforce_rate_limit("extract", _request_actor(request, user=user), limit=20, window_seconds=900)
    
    # Read raw bytes from the uploaded file
    raw_bytes = await file.read()
    filename = (file.filename or "").lower()

    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    if not raw_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Invalid PDF file signature")
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty")
    if len(raw_bytes) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds max upload size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    # Use existing request_id if provided (for split documents) or generate a new one
    current_request_id = request_id or str(uuid.uuid4())
    resolved_tenant_id = user.id if user else (tenant_id or "public_demo")

    contexts = await _build_contexts(
        raw_bytes=raw_bytes,
        filename=filename,
        resolved_tenant_id=resolved_tenant_id,
        doc_type=doc_type,
        request_id=current_request_id,
    )

    if async_mode and settings.ENABLE_ASYNC_PROCESSING:
        await container.job_store.create_job(current_request_id, resolved_tenant_id, filename, doc_type.value)
        _schedule_background_job(current_request_id, contexts)
        return container.serializer.queued_response(current_request_id, filename, doc_type.value)

    return await _process_contexts(contexts)


@app.get("/api/v1/extract/{request_id}/status")
async def get_extract_status(request_id: str, user: Optional[User] = Depends(get_optional_user)):
    job = await container.job_store.get_job(request_id)
    if not isinstance(job, dict):
        tenant_hint = user.id if user else "public_demo"
        trace = await container.audit_store.get(tenant_hint, request_id)
        if not isinstance(trace, dict):
            raise HTTPException(status_code=404, detail="Processing request not found")
        return trace

    tenant_id = job.get("tenant_id")
    if tenant_id and tenant_id != "public_demo":
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not (_is_admin_user(user) or user.id == tenant_id):
            raise HTTPException(status_code=403, detail="Not authorized to access this request")
    return job

@app.get("/api/v1/document/{request_id}")
async def get_document(
    request_id: str,
    token: Optional[str] = Query(default=None),
    user: Optional[User] = Depends(get_optional_user),
):
    content = await container.document_store.get(request_id)
    if not content:
        raise HTTPException(status_code=404, detail="Not found")

    metadata = await container.document_store.get_meta(request_id) or {}
    effective_user = user or await get_user_from_query_token(token)
    tenant_id = metadata.get("tenant_id")
    if tenant_id and tenant_id != "public_demo":
        if not effective_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not (_is_admin_user(effective_user) or effective_user.id == tenant_id):
            raise HTTPException(status_code=403, detail="Not authorized to access this document")
    return Response(content=content, media_type="application/pdf")

@app.post("/api/v1/reconcile/upload-portal")
async def upload_portal_data(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    await _enforce_rate_limit("portal_upload", _request_actor(request, user=user), limit=10, window_seconds=900)
    if not file.filename.endswith((".xlsx", ".xls")): raise HTTPException(status_code=400, detail="Excel only")
    from tools.portal_parser import PortalExcelParser
    records = PortalExcelParser().parse(await file.read())
    if not records:
        raise HTTPException(status_code=400, detail="No portal records could be parsed from the uploaded file")
    await container.schema_store.set_schema(user.id, "portal_data", {"records": records})
    return {"status": "success", "records": len(records)}

@app.get("/api/v1/review/pending")
async def pending_reviews(user: Optional[User] = Depends(get_optional_user)):
    if not user and not settings.ALLOW_PUBLIC_DEMO:
        raise HTTPException(status_code=401, detail="Authentication required")
    pending = await container.hitl_queue.get_pending()
    if user and not _is_admin_user(user):
        pending = [item for item in pending if item.get("tenant_id") == user.id]
    elif not user:
        pending = [item for item in pending if item.get("tenant_id") == "public_demo"]
    return {"pending_count": len(pending), "items": pending}

@app.post("/api/v1/review/{request_id}/resolve")
async def resolve_review(
    request_id: str,
    corrected_data: dict = Body(default={}),
    user: Optional[User] = Depends(get_optional_user)
):
    if not user and not settings.ALLOW_PUBLIC_DEMO:
        raise HTTPException(status_code=401, detail="Authentication required")
    queue_items = await container.hitl_queue.get_pending()
    queued_item = next((item for item in queue_items if item.get("request_id") == request_id), None)
    if not queued_item:
        raise HTTPException(status_code=404, detail="Review item not found")

    tenant_id = queued_item.get("tenant_id") or (user.id if user else "public_demo")
    if tenant_id != "public_demo":
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not (_is_admin_user(user) or user.id == tenant_id):
            raise HTTPException(status_code=403, detail="Not authorized to resolve this review item")
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
    existing_trace = await container.audit_store.get(tenant_id, request_id)
    if isinstance(existing_trace, dict):
        resolved_data = corrected_data or partial_data
        existing_trace["status"] = ProcessingStatus.COMPLETED.value
        existing_trace["extracted_data"] = resolved_data
        existing_trace["confidence"] = 1.0
        existing_trace["overall_confidence"] = 1.0
        existing_trace["resolved_at"] = datetime.utcnow().isoformat()
        await container.audit_store.record(tenant_id, request_id, existing_trace)
    return {"status": "success", "message": "Review resolved"}

app.include_router(auth_router)
app.include_router(admin_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
