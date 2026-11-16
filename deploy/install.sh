#!/usr/bin/env bash
# First installation on the shared host.
set -euo pipefail
umask 077

version=${1:?Missing release version}
expected_sha=${2:?Missing archive SHA-256}
resume=${3:-}
[[ $version =~ ^[0-9]{8}T[0-9]{6}$ && $expected_sha =~ ^[a-f0-9]{64}$ ]]
[[ -z $resume || $resume == --resume-first-install ]]
archive=/root/address-book-$version.tar.gz
root=/opt/websites/address-book
release=$root/releases/$version
config=/etc/web-address-book
unit=/etc/systemd/system/web-address-book.service
limits=/etc/nginx/conf.d/address-book-limits.conf
route=/etc/nginx/calculator-sites.d/address-book.conf
origin=https://47.117.170.115

printf '%s  %s\n' "$expected_sha" "$archive" | sha256sum --check
test -d /etc/nginx/calculator-sites.d
grep -Fq 'include /etc/nginx/calculator-sites.d/*.conf;' /etc/nginx/sites-available/calculator
for path in "$root/current" "$release" "$unit" "$limits" "$route"; do
    if [[ -e "$path" || -L "$path" ]]; then
        printf 'Existing Address Book path: %s\n' "$path" >&2
        exit 1
    fi
done
if ss -H -lnt 'sport = :3002' | grep -q .; then
    echo 'Address Book port is already in use' >&2
    exit 1
fi
if [[ -z $resume ]]; then
    test ! -e "$config"
    test ! -e /var/lib/web-address-book
    ! getent passwd web-address-book >/dev/null
else
    test -s "$config/environment"
    test "$(stat -c %U /var/lib/web-address-book)" = web-address-book
    test "$(getent passwd web-address-book | cut -d: -f6-7)" = /var/lib/web-address-book:/usr/sbin/nologin
    test ! -e "$config/htpasswd"
fi

check_existing() {
    systemctl is-active --quiet nginx
    systemctl is-active --quiet calculator
    for existing in / /scriptchisel/ /api/health /tongyan/; do
        curl -fsS --max-time 10 -o /dev/null "$origin$existing"
    done
}
check_existing
test "$(curl -fsS "$origin/" | sha256sum)" = "$(curl -fsS "$origin/address-book/" | sha256sum)"
calculator_release=$(readlink -f /opt/calculator/current)
calculator_pid=$(systemctl show -p MainPID --value calculator)

activated=0
nginx_reloaded=0
rollback() {
    code=$?
    if (( code != 0 )); then
        if (( activated )); then
            rm -f -- "$route" "$limits"
            if (( nginx_reloaded )); then
                nginx -t && systemctl reload nginx
            fi
            journalctl -u web-address-book -n 30 --no-pager >&2
            systemctl disable --now web-address-book || true
            rm -f -- "$unit" "$root/current"
            systemctl daemon-reload
        fi
        echo 'Installation failed. Any staged Address Book release or state was retained for diagnosis.' >&2
    fi
}
trap rollback EXIT

install -d -m 0755 "$root" "$root/releases" "$release"
tar -xzf "$archive" --no-same-owner -C "$release"
python3 -m venv "$release/.venv"
env -u PIP_EXTRA_INDEX_URL -u PIP_TRUSTED_HOST PIP_CONFIG_FILE=/dev/null \
    "$release/.venv/bin/python" -m pip install --index-url https://pypi.org/simple \
    --no-cache-dir --disable-pip-version-check -r "$release/deploy/requirements.txt"
"$release/.venv/bin/python" -m pip check
chmod -R u=rwX,go=rX "$release"

if [[ -z $resume ]]; then
    useradd --system --user-group --no-create-home --home-dir /var/lib/web-address-book --shell /usr/sbin/nologin web-address-book
    install -d -m 0755 "$config"
    printf 'ADDRESS_BOOK_SECRET=%s\nADDRESS_BOOK_URL=%s/address-book/\n' "$(openssl rand -hex 32)" "$origin" > "$config/environment"
fi

activated=1
ln -s "$release" "$root/current"
install -m 0644 "$release/deploy/web-address-book.service" "$unit"
systemd-analyze verify "$unit"
systemctl daemon-reload
systemctl enable --now web-address-book
for attempt in {1..10}; do
    if curl -fsS --max-time 2 -H 'Host: 47.117.170.115' http://127.0.0.1:3002/address-book/health >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
curl -fsS --max-time 3 -H 'Host: 47.117.170.115' http://127.0.0.1:3002/address-book/health

install -m 0644 "$release/deploy/nginx-limits.conf" "$limits"
install -m 0644 "$release/deploy/nginx-route.conf" "$route"
nginx -t
nginx_reloaded=1
systemctl reload nginx

public_code() {
    curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "$origin$1"
}
expect_status() {
    printf '%s: %s (expected %s)\n' "$1" "$2" "$3"
    test "$2" = "$3"
}
for attempt in {1..10}; do
    if [[ $(public_code /address-book) == 308 ]]; then
        break
    fi
    sleep 1
done
expect_status redirect "$(public_code /address-book)" 308
expect_status public_home "$(public_code /address-book/)" 200
expect_status health "$(public_code /address-book/health)" 200
expect_status stylesheet "$(public_code /address-book/static/ambient-background.css)" 200
expect_status missing_asset "$(public_code /address-book/static/missing.js)" 404
expect_status csrf "$(curl -sS --max-time 10 -X POST -o /dev/null -w '%{http_code}' "$origin/address-book/contacts/new")" 403
check_existing
test "$(readlink -f /opt/calculator/current)" = "$calculator_release"
test "$(systemctl show -p MainPID --value calculator)" = "$calculator_pid"
systemctl is-active --quiet web-address-book
stat -c '%a %U %n' /var/lib/web-address-book /var/lib/web-address-book/address_book.sqlite "$config/environment"
rm -f -- "$archive"
printf 'Deployed %s at %s/address-book/\n' "$version" "$origin"
