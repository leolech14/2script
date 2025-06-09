# Golden-Guided Parsing for Itaú Statements

## Overview

This approach leverages the *golden* (reference) CSV to guide and explain the parsing of Itaú statement text files.  
It is designed for maximum accuracy, explainability, and rapid adaptation to new layouts or statement formats.

---

## Workflow

1. **Golden CSV Analysis**
    - Load the golden CSV.
    - For each posting, extract key fields: date, amount, description, type, etc.

2. **Text File Analysis**
    - Load the raw TXT (or PDF-extracted lines).
    - Clean and preprocess lines.

3. **Matching Engine**
    - For each golden posting, find the best matching candidate in the text file using:
        - Date, amount, description, and fuzzy matching.
    - Record which text lines correspond to each golden posting.

4. **Rule Extraction / Pattern Learning**
    - For each matched pair, analyze:
        - How the posting appears in the text (structure, neighbors, etc).
    - Build a set of “golden rules” for explainability and future automation.

5. **CSV Skeleton & Metadata Enrichment**
    - Create a CSV skeleton aligned with the golden.
    - Extract and fill in additional metadata (category, merchant city, FX rate, etc) from the text context.

6. **Output**
    - Write the completed CSV, matching the golden in structure and content.
    - Optionally, export the learned rules for future use.

---

## Benefits

- **Maximum accuracy:** Directly aligns output with the golden reference.
- **Explainability:** Each posting’s mapping is transparent and auditable.
- **Adaptability:** Easily handles new layouts—just provide a new golden.
- **Training data:** The learned rules can be used for future automation or ML.

---

## Usage

```bash
python golden_guided_parser.py --golden golden.csv --txt statement.txt --out output.csv
```

- `--golden`: Path to the golden/reference CSV.
- `--txt`: Path to the raw statement TXT file.
- `--out`: Output CSV file (aligned with golden).

---

## Integration

- **Shared utilities** are in `parser_utils.py`.
- **Testing**: Use `parser_comparison.py` and `test_runner.py` to validate output.
- **Documentation**: Update this file as new rules or edge cases are discovered.

---

## Extending

- Add new enrichment logic to extract more metadata from the text.
- Export and review the learned rules for continuous improvement.
- Integrate with ML models for automated pattern recognition if desired.

---

## Example Output

- `output.csv`: Fully aligned with the golden, with all available metadata.
- `output.rules.json`: JSON file with learned pattern rules for each posting.

---

## Authors & Contact

- Developed by the Itaú parsing project team.
- For questions or contributions, contact the maintainers.

---