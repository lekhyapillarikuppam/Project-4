# Backend deployment (Feature 008 T03)

The API runs on the Azure VM that also hosts Project 2, behind Project 2's Caddy, at
`https://lekhya-audiobook.centralindia.cloudapp.azure.com/tripwise/` (health: `/tripwise/health`).

| Piece | Where | Notes |
|---|---|---|
| Code and dataset | `/opt/tripwise/backend`, `/opt/tripwise/data/curated` | from `git archive HEAD`; venv in `backend/.venv` (Python 3.12) |
| Service | `tripwise-api` (systemd, `deploy/tripwise-api.service`) | uvicorn, 1 worker, user `tripwise`, `MemoryMax=450M`, bound to `172.18.0.1:8100` (the `audiobook_default` Docker network gateway) |
| Secrets | `/etc/tripwise.env` (root, 600) | `DATABASE_URL`, `JWT_SECRET`, `GROQ_API_KEY`, `FRONTEND_ORIGIN`, `APP_ENV=production`, `DB_SCHEMA=app` |
| HTTPS | Project 2 Caddy (Docker), block in `deploy/Caddyfile.tripwise` | Let's Encrypt certificate already held by Caddy; HTTP redirects to HTTPS (308) |
| Firewall | UFW rule `172.18.0.0/16 → 172.18.0.1 port 8100/tcp` | only Caddy's network reaches the API; port 8100 is closed from the internet |

Redeploy after a commit: `.\deploy\deploy.ps1` (PowerShell, repo root). Logs: `sudo journalctl -u tripwise-api -f`.
Undo the Caddy change: `~/Project-2/deploy/Caddyfile.bak-before-tripwise` is the original.
