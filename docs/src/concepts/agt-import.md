# Agent audit-log import and dispute report

**What it is:** two offline, read-only commands that read an audit log an agent
runtime governance toolkit has already written to a file, and render a per-agent
report of what the agent was told, what the policy decided and why. OpenComplAI
reads files written by that toolkit; it does not call it, import its library or
touch the network.

**Trademark note:** the toolkit is named here only to say which file format is
read (compatible-with wording). OpenComplAI has no affiliation with it and its
authors, and implies no endorsement by them.

## What is read

Only the file sink: one JSON object per line (JSONL). The format is a public
preview and the exact field names are not confirmed, so the built-in mapping is
a low-confidence preset that tries several candidate keys per field. If your
records use other keys, override them with `--map field=dotted.path`.

Fields: `ts`, `agent_id`, `action`, `decision`, `rule`, `told`, `approver`.
Blank lines are skipped; a line that is not a JSON object, or that maps none of
`ts`, `action` and `decision`, is counted as rejected and never stops the run.
A UTF-8 byte order mark and CRLF line endings are accepted. The sample files in
`packages/core/tests/fixtures/agt_audit/` are synthetic and were not produced by
the toolkit.

## Commands

```text
opencomplai agents import-log FILE [--source agt] [--map field=path ...]
                                   [--format human|json] [--output FILE]

opencomplai agents dispute-report --log FILE --from DATE --to DATE
                                  [--source agt|native] [--agent ID]
                                  [--map field=path ...]
                                  [--format markdown|json] [--output FILE]
```

`import-log` prints line counts, the integrity label, the evidence status and
the limits. `dispute-report` needs an explicit window: `--from` and `--to` take
an ISO date or datetime (UTC when no offset is given); a date-only `--to` covers
that whole day, and both ends are inclusive. Records without a usable timestamp
are counted as undated and not listed. The report prints no generation date, so
the same input gives identical output. `--source native` reads a native agent
decision log (see `agents verify-log`); `--map` applies to `agt` only.

## Integrity and status

Every record set is labelled **format-valid, not verified**. The sink's integrity
hash is unkeyed unless the operator holds a key, so without that key it shows
format only. The import never verifies a chain or signature; a native log is
verified with `opencomplai agents verify-log`.

Evidence from this import is capped at **Partial**: it never reports Met. A file
with at least one mapped record is Partial; a file with none is Unverified.

## What is never claimed

- Completeness: rotated files restart their chain and there is no signed head.
- Retention: nothing shows how long records are kept.
- Coverage of any logging article, such as Art. 12 of the EU AI Act.
- That the record author is independent: it may be the operator being assessed.

## Effect on gates

None. The commands exit 0 whenever the file was read (rejected lines and an
Unverified status are reported, not fatal) and exit 2 only for an unreadable or
missing file, an invalid `--map`, an unsupported `--source` or other usage
errors. The output is not part of `check`, `gaps`, a dossier or a push payload,
and the log is not registered with `opencomplai verify`.
