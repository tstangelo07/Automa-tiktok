"""
Script d'initialisation de la base de données PostgreSQL
JVN Lab TikTok Automation
Fichier : scripts/init_db.py

Usage :
  python scripts/init_db.py           # Crée les tables si elles n'existent pas
  python scripts/init_db.py --reset   # Supprime et recrée toutes les tables ( perte de données)
  python scripts/init_db.py --status  # Affiche l'état des tables existantes
"""

import os
import sys
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# ──────────────────────────────────────────────
# SCHÉMA SQL
# ──────────────────────────────────────────────

TABLES = {

    "videos": """
        CREATE TABLE IF NOT EXISTS videos (
            id          SERIAL PRIMARY KEY,
            account     VARCHAR(50)     NOT NULL,
            trend       TEXT,
            script      TEXT,
            tiktok_id   VARCHAR(100),
            status      VARCHAR(30)     DEFAULT 'pending',
            cost_eur    DECIMAL(8,5)    DEFAULT 0,
            views_j1    INT             DEFAULT 0,
            views_j7    INT             DEFAULT 0,
            likes_j7    INT             DEFAULT 0,
            shares_j7   INT             DEFAULT 0,
            created_at  TIMESTAMP       DEFAULT NOW(),
            updated_at  TIMESTAMP       DEFAULT NOW()
        );
        COMMENT ON TABLE videos IS 'Suivi de chaque vidéo produite et publiée';
        COMMENT ON COLUMN videos.status IS 'pending | sourcing_done | ideation_done | assets_done | assembled | qa_pending | published | failed';
    """,

    "pipeline_logs": """
        CREATE TABLE IF NOT EXISTS pipeline_logs (
            id          SERIAL PRIMARY KEY,
            video_id    INT             REFERENCES videos(id) ON DELETE CASCADE,
            step        VARCHAR(50)     NOT NULL,
            status      VARCHAR(20)     NOT NULL,
            error       TEXT,
            duration_ms INT             DEFAULT 0,
            metadata    JSONB,
            logged_at   TIMESTAMP       DEFAULT NOW()
        );
        COMMENT ON TABLE pipeline_logs IS 'Logs détaillés de chaque étape du pipeline par vidéo';
        COMMENT ON COLUMN pipeline_logs.step IS 'sourcing | ideation | audio | video | images | assembly | qa | publication';
        COMMENT ON COLUMN pipeline_logs.status IS 'success | error | warning | skipped';
    """,

    "scripts_generated": """
        CREATE TABLE IF NOT EXISTS scripts_generated (
            id          SERIAL PRIMARY KEY,
            video_id    INT             REFERENCES videos(id) ON DELETE CASCADE,
            hook        TEXT,
            corps       TEXT,
            cta         TEXT,
            hashtags    JSONB,
            angle       TEXT,
            duree_estimee VARCHAR(10),
            score       INT             DEFAULT 0,
            score_details JSONB,
            selected    BOOLEAN         DEFAULT FALSE,
            model_used  VARCHAR(50),
            created_at  TIMESTAMP       DEFAULT NOW()
        );
        COMMENT ON TABLE scripts_generated IS 'Historique de tous les scripts générés par Claude API';
        COMMENT ON COLUMN scripts_generated.score IS 'Score /10 : hook(4) + corps(3) + conformité(3)';
    """,

    "assets": """
        CREATE TABLE IF NOT EXISTS assets (
            id          SERIAL PRIMARY KEY,
            video_id    INT             REFERENCES videos(id) ON DELETE CASCADE,
            type        VARCHAR(30)     NOT NULL,
            url         TEXT,
            local_path  TEXT,
            provider    VARCHAR(50),
            model_used  VARCHAR(100),
            duration_s  DECIMAL(6,2),
            cost_eur    DECIMAL(8,5)    DEFAULT 0,
            metadata    JSONB,
            created_at  TIMESTAMP       DEFAULT NOW()
        );
        COMMENT ON TABLE assets IS 'Référencement de tous les assets générés (audio, clips, images)';
        COMMENT ON COLUMN assets.type IS 'audio | video_hook | video_body_1 | video_body_2 | video_cta | image_cutaway | subtitles';
    """,

    "performance": """
        CREATE TABLE IF NOT EXISTS performance (
            id          SERIAL PRIMARY KEY,
            video_id    INT             REFERENCES videos(id) ON DELETE CASCADE,
            recorded_at TIMESTAMP       DEFAULT NOW(),
            period      VARCHAR(10),
            views       INT             DEFAULT 0,
            likes       INT             DEFAULT 0,
            shares      INT             DEFAULT 0,
            comments    INT             DEFAULT 0,
            watch_pct   DECIMAL(5,2)    DEFAULT 0,
            reach       INT             DEFAULT 0,
            saves       INT             DEFAULT 0
        );
        COMMENT ON TABLE performance IS 'Métriques TikTok par vidéo — relevés à J+1 et J+7';
        COMMENT ON COLUMN performance.period IS 'j1 | j7 | j30';
    """,

    "accounts": """
        CREATE TABLE IF NOT EXISTS accounts (
            id          SERIAL PRIMARY KEY,
            slug        VARCHAR(50)     UNIQUE NOT NULL,
            name        VARCHAR(100),
            niche       VARCHAR(100),
            tiktok_handle VARCHAR(100),
            status      VARCHAR(20)     DEFAULT 'warmup',
            profile_id  VARCHAR(100),
            proxy_zone  VARCHAR(100),
            voice_id    VARCHAR(100),
            created_at  TIMESTAMP       DEFAULT NOW(),
            updated_at  TIMESTAMP       DEFAULT NOW()
        );
        COMMENT ON TABLE accounts IS 'Registre des 6 comptes TikTok gérés par le pipeline';
        COMMENT ON COLUMN accounts.status IS 'warmup | active | paused | banned';
    """,
}

# Données initiales pour les 6 comptes
INITIAL_ACCOUNTS = [
    ("genalternance",   "GenAlternance",    "Alternance / Formation / Rush School", "active"),
    ("lea_beauty",      "Léa Beauty",       "Beauté / Skincare",                    "active"),
    ("compte_3",        "Compte Finance",   "Finance / Investissement FR",          "warmup"),
    ("compte_4",        "Compte Tech IA",   "Tech / Intelligence Artificielle",     "warmup"),
    ("compte_5",        "Compte Immo",      "Immobilier / Investissement locatif",  "warmup"),
    ("compte_6",        "Compte Lifestyle", "Productivité / Lifestyle Premium",     "warmup"),
]

# Index pour optimiser les requêtes fréquentes
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_videos_account    ON videos(account);",
    "CREATE INDEX IF NOT EXISTS idx_videos_status     ON videos(status);",
    "CREATE INDEX IF NOT EXISTS idx_videos_created    ON videos(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_logs_video_id     ON pipeline_logs(video_id);",
    "CREATE INDEX IF NOT EXISTS idx_logs_step         ON pipeline_logs(step);",
    "CREATE INDEX IF NOT EXISTS idx_scripts_video_id  ON scripts_generated(video_id);",
    "CREATE INDEX IF NOT EXISTS idx_scripts_selected  ON scripts_generated(selected);",
    "CREATE INDEX IF NOT EXISTS idx_assets_video_id   ON assets(video_id);",
    "CREATE INDEX IF NOT EXISTS idx_assets_type       ON assets(type);",
    "CREATE INDEX IF NOT EXISTS idx_perf_video_id     ON performance(video_id);",
    "CREATE INDEX IF NOT EXISTS idx_accounts_slug     ON accounts(slug);",
]


# ──────────────────────────────────────────────
# FONCTIONS
# ──────────────────────────────────────────────

def get_connection():
    """Connexion PostgreSQL"""
    if not DATABASE_URL:
        print(" DATABASE_URL manquante dans le .env")
        sys.exit(1)
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f" Connexion DB échouée : {e}")
        sys.exit(1)


def get_existing_tables(cur) -> list:
    """Retourne la liste des tables existantes"""
    cur.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename;
    """)
    return [row[0] for row in cur.fetchall()]


def show_status():
    """Affiche l'état actuel de la base de données"""
    print("\n ÉTAT DE LA BASE DE DONNÉES")
    print("=" * 50)

    conn = get_connection()
    cur  = conn.cursor()

    existing = get_existing_tables(cur)
    expected = list(TABLES.keys())

    print(f"\nTables attendues : {len(expected)}")
    print(f"Tables existantes : {len(existing)}\n")

    for table in expected:
        if table in existing:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            print(f"  {table:<25} — {count} lignes")
        else:
            print(f"   {table:<25} — MANQUANTE")

    # Tables inattendues
    extra = [t for t in existing if t not in expected]
    if extra:
        print(f"\nTables supplémentaires : {extra}")

    cur.close()
    conn.close()
    print("\n" + "=" * 50)


def reset_db(conn, cur):
    """Supprime toutes les tables (DANGER — perte de données)"""
    print("\n  RESET : Suppression de toutes les tables...")
    tables_order = ["performance", "assets", "scripts_generated", "pipeline_logs", "videos", "accounts"]
    for table in tables_order:
        cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
        print(f"     Table '{table}' supprimée")
    conn.commit()
    print("    Reset terminé\n")


def create_tables(conn, cur):
    """Crée toutes les tables et index"""
    existing = get_existing_tables(cur)

    print("\n Création des tables...")
    for table_name, sql in TABLES.items():
        cur.execute(sql)
        if table_name in existing:
            print(f"     '{table_name}' — déjà existante (ignorée)")
        else:
            print(f"    '{table_name}' — créée")

    print("\n Création des index...")
    for idx_sql in INDEXES:
        cur.execute(idx_sql)
    print(f"    {len(INDEXES)} index créés")

    conn.commit()


def insert_initial_accounts(conn, cur):
    """Insère les 6 comptes initiaux si la table est vide"""
    cur.execute("SELECT COUNT(*) FROM accounts;")
    count = cur.fetchone()[0]

    if count == 0:
        print("\n👥 Insertion des 6 comptes initiaux...")
        for slug, name, niche, status in INITIAL_ACCOUNTS:
            cur.execute("""
                INSERT INTO accounts (slug, name, niche, status)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (slug) DO NOTHING;
            """, (slug, name, niche, status))
            print(f"    {name} ({slug}) — {status}")
        conn.commit()
    else:
        print(f"\n👥 Comptes déjà présents ({count} entrées) — ignoré")


def verify_connection():
    """Teste la connexion et affiche les infos"""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()[0]
    cur.execute("SELECT current_database();")
    db_name = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"   Serveur  : {version.split(',')[0]}")
    print(f"   Database : {db_name}")
    print(f"   URL      : {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    print("=" * 50)
    print("  JVN LAB — Init Base de Données")
    print(f"   {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 50)

    # Vérification connexion
    print("\n Connexion à PostgreSQL...")
    verify_connection()
    print("    Connexion OK")

    # Mode --status
    if "--status" in args:
        show_status()
        return

    # Connexion pour modifications
    conn = get_connection()
    cur  = conn.cursor()

    try:
        # Mode --reset
        if "--reset" in args:
            confirm = input("\n  ATTENTION : Cette opération supprime TOUTES les données.\n   Tapez 'RESET' pour confirmer : ")
            if confirm != "RESET":
                print(" Reset annulé.")
                return
            reset_db(conn, cur)

        # Création des tables
        create_tables(conn, cur)

        # Insertion comptes initiaux
        insert_initial_accounts(conn, cur)

        # Résumé final
        print("\n" + "=" * 50)
        print(" Base de données initialisée avec succès !")
        print("=" * 50)
        show_status()

    except Exception as e:
        conn.rollback()
        print(f"\n Erreur : {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()