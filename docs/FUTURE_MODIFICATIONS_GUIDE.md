# 🛠️ Guide: Making Future Modifications & Integrations in the Itaú Parser Repository

This guide explains **how to safely extend, refactor, or integrate new logic** into the Itaú PDF/TXT → CSV parsing system, ensuring compatibility with golden CSVs, robust test coverage, and maintainability.

---

## 1. 📦 **Repository Structure Overview**

```
repo-root/
 ├─ script.py                  # Main parser (single-file, golden-compatible)
 ├─ config/
 │   ├─ regexes.yml            # Regex patterns for parsing
 │   └─ categories.yml         # Category mapping and keywords
 ├─ tests/
 │   ├─ test_golden.py         # Golden file integration tests
 │   └─ ...                    # Unit tests for each block/parser
 ├─ docs/
 │   └─ FUTURE_MODIFICATIONS_GUIDE.md
 ├─ golden/                    # Golden reference CSVs for regression
 └─ ...
```

---

## 2. 🧩 **Adding or Modifying Parsing Logic**

### **A. Block Parsers**

- **Each parsing “block”** (FX, Payment, Domestic, IOF, etc.) should be a function that:
  - Accepts lines (and context if needed)
  - Returns a `Transaction` with **all SCHEMA fields** filled (or empty)
- **To add a new block:**
  1. Write a function (e.g., `parse_new_block(lines, idx)`) in `script.py` or a new module.
  2. Insert it in the main parsing loop, before the fallback/domestic parser.
  3. Ensure it returns a `Transaction` with all fields (see SCHEMA in `script.py`).

### **B. Regexes and Categories**

- **Edit `config/regexes.yml` and `config/categories.yml`** to add new patterns or categories.
- **Reload config** by restarting the parser (or implement hot-reload if needed).
- **Validate YAML**: Always check for syntax errors and required keys.

---

## 3. 🗃️ **Updating the SCHEMA**

- **SCHEMA is defined in `script.py`** as a superset of all fields found in golden CSVs.
- **When adding a new field:**
  1. Add it to the `SCHEMA` list.
  2. Update all block parsers to fill (or leave empty) the new field.
  3. Update `Transaction.to_csv_row()` to ensure the field is always present in output.
  4. Update golden CSVs and tests if needed.

---

## 4. 🧪 **Testing and Validation**

- **Unit tests**: Add/modify tests in `tests/` for any new logic or parser.
- **Golden tests**: Place new golden PDFs and their expected CSVs in `golden/`.
- **Run all tests** before merging:
  ```bash
  pytest
  ```
- **CI**: Ensure GitHub Actions or your CI pipeline runs all tests and golden comparisons.

---

## 5. 🔄 **Integrating with Other Scripts/Modules**

- **To call the parser from another script:**
  ```python
  from script import parse_statement
  rows = parse_statement(Path("statement.pdf"))
  ```
- **For batch processing**: Loop over files and call `parse_statement` for each.
- **For web/API integration**: Wrap `parse_statement` in a FastAPI or Flask endpoint.

---

## 6. 📝 **Best Practices for Future Modifications**

- **Always output all SCHEMA fields** (even if empty) for every transaction.
- **Never change field names** without updating golden CSVs and all tests.
- **Log unmatched lines** for future training (add a CLI flag if needed).
- **Document any new block parser** or config field in `docs/`.
- **Keep config in YAML** for easy tuning by non-developers.
- **Prefer pure functions** for block parsers—easier to test and maintain.
- **Update this guide** if you introduce new architectural patterns.

---

## 7. 🚦 **Checklist for Safe Modifications**

- [ ] Update/add parsing logic in a modular function.
- [ ] Update SCHEMA if new fields are introduced.
- [ ] Edit YAML config for new patterns/categories.
- [ ] Add/modify unit and golden tests.
- [ ] Run all tests and check golden diffs.
- [ ] Document changes in `docs/`.
- [ ] Bump version if public API or output changes.

---

## 8. 🧭 **Extending for New Bank Layouts or Formats**

- **Add new regexes/categories** to YAML.
- **Write a new block parser** for the new format.
- **Add golden samples** for the new layout.
- **Test, test, test!**

---

## 9. 📚 **Further Reading**

- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) – For advanced integration and training.
- [README.md](../README.md) – For quickstart and CLI usage.
- [config/regexes.yml](../config/regexes.yml) – For pattern tuning.

---

**Happy parsing and extending!**