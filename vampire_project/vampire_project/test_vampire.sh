#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
USERNAME="${USERNAME:-vampire_user}"
PASSWORD="${PASSWORD:-vampire_pass_42}"
TMP_DIR="$(mktemp -d)"
TOKEN=""
VM_ID=""

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Commande requise introuvable: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd jq

print_step() {
  echo
  echo "==> $1"
}

api_call() {
  local method="$1"
  local url="$2"
  local body="${3:-}"
  local outfile="$4"
  local statusfile="$5"
  shift 5 || true

  local headers=(-H "Accept: application/json")
  if [[ -n "$TOKEN" ]]; then
    headers+=(-H "Authorization: Bearer $TOKEN")
  fi

  if [[ -n "$body" ]]; then
    curl -sS -X "$method" "$url" \
      -H "Content-Type: application/json" \
      "${headers[@]}" \
      -d "$body" \
      -o "$outfile" -w "%{http_code}" > "$statusfile"
  else
    curl -sS -X "$method" "$url" \
      "${headers[@]}" \
      -o "$outfile" -w "%{http_code}" > "$statusfile"
  fi
}

assert_status() {
  local expected="$1"
  local status
  status="$(cat "$2")"
  if [[ "$status" != "$expected" ]]; then
    echo "Échec: code HTTP attendu=$expected obtenu=$status" >&2
    echo "Réponse:" >&2
    cat "$3" >&2
    echo >&2
    exit 1
  fi
}

assert_jq() {
  local expr="$1"
  local file="$2"
  if ! jq -e "$expr" "$file" >/dev/null; then
    echo "Échec: condition jq non satisfaite: $expr" >&2
    cat "$file" >&2
    echo >&2
    exit 1
  fi
}

print_step "Healthcheck"
api_call GET "$BASE_URL/health" "" "$TMP_DIR/health.json" "$TMP_DIR/health.status"
assert_status 200 "$TMP_DIR/health.status" "$TMP_DIR/health.json"
assert_jq '.status == "ok"' "$TMP_DIR/health.json"

echo "API joignable"

print_step "Inscription utilisateur"
REGISTER_PAYLOAD=$(jq -nc --arg username "$USERNAME" --arg password "$PASSWORD" '{username:$username,password:$password}')
api_call POST "$BASE_URL/api/register" "$REGISTER_PAYLOAD" "$TMP_DIR/register.json" "$TMP_DIR/register.status"
REGISTER_STATUS="$(cat "$TMP_DIR/register.status")"
if [[ "$REGISTER_STATUS" != "201" && "$REGISTER_STATUS" != "409" ]]; then
  echo "Échec: register doit répondre 201 ou 409, obtenu $REGISTER_STATUS" >&2
  cat "$TMP_DIR/register.json" >&2
  exit 1
fi
echo "Inscription OK (ou utilisateur déjà existant)"

print_step "Connexion"
api_call POST "$BASE_URL/api/login" "$REGISTER_PAYLOAD" "$TMP_DIR/login.json" "$TMP_DIR/login.status"
assert_status 200 "$TMP_DIR/login.status" "$TMP_DIR/login.json"
TOKEN="$(jq -r '.token' "$TMP_DIR/login.json")"
[[ -n "$TOKEN" && "$TOKEN" != "null" ]] || { echo "Token JWT absent" >&2; exit 1; }
echo "Token récupéré"

print_step "Création d'une VM"
CREATE_VM_PAYLOAD='{
  "nom": "P41_LINUX_RL_003",
  "titre": "RockyLinux 9.5 serveur Web projet 41",
  "description": "Serveur web Nginx",
  "cpu": 2,
  "ram_go": 4,
  "disques": [
    {"nom": "disk_1", "capacite_go": 10},
    {"nom": "disk_2", "capacite_go": 100}
  ],
  "interfaces_reseau": ["NIC_1", "NIC_2"],
  "hyperviseur": "qemu+kvm://172.17.3.2"
}'
api_call POST "$BASE_URL/api/vms" "$CREATE_VM_PAYLOAD" "$TMP_DIR/create_vm.json" "$TMP_DIR/create_vm.status"
assert_status 201 "$TMP_DIR/create_vm.status" "$TMP_DIR/create_vm.json"
VM_ID="$(jq -r '.vm.id' "$TMP_DIR/create_vm.json")"
assert_jq '.vm.nom == "P41_LINUX_RL_003"' "$TMP_DIR/create_vm.json"
echo "VM créée avec id=$VM_ID"

print_step "Lister les VM"
api_call GET "$BASE_URL/api/vms" "" "$TMP_DIR/list_vms.json" "$TMP_DIR/list_vms.status"
assert_status 200 "$TMP_DIR/list_vms.status" "$TMP_DIR/list_vms.json"
jq -e --argjson id "$VM_ID" '.vms | map(.id) | index($id) != null' "$TMP_DIR/list_vms.json" >/dev/null || { echo "Échec: la VM créée n'apparaît pas dans la liste" >&2; cat "$TMP_DIR/list_vms.json" >&2; exit 1; }
echo "La VM est visible dans la liste"

print_step "Lecture de la VM"
api_call GET "$BASE_URL/api/vms/$VM_ID" "" "$TMP_DIR/get_vm.json" "$TMP_DIR/get_vm.status"
assert_status 200 "$TMP_DIR/get_vm.status" "$TMP_DIR/get_vm.json"
jq -e --argjson id "$VM_ID" '.vm.id == $id' "$TMP_DIR/get_vm.json" >/dev/null || { echo "Échec: la VM retournée n'a pas le bon id" >&2; cat "$TMP_DIR/get_vm.json" >&2; exit 1; }
echo "Lecture OK"

print_step "Mise à jour complète de la VM"
UPDATE_VM_PAYLOAD='{
  "nom": "P41_LINUX_RL_003",
  "titre": "RockyLinux 9.5 serveur Web projet 41 - MAJ",
  "description": "Serveur web Nginx mis à jour",
  "cpu": 4,
  "ram_go": 8,
  "disques": [
    {"nom": "disk_1", "capacite_go": 20},
    {"nom": "disk_2", "capacite_go": 100}
  ],
  "interfaces_reseau": ["NIC_1", "NIC_2", "NIC_3"],
  "hyperviseur": "qemu+kvm://172.17.3.2",
  "statut": "stopped"
}'
api_call PUT "$BASE_URL/api/vms/$VM_ID" "$UPDATE_VM_PAYLOAD" "$TMP_DIR/update_vm.json" "$TMP_DIR/update_vm.status"
assert_status 200 "$TMP_DIR/update_vm.status" "$TMP_DIR/update_vm.json"
assert_jq '.vm.cpu == 4 and .vm.ram_go == 8' "$TMP_DIR/update_vm.json"
echo "Mise à jour OK"

print_step "Power on"
api_call POST "$BASE_URL/api/vms/$VM_ID/power_on" '{}' "$TMP_DIR/power_on.json" "$TMP_DIR/power_on.status"
assert_status 200 "$TMP_DIR/power_on.status" "$TMP_DIR/power_on.json"
assert_jq '.vm.statut == "running"' "$TMP_DIR/power_on.json"
echo "Power on OK"

print_step "Suspend"
api_call POST "$BASE_URL/api/vms/$VM_ID/suspend" '{}' "$TMP_DIR/suspend.json" "$TMP_DIR/suspend.status"
assert_status 200 "$TMP_DIR/suspend.status" "$TMP_DIR/suspend.json"
assert_jq '.vm.statut == "suspended"' "$TMP_DIR/suspend.json"
echo "Suspend OK"

print_step "Snapshot"
api_call POST "$BASE_URL/api/vms/$VM_ID/snapshot" '{"snapshot_name":"snap-1"}' "$TMP_DIR/snapshot.json" "$TMP_DIR/snapshot.status"
assert_status 201 "$TMP_DIR/snapshot.status" "$TMP_DIR/snapshot.json"
assert_jq '.vm.snapshots | length >= 1' "$TMP_DIR/snapshot.json"
echo "Snapshot OK"

print_step "Backup"
api_call POST "$BASE_URL/api/vms/$VM_ID/backup" '{}' "$TMP_DIR/backup.json" "$TMP_DIR/backup.status"
assert_status 200 "$TMP_DIR/backup.status" "$TMP_DIR/backup.json"
assert_jq '.vm.last_backup_at != null' "$TMP_DIR/backup.json"
echo "Backup OK"

print_step "Migration"
api_call POST "$BASE_URL/api/vms/$VM_ID/migrate" '{"hyperviseur":"qemu+kvm://172.17.3.99"}' "$TMP_DIR/migrate.json" "$TMP_DIR/migrate.status"
assert_status 200 "$TMP_DIR/migrate.status" "$TMP_DIR/migrate.json"
assert_jq '.to == "qemu+kvm://172.17.3.99"' "$TMP_DIR/migrate.json"
echo "Migration OK"

print_step "Lecture du statut"
api_call GET "$BASE_URL/api/vms/$VM_ID/status" "" "$TMP_DIR/status.json" "$TMP_DIR/status.status"
assert_status 200 "$TMP_DIR/status.status" "$TMP_DIR/status.json"
assert_jq '.statut == "suspended"' "$TMP_DIR/status.json"
echo "Statut OK"

print_step "Recherche de VM"
api_call GET "$BASE_URL/api/vms/search?min_cpu=4&hyperviseur=qemu%2Bkvm%3A%2F%2F172.17.3.99" "" "$TMP_DIR/search.json" "$TMP_DIR/search.status"
assert_status 200 "$TMP_DIR/search.status" "$TMP_DIR/search.json"
assert_jq '.count >= 1' "$TMP_DIR/search.json"
echo "Recherche OK"

print_step "Suppression"
api_call DELETE "$BASE_URL/api/vms/$VM_ID" "" "$TMP_DIR/delete.json" "$TMP_DIR/delete.status"
assert_status 200 "$TMP_DIR/delete.status" "$TMP_DIR/delete.json"
assert_jq '.message == "VM deleted successfully"' "$TMP_DIR/delete.json"
echo "Suppression OK"

print_step "Vérification de la suppression"
api_call GET "$BASE_URL/api/vms/$VM_ID" "" "$TMP_DIR/get_deleted.json" "$TMP_DIR/get_deleted.status"
assert_status 404 "$TMP_DIR/get_deleted.status" "$TMP_DIR/get_deleted.json"
echo "La VM n'existe plus"

echo
echo "✅ Tous les tests VAMPIRE sont passés avec succès."
