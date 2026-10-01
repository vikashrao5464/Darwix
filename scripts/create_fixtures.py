"""Generate small synthetic PDF fixtures; no external business data."""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def generate():
    path = ROOT / "data/raw/demo_policy.pdf"
    pages = [
        """Synthetic Demo Policy - Header
## Processing fees
The synthetic processing fee is 2 percent of the approved loan amount.
Any applicable taxes must be confirmed in a verified written offer.
## Consent
Obtain consent before collecting qualification details or recording a call.
If consent is declined, stop collecting details and offer human assistance.
Synthetic Demo Policy - Footer""",
        """Synthetic Demo Policy - Header
## Early repayment
Early repayment charges are not specified in the synthetic demo.
A human representative must confirm charges before the customer commits.
## Policy effective date
The synthetic policy effective date is 01/10/2026, version 1.0.
This is assessment content and is not a real lender or Darwix policy.
Synthetic Demo Policy - Footer""",
    ]
    with pymupdf.open() as document:
        for text in pages:
            page = document.new_page()
            page.insert_text((40, 50), text, fontsize=11)
        document.set_metadata({"title": "Synthetic Demo Policy", "author": "Assessment fixture generator"})
        document.save(path)
    print(f"Generated {path.relative_to(ROOT)} ({len(pages)} pages)")


if __name__ == "__main__":
    generate()
