# VAMPIRE – API REST de gestion de machines virtuelles

## Description

VAMPIRE est une API REST développée en Python avec Flask permettant de gérer le cycle de vie de machines virtuelles (VM).

Elle fournit :

* une gestion complète des VM (CRUD)
* des actions système (power, snapshot, backup…)
* une authentification sécurisée via JWT
* des outils de test automatisés et manuels

---

## Objectifs du projet

* Implémenter une API REST conforme aux bonnes pratiques
* Gérer des ressources (machines virtuelles)
* Mettre en place une authentification JWT
* Tester les endpoints avec différents outils (script SH + Bruno)
* Valider le fonctionnement global de l’API

---

## Technologies utilisées

* Python 3
* Flask
* Flask-SQLAlchemy
* SQLite
* PyJWT
* Bash (script de test)
* Bruno CLI (tests API)
* Bruno Application (Visualisation en direct)

---

## Architecture

Client → API Flask → Base SQLite → Hyperviseur (simulé)

L’hyperviseur est simulé : les actions (`power_on`, `snapshot`, etc.) modifient l’état en base.

---

## Authentification (JWT)

L’API utilise des tokens JWT.

### Fonctionnement :

1. Inscription (`/api/register`)
2. Connexion (`/api/login`)
3. Récupération d’un token
4. Utilisation du token dans les requêtes protégées

### Header requis :

```http
Authorization: Bearer <token>
```

---

## Installation

### 1. Cloner le projet

```bash
git clone <repo_url>
cd vampire_project
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Configurer la clé secrète

```bash
export VAMPIRE_SECRET_KEY="votre_cle_secrete_longue"
```

### 4. Lancer l’API

```bash
python3 app.py
```

API disponible sur :

```
http://127.0.0.1:5000
```

---

## Modèle de données

### User

* id
* username
* password

### VM

* id
* uuid
* nom
* titre
* description
* cpu
* ram_go
* disques
* interfaces_reseau
* hyperviseur
* status
* owner_id

---

## Endpoints

### Authentification

| Méthode | Endpoint      | Description |
| ------- | ------------- | ----------- |
| POST    | /api/register | Inscription |
| POST    | /api/login    | Connexion   |

---

### VM (CRUD)

| Méthode | Endpoint      | Description |
| ------- | ------------- | ----------- |
| POST    | /api/vms      | Créer       |
| GET     | /api/vms      | Lister      |
| GET     | /api/vms/{id} | Détail      |
| PUT     | /api/vms/{id} | Modifier    |
| DELETE  | /api/vms/{id} | Supprimer   |

---

### Actions VM

| Méthode | Endpoint                |
| ------- | ----------------------- |
| POST    | /api/vms/{id}/power_on  |
| POST    | /api/vms/{id}/power_off |
| POST    | /api/vms/{id}/suspend   |
| POST    | /api/vms/{id}/snapshot  |
| POST    | /api/vms/{id}/backup    |
| POST    | /api/vms/{id}/migrate   |
| GET     | /api/vms/{id}/status    |

---

### Recherche

```http
GET /api/vms/search?min_cpu=2&hyperviseur=kvm
```

---

# Tests

## 🔹 1. Script automatique (Bash)

Le script `test_vampire.sh` permet de tester l’API de bout en bout.

### Fonctionnement :

* création d’un utilisateur
* login → récupération du token
* création d’une VM
* opérations complètes (CRUD + actions)
* suppression
* vérification finale

### Lancer :

```bash
chmod +x test_vampire.sh
./test_vampire.sh
```

### Résultat attendu :

```
✅ Tous les tests VAMPIRE sont passés avec succès.
```

-> Ce script valide entièrement le bon fonctionnement de l’API.

---

## 🔹 2. Tests avec Bruno (CLI)

Une collection Bruno est fournie :

```
bruno/VAMPIRE/
```

### Installation Bruno CLI :

```bash
npm install -g @usebruno/cli
```

### Lancer les tests :

```bash
cd bruno/VAMPIRE
bru run . --env local
```

---

### Particularité Bruno CLI

Dans ce projet :

* les variables dynamiques (`baseUrl`) ont été remplacées par une URL fixe
* la gestion automatique des variables (`token`, `vmId`) n’est pas active en CLI

Conséquence :

* certaines requêtes peuvent renvoyer `401` ou `404`
* mais l’exécution de la collection est bien validée

-> Bruno est utilisé ici pour démontrer :

* l’enchaînement des requêtes
* l’utilisation d’un outil de test API

---

## Comparaison des tests

| Outil     | Fonction                              |
| --------- | ------------------------------------- |
| Script SH | Validation complète et automatique    |
| Bruno     | Test manuel / exécution de collection |

---

## Bonnes pratiques appliquées

* API REST stateless
* séparation des responsabilités
* authentification JWT
* variables d’environnement pour la sécurité
* gestion des erreurs HTTP
* tests automatisés

---

## Remarques

* Hyperviseur simulé
* Flask en mode développement
* Bruno CLI limité pour la gestion des variables dynamiques

---

## Améliorations possibles

* Swagger / OpenAPI
* Docker
* pagination
* logs
* connexion à un vrai hyperviseur


---

## Note sur Bruno

Pour les tests avec Bruno CLI, la variable `{{baseUrl}}` a été remplacée par une URL fixe (`http://127.0.0.1:5000`) dans les fichiers `.bru`.

Cela corrige un problème de gestion des variables dans l’environnement CLI (erreur `ENOTFOUND`).

-> Aucun impact sur l’API ni sur le script de test.

Par alleurs, j'ai aussi tester Bruno en application pour visualiser le tests API en direct

---


## Auteur

Karim GASMI

M1 Systèmes, Réseaux & Cloud Computing – ESGI

API REST – M. Malinge
