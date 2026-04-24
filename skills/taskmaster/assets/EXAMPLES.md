# Taskmaster v5 Examples

## Single Task — Compact

**Scenario**: rename one CLI flag across a small script set.

```csv
id,task,status,completed_at,notes
1,Locate affected scripts,IN_PROGRESS,,
2,Rename the flag,TODO,,
3,Run smoke test,TODO,,
```

## Single Task — Full

**Scenario**: fix one OAuth callback bug with full recovery support.

```text
.codex-tasks/20260313-auth-fix/
├── SPEC.md
├── TODO.csv
├── PROGRESS.md
└── raw/
```

## Epic Task

**Scenario**: ship a billing dashboard across backend, frontend, and docs.

```text
.codex-tasks/20260313-billing-epic/
├── EPIC.md
├── SUBTASKS.csv
├── PROGRESS.md
└── tasks/
    ├── 20260313-api/
    ├── 20260313-frontend/
    └── 20260313-docs/
```

```csv
id,task,task_type,status,depends_on,task_dir,acceptance_criteria,validation_command,completed_at,retry_count,notes
1,Implement billing API,single-full,DONE,,tasks/20260313-api,API tests pass,pytest tests/billing_api.py,2026-03-13 10:12,0,
2,Build billing UI,single-full,IN_PROGRESS,1,tasks/20260313-frontend,UI renders invoices,npm test -- --grep billing,,0,
3,Update billing docs,batch,TODO,1;2,tasks/20260313-docs,All docs rows succeed,python3 scripts/validate_docs.py,,0,
```

## Batch Task

**Scenario**: audit 80 Markdown files for frontmatter consistency.

```text
.codex-tasks/20260313-doc-audit/
├── SPEC.md
├── TODO.csv
├── PROGRESS.md
├── batch/
│   ├── BATCH.md
│   ├── workers-input.csv
│   └── workers-output.csv
└── raw/
```

```csv
id,file_path,target_rule,notes
1,docs/a.md,frontmatter-required,
2,docs/b.md,frontmatter-required,
3,docs/c.md,frontmatter-required,
```

```csv
id,status,summary,changed,evidence_path,error
1,DONE,Frontmatter already valid,false,artifacts/a.json,
2,FAILED,Missing title,false,artifacts/b.json,missing title
3,DONE,Frontmatter fixed,true,artifacts/c.json,
```

## Epic with Mixed Children (End-to-End)

**Scenario**: ship an i18n system — backend API (Single), frontend integration
(Single), and batch-translate 40 locale files (Batch).

### Directory layout

```text
.codex-tasks/20260313-i18n-epic/
├── EPIC.md
├── SUBTASKS.csv
├── PROGRESS.md
└── tasks/
    ├── 20260313-i18n-api/           ← single-full child
    │   ├── SPEC.md
    │   ├── TODO.csv
    │   └── PROGRESS.md
    ├── 20260313-i18n-frontend/      ← single-full child
    │   ├── SPEC.md
    │   ├── TODO.csv
    │   └── PROGRESS.md
    └── 20260313-i18n-translate/     ← batch child
        ├── SPEC.md
        ├── TODO.csv                 ← 3-step batch plan
        ├── PROGRESS.md
        └── batch/
            ├── BATCH.md
            ├── workers-input.csv
            └── workers-output.csv
```

### SUBTASKS.csv

```csv
id,task,task_type,status,depends_on,task_dir,acceptance_criteria,validation_command,completed_at,retry_count,notes
1,Build i18n API,single-full,DONE,,tasks/20260313-i18n-api,API returns translated strings,pytest tests/i18n_api.py,2026-03-13 09:40,0,
2,Integrate i18n in frontend,single-full,IN_PROGRESS,1,tasks/20260313-i18n-frontend,UI renders in selected locale,npm test -- --grep i18n,,0,
3,Batch-translate 40 locale files,batch,TODO,1,tasks/20260313-i18n-translate,All locale rows pass,test -f tasks/20260313-i18n-translate/batch/workers-output.csv,,0,
```

### Batch child TODO.csv (tasks/20260313-i18n-translate/)

```csv
id,task,status,acceptance_criteria,validation_command,completed_at,retry_count,notes
1,Build workers-input.csv from locales/,TODO,batch/workers-input.csv exists,test -f batch/workers-input.csv,,0,
2,Run spawn_agents_on_csv,TODO,batch/workers-output.csv exists,test -f batch/workers-output.csv,,0,
3,Merge results and handle failures,TODO,All rows pass or are accepted,grep -c FAILED batch/workers-output.csv | grep -q ^0$,,0,
```

### Batch child workers-input.csv

```csv
id,file_path,source_lang,target_lang
1,locales/en.json,en,zh
2,locales/en.json,en,ja
3,locales/en.json,en,ko
...
40,locales/en.json,en,pt
```

### Batch child workers-output.csv (after run)

```csv
id,status,summary,changed,evidence_path,error
1,DONE,Translated 182 keys,true,artifacts/zh.json,
2,DONE,Translated 182 keys,true,artifacts/ja.json,
3,FAILED,3 keys untranslatable,false,artifacts/ko.json,keys: date_fmt; plural_rule; honorific
```

In this example, the Epic parent waits for child tasks 1-3 to all reach `DONE`.
Child 3 (Batch) internally retries failed rows via `workers-input-retry.csv`
before escalating.

