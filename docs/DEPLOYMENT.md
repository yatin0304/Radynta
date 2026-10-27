# Deployment and domains

Nothing has been deployed and no DNS has been changed. These are the steps to do it.

## 1. Choose hosting

The app needs Python and a **persistent disk** (enquiries and audits live in SQLite).

| Option | Fit | Notes |
|---|---|---|
| Small Linux VPS (1 vCPU / 1 GB) | **Recommended** | Cheapest reliable option; full control; runs the crawler without platform limits. |
| PythonAnywhere (paid tier) | Good | Persistent files and simple setup. Check that outbound requests to arbitrary sites are allowed on your plan, because the crawler needs them. |
| Render / Railway / Fly free tiers | Avoid for now | Free-tier disks are often ephemeral, so SQLite data would be lost on redeploy. Add a persistent volume or move to Postgres first. |

## 2. VPS setup (Ubuntu)

```bash
sudo apt update && sudo apt install -y python3-venv nginx certbot python3-certbot-nginx
sudo useradd -m -s /bin/bash radynta && sudo -iu radynta
git clone <your repo> app && cd app
python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
cp .env.example .env   # set RADYNTA_ENV=production, RADYNTA_SECRET_KEY, CONTACT_EMAIL ...
flask --app radynta init-db && flask --app radynta create-user you@radynta.com
pytest                 # confirm everything passes on the server
```

`/etc/systemd/system/radynta.service`:

```ini
[Unit]
Description=RADYNTA
After=network.target

[Service]
User=radynta
WorkingDirectory=/home/radynta/app
ExecStart=/home/radynta/app/venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 "radynta:create_app()"
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now radynta
```

Use 2 workers or fewer, because the rate limiter is per-process.

## 3. DNS (GoDaddy)

For **radynta.com**:
- `A` record `@` → your server IP
- `CNAME` record `www` → `radynta.com`

For **radynta.in**, point it at the same server so redirects preserve the path:
- `A` record `@` → your server IP
- `CNAME` record `www` → `radynta.in`

Don't use GoDaddy's "domain forwarding" for radynta.in unless you've confirmed it preserves the path and query string. Server-side 301s are more reliable.

**Business email:** keep the MX records your email provider gives you (Google Workspace, Zoho, etc.) when editing DNS. Don't delete them.

## 4. nginx + TLS

`/etc/nginx/sites-available/radynta`:

```nginx
# Secondary hosts -> canonical, preserving path and query
server {
    listen 80;
    listen 443 ssl;
    server_name radynta.in www.radynta.in www.radynta.com;
    # ssl_certificate lines are added by certbot
    return 301 https://radynta.com$request_uri;
}

server {
    listen 80;
    server_name radynta.com;
    return 301 https://radynta.com$request_uri;
}

server {
    listen 443 ssl;
    server_name radynta.com;
    client_max_body_size 1m;
    location /static/ { alias /home/radynta/app/radynta/static/; expires 7d; }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/radynta /etc/nginx/sites-enabled/
sudo certbot --nginx -d radynta.com -d www.radynta.com -d radynta.in -d www.radynta.in
sudo nginx -t && sudo systemctl reload nginx
```

The Flask app also 301-redirects `REDIRECT_HOSTS` to `CANONICAL_HOST`, as a fallback if a request reaches it directly.

## 5. Verify after go-live

```bash
curl -sI http://radynta.in/services/?x=1        # 301 -> https://radynta.com/services/?x=1
curl -sI https://www.radynta.com/about/         # 301 -> https://radynta.com/about/
curl -s https://radynta.com/robots.txt
curl -s https://radynta.com/sitemap.xml | head
```

Then:
- Submit `https://radynta.com/sitemap.xml` in Google Search Console and Bing Webmaster Tools, and add both radynta.com and radynta.in as properties.
- Submit a test enquiry and confirm it appears at `/monitor/enquiries`.
- Back up the database daily: `sqlite3 instance/radynta.db ".backup '/home/radynta/backups/radynta-$(date +%F).db'"` from cron.

## 6. Security checklist before exposing /monitor

- [ ] `RADYNTA_ENV=production` and a random `RADYNTA_SECRET_KEY`
- [ ] HTTPS working on all four hostnames
- [ ] Monitor user created with a strong, unique password; no demo users
- [ ] `.env` readable only by the app user (`chmod 600 .env`)
- [ ] Optional: restrict `/monitor` to your IP in nginx (`allow x.x.x.x; deny all;`)
