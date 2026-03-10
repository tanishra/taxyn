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
> **Taxyn extracts structured data, validates Indian compliance rules, and flags anomalies — automatically.**

<br/>

</div>

---

## What It Does

Taxyn is an AI agent pipeline that processes Indian financial documents end-to-end:

1. **Extracts** raw text from PDF using Docling (tables preserved, 30x faster than OCR)
2. **Parses** structured fields using LLM + Instructor (typed Pydantic output, no JSON errors)
3. **Validates** Indian compliance rules deterministically — GST rates, GSTIN format, PAN format, date checks
4. **Scores** confidence per field — below 85% threshold → routed to human review
5. **Returns** clean structured JSON or queues for HITL review

---

## Architecture

```mermaid
graph LR
    A["REST Client"] --> G1
    B["Webhook"] --> G1

    subgraph GATEWAY["API GATEWAY"]
        G1["Auth + RateLimit + Router"]
    end

    subgraph AGENT["AGENT LAYER"]
        AL["AgentLoop\nStateless Orchestrator"]
        CO["ContextObject\nImmutable Data"]
        PL["Planner\nSkill Selector"]
    end

    subgraph SKILLS["SKILLS"]
        S1["InvoiceSkill"]
        S2["GSTSkill"]
        S3["BankSkill"]
        S4["TDSSkill"]
    end

    subgraph TOOLS["TOOLS"]
        T1["ExtractorTool\nDocling"]
        T2["ParserTool\nGPT-4o + Instructor"]
        T3["ValidatorTool\nDeterministic"]
        T4["ConfidenceScorerTool"]
    end

    subgraph MEMORY["STORAGE LAYER"]
        M1["SchemaStore"]
        M2["CorrectionStore"]
        M3["AuditStore"]
        M4[("SQL Persistence\nPostgres/SQLite")]
    end

    subgraph OUTPUT["OUTPUT"]
        O1["ResponseSerializer"]
        O2["HITLQueue\nHuman Review"]
        O3["Tracer"]
    end

    G1 --> AL
    AL --> CO --> PL

    PL --> S1
    PL --> S2
    PL --> S3
    PL --> S4

    S1 --> T1
    S2 --> T1
    S3 --> T1
    S4 --> T1

    T1 --> T2 --> T3 --> T4

    T4 -->|"confidence >= 0.85"| O1
    T4 -->|"confidence < 0.85"| O2

    MEMORY --> AL
    AL --> O3 --> M3
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Add your OPENAI_API_KEY and DATABASE_URL (optional)

# 3. Run Backend
python main.py

# 4. Run Frontend
cd frontend
npm install
npm run dev
```

---

## Key Features

- **Deterministic Validation:** 100% code-based verification for GSTIN, PAN, and Indian Tax rates. No AI "hallucinations."
- **Side-by-Side Correction:** Professional human review interface with source PDF and editable fields for low-confidence data.
- **Resilient Storage:** Cascading fallback system (PostgreSQL → SQLite → In-Memory) ensuring 100% uptime.
- **Data Flywheel:** Learns from every human correction, improving vendor-specific accuracy over time.
- **Table Preservation:** Powered by IBM Docling to ensure complex financial tables are extracted perfectly.

---

## Supported Documents

Taxyn is pre-configured to understand the specific layouts of Indian financial documents:

- **Invoices:** Handles B2B and B2C invoices with multi-line item extraction.
- **GST Returns:** Parses GSTR-1, GSTR-3B, and GSTR-2A/2B summaries.
- **Bank Statements:** Processes PDF ledgers from all major Indian banks.
- **TDS Certificates:** Extracts Form 16/16A data for tax reconciliation.

---

## Roadmap & Contributions

- **Smart Features:** Building auto-matching for GST data and fraud detection.
- **Easy Sync:** Connecting Taxyn directly to WhatsApp, Tally, and Zoho.
- **Wider Reach:** Adding support for regional languages and a mobile app.
- **Contribute:** PRs welcome! Help us make Taxyn better.

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:24243e,50:302b63,100:0f0c29&height=100&section=footer" width="100%"/>

</div>
