# Zentra — deployment (Safespring VPS)

## Live

**http://192.121.133.232** — Ubuntu 24.04, 2 cores, 3.9 GB RAM, 96 GB disk.

| Layer | What |
|---|---|
| nginx :80 | reverse proxy → 127.0.0.1:8010, no-store headers, 6 MB upload cap, 90 s timeouts (AI calls) |
| systemd `zentra` | uvicorn, `Restart=always`, logs to `~/zentra/server.log` |
| app | `/home/ubuntu/zentra`, venv at `.venv`, `DATA_MODE=seed` |

## Access

```bash
ssh <your-key> <your-host>
```

Key: the VPS keypair (kept outside this repo).
Host keys were rotated when the VM was rebuilt; local `known_hosts` updated 2026-08-25
(backup at `~/.ssh/known_hosts.bak.*`).

## Operations

```bash
sudo systemctl status zentra        # health
sudo systemctl restart zentra       # restart app
tail -f ~/zentra/server.log         # logs
curl -s -X POST localhost/api/reset # re-arm the demo scenario
```

## Deploy an update

```bash
ssh <your-key> <your-host> \
  'cd ~/zentra && git pull -q && .venv/bin/pip install -q -r requirements.txt \
   && .venv/bin/python -m backend.seed.generate && sudo systemctl restart zentra'
```

## Verified after deploy (2026-08-25)

- public IPv4 200 in 20 ms; 13/13 tests pass on the box
- fraud hold (Städgrossisten 48 000 kr), payroll hold (Jonas Bergström)
- 13 cleared / 9 paid today, validator ALL GREEN (9 checks)
- planned min 22 200 vs naive 4 200; report + assistant + upload endpoints all answer

## Notes / gotchas

- **IPv6** (`2a09:d400:1:40::291`) is assigned but not reachable from the build machine —
  IPv4 is the demo address. Not worth debugging before the event.
- **Port 8000 is unusable locally** (Docker Desktop on Windows forwards it to another
  container); the app runs on **8010** everywhere for consistency.
- `LLM_BACKEND=none` in the systemd unit until Claude CLI is authenticated on the box;
  every AI surface has a deterministic template fallback, so nothing breaks — set it to
  `claude-code` after `claude login` to enable AI narration.
- `.env` is chmod 600 on the VPS and gitignored. **Rotate the Open Payments secret after
  the event.**
- HTTP only (no TLS). Fine for a demo IP; add Caddy/certbot if a domain is attached.
