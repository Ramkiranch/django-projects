#!/usr/bin/env bash
# server-hardening.sh — defense-in-depth setup for the Lightsail VM.
#
# What this does:
#   1. Enables UFW with a deny-by-default policy and explicit allows for
#      SSH (22), HTTP (80), HTTPS (443/tcp + 443/udp for HTTP/3).
#   2. Disables SSH password authentication so only key-based logins work.
#
# What it does NOT do:
#   - Touch the Lightsail-edge IPv4 firewall (configure that in the AWS
#     console; UFW here is a second layer behind it).
#   - Disable root SSH (Lightsail Ubuntu images already have root login
#     disabled out of the box).
#   - Install fail2ban (optional add-on; uncomment the section near the
#     bottom if you want it).
#
# Idempotent: re-running this on a hardened host is a no-op (each step
# is gated on a "needs change?" check). Safe to run any time.
#
# Run as: sudo bash /opt/ramkiransblog/scripts/server-hardening.sh
#
# After running, re-verify with:
#   sudo ufw status verbose
#   sudo sshd -T | grep -i passwordauthentication
#   ss -tlnp | grep -E ':(8000|5432)'   # should be empty (internal-only)

set -euo pipefail

# Pretty-print steps
say() { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
ok()  { printf '   \033[32m✓\033[0m %s\n' "$*"; }

if [[ $EUID -ne 0 ]]; then
  echo "Must run as root: sudo bash $0" >&2
  exit 1
fi

# -------------------------------------------------------------------
# 1. UFW
# -------------------------------------------------------------------
say "Configuring UFW (defense-in-depth firewall)"

if ! command -v ufw >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq ufw
  ok "installed ufw"
else
  ok "ufw already installed"
fi

# Reset to a known baseline only on first configure; otherwise just
# ensure each rule exists. `ufw allow` is idempotent — adding the same
# rule twice is a no-op, so this block is safe to re-run.
ufw --force default deny incoming  >/dev/null
ufw --force default allow outgoing >/dev/null
ufw allow 22/tcp  comment 'SSH'    >/dev/null
ufw allow 80/tcp  comment 'HTTP'   >/dev/null
ufw allow 443/tcp comment 'HTTPS'  >/dev/null
ufw allow 443/udp comment 'HTTP/3' >/dev/null
ok "rules: allow 22/tcp, 80/tcp, 443/tcp, 443/udp; deny everything else inbound"

# Enable only if not already enabled (avoids the interactive prompt entirely).
if ufw status | grep -q "Status: active"; then
  ok "ufw already active"
else
  ufw --force enable >/dev/null
  ok "ufw enabled"
fi

ufw status verbose

# -------------------------------------------------------------------
# 2. SSH: disable password authentication
# -------------------------------------------------------------------
say "Disabling SSH password authentication"

SSHD_CONFIG="/etc/ssh/sshd_config"
BACKUP="${SSHD_CONFIG}.bak.$(date +%Y%m%d-%H%M%S)"

# Only edit if password auth isn't already disabled. Use `sshd -T` (the
# effective merged config) as the source of truth — files in
# /etc/ssh/sshd_config.d/ can override what's in the main file.
EFFECTIVE=$(sshd -T 2>/dev/null | awk '/^passwordauthentication / {print $2}')

if [[ "${EFFECTIVE:-}" == "no" ]]; then
  ok "PasswordAuthentication is already 'no' (effective)"
else
  cp "$SSHD_CONFIG" "$BACKUP"
  ok "backed up sshd_config -> $BACKUP"

  # Replace any existing PasswordAuthentication line (commented or not);
  # if no line exists at all, append one.
  if grep -qE '^[#[:space:]]*PasswordAuthentication[[:space:]]' "$SSHD_CONFIG"; then
    sed -i 's/^[#[:space:]]*PasswordAuthentication[[:space:]].*/PasswordAuthentication no/' "$SSHD_CONFIG"
  else
    printf '\n# Hardened by scripts/server-hardening.sh\nPasswordAuthentication no\n' >> "$SSHD_CONFIG"
  fi

  # Also override any drop-in that might re-enable it (Ubuntu 22.04 ships
  # /etc/ssh/sshd_config.d/50-cloud-init.conf which sets PasswordAuth yes
  # on some images).
  mkdir -p /etc/ssh/sshd_config.d
  cat > /etc/ssh/sshd_config.d/99-hardening.conf <<'EOF'
# Managed by scripts/server-hardening.sh — see repo for details.
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
  ok "wrote /etc/ssh/sshd_config.d/99-hardening.conf"

  # Validate before reloading so a typo can't lock us out.
  sshd -t
  systemctl reload ssh
  ok "sshd reloaded"
fi

# -------------------------------------------------------------------
# 3. Sanity: app ports must NOT be host-bound
# -------------------------------------------------------------------
say "Checking that app ports are internal-only"

LEAKS=$(ss -tlnp 2>/dev/null | awk '/:(8000|5432) / {print}' || true)
if [[ -n "$LEAKS" ]]; then
  echo "   WARNING: app ports appear bound on the host:" >&2
  echo "$LEAKS" >&2
  echo "   This usually means docker-compose is publishing them — check the compose file." >&2
else
  ok "neither 8000 (gunicorn) nor 5432 (postgres) is host-bound"
fi

# -------------------------------------------------------------------
# Optional: fail2ban
# -------------------------------------------------------------------
# Uncomment to install fail2ban with the default sshd jail enabled.
# Useful if you ever need to leave SSH password auth on, less useful
# in a key-only setup but free defense-in-depth.
#
# if ! command -v fail2ban-server >/dev/null 2>&1; then
#   say "Installing fail2ban"
#   apt-get install -y -qq fail2ban
#   systemctl enable --now fail2ban
#   ok "fail2ban installed and enabled"
# fi

say "Hardening complete"
echo "   Re-verify in a NEW shell session that you can still ssh in"
echo "   (don't close this session until you've confirmed)."
