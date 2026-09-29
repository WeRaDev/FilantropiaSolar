# TRL5 Odoo boot resilience

## Problem
After host reboot, `filantropia-odoo` could come back **without Docker networks**
(empty `Networks`, cannot resolve `odoo-db`), crash-loop, and leave
https://filantropiasolar.pt on Cloudflare **502**. Container `restart: unless-stopped`
alone is not enough if the container is orphaned off the compose network.

Also, base compose used to `depends_on: nextcloud` (legacy). On TRL5 the SoT is
**Nextcloud AIO** and `filantropia-nextcloud` is stopped — that dependency was harmful.

## Fix (installed on TRL5)

| Piece | Path / unit |
|-------|-------------|
| Ensure script | `/opt/FilantropiaSolar/nextcloud-app/scripts/trl5-ensure-stack.sh` |
| Boot unit | `filantropia-stack.service` (enabled) |
| Periodic heal | `filantropia-stack-health.timer` every 15 min |
| Compose | `odoo` waits for healthy `odoo-db`; no hard dep on legacy NC |
| TRL5 override | legacy `nextcloud` service `restart: "no"` |

### What the ensure script does
1. `docker compose --profile odoo up -d` for db/redis/ml/odoo-db/odoo  
2. Starts cloudflared compose in `/home/wera-admin/cloudflared-nc`  
3. Re-attaches containers to `nextcloud-app_filantropia-net` (+ tunnel to `nextcloud-aio`)  
4. Keeps `filantropia-nextcloud` stopped  
5. Waits until `http://127.0.0.1:8069/web/login` returns 200  

### Ops commands
```bash
sudo systemctl status filantropia-stack.service
sudo systemctl start filantropia-stack.service   # manual heal
sudo journalctl -u filantropia-stack.service -n 50 --no-pager
bash /opt/FilantropiaSolar/nextcloud-app/scripts/trl5-ensure-stack.sh
```

### Verify after reboot
```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8069/inicio
curl -sS -o /dev/null -w '%{http_code}\n' https://filantropiasolar.pt/inicio
docker inspect filantropia-odoo --format 'nets={{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
# expect nextcloud-app_filantropia-net
```

## Frank standby and one-writer failover

TRL5's daily Odoo recovery timer copies a verified database/filestore pair to
Frank; it does not overwrite Frank's dormant database or start its Odoo. The
latest verified recovery set is recorded in `docs/ops/TRL5-BACKUP.md`. Frank's
`filantropia-odoo` remains stopped with restart policy `no`; do not start it
for routine backup checks or because a public health check fails.
TRL5 is authoritative while online. A bundle on Frank is a TRL5-originated
promotion snapshot, not a record of any later writes accepted by Frank.

Read-only checks on 2026-09-29 found that Frank's mounted addon source is
`19.0.2.34.0` (the recovered database is `19.0.2.35.0`), `FS_NC_OFFLINE` is
unset, and `filantropia-cloudflared.service` is inactive. Frank's Docker root
is `/data-bulk/docker` on `/dev/sda7` ext4; encrypted `/data` is a separate
mount and does not establish at-rest protection for the Odoo volume. These
must be resolved or explicitly accepted before promotion; no storage,
deployment, service, or route change has been made.

Promotion is a manual, explicitly approved operation:

1. Prove which origin is serving the public site and fence the current writer
   before restoring or routing traffic. If TRL5 is reachable, disable its
   boot/ensure unit and health timer for the approved cutover, stop
   `filantropia-odoo`, and verify it stays stopped:

   ```bash
   sudo systemctl disable --now filantropia-stack.service filantropia-stack-health.timer
   docker stop filantropia-odoo
   docker inspect --format '{{.State.Status}}' filantropia-odoo  # must be exited
   ```

   Re-enable the TRL5 units only during an approved failback after Frank is
   fenced. If TRL5 is unreachable, independently fence its ingress/writer; if
   that cannot be proven, do not promote Frank.
2. Verify the selected TRL5-originated bundle's outer/component hashes and
   restore both components using the gated procedure in
   `docs/ops/TRL5-BACKUP.md`. Before replacing Frank's current volume, rule
   out prior unreconciled Frank-originated writes; if that cannot be proved,
   stop and capture/reconcile them before the destructive restore.
3. Before starting Frank, verify its addon source matches the restored
   database (`19.0.2.35.0` for the current recovery set), verify offline
   Nextcloud settings and Odoo configuration, and validate the restored
   website/filestore. The bundle contains neither source code nor secrets.
4. Route public ingress to exactly one writer only after the restore and
   origin have been proved. Start Frank's Odoo only in that approved
   promotion window; monitor the site and queued mail. Do not start both
   Odoo writers, and do not treat HTTP 200 alone as proof of the serving
   origin.
5. Failback is not automatic. If Frank accepted no writes, fence Frank and
   resume TRL5 with its pre-outage database/filestore still in place; do not
   restore a TRL5-originated bundle from Frank back onto TRL5. If Frank
   accepted writes or that cannot be ruled out, fence Frank, create and
   verify a fresh Frank-originated DB+filestore recovery set, preserve TRL5's
   pre-failback state for rollback, then restore and validate before routing
   back. Follow `docs/ops/TRL4-ODOO-FAILOVER.md` for the manual single-writer
   gates.

The public TRL5 routes were verified after deployment on 2026-09-28:
`/inicio`, `/projetos`, and `/contacto` each returned HTTP 200. This confirms
the current site is healthy, not that Frank is a proven public origin or is
ready for promotion.
