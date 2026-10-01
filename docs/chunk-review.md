# Manual chunk inspection

Inspected twelve actual generated records on 2026-10-01 from `data/normalized/records.jsonl` after the synthetic rebuild. The corpus had 23 records. Chunk IDs are document/location/version based and were unchanged by the embedding-adapter revision.

| Record suffix / source | Section | Manual observation |
|---|---|---|
| `1dd7bbc67dec4a56` / demo_duplicate.md | Annual turnover near duplicate | INR 1200000 and the extra wording remain; similarity flagged, no automatic rule removal. |
| `c8bf37db0fb9f9ce` / demo_eligibility.md | Annual turnover | Turnover amount and verification condition remain; version 1.0 retained. |
| `99b00bf046cc677f` / demo_faq.html | Application timeline | Five working days remains with the non-guarantee condition; navigation removed. |
| `422efadb0ffc9646` / demo_product.json | Repayment term | 12–36 months and written-offer condition retained together. |
| `447138df9c769967` / demo_policy.pdf | Early repayment | Page 2 retained; no invented charge and human confirmation remains. |
| `b5d69eec33214169` / demo_rates.txt | Guaranteed approval | Prohibition retained; preliminary qualification is distinguished from final approval. |
| `78e1c24f23fcba7a` / demo_eligibility.md | Synthetic eligibility example | Synthetic/not-Darwix disclosure retained; low-information disclosure remains traceable. |
| `c057e1db4cf15ef8` / demo_faq.html | Required documents | Registration, identity, bank statements and turnover evidence retained; secure-channel warning remains. |
| `3c7bd80d110b4eda` / demo_eligibility.md | Minimum business age | Both 24-month minimum and 12-month counterexample remain; no numeric redaction. |
| `15b96a466a82adc8` / demo_support.csv | Contact redaction example | Email and phone replaced with typed placeholders; `contains_pii: true`; source/section retained. |
| `1d4a44c67a60c2ea` / demo_policy.pdf | Processing fees | Page 1 retained; 2 percent and tax-confirmation condition remain; repeated PDF boilerplate removed. |
| `8bf64b66c142d8fe` / demo_policy.pdf | Policy effective date | Page 2 retained; date normalized to 2026-10-01 and document version stays 1.0. |

All inspected records included a full chunk ID, document ID, category, product, source/type, available page/section, version, language, checksum, creation timestamp and synthetic status. These small sections were kept separate; no unrelated policy sections were merged. This review covers synthetic fixtures only. Approved real sources need a new manual extraction, redaction and policy review.
