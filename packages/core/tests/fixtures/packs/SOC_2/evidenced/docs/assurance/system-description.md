<!-- scaffold: source=heuristic starter (no legal source); confidence=low; needs_founder_review=true -->
# System description

Draft system description for Example Ltd, kept for a SOC 2 style assessment. This is a draft, not a finding.

<!-- clause: services -->
## Services provided

Example Ltd offers a hosted service desk service. Customers and their users raise and rank support tickets.

<!-- clause: components -->
## System components

The system has software components on managed hosting infrastructure. It holds ticket data and is run by a small operations team with written procedures.

<!-- clause: boundaries -->
## System boundaries

In scope: the web application, the API and the database. Out of scope: customer networks. The hosting provider is a subservice organisation and is excluded from our own controls.

<!-- clause: commitments -->
## Service commitments and system requirements

Our customer agreements state an uptime commitment of 99.5 per cent. Requirements behind it: monitoring, backups and a tested restore.

<!-- clause: incidents -->
## Incidents in the period

One minor outage in the period. It was resolved the same day and a corrective action was logged.
