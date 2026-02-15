# Deploy `hand-gesture-app` on Vultr (VM + Docker Compose)

This guide is copy/paste-friendly and starts from a fresh Vultr VM.

## 1) SSH into your Vultr VM

Run on your local machine:

```bash
ssh root@<VULTR_IP>
```

---

## 2) Install Docker Engine + Docker Compose Plugin

Run on the VM:

```bash
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release git ufw

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
docker --version
docker compose version
```

---

## 3) Open firewall ports on the VM

Run on the VM:

```bash
ufw allow OpenSSH
ufw allow 8090/tcp
ufw --force enable
ufw status
```

---

## 4) Clone your repo on the VM

Run on the VM:

```bash
mkdir -p /opt
cd /opt
git clone <YOUR_GIT_REPO_URL> museaid
cd /opt/museaid/hand-gesture-app
```

---

## 5) Create runtime environment file

Run on the VM:

```bash
cat > .env.vultr << 'EOF'
CAMERA_SRC=http://<YOUR_CAMERA_HOST_OR_IP>:<PORT>/stream.mjpg
HEADLESS=1
ENABLE_MJPEG=1
MJPEG_PORT=8090
MUSEAID_SERVER_URL=http://<YOUR_MUSEAID_SERVER_HOST_OR_IP>:8000
EOF
```

> If your camera URL is different, replace `CAMERA_SRC` accordingly.

---

## 6) Start container (using existing compose file)

This uses the compose setup in `docker-compose.yml`.

```bash
docker compose --env-file .env.vultr up --build -d
```

---

## 7) Verify service health

```bash
docker compose --env-file .env.vultr ps
docker compose --env-file .env.vultr logs -f hand-gesture-app
```

If camera connection fails, test reachability from the VM:

```bash
curl -I "$CAMERA_SRC"
```

---

## 8) Open app from your laptop

```text
http://<VULTR_IP>:8090/
```

---

## Day-2 operations

### Redeploy after pulling updates

```bash
cd /opt/museaid
git pull
cd /opt/museaid/hand-gesture-app
docker compose --env-file .env.vultr up --build -d
```

### Restart only

```bash
cd /opt/museaid/hand-gesture-app
docker compose --env-file .env.vultr restart hand-gesture-app
```

### Stop all services

```bash
cd /opt/museaid/hand-gesture-app
docker compose --env-file .env.vultr down
```

### Rollback (source-based)

```bash
cd /opt/museaid
git checkout <PREVIOUS_COMMIT_OR_TAG>
cd /opt/museaid/hand-gesture-app
docker compose --env-file .env.vultr up --build -d
```

---

## Notes

- Your existing compose file is at `hand-gesture-app/docker-compose.yml`.
- Docker restart policy is already configured there as `unless-stopped`.
- Keep `HEADLESS=1` in server/container deployments.
