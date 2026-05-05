# 🚀 Guide de Déploiement — Let's Meet Morocco

## Option 1 : Render.com (Recommandé — Gratuit)

### Étapes
1. **Crée un compte** sur [render.com](https://render.com)
2. **Mets le code sur GitHub** (dépôt privé)
3. **New → Web Service** → connecter le repo
4. **Paramètres :**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
5. **Variables d'environnement** (dans l'onglet Environment) :
   ```
   SECRET_KEY=<génère avec: python -c "import secrets; print(secrets.token_hex(32))">
   FLASK_ENV=production
   MAIL_USERNAME=tonapp@gmail.com
   MAIL_PASSWORD=ton-app-password
   ```
6. **Deploy** → ton app est en ligne !

---

## Option 2 : Railway.app (Alternatif — Gratuit)

1. Crée un compte sur [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Add variables d'environnement
4. Ajoute un service PostgreSQL depuis Railway

---

## Configuration Email (Mot de passe oublié)

### Gmail
1. Va sur [myaccount.google.com](https://myaccount.google.com)
2. Sécurité → Validation en 2 étapes → Activer
3. Sécurité → Mots de passe des applications → Créer
4. Copie le mot de passe de 16 caractères
5. Dans les variables d'environnement :
   ```
   MAIL_USERNAME=tonapp@gmail.com
   MAIL_PASSWORD=xxxx xxxx xxxx xxxx
   ```

---

## Checklist avant lancement

- [ ] `FLASK_ENV=production` dans les variables d'environnement
- [ ] `SECRET_KEY` générée et unique (jamais la valeur par défaut)
- [ ] Email configuré (MAIL_USERNAME + MAIL_PASSWORD)
- [ ] Testé sur mobile (responsive)
- [ ] Compte admin créé et fonctionnel
- [ ] Au moins 2-3 activités de test créées
- [ ] Page /landing vérifiée

---

## Domaine personnalisé

Sur Render : Settings → Custom Domains → ajouter `letsmeetmorocco.com`
HTTPS est automatique via Let's Encrypt.

---

## Commandes utiles en local

```bash
# Installer les dépendances
pip install -r requirements.txt

# Lancer en développement
python app.py

# Lancer comme en production (avec gunicorn)
gunicorn app:app --bind 0.0.0.0:5000

# Générer une clé secrète
python -c "import secrets; print(secrets.token_hex(32))"
```
