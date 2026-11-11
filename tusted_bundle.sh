#!/usr/bin/env bash
# Consolidates all trusted .cer / .pem files from $TRUSTED_CERT_DIR
# into a single PEM bundle used by Apache for client authentication.

set -euo pipefail

TRUSTED_CERT_DIR="${TRUSTED_CERT_DIR:?TRUSTED_CERT_DIR is not set}"
TRUSTED_BUNDLE="${TRUSTED_BUNDLE:-/etc/httpd/conf/trusted/ca-bundle.pem}"

if [[ ! -d "$TRUSTED_CERT_DIR" ]]; then
    echo "ERROR: $TRUSTED_CERT_DIR is not a directory" >&2
    exit 1
fi

mkdir -p "$(dirname "$TRUSTED_BUNDLE")"
TMP_BUNDLE="$(mktemp "${TRUSTED_BUNDLE}.XXXXXX")"
trap 'rm -f "$TMP_BUNDLE"' EXIT

declare -A SEEN
count=0

while IFS= read -r -d '' file; do
    # .cer files may be PEM (text) or DER (binary); detect and convert.
    if grep -q "BEGIN CERTIFICATE" "$file"; then
        pem_src="$(openssl x509 -in "$file" -outform PEM 2>/dev/null || true)"
        # A file may contain several certs (chain); handle them all
        if [[ $(grep -c "BEGIN CERTIFICATE" "$file") -gt 1 ]]; then
            pem_src="$(awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/' "$file" | tr -d '\r')"
        fi
    else
        pem_src="$(openssl x509 -inform DER -in "$file" -outform PEM 2>/dev/null || true)"
    fi

    if [[ -z "$pem_src" ]]; then
        echo "WARN: skipping invalid certificate file: $file" >&2
        continue
    fi

    # Split into individual certs, validate and de-duplicate by fingerprint
    tmpdir="$(mktemp -d)"
    printf '%s\n' "$pem_src" | awk -v d="$tmpdir" '
        /BEGIN CERTIFICATE/ {n++; f=sprintf("%s/c%03d.pem", d, n)}
        f {print > f}
        /END CERTIFICATE/ {close(f); f=""}'

    for c in "$tmpdir"/c*.pem; do
        [[ -e "$c" ]] || continue
        fp="$(openssl x509 -in "$c" -noout -fingerprint -sha256 2>/dev/null || true)"
        if [[ -z "$fp" ]]; then
            echo "WARN: invalid cert inside $file, skipped" >&2
            continue
        fi
        if [[ -n "${SEEN[$fp]:-}" ]]; then
            continue
        fi
        SEEN[$fp]=1
        subj="$(openssl x509 -in "$c" -noout -subject | sed 's/^subject= *//')"
        {
            echo "# Source: $(basename "$file") | $subj"
            cat "$c"
        } >> "$TMP_BUNDLE"
        count=$((count + 1))
    done
    rm -rf "$tmpdir"
done < <(find "$TRUSTED_CERT_DIR" -maxdepth 1 -type f \
            \( -iname '*.cer' -o -iname '*.pem' -o -iname '*.crt' \) -print0 | sort -z)

if [[ $count -eq 0 ]]; then
    echo "ERROR: no valid certificates found in $TRUSTED_CERT_DIR" >&2
    exit 1
fi

chmod 644 "$TMP_BUNDLE"
mv -f "$TMP_BUNDLE" "$TRUSTED_BUNDLE"     # atomic replace
trap - EXIT

echo "Trusted bundle created: $TRUSTED_BUNDLE ($count certificates)"
