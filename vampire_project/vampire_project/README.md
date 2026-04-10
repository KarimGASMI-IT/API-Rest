# VAMPIRE - API REST pour manager des VM

Projet Flask réalisé pour l'évaluation **VAMPIRE**.

## Contenu

- `app.py` : API REST complète
- `requirements.txt` : dépendances Python
- `test_vampire.sh` : script shell de validation automatique
- `bruno/` : collection Bruno pour tester l'API et gérer le token JWT

## Choix de conception

- **Flask** pour exposer les endpoints REST
- **SQLAlchemy + SQLite** pour stocker utilisateurs et VM
- **JWT** pour protéger les routes
- **Chaque utilisateur ne voit que ses VM**
- **JSON uniquement**

## Endpoints

### Authentification

- `POST /api/register`
- `POST /api/login`

### VM

- `POST /api/vms`
- `GET /api/vms`
- `GET /api/vms/<id>`
- `PUT /api/vms/<id>`
- `PATCH /api/vms/<id>`
- `DELETE /api/vms/<id>`
- `GET /api/vms/search`
- `GET /api/vms/<id>/status`
- `POST /api/vms/<id>/power_on`
- `POST /api/vms/<id>/power_off`
- `POST /api/vms/<id>/suspend`
- `POST /api/vms/<id>/snapshot`
- `POST /api/vms/<id>/backup`
- `POST /api/vms/<id>/migrate`

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancement

```bash
python3 app.py
```

L'API écoute sur `http://127.0.0.1:5000`.

## Validation automatique

Dans un autre terminal :

```bash
chmod +x test_vampire.sh
./test_vampire.sh
```

Le script utilise `curl` et `jq`.

## Utilisation dans Bruno

1. Ouvrir le dossier `bruno/VAMPIRE`
2. Vérifier les variables de collection :
   - `baseUrl`
   - `username`
   - `password`
3. Exécuter dans l'ordre :
   - Register
   - Login
   - Create VM
   - List VMs
   - Get VM by ID
   - Update VM
   - Power On VM
   - Suspend VM
   - Snapshot VM
   - Backup VM
   - Migrate VM
   - Get VM Status
   - Search VMs
   - Delete VM

La requête **Login** enregistre le JWT dans la variable `token`, qui est ensuite réutilisée dans les routes protégées avec :

```http
Authorization: Bearer {{token}}
```

## Exemple de données VM

```json
{
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
}
```
