# ClauseGuard — AI Insurance Fraud & Policy Loophole Detection

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063.svg)](https://docs.pydantic.dev/)
[![Tests](https://img.shields.io/badge/tests-15%20passed-brightgreen.svg)]()

ClauseGuard is a modular, explainable, AI-assisted insurance fraud and policy loophole detection platform inspired by modern document intelligence and risk-analysis systems.

The platform assists claims adjusters, forensic auditors, and underwriting teams by detecting:
- **Fraud Indicators**: Suspicious date sequencing, inflated amounts, invoice tampering, and duplicate billings.
- **Policy Violations**: Claims made against explicit exclusions, unfulfilled waiting periods, and breached sub-limits.
- **Document Discrepancies**: Missing mandatory documentation, mismatched patient/claimant details, and inconsistent line items.
- **Ambiguities & Loopholes**: Vague policy clauses prone to conflicting interpretations or abusive exploitation.
- **Human-in-the-Loop Reviews**: Explainable reasoning traces with cited policy clauses and verifiable evidence snippets.

---

## Progressive Roadmap

ClauseGuard is developed across progressive, testable levels:

- [x] **Level 1: Core Foundation, Domain Data Models & API Skeleton**
  - Modular project architecture (`backend`, `storage`, `tests`)
  - Type-safe environment & settings management (`pydantic-settings`, `.env`)
  - Structured domain data models (`Policy`, `PolicyClause`, `Claim`, `ClaimDocument`, `DiscrepancyFinding`, `AnalysisReport`, `AuditLog`)
  - SQLite persistence layer with SQLAlchemy 2.0 ORM & automated migrations
  - Pydantic v2 validation schemas for requests, responses, and constraints
  - FastAPI foundational REST API (`/health`, `/system/status`, `/policies`, `/claims`)
  - Full automated Pytest suite (15 unit & integration tests)
- [ ] **Level 2: Document Ingestion, PDF Processing & Multi-Engine OCR Pipeline**
  - PyMuPDF and pdfplumber document parsing for native PDF policies & forms
  - Tesseract OCR + Pillow preprocessing for scanned invoices and photo evidence
  - SHA-256 document hashing for tamper detection and duplicate prevention
- [ ] **Level 3: Vector Embeddings, Semantic Search & Policy Clause Extraction**
  - Policy clause segmentation and semantic classification
  - ChromaDB local vector store integration
  - Hybrid lexical & semantic retrieval for relevant policy clauses
- [ ] **Level 4: Rule-Based Discrepancy & Cross-Document Verification Engine**
  - Deterministic validation: incident date vs filing date, effective dates, sub-limit caps
  - Cross-document validation: medical invoice line items vs claim form totals
  - Automated finding generation with severity scoring
- [ ] **Level 5: LangGraph Multi-Agent Orchestration & Gemini LLM Reasoning Engine**
  - Multi-agent state machine (Intake Agent, Policy Agent, Verification Agent, Fraud Specialist Agent, Synthesis Agent)
  - Configurable Gemini LLM provider interface with offline mock fallback
  - Transparent agent trace logging and explainable rationale generation
- [ ] **Level 6: Interactive Streamlit Auditor Dashboard & Explainability UI**
  - Policy clause explorer & loophole visualizer
  - Claim inspection workspace with side-by-side evidence viewer
  - Audit trail viewer and interactive human review verification
- [ ] **Level 7: End-to-End Integration, Dockerization & Production Verification**
  - Docker & Docker Compose orchestration
  - End-to-end integration testing and synthetic claim datasets

---

## Directory Structure

```text
fraudlens/
│
├── .env.example                # Example environment variables
├── .env                        # Local development environment configuration
├── .gitignore                  # Git ignore rules
├── requirements.txt            # Project dependencies
├── pytest.ini                  # Pytest configuration
├── README.md                   # Documentation
│
├── backend/
│   ├── __init__.py             # Package init & version (v0.1.0)
│   ├── main.py                 # FastAPI application entrypoint & lifespan
│   │
│   ├── core/
│   │   ├── config.py           # Pydantic BaseSettings & directory management
│   │   ├── database.py         # SQLAlchemy engine, session maker, base model
│   │   └── logging_config.py   # Colored structured console & file logging
│   │
│   ├── models/                 # SQLAlchemy 2.0 ORM domain entities
│   │   ├── enums.py            # Status, ClauseType, FindingType, Severity enums
│   │   ├── policy.py           # Policy and PolicyClause models
│   │   ├── claim.py            # Claim and ClaimDocument models
│   │   ├── finding.py          # DiscrepancyFinding model
│   │   └── report.py           # AnalysisReport and AuditLog models
│   │
│   ├── schemas/                # Pydantic v2 validation and transfer models
│   │   ├── common.py           # BaseSchema, PaginatedResponse, MessageResponse
│   │   ├── policy.py           # PolicyCreate, PolicyUpdate, PolicyResponse
│   │   ├── claim.py            # ClaimCreate, ClaimUpdate, ClaimResponse
│   │   ├── finding.py          # FindingCreate, FindingResponse, AnalysisReport
│   │   └── system.py           # HealthCheckResponse, SystemStatusResponse
│   │
│   ├── crud/                   # Database CRUD operations
│   │   ├── policy.py           # Policy & clause database queries
│   │   └── claim.py            # Claim, document & finding database queries
│   │
│   └── api/
│       └── v1/
│           ├── router.py       # Aggregator for v1 API routes
│           └── endpoints/
│               ├── system.py   # /health and /system/status deep inspection
│               ├── policies.py # Policy lifecycle REST routes
│               └── claims.py   # Claim lifecycle REST routes
│
├── storage/                    # Local file and database storage
│   ├── uploads/                # Document upload directory
│   ├── chroma_db/              # Vector database storage
│   └── clauseguard.db          # SQLite structured database
│
└── tests/                      # Automated Pytest suite
    ├── conftest.py             # In-memory SQLite session fixture & TestClient
    ├── test_config.py          # Settings and environment tests
    ├── test_database_models.py # ORM models, relations, and cascade tests
    ├── test_schemas.py         # Pydantic schema validation tests
    ├── test_system_api.py      # System and health API integration tests
    └── test_crud_and_endpoints.py # Policy & Claim REST lifecycle tests
```

---

## Getting Started

### 1. Prerequisites
- Python 3.11 or 3.12
- Git

### 2. Environment Setup
Create a virtual environment and install the dependencies:
```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Automated Tests
Execute the comprehensive test suite:
```bash
pytest -v
```

### 4. Launch the Backend API
Start the FastAPI development server:
```bash
python -m uvicorn backend.main:app --reload --port 8000
```

Once running, access:
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **Deep System Status**: [http://localhost:8000/api/v1/system/status](http://localhost:8000/api/v1/system/status)
