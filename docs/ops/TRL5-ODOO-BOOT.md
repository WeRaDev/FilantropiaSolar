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
