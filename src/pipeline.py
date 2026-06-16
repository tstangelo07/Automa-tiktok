"""
Pipeline Orchestrateur — Sourcing → Idéation
JVN Lab TikTok Automation
Fichier : src/pipeline.py

Enchaîne :
  1. Sourcing (TikTok Creative Center / AI Toker)
  2. Idéation (Claude API → 3 scripts scorés)
  3. Log en base PostgreSQL
"""

import os
import json
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Import des modules
from sourcing.sourcing import get_best_trend, ACCOUNT_CONFIG
from ideation.claude_client import generate_scripts

DATABASE_URL = os.getenv("DATABASE_URL", "")


# ──────────────────────────────────────────────
# CONNEXION BASE DE DONNÉES
# ──────────────────────────────────────────────

def get_db_connection():
    """Connexion PostgreSQL via DATABASE_URL"""
    if not DATABASE_URL:
        print("     DATABASE_URL manquante — logs désactivés")
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"     DB connexion échouée : {e}")
        return None


def log_video_to_db(conn, account: str, trend: str, best_script: dict, cost_eur: float) -> int | None:
    """
    Insère une entrée dans la table videos et scripts_generated.
    Retourne l'ID de la vidéo créée.
    """
    if not conn:
        return None
    try:
        cur = conn.cursor()

        # Insertion dans videos
        cur.execute("""
            INSERT INTO videos (account, script, status, cost_eur, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            account,
            best_script.get("corps", ""),
            "ideation_done",
            cost_eur,
            datetime.now()
        ))
        video_id = cur.fetchone()[0]

        # Insertion dans scripts_generated
        cur.execute("""
            INSERT INTO scripts_generated (video_id, hook, corps, cta, hashtags, score, selected, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            video_id,
            best_script.get("hook", ""),
            best_script.get("corps", ""),
            best_script.get("cta", ""),
            json.dumps(best_script.get("hashtags", []), ensure_ascii=False),
            best_script.get("score", 0),
            True,
            datetime.now()
        ))

        # Log pipeline
        cur.execute("""
            INSERT INTO pipeline_logs (video_id, step, status, logged_at)
            VALUES (%s, %s, %s, %s)
        """, (video_id, "ideation", "success", datetime.now()))

        conn.commit()
        cur.close()
        print(f"    Vidéo #{video_id} loggée en base")
        return video_id

    except Exception as e:
        print(f"   Erreur DB log : {e}")
        conn.rollback()
        return None


# ──────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ──────────────────────────────────────────────

def run_pipeline(account: str, dry_run: bool = False) -> dict:
    """
    Exécute le pipeline Sourcing → Idéation pour un compte.

    Args:
        account  : Slug du compte (ex: "genalternance")
        dry_run  : Si True, ne logue pas en base

    Returns:
        dict avec le résultat complet du pipeline
    """
    start_time = datetime.now()
    print(f"\n{'='*60}")
    print(f" PIPELINE JVN LAB — {account.upper()}")
    print(f"   Démarrage : {start_time.strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    result = {
        "account": account,
        "status": "pending",
        "started_at": start_time.isoformat(),
        "trend": None,
        "best_script": None,
        "video_id": None,
        "cost_eur": 0,
        "duration_seconds": 0,
        "error": None
    }

    try:
        # ── ÉTAPE 1 : SOURCING ──
        print(f"\n ÉTAPE 1/2 — Sourcing tendances...")
        trend = get_best_trend(account)
        result["trend"] = trend["trend"]
        print(f"   Tendance : '{trend['trend']}' (score {trend['viral_score']}/10)")

        # ── ÉTAPE 2 : IDÉATION ──
        print(f"\n ÉTAPE 2/2 — Génération scripts Claude...")
        scripts_result = generate_scripts(
            trend=trend["trend"],
            account=account
        )

        best_script = scripts_result["best_script"]
        cost_eur = scripts_result["usage"]["cost_eur_estimate"]
        result["best_script"] = best_script
        result["cost_eur"] = cost_eur

        print(f"\n    Script sélectionné (score {best_script['score']}/10) :")
        print(f"   Hook  : {best_script['hook']}")
        print(f"   Corps : {best_script['corps'][:80]}...")
        print(f"   CTA   : {best_script['cta']}")
        print(f"    Coût : {cost_eur} €")

        # ── LOG BASE DE DONNÉES ──
        if not dry_run:
            conn = get_db_connection()
            if conn:
                video_id = log_video_to_db(conn, account, trend["trend"], best_script, cost_eur)
                result["video_id"] = video_id
                conn.close()

        # ── RÉSULTAT ──
        duration = (datetime.now() - start_time).seconds
        result["status"] = "ideation_done"
        result["duration_seconds"] = duration

        print(f"\n{'='*60}")
        print(f" Pipeline terminé en {duration}s — Prêt pour génération assets (S3)")
        print(f"{'='*60}")

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"\n Erreur pipeline : {e}")

    return result


def run_all_accounts(dry_run: bool = False) -> list[dict]:
    """
    Exécute le pipeline pour tous les 6 comptes.
    Appelé par n8n chaque matin à 5h00 UTC.
    """
    accounts = list(ACCOUNT_CONFIG.keys())
    results = []

    print(f"\n{'='*60}")
    print(f" PIPELINE QUOTIDIEN JVN LAB — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"   {len(accounts)} comptes à traiter")
    print(f"{'='*60}")

    for account in accounts:
        result = run_pipeline(account, dry_run=dry_run)
        results.append(result)

        # Résumé rapide
        status_icon = "✅" if result["status"] == "ideation_done" else "❌"
        print(f"\n{status_icon} {account} : {result['status']} — coût {result['cost_eur']} €")

    # Résumé global
    total_cost = sum(r["cost_eur"] for r in results)
    success_count = sum(1 for r in results if r["status"] == "ideation_done")

    print(f"\n{'='*60}")
    print(f" RÉSUMÉ QUOTIDIEN")
    print(f"   Comptes traités : {success_count}/{len(accounts)}")
    print(f"   Coût total      : {round(total_cost, 5)} €")
    print(f"{'='*60}")

    return results


# ──────────────────────────────────────────────
# TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Test sur un seul compte en dry_run (pas de log DB)
    account = sys.argv[1] if len(sys.argv) > 1 else "genalternance"

    print(f"Mode : dry_run (pas de log DB)")
    result = run_pipeline(account, dry_run=True)

    # Sauvegarde résultat
    output_file = f"test_pipeline_{account}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n Résultat sauvegardé dans {output_file}")