<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f0c29,50:302b63,100:24243e&height=200&section=header&text=Taxyn&fontSize=80&fontColor=FFFFFF&fontAlignY=38&desc=AI%20Compliance%20Document%20Automation&descAlignY=60&descColor=ffffff&descSize=20" width="100%"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![Docling](https://img.shields.io/badge/IBM-Docling-054ADA?style=for-the-badge&logo=ibm&logoColor=white)](https://github.com/DS4SD/docling)
[![Instructor](https://img.shields.io/badge/Instructor-Structured_Output-E535AB?style=for-the-badge)](https://github.com/jxnl/instructor)
[![License](https://img.shields.io/badge/License-MIT-FF6B6B?style=for-the-badge)](LICENSE)

<br/>

> **Upload a PDF invoice, GST return, bank statement, or TDS certificate.**
> **Taxyn extracts structured data, validates Indian compliance rules, and reconciles against portal data — automatically.**

<br/>

</div>

---

## What It Does

Taxyn is an AI-powered platform that automates Indian financial document audits:

1. **Secure Identity:** Email verification (OTP) and Google Auth ensure data isolation per user.
2. **Deep Extraction:** Pulls multi-line tables from PDFs using IBM Docling (30x faster than traditional OCR).
3. **Smart Reconciliation:** Matches physical invoices against actual Government GSTR-2A portal Excel files to find missing tax credits.
4. **Deterministic Audit:** Hardcoded validation for GSTIN, PAN, and tax math to eliminate AI hallucinations.
5. **Continuous Learning:** Remembers every human correction, improving vendor-specific accuracy over time.

---

## Architecture

```mermaid
graph LR
    A["REST Client"] --> G1
    B["Google Auth"] --> G1

    subgraph GATEWAY["SECURE GATEWAY"]
        G1["JWT Auth + OTP Verification"]
    end

    subgraph AGENT["AGENT LAYER"]
        AL["AgentLoop\nUser-Isolated Orchestrator"]
        CO["ContextObject\nMetadata + Multi-Tenant ID"]
        PL["Planner\nSpecialist Selector"]
    end

    subgraph SKILLS["SKILLS"]
        S1["InvoiceSkill"]
        S2["GSTSkill"]
        S3["BankSkill"]
        S4["ReconciliationSkill"]
    end

    subgraph TOOLS["TOOLS"]
        T1["ExtractorTool\nDocling"]
        T2["ParserTool\nGPT-4o + Instructor"]
        T3["ValidatorTool\nDeterministic Compliance"]
        T4["PortalParser\nPandas Excel Engine"]
    end

    subgraph MEMORY["PERSISTENCE (Postgres)"]
        M1["UserStore\nAccounts + Profiles"]
        M2["AuditStore\nFull Document History"]
        M3["CorrectionStore\nVendor Learning Flywheel"]
        M4["DocumentStore\nSource PDF Persistence"]
    end

    G1 --> AL
    AL --> CO --> PL
    PL --> S1 & S2 & S3 & S4
    S1 & S2 & S3 & S4 --> T1 --> T2 --> T3
    S4 --> T4
    MEMORY --> AL
```

---

## Quick Start

```bash
# 1. Clone & Setup
git clone https://github.com/tanishra/taxyn.git
cd taxyn
pip install -r requirements.txt

# 2. Configure Environment
# Add DATABASE_URL, OPENAI_API_KEY, and SMTP settings for OTP to .env

# 3. Run Backend
python main.py

# 4. Choose your Interface:

# Option A: Modern SaaS Dashboard (Next.js)
cd frontend
npm install
npm run dev

# Option B: Simple Utility (Streamlit)
streamlit run app.py
```

---

## Key Features

- **GSTR-2A Portal Sync:** Upload actual government Excel files to find missing Input Tax Credit (ITC) instantly.
- **Side-by-Side Verification:** Professional UI to verify AI extractions against the source PDF in real-time.
- **Enterprise Persistence:** All documents, audits, and profiles are stored in high-performance PostgreSQL.
- **Vendor Memory:** System learns from your corrections once and applies them to all future documents from that vendor.
- **SaaS Identity:** Full account management with profile sections for Company Name and GSTIN.

---

## Supported Documents

Taxyn is specialized for the unique layouts of Indian compliance documentation:

- **Invoices:** B2B and B2C invoices with multi-line item table extraction.
- **Bank Statements:** Full ledger processing from all major Indian banks (SBI, HDFC, ICICI, etc.).
- **GST Returns:** Parses GSTR-1, GSTR-3B, and portal summaries for audit.
- **TDS Certificates:** Automated reconciliation of Form 16/16A data.

---

## Roadmap & Contributions

- **Bulk Ingestion:** Background batch processing for thousands of documents.
- **Direct ERP Sync:** One-click data push to Tally Prime and Zoho Books.
- **Risk Scoring:** Automated vendor fraud detection based on GST registration status.
- **Mobile App:** Rapid capture of physical bills via smartphone camera.
- **Contribute:** PRs welcome! Help us make Taxyn better.

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0f0c29&height=100&section=footer" width="100%"/>

</div>
