# 🇲🇦 Let's Meet Morocco

> Application sociale marocaine pour organiser et rejoindre des activités — sport, culture, sorties — et rencontrer des gens près de toi.

[![Flask](https://img.shields.io/badge/Flask-3.0-green)](https://flask.palletsprojects.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-3.1-orange)](https://sqlalchemy.org)

---

## 🎯 Description

**Let's Meet Morocco** connecte des personnes qui veulent partager des activités dans leurs villes. Tu publies une activité, des gens rejoignent, vous vous rencontrez. Simple, gratuit, authentique.

Projet académique développé à l'**ENCG Marrakech** (École Nationale de Commerce et de Gestion).

---

## ⚡ Technologies utilisées

| Technologie | Rôle |
|---|---|
| **Flask 3.0** | Framework web backend |
| **SQLAlchemy** | ORM base de données |
| **SQLite** (dev) / **PostgreSQL** (prod) | Base de données |
| **HTML/CSS/JS** | Frontend responsive |
| **Leaflet.js** | Carte interactive |
| **Chart.js** | Graphiques admin |
| **Werkzeug** | Hachage mots de passe |
| **Flask-Mail** | Emails (récupération MDP) |
| **Gunicorn** | Serveur production |

---

## 🚀 Installation en 4 étapes

```bash
# 1. Cloner le projet
git clone https://github.com/ton-username/letsmeetmorocco.git
cd letsmeetmorocco/letsmeet3

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer l'environnement (optionnel)
cp .env.example .env
# Éditer .env avec tes valeurs

# 4. Lancer l'application
python app.py
```

Ouvre http://127.0.0.1:5000 dans ton navigateur.

---

## 👤 Comptes de test

| Rôle | Email | Mot de passe |
|---|---|---|
| Utilisateur | youssef@mail.com | 1234 |
| Utilisateur | salma@mail.com | 1234 |
| Utilisateur | nadia@mail.com | 1234 |
| Utilisateur | mehdi@mail.com | 1234 |
| Admin | admin@letsmeet.ma | admin123 |

URL Admin : http://127.0.0.1:5000/admin/login

---

## ✨ Fonctionnalités principales

### Utilisateurs
- Inscription multi-étapes avec centres d'intérêt visuels
- Connexion sécurisée + récupération mot de passe par email
- Profil avec bannière, badges, statistiques, réputation
- Statut en ligne en temps réel 🟢

### Activités
- Créer/rejoindre des activités (sport, café, culture, sorties...)
- Carte interactive style Google Maps avec géocodage précis
- Filtres par type, ville, date
- Countdown timer avant chaque activité

### Social
- Système d'amis (demande/accepter/refuser)
- Messagerie privée (DM) style WhatsApp
- Chat de groupe par activité (polling temps réel 3s)
- Réactions emoji sur les messages
- Inviter des amis à une activité

### Gamification
- Badges (Organisateur, Sociable, Top membre...)
- Streak de participation 🔥
- Classement / Leaderboard
- XP et niveaux (Débutant → Légende)
- Défis mensuels

### Admin (URL cachée)
- Dashboard avec statistiques et graphiques
- Validation/blocage des comptes
- Gestion des signalements
- Export CSV
- Notifications broadcast

---

## 🏗️ Structure du projet

```
letsmeet3/
├── app.py              # Application principale (67 routes, 15 modèles)
├── config.py           # Configurations dev/production
├── requirements.txt    # Dépendances Python
├── .env.example        # Template variables d'environnement
├── DEPLOIEMENT.md      # Guide de déploiement Render.com
├── static/
│   ├── css/style.css   # Styles responsives (mobile + desktop)
│   ├── js/main.js      # JavaScript frontend
│   ├── img/logo.png    # Logo de l'application
│   └── sw.js           # Service Worker (PWA)
└── templates/          # 33 templates HTML Jinja2
```

---

## 🌐 Déploiement (Render.com)

```bash
# Variables d'environnement sur Render :
SECRET_KEY=<clé-aléatoire-sécurisée>
FLASK_ENV=production
DATABASE_URL=<fourni-automatiquement-par-render-postgresql>
ADMIN_EMAIL=admin@letsmeet.ma
ADMIN_PASSWORD=<mot-de-passe-sécurisé>
MAIL_USERNAME=<gmail>
MAIL_PASSWORD=<app-password>
```

Commande de démarrage : `gunicorn app:app`

---

## 👥 Équipe

Développé par **Ahmed Chaouki Chalabi** — Étudiant 3ème année ENCG Marrakech

---

## 📄 Licence

Projet académique — ENCG Marrakech 2025-2026
