# OCI Deployment (Phase P4) — Always-Free Ampere A1, CLI only

All infra changes are delivered as `oci` CLI commands (owner preference). Replace the
placeholder OCIDs; verify current image OCIDs with the list command below, as they rotate.

## 1. Instance (4 OCPU / 24 GB fits the Always-Free A1 allowance)

```bash
# Find latest Ubuntu 24.04 aarch64 image OCID
oci compute image list --compartment-id "$COMPARTMENT_OCID" \
  --operating-system "Canonical Ubuntu" --operating-system-version "24.04" \
  --shape "VM.Standard.A1.Flex" --sort-by TIMECREATED --sort-order DESC \
  --query 'data[0].id' --raw-output

oci compute instance launch \
  --compartment-id "$COMPARTMENT_OCID" \
  --availability-domain "$AD" \
  --shape "VM.Standard.A1.Flex" \
  --shape-config '{"ocpus": 4, "memoryInGBs": 24}' \
  --image-id "$IMAGE_OCID" \
  --subnet-id "$SUBNET_OCID" \
  --assign-public-ip true \
  --ssh-authorized-keys-file ~/.ssh/id_ed25519.pub \
  --display-name meridian-prod
```

## 2. Open ports 80/443 on the subnet's security list

```bash
oci network security-list update --security-list-id "$SECLIST_OCID" --force \
  --ingress-security-rules '[
    {"protocol":"6","source":"0.0.0.0/0","tcpOptions":{"destinationPortRange":{"min":80,"max":80}}},
    {"protocol":"6","source":"0.0.0.0/0","tcpOptions":{"destinationPortRange":{"min":443,"max":443}}},
    {"protocol":"6","source":"0.0.0.0/0","tcpOptions":{"destinationPortRange":{"min":22,"max":22}}}
  ]'
```

Note: Ubuntu images also ship iptables rules; on the VM allow 80/443 or use ufw.

## 3. On the VM

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER && newgrp docker
git clone git@github.com:<owner>/meridian.git && cd meridian
cp .env.example .env   # fill secrets
docker compose --profile ingest --profile web up -d --build
```

## 4. TLS

Add a `caddy` service (ports 80/443) reverse-proxying api:8000 and web:80 — automatic
Let's Encrypt. Add in P4.

## 5. CI/CD

GitHub Actions: build multi-arch images (linux/arm64!) -> push to OCIR -> SSH deploy step
runs `docker compose pull && up -d`. Skeleton in .github/workflows/ci.yml; extend in P4.
