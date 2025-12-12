# AWS EC2 deployment (Streamlit + systemd + Nginx)

This uses a single Ubuntu EC2 instance, systemd to keep Streamlit running on port 8501, and Nginx + Let’s Encrypt for HTTPS. Adjust sizes and regions as you like.

## 1) Launch the instance
- Choose Ubuntu 22.04 LTS (or newer), t3.small or better if you plan to render fights (moviepy/ffmpeg is CPU-heavy). Free tier t2.micro works for light web use only.
- Security group: allow TCP 22 (SSH), 80 (HTTP), 443 (HTTPS). Lock SSH to your IP if possible.
- Add an Elastic IP if you want a stable address.

## 2) SSH in
```bash
ssh -i /path/to/key.pem ubuntu@<your-ec2-public-dns>
```

## 3) Install system packages
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git ffmpeg nginx
sudo snap install --classic certbot  # for HTTPS later
```

## 4) Get the code onto the box
- Option A: push this repo to GitHub and clone:
  ```bash
  cd /opt
  sudo git clone https://github.com/<you>/<repo>.git ufc-app
  sudo chown -R ubuntu:ubuntu /opt/ufc-app
  ```
- Option B: `scp`/`rsync` the folder from your machine to `/opt/ufc-app`.

All commands below assume the app lives in `/opt/ufc-app` and you run them as `ubuntu` (or another non-root user).

## 5) Create the virtualenv and install requirements
```bash
cd /opt/ufc-app
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 6) Configure environment variables
Create `/opt/ufc-app/.env`:
```
PAYMENT_MODE=prod          # or dev to disable Stripe checkout
STRIPE_SECRET_KEY=sk_live_xxx
UFC_ENV=prod               # prod keeps data in data/prod and battles/prod
UFC_REFRESH_FOLLOWERS=0
INSTAGRAM_USERNAME=ultimatefollowerschampionship
INSTAGRAM_PASSWORD=...     # required if the session file is missing/expired
INSTAGRAM_SESSION_FILE=ultimatefollowingchampionship-session
```
Place your Instagram session file at `/opt/ufc-app/sessions/ultimatefollowingchampionship-session` if you have one; otherwise the app will try to refresh using the username/password.

## 7) Systemd service to keep Streamlit running
Create `/etc/systemd/system/ufc-streamlit.service` (sudo needed):
```
[Unit]
Description=UFC Streamlit app
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/ufc-app
EnvironmentFile=/opt/ufc-app/.env
ExecStart=/opt/ufc-app/.venv/bin/streamlit run apps/web_app.py --server.port=8501 --server.address=0.0.0.0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Enable and start it:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ufc-streamlit
sudo systemctl status ufc-streamlit
```

## 8) Nginx reverse proxy (HTTP)
Create `/etc/nginx/sites-available/ufc`:
```
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Enable and test:
```bash
sudo ln -s /etc/nginx/sites-available/ufc /etc/nginx/sites-enabled/ufc
sudo nginx -t
sudo systemctl reload nginx
```
If you don’t have a domain yet, you can skip Nginx and hit `http://<ec2-ip>:8501` directly (open port 8501 in the security group).

## 9) HTTPS with Let’s Encrypt
Point your domain’s DNS (A/AAAA) to the EC2 IP, then:
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
sudo systemctl reload nginx
```
Certbot sets up auto-renew via systemd timers.

## 10) Updating the app
```bash
cd /opt/ufc-app
git pull            # or copy the new files
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart ufc-streamlit
```

## 11) Troubleshooting
- `journalctl -u ufc-streamlit -f` to tail app logs.
- `sudo systemctl status ufc-streamlit` to see service health.
- If video rendering fails, ensure `ffmpeg` is installed (already in step 3) and instance size is adequate.
- If Instagram rate limits, set `UFC_REFRESH_FOLLOWERS=0` to rely on cached followers and session files.
