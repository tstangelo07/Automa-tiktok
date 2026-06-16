"""
Module Sourcing — Tendances TikTok
JVN Lab TikTok Automation
Fichier : src/sourcing/sourcing.py

Deux sources :
  1. TikTok Creative Center (gratuit, officiel)
  2. AI Toker API (payant, clé requise)
"""

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

AITOKER_API_KEY = os.getenv("AITOKER_API_KEY", "")

# ──────────────────────────────────────────────
# CONFIGURATION PAR COMPTE
# Mots-clés et hashtags ciblés par niche
# ──────────────────────────────────────────────

ACCOUNT_CONFIG = {
    "genalternance": {
        "keywords": ["alternance", "formation", "apprentissage", "rush school", "emploi jeune"],
        "hashtags": ["alternance", "formation", "apprentissage", "rushschool", "emploi"],
        "region": "FR",
        "niche": "Education / Formation"
    },
    "lea_beauty": {
        "keywords": ["skincare", "beauté", "soin visage", "routine beauté", "cosmétique"],
        "hashtags": ["skincare", "beauty", "soinsvisage", "routinebeaute", "cosmetique"],
        "region": "FR",
        "niche": "Beauté / Skincare"
    },
    "ia_facile": {
        "keywords": ["intelligence artificielle", "outil IA", "ChatGPT", "automatisation", "IA gratuit"],
        "hashtags": ["iafacile", "intelligenceartificielle", "chatgpt", "outils", "techpourtous"],
        "region": "FR",
        "niche": "IA Accessible"
    },
    "maison_neroli": {
        "keywords": ["décoration intérieure", "art de vivre", "ambiance maison", "parfum maison", "lifestyle élégant"],
        "hashtags": ["deco", "interieurdouce", "artdevivre", "lifestyle", "maisonneroli"],
        "region": "FR",
        "niche": "Art de Vivre / Déco"
    },
    "etrange_mais_vrai": {
        "keywords": ["fait étrange", "histoire vraie", "mystère", "inexpliqué", "fait insolite"],
        "hashtags": ["etrangemaisvrai", "faitsétranges", "mystery", "histoiresvraies", "insolite"],
        "region": "FR",
        "niche": "Faits Étranges / Mystères"
    },
    "patron_en_franchise": {
        "keywords": ["franchise", "devenir franchisé", "ouvrir une franchise", "quitter le salariat", "OpenFranchise"],
        "hashtags": ["franchise", "entrepreneuriat", "openfranchise", "patronenfranchise", "independance"],
        "region": "FR",
        "niche": "Franchise / Entrepreneuriat"
    },
}


# ──────────────────────────────────────────────
# SOURCE 1 — TIKTOK CREATIVE CENTER (gratuit)
# ──────────────────────────────────────────────

def fetch_tiktok_creative_center(account: str) -> list[dict]:
    """
    Fetch les tendances TikTok via le Creative Center.
    Endpoint public officiel TikTok — pas de clé requise.
    Retourne une liste de tendances avec score de viralité.
    """
    config = ACCOUNT_CONFIG.get(account)
    if not config:
        raise ValueError(f"Compte inconnu : {account}")

    print(f"\n [TikTok Creative Center] Fetch tendances pour '{account}'...")

    trends = []

    # ── Fetch hashtags tendance ──
    try:
        url = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
        params = {
            "page": 1,
            "limit": 20,
            "period": 7,          # 7 derniers jours
            "country_code": "FR",
            "industry_id": ""
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://ads.tiktok.com/business/creativecenter/hashtag/fr/pc/fr"
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            hashtag_list = data.get("data", {}).get("list", [])

            for item in hashtag_list[:10]:
                hashtag_name = item.get("hashtag_name", "")
                publish_cnt  = item.get("publish_cnt", 0)
                video_views  = item.get("video_views", 0)

                # Filtre par pertinence niche
                keywords = config["keywords"] + config["hashtags"]
                is_relevant = any(
                    kw.lower() in hashtag_name.lower()
                    for kw in keywords
                ) if keywords else True

                if is_relevant or len(trends) < 3:
                    trends.append({
                        "source": "tiktok_creative_center",
                        "type": "hashtag",
                        "trend": f"#{hashtag_name}",
                        "description": f"Hashtag #{hashtag_name} en tendance FR — {publish_cnt:,} publications, {video_views:,} vues",
                        "viral_score": min(10, round((video_views / 1_000_000), 1)) if video_views else 5,
                        "account": account,
                        "fetched_at": datetime.now().isoformat()
                    })

    except Exception as e:
        print(f"     TikTok Creative Center hashtags : {e}")

    # ── Fallback : tendances construites depuis les keywords du compte ──
    if len(trends) < 3:
        print(f"    Fallback sur tendances générées depuis les mots-clés du compte...")
        fallback_trends = generate_keyword_trends(account)
        trends.extend(fallback_trends)

    print(f"    {len(trends)} tendances récupérées via TikTok Creative Center")
    return trends[:10]


def generate_keyword_trends(account: str) -> list[dict]:
    """
    Génère des tendances pertinentes depuis les mots-clés du compte.
    Utilisé en fallback si l'API Creative Center est indisponible.
    """
    config = ACCOUNT_CONFIG[account]
    trends = []

    templates = [
        "Les {keyword} que personne ne te dit",
        "Pourquoi tu rates ta {keyword} en 2026",
        "3 erreurs fatales en {keyword}",
        "La vérité sur {keyword} que les experts cachent",
        "Comment j'ai tout changé grâce à {keyword}",
    ]

    for i, keyword in enumerate(config["keywords"][:5]):
        template = templates[i % len(templates)]
        trend_text = template.format(keyword=keyword)
        trends.append({
            "source": "keyword_fallback",
            "type": "generated_trend",
            "trend": trend_text,
            "description": f"Tendance générée depuis le mot-clé '{keyword}' pour la niche {config['niche']}",
            "viral_score": round(7 - i * 0.5, 1),
            "account": account,
            "fetched_at": datetime.now().isoformat()
        })

    return trends


# ──────────────────────────────────────────────
# SOURCE 2 — AI TOKER API (payant)
# ──────────────────────────────────────────────

def fetch_aitoker(account: str) -> list[dict]:
    """
    Fetch les tendances TikTok via AI Toker API.
    Requiert AITOKER_API_KEY dans le .env.
    Documentation : https://aitoker.com/api
    """
    if not AITOKER_API_KEY:
        print(f"     AITOKER_API_KEY manquante — skip AI Toker")
        return []

    config = ACCOUNT_CONFIG.get(account)
    if not config:
        raise ValueError(f"Compte inconnu : {account}")

    print(f"\n [AI Toker] Fetch tendances pour '{account}'...")

    try:
        # Endpoint AI Toker (à adapter selon leur doc officielle)
        url = "https://api.aitoker.com/v1/trends"
        headers = {
            "Authorization": f"Bearer {AITOKER_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "region": config["region"],
            "keywords": config["keywords"],
            "limit": 10,
            "period": "7d"
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        trends = []
        for item in data.get("trends", []):
            trends.append({
                "source": "aitoker",
                "type": item.get("type", "trend"),
                "trend": item.get("title", ""),
                "description": item.get("description", ""),
                "viral_score": item.get("viral_score", 5),
                "account": account,
                "fetched_at": datetime.now().isoformat()
            })

        print(f"    {len(trends)} tendances récupérées via AI Toker")
        return trends

    except Exception as e:
        print(f"    AI Toker erreur : {e}")
        return []


# ──────────────────────────────────────────────
# FONCTION PRINCIPALE — AGRÉGATION & SCORING
# ──────────────────────────────────────────────

def get_top_trends(account: str, top_n: int = 5) -> list[dict]:
    """
    Agrège les tendances de toutes les sources disponibles,
    déduplique, trie par score viral et retourne le top N.

    Args:
        account : Slug du compte (ex: "genalternance")
        top_n   : Nombre de tendances à retourner (défaut: 5)

    Returns:
        Liste des N meilleures tendances scorées
    """
    if account not in ACCOUNT_CONFIG:
        raise ValueError(f"Compte inconnu : {account}. Disponibles : {list(ACCOUNT_CONFIG.keys())}")

    print(f"\n Sourcing tendances — Compte: {account}")
    print(f"   Niche: {ACCOUNT_CONFIG[account]['niche']}")

    all_trends = []

    # Source 1 — TikTok Creative Center
    cc_trends = fetch_tiktok_creative_center(account)
    all_trends.extend(cc_trends)

    # Source 2 — AI Toker (si clé disponible)
    aitoker_trends = fetch_aitoker(account)
    all_trends.extend(aitoker_trends)

    # Déduplification par similarité de texte
    seen = set()
    unique_trends = []
    for t in all_trends:
        key = t["trend"].lower().strip()[:50]
        if key not in seen:
            seen.add(key)
            unique_trends.append(t)

    # Tri par score viral décroissant
    sorted_trends = sorted(unique_trends, key=lambda x: x.get("viral_score", 0), reverse=True)

    top_trends = sorted_trends[:top_n]

    print(f"\n Top {top_n} tendances sélectionnées pour '{account}' :")
    for i, t in enumerate(top_trends, 1):
        print(f"   {i}. [{t['source']}] {t['trend']} — Score: {t['viral_score']}/10")

    return top_trends


def get_best_trend(account: str) -> dict:
    """
    Retourne la meilleure tendance du moment pour un compte.
    C'est cette fonction que n8n appellera pour déclencher le pipeline.
    """
    trends = get_top_trends(account, top_n=5)
    if not trends:
        raise Exception(f"Aucune tendance trouvée pour {account}")

    best = trends[0]
    print(f"\n Meilleure tendance sélectionnée : '{best['trend']}' (score {best['viral_score']}/10)")
    return best


# ──────────────────────────────────────────────
# TEST RAPIDE
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("TEST MODULE SOURCING — JVN Lab")
    print("=" * 60)

    # Test sur tous les comptes
    accounts = list(ACCOUNT_CONFIG.keys())

    for account in accounts[:2]:  # Test sur les 2 premiers pour la démo
        print(f"\n{'='*60}")
        try:
            best = get_best_trend(account)
            print(f"\n Résultat final pour '{account}' :")
            print(f"   Tendance : {best['trend']}")
            print(f"   Source   : {best['source']}")
            print(f"   Score    : {best['viral_score']}/10")
            print(f"   Fetched  : {best['fetched_at']}")

        except Exception as e:
            print(f" Erreur pour {account} : {e}")

    print(f"\n{'='*60}")
    print("Test terminé ! Prochaine étape : brancher ce module à claude_client.py")
    print("Pipeline : get_best_trend() → generate_scripts() → ElevenLabs → Higgsfield")