# Trivy last run

Point-in-time record of the release gate's vulnerability scan on the five service images. The release gate
(`.github/workflows/supply-chain.yml`) stays the authority; new CVEs appear later.

- Trivy version: 0.74.0
- Gate flags: `--exit-code 1 --ignore-unfixed --severity CRITICAL,HIGH --timeout 15m`
- Scan date: 2026-10-07 (risk-engine, evidence-vault, doc-generator, egress-proxy); 2026-10-08 (gateway-api on node:24-alpine)
- Build: `docker buildx build --load --pull --no-cache -t opencomplai/<svc>:scan -f infra/docker/<svc>.Dockerfile .`
- Scan: `trivy image --format table --exit-code 1 --ignore-unfixed --severity CRITICAL,HIGH --timeout 15m opencomplai/<svc>:scan` (exit 0 on all five); counts from the same flags with `--format json --exit-code 0`.

| service | image id | base digest | HIGH | CRITICAL |
|---|---|---|---|---|
| gateway-api | sha256:9e3f43ec6652c606ded8f42d2b78ced9b69e1dc3b8b1f6df7c65b5e1373a6f77 | sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 | 0 | 0 |
| risk-engine | sha256:0cbd5d261a2ac408303f84719aa2c91aa85cf65a2d53fc89a433f127c79ea8dc | sha256:6f31d6e9ba2b0a787a3f81c37b004155b87b9efa1b771182bd550c1615745be5 | 0 | 0 |
| evidence-vault | sha256:624c08b2c1e7b3ab6ac6be408d7b6cd7019d65fd6eb6091cf8cb714ed932c9ac | sha256:6f31d6e9ba2b0a787a3f81c37b004155b87b9efa1b771182bd550c1615745be5 | 0 | 0 |
| doc-generator | sha256:12602ba3e8bc3947afe7f89565237509003ba75be992f219ff79577767171185 | sha256:6f31d6e9ba2b0a787a3f81c37b004155b87b9efa1b771182bd550c1615745be5 | 0 | 0 |
| egress-proxy | sha256:6661c814e09f6a33631b4df00ad70a7f532dd4ffe235f6c11877877d1e26eef5 | sha256:6f31d6e9ba2b0a787a3f81c37b004155b87b9efa1b771182bd550c1615745be5 | 0 | 0 |
