# CLI reference

The `opencomplai` command comes from the `opencomplai-cli` package; each command has its own page below, and `opencomplai <command> --help` prints the same options.

- [init](init.md): create a system manifest and set up the local signing keypair.
- [checker](checker.md): run the EU AI Act applicability checker.
- [validate-manifest](validate-manifest.md): validate a system manifest file against the required schema.
- [check](check.md): run a full compliance check against EU AI Act rules.
- [accept](accept.md): record that a person has accepted a system's high-risk classification.
- [scan](scan.md): cross-check the declared intended purpose against AI capability signals in the repository.
- [gaps](gaps.md): print a gap report for every target framework.
- [diff](diff.md): compare two compliance artifacts or gap reports.
- [rules changelog](rules.md): show the rule-set history.
- [controls](controls.md): operate the persistent control register.
- [incident](incident.md): record Art. 73 serious incidents locally and watch their deadlines.
- [agents](agents.md): offline view of the agent inventory declared in the system manifest.
- [recommend](recommend.md): write one remediation file per Missing or Partial requirement.
- [qms](qms.md): write a filled Art. 17 quality-management-system document.
- [fria](fria.md): draft an Art. 27 fundamental rights impact assessment.
- [report](report.md): render a single shareable HTML or PDF document.
- [risk classify](risk-classify.md): classify the risk level for an intended purpose.
- [verify-output](verify-output.md): verify an AI output claim against ground-truth sources.
- [verify](verify.md): check that a signed file is intact.
- [docs generate](docs-generate.md): generate an Annex IV technical documentation dossier.
- [instructions generate](instructions-generate.md): draft the Art. 13(3) instructions for use.
- [sync metadata](sync-metadata.md): sync allowlisted compliance metadata to the Premium Dashboard.
- [dashboard](dashboard.md): manage enrollment in the Premium Dashboard.
- [serve](serve.md): start a tiny localhost dashboard.
- [eval](eval.md): run the pipeline evaluators.
- [push](push.md): publish a signed artifact to the Premium Dashboard.
- [approve / resume](approve-resume.md): the human-in-the-loop hold.
- [keys](keys.md): manage the local Ed25519 signing keypair.
- [ai](ai.md): choose and inspect the backend used by the AI intent scan.
- [info and version](info.md): show what is installed.
- [deployer-pack](deployer-pack.md): seal an instructions-for-use document into one portable file.
- [portfolio](portfolio.md): check several systems in one command.
- [Exit codes](exit-codes.md): the fixed, contractual exit codes for CI gating.
