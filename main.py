"""
main.py — Taxyn API Entry Point
================================
Wires all components together using dependency injection.
No hardcoding — all dependencies passed explicitly.

This is your config-driven wiring layer.
Change a component → swap it here. Nothing else.
"""

import structlog
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# ── Core Components ────────────────────────────────────────
from agent.loop import AgentLoop
from agent.planner import Planner
from skills.factory import SkillFactory
from memory.stores import SQLRepository, InMemoryRepository, SchemaStore, CorrectionStore, AuditStore, DocumentStore
from output.serializer import ResponseSerializer
from output.hitl_queue import HITLQueue
from observability.tracer import Tracer
from api.channels.rest_adapter import RestAdapter
from config.settings import settings

# ── Logging setup ──────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger(__name__)


# ── Dependency Container (simple, no framework) ───────────
class Container:
    """
    Manual dependency injection container.
    No magic, no hidden wiring — fully explicit.
    """

    def __init__(self):
        # ── Memory layer (Smart Fallback) ──────────────────────
        from memory.stores import SQLRepository, InMemoryRepository
        
        # Priority 1: PostgreSQL
        if settings.DATABASE_URL and settings.DATABASE_URL.startswith("postgresql"):
            try:
                logger.info("db.trying_postgres")
                self.repo = SQLRepository(settings.DATABASE_URL)
            except Exception as e:
                logger.error("db.postgres_failed", error=str(e))
                self.repo = None

        # Priority 2: SQLite (if Postgres not configured or failed)
        if not getattr(self, 'repo', None):
            try:
                sqlite_url = "sqlite+aiosqlite:///./taxyn.db"
                logger.info("db.falling_back_to_sqlite", url=sqlite_url)
                self.repo = SQLRepository(sqlite_url)
            except Exception as e:
                logger.error("db.sqlite_failed", error=str(e))
                self.repo = InMemoryRepository()
                logger.warning("db.falling_back_to_memory")

        self.schema_store = SchemaStore(self.repo)
        self.correction_store = CorrectionStore(self.repo)
        self.audit_store = AuditStore(self.repo)
        self.document_store = DocumentStore(self.repo)

        # ── Output layer ──────────────────────────────
        self.serializer = ResponseSerializer()
        self.hitl_queue = HITLQueue()
        self.tracer = Tracer(self.audit_store)

        # ── Agent layer ───────────────────────────────
        skill_factory = SkillFactory()
        planner = Planner(skill_factory, self.schema_store)
        self.agent_loop = AgentLoop(
            planner=planner,
            serializer=self.serializer,
            hitl_queue=self.hitl_queue,
            tracer=self.tracer,
        )

        # ── Channel adapters ──────────────────────────
        self.rest_adapter = RestAdapter(self.schema_store)


# Global container instance
container = Container()


# ── App lifecycle ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("taxyn.startup", env=settings.APP_ENV)
    
    # Initialize Database Tables
    from memory.stores import SQLRepository, Base
    if isinstance(container.repo, SQLRepository):
        # In development, we ensure the schema is fresh to match our models
        async with container.repo.engine.begin() as conn:
            # Force refresh: Drop existing tables and recreate with new columns
            await conn.run_sync(Base.metadata.drop_all) 
            await conn.run_sync(Base.metadata.create_all)
        logger.info("sql_db.ready")
        
    yield
    logger.info("taxyn.shutdown")


# ── FastAPI App ────────────────────────────────────────────
app = FastAPI(
    title="Taxyn API",
    description="AI Compliance Document Automation for Indian CA Firms",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "taxyn", "env": settings.APP_ENV}


@app.post("/api/v1/extract")
async def extract_document(
    file: UploadFile = File(..., description="PDF document to process"),
    tenant_id: str = Form(..., description="Your tenant/firm ID"),
    doc_type: str = Form(default="unknown", description="invoice | gst_return | bank_statement | tds_certificate"),
):
    """
    Main extraction endpoint.
    """
    if not file.filename or not file.filename.endswith((".pdf", ".PDF")):
        raise HTTPException(status_code=400, detail="Only PDF files are supported currently.")

    # ── Adapter: HTTP request → Context ───────────────────
    context = await container.rest_adapter.parse_request({
        "file": file,
        "tenant_id": tenant_id,
        "doc_type": doc_type,
    })

    # ── PERSISTENCE: Store raw bytes for rendering ───────
    await container.document_store.save(context.request_id, context.raw_bytes)

    # ── AgentLoop: Context → Result ───────────────────────
    result = await container.agent_loop.run(context)

    return result


@app.get("/api/v1/document/{request_id}")
async def get_document(request_id: str):
    """Serve the original PDF for side-by-side review."""
    content = await container.document_store.get(request_id)
    if not content:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(content=content, media_type="application/pdf")


@app.get("/api/v1/review/pending")
async def get_pending_reviews():
    """Get all documents pending human review."""
    items = await container.hitl_queue.get_pending()
    return {"pending_count": len(items), "items": items}


@app.post("/api/v1/review/{request_id}/resolve")
async def resolve_review(request_id: str, corrected_data: dict):
    """
    Submit human corrections.
    Saves to CorrectionStore with vendor memory support.
    """
    # 1. Fetch original audit to get vendor name and tenant id
    # In production, HITLQueue might store this directly
    trace = await container.audit_store.get("demo_user", request_id)
    vendor_name = "unknown"
    tenant_id = "demo_user"
    
    if trace:
        vendor_name = trace.get("extracted_data", {}).get("vendor_name", "unknown")
        tenant_id = trace.get("tenant_id", "demo_user")

    # 2. Save corrections to memory for learning
    for field, value in corrected_data.items():
        original = trace.get("extracted_data", {}).get(field) if trace else None
        await container.correction_store.save_correction(
            tenant_id=tenant_id,
            request_id=request_id,
            vendor_name=vendor_name,
            field=field,
            original=original,
            corrected=value
        )

    resolved = await container.hitl_queue.resolve(request_id, corrected_data)
    if not resolved:
        raise HTTPException(status_code=404, detail="Review item not found.")
    return {"status": "resolved", "request_id": request_id}


@app.get("/api/v1/audit/{tenant_id}/{request_id}")
async def get_audit_trace(tenant_id: str, request_id: str):
    """Get full pipeline trace."""
    trace = await container.audit_store.get(tenant_id, request_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Audit record not found.")
    return trace


# ── Run ────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.APP_PORT, reload=True)
