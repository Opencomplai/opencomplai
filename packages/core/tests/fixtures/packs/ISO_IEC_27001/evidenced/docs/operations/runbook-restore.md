# Runbook: restore the ticket database

Owner: Head of Operations (on-call role: platform on-call).

## Procedure

This procedure has four steps.

1. Declare the restore in the incident channel.
2. Pick the latest backup and restore it to a new instance.
3. Run the smoke tests against the new instance.
4. Switch the service to the new instance.

## Rollback

If the smoke tests fail, keep the old instance and escalate to the Head of Operations.
