"""
Module Génération Vidéo B-roll — Higgsfield AI
JVN Lab TikTok Automation
Fichier : src/generation/video/higgsfield.py

Modèles disponibles :
  - higgsfield-ai/dop/lite     → Tests & CTA (économique)
  - higgsfield-ai/dop/standard → Corps de vidéo (bon rapport qualité/prix)
  - higgsfield-ai/dop/turbo    → Hook d'ouverture (meilleure qualité)

Usage :
  python src/generation/video/higgsfield.py --diag
  python src/generation/video/higgsfield.py genalternance body_1 "Prompt du clip"
"""

import os
import sys
import requests
import higgsfield_client
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Auth via variables d'environnement (lues automatiquement par le SDK)
# HF_API_KEY et HF_API_SECRET dans le .env

OUTPUT_DIR = Path("output/video")

# ──────────────────────────────────────────────
# CONFIGURATION DES MODÈLES
# ──────────────────────────────────────────────

CLIP_CONFIG = {
    "hook": {
        "model": "higgsfield-ai/dop/turbo",
        "description": "Hook d'ouverture — meilleure qualité visuelle, 1ère seconde critique",
        "credits_estimate": 500,
        "cost_usd_estimate": 0.50,
    },
    "body_1": {
        "model": "higgsfield-ai/dop/standard",
        "description": "Corps vidéo 1 — développement du message principal",
        "credits_estimate": 250,
        "cost_usd_estimate": 0.25,
    },
    "body_2": {
        "model": "higgsfield-ai/dop/standard",
        "description": "Corps vidéo 2 — argument complémentaire",
        "credits_estimate": 250,
        "cost_usd_estimate": 0.25,
    },
    "cta": {
        "model": "higgsfield-ai/dop/lite",
        "description": "CTA final — économique, moins critique visuellement",
        "credits_estimate": 200,
        "cost_usd_estimate": 0.12,
    },
}

# ──────────────────────────────────────────────
# STYLE VISUEL PAR COMPTE
# ──────────────────────────────────────────────

VISUAL_STYLE = {
    "genalternance": (
        "young French professional, modern office environment, warm lighting, "
        "signing contract, photorealistic, cinematic"
    ),
    "lea_beauty": (
        "beauty studio, skincare products, pastel colors, soft feminine lighting, "
        "elegant aesthetic, photorealistic, cinematic"
    ),
    "ia_facile": (
        "person using laptop with AI interface, bright modern workspace, "
        "friendly and approachable, photorealistic"
    ),
    "maison_neroli": (
        "elegant interior, noble materials, natural light, linen and brass, "
        "slow living aesthetic, warm tones, cinematic"
    ),
    "etrange_mais_vrai": (
        "mysterious atmospheric scene, desaturated cinematic look, "
        "documentary style, dramatic lighting, photorealistic"
    ),
    "pause_douce": (
        "cozy evening atmosphere, warm candlelight, soft textiles, "
        "hands holding tea cup, gentle and soothing, cinematic"
    ),
}

# Image de test par défaut (sera remplacée par Midjourney en prod)
DEFAULT_TEST_IMAGE = "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=640"

# Images de test par compte (plus pertinentes visuellement)
TEST_IMAGES = {
    "genalternance":  "https://images.unsplash.com/photo-1521737852567-6949f3f9f2b5?w=640",
    "lea_beauty":     "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=640",
    "ia_facile":      "https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=640",
    "maison_neroli":  "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=640",
    "etrange_mais_vrai": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=640",
    "pause_douce":    "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=640",
}


# ──────────────────────────────────────────────
# GÉNÉRATION D'UN CLIP
# ──────────────────────────────────────────────

def generate_clip(
    prompt: str,
    account: str,
    clip_type: str = "body_1",
    image_url: str = None,
    save_local: bool = True,
) -> dict:
    """
    Génère un clip vidéo via Higgsfield DoP.

    Args:
        prompt     : Description du mouvement/scène
        account    : Slug du compte (ex: "genalternance")
        clip_type  : Type de clip (hook, body_1, body_2, cta)
        image_url  : URL de l'image de base (Midjourney en prod, Unsplash en test)
        save_local : Sauvegarder le fichier en local

    Returns:
        dict avec URL du clip, chemin local, crédits utilisés
    """
    if clip_type not in CLIP_CONFIG:
        raise ValueError(
            f"Type de clip inconnu : '{clip_type}'. "
            f"Disponibles : {list(CLIP_CONFIG.keys())}"
        )

    config     = CLIP_CONFIG[clip_type]
    style      = VISUAL_STYLE.get(account, "photorealistic, cinematic, high quality")
    full_prompt = f"{prompt}, {style}"

    # Image source : Midjourney en prod, test image en dev
    source_image = (
        image_url or
        TEST_IMAGES.get(account, DEFAULT_TEST_IMAGE)
    )

    print(f"\n Génération clip Higgsfield")
    print(f"   Compte    : {account}")
    print(f"   Type      : {clip_type}")
    print(f"   Modèle    : {config['model']}")
    print(f"   Prompt    : {full_prompt[:100]}...")
    print(f"   Image src : {source_image[:60]}...")
    print(f"   Crédits   : ~{config['credits_estimate']}")

    # Soumission du job
    ctrl = higgsfield_client.submit(
        config["model"],
        arguments={
            "prompt": full_prompt,
            "image_url": source_image,
        }
    )

    print(f"    Job soumis : {ctrl.request_id}")
    print(f"    En attente de génération (1-3 min)...")

    # Polling jusqu'à completion
    for status in ctrl.poll_request_status(delay=5):
        status_name = type(status).__name__
        if status_name not in ("Queued", "InProgress"):
            print(f"    Statut final : {status_name}")
        elif status_name == "InProgress":
            print(f"    {status_name}...", end="\r")

    # Récupération du résultat
    result_data = ctrl.get()
    video_url   = result_data.get("video", {}).get("url")

    if not video_url:
        raise Exception(f"Pas d'URL vidéo dans la réponse : {result_data}")

    print(f"\n    Clip généré : {video_url}")

    result = {
        "account":           account,
        "clip_type":         clip_type,
        "model":             config["model"],
        "request_id":        ctrl.request_id,
        "prompt":            full_prompt,
        "source_image":      source_image,
        "video_url":         video_url,
        "local_path":        None,
        "credits_used":      config["credits_estimate"],
        "cost_usd_estimate": config["cost_usd_estimate"],
        "generated_at":      datetime.now().isoformat(),
    }

    # Téléchargement local
    if save_local and video_url:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename   = f"{account}_{clip_type}_{timestamp}.mp4"
        local_path = OUTPUT_DIR / filename

        print(f"    Téléchargement...")
        dl = requests.get(video_url, timeout=120)
        local_path.write_bytes(dl.content)
        result["local_path"] = str(local_path)
        size_mb = len(dl.content) / 1_000_000
        print(f"    Sauvegardé : {local_path} ({size_mb:.1f} MB)")

    return result


def generate_all_clips(
    script: dict,
    account: str,
    image_url: str = None,
    video_id: int = None,
) -> list:
    """
    Génère les 4 clips pour une vidéo complète.
    Utilisé par le pipeline orchestrateur (src/pipeline.py).

    Args:
        script    : Script complet (output de claude_client.py)
        account   : Slug du compte
        image_url : Image Midjourney de base (optionnel — test image si absent)
        video_id  : ID vidéo en base (pour nommage)

    Returns:
        Liste des 4 clips générés avec leurs métadonnées
    """
    print(f"\n Génération complète — 4 clips pour '{account}'")

    # Construction des prompts depuis le script Claude
    hook_prompt  = f"{script.get('hook', '')} — dynamic opening"
    body1_prompt = f"{script.get('corps', '')[:120]} — informative visual"
    body2_prompt = f"{script.get('corps', '')[-120:]} — complementary scene"
    cta_prompt   = f"{script.get('cta', '')} — call to action"

    clip_map = [
        ("hook",   hook_prompt),
        ("body_1", body1_prompt),
        ("body_2", body2_prompt),
        ("cta",    cta_prompt),
    ]

    clips          = []
    total_credits  = 0
    total_cost_usd = 0

    for clip_type, prompt in clip_map:
        try:
            clip = generate_clip(
                prompt=prompt,
                account=account,
                clip_type=clip_type,
                image_url=image_url,
                save_local=True,
            )
            clips.append(clip)
            total_credits  += clip["credits_used"]
            total_cost_usd += clip["cost_usd_estimate"]
            print(f"    {clip_type} OK")

        except Exception as e:
            print(f"    {clip_type} échoué : {e}")
            clips.append({
                "clip_type": clip_type,
                "status":    "error",
                "error":     str(e)
            })

    print(f"\n  Total crédits : {total_credits}")
    print(f"    Coût estimé   : ~${total_cost_usd:.2f}")
    return clips


# ──────────────────────────────────────────────
# DIAGNOSTIC
# ──────────────────────────────────────────────

def run_diagnostics():
    """Affiche les infos de configuration et vérifie l'accès API"""
    print("\n DIAGNOSTIC HIGGSFIELD AI")
    print("=" * 50)

    api_key    = os.getenv("HF_API_KEY", "")
    api_secret = os.getenv("HF_API_SECRET", "")

    if not api_key or not api_secret:
        print(" HF_API_KEY ou HF_API_SECRET manquants dans le .env")
        return

    print(f" HF_API_KEY    : {api_key[:8]}...")
    print(f" HF_API_SECRET : {api_secret[:8]}...")

    print(f"\n🎬 Modèles configurés :")
    for clip_type, config in CLIP_CONFIG.items():
        print(f"   {clip_type:<10} → {config['model']:<35} ~{config['credits_estimate']} crédits (~${config['cost_usd_estimate']})")

    print(f"\n Styles visuels par compte :")
    for account, style in VISUAL_STYLE.items():
        print(f"   {account:<20} → {style[:60]}...")

    print(f"\n  Images de test par compte :")
    for account, img in TEST_IMAGES.items():
        print(f"   {account:<20} → {img[:60]}...")

    print("\n" + "=" * 50)


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--diag" in args or len(args) == 0:
        run_diagnostics()
        sys.exit(0)

    # Mode génération : python higgsfield.py <account> <clip_type> "<prompt>"
    if len(args) >= 3:
        account   = args[0]
        clip_type = args[1]
        prompt    = args[2]
        image_url = args[3] if len(args) >= 4 else None

        try:
            result = generate_clip(
                prompt=prompt,
                account=account,
                clip_type=clip_type,
                image_url=image_url,
            )
            print(f"\n Succès !")
            print(f"   URL    : {result['video_url']}")
            print(f"   Local  : {result['local_path']}")
            print(f"   Coût   : ~${result['cost_usd_estimate']}")
        except Exception as e:
            print(f"\n Erreur : {e}")
            sys.exit(1)

    else:
        print("Usage :")
        print("  python higgsfield.py --diag")
        print("  python higgsfield.py <account> <clip_type> \"<prompt>\"")
        print("  python higgsfield.py <account> <clip_type> \"<prompt>\" <image_url>")
        print(f"\nClip types : {list(CLIP_CONFIG.keys())}")
        print(f"Comptes    : {list(VISUAL_STYLE.keys())}")