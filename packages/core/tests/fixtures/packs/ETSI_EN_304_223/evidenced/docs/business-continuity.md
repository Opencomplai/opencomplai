# Continuity plan

Owner: Operations lead, Example Ltd
Last reviewed: 2026-09-01

## Critical services

- Critical services are the public API, the main database and the login service.
- Customers and support staff depend on all three.

## Recovery objectives

- The recovery time objective is four hours for each critical service.
- The recovery point objective is one hour of data.

## Recovery steps

- Fail over to the standby region, or rebuild from the infrastructure code.
- The operations lead decides when to start recovery.

## Testing

- The plan is exercised with a failover drill every quarter.
- Test results are recorded in the restore test report.
