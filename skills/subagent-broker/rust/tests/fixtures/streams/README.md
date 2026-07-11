# Claude Code stream fixtures (desensitized)

These are synthetic stream-json samples used by unit tests. No secrets.

## success_with_identity.jsonl
system init + assistant tool use + result with model identity.

## denial_with_success_claim.jsonl
Vendor result subtype success but permission_denials present.

## identity_mismatch_grok_as_claude.jsonl
Requested as claude-code but stream declares grok/xai model.

## verbose_tool_result.jsonl
Large tool_result content then final result (raw log truncation scenario).

## cancelled_incomplete.jsonl
Stream ends without a result event (invalid/cancelled path).
