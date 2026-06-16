"""
Module Génération Voix Off — ElevenLabs Pro
JVN Lab TikTok Automation
Fichier : src/generation/audio/elevenlabs.py

Usage :
  python src/generation/audio/elevenlabs.py genalternance "Voici le texte à générer"
"""

import os
import sys
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
BASE_URL = "https://api.elevenlabs.io/v1"
OUTPUT_DIR = Path("output/audio")

# ──────────────────────────────────────────────
# CONFIGURATION VOIX PAR COMPTE
# Voice IDs à remplacer par les vrais IDs après clonage
# Pour obtenir vos Voice IDs : GET /v1/voices
# ──────────────────────────────────────────────

VOICE_CONFIG = {
    "genalternance": {
        "voice_id": os.getenv("VOICE_ID_GENALTERNANCE", "21m00Tcm4TlvDq8ikWAM"),  # Rachel (démo)
        "name": "GenAlternance Voice",
        "stability": 0.65,
        "similarity_boost": 0.75,
        "style": 0.15,
        "use_speaker_boost": False,
        "model_id": "eleven_multilingual_v2",
        "description": "Voix masculine dynamique et bienveillante — ton jeune professionnel"
    },
    "lea_beauty": {
        "voice_id": os.getenv("VOICE_ID_LEA_BEAUTY", "EXAVITQu4vr4xnSDxMaL"),  # Bella (démo)
        "name": "Léa Beauty Voice",
        "stability": 0.65, 
        "similarity_boost": 0.80,
        "style": 0.4,
        "use_speaker_boost": True,
        "model_id": "eleven_multilingual_v2",
        "description": "Voix féminine chaleureuse et lifestyle — ton expert accessible"
    },
    "compte_3": {
        "voice_id": os.getenv("VOICE_ID_COMPTE_3", "VR6AewLTigWG4xSOukaG"),  # Arnold (démo)
        "name": "Finance Voice",
        "stability": 0.7,
        "similarity_boost": 0.75,
        "style": 0.2,
        "use_speaker_boost": True,
        "model_id": "eleven_multilingual_v2",
        "description": "Voix masculine crédible et pédagogique — ton expert finance"
    },
    "compte_4": {
        "voice_id": os.getenv("VOICE_ID_COMPTE_4", "pNInz6obpgDQGcFmaJgB"),  # Adam (démo)
        "name": "Tech IA Voice",
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.35,
        "use_speaker_boost": True,
        "model_id": "eleven_multilingual_v2",
        "description": "Voix masculine enthousiaste et tech — ton early adopter"
    },
    "compte_5": {
        "voice_id": os.getenv("VOICE_ID_COMPTE_5", "yoZ06aMxZJJ28mfd3POQ"),  # Sam (démo)
        "name": "Immobilier Voice",
        "stability": 0.65,
        "similarity_boost": 0.80,
        "style": 0.25,
        "use_speaker_boost": True,
        "model_id": "eleven_multilingual_v2",
        "description": "Voix masculine rassurante et pragmatique — ton expert immo"
    },
    "compte_6": {
        "voice_id": os.getenv("VOICE_ID_COMPTE_6", "AZnzlk1XvdvUeBnXmlld"),  # Domi (démo)
        "name": "Lifestyle Voice",
        "stability": 0.55,
        "similarity_boost": 0.75,
        "style": 0.45,
        "use_speaker_boost": True,
        "model_id": "eleven_multilingual_v2",
        "description": "Voix inspirante et directe — ton coach pragmatique"
    },
}

HEADERS = {
    "xi-api-key": ELEVENLABS_API_KEY,
    "Content-Type": "application/json"
}


# ──────────────────────────────────────────────
# FONCTIONS UTILITAIRES
# ──────────────────────────────────────────────

def check_api_key() -> bool:
    """Vérifie que la clé API est valide"""
    if not ELEVENLABS_API_KEY:
        print(" ELEVENLABS_API_KEY manquante dans le .env")
        return False
    resp = requests.get(f"{BASE_URL}/user", headers=HEADERS, timeout=10)
    return resp.status_code == 200


def get_available_voices() -> list:
    """Retourne toutes les voix disponibles sur le compte"""
    resp = requests.get(f"{BASE_URL}/voices", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    voices = resp.json().get("voices", [])
    return voices


def get_subscription_info() -> dict:
    """Retourne les infos d'abonnement et quota restant"""
    resp = requests.get(f"{BASE_URL}/user/subscription", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def build_script_text(script: dict) -> str:
    """
    Construit le texte avec pauses SSML pour une voix naturelle.
    Les balises <break> ajoutent des respirations entre les phrases.
    """
    parts = []

    if script.get("hook"):
        parts.append(script["hook"])

    if script.get("corps"):
        # Ajoute une pause après le hook
        parts.append("<break time='0.6s'/>")
        # Découpe le corps en phrases et ajoute des micro-pauses
        phrases = [p.strip() for p in script["corps"].split(".") if p.strip()]
        parts.append(". <break time='0.4s'/>".join(phrases) + ".")

    if script.get("cta"):
        # Pause plus longue avant le CTA
        parts.append("<break time='0.8s'/>")
        parts.append(script["cta"])

    return " ".join(parts)


def estimate_duration(text: str) -> float:
    """
    Estime la durée audio en secondes.
    Moyenne : ~140 mots/minute en français TikTok (débit rapide)
    """
    word_count = len(text.split())
    return round(word_count / 140 * 60, 1)


# ──────────────────────────────────────────────
# GÉNÉRATION AUDIO
# ──────────────────────────────────────────────

def generate_voiceover(
    text: str,
    account: str,
    output_filename: str = None,
    save_local: bool = True
) -> dict:
    """
    Génère un fichier audio MP3 depuis un texte via ElevenLabs.

    Args:
        text            : Texte à synthétiser
        account         : Slug du compte (ex: "genalternance")
        output_filename : Nom du fichier de sortie (auto-généré si None)
        save_local      : Sauvegarder le fichier en local

    Returns:
        dict avec chemin du fichier, durée estimée, coût estimé
    """
    if account not in VOICE_CONFIG:
        raise ValueError(f"Compte inconnu : {account}. Disponibles : {list(VOICE_CONFIG.keys())}")

    if not ELEVENLABS_API_KEY:
        raise EnvironmentError("ELEVENLABS_API_KEY manquante dans le .env")

    config = VOICE_CONFIG[account]
    voice_id = config["voice_id"]

    print(f"\n  Génération voix off — Compte: {account}")
    print(f"   Voix      : {config['name']} ({voice_id})")
    print(f"   Modèle    : {config['model_id']}")
    print(f"   Texte     : {text[:80]}{'...' if len(text) > 80 else ''}")
    print(f"   Mots      : {len(text.split())} (~{estimate_duration(text)}s estimé)")

    # Payload ElevenLabs
    payload = {
        "text": text,
        "model_id": config["model_id"],
        "voice_settings": {
            "stability": config["stability"],
            "similarity_boost": config["similarity_boost"],
            "style": config["style"],
            "use_speaker_boost": config["use_speaker_boost"]
        }
    }

    # Appel API
    url = f"{BASE_URL}/text-to-speech/{voice_id}"
    params = {"output_format": "mp3_44100_128"}

    resp = requests.post(url, json=payload, headers=HEADERS, params=params, timeout=60)

    if resp.status_code != 200:
        error_msg = resp.json().get("detail", {}).get("message", resp.text)
        raise Exception(f"ElevenLabs API erreur {resp.status_code}: {error_msg}")

    # Sauvegarde du fichier
    result = {
        "account": account,
        "text": text,
        "voice_id": voice_id,
        "voice_name": config["name"],
        "duration_estimated_s": estimate_duration(text),
        "char_count": len(text),
        "cost_eur_estimated": round(len(text) * 0.00003 * 0.93, 5),  # ~0.03$/1k chars converti en €
        "generated_at": datetime.now().isoformat(),
        "local_path": None
    }

    if save_local:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if not output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{account}_{timestamp}.mp3"
        output_path = OUTPUT_DIR / output_filename
        output_path.write_bytes(resp.content)
        result["local_path"] = str(output_path)
        print(f"    Audio généré : {output_path}")
        print(f"    Coût estimé  : {result['cost_eur_estimated']} €")
        print(f"    Durée estimée : {result['duration_estimated_s']}s")

    return result


def generate_from_script(script: dict, account: str, video_id: int = None) -> dict:
    """
    Génère la voix off depuis un script complet généré par Claude.
    Utilisé directement par le pipeline orchestrateur.

    Args:
        script   : Dict contenant hook, corps, cta (output de claude_client.py)
        account  : Slug du compte
        video_id : ID de la vidéo en base (pour nommer le fichier)

    Returns:
        dict avec résultat de génération
    """
    text = build_script_text(script)

    if not text.strip():
        raise ValueError("Script vide — impossible de générer la voix off")

    filename = f"{account}_video{video_id or 'test'}_{datetime.now().strftime('%H%M%S')}.mp3"

    return generate_voiceover(
        text=text,
        account=account,
        output_filename=filename,
        save_local=True
    )


# ──────────────────────────────────────────────
# TEST & DIAGNOSTIC
# ──────────────────────────────────────────────

def run_diagnostics():
    """Vérifie la connexion API et affiche les infos du compte"""
    print("\n DIAGNOSTIC ELEVENLABS")
    print("=" * 50)

    # Vérification clé
    if not ELEVENLABS_API_KEY:
        print(" ELEVENLABS_API_KEY manquante dans le .env")
        return

    print(" Clé API présente")

    # Infos abonnement
    try:
        sub = get_subscription_info()
        tier = sub.get("tier", "inconnu")
        chars_used = sub.get("character_count", 0)
        chars_limit = sub.get("character_limit", 0)
        chars_remaining = chars_limit - chars_used
        next_reset = sub.get("next_character_count_reset_unix", "")

        print(f"\n Abonnement :")
        print(f"   Plan          : {tier}")
        print(f"   Chars utilisés : {chars_used:,} / {chars_limit:,}")
        print(f"   Chars restants : {chars_remaining:,}")
        print(f"   Prochain reset : {next_reset}")
    except Exception as e:
        print(f"  Impossible de récupérer les infos abonnement : {e}")

    # Voix disponibles
    try:
        voices = get_available_voices()
        print(f"\n  Voix disponibles ({len(voices)}) :")
        for v in voices[:10]:
            vtype = v.get("category", "")
            print(f"   - {v['name']:<30} ID: {v['voice_id']} [{vtype}]")
        if len(voices) > 10:
            print(f"   ... et {len(voices)-10} autres")
    except Exception as e:
        print(f"  Impossible de récupérer les voix : {e}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    args = sys.argv[1:]

    # Mode diagnostic
    if "--diag" in args or len(args) == 0:
        run_diagnostics()
        sys.exit(0)

    # Mode génération : python elevenlabs.py <account> "<texte>"
    if len(args) >= 2:
        account = args[0]
        text    = args[1]

        try:
            result = generate_voiceover(text=text, account=account)
            print(f"\n Succès ! Fichier : {result['local_path']}")
        except Exception as e:
            print(f"\n Erreur : {e}")
            sys.exit(1)
    else:
        print("Usage : python elevenlabs.py <account> \"<texte>\"")
        print("        python elevenlabs.py --diag")
        print("\nComptes disponibles :", list(VOICE_CONFIG.keys()))