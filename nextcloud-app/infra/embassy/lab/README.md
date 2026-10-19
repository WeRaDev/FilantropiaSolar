# Isolated failover lab

Local-only rehearsal for the software lease authority. This compose file does
**not** contact TRL5, Frank, or production Cloudflare.

## Lease authority smoke

```bash
cd nextcloud-app/infra/embassy/lab
# Prefer a plain process if Docker mounts are read-only on the host:
#   LEASE_API_TOKEN=lab-only-token LEASE_TTL_SECONDS=6 \
#   PYTHONPATH=../.. python3 lease_authority_server.py
docker compose up -d lease-authority
# from repo with PYTHONPATH=nextcloud-app/infra
FS_LEASE_AUTHORITY_URL=http://127.0.0.1:8787 \
FS_LEASE_AUTHORITY_TOKEN=lab-only-token \
python3 - <<'PY'
from embassy.lease_client import HttpLeaseClient, LeaseClientConfig
c = HttpLeaseClient(LeaseClientConfig('http://127.0.0.1:8787','lab-only-token'))
print(c.bootstrap(node_id='trl5', generation='lab-1'))
print(c.status())
# After request_takeover, wait > LEASE_TTL + DRAIN + GRACE before acquire.
PY
```

PostgreSQL primary/standby containers are placeholders for future guarded
`pg_basebackup` rehearsals. Do not point them at production data.
