# AGENTS.md — Darwix AI Engineer Assessment

## 1. Objective

Build one coherent AI voice platform that satisfies all four assessment questions:

1. Knowledge-grounded voice agent
2. Production-ready knowledge base
3. Native-language voice bots for the Philippines and Indonesia
4. Real-time insights and nudges from call audio

The implementation must favor:
- working end-to-end behavior
- grounded answers over hallucination
- traceable retrieval
- explicit fallbacks
- measurable latency
- reproducible tests
- simple architecture that can be explained clearly

Do not optimize for visual polish before the core workflow works.

---

## 2. Chosen Product Scenarios

### Q1 + Q2
Use case: **Business-loan lead qualification**

The voice agent should:
- greet and obtain consent to continue
- collect qualification fields
- answer FAQs using the Q2 knowledge base
- handle objections using retrieved business content
- detect conflicting/incomplete user information
- refuse to invent unsupported information
- support human escalation
- optionally create a mock CRM lead / callback request

### Q3 — Philippines
Use case: **Life-insurance premium / renewal reminder**

Support:
- English
- Filipino/Tagalog
- natural Taglish

The bot should preserve the customer's current language/register where possible.

### Q3 — Indonesia
Use case: **Consumer-finance installment reminder**

Support:
- formal Bahasa Indonesia
- colloquial Bahasa Indonesia
- finance-related English loanwords
- at least one documented regional-accent test case

### Q4
Use a recorded call from Q1 or Q3 and replay it at real-time speed in chunks.

Detect at minimum:
- missed opportunity
- compliance/risky statement
- rising frustration
- payment difficulty / callback need

Generate short live nudges while the audio is still being replayed.

---

## 3. Recommended Stack

### Backend
- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy or SQLModel
- SQLite for prototype relational state
- Qdrant for vector retrieval
- WebSocket endpoint for Q4 live events

### AI
Use provider adapters so APIs can be swapped.

Required abstractions:
- `EmbeddingProvider`
- `LLMProvider`
- `ASRProvider`
- `TTSProvider`
- `VoiceProvider`

Do not scatter vendor SDK calls throughout business logic.

### Frontend
- React + Vite
- minimal CSS/Tailwind if already convenient
- two screens are enough:
  - `/call` — browser/call access or provider link
  - `/live` — transcript + signals + nudges + latency

### Parsing
- PyMuPDF for PDFs
- BeautifulSoup for HTML
- standard Python for JSON/CSV/Markdown

### Testing
- pytest
- deterministic fixture documents
- JSON fixtures for expected retrieval/signal results

---

## 4. Repository Structure

```text
darwix-ai-assessment/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ config.py
│  │  ├─ api/
│  │  │  ├─ health.py
│  │  │  ├─ knowledge.py
│  │  │  ├─ leads.py
│  │  │  ├─ callbacks.py
│  │  │  ├─ voice_tools.py
│  │  │  └─ realtime.py
│  │  ├─ knowledge/
│  │  │  ├─ extract.py
│  │  │  ├─ clean.py
│  │  │  ├─ pii.py
│  │  │  ├─ dedupe.py
│  │  │  ├─ normalize.py
│  │  │  ├─ chunk.py
│  │  │  ├─ embed.py
│  │  │  ├─ index.py
│  │  │  ├─ retrieve.py
│  │  │  └─ citations.py
│  │  ├─ voice/
│  │  │  ├─ qualification.py
│  │  │  ├─ conversation_rules.py
│  │  │  ├─ tools.py
│  │  │  └─ escalation.py
│  │  ├─ localization/
│  │  │  ├─ philippines.py
│  │  │  ├─ indonesia.py
│  │  │  └─ language_state.py
│  │  ├─ realtime/
│  │  │  ├─ replay.py
│  │  │  ├─ transcription.py
│  │  │  ├─ signals.py
│  │  │  ├─ nudges.py
│  │  │  ├─ suppression.py
│  │  │  ├─ latency.py
│  │  │  └─ events.py
│  │  ├─ providers/
│  │  │  ├─ llm.py
│  │  │  ├─ embeddings.py
│  │  │  ├─ asr.py
│  │  │  ├─ tts.py
│  │  │  └─ voice.py
│  │  ├─ db/
│  │  │  ├─ models.py
│  │  │  ├─ session.py
│  │  │  └─ migrations.py
│  │  └─ schemas/
│  │     ├─ knowledge.py
│  │     ├─ lead.py
│  │     ├─ retrieval.py
│  │     ├─ realtime.py
│  │     └─ evaluation.py
│  ├─ tests/
│  └─ requirements.txt
│
├─ frontend/
│  ├─ src/
│  │  ├─ pages/
│  │  │  ├─ CallDemo.jsx
│  │  │  └─ LiveInsights.jsx
│  │  ├─ components/
│  │  │  ├─ TranscriptPanel.jsx
│  │  │  ├─ SignalList.jsx
│  │  │  ├─ NudgeCard.jsx
│  │  │  └─ LatencyPanel.jsx
│  │  └─ lib/
│  │     └─ websocket.js
│  └─ package.json
│
├─ data/
│  ├─ raw/
│  ├─ normalized/
│  ├─ fixtures/
│  └─ audio/
│
├─ evaluations/
│  ├─ retrieval/
│  ├─ voice/
│  ├─ localization/
│  └─ realtime/
│
├─ scripts/
│  ├─ ingest.py
│  ├─ evaluate_retrieval.py
│  ├─ replay_audio.py
│  └─ summarize_latency.py
│
├─ docs/
│  ├─ architecture.md
│  ├─ knowledge-base.md
│  ├─ q1-results.md
│  ├─ q2-retrieval-evaluation.md
│  ├─ q3-localization-report.md
│  ├─ q4-latency-report.md
│  └─ production-improvements.md
│
├─ .env.example
├─ docker-compose.yml
├─ README.md
├─ AGENTS.md
└─ BUILD_STEPS.md
```

---

## 5. Engineering Rules for Codex

### General
- Keep the implementation small and explainable.
- Do not introduce Kafka, Kubernetes, Redis, Celery, or microservices unless a hard requirement emerges.
- Keep Q1–Q4 in one repository and one backend.
- Prefer explicit modules over clever abstractions.
- Never commit credentials or actual customer information.
- Every external provider must be configured with environment variables.

### Error handling
Every external AI/provider call must:
- have a timeout
- catch provider errors
- return a safe fallback
- log enough context for debugging without logging secrets or PII

### Grounding
The LLM must not answer business-policy questions from general model knowledge.

For policy/FAQ/qualification questions:
1. retrieve relevant KB records
2. check retrieval confidence / evidence availability
3. answer only from retrieved context
4. attach source metadata internally
5. if evidence is insufficient, say the information is unavailable and offer escalation

### Prompts
System prompts should contain:
- role
- conversation rules
- safety/fallback behavior
- tool-use instructions
- tone

Do **not** hardcode the entire knowledge base into a system prompt.

### Data
If no official business dataset was supplied:
- use clearly labelled synthetic demo documents
- never represent synthetic rules as Darwix policies
- document this in README

### PII
At minimum detect/redact:
- phone numbers
- email addresses
- government-ID-like numeric patterns
- account/card-like long numeric sequences

Store the redacted form for retrieval unless raw retention is explicitly required.

### Citations
Every KB chunk must retain:
- source filename/URL
- source type
- page/section where available
- document version
- chunk ID

### Retrieval
Baseline:
- vector similarity retrieval
- metadata filtering
- top-k results

Optional only after baseline works:
- reranking
- hybrid lexical + vector retrieval

### Voice flow
Conversation state should be deterministic where possible:
- qualification fields
- eligibility state
- callback request
- escalation request
- current language/register

Use the LLM for natural-language interpretation and response wording, not as the only state machine.

### Q4 real-time constraint
Do not implement Q4 as upload → full transcription → analysis.

Allowed prototype:
- replay a recording at real-time speed
- stream fixed-duration chunks
- transcribe continuously
- evaluate rolling transcript
- emit nudges before replay ends

### Q4 nudge quality
A nudge must be:
- short
- actionable
- based on evidence from recent transcript
- confidence-scored
- deduplicated

Minimum suppression logic:
- confidence threshold
- cooldown per signal type
- duplicate fingerprint
- expiry
- priority

### Metrics
Never write "low latency" without measured numbers.

Capture at least:
- ASR latency
- signal extraction latency
- LLM/nudge latency
- delivery latency
- end-to-end latency

Report:
- P50
- P95
- sample count

### Testing
Test failure paths deliberately:
- unknown FAQ
- retrieval miss
- conflicting qualification value
- human escalation
- provider timeout
- noisy/ambiguous Q4 segment
- repeated identical signal
- language switch

---

## 6. Core Data Schemas

### KnowledgeRecord

```json
{
  "record_id": "kb_business_loan_eligibility_001",
  "document_id": "business_loan_policy",
  "title": "Minimum Business Vintage",
  "content": "Applicants must have operated the business for at least two years.",
  "category": "qualification",
  "product": "business_loan",
  "source_type": "pdf",
  "source": "business_loan_policy.pdf",
  "source_page": 4,
  "source_section": "Eligibility",
  "version": "1.0",
  "contains_pii": false,
  "language": "en",
  "checksum": "sha256:...",
  "created_at": "ISO-8601"
}
```

### RetrievalResult

```json
{
  "query": "How old must my business be?",
  "records": [
    {
      "record_id": "kb_business_loan_eligibility_001",
      "score": 0.89,
      "content": "...",
      "source": "business_loan_policy.pdf",
      "source_page": 4
    }
  ],
  "grounded": true
}
```

### Lead

```json
{
  "lead_id": "lead_001",
  "name": "Demo User",
  "phone": "[REDACTED]",
  "requested_amount": 1000000,
  "business_type": "retail",
  "business_age_months": 48,
  "annual_turnover": 5000000,
  "existing_loan": true,
  "city": "Demo City",
  "qualification_status": "qualified",
  "qualification_reasons": [],
  "callback_requested": true
}
```

### Signal

```json
{
  "signal_id": "sig_001",
  "call_id": "call_001",
  "type": "payment_difficulty",
  "confidence": 0.91,
  "evidence": "The EMI may be difficult for me.",
  "speaker": "customer",
  "detected_at_ms": 43000,
  "priority": "high"
}
```

### Nudge

```json
{
  "nudge_id": "nudge_001",
  "signal_id": "sig_001",
  "type": "payment_support",
  "text": "Ask about an approved repayment or callback option.",
  "priority": "high",
  "confidence": 0.91,
  "created_at_ms": 44120,
  "expires_at_ms": 64120,
  "suppression_key": "payment_support"
}
```

### LatencySample

```json
{
  "call_id": "call_001",
  "chunk_id": 12,
  "audio_received_ms": 42000,
  "asr_done_ms": 42720,
  "signal_done_ms": 43010,
  "llm_done_ms": 43950,
  "delivered_ms": 44120,
  "asr_latency_ms": 720,
  "signal_latency_ms": 290,
  "llm_latency_ms": 940,
  "delivery_latency_ms": 170,
  "end_to_end_latency_ms": 2120
}
```

---

## 7. API Contract

### Health
`GET /health`

Response:
```json
{"status":"ok"}
```

### Ingest documents
`POST /api/knowledge/ingest`

Input:
```json
{
  "paths": ["data/raw/business_loan_policy.pdf"],
  "version": "1.0"
}
```

### Retrieve
`POST /api/knowledge/search`

Input:
```json
{
  "query": "What documents are required?",
  "product": "business_loan",
  "top_k": 5
}
```

### Grounded answer
`POST /api/knowledge/answer`

Input:
```json
{
  "query": "Can a one-year-old business apply?",
  "product": "business_loan"
}
```

Response:
```json
{
  "answer": "...",
  "grounded": true,
  "citations": [
    {
      "record_id": "...",
      "source": "...",
      "page": 4
    }
  ]
}
```

### Qualification update
`POST /api/voice/qualification`

Input:
```json
{
  "call_id": "call_001",
  "field": "business_age_months",
  "value": 12
}
```

### Create mock lead
`POST /api/leads`

### Request callback
`POST /api/callbacks`

### Human escalation
`POST /api/escalations`

### Real-time WebSocket
`WS /ws/calls/{call_id}`

Server events:
```json
{"type":"transcript","payload":{...}}
{"type":"signal","payload":{...}}
{"type":"nudge","payload":{...}}
{"type":"latency","payload":{...}}
```

---

## 8. Definition of Done

The project is not done because endpoints exist.

It is done when all of these are demonstrable:

- Q1 bot can converse and use the Q2 KB
- unsupported questions produce a safe non-hallucinated fallback
- at least three Q1 test calls exist with transcripts/results
- Q2 has traceable chunks with source metadata
- at least five documented retrieval evaluations exist
- Philippines prototype demonstrates English/Filipino/Taglish behavior
- Indonesia prototype demonstrates formal/colloquial behavior, finance terminology and a regional-accent test
- two recorded calls per Q3 market exist
- Q4 emits a nudge while audio is still streaming/replaying
- Q4 includes compliance and missed-opportunity examples
- repeated/low-confidence nudges are suppressed
- P50/P95 latency is calculated from real samples
- noisy/ambiguous input is tested
- README contains reproducible setup
- `.env.example` exists
- no credentials or customer data are committed
- limitations and production improvements are explicitly documented
