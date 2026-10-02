# Production improvements and unresolved requirements

The demonstrated deployment is one loopback FastAPI process, SQLite, Qdrant and React. It uses synthetic business content and local CPU speech models. The observations are prototype measurements, not a production SLA or native-language certification. The following changes are design work for production, not infrastructure already implemented here.

## Ten times the traffic

Separate call state from process memory before adding stateless API replicas. Replace SQLite with a transactional relational service and migrations, retain call revisions and idempotent business-action keys, and use consistent ownership/leases for active calls. SQLite and a process-local replay manager cannot coordinate many replicas.

Provision a managed Qdrant deployment with backups, capacity monitoring, metadata indexes and reviewed embedding versions. Batch large ingestion jobs; coordinate a single publisher and atomically roll out aliases. Do not rebuild the entire corpus per update at scale. Current `product`/`language` keyword indexes support strict-mode filtered retrieval; trained semantic embeddings and threshold recalibration need a measured rollout.

Local CPU ASR currently permits one active replay and a bounded queue. Scale a bounded speech-worker pool with reserved capacity, admission control and load shedding. Maintain a warm model per worker; set quotas per provider/tenant and monitor queue wait, worker memory, inference time, errors and provider rate limits. Introduce durable background jobs only where recovery of ingestion/call processing requires them. A broker or managed stream might then be justified; it is not necessary in this prototype.

WebSocket subscriptions currently live in one process. At higher traffic, use call ownership and a bounded event fan-out service, sequence numbers, resume tokens, heartbeats and backpressure. Partition delivery by call rather than broadcasting every event to every replica. Slow subscribers should reconnect from a persisted cursor. Browser acknowledgements measure observable delivery but include the return trip; monitor send time, queue time and client render time separately where clock synchronization permits it.

Collect traces for retrieval, provider calls, call transitions, audio chunks and event delivery. Export histograms with P50/P95/sample counts, alert on missing/late chunks, timeouts and undelivered events, and retain redacted audit IDs. Measure throughput and admission failure under a representative load before selecting instance counts or claiming a 10x capacity figure.

## Noisy audio and language quality

The interactive path already measures input energy, enables browser noise suppression, applies bounded gain and confirms spoken values. Q4 uses ASR VAD and rejects low decoder scores. Evaluate real microphone recordings, codecs and packet loss; prefer appropriately fitted headsets and supported PCM/telephony formats. Add calibrated VAD/end-pointing, cautiously tested denoising and overlapping context or token-level streaming to avoid cutting words at six-second boundaries. Avoid amplifying silence or treating model confidence as a correctness percentage.

Compare streaming providers on consented finance calls, regional accents and Taglish/Indonesian code switching. Retain errors and calibrate rejection thresholds by language, microphone and risk. The present Q3 probes reach intended behavior on 4/6 synthesized inputs; the two Filipino/Taglish errors require review rather than a claim of reliable native voice recognition. Review MMS pronunciation/prosody with native speakers, including English finance words, money and dates. Obtain appropriately licensed commercial voices before commercial use; the present MMS models assume noncommercial assessment use.

Q4 speaker labels come from registered synthetic recording annotations. Implement channel separation for real dual-channel calls or validate a diarization provider; mark uncertain speakers unknown. Do not use transcript wording as evidence of who spoke. Expand evaluation to negation, sarcasm, noisy speech, accents, interrupted disclosures, false alarms and missing opportunities. Suppress weak evidence and require confirmation before financial/high-risk actions.

## Reliability

Use bounded exponential backoff with jitter only for safe/idempotent provider requests. Honor rate limits and a total time budget; never retry a business action with a new action ID. Add circuit breakers and separately measured fallback providers where cost, data residency and failure independence justify them. Preserve explicit human-assistance fallbacks and source evidence gates when all providers fail.

Warm ASR workers need health checks, crash recovery and bounded queue ownership. The current prototype kills timed-out/cancelled workers and fails the replay safely; it does not recover an active replay across a backend restart. Production should persist progress and resume acknowledged chunks with sequence IDs while preventing duplicate actions/nudges. Keep call actions transactional and audit both model interpretation and deterministic validation without raw PII. Implement storage migrations, backup/restore tests and versioned schema/event contracts.

## Compliance and privacy

Obtain approved business policies, reviewed qualification rules and market-specific legal/compliance review. Synthetic amounts, dates and definitions are demonstrations only. Obtain separate informed conversation/recording consent, support revocation and disclosure requirements, and review each regional language/register with native speakers. Human calls and regional/noisy finance speech remain manual validation work.

The unauthenticated prototype must stay on loopback. Add authenticated role/tenant access, origin/CSRF policy, quotas, encryption in transit/at rest and encrypted secret management before external exposure. Regex redaction is a baseline: add locale-aware detection and source-metadata checks, minimize raw audio retention and implement documented deletion/access/export procedures. Make retention configurable and verify that backups/provider retention obey it. Regional data residency and provider subprocess/hosted processing require legal review.

Private customer audio, model caches and regional corpus downloads are ignored by Git. The public Batak corpus prohibits redistribution to another public repository; preserve its attribution and download privately with the provided setup script. Audit third-party model/dataset licenses. The previously exposed local provider key requires owner-side rotation if still valid; no replacement secret belongs in the repository.

Callbacks and escalation currently create mock requests. Integrate an approved CRM/contact workflow with authenticated coordinators, consented contact details, an audit trail and reliable status reporting. The current bot cannot verify payment, renew coverage, approve credit, waive a fee or contact a real person.
