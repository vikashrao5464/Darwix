# Q2 retrieval evaluation

Generated from actual Qdrant retrieval and answer output; synthetic demo data only.

Embedding adapter: `hash-v2:512:ad48db4a2266`. Answer adapter: `extractive`. Evidence threshold: 0.3. Samples: 11.

Verdicts check source, section, category, rank, required facts, citations and the fallback. This small fixture set is not a general accuracy benchmark.

| Case / query | Expected topic | Top source / section | Score | Grounded answer | Verdict | Explanation |
|---|---|---|---|---|---|---|
| product_amount: What are the loan amount limits? | product | data/raw/demo_product.json / Loan amount limits | 0.7620 | True | correct | Expected source/section ranked first, supplied required facts and was cited. |
| policy_fees: What is the processing fee? | policy | data/raw/demo_policy.pdf / Processing fees | 0.5345 | True | correct | Expected source/section ranked first, supplied required facts and was cited. |
| qualification_age: What is the minimum business age? | qualification | data/raw/demo_eligibility.md / Minimum business age | 0.7878 | True | correct | Expected source/section ranked first, supplied required facts and was cited. |
| faq_documents: What documents are required? | faq | data/raw/demo_faq.html / Required documents | 0.7385 | True | correct | Expected source/section ranked first, supplied required facts and was cited. |
| objection_documents: I do not want to share documents. | objection | data/raw/demo_objections.md / Do not want to share documents | 0.7500 | True | correct | Expected source/section ranked first, supplied required facts and was cited. |
| unknown_faq: What is the cashback promotion for lunar tourism? | unsupported | data/raw/demo_objections.md / Do not want to share documents | 0.1443 | False | correct | Insufficient evidence produced a fallback. |
| unsupported_language: What is the processing fee? | unsupported | No results | — | False | correct | Insufficient evidence produced a fallback. |
| unsupported_product: What is the processing fee? | unsupported | data/raw/ph_reminder_en.json / policy | 0.0000 | False | correct | Insufficient evidence produced a fallback. |
| short_paraphrase: How old must my business be? | qualification | data/raw/demo_eligibility.md / Minimum business age | 0.5571 | True | correct | Expected source/section ranked first, supplied required facts and was cited. |
| semantic_paraphrase: What paperwork should I bring to apply? | faq | data/raw/demo_eligibility.md / Existing borrowing | 0.4082 | False | incorrect | Expected source/section was absent from top-k. |
| mixed_unsupported_topic: What is the processing fee for lunar tourism? | unsupported | data/raw/demo_policy.pdf / Processing fees | 0.4725 | False | correct | Insufficient evidence produced a fallback. |

Actual verdict counts: `{'correct': 10, 'incorrect': 1}`.

Full returned records, source/page/version, scores and answers: [results.json](../evaluations/retrieval/results.json).

Hash embeddings are a lexical vector baseline and can miss short or semantic paraphrases. Hosted adapters were not exercised with live credentials unless the report provider fields say otherwise.
