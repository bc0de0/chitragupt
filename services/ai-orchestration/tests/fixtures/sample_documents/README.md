# Sample Document Fixtures

Test files used by DocumentProcessor and IngestionPipeline tests.

## Files

| File | Purpose | Tests |
|---|---|---|
| `sample_text.txt` | Plain text document with BA content | T-CORR-07 (text extraction) |
| `sample_with_pii.txt` | Text containing email, phone, SSN, CC | T-QUAL-06 (PII scrubbing) |
| `zero_byte.pdf` | Empty file (0 bytes) | T-EDGE-07 (EMPTY_FILE rejection) |
| `binary.bin` | Random binary data | T-EDGE-06 (UNSUPPORTED_TYPE rejection) |
| `image_only.pdf` | Placeholder name for image-only PDF | T-EDGE-08 (graceful no-text handling) |

## Note

Actual PDF and DOCX files are created programmatically in test fixtures or via
monkeypatching. The binary.bin and zero_byte.pdf files can be created with:

```powershell
# zero_byte.pdf
New-Item -ItemType File -Path tests/fixtures/sample_documents/zero_byte.pdf

# binary.bin (256 bytes of all byte values)
[byte[]] (0..255) | Set-Content -Path tests/fixtures/sample_documents/binary.bin -Encoding Byte
```
