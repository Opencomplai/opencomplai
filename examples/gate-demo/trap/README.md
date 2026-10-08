# Trap demo

A fictional customer support chatbot. On its own it is fine (see `../limited`).
The trap comes from the command, not the manifest: `--change-context model_retrain`
says the model was substantially modified, which trips the Art. 25 modification trap.

```bash
opencomplai check -m system-manifest.json --change-context model_retrain
```

Expected exit code: **4** (TRAP_DETECTED). The system is halted until a human approves
the change (`opencomplai accept --trap-approval --change-context model_retrain ...`).
The halted state is stored under `~/.opencomplai`; set `OPENCOMPLAI_STATE_DIR` to a
scratch directory to keep your real state clean.

These are fictional systems and an illustrative sandbox classification, not a legal classification or legal advice.
