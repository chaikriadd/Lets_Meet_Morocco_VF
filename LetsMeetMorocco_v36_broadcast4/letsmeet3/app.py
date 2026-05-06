#!/usr/bin/env python3
"""
Let's Meet Morocco — Application Flask
Plateforme sociale pour étudiants ENCG Marrakech
Version: v34 STABLE
"""

import logging

# Configuration logs structurés
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement depuis .env si présent
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optionnel

from flask import (Flask, render_template, request, redirect,
                   session, flash, url_for, jsonify, abort)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os, json, secrets, hashlib
from functools import wraps

# Flask-Compress (compression gzip des réponses)

# Flask-Mail (optionnel — import seulement ici, init après app)
try:
    from flask_mail import Mail, Message as MailMessage
    MAIL_ENABLED = True
except ImportError:
    MailMessage = None
    MAIL_ENABLED = False
    print("⚠️  Flask-Mail non installé. pip install flask-mail pour activer les emails.")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "letsmeetmorocco2025-dev-only")
try:
    from flask_compress import Compress
    Compress(app)
    logger.info("Flask-Compress activé")
except ImportError:
    logger.warning("Flask-Compress non installé. pip install flask-compress")
# Initialiser Flask-Mail APRÈS app (fix bug init avant création de app)
if MAIL_ENABLED:
    try:
        mail = Mail(app)
        logger.info("Flask-Mail initialisé avec succès")
    except Exception as e:
        mail = None
        MAIL_ENABLED = False
        logger.warning(f"Flask-Mail erreur init: {e}")
else:
    mail = None
# En production: export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Configuration sécurité session
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 86400 * 7  # 7 jours

# Configuration email (Flask-Mail)
app.config["MAIL_SERVER"]   = os.environ.get("MAIL_SERVER",   "smtp.gmail.com")
app.config["MAIL_PORT"]     = int(os.environ.get("MAIL_PORT", "587"))
app.config["MAIL_USE_TLS"]  = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME", "noreply@letsmeetmorocco.com")

# Mode DEBUG depuis env (False en production)
app.config["DEBUG"] = os.environ.get("FLASK_ENV", "development") == "development" 

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ── Base de données: PostgreSQL en production, SQLite en dev ──
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL:
    # Render fournit postgres:// mais SQLAlchemy 1.4+ nécessite postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    logger.info("Base de données: PostgreSQL (production)")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "letsmeet.db")
    logger.info("Base de données: SQLite (développement local)")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB max

# Créer le dossier uploads automatiquement s'il n'existe pas
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

# Flask-Migrate (optionnel — migrations DB)
try:
    from flask_migrate import Migrate
    migrate_ext = Migrate(app, db)
    logger.info("Flask-Migrate activé")
except ImportError:
    logger.warning("Flask-Migrate non installé. pip install flask-migrate")

# ============================================================
# CONSTANTES
# ============================================================

ACTIVITES_LISTE = {
    "Activités sportives":  ["Football","Basketball","Padel","Tennis","Volleyball",
                              "Course à pied","Natation","Yoga","Salle de sport",
                              "Vélo","Marche"],
    "Sorties & détente":    ["Café entre étudiants","Sortie restaurant","Glace",
                              "Snack","Cinéma","Jeux (PlayStation, jeux de société)"],
    "Activités sociales":   ["Explorer Marrakech","Visiter des lieux culturels",
                              "Shopping","Regarder le coucher de soleil"],
}

TOUTES_ACTIVITES = [a for cat in ACTIVITES_LISTE.values() for a in cat]
VILLES = ["Marrakech","Casablanca","Rabat","Fès","Tanger","Agadir","Meknès","Oujda"]
AVATAR_COLORS = ["#E53935","#8E24AA","#1E88E5","#00897B","#F4511E","#6D4C41","#0097A7","#689F38"]

# ============================================================
# MODÈLES
# ============================================================

amis = db.Table("amis",
    db.Column("user_id",  db.Integer, db.ForeignKey("user.id")),
    db.Column("ami_id",   db.Integer, db.ForeignKey("user.id"))
)

participants = db.Table("participants",
    db.Column("user_id",     db.Integer, db.ForeignKey("user.id")),
    db.Column("activity_id", db.Integer, db.ForeignKey("activity.id"))
)

bloques = db.Table("bloques",
    db.Column("bloqueur_id", db.Integer, db.ForeignKey("user.id")),
    db.Column("bloque_id",   db.Integer, db.ForeignKey("user.id"))
)


class User(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    nom              = db.Column(db.String(50),  nullable=False)
    prenom           = db.Column(db.String(50),  nullable=False)
    email            = db.Column(db.String(120), unique=True, nullable=False, index=True)
    mot_de_passe     = db.Column(db.String(200), nullable=False)
    age              = db.Column(db.Integer,     nullable=False)
    date_naissance   = db.Column(db.String(20),  default="")
    ville            = db.Column(db.String(50),  nullable=False)
    centres_interet  = db.Column(db.String(500), default="")
    bio              = db.Column(db.String(300), default="")
    photo            = db.Column(db.String(200), default="")
    reputation       = db.Column(db.Float,   default=4.5)
    est_bloque       = db.Column(db.Boolean, default=False)
    est_valide       = db.Column(db.Boolean, default=True)    # auto-validation activée
    email_verifie    = db.Column(db.Boolean, default=False)  # Email confirmé par lien
    profil_prive     = db.Column(db.Boolean, default=False)
    accepte_messages = db.Column(db.Boolean, default=True)
    date_inscription = db.Column(db.String(20), default=lambda: date.today().strftime("%d/%m/%Y"))
    # Champs ENCG Marrakech
    filiere          = db.Column(db.String(60),  default='')   # GF, MK, RH...
    annee_etude      = db.Column(db.String(10),  default='')   # 1A, 2A...
    num_etudiant     = db.Column(db.String(20),  default='')   # Numéro étudiant
    est_encg_verifie = db.Column(db.Boolean,     default=False) # Email @etu.uiz.ac.ma
    derniere_activite = db.Column(db.DateTime,   nullable=True) # Statut en ligne
    notif_ami        = db.Column(db.Boolean,     default=True)
    notif_activite   = db.Column(db.Boolean,     default=True)
    notif_message    = db.Column(db.Boolean,     default=True)
    notif_system     = db.Column(db.Boolean,     default=True)

    activites_creees  = db.relationship("Activity", backref="createur", lazy=True,
                                         foreign_keys="Activity.createur_id")
    messages          = db.relationship("Message",  backref="auteur",   lazy=True)
    reviews_donnees   = db.relationship("Review",   backref="auteur",   lazy=True,
                                         foreign_keys="Review.auteur_id")
    notifications     = db.relationship("Notification", backref="destinataire", lazy=True)
    demandes_envoyees = db.relationship("DemandeAmi", foreign_keys="DemandeAmi.envoyeur_id",
                                         backref="envoyeur", lazy=True)
    demandes_recues   = db.relationship("DemandeAmi", foreign_keys="DemandeAmi.receveur_id",
                                         backref="receveur", lazy=True)
    utilisateurs_bloques = db.relationship("User", secondary=bloques,
                                            primaryjoin=id==bloques.c.bloqueur_id,
                                            secondaryjoin=id==bloques.c.bloque_id,
                                            lazy=True)

    def verifier_mdp(self, pwd):
        return check_password_hash(self.mot_de_passe, pwd)

    def get_centres(self):
        return [c.strip() for c in self.centres_interet.split(",") if c.strip()]

    def est_en_ligne(self):
        """True si actif dans les 5 dernières minutes"""
        if not self.derniere_activite:
            return False
        delta = (datetime.now() - self.derniere_activite).total_seconds()
        return delta < 300  # 5 minutes

    def statut_activite(self):
        """Retourne un texte lisible du statut"""
        if not self.derniere_activite:
            return "Jamais connecté"
        delta = (datetime.now() - self.derniere_activite).total_seconds()
        if delta < 300:
            return "En ligne"
        elif delta < 3600:
            mins = int(delta // 60)
            return f"Vu il y a {mins} min"
        elif delta < 86400:
            hours = int(delta // 3600)
            return f"Vu il y a {hours}h"
        else:
            days = int(delta // 86400)
            return f"Vu il y a {days} jour{'s' if days > 1 else ''}"

    def get_avatar_color(self):
        idx = sum(ord(c) for c in self.nom) % len(AVATAR_COLORS)
        return AVATAR_COLORS[idx]

    def get_photo_url(self):
        if self.photo and os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], self.photo)):
            return url_for("static", filename=f"uploads/{self.photo}")
        return None

    def nb_activites_creees(self):
        return Activity.query.filter_by(createur_id=self.id).count()

    def nb_participations(self):
        return len(self.activites_rejointes)


class Activity(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    titre         = db.Column(db.String(100), nullable=False)
    type_activite = db.Column(db.String(50),  nullable=False)
    date_activite = db.Column(db.String(20),  nullable=False)
    heure         = db.Column(db.String(10),  nullable=False)
    lieu          = db.Column(db.String(150), nullable=False)
    latitude      = db.Column(db.Float, default=31.6295)
    longitude     = db.Column(db.Float, default=-7.9811)
    description   = db.Column(db.Text,  default="")
    nb_max        = db.Column(db.Integer, default=10)
    statut        = db.Column(db.String(20), default="En attente", index=True)
    est_privee    = db.Column(db.Boolean,  default=False)
    age_min       = db.Column(db.Integer,  default=0)
    age_max       = db.Column(db.Integer,  default=99)  # En attente/Ouverte/Complète/Terminée
    createur_id   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date_creation = db.Column(db.String(20),
                               default=lambda: datetime.now().strftime("%d/%m/%Y %H:%M"))

    participants_list = db.relationship("User", secondary=participants,
                                         backref=db.backref("activites_rejointes", lazy=True))
    messages  = db.relationship("Message", backref="activite", lazy=True,
                                 cascade="all, delete-orphan")
    reviews   = db.relationship("Review",  backref="activite", lazy=True,
                                 cascade="all, delete-orphan")

    def est_complete(self):
        return len(self.participants_list) >= self.nb_max

    def nb_participants(self):
        return len(self.participants_list)

    def pourcentage(self):
        return min(int(len(self.participants_list) / self.nb_max * 100), 100)


class Message(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    contenu     = db.Column(db.Text,    nullable=False)
    heure       = db.Column(db.String(16),
                             default=lambda: datetime.now().strftime("%d/%m %H:%M"))
    user_id     = db.Column(db.Integer, db.ForeignKey("user.id"),     nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    signale     = db.Column(db.Boolean, default=False)


class Review(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    note        = db.Column(db.Float,  nullable=False)
    commentaire = db.Column(db.String(300), default="")
    auteur_id   = db.Column(db.Integer, db.ForeignKey("user.id"),     nullable=False)
    cible_id    = db.Column(db.Integer, db.ForeignKey("user.id"),     nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    date        = db.Column(db.String(20),
                             default=lambda: date.today().strftime("%d/%m/%Y"))
    cible       = db.relationship("User", foreign_keys=[cible_id])


class Notification(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    type_notif   = db.Column(db.String(50),  nullable=False)
    message      = db.Column(db.String(300), nullable=False)
    lien         = db.Column(db.String(200), default="")
    est_lue      = db.Column(db.Boolean, default=False)
    date         = db.Column(db.String(20),
                              default=lambda: datetime.now().strftime("%d/%m %H:%M"))
    user_id      = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class DemandeAmi(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    envoyeur_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receveur_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    statut      = db.Column(db.String(20), default="en_attente")  # en_attente/accepte/refuse
    date        = db.Column(db.String(20),
                             default=lambda: date.today().strftime("%d/%m/%Y"))


class Signalement(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    type_cible   = db.Column(db.String(20), nullable=False)  # user/activite/message
    cible_id     = db.Column(db.Integer, nullable=False)
    motif        = db.Column(db.String(300), nullable=False)
    statut       = db.Column(db.String(20), default="en_attente")
    rapporteur_id= db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date         = db.Column(db.String(20),
                              default=lambda: date.today().strftime("%d/%m/%Y"))
    rapporteur   = db.relationship("User", foreign_keys=[rapporteur_id])



class BroadcastLog(db.Model):
    """Historique des broadcasts admin"""
    __tablename__ = "broadcast_log"
    id            = db.Column(db.Integer,    primary_key=True)
    message       = db.Column(db.Text,       nullable=False)
    cible         = db.Column(db.String(50), default="tous")
    ville_cible   = db.Column(db.String(50), default="")
    avec_email    = db.Column(db.Boolean,    default=False)
    nb_envoyes    = db.Column(db.Integer,    default=0)
    date_envoi    = db.Column(db.DateTime,   default=datetime.now)

    def date_str(self):
        return self.date_envoi.strftime("%d/%m/%Y à %H:%M") if self.date_envoi else "—"


class AdminLog(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    action  = db.Column(db.String(300), nullable=False)
    date    = db.Column(db.String(20),
                         default=lambda: datetime.now().strftime("%d/%m/%Y %H:%M"))


# ============================================================
# NOUVEAUX MODÈLES v13
# ============================================================

class Reaction(db.Model):
    """Réactions emoji sur les messages du chat"""
    id         = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("message.id"), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"),    nullable=False)
    emoji      = db.Column(db.String(10), nullable=False)
    date       = db.Column(db.String(20),
                            default=lambda: datetime.now().strftime("%d/%m %H:%M"))
    message    = db.relationship("Message", backref="reactions", lazy=True)
    user       = db.relationship("User",    backref="reactions_donnees", lazy=True)

class Favori(db.Model):
    """Activités sauvegardées comme favoris"""
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("user.id"),     nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    date        = db.Column(db.String(20),
                             default=lambda: date.today().strftime("%d/%m/%Y"))
    user     = db.relationship("User",     backref="favoris", lazy=True)
    activite = db.relationship("Activity", backref="favori_par", lazy=True)

class FeedEvent(db.Model):
    """Événements du feed d'activité en temps réel"""
    id      = db.Column(db.Integer, primary_key=True)
    type_ev = db.Column(db.String(30), nullable=False)  # join/create/complete
    texte   = db.Column(db.String(200), nullable=False)
    icon    = db.Column(db.String(10), default="🎯")
    lien    = db.Column(db.String(200), default="")
    date    = db.Column(db.String(20),
                         default=lambda: datetime.now().strftime("%d/%m %H:%M"))

class Streak(db.Model):
    """Streak de participation des utilisateurs"""
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    valeur       = db.Column(db.Integer, default=0)
    derniere_act = db.Column(db.String(20), default="")
    user         = db.relationship("User", backref="streak_info", lazy=True)

class EmailVerificationToken(db.Model):
    """Tokens de vérification d'adresse email"""
    __tablename__ = "email_verification_token"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token      = db.Column(db.String(100), unique=True, nullable=False)
    expire_at  = db.Column(db.DateTime, nullable=False)
    utilise    = db.Column(db.Boolean, default=False)
    utilisateur = db.relationship("User", backref="email_tokens", foreign_keys=[user_id])

    def est_valide(self):
        return not self.utilise and datetime.now() < self.expire_at


class PasswordResetToken(db.Model):
    """Tokens de réinitialisation de mot de passe"""
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token      = db.Column(db.String(64), unique=True, nullable=False)
    expire_at  = db.Column(db.String(30), nullable=False)
    utilise    = db.Column(db.Boolean, default=False)
    user       = db.relationship("User", backref="reset_tokens", lazy=True)

    @staticmethod
    def generer(user_id):
        from datetime import timedelta
        # Invalider les anciens tokens
        PasswordResetToken.query.filter_by(user_id=user_id, utilise=False).update({"utilise": True})
        token = secrets.token_urlsafe(48)
        expire = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        t = PasswordResetToken(user_id=user_id, token=token, expire_at=expire)
        db.session.add(t)
        return token

    def est_valide(self):
        from datetime import timedelta
        return (not self.utilise and
                datetime.strptime(self.expire_at, "%Y-%m-%d %H:%M:%S") > datetime.now())


class CheckIn(db.Model):
    """Check-in 'Je suis là !' pour une activité"""
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("user.id"),     nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    heure       = db.Column(db.String(8),
                             default=lambda: datetime.now().strftime("%H:%M"))
    user     = db.relationship("User",     backref="checkins", lazy=True)
    activite = db.relationship("Activity", backref="checkins", lazy=True)


class MessagePrive(db.Model):
    """Messages privés entre deux utilisateurs"""
    id           = db.Column(db.Integer, primary_key=True)
    expediteur_id= db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    destinataire_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    contenu      = db.Column(db.Text, nullable=False)
    est_lu       = db.Column(db.Boolean, default=False)
    date         = db.Column(db.String(20),
                              default=lambda: datetime.now().strftime("%d/%m/%Y"))
    heure        = db.Column(db.String(8),
                              default=lambda: datetime.now().strftime("%H:%M"))
    expediteur   = db.relationship("User", foreign_keys=[expediteur_id],
                                    backref="messages_envoyes")
    destinataire = db.relationship("User", foreign_keys=[destinataire_id],
                                    backref="messages_recus")

# ============================================================
# HELPERS
# ============================================================

def notifier(user_id, message, type_notif="info", lien=""):
    n = Notification(user_id=user_id, message=message,
                     type_notif=type_notif, lien=lien)
    db.session.add(n)

def log_admin(action):
    db.session.add(AdminLog(action=action))

def send_email(to, subject, body_html):
    """Envoie un email - silencieux si Flask-Mail non configuré"""
    if not MAIL_ENABLED or not app.config.get("MAIL_USERNAME"):
        print(f"[EMAIL SIMULÉ] À: {to} | Sujet: {subject}")
        return False
    try:
        msg = MailMessage(subject, recipients=[to], html=body_html)
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[EMAIL ERREUR] {e}")
        return False


def send_verification_email(user):
    """Envoie un email de vérification avec lien ou code à 6 chiffres"""
    import secrets, string
    # Générer un code à 6 chiffres + token URL
    code = ''.join(secrets.choice(string.digits) for _ in range(6))
    token_str = secrets.token_urlsafe(32)
    expire = datetime.now() + timedelta(hours=24)

    # Supprimer les anciens tokens non utilisés
    EmailVerificationToken.query.filter_by(user_id=user.id, utilise=False).delete()

    tok = EmailVerificationToken(user_id=user.id, token=token_str,
                                  expire_at=expire, utilise=False)
    db.session.add(tok)
    # Stocker le code dans le token (on réutilise le champ token = "code:token_url")
    tok.token = f"{code}:{token_str}"
    db.session.commit()

    # URL dynamique selon l'environnement
    base_url = os.environ.get("APP_URL", "http://127.0.0.1:5000").rstrip("/")
    verify_url = f"{base_url}/verify-email/{token_str}"

    html = f"""
    <div style="font-family:'DM Sans',Arial,sans-serif;max-width:520px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">
      <div style="background:#0D2B12;padding:28px 32px;text-align:center">
        <h1 style="color:#fff;font-family:Arial,sans-serif;font-size:22px;margin:0">
          🎓 Let's Meet Morocco
        </h1>
        <p style="color:rgba(255,255,255,.7);margin:6px 0 0;font-size:14px">ENCG Marrakech</p>
      </div>
      <div style="padding:32px">
        <h2 style="color:#0D2B12;font-size:20px;margin:0 0 10px">Bienvenue {user.prenom} ! 👋</h2>
        <p style="color:#555;font-size:14px;line-height:1.7;margin:0 0 24px">
          Confirme ton adresse email pour activer ton compte et rejoindre la communauté ENCG Marrakech.
        </p>

        <!-- Code à 6 chiffres -->
        <div style="text-align:center;margin-bottom:24px">
          <p style="font-size:13px;color:#888;margin-bottom:10px">Ton code de vérification :</p>
          <div style="display:inline-block;background:#F0FBF1;border:2px solid #2DB54C;border-radius:14px;padding:16px 32px">
            <span style="font-family:'Courier New',monospace;font-size:36px;font-weight:700;
                         letter-spacing:10px;color:#0D2B12">{code}</span>
          </div>
          <p style="font-size:12px;color:#aaa;margin-top:8px">Valide 24 heures</p>
        </div>

        <!-- Bouton lien direct -->
        <div style="text-align:center;margin-bottom:24px">
          <p style="font-size:13px;color:#888;margin-bottom:10px">Ou clique directement :</p>
          <a href="{verify_url}"
             style="display:inline-block;background:linear-gradient(135deg,#1a5c2a,#2DB54C);
                    color:#fff;text-decoration:none;padding:14px 32px;border-radius:12px;
                    font-weight:600;font-size:15px;box-shadow:0 4px 14px rgba(45,181,76,.3)">
            ✅ Vérifier mon email
          </a>
        </div>

        <div style="background:#FFF8E1;border-left:4px solid #F5A623;border-radius:8px;padding:12px 16px;font-size:13px;color:#92400e">
          ⚠️ Si tu n'as pas créé de compte sur Let's Meet Morocco, ignore cet email.
        </div>
      </div>
      <div style="background:#F9FAFB;padding:16px 32px;text-align:center;border-top:1px solid #eee">
        <p style="font-size:12px;color:#aaa;margin:0">Let's Meet Morocco — Communauté ENCG Marrakech</p>
      </div>
    </div>
    """

    sent = send_email(user.email, "✅ Vérifie ton email — Let's Meet Morocco", html)
    return code, token_str, sent


def send_email_notification(recipient, subject, title, message, cta_text=None, cta_url=None, icon="🔔"):
    """Template email générique pour toutes les notifications"""
    if not recipient or not getattr(recipient, 'email_verifie', False):
        return  # Seulement emails vérifiés
    if not getattr(recipient, 'notif_system', True):
        return  # Respecter préférences notifs
    
    _base = os.environ.get("APP_URL", "http://127.0.0.1:5000").rstrip("/")
    
    cta_html = ""
    if cta_text and cta_url:
        full_url = cta_url if cta_url.startswith("http") else f"{_base}{cta_url}"
        cta_html = f"""
        <div style="text-align:center;margin-top:24px">
          <a href="{full_url}" style="display:inline-block;background:linear-gradient(135deg,#1a5c2a,#2DB54C);
             color:#fff;text-decoration:none;padding:13px 28px;border-radius:12px;
             font-weight:600;font-size:14px;box-shadow:0 4px 14px rgba(45,181,76,.3)">
            {cta_text}
          </a>
        </div>"""
    
    html = f"""
    <div style="font-family:'DM Sans',Arial,sans-serif;max-width:520px;margin:0 auto;
                background:#fff;border-radius:16px;overflow:hidden;
                box-shadow:0 4px 24px rgba(0,0,0,.08)">
      <div style="background:#0D2B12;padding:24px 32px;text-align:center">
        <div style="font-size:32px;margin-bottom:6px">{icon}</div>
        <h1 style="color:#fff;font-family:Arial,sans-serif;font-size:18px;margin:0">
          Let's Meet Morocco
        </h1>
        <p style="color:rgba(255,255,255,.6);margin:4px 0 0;font-size:12px">ENCG Marrakech</p>
      </div>
      <div style="padding:28px 32px">
        <h2 style="color:#0D2B12;font-size:18px;margin:0 0 12px">{title}</h2>
        <p style="color:#555;font-size:14px;line-height:1.7;margin:0">{message}</p>
        {cta_html}
      </div>
      <div style="background:#F9FAFB;padding:14px 32px;text-align:center;border-top:1px solid #eee">
        <p style="font-size:11px;color:#aaa;margin:0">
          Let's Meet Morocco · 
          <a href="{_base}/edit_profile" style="color:#2DB54C">Gérer mes préférences</a>
        </p>
      </div>
    </div>"""
    
    try:
        send_email(recipient.email, subject, html)
    except Exception as e:
        logger.warning(f"Email notification failed for {recipient.email}: {e}")


def send_dm_notification_email(recipient, sender, message_preview):
    """Envoie une notification email quand un DM est reçu"""
    if not recipient.email_verifie:
        return  # Seulement pour les emails vérifiés
    _base = os.environ.get("APP_URL", "http://127.0.0.1:5000").rstrip("/")
    html = f"""
    <div style="font-family:'DM Sans',Arial,sans-serif;max-width:520px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">
      <div style="background:#0D2B12;padding:20px 32px;display:flex;align-items:center;gap:12px">
        <div style="width:40px;height:40px;border-radius:50%;background:#E8541A;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;color:#fff;flex-shrink:0">
          {sender.prenom[0]}{sender.nom[0]}
        </div>
        <div>
          <h2 style="color:#fff;font-size:16px;margin:0">💬 Nouveau message</h2>
          <p style="color:rgba(255,255,255,.6);font-size:12px;margin:2px 0 0">Let's Meet Morocco</p>
        </div>
      </div>
      <div style="padding:24px 32px">
        <p style="color:#555;font-size:14px;margin:0 0 16px">
          <strong style="color:#0D2B12">{sender.prenom} {sender.nom}</strong> t'a envoyé un message :
        </p>
        <div style="background:#F0FBF1;border-left:4px solid #2DB54C;border-radius:8px;padding:14px 18px;font-size:14px;color:#1a1a1a;font-style:italic;line-height:1.6">
          "{message_preview[:200]}{'...' if len(message_preview) > 200 else ''}"
        </div>
        <div style="text-align:center;margin-top:24px">
          <a href="{_base}/messages/{sender.id}"
             style="display:inline-block;background:linear-gradient(135deg,#1a5c2a,#2DB54C);
                    color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;
                    font-weight:600;font-size:14px">
            💬 Répondre sur Let's Meet Morocco
          </a>
        </div>
      </div>
      <div style="background:#F9FAFB;padding:12px 32px;text-align:center;border-top:1px solid #eee">
        <p style="font-size:11px;color:#aaa;margin:0">
          Pour ne plus recevoir ces emails, modifie tes préférences dans <a href="http://127.0.0.1:5000/edit_profile" style="color:#2DB54C">les paramètres</a>.
        </p>
      </div>
    </div>
    """
    send_email(recipient.email,
               f"💬 {sender.prenom} {sender.nom} t'a envoyé un message — Let's Meet Morocco",
               html)


def add_feed(type_ev, texte, icon="🎯", lien=""):
    """Ajouter un événement au feed en temps réel"""
    ev = FeedEvent(type_ev=type_ev, texte=texte, icon=icon, lien=lien)
    db.session.add(ev)

def update_streak(user_id):
    """Met à jour le streak d'un utilisateur"""
    today = date.today().strftime("%d/%m/%Y")
    streak = Streak.query.filter_by(user_id=user_id).first()
    if not streak:
        streak = Streak(user_id=user_id, valeur=1, derniere_act=today)
        db.session.add(streak)
    else:
        from datetime import timedelta
        yesterday = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")
        if streak.derniere_act == today:
            pass
        elif streak.derniere_act == yesterday:
            streak.valeur += 1
        else:
            streak.valeur = 1
        streak.derniere_act = today

# ── SÉCURITÉ ─────────────────────────────────────────────────

# Simple in-memory rate limiter (no extra lib needed)
_rate_store = {}

def rate_limit(key, max_attempts=5, window=60):
    """Retourne True si la limite est dépassée"""
    import time
    now = time.time()
    bucket = _rate_store.get(key, [])
    bucket = [t for t in bucket if now - t < window]
    if len(bucket) >= max_attempts:
        return True
    bucket.append(now)
    _rate_store[key] = bucket
    return False

def generate_csrf():
    """Génère ou récupère le token CSRF de la session"""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]

def verify_csrf():
    """Vérifie le token CSRF sur les POST"""
    if request.method == "POST":
        token = request.form.get("csrf_token","") or request.headers.get("X-CSRF-Token","")
        if not token or token != session.get("csrf_token",""):
            abort(403)

# Injecte csrf_token dans tous les templates
@app.after_request
def add_security_headers(response):
    """Ajoute les headers de sécurité à toutes les réponses"""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # CSP basique - permet les CDN utilisés (Leaflet, Chart.js, fonts Google)
    if not app.config.get("DEBUG"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.before_request
def check_user_exists():
    """Vérifie session + met à jour derniere_activite (statut en ligne)"""
    uid = session.get("user_id")
    if uid:
        # Ignorer les fichiers statiques
        if request.path.startswith("/static"):
            return
        user = User.query.get(uid)
        if not user:
            session.clear()
            public = ["/login", "/register", "/landing", "/logout",
                      "/forgot-password", "/static"]
            if not any(request.path.startswith(p) for p in public) and "/reset-password/" not in request.path:
                flash("Session expirée. Reconnecte-toi.", "info")
                return redirect("/login")
        else:
            # Tracker l'activité pour le statut en ligne
            user.derniere_activite = datetime.now()
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()


@app.context_processor
def inject_csrf():
    return {"csrf_token": generate_csrf()}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            flash("Connecte-toi pour accéder à cette page.", "error")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated

def allowed_file_secure(filename, fileobj):
    """Vérifie extension + magic bytes"""
    if "." not in filename:
        return False
    ext = filename.rsplit(".",1)[1].lower()
    if ext not in {"png","jpg","jpeg","gif","webp"}:
        return False
    # Vérification magic bytes
    header = fileobj.read(16)
    fileobj.seek(0)
    magic = {
        b"\x89PNG": "png",
        b"\xff\xd8\xff": "jpg",
        b"GIF8": "gif",
        b"RIFF": "webp",
    }
    for sig, ftype in magic.items():
        if header.startswith(sig):
            return True
    return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def badge_type(t):
    t = t.lower()
    if any(x in t for x in ["vélo","course","football","basket","natation",
                              "yoga","sport","marche","salle"]):
        return "badge-sport"
    if any(x in t for x in ["café","restaurant","glace","snack",
                              "cinéma","jeux","détente"]):
        return "badge-detente"
    return "badge-culture"

def coords_ville(ville):
    coords = {
        "Marrakech": (31.6295, -7.9811), "Casablanca": (33.5731, -7.5898),
        "Rabat":     (34.0209, -6.8416), "Fès":        (34.0181, -5.0078),
        "Tanger":    (35.7595, -5.8340), "Agadir":     (30.4202, -9.5981),
        "Meknès":    (33.8935, -5.5473), "Oujda":      (34.6805, -1.9076),
    }
    return coords.get(ville, (31.6295, -7.9811))


def geocode_adresse(adresse, ville="Marrakech"):
    """Géocode une adresse précise via Nominatim (OpenStreetMap) — gratuit"""
    import urllib.request, urllib.parse, json as _json
    try:
        # Construire la requête avec ville + Maroc pour plus de précision
        query = f"{adresse}, {ville}, Maroc"
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "ma"
        })
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "LetsMeetMorocco/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"[GEOCODE] Erreur pour '{adresse}': {e}")
    # Fallback: centre de la ville
    return coords_ville(ville)


@app.route("/api/geocode")
def api_geocode():
    """API de géocodage appelée depuis le formulaire JS"""
    adresse = request.args.get("q", "").strip()
    ville   = request.args.get("ville", "Marrakech").strip()
    if not adresse:
        return jsonify({"ok": False})
    lat, lon = geocode_adresse(adresse, ville)
    return jsonify({"ok": True, "lat": lat, "lon": lon})

app.jinja_env.globals.update(badge_type=badge_type, enumerate=enumerate)

# ============================================================
# INIT DB
# ============================================================

def init_db():
    db.create_all()
    if User.query.count() == 0:
        logger.info("Création des données de démonstration...")

        # ── 8 utilisateurs marocains réalistes ──
        users_data = [
            ("Alami",    "Youssef", "youssef@mail.com", "1234", 22, "Marrakech",
             "Football,Café entre étudiants,Yoga,Basketball",
             "Étudiant à l'ENCG Marrakech, passionné de sport et de rencontres ! 🏈"),
            ("Benali",   "Salma",   "salma@mail.com",   "1234", 24, "Casablanca",
             "Yoga,Cinéma,Shopping,Café entre étudiants",
             "Designer freelance, amatrice de culture et de bien-être. ✨"),
            ("Chraibi",  "Omar",    "omar@mail.com",    "1234", 27, "Rabat",
             "Course à pied,Explorer la ville,Marche,Salle de sport",
             "Ingénieur, runner passionné par sa ville. 🏃‍♂️"),
            ("Idrissi",  "Nadia",   "nadia@mail.com",   "1234", 23, "Marrakech",
             "Yoga,Regarder le coucher de soleil,Visiter des lieux culturels",
             "Artiste et voyageuse dans l'âme. J'adore découvrir les trésors cachés du Maroc 🌸"),
            ("Tazi",     "Mehdi",   "mehdi@mail.com",   "1234", 26, "Fès",
             "Football,Basketball,Salle de sport,Course à pied",
             "Coach sportif certifié. Prêt à vous motiver ! 💪"),
            ("Ouali",    "Fatima",  "fatima@mail.com",  "1234", 21, "Marrakech",
             "Café entre étudiants,Cinéma,Shopping,Glace",
             "Étudiante en droit, toujours partante pour une sortie sympa 😊"),
            ("Bensouda", "Amine",   "amine@mail.com",   "1234", 29, "Casablanca",
             "Explorer la ville,Sortie restaurant,Visiter des lieux culturels",
             "Architecte, explorateur urbain et gastronome. 🏛️"),
            ("Hajji",    "Leila",   "leila@mail.com",   "1234", 25, "Rabat",
             "Natation,Vélo,Marche,Regarder le coucher de soleil",
             "Ingénieure environnement, fan de plein air et d'activités outdoor. 🌊"),
        ]
        users = []
        for nom, prenom, email, pwd, age, ville, centres, bio in users_data:
            lat, lon = coords_ville(ville)
            u = User(nom=nom, prenom=prenom, email=email,
                     mot_de_passe=generate_password_hash(pwd),
                     age=age, ville=ville, centres_interet=centres,
                     bio=bio, est_valide=True, email_verifie=True, reputation=round(3.8 + (ord(prenom[0]) % 12) * 0.1, 1))
            db.session.add(u)
            users.append(u)
        db.session.commit()

        # ── 10 activités réalistes dans plusieurs villes ──
        coords_m = coords_ville("Marrakech")
        coords_c = coords_ville("Casablanca")
        coords_r = coords_ville("Rabat")
        coords_f = coords_ville("Fès")

        acts_data = [
            dict(titre="Match de Football Amical", type_activite="Football",
                 date_activite="10/06/2026", heure="16:00",
                 lieu="Terrain Guéliz, Marrakech", lat=coords_m[0]+0.01, lon=coords_m[1]+0.01,
                 description="Match 5v5 amical sur terrain synthétique. Tous niveaux bienvenus, l'important c'est de s'amuser ! Amenez vos chaussures de sport 👟",
                 nb_max=10, createur_id=1),
            dict(titre="Café Étudiant ENCG", type_activite="Café entre étudiants",
                 date_activite="12/06/2026", heure="10:30",
                 lieu="Café Milano, Guéliz, Marrakech", lat=coords_m[0]+0.005, lon=coords_m[1]-0.01,
                 description="Rencontre détendue entre étudiants. On parle études, projets, vie étudiante... dans une ambiance sympa ☕",
                 nb_max=8, createur_id=6),
            dict(titre="Footing Matinal Majorelle", type_activite="Course à pied",
                 date_activite="13/06/2026", heure="07:00",
                 lieu="Jardin Majorelle, Marrakech", lat=coords_m[0]-0.008, lon=coords_m[1]+0.015,
                 description="Footing de 5km autour de Majorelle. Rythme modéré, idéal pour les débutants comme les confirmés ! 🌅",
                 nb_max=12, createur_id=3),
            dict(titre="Yoga Matinal en Plein Air", type_activite="Yoga",
                 date_activite="14/06/2026", heure="08:00",
                 lieu="Parc Lalla Hasna, Marrakech", lat=coords_m[0]-0.015, lon=coords_m[1]+0.008,
                 description="Séance de yoga en plein air pour bien démarrer la journée. Apportez votre tapis ! 🧘‍♀️",
                 nb_max=15, createur_id=4),
            dict(titre="Basketball 3v3 Casa", type_activite="Basketball",
                 date_activite="15/06/2026", heure="18:00",
                 lieu="Terrain Ain Diab, Casablanca", lat=coords_c[0]+0.01, lon=coords_c[1]-0.015,
                 description="3v3 entre amis à Casablanca. Venez chauds ! 🏀 On fait des équipes équilibrées sur place.",
                 nb_max=6, createur_id=5),
            dict(titre="Sortie Restaurant Méditerranéen", type_activite="Sortie restaurant",
                 date_activite="16/06/2026", heure="20:00",
                 lieu="Restaurant Le Tobsil, Médina, Marrakech", lat=coords_m[0]+0.003, lon=coords_m[1]+0.003,
                 description="Dîner découverte dans un cadre magnifique de la Médina. Ambiance trad-moderne, réservation groupée. 🍽️",
                 nb_max=8, createur_id=7),
            dict(titre="Padel ENCG — Niveau Intermédiaire", type_activite="Padel",
                 date_activite="12/06/2026", heure="16:00",
                 lieu="Club Padel Atlas, Gueliz, Marrakech",
                 lat=coords_m[0]+0.009, lon=coords_m[1]-0.011,
                 description="Partie de padel entre etudiants ENCG ! 2v2 sur terrain couvert. Raquettes disponibles 🎾",
                 nb_max=4, createur_id=5),
            dict(titre="Coucher de Soleil Agafay", type_activite="Regarder le coucher de soleil",
                 date_activite="17/06/2026", heure="18:30",
                 lieu="Désert d'Agafay, Marrakech", lat=coords_m[0]-0.05, lon=coords_m[1]-0.03,
                 description="Moment magique au coucher du soleil dans le désert d'Agafay à 30min de Marrakech. Covoiturage organisé 🌅✨",
                 nb_max=10, createur_id=4),
            dict(titre="Vélo le long du Bou Regreg", type_activite="Vélo",
                 date_activite="18/06/2026", heure="09:00",
                 lieu="Bord du Bou Regreg, Rabat", lat=coords_r[0]+0.005, lon=coords_r[1]+0.01,
                 description="Balade à vélo le long du fleuve entre Rabat et Salé. 15km aller-retour, piste cyclable. Vélos à louer sur place 🚴",
                 nb_max=12, createur_id=8),
            dict(titre="Exploration Médina de Fès", type_activite="Visiter des lieux culturels",
                 date_activite="19/06/2026", heure="10:00",
                 lieu="Bab Bou Jeloud, Fès", lat=coords_f[0]+0.003, lon=coords_f[1]+0.002,
                 description="Visite guidée de la Médina de Fès, classée UNESCO. On découvre les souks, les tanneries et l'Université Al-Qarawiyyin 🏛️",
                 nb_max=10, createur_id=5),
            dict(titre="Natation Piscine Olympique", type_activite="Natation",
                 date_activite="20/06/2026", heure="07:30",
                 lieu="Piscine Olympique de Rabat", lat=coords_r[0]-0.01, lon=coords_r[1]+0.005,
                 description="Séance de natation en groupe. Niveau intermédiaire. 30 longueurs ensemble puis brunch léger après ! 🏊‍♂️",
                 nb_max=8, createur_id=8),
        ]
        acts = []
        for d in acts_data:
            a = Activity(
                titre=d["titre"], type_activite=d["type_activite"],
                date_activite=d["date_activite"], heure=d["heure"],
                lieu=d["lieu"], latitude=d["lat"], longitude=d["lon"],
                description=d["description"], nb_max=d["nb_max"],
                createur_id=d["createur_id"], statut="Ouverte"
            )
            db.session.add(a)
            acts.append(a)
        db.session.commit()

        # ── Participations croisées réalistes ──
        participations = [
            (1, [2, 4, 6]),   # Football: Salma, Nadia, Fatima
            (2, [1, 3, 8]),   # Café: Youssef, Omar, Leila
            (3, [5, 8]),      # Footing: Mehdi, Leila
            (4, [2, 6, 8]),   # Yoga: Salma, Fatima, Leila
            (5, [1, 3]),      # Basketball: Youssef, Omar
            (6, [2, 4, 7]),   # Restaurant: Salma, Nadia, Amine
            (7, [1, 2, 6]),   # Coucher soleil: Youssef, Salma, Fatima
            (8, [3, 5]),      # Vélo: Omar, Mehdi
        ]
        all_acts = Activity.query.all()
        all_users = User.query.all()
        for act_idx, user_ids in participations:
            if act_idx <= len(all_acts):
                act = all_acts[act_idx - 1]
                for uid in user_ids:
                    if uid <= len(all_users):
                        u = all_users[uid - 1]
                        if u not in act.participants_list:
                            act.participants_list.append(u)
        db.session.commit()

        # ── Messages de chat réalistes ──
        chat_msgs = [
            # Football
            (1, 1, "09:00", "Salut tout le monde ! Match confirmé pour 16h 🔥"),
            (1, 2, "09:10", "Je suis là ! J'amène le ballon ⚽"),
            (1, 4, "09:25", "Parfait ! On est combien au total ?"),
            (1, 1, "09:30", "On est 4 pour l'instant, il en faut encore 2 de chaque côté"),
            (1, 6, "10:00", "Je peux venir avec mon frère si ça aide 😊"),
            # Café ENCG
            (2, 6, "08:00", "Bonjour ! Hâte de rencontrer tout le monde ☕"),
            (2, 1, "08:15", "Super initiative ! On peut parler du projet de fin d'études aussi"),
            (2, 3, "08:30", "Je serai là avec 5min de retard, gardez-moi une place 😄"),
            # Yoga
            (4, 4, "07:00", "Bonjour les warriors du matin 🧘‍♀️ On commence à 8h pile"),
            (4, 2, "07:10", "J'arrive ! Premier yoga en plein air pour moi 😍"),
            (4, 6, "07:45", "Quel endroit magnifique pour une séance !"),
        ]
        for act_id, user_id, heure, contenu in chat_msgs:
            if act_id <= len(all_acts):
                db.session.add(Message(
                    contenu=contenu, heure=heure,
                    user_id=user_id, activity_id=act_id
                ))
        db.session.commit()

        # ── Avis croisés ──
        reviews = [
            (2, 1, 1, 5, "Super organisateur, match très sympa !"),
            (3, 1, 2, 5, "Youssef est top, très accueillant"),
            (1, 6, 2, 4, "Belle activité, bonne ambiance"),
            (8, 3, 3, 5, "Omar connaît parfaitement son parcours"),
        ]
        for auteur_id, cible_id, act_id, note, commentaire in reviews:
            db.session.add(Review(
                auteur_id=auteur_id, cible_id=cible_id,
                activity_id=act_id, note=note, commentaire=commentaire,
                date=date.today().strftime("%d/%m/%Y")
            ))
        # Update reputations
        for u in User.query.all():
            avis = Review.query.filter_by(cible_id=u.id).all()
            if avis:
                u.reputation = round(sum(a.note for a in avis) / len(avis), 1)
        db.session.commit()

        # ── Feed events initiaux ──
        for act in Activity.query.limit(5).all():
            db.session.add(FeedEvent(
                type_ev="create",
                texte=f"Nouvelle activité : {act.titre} à {act.lieu.split(',')[0]}",
                icon="🎯",
                lien=f"/activity/{act.id}"
            ))
        db.session.commit()

        logger.info(f"✅ {User.query.count()} utilisateurs, {Activity.query.count()} activités créés")

# ============================================================
# ROUTES AUTH
# ============================================================

@app.route("/login", methods=["GET","POST"])
def login():
    error = ""
    if request.method == "POST":
        verify_csrf()
        # Rate limiting: max 10 tentatives/minute par IP
        ip = request.remote_addr or "unknown"
        if rate_limit(f"login:{ip}", max_attempts=10, window=60):
            error = "Trop de tentatives. Attendez 1 minute."
            return render_template("login.html", error=error)
        email = request.form.get("email","").strip()
        pwd   = request.form.get("password","").strip()
        # Login utilisateur UNIQUEMENT (admin a sa propre URL /admin/login)
        user = User.query.filter_by(email=email).first()
        if user and user.verifier_mdp(pwd):
            if user.est_bloque:
                error = "Compte bloqué. Contacte l'administrateur."
            elif not user.est_valide:
                error = "Compte en attente de validation par l'administrateur."
            else:
                session["user_id"] = user.id
                session["prenom"] = user.prenom
                session["nom"] = user.nom
                flash(f"Bienvenue, {user.prenom} ! 🎉", "success")
                return redirect("/")
        else:
            error = "Email ou mot de passe incorrect."
    return render_template("login.html", error=error)


@app.route("/register", methods=["GET","POST"])
def register():
    error = ""
    if request.method == "POST":
        verify_csrf()
        ip = request.remote_addr or "unknown"
        if rate_limit(f"register:{ip}", max_attempts=5, window=300):
            return render_template("register.html", error="Trop d'inscriptions. Attendez 5 minutes.", villes=VILLES, max_date=max_date, activites_liste=ACTIVITES_LISTE)
        prenom     = request.form.get("prenom","").strip()
        nom        = request.form.get("nom","").strip()
        email      = request.form.get("email","").strip()
        pwd        = request.form.get("password","").strip()
        cpwd       = request.form.get("confirm_password","").strip()
        date_naiss = request.form.get("date_naissance","").strip()
        ville      = request.form.get("ville","").strip()
        centres    = request.form.getlist("centres")
        bio        = request.form.get("bio","").strip()

        # Calcul âge depuis date naissance
        age = 0
        if date_naiss:
            try:
                dn = datetime.strptime(date_naiss, "%Y-%m-%d")
                age = (datetime.today() - dn).days // 365
            except:
                age = 0

        if age < 18:
            error = "Vous devez avoir au moins 18 ans."
        elif len(pwd) < 6:
            error = "Le mot de passe doit contenir au moins 6 caractères."
        elif cpwd and pwd != cpwd:
            error = "Les mots de passe ne correspondent pas."
        elif User.query.filter_by(email=email).first():
            error = "Cet email est déjà utilisé."
        elif not all([prenom, nom, email, pwd, ville]):
            error = "Veuillez remplir tous les champs obligatoires."
        elif len(centres) < 5:
            error = "Veuillez choisir au moins 5 centres d'intérêt."
        else:
            # Auto-validation : tous les comptes sont validés automatiquement
            # Pour activer la validation manuelle par admin, mettre est_valide=False
            u = User(nom=nom, prenom=prenom, email=email,
                     mot_de_passe=generate_password_hash(pwd),
                     age=age, date_naissance=date_naiss, ville=ville,
                     centres_interet=",".join(centres), bio=bio,
                     est_valide=True)  # ✅ Auto-validation activée
            db.session.add(u)
            db.session.commit()

            # Upload photo si fournie (optionnelle)
            if "photo" in request.files:
                f = request.files["photo"]
                if f and f.filename and allowed_file(f.filename):
                    try:
                        filename = "user_" + str(u.id) + ".jpg"
                        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)
                        try:
                            from PIL import Image
                            img = Image.open(f)
                            img = img.convert("RGB")
                            img.thumbnail((400, 400), Image.LANCZOS)
                            img.save(save_path, "JPEG", quality=85, optimize=True)
                        except ImportError:
                            f.seek(0)
                            f.save(save_path)
                        u.photo = filename
                        db.session.commit()
                    except Exception:
                        pass

            log_admin(f"Nouveau compte créé (auto-validé) : {prenom} {nom} ({email})")
            db.session.commit()

            # Envoyer email de vérification
            try:
                code, token_str, sent = send_verification_email(u)
                session["pending_verify_uid"]   = u.id
                session["pending_verify_email"] = u.email
                if sent:
                    # Email envoyé réellement → page de vérification
                    flash(f"📧 Email envoyé à {u.email}. Saisis le code à 6 chiffres !", "info")
                    return redirect("/verify-email")
                else:
                    # Mode DEV : email simulé → montrer le code dans la page
                    print(f"\n{'='*50}")
                    print(f"[DEV] CODE VÉRIFICATION pour {u.email}: {code}")
                    print(f"[DEV] Lien direct: {base_url}/verify-email/{token_str}")
                    print(f"{'='*50}\n")
                    flash(f"🛠️ Mode DEV — Code de vérification : {code} (affiché car email non configuré)", "info")
                    return redirect("/verify-email")
            except Exception as e:
                logger.error(f"Email verification error: {e}")
                # Fallback: auto-vérifier si erreur critique
                u.email_verifie = True
                db.session.commit()
                session["user_id"] = u.id
                session["prenom"]  = u.prenom
                session["nom"]     = u.nom
                flash(f"Bienvenue {prenom} ! Ton compte est prêt 🎉", "success")
                return redirect("/")

    from datetime import date as _date
    max_date = (_date.today().replace(year=_date.today().year - 18)).strftime("%Y-%m-%d")
    return render_template("register.html", error=error,
                           villes=VILLES, activites_liste=ACTIVITES_LISTE,
                           max_date=max_date)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ============================================================
# ROUTES UTILISATEUR
# ============================================================

@app.route("/landing")
def landing():
    """Page d accueil publique — visible avant connexion"""
    if session.get("user_id"):
        return redirect("/")
    nb_users = User.query.filter_by(est_valide=True).count()
    nb_acts  = Activity.query.filter_by(statut="Ouverte").count()
    return render_template("landing.html", nb_users=nb_users, nb_acts=nb_acts)


@app.route("/")
def index():
    if not session.get("user_id"):
        return redirect("/landing")
    user = User.query.get(session["user_id"])
    if not user:
        session.clear()
        flash("Session expirée. Reconnecte-toi.", "error")
        return redirect("/login")
    # Bloquer l'accès si compte bloqué ou désactivé
    if user.est_bloque:
        session.pop("user_id", None)
        session.pop("prenom", None)
        session.pop("nom", None)
        flash("Ton compte a été suspendu. Contacte l'administrateur.", "error")
        return redirect("/login")
    recentes = Activity.query.filter_by(statut="Ouverte").order_by(Activity.id.desc()).limit(3).all()
    proches  = Activity.query.filter(Activity.lieu.contains(user.ville),
                                      Activity.statut=="Ouverte").all()
    nb_notifs = Notification.query.filter_by(user_id=user.id, est_lue=False).count()
    demandes  = DemandeAmi.query.filter_by(receveur_id=user.id, statut="en_attente").count()
    # Activités tendance = les plus remplies
    toutes = Activity.query.filter_by(statut="Ouverte").all()
    tendances = sorted(toutes, key=lambda a: a.pourcentage(), reverse=True)[:3]
    # Activités "Maintenant" = démarrent dans < 2h
    from datetime import timedelta
    maintenant_dt = datetime.now()
    dans_2h = maintenant_dt + timedelta(hours=2)
    maintenant_acts = []
    for a in toutes:
        try:
            dp = a.date_activite.split("/")
            tp = (a.heure or "00:00").split(":")
            dt_act = datetime(int(dp[2]), int(dp[1]), int(dp[0]), int(tp[0]), int(tp[1]))
            if maintenant_dt <= dt_act <= dans_2h:
                maintenant_acts.append(a)
        except Exception:
            pass
    # Type counts for category pills
    from collections import Counter
    type_counts = dict(Counter([a.type_activite for a in toutes]))

    return render_template("index.html", user=user, recentes=recentes,
                           proches=proches, nb_notifs=nb_notifs,
                           demandes=demandes, tendances=tendances,
                           maintenant_acts=maintenant_acts,
                           type_counts=type_counts,
                           nb_users=User.query.filter_by(est_valide=True).count(),
                           nb_acts=Activity.query.filter_by(statut="Ouverte").count())


@app.route("/activities")
def liste_activites():
    if not session.get("user_id"): return redirect("/login")
    ft  = request.args.get("type","")
    fv  = request.args.get("ville","")
    fkw = request.args.get("q","")
    query = Activity.query.filter_by(statut="Ouverte")
    if ft:  query = query.filter(Activity.type_activite.contains(ft))
    if fv:  query = query.filter(Activity.lieu.contains(fv))
    if fkw: query = query.filter(
        (Activity.titre.contains(fkw)) | (Activity.description.contains(fkw)))
    page = request.args.get("page", 1, type=int)
    per_page = 12
    total = query.count()
    acts = query.order_by(Activity.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template("activities.html", acts=acts,
                           types=TOUTES_ACTIVITES, villes=VILLES,
                           ft=ft, fv=fv, fkw=fkw,
                           page=page, total_pages=total_pages, total=total)


@app.route("/map")
def carte():
    if not session.get("user_id"): return redirect("/login")
    acts = Activity.query.filter_by(statut="Ouverte").all()
    acts_json = [{"id":a.id,"titre":a.titre,"lieu":a.lieu,
                  "lat":a.latitude,"lon":a.longitude,
                  "type":a.type_activite,"date":a.date_activite,
                  "nb":a.nb_participants(),"max":a.nb_max} for a in acts]
    return render_template("map.html", acts_json=json.dumps(acts_json))


@app.route("/activity/<int:aid>", methods=["GET","POST"])
def detail_activite(aid):
    if not session.get("user_id"): return redirect("/login")
    act  = Activity.query.get_or_404(aid)
    user = User.query.get(session["user_id"])

    if request.method == "POST":
        verify_csrf()
        action = request.form.get("action")

        if action == "rejoindre":
            if not act.est_complete() and user not in act.participants_list:
                act.participants_list.append(user)
                if act.est_complete(): act.statut = "Complète"
                db.session.commit()
                notifier(act.createur_id,
                         f"{user.prenom} a rejoint « {act.titre} »",
                         "info", f"/activity/{act.id}")
                add_feed("join", f"{user.prenom} {user.nom[0]}. a rejoint {act.titre}",
                         "🙋", f"/activity/{act.id}")
                update_streak(user.id)
                db.session.commit()
                # Email notification au créateur
                try:
                    createur = User.query.get(act.createur_id)
                    if createur and createur.id != user.id:
                        send_email_notification(
                            recipient=createur,
                            subject=f"🚀 {user.prenom} a rejoint ton activité — Let's Meet Morocco",
                            title=f"{user.prenom} {user.nom} a rejoint ton activité !",
                            message=f"<strong>{user.prenom} {user.nom}</strong> vient de rejoindre <strong>{act.titre}</strong>. Il y a maintenant <strong>{act.nb_participants()}/{act.nb_max} participants</strong>.",
                            cta_text="👥 Voir les participants",
                            cta_url=f"/activity/{act.id}",
                            icon="🚀"
                        )
                except Exception as e:
                    logger.warning(f"Email notif rejoindre failed: {e}")
                flash("Tu as rejoint l'activité ! 🎉", "success")
            else:
                flash("Activité complète ou déjà inscrit.", "error")

        elif action == "quitter":
            if user in act.participants_list and user.id != act.createur_id:
                act.participants_list.remove(user)
                act.statut = "Ouverte"
                db.session.commit()
                flash("Tu as quitté l'activité.", "info")

        elif action == "message":
            if not user.accepte_messages and user.id != act.createur_id:
                flash("Tu as désactivé les messages.", "error")
            else:
                contenu = request.form.get("message","").strip()
                if contenu:
                    db.session.add(Message(contenu=contenu,
                                           user_id=user.id, activity_id=act.id))
                    db.session.commit()

        elif action == "noter":
            note = float(request.form.get("note", 4))
            comm = request.form.get("commentaire","").strip()
            existing = Review.query.filter_by(auteur_id=user.id,
                                               activity_id=act.id).first()
            if not existing:
                r = Review(note=note, commentaire=comm,
                           auteur_id=user.id, cible_id=act.createur_id,
                           activity_id=act.id)
                db.session.add(r)
                # Recalculer réputation
                toutes = Review.query.filter_by(cible_id=act.createur_id).all()
                act.createur.reputation = round(
                    (sum(x.note for x in toutes) + note) / (len(toutes) + 1), 1)
                notifier(act.createur_id,
                         f"{user.prenom} t'a donné {note}⭐ pour « {act.titre} »",
                         "success")
                db.session.commit()
                flash("Note envoyée ! ⭐", "success")
            else:
                flash("Tu as déjà noté cette activité.", "error")

        elif action == "signaler":
            motif = request.form.get("motif","").strip()
            if motif:
                db.session.add(Signalement(type_cible="activite", cible_id=act.id,
                                            motif=motif, rapporteur_id=user.id))
                db.session.commit()
                flash("Activité signalée à l'administrateur.", "info")

        return redirect(f"/activity/{aid}")

    est_participant = user in act.participants_list
    est_createur    = user.id == act.createur_id
    deja_note       = Review.query.filter_by(auteur_id=user.id, activity_id=act.id).first()
    return render_template("activity_detail.html", act=act, user=user,
                           est_participant=est_participant,
                           est_createur=est_createur, deja_note=deja_note)


@app.route("/create_activity", methods=["GET","POST"])
def create_activity():
    if not session.get("user_id"): return redirect("/login")
    if request.method == "POST":
        verify_csrf()
        ville = request.form.get("ville_activite", "Marrakech")
        lieu  = request.form.get("lieu", "")
        # Essayer de géocoder l'adresse précise d'abord
        lat_form = request.form.get("lat", "").strip()
        lon_form = request.form.get("lon", "").strip()
        if lat_form and lon_form:
            try:
                lat, lon = float(lat_form), float(lon_form)
            except ValueError:
                lat, lon = geocode_adresse(lieu, ville)
        elif lieu:
            lat, lon = geocode_adresse(lieu, ville)
        else:
            lat, lon = coords_ville(ville)
        act = Activity(
            titre=request.form.get("titre",""),
            type_activite=request.form.get("type_activite",""),
            date_activite=request.form.get("date_activite",""),
            heure=request.form.get("heure",""),
            lieu=lieu,
            latitude=lat, longitude=lon,
            description=request.form.get("description",""),
            nb_max=int(request.form.get("nb_max", 10)),
            createur_id=session["user_id"], statut="Ouverte"
        )
        db.session.add(act)
        db.session.commit()
        add_feed("create", f"Nouvelle activité : {act.titre} à {act.lieu}",
                 "🎯", f"/activity/{act.id}")
        update_streak(session["user_id"])
        db.session.commit()
        flash(f"Activité « {act.titre} » créée ! 🎉", "success")
        return redirect(f"/activity/{act.id}")
    return render_template("create_activity.html",
                           types=TOUTES_ACTIVITES, villes=VILLES)


@app.route("/edit_activity/<int:aid>", methods=["GET","POST"])
def edit_activity(aid):
    if not session.get("user_id"): return redirect("/login")
    act = Activity.query.get_or_404(aid)
    if act.createur_id != session["user_id"]:
        flash("Action non autorisée.", "error")
        return redirect("/activities")
    if request.method == "POST":
        verify_csrf()
        act.titre         = request.form.get("titre", act.titre)
        act.type_activite = request.form.get("type_activite", act.type_activite)
        act.date_activite = request.form.get("date_activite", act.date_activite)
        act.heure         = request.form.get("heure", act.heure)
        act.lieu          = request.form.get("lieu", act.lieu)
        act.description   = request.form.get("description", act.description)
        act.nb_max        = int(request.form.get("nb_max", act.nb_max))
        db.session.commit()
        flash("Activité modifiée ✅", "success")
        return redirect(f"/activity/{act.id}")
    return render_template("edit_activity.html", act=act, types=TOUTES_ACTIVITES)


@app.route("/delete_activity/<int:aid>")
def delete_activity(aid):
    if not session.get("user_id"): return redirect("/login")
    act = Activity.query.get_or_404(aid)
    if act.createur_id == session["user_id"]:
        db.session.delete(act)
        db.session.commit()
        flash("Activité supprimée.", "info")
    return redirect("/activities")


# ── PROFIL ──────────────────────────────────────────────────

@app.route("/profile", methods=["GET","POST"])
def profile():
    try:
        if request.method == "POST": verify_csrf()
    except Exception:
        pass  # Allow AJAX calls with CSRF in body
    if not session.get("user_id"): return redirect("/login")
    user = User.query.get(session["user_id"])
    mes_act  = Activity.query.filter_by(createur_id=user.id).all()
    favoris_ids = [f.activity_id for f in Favori.query.filter_by(user_id=user.id).all()]
    acts_favoris = [a for a in [Activity.query.get(fid) for fid in favoris_ids] if a]
    mes_part = [a for a in user.activites_rejointes if a.createur_id != user.id]
    mes_avis = Review.query.filter_by(cible_id=user.id).all()
    demandes_recues = DemandeAmi.query.filter_by(receveur_id=user.id,
                                                   statut="en_attente").all()
    # Calcul des badges
    badges = []
    if len(mes_act) >= 1:  badges.append({"icon":"🎯","nom":"Organisateur","desc":"1ère activité créée"})
    if len(mes_act) >= 5:  badges.append({"icon":"🏆","nom":"Super Organisateur","desc":"5 activités créées"})
    if len(mes_part) >= 3: badges.append({"icon":"🤝","nom":"Sociable","desc":"3+ participations"})
    if len(mes_part) >= 10:badges.append({"icon":"⭐","nom":"Membre actif","desc":"10+ participations"})
    if user.reputation >= 4.5: badges.append({"icon":"💎","nom":"Top membre","desc":"Note ≥ 4.5/5"})
    if len(mes_avis) >= 5: badges.append({"icon":"🌟","nom":"Bien noté","desc":"5+ avis reçus"})

    # Activités populaires (tendance)
    from collections import Counter
    type_count = Counter([a.type_activite for a in mes_act + mes_part])

    return render_template("profile.html", user=user, mes_act=mes_act,
                           mes_part=mes_part, mes_avis=mes_avis,
                           demandes_recues=demandes_recues, badges=badges,
                           acts_favoris=acts_favoris)


@app.route("/edit_profile", methods=["GET","POST"])
def edit_profile():
    if not session.get("user_id"): return redirect("/login")
    user  = User.query.get(session["user_id"])
    error = ""
    if request.method == "POST":
        verify_csrf()
        action = request.form.get("action","profil")

        if action == "profil":
            centres = request.form.getlist("centres")
            if len(centres) > 5:
                error = "Maximum 5 centres d'intérêt."
            else:
                user.ville           = request.form.get("ville", user.ville)
                user.bio             = request.form.get("bio","")[:300]
                user.centres_interet = ",".join(centres)
                user.profil_prive    = "profil_prive" in request.form
                user.accepte_messages= "accepte_messages" in request.form

                if "photo" in request.files:
                    f = request.files["photo"]
                    if f and f.filename and allowed_file(f.filename):
                        filename = "user_" + str(user.id) + ".jpg"
                        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)
                        try:
                            from PIL import Image
                            import io
                            img = Image.open(f)
                            img = img.convert("RGB")
                            img.thumbnail((400, 400), Image.LANCZOS)
                            img.save(save_path, "JPEG", quality=85, optimize=True)
                            logger.info(f"Photo compressée: {filename}")
                        except ImportError:
                            # Pillow non installé — save directement
                            f.seek(0)
                            f.save(save_path)
                        user.photo = filename

                db.session.commit()
                flash("Profil mis à jour ✅", "success")
                return redirect("/profile")

        elif action == "mdp":
            ancien = request.form.get("ancien_mdp","")
            nouveau = request.form.get("nouveau_mdp","")
            confirm = request.form.get("confirm_mdp","")
            if not user.verifier_mdp(ancien):
                error = "Ancien mot de passe incorrect."
            elif len(nouveau) < 8:
                error = "Le nouveau mot de passe doit contenir au moins 8 caractères."
            elif not any(c.isdigit() for c in nouveau):
                error = "Le mot de passe doit contenir au moins un chiffre."
            elif nouveau != confirm:
                error = "Les mots de passe ne correspondent pas."
            else:
                user.mot_de_passe = generate_password_hash(nouveau)
                db.session.commit()
                flash("Mot de passe changé ✅", "success")
                return redirect("/profile")

        elif action == "email":
            nouvel_email = request.form.get("nouvel_email","").strip().lower()
            mdp_confirm  = request.form.get("mdp_confirm","")
            if not user.verifier_mdp(mdp_confirm):
                error = "Mot de passe incorrect."
            elif not nouvel_email or "@" not in nouvel_email:
                error = "Email invalide."
            elif User.query.filter_by(email=nouvel_email).first():
                error = "Cet email est déjà utilisé."
            else:
                user.email = nouvel_email
                db.session.commit()
                flash("Email mis à jour ✅", "success")
                return redirect("/profile")

        elif action == "notifs":
            user.notif_ami      = "notif_ami"      in request.form
            user.notif_activite = "notif_activite" in request.form
            user.notif_message  = "notif_message"  in request.form
            user.notif_system   = "notif_system"   in request.form
            db.session.commit()
            flash("Paramètres de notifications mis à jour ✅", "success")
            return redirect("/profile")

    mes_centres = user.get_centres()
    return render_template("edit_profile.html", user=user, error=error,
                           villes=VILLES, activites_liste=ACTIVITES_LISTE,
                           mes_centres=mes_centres)


@app.route("/delete_account", methods=["POST"])
def delete_account():
    if not session.get("user_id"): return redirect("/login")
    try:
        verify_csrf()
    except Exception:
        pass
    uid = session["user_id"]
    user = User.query.get(uid)
    if not user:
        session.clear()
        return redirect("/login")
    try:
        nom = f"{user.prenom} {user.nom}"
        # Cascade delete — même ordre que admin_delete_user
        for act in Activity.query.filter_by(createur_id=uid).all():
            Message.query.filter_by(activity_id=act.id).delete()
            Review.query.filter_by(activity_id=act.id).delete()
            act.participants_list.clear()
            Favori.query.filter_by(activity_id=act.id).delete()
            CheckIn.query.filter_by(activity_id=act.id).delete()
            db.session.delete(act)
        Message.query.filter_by(user_id=uid).delete()
        MessagePrive.query.filter(
            (MessagePrive.expediteur_id == uid) | (MessagePrive.destinataire_id == uid)
        ).delete(synchronize_session=False)
        Reaction.query.filter_by(user_id=uid).delete()
        DemandeAmi.query.filter(
            (DemandeAmi.envoyeur_id == uid) | (DemandeAmi.receveur_id == uid)
        ).delete(synchronize_session=False)
        Notification.query.filter_by(user_id=uid).delete()
        Signalement.query.filter_by(rapporteur_id=uid).delete()
        Favori.query.filter_by(user_id=uid).delete()
        Streak.query.filter_by(user_id=uid).delete()
        CheckIn.query.filter_by(user_id=uid).delete()
        Review.query.filter(
            (Review.auteur_id == uid) | (Review.cible_id == uid)
        ).delete(synchronize_session=False)
        PasswordResetToken.query.filter_by(user_id=uid).delete()
        EmailVerificationToken.query.filter_by(user_id=uid).delete()
        for act in Activity.query.filter(Activity.participants_list.any(id=uid)).all():
            act.participants_list = [p for p in act.participants_list if p.id != uid]
        db.session.flush()
        db.session.delete(user)
        db.session.commit()
        session.clear()
        flash("Ton compte a été supprimé définitivement. À bientôt ! 👋", "info")
        return redirect("/landing")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur auto-suppression user {uid}: {e}")
        flash(f"Erreur lors de la suppression. Réessaie.", "error")
        return redirect("/profile")


@app.route("/user/<int:uid>")
def voir_profil(uid):
    if not session.get("user_id"): return redirect("/login")
    cible      = User.query.get_or_404(uid)
    moi        = User.query.get(session["user_id"])
    avis        = Review.query.filter_by(cible_id=uid).all()
    mes_act    = Activity.query.filter_by(createur_id=uid).all()

    # Vérifier relation d'amis
    demande    = DemandeAmi.query.filter_by(
        envoyeur_id=moi.id, receveur_id=uid).first()
    sont_amis  = cible in (moi.utilisateurs_bloques or [])

    if cible.profil_prive and uid != moi.id:
        return render_template("profil_prive.html", cible=cible)

    return render_template("voir_profil.html", cible=cible, moi=moi,
                           avis=avis, mes_act=mes_act, demande=demande)


# ── AMIS ────────────────────────────────────────────────────

@app.route("/demande_ami/<int:uid>")
def demande_ami(uid):
    if not session.get("user_id"): return redirect("/login")
    moi = session["user_id"]
    if uid == moi:
        flash("Tu ne peux pas t'ajouter toi-même.", "error")
        return redirect("/activities")
    if not DemandeAmi.query.filter_by(envoyeur_id=moi, receveur_id=uid).first():
        db.session.add(DemandeAmi(envoyeur_id=moi, receveur_id=uid))
        notifier(uid, f"{User.query.get(moi).prenom} t'a envoyé une demande d'ami",
                 "ami", f"/user/{moi}")
        db.session.commit()
        # Email notification
        try:
            receveur_user = User.query.get(uid)
            envoyeur_user = User.query.get(moi)
            if receveur_user and envoyeur_user:
                send_email_notification(
                    recipient=receveur_user,
                    subject=f"👥 {envoyeur_user.prenom} {envoyeur_user.nom} veut être ton ami — Let's Meet Morocco",
                    title="Nouvelle demande d'ami !",
                    message=f"<strong>{envoyeur_user.prenom} {envoyeur_user.nom}</strong> t'a envoyé une demande d'ami sur Let's Meet Morocco.",
                    cta_text="👥 Voir la demande",
                    cta_url="/amis",
                    icon="👥"
                )
        except Exception as e:
            logger.warning(f"Email demande ami failed: {e}")
        flash("Demande d'ami envoyée !", "success")
    return redirect(f"/user/{uid}")


@app.route("/repondre_ami/<int:did>/<string:reponse>")
def repondre_ami(did, reponse):
    if not session.get("user_id"): return redirect("/login")
    d = DemandeAmi.query.get_or_404(did)
    if d.receveur_id == session["user_id"]:
        d.statut = "accepte" if reponse == "oui" else "refuse"
        db.session.commit()
        if reponse == "oui":
            # Email notification à l'envoyeur
            try:
                receveur_u = User.query.get(d.receveur_id)
                if d.envoyeur and receveur_u and reponse == "oui":
                    send_email_notification(
                        recipient=d.envoyeur,
                        subject=f"🎉 {receveur_u.prenom} a accepté ta demande — Let's Meet Morocco",
                        title="Demande d'ami acceptée !",
                        message=f"<strong>{receveur_u.prenom} {receveur_u.nom}</strong> a accepté ta demande d'ami ! Vous pouvez maintenant chatter et partager des activités.",
                        cta_text="💬 Envoyer un message",
                        cta_url=f"/messages/{receveur_u.id}",
                        icon="🎉"
                    )
            except Exception as e:
                logger.warning(f"Email ami accept failed: {e}")
            flash(f"Tu es maintenant ami avec {d.envoyeur.prenom} !", "success")
        else:
            flash("Demande refusée.", "info")
    return redirect("/profile")


@app.route("/bloquer/<int:uid>")
def bloquer_user(uid):
    if not session.get("user_id"): return redirect("/login")
    if uid == session["user_id"]:
        flash("Tu ne peux pas te bloquer toi-même.", "error")
        return redirect("/activities")
    moi   = User.query.get(session["user_id"])
    cible = User.query.get_or_404(uid)
    if cible not in moi.utilisateurs_bloques:
        moi.utilisateurs_bloques.append(cible)
        db.session.commit()
        flash(f"{cible.prenom} a été bloqué.", "info")
    return redirect("/activities")


@app.route("/signaler_user/<int:uid>", methods=["POST"])
def signaler_user(uid):
    if not session.get("user_id"): return redirect("/login")
    verify_csrf()
    motif = request.form.get("motif","").strip()
    if motif:
        db.session.add(Signalement(type_cible="user", cible_id=uid,
                                    motif=motif, rapporteur_id=session["user_id"]))
        db.session.commit()
        flash("Utilisateur signalé à l'administrateur.", "info")
    return redirect(f"/user/{uid}")


# ── NOTIFICATIONS ────────────────────────────────────────────

@app.route("/notifications")
def notifications():
    if not session.get("user_id"): return redirect("/login")
    notifs = Notification.query.filter_by(
        user_id=session["user_id"]).order_by(Notification.id.desc()).all()
    for n in notifs:
        n.est_lue = True
    db.session.commit()
    return render_template("notifications.html", notifs=notifs)


@app.route("/api/notifs_count")
def api_notifs_count():
    if not session.get("user_id"):
        return jsonify({"count": 0})
    count = Notification.query.filter_by(
        user_id=session["user_id"], est_lue=False).count()
    return jsonify({"count": count})


# ── NOUVELLES API v13 ────────────────────────────────────────

@app.route("/api/reaction/<int:msg_id>", methods=["POST"])
def api_reaction(msg_id):
    if not session.get("user_id"): return jsonify({"ok":False})
    try:
        if request.method == "POST": verify_csrf()
    except Exception:
        pass  # Allow AJAX calls with CSRF in body
    data = request.get_json(silent=True) or {}
    emoji = data.get("emoji","👍")
    user_id = session["user_id"]
    existing = Reaction.query.filter_by(message_id=msg_id, user_id=user_id, emoji=emoji).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Reaction(message_id=msg_id, user_id=user_id, emoji=emoji))
    db.session.commit()
    reactions = {}
    for r in Reaction.query.filter_by(message_id=msg_id).all():
        reactions[r.emoji] = reactions.get(r.emoji, 0) + 1
    return jsonify({"ok":True,"reactions":reactions})


@app.route("/api/favori/<int:act_id>", methods=["POST"])
def api_favori(act_id):
    if not session.get("user_id"): return jsonify({"ok":False})
    try:
        if request.method == "POST": verify_csrf()
    except Exception:
        pass  # Allow AJAX calls with CSRF in body
    user_id = session["user_id"]
    existing = Favori.query.filter_by(user_id=user_id, activity_id=act_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"ok":True,"saved":False})
    db.session.add(Favori(user_id=user_id, activity_id=act_id))
    db.session.commit()
    return jsonify({"ok":True,"saved":True})


@app.route("/api/favori/<int:act_id>/check")
def api_favori_check(act_id):
    """Check if activity is saved by current user"""
    if not session.get("user_id"):
        return jsonify({"saved": False})
    existing = Favori.query.filter_by(
        user_id=session["user_id"], activity_id=act_id
    ).first()
    return jsonify({"saved": existing is not None})


@app.route("/api/feed")
def api_feed():
    if not session.get("user_id"): return jsonify([])
    events = FeedEvent.query.order_by(FeedEvent.id.desc()).limit(15).all()
    return jsonify([{"icon":e.icon,"texte":e.texte,"date":e.date,"lien":e.lien} for e in events])


@app.route("/inviter/<int:act_id>/<int:ami_id>")
def inviter_ami(act_id, ami_id):
    """Invite un ami à une activité via message automatique"""
    if not session.get("user_id"): return redirect("/login")
    uid = session["user_id"]
    user = User.query.get(uid)
    act  = Activity.query.get_or_404(act_id)
    ami  = User.query.get_or_404(ami_id)
    # Envoyer un DM automatique
    msg_texte = f"Hey ! Je t'invite à rejoindre mon activité : {act.titre} le {act.date_activite} à {act.heure} ({act.lieu}). C'est par ici 👉 /activity/{act_id}"
    msg = MessagePrive(expediteur_id=uid, destinataire_id=ami_id, contenu=msg_texte)
    db.session.add(msg)
    notifier(ami_id, f"{user.prenom} t'invite à {act.titre} !", "info", f"/activity/{act_id}")
    db.session.commit()
    flash(f"Invitation envoyée à {ami.prenom} !", "success")
    return redirect(f"/activity/{act_id}")


@app.route("/api/streak")
def api_streak():
    if not session.get("user_id"): return jsonify({"valeur":0})
    s = Streak.query.filter_by(user_id=session["user_id"]).first()
    return jsonify({"valeur": s.valeur if s else 0})


# ══════════════════════════════════════════════════════════
# MESSAGERIE PRIVÉE (DM)
# ══════════════════════════════════════════════════════════

@app.route("/messages")
def messages_list():
    """Liste des conversations de l'utilisateur"""
    if not session.get("user_id"):
        return redirect("/login")
    uid = session["user_id"]
    user = User.query.get(uid)

    # Récupérer tous les interlocuteurs uniques
    sent  = db.session.query(MessagePrive.destinataire_id).filter_by(expediteur_id=uid)
    recvd = db.session.query(MessagePrive.expediteur_id).filter_by(destinataire_id=uid)
    contact_ids = {r[0] for r in sent.all()} | {r[0] for r in recvd.all()}

    conversations = []
    for cid in contact_ids:
        contact = User.query.get(cid)
        if not contact:
            continue
        # Dernier message échangé
        last_msg = MessagePrive.query.filter(
            ((MessagePrive.expediteur_id == uid) & (MessagePrive.destinataire_id == cid)) |
            ((MessagePrive.expediteur_id == cid) & (MessagePrive.destinataire_id == uid))
        ).order_by(MessagePrive.id.desc()).first()
        # Messages non lus
        unread = MessagePrive.query.filter_by(
            expediteur_id=cid, destinataire_id=uid, est_lu=False).count()
        conversations.append({
            "contact": contact,
            "last_msg": last_msg,
            "unread": unread
        })
    # Trier par dernier message
    conversations.sort(key=lambda x: x["last_msg"].id if x["last_msg"] else 0, reverse=True)

    return render_template("messages.html", user=user, conversations=conversations)


@app.route("/messages/<int:contact_id>", methods=["GET", "POST"])
def conversation(contact_id):
    """Conversation avec un contact spécifique"""
    if not session.get("user_id"):
        return redirect("/login")
    uid = session["user_id"]
    user = User.query.get(uid)
    contact = User.query.get_or_404(contact_id)

    if request.method == "POST":
        verify_csrf()
        contenu = request.form.get("message", "").strip()
        if contenu and len(contenu) <= 1000:
            msg = MessagePrive(
                expediteur_id=uid,
                destinataire_id=contact_id,
                contenu=contenu
            )
            db.session.add(msg)
            # Notifier le destinataire
            notifier(contact_id,
                     f"Nouveau message de {user.prenom} {user.nom}",
                     "message", f"/messages/{uid}")
            db.session.commit()
            flash("Message envoyé !", "success")
        return redirect(f"/messages/{contact_id}")

    # Marquer messages comme lus
    MessagePrive.query.filter_by(
        expediteur_id=contact_id, destinataire_id=uid, est_lu=False
    ).update({"est_lu": True})
    db.session.commit()

    # Récupérer la conversation
    msgs = MessagePrive.query.filter(
        ((MessagePrive.expediteur_id == uid) & (MessagePrive.destinataire_id == contact_id)) |
        ((MessagePrive.expediteur_id == contact_id) & (MessagePrive.destinataire_id == uid))
    ).order_by(MessagePrive.id.asc()).all()

    return render_template("conversation.html", user=user, contact=contact, msgs=msgs)


@app.route("/bloquer_dm/<int:uid>")
def bloquer_depuis_dm(uid):
    """Bloquer quelqu'un directement depuis la conversation"""
    if not session.get("user_id"): return redirect("/login")
    if uid == session["user_id"]:
        return redirect("/messages")
    moi   = User.query.get(session["user_id"])
    cible = User.query.get_or_404(uid)
    if cible not in moi.utilisateurs_bloques:
        moi.utilisateurs_bloques.append(cible)
        db.session.commit()
        flash(f"{cible.prenom} a été bloqué(e). Ses messages ne t'apparaîtront plus.", "info")
    return redirect("/messages")


@app.route("/messages/new/<int:contact_id>")
def new_conversation(contact_id):
    """Redirige vers la conversation (crée si nécessaire)"""
    if not session.get("user_id"):
        return redirect("/login")
    return redirect(f"/messages/{contact_id}")


@app.route("/api/checkin/<int:act_id>", methods=["POST"])
def api_checkin(act_id):
    """Check-in 'Je suis là !' pour une activité"""
    if not session.get("user_id"): return jsonify({"ok": False})
    uid = session["user_id"]
    # Vérifier que l'user participe
    act = Activity.query.get_or_404(act_id)
    user = User.query.get(uid)
    if user not in act.participants_list:
        return jsonify({"ok": False, "msg": "Tu ne participes pas à cette activité"})
    # Check si déjà checké
    existing = CheckIn.query.filter_by(user_id=uid, activity_id=act_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"ok": True, "checked": False})
    db.session.add(CheckIn(user_id=uid, activity_id=act_id))
    db.session.commit()
    # Notifier l'organisateur
    notifier(act.createur_id,
             f"{user.prenom} vient d'arriver à {act.titre} 📍",
             "info", f"/activity/{act_id}")
    # Ajouter au feed
    add_feed("checkin", f"{user.prenom} est arrivé(e) à {act.titre}",
             "📍", f"/activity/{act_id}")
    db.session.commit()
    present = CheckIn.query.filter_by(activity_id=act_id).count()
    return jsonify({"ok": True, "checked": True, "present": present})


@app.route("/api/dm/<int:contact_id>", methods=["GET"])
def api_dm_messages(contact_id):
    """API pour récupérer les messages DM en temps réel"""
    if not session.get("user_id"):
        return jsonify({"messages": [], "error": "not_logged_in"})
    uid = session["user_id"]
    # Marquer comme lu
    MessagePrive.query.filter_by(
        expediteur_id=contact_id, destinataire_id=uid, est_lu=False
    ).update({"est_lu": True})
    db.session.commit()
    msgs = MessagePrive.query.filter(
        ((MessagePrive.expediteur_id == uid) & (MessagePrive.destinataire_id == contact_id)) |
        ((MessagePrive.expediteur_id == contact_id) & (MessagePrive.destinataire_id == uid))
    ).order_by(MessagePrive.id.asc()).all()
    return jsonify({"messages": [{
        "id": m.id,
        "contenu": m.contenu,
        "heure": m.heure,
        "date": m.date,
        "est_moi": m.expediteur_id == uid,
        "est_lu": m.est_lu,
        "prenom": m.expediteur.prenom
    } for m in msgs]})


@app.route("/api/dm/<int:contact_id>/send", methods=["POST"])
def api_dm_send(contact_id):
    """API pour envoyer un message DM sans rechargement"""
    if not session.get("user_id"):
        return jsonify({"ok": False, "error": "not_logged_in"})
    try:
        verify_csrf()
    except Exception:
        pass
    uid = session["user_id"]
    user = User.query.get(uid)
    contenu = request.form.get("message", "").strip()
    if not contenu or len(contenu) > 1000:
        return jsonify({"ok": False, "error": "invalid_message"})
    msg = MessagePrive(
        expediteur_id=uid,
        destinataire_id=contact_id,
        contenu=contenu
    )
    db.session.add(msg)
    notifier(contact_id,
             f"Nouveau message de {user.prenom} {user.nom}",
             "message", f"/messages/{uid}")
    db.session.commit()
    # Notification email
    try:
        contact_user = User.query.get(contact_id)
        if contact_user:
            send_dm_notification_email(contact_user, user, contenu)
    except Exception as e:
        logger.warning(f"API email DM notification failed: {e}")
    return jsonify({
        "ok": True,
        "message": {
            "id": msg.id,
            "contenu": msg.contenu,
            "heure": msg.heure,
            "date": msg.date,
            "est_moi": True,
            "est_lu": False
        }
    })


@app.route("/api/dm_count")
def api_dm_count():
    """Nombre de messages non lus"""
    if not session.get("user_id"):
        return jsonify({"count": 0})
    uid = session["user_id"]
    count = MessagePrive.query.filter_by(destinataire_id=uid, est_lu=False).count()
    return jsonify({"count": count})


# PASSWORD RESET ROUTES

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if session.get("user_id"): return redirect("/")
    message = ""
    if request.method == "POST":
        verify_csrf()
        ip = request.remote_addr or "unknown"
        if rate_limit(f"forgot:{ip}", max_attempts=3, window=300):
            message = "Trop de demandes. Attendez 5 minutes."
        else:
            email = request.form.get("email","").strip().lower()
            user = User.query.filter_by(email=email).first()
            message = "Si cet email existe, un lien de reinitialisation a ete envoye."
            if user and user.est_valide:
                token = PasswordResetToken.generer(user.id)
                db.session.commit()
                reset_url = request.host_url.rstrip("/") + f"/reset-password/{token}"
                prenom = user.prenom
                html = (
                    f"<div style='font-family:sans-serif;max-width:520px;margin:0 auto;padding:32px'>"
                    f"<h2 style='color:#0F1A10'>Reinitialisation de ton mot de passe</h2>"
                    f"<p style='color:#555;line-height:1.6'>Bonjour {prenom},<br><br>"
                    f"Clique sur le bouton ci-dessous dans les <strong>2 heures</strong> :</p>"
                    f"<a href='{reset_url}' style='display:inline-block;background:#E8541A;color:#fff;"
                    f"padding:14px 32px;border-radius:12px;text-decoration:none;font-weight:600;font-size:15px'>"
                    f"Reinitialiser mon mot de passe</a>"
                    f"<p style='color:#aaa;font-size:12px;margin-top:24px'>"
                    f"Le lien expire dans 2 heures. Si tu n'as pas fait cette demande, ignore cet email.</p>"
                    f"</div>"
                )
                send_email(user.email, "Reinitialisation mot de passe — Let's Meet Morocco", html)
    return render_template("forgot_password.html", message=message)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if session.get("user_id"): return redirect("/")
    reset = PasswordResetToken.query.filter_by(token=token).first()
    if not reset or not reset.est_valide():
        flash("Ce lien est invalide ou a expire. Fais une nouvelle demande.", "error")
        return redirect("/forgot-password")
    error = ""
    if request.method == "POST":
        verify_csrf()
        nouveau = request.form.get("password","")
        confirm = request.form.get("confirm","")
        if len(nouveau) < 6:
            error = "Le mot de passe doit avoir au moins 6 caracteres."
        elif nouveau != confirm:
            error = "Les mots de passe ne correspondent pas."
        else:
            user = reset.user
            user.mot_de_passe = generate_password_hash(nouveau)
            reset.utilise = True
            db.session.commit()
            flash("Mot de passe modifie ! Tu peux te connecter.", "success")
            return redirect("/login")
    return render_template("reset_password.html", token=token, error=error)


@app.route("/amis")
def mes_amis():
    """Page listant tous mes amis acceptés"""
    if not session.get("user_id"): return redirect("/login")
    uid  = session["user_id"]
    user = User.query.get(uid)
    # Amis = demandes acceptées dans les deux sens
    amis_envoyes  = DemandeAmi.query.filter_by(envoyeur_id=uid,  statut="accepte").all()
    amis_recus    = DemandeAmi.query.filter_by(receveur_id=uid,  statut="accepte").all()
    amis = []
    for d in amis_envoyes:
        amis.append({"user": d.receveur,   "depuis": d.date})
    for d in amis_recus:
        amis.append({"user": d.envoyeur,   "depuis": d.date})
    # Trier par nom
    amis.sort(key=lambda x: x["user"].prenom)
    return render_template("mes_amis.html", user=user, amis=amis)


@app.route("/supprimer_ami/<int:uid>")
def supprimer_ami(uid):
    if not session.get("user_id"): return redirect("/login")
    moi = session["user_id"]
    d = DemandeAmi.query.filter(
        ((DemandeAmi.envoyeur_id==moi)  & (DemandeAmi.receveur_id==uid)) |
        ((DemandeAmi.envoyeur_id==uid)  & (DemandeAmi.receveur_id==moi))
    ).first()
    if d:
        db.session.delete(d)
        db.session.commit()
        flash("Ami supprimé.", "info")
    return redirect("/amis")


@app.route("/leaderboard")
def leaderboard():
    if not session.get("user_id"): return redirect("/login")
    user = User.query.get(session["user_id"])
    users = User.query.filter_by(est_valide=True, est_bloque=False).all()
    scored = []
    for u in users:
        score = u.nb_activites_creees()*3 + u.nb_participations() + int(u.reputation*2)
        s = Streak.query.filter_by(user_id=u.id).first()
        scored.append({"user":u,"score":score,"streak":s.valeur if s else 0})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return render_template("leaderboard.html", ranked=scored[:20], current_user=user)


# ── CHAT AJAX ────────────────────────────────────────────────

@app.route("/api/messages/<int:aid>")
def api_messages(aid):
    if not session.get("user_id"):
        return jsonify([])
    msgs = Message.query.filter_by(activity_id=aid).all()
    return jsonify([{
        "id": m.id,
        "contenu": m.contenu,
        "heure": m.heure,
        "prenom": m.auteur.prenom,
        "user_id": m.user_id
    } for m in msgs])


# ============================================================
# ROUTES ADMIN
# ============================================================

def _parse_date_admin(s):
    try: return datetime.strptime(s, "%d/%m/%Y").date()
    except: return None

def _parse_date_creation(s):
    try: return datetime.strptime(s[:10], "%d/%m/%Y").date()
    except: return None


# ── ADMIN LOGIN SÉPARÉ ──────────────────────────────────────
# URL cachée — les utilisateurs normaux ne la connaissent pas

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Page de connexion admin — URL séparée de /login"""
    if session.get("is_admin"):
        return redirect("/admin")
    error = ""
    if request.method == "POST":
        verify_csrf()
        ip = request.remote_addr or "unknown"
        if rate_limit(f"admin_login:{ip}", max_attempts=5, window=120):
            error = "Trop de tentatives. Attendez 2 minutes."
            return render_template("admin_login.html", error=error)
        email = request.form.get("email", "").strip()
        pwd   = request.form.get("password", "").strip()
        # Identifiants admin depuis variables d'environnement
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@letsmeet.ma")
        admin_pwd   = os.environ.get("ADMIN_PASSWORD", "admin123")
        if email == admin_email and pwd == admin_pwd:
            session["is_admin"] = True
            session.permanent = True
            return redirect("/admin")
        error = "Identifiants incorrects."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect("/admin/login")


@app.route("/admin/broadcast", methods=["POST"])
def admin_broadcast():
    """Broadcast amélioré : ciblage + email + historique"""
    if not session.get("is_admin"): return redirect("/admin/login")
    try: verify_csrf()
    except: pass

    message     = request.form.get("message","").strip()
    cible       = request.form.get("cible","tous")          # tous / actifs / ville / email_verifie
    ville_cible = request.form.get("ville_cible","").strip()
    avec_email  = request.form.get("avec_email","0") == "1"

    if not message:
        flash("Le message ne peut pas être vide.", "error")
        return redirect("/admin?tab=dashboard")

    # ── Construire la liste des destinataires ──
    q = User.query.filter_by(est_bloque=False, est_valide=True)

    if cible == "actifs":
        # Actifs = connectés dans les 30 derniers jours
        from datetime import timedelta
        seuil = datetime.now() - timedelta(days=30)
        q = q.filter(User.derniere_activite >= seuil)
    elif cible == "ville" and ville_cible:
        q = q.filter_by(ville=ville_cible)
    elif cible == "email_verifie":
        q = q.filter_by(email_verifie=True)

    destinataires = q.all()

    if not destinataires:
        flash("Aucun destinataire trouvé pour ce ciblage.", "error")
        return redirect("/admin?tab=dashboard")

    # ── Envoyer notifications internes ──
    for u in destinataires:
        notifier(u.id, f"📢 {message}", "info", "/notifications")

    # ── Envoyer emails si demandé ──
    nb_emails = 0
    if avec_email:
        for u in destinataires:
            if u.email_verifie and getattr(u, "notif_system", True):
                try:
                    send_email_notification(
                        recipient=u,
                        subject="📢 Message de Let's Meet Morocco",
                        title="Message de l'administration",
                        message=message,
                        cta_text="Voir les notifications",
                        cta_url="/notifications",
                        icon="📢"
                    )
                    nb_emails += 1
                except Exception as e:
                    logger.warning(f"Broadcast email failed for {u.email}: {e}")

    # ── Enregistrer dans l'historique ──
    log = BroadcastLog(
        message=message,
        cible=cible,
        ville_cible=ville_cible if cible == "ville" else "",
        avec_email=avec_email,
        nb_envoyes=len(destinataires)
    )
    db.session.add(log)

    # ── Label ciblage pour le journal ──
    label_cible = {"tous":"tous","actifs":"membres actifs",
                   "ville":f"ville={ville_cible}","email_verifie":"emails vérifiés"}.get(cible, cible)
    log_admin(f"Broadcast → {len(destinataires)} membres ({label_cible})"
              f"{' + '+str(nb_emails)+' emails' if avec_email else ''}: {message[:60]}")

    db.session.commit()

    msg_flash = f"✅ Notification envoyée à <strong>{len(destinataires)} membres</strong>"
    if avec_email and nb_emails > 0:
        msg_flash += f" · <strong>{nb_emails} emails</strong> envoyés"
    flash(msg_flash, "success")
    return redirect("/admin?tab=dashboard")


@app.route("/admin/broadcast_history")
def admin_broadcast_history():
    """API JSON — historique des broadcasts pour le dashboard"""
    if not session.get("is_admin"):
        return jsonify([])
    logs = BroadcastLog.query.order_by(BroadcastLog.id.desc()).limit(20).all()
    return jsonify([{
        "id":          l.id,
        "message":     l.message,
        "cible":       l.cible,
        "ville_cible": l.ville_cible,
        "avec_email":  l.avec_email,
        "nb_envoyes":  l.nb_envoyes,
        "date":        l.date_str()
    } for l in logs])


@app.route("/admin/ban-temp/<int:uid>/<int:jours>")
def admin_ban_temp(uid, jours):
    """Bannissement temporaire d'un utilisateur"""
    if not session.get("is_admin"): return redirect("/admin/login")
    user = User.query.get_or_404(uid)
    user.est_bloque = True
    # Store ban expiry in a note (simple approach)
    from datetime import timedelta
    expiry = (datetime.now() + timedelta(days=jours)).strftime("%d/%m/%Y")
    notifier(uid, f"Ton compte a été suspendu pour {jours} jour(s) jusqu'au {expiry}.", "error", "/")
    log_admin(f"Ban temporaire {jours}j : {user.prenom} {user.nom} (jusqu'au {expiry})")
    db.session.commit()
    flash(f"{user.prenom} banni temporairement pour {jours} jour(s)", "info")
    return redirect(f"/admin/user/{uid}")


@app.route("/admin")
def admin_dashboard():
    if not session.get("is_admin"): return redirect("/admin/login")
    users      = User.query.all()
    activities = Activity.query.all()
    en_attente = User.query.filter_by(est_valide=False, est_bloque=False).all()
    signalements = Signalement.query.filter_by(statut="en_attente").all()
    logs       = AdminLog.query.order_by(AdminLog.id.desc()).limit(20).all()

    types_count = {}
    for a in activities:
        types_count[a.type_activite] = types_count.get(a.type_activite, 0) + 1
    villes_count = {}
    for u in users:
        villes_count[u.ville] = villes_count.get(u.ville, 0) + 1

    # Inscriptions 30 derniers jours
    from datetime import timedelta
    today_d = date.today()
    reg_labels, reg_data = [], []
    for i in range(29, -1, -1):
        d = today_d - timedelta(days=i)
        day_str = d.strftime("%d/%m/%Y")
        reg_labels.append(d.strftime("%d/%m"))
        reg_data.append(sum(1 for u in users if u.date_inscription == day_str))

    # Tendance semaine
    new_users_week = sum(1 for u in users
                         if _parse_date_admin(u.date_inscription or "")
                         and (today_d - _parse_date_admin(u.date_inscription)).days < 7)
    new_acts_week  = sum(1 for a in activities
                         if _parse_date_creation(a.date_creation or "")
                         and (today_d - _parse_date_creation(a.date_creation)).days < 7)

    stats = {
        "nb_users":       User.query.count(),
        "nb_acts":        Activity.query.count(),
        "actifs":         User.query.filter_by(est_bloque=False, est_valide=True).count(),
        "en_attente":     len(en_attente),
        "ouvertes":       Activity.query.filter_by(statut="Ouverte").count(),
        "signalements":   len(signalements),
        "new_users_week": new_users_week,
        "new_acts_week":  new_acts_week,
        "online":         max(1, User.query.filter_by(est_valide=True, est_bloque=False).count() // 3),
        "total_messages": Message.query.count(),
    }
    return render_template("admin.html",
                           users=users,
                           activities=activities,
                           en_attente=en_attente,
                           signalements=signalements,
                           stats=stats,
                           logs=logs,
                           broadcast_logs=BroadcastLog.query.order_by(BroadcastLog.id.desc()).limit(20).all(),
                           villes=VILLES,
                           types_json=json.dumps(types_count),
                           villes_json=json.dumps(villes_count),
                           reg_labels=json.dumps(reg_labels),
                           reg_data=json.dumps(reg_data))


@app.route("/admin/valider/<int:uid>")
def admin_valider(uid):
    if not session.get("is_admin"): return redirect("/admin/login")
    u = User.query.get(uid)
    if u:
        u.est_valide = True
        notifier(u.id, "Ton compte a été validé ! Bienvenue sur Let's Meet Morocco 🎉",
                 "success", "/")
        log_admin(f"Compte validé : {u.prenom} {u.nom}")
        db.session.commit()
        flash(f"Compte de {u.prenom} validé.", "success")
    return redirect("/admin")


@app.route("/admin/block/<int:uid>")
def admin_block(uid):
    if not session.get("is_admin"): return redirect("/admin/login")
    u = User.query.get(uid)
    if u:
        u.est_bloque = True
        log_admin(f"Compte bloqué : {u.prenom} {u.nom}")
        db.session.commit()
        flash(f"{u.prenom} bloqué.", "info")
    ref = request.referrer
    if ref and "/admin" in ref:
        return redirect(ref)
    return redirect("/admin?tab=users")


@app.route("/admin/unblock/<int:uid>")
def admin_unblock(uid):
    if not session.get("is_admin"):
        return redirect("/admin/login")
    u = User.query.get(uid)
    if u:
        u.est_bloque = False
        log_admin(f"Compte débloqué : {u.prenom} {u.nom}")
        db.session.commit()
        flash(f"✅ {u.prenom} {u.nom} a été débloqué.", "success")
    # Redirect back to referrer or admin
    ref = request.referrer
    if ref and "/admin" in ref:
        return redirect(ref)
    return redirect("/admin?tab=users")


@app.route("/admin/delete_user/<int:uid>")
def admin_delete_user(uid):
    if not session.get("is_admin"): return redirect("/admin/login")
    u = User.query.get(uid)
    if not u:
        flash("Utilisateur introuvable.", "error")
        return redirect("/admin")
    try:
        nom_complet = f"{u.prenom} {u.nom}"
        # 1. Supprimer les activités créées par cet user (avec leurs messages, reviews, participants)
        for act in Activity.query.filter_by(createur_id=uid).all():
            # Supprimer les messages de cette activité
            Message.query.filter_by(activity_id=act.id).delete()
            Reaction.query.filter(Reaction.message_id.in_(
                [m.id for m in Message.query.filter_by(activity_id=act.id)]
            )).delete(synchronize_session=False)
            # Supprimer les reviews liées
            Review.query.filter_by(activity_id=act.id).delete()
            # Retirer les participants
            act.participants_list.clear()
            # Supprimer les favoris liés
            Favori.query.filter_by(activity_id=act.id).delete()
            # Supprimer les checkins liés
            CheckIn.query.filter_by(activity_id=act.id).delete()
            db.session.delete(act)

        # 2. Supprimer les messages envoyés dans d'autres activités
        Message.query.filter_by(user_id=uid).delete()

        # 3. Supprimer les messages privés
        MessagePrive.query.filter(
            (MessagePrive.expediteur_id == uid) |
            (MessagePrive.destinataire_id == uid)
        ).delete(synchronize_session=False)

        # 4. Supprimer les réactions
        Reaction.query.filter_by(user_id=uid).delete()

        # 5. Supprimer les demandes d'ami
        DemandeAmi.query.filter(
            (DemandeAmi.envoyeur_id == uid) |
            (DemandeAmi.receveur_id == uid)
        ).delete(synchronize_session=False)

        # 6. Supprimer les notifications
        Notification.query.filter_by(user_id=uid).delete()

        # 7. Supprimer les signalements
        Signalement.query.filter_by(rapporteur_id=uid).delete()

        # 8. Supprimer les favoris de l'user
        Favori.query.filter_by(user_id=uid).delete()

        # 9. Supprimer le streak
        Streak.query.filter_by(user_id=uid).delete()

        # 10. Supprimer les checkins
        CheckIn.query.filter_by(user_id=uid).delete()

        # 11. Supprimer les reviews données et reçues
        Review.query.filter(
            (Review.auteur_id == uid) | (Review.cible_id == uid)
        ).delete(synchronize_session=False)

        # 12. Supprimer les tokens de reset
        PasswordResetToken.query.filter_by(user_id=uid).delete()
        # 12b. Supprimer les tokens de vérification email
        EmailVerificationToken.query.filter_by(user_id=uid).delete()

        # 13. Retirer des activités rejointes
        user_acts_joined = Activity.query.filter(
            Activity.participants_list.any(id=uid)
        ).all()
        for act in user_acts_joined:
            act.participants_list = [p for p in act.participants_list if p.id != uid]

        # 14. Supprimer l'utilisateur
        db.session.flush()
        db.session.delete(u)
        db.session.commit()

        log_admin(f"Compte définitivement supprimé : {nom_complet} (id={uid})")
        flash(f"✅ Compte de {nom_complet} supprimé définitivement.", "success")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur suppression user {uid}: {e}")
        flash(f"Erreur lors de la suppression : {str(e)[:200]}", "error")

    return redirect("/admin?tab=users")


@app.route("/admin/delete_activity/<int:aid>")
def admin_delete_activity(aid):
    if not session.get("is_admin"): return redirect("/admin/login")
    act = Activity.query.get(aid)
    if act:
        log_admin(f"Activité supprimée : {act.titre}")
        db.session.delete(act)
        db.session.commit()
        flash("Activité supprimée.", "info")
    return redirect("/admin")


@app.route("/admin/traiter_signalement/<int:sid>/<string:decision>")
def traiter_signalement(sid, decision):
    if not session.get("is_admin"): return redirect("/admin/login")
    s = Signalement.query.get_or_404(sid)
    s.statut = "traite"
    log_admin(f"Signalement #{sid} traité : {decision}")
    db.session.commit()
    flash(f"Signalement traité ({decision}).", "success")
    return redirect("/admin")


@app.route("/admin/export_csv")
def admin_export_csv():
    if not session.get("is_admin"): return redirect("/admin/login")
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Prénom","Nom","Email","Ville","Âge","Statut","Réputation","Date inscription"])
    for u in User.query.all():
        statut = "Bloqué" if u.est_bloque else ("Actif" if u.est_valide else "En attente")
        writer.writerow([u.id, u.prenom, u.nom, u.email, u.ville,
                         u.age, statut, u.reputation, u.date_inscription])
    from flask import make_response
    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = "attachment; filename=utilisateurs.csv"
    resp.headers["Content-type"] = "text/csv; charset=utf-8"
    return resp


@app.route("/admin/user/<int:uid>")
def admin_user_detail(uid):
    if not session.get("is_admin"): return redirect("/admin/login")
    u = User.query.get_or_404(uid)
    activites_creees = Activity.query.filter_by(createur_id=uid).all()
    participations   = u.activites_rejointes
    reviews_recues   = Review.query.filter_by(cible_id=uid).all()
    av_colors = ["#E8541A","#2DB54C","#00B4D8","#7B2D8B","#F5A623","#0077B6","#C67C3A"]
    av_color  = av_colors[uid % len(av_colors)]
    avis = Review.query.filter_by(cible_id=uid).all()
    try:
        nb_part = len(u.activites_rejointes)
    except Exception:
        nb_part = 0
    return render_template("admin_user_detail.html", u=u,
                           av_color=av_color, avis=avis,
                           participations=nb_part)


@app.route("/admin/bulk_action", methods=["POST"])
def admin_bulk_action():
    if not session.get("is_admin"): return redirect("/admin/login")
    verify_csrf()
    action   = request.form.get("action")
    user_ids = request.form.getlist("user_ids")
    count    = 0
    for uid in user_ids:
        u = User.query.get(int(uid))
        if not u: continue
        if action == "block":
            u.est_bloque = True
            log_admin(f"Blocage groupé : {u.prenom} {u.nom}")
            count += 1
        elif action == "delete":
            log_admin(f"Suppression groupée : {u.prenom} {u.nom}")
            db.session.delete(u)
            count += 1
        elif action == "validate":
            u.est_valide = True
            log_admin(f"Validation groupée : {u.prenom} {u.nom}")
            count += 1
    db.session.commit()
    flash(f"{count} utilisateur(s) traité(s).", "success")
    return redirect("/admin?tab=users")


@app.route("/api/admin/search")
def api_admin_search():
    if not session.get("is_admin"): return jsonify([])
    q = request.args.get("q", "").strip()
    if len(q) < 2: return jsonify([])
    results = []
    for u in User.query.filter(
        (User.prenom.ilike(f"%{q}%")) |
        (User.nom.ilike(f"%{q}%")) |
        (User.email.ilike(f"%{q}%"))
    ).limit(6).all():
        results.append({"type":"user","id":u.id,
                         "label":f"{u.prenom} {u.nom}","sub":u.email,
                         "url":f"/admin/user/{u.id}"})
    for a in Activity.query.filter(Activity.titre.ilike(f"%{q}%")).limit(4).all():
        results.append({"type":"activity","id":a.id,
                         "label":a.titre,"sub":a.type_activite,
                         "url":f"/activity/{a.id}"})
    return jsonify(results)


# ============================================================
# HEALTH CHECK
# ============================================================

# ══════════════════════════════════════════════════════════
# PAGES LÉGALES & SEO
# ══════════════════════════════════════════════════════════

@app.route("/mentions-legales")
def mentions_legales():
    return render_template("mentions_legales.html")

@app.route("/confidentialite")
def confidentialite():
    return render_template("confidentialite.html")

@app.route("/cgu")
def cgu():
    return render_template("cgu.html")

@app.route("/a-propos")
def a_propos():
    return render_template("a_propos.html")

@app.route("/robots.txt")
def robots_txt():
    from flask import Response
    content_txt = """User-agent: *
Allow: /
Allow: /activities
Allow: /landing
Allow: /a-propos
Allow: /cgu
Allow: /confidentialite
Allow: /mentions-legales
Disallow: /admin
Disallow: /admin/
Disallow: /api/
Disallow: /profile
Disallow: /edit_profile
Disallow: /messages
Sitemap: {base}/sitemap.xml""".format(base=request.host_url.rstrip("/"))
    return Response(content_txt, mimetype="text/plain")

@app.route("/sitemap.xml")
def sitemap():
    from flask import Response
    base = request.host_url.rstrip("/")
    pages = ["/", "/landing", "/activities", "/map", "/a-propos",
             "/cgu", "/confidentialite", "/mentions-legales", "/leaderboard"]
    acts  = Activity.query.filter_by(statut="Ouverte").limit(100).all()
    xml   = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        xml.append(f"<url><loc>{base}{p}</loc><changefreq>weekly</changefreq></url>")
    for a in acts:
        xml.append(f"<url><loc>{base}/activity/{a.id}</loc><changefreq>daily</changefreq></url>")
    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")


# ══════════════════════════════════════════════════════════
# RECHERCHE MEMBRES
# ══════════════════════════════════════════════════════════

@app.route("/search")
def search_users():
    if not session.get("user_id"): return redirect("/login")
    user = User.query.get(session["user_id"])
    q = request.args.get("q","").strip()
    results = []
    if q and len(q) >= 2:
        results = User.query.filter(
            (User.prenom.ilike(f"%{q}%")) |
            (User.nom.ilike(f"%{q}%"))   |
            (User.ville.ilike(f"%{q}%"))
        ).filter_by(est_valide=True, est_bloque=False).limit(20).all()
    return render_template("search.html", user=user, results=results, q=q)


# ══════════════════════════════════════════════════════════
# HISTORIQUE & STATISTIQUES PERSONNELLES
# ══════════════════════════════════════════════════════════

@app.route("/mes-souvenirs")
def mes_souvenirs():
    if not session.get("user_id"): return redirect("/login")
    uid  = session["user_id"]
    user = User.query.get(uid)
    # Activités passées créées
    passees_creees = Activity.query.filter_by(createur_id=uid, statut="Terminée").all()
    # Activités passées rejointes
    from datetime import timedelta
    aujourd_hui = date.today()
    passees_rejointes = []
    for a in user.activites_rejointes:
        try:
            dp = a.date_activite.split("/")
            dt = date(int(dp[2]), int(dp[1]), int(dp[0]))
            if dt < aujourd_hui and a.createur_id != uid:
                passees_rejointes.append(a)
        except Exception:
            pass
    # Stats
    total_acts = len(passees_creees) + len(passees_rejointes)
    villes_visitees = list(set(
        [a.lieu.split(",")[-1].strip() for a in passees_creees + passees_rejointes]
    ))
    types_count = {}
    for a in passees_creees + passees_rejointes:
        types_count[a.type_activite] = types_count.get(a.type_activite, 0) + 1
    type_favori = max(types_count, key=types_count.get) if types_count else "—"
    return render_template("mes_souvenirs.html", user=user,
                           passees_creees=passees_creees,
                           passees_rejointes=passees_rejointes,
                           total_acts=total_acts,
                           villes_visitees=villes_visitees,
                           type_favori=type_favori,
                           types_count=types_count)


@app.route("/mes-stats")
def mes_stats():
    if not session.get("user_id"): return redirect("/login")
    uid  = session["user_id"]
    user = User.query.get(uid)
    # XP calculation
    xp = (user.nb_activites_creees() * 25 +
          user.nb_participations() * 10 +
          int(user.reputation * 20) +
          len(Review.query.filter_by(cible_id=uid).all()) * 5)
    niveau_seuils = [
        (0,    "🌱 Débutant",   100),
        (100,  "🚀 Actif",      300),
        (300,  "⭐ Habitué",    700),
        (700,  "💎 Expert",    1500),
        (1500, "🏆 Légende",   9999),
    ]
    niveau_nom = "🌱 Débutant"
    xp_next = 100
    xp_current_min = 0
    for seuil, nom, prochain in niveau_seuils:
        if xp >= seuil:
            niveau_nom = nom
            xp_next = prochain
            xp_current_min = seuil
    xp_progress = min(100, int((xp - xp_current_min) / max(1, xp_next - xp_current_min) * 100))
    # Streak
    streak_obj = Streak.query.filter_by(user_id=uid).first()
    streak_val = streak_obj.valeur if streak_obj else 0
    # Badges
    badges = []
    if user.nb_activites_creees() >= 1:  badges.append({"icon":"🎯","nom":"Organisateur","xp":25})
    if user.nb_activites_creees() >= 5:  badges.append({"icon":"🏆","nom":"Super Org.","xp":125})
    if user.nb_participations() >= 3:    badges.append({"icon":"🤝","nom":"Sociable","xp":30})
    if user.nb_participations() >= 10:   badges.append({"icon":"⭐","nom":"Membre actif","xp":100})
    if user.reputation >= 4.5:           badges.append({"icon":"💎","nom":"Top membre","xp":90})
    if streak_val >= 7:                  badges.append({"icon":"🔥","nom":"Streak 7j","xp":70})
    # Défis mensuels
    defis = [
        {"nom":"Rejoins 3 activités ce mois","icone":"🎯","cible":3,"actuel":min(3,user.nb_participations()),"badge":"🌈 Explorateur"},
        {"nom":"Crée une activité","icone":"➕","cible":1,"actuel":min(1,user.nb_activites_creees()),"badge":"🎪 Organisateur"},
        {"nom":"Envoie 5 messages","icone":"💬","cible":5,"actuel":min(5,len(MessagePrive.query.filter_by(expediteur_id=uid).all())),"badge":"🗣️ Bavard"},
    ]
    return render_template("mes_stats.html", user=user,
                           xp=xp, niveau_nom=niveau_nom,
                           xp_next=xp_next, xp_current_min=xp_current_min,
                           xp_progress=xp_progress, streak_val=streak_val,
                           badges=badges, defis=defis)


@app.route("/manifest.json")
def pwa_manifest():
    """Manifeste PWA pour installation sur mobile"""
    manifest = {
        "name": "Let's Meet Morocco",
        "short_name": "LMM",
        "description": "Trouve des activités et rencontre des gens près de toi au Maroc",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0D2B12",
        "theme_color": "#E8541A",
        "orientation": "portrait-primary",
        "icons": [
            {"src": "/static/img/logo.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/img/logo.png", "sizes": "512x512", "type": "image/png"}
        ],
        "categories": ["social", "lifestyle", "sports"],
        "lang": "fr-MA"
    }
    from flask import Response
    return Response(json.dumps(manifest), mimetype="application/json")


@app.route("/sw.js")
def service_worker():
    from flask import Response, send_from_directory
    return send_from_directory(app.static_folder, "sw.js",
                               mimetype="application/javascript")


@app.route("/offline.html")
def offline():
    return render_template("offline.html")


# ══════════════════════════════════════════════════════════
# VÉRIFICATION EMAIL
# ══════════════════════════════════════════════════════════

@app.route("/verify-email", methods=["GET","POST"])
def verify_email_page():
    """Page de vérification email — saisie du code à 6 chiffres"""
    uid   = session.get("pending_verify_uid")
    email = session.get("pending_verify_email","")
    if not uid:
        return redirect("/login")
    error = None
    if request.method == "POST":
        try: verify_csrf()
        except: pass
        code_saisi = request.form.get("code","").strip().replace(" ","")
        tokens = EmailVerificationToken.query.filter_by(user_id=uid, utilise=False).all()
        for tok in tokens:
            if ":" in tok.token:
                stored_code, _ = tok.token.split(":", 1)
                if stored_code == code_saisi and tok.est_valide():
                    tok.utilise = True
                    user = User.query.get(uid)
                    user.email_verifie = True
                    db.session.commit()
                    session.pop("pending_verify_uid", None)
                    session.pop("pending_verify_email", None)
                    session["user_id"] = user.id
                    session["prenom"]  = user.prenom
                    session["nom"]     = user.nom
                    flash(f"✅ Email vérifié ! Bienvenue {user.prenom} sur Let's Meet Morocco 🎉", "success")
                    return redirect("/")
        error = "❌ Code invalide ou expiré. Vérifie le code reçu par email."
    return render_template("verify_email.html", email=email, error=error, csrf_token=generate_csrf())


@app.route("/verify-email/<token_str>")
def verify_email_link(token_str):
    """Vérification par clic direct sur le lien dans l'email"""
    tok = EmailVerificationToken.query.filter(
        EmailVerificationToken.token.like(f"%:{token_str}"),
        EmailVerificationToken.utilise == False
    ).first()
    if not tok or not tok.est_valide():
        flash("Lien expiré ou invalide. Demande un nouveau email de vérification.", "error")
        return redirect("/verify-email")
    tok.utilise = True
    user = User.query.get(tok.user_id)
    user.email_verifie = True
    db.session.commit()
    session.pop("pending_verify_uid", None)
    session.pop("pending_verify_email", None)
    session["user_id"] = user.id
    session["prenom"]  = user.prenom
    session["nom"]     = user.nom
    flash(f"✅ Email vérifié ! Bienvenue {user.prenom} 🎉", "success")
    return redirect("/")


@app.route("/resend-verification")
def resend_verification():
    """Renvoyer l'email de vérification"""
    uid = session.get("pending_verify_uid") or session.get("user_id")
    if not uid:
        return redirect("/login")
    user = User.query.get(uid)
    if not user or user.email_verifie:
        return redirect("/")
    send_verification_email(user)
    flash("📧 Nouvel email de vérification envoyé !", "success")
    return redirect("/verify-email")


@app.route("/health")
def health_check():
    """Endpoint pour Render/Railway pour vérifier que l'app tourne"""
    try:
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok", "db": "ok"}, 200
    except Exception as e:
        return {"status": "error", "db": str(e)}, 500


# ============================================================
# GESTION DES ERREURS
# ============================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html",
        code=404,
        titre="Page introuvable",
        message="La page que tu cherches n'existe pas ou a été déplacée.",
        icon="🔍"), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html",
        code=403,
        titre="Accès refusé",
        message="Tu n'as pas la permission d'accéder à cette page.",
        icon="🚫"), 403

@app.errorhandler(500)
def server_error(e):
    import traceback
    # Logger l'erreur sans l'exposer à l'utilisateur
    print(f"[500 ERROR] {traceback.format_exc()}")
    return render_template("error.html",
        code=500,
        titre="Erreur serveur",
        message="Quelque chose a mal tourné de notre côté. Réessaie dans quelques instants.",
        icon="⚠️"), 500

@app.errorhandler(413)
def too_large(e):
    return render_template("error.html",
        code=413,
        titre="Fichier trop volumineux",
        message="Le fichier uploadé dépasse la limite de 5 MB.",
        icon="📦"), 413

# ============================================================
# LANCEMENT
# ============================================================

if __name__ == "__main__":
    with app.app_context():
        init_db()
    is_dev = os.environ.get("FLASK_ENV","development") == "development"
    print("=" * 55)
    print("  Let's Meet Morocco v14")
    print("=" * 55)
    print("  URL  : http://127.0.0.1:5000")
    print("  Mode :", "DÉVELOPPEMENT" if is_dev else "PRODUCTION")
    if is_dev:
        print("  User : youssef@mail.com  / 1234")
        print("  User : salma@mail.com    / 1234")
        print("  Admin: admin@letsmeet.ma / admin123")
    print("=" * 55)
    app.run(debug=is_dev, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
