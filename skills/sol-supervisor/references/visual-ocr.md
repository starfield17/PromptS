# Visual OCR / transcription routing

Read this reference only when visual understanding is required for scanned pages, screenshots, photos, handwriting, forms, unusual typography/layout, or unreliable/garbled parsed text.

## Route

```text
visual/scanned/non-standard document
→ Luna xhigh visual transcription/OCR
→ optional parallel Luna page/range leaves for large documents
→ Terra high synthesis if the document set is broad/context-heavy
→ Sol uses the distilled text/evidence for judgment
```

Use Luna **max** only for unusually difficult handwriting/layout where xhigh leaves unresolved transcription uncertainty and the task remains bounded transcription rather than interpretation.

For large documents, split independent pages or contiguous page ranges across a small parallel Luna wave when useful. Preserve original page/order identity so results can be recombined deterministically.

## Return contract

Ask Luna to:

- transcribe faithfully before interpreting;
- preserve page number, section/order, headings, table/form relationships when material;
- distinguish transcription from inferred reconstruction;
- mark uncertain text explicitly, e.g. `[uncertain: ...]` or `[illegible]`;
- avoid silently "correcting" names, numbers, dates, citations, identifiers, or handwriting;
- return only the relevant transcription plus uncertainty/evidence unless analysis is separately requested.

When exact wording matters, Sol/Terra should rely on page-referenced transcription and re-check disputed or critical spans rather than visually rereading the whole document.

Do not force OCR for clean machine-readable text whose extraction is already reliable. Use it only where visual understanding adds value.
