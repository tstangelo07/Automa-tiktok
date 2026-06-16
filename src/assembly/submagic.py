"""
Module Sous-titres — Submagic API + FFmpeg fallback
JVN Lab TikTok Automation
Fichier : src/assembly/submagic.py

Deux modes :
  1. Submagic API (priorité) — sous-titres animés premium
  2. FFmpeg Whisper fallback — sous-titres basiques si Submagic indisponible

Usage :
  python3 src/assembly/submagic.py --test output/audio/test.mp3
  python3 src/assembly/submagic.py --burn output/audio/test.mp3 output/final/video.mp4
"""

import os
import sys
import json
import time
from tkinter import font
import requests
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SUBMAGIC_API_KEY = os.getenv("SUBMAGIC_API_KEY", "")
OUTPUT_DIR       = Path("output/subtitles")

# ──────────────────────────────────────────────
# STYLE DES SOUS-TITRES PAR COMPTE
# ──────────────────────────────────────────────

SUBTITLE_STYLE = {
    "genalternance": {
        "font":       "Arial Bold",
        "fontsize":   60,
        "color":      "white",
        "stroke":     "black",
        "stroke_width": 2,
        "position":   "center",
        "animation":  "pop",         # Submagic : pop, slide, fade
        "max_words":  4,             # Mots par sous-titre
        "description": "Blanc gras, impact, style social media"
    },
    "lea_beauty": {
        "font":       "Georgia",
        "fontsize":   52,
        "color":      "#FFE4E1",     # Rose pâle
        "stroke":     "#8B0000",
        "stroke_width": 1,
        "position":   "center",
        "animation":  "fade",
        "max_words":  5,
        "description": "Rose pastel, élégant, style beauté"
    },
    "ia_facile": {
        "font":       "Arial Bold",
        "fontsize":   58,
        "color":      "#00FF88",     # Vert tech
        "stroke":     "black",
        "stroke_width": 2,
        "position":   "center",
        "animation":  "pop",
        "max_words":  4,
        "description": "Vert tech, dynamique, style numérique"
    },
    "maison_neroli": {
        "font":       "Georgia Italic",
        "fontsize":   48,
        "color":      "#F5E6D0",     # Beige chaud
        "stroke":     "#5C4033",
        "stroke_width": 1,
        "position":   "center",
        "animation":  "fade",
        "max_words":  5,
        "description": "Beige chaud, élégant, style lifestyle"
    },
    "etrange_mais_vrai": {
        "font":       "Arial Bold",
        "fontsize":   58,
        "color":      "#FF4444",     # Rouge mystère
        "stroke":     "black",
        "stroke_width": 3,
        "position":   "center",
        "animation":  "slide",
        "max_words":  4,
        "description": "Rouge tendu, dramatique, style mystère"
    },
    "pause_douce": {
        "font":       "Georgia",
        "fontsize":   50,
        "color":      "#FFF8F0",     # Crème doux
        "stroke":     "#8B7355",
        "stroke_width": 1,
        "position":   "center",
        "animation":  "fade",
        "max_words":  5,
        "description": "Crème doux, apaisant, style bien-être"
    },
}


# ──────────────────────────────────────────────
# GÉNÉRATION SRT DEPUIS LE TEXTE (fallback local)
# ──────────────────────────────────────────────

def text_to_srt(text: str, audio_duration: float, max_words: int = 4) -> str:
    """
    Génère un fichier SRT basique depuis un texte et une durée audio.
    Découpe le texte en chunks de max_words mots, répartis sur la durée.

    Args:
        text          : Texte complet du script
        audio_duration: Durée de l'audio en secondes
        max_words     : Nombre de mots max par sous-titre

    Returns:
        Contenu SRT formaté
    """
    # Nettoyage du texte (supprime les balises SSML)
    import re
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    # Découpe en mots
    words = clean_text.split()
    if not words:
        return ""

    # Découpe en chunks
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
        chunks.append(chunk)

    # Calcul des timestamps
    time_per_chunk = audio_duration / len(chunks)
    srt_lines      = []

    for i, chunk in enumerate(chunks):
        start_s = i * time_per_chunk
        end_s   = (i + 1) * time_per_chunk - 0.1  # petit gap entre sous-titres

        start_str = seconds_to_srt_time(start_s)
        end_str   = seconds_to_srt_time(end_s)

        srt_lines.append(f"{i + 1}")
        srt_lines.append(f"{start_str} --> {end_str}")
        srt_lines.append(chunk)
        srt_lines.append("")

    return "\n".join(srt_lines)


def seconds_to_srt_time(seconds: float) -> str:
    """Convertit des secondes en format SRT (HH:MM:SS,mmm)"""
    hours   = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs    = int(seconds % 60)
    millis  = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def save_srt(srt_content: str, output_path: str) -> str:
    """Sauvegarde le fichier SRT"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    return output_path


# ──────────────────────────────────────────────
# SUBMAGIC API
# ──────────────────────────────────────────────

def generate_subtitles_submagic(
    audio_path: str,
    account: str,
    script_text: str = "",
) -> dict:
    """
    Génère des sous-titres animés via Submagic API.
    Retourne l'URL du fichier SRT ou ASS animé.
    """
    if not SUBMAGIC_API_KEY:
        raise EnvironmentError("SUBMAGIC_API_KEY manquante dans le .env")

    style = SUBTITLE_STYLE.get(account, SUBTITLE_STYLE["genalternance"])

    print(f"\n Génération sous-titres Submagic — {account}")
    print(f"   Style : {style['description']}")

    headers = {
        "Authorization": f"Bearer {SUBMAGIC_API_KEY}",
        "Content-Type": "application/json"
    }

    # Upload audio vers Submagic
    with open(audio_path, "rb") as f:
        upload_resp = requests.post(
            "https://api.submagic.co/v1/transcribe",
            headers={"Authorization": f"Bearer {SUBMAGIC_API_KEY}"},
            files={"audio": f},
            data={
                "language": "fr",
                "style": style["animation"],
                "max_words_per_caption": style["max_words"],
                "font_size": style["fontsize"],
                "font_color": style["color"],
            },
            timeout=60
        )

    if upload_resp.status_code not in [200, 201, 202]:
        raise Exception(f"Submagic erreur {upload_resp.status_code}: {upload_resp.text[:200]}")

    job_data = upload_resp.json()
    job_id   = job_data.get("id") or job_data.get("job_id")

    if not job_id:
        raise Exception(f"Pas de job_id Submagic : {job_data}")

    print(f"    Job soumis : {job_id}")

    # Polling
    max_wait = 120
    start    = time.time()
    while time.time() - start < max_wait:
        time.sleep(5)
        status_resp = requests.get(
            f"https://api.submagic.co/v1/transcribe/{job_id}",
            headers=headers,
            timeout=15
        )
        status_data   = status_resp.json()
        status        = status_data.get("status", "pending")

        if status in ["completed", "done", "success"]:
            srt_url = status_data.get("srt_url") or status_data.get("output_url")
            print(f"    Sous-titres prêts : {srt_url}")
            return {
                "source":  "submagic",
                "job_id":  job_id,
                "srt_url": srt_url,
                "style":   style["description"]
            }
        elif status in ["failed", "error"]:
            raise Exception(f"Submagic job échoué : {status_data}")

    raise Exception(f"Submagic timeout après {max_wait}s")


# ──────────────────────────────────────────────
# FALLBACK LOCAL (sans Submagic)
# ──────────────────────────────────────────────

def generate_subtitles_local(
    audio_path: str,
    account: str,
    script_text: str,
    audio_duration: float = None,
) -> dict:
    """
    Génère un SRT basique localement depuis le texte du script.
    Fallback si Submagic est indisponible ou non souscrit.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    style    = SUBTITLE_STYLE.get(account, SUBTITLE_STYLE["genalternance"])
    max_words = style["max_words"]

    # Récupère la durée audio via FFprobe
    if audio_duration is None:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            audio_duration = float(result.stdout.strip())
        except:
            audio_duration = 30.0

    print(f"\n Génération SRT local — {account}")
    print(f"   Durée audio  : {audio_duration:.1f}s")
    print(f"   Mots/sous-titre : {max_words}")

    # Génère le SRT
    srt_content = text_to_srt(script_text, audio_duration, max_words)

    # Sauvegarde
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    srt_path   = str(OUTPUT_DIR / f"{account}_{timestamp}.srt")
    save_srt(srt_content, srt_path)

    nb_subs = srt_content.count("\n\n")
    print(f"    SRT généré : {srt_path} ({nb_subs} sous-titres)")

    return {
        "source":       "local",
        "srt_path":     srt_path,
        "srt_content":  srt_content,
        "duration_s":   audio_duration,
        "nb_subtitles": nb_subs,
        "style":        style["description"]
    }


# ──────────────────────────────────────────────
# BURN-IN DES SOUS-TITRES SUR LA VIDÉO
# ──────────────────────────────────────────────

def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
    account: str,
) -> str:
    """
    Incruste les sous-titres SRT directement sur la vidéo via FFmpeg.
    Le style visuel est défini par compte.

    Args:
        video_path  : Vidéo source
        srt_path    : Fichier SRT
        output_path : Vidéo de sortie avec sous-titres
        account     : Slug du compte pour le style

    Returns:
        Chemin de la vidéo avec sous-titres
    """
    style = SUBTITLE_STYLE.get(account, SUBTITLE_STYLE["genalternance"])

    # Couleur hexadécimale → format FFmpeg (&HAABBGGRR)
    def hex_to_ass_color(hex_color: str) -> str:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            return f"&H00{b}{g}{r}"
        return "&H00FFFFFF"

    font_color   = hex_to_ass_color(style["color"]) if style["color"].startswith("#") else "&H00FFFFFF"
    stroke_color = hex_to_ass_color(style["stroke"]) if style["stroke"].startswith("#") else "&H00000000"

    # Style SubRip pour FFmpeg
    
    font      = style['font']
    fontsize  = style['fontsize']
    sw        = style['stroke_width']

    subtitle_filter = (
        f"subtitles={srt_path}:"
        f"force_style='"
        f"FontName={font},"
        f"FontSize={fontsize},"
        f"PrimaryColour={font_color},"
        f"OutlineColour={stroke_color},"
        f"Outline={sw},"
        f"Alignment=2,"
        f"MarginV=100"
        f"'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", subtitle_filter,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "copy",
        output_path
    ]

    print(f"\n Burn-in sous-titres — {account}")
    result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0:
        # Fallback sans style custom si erreur de police
        print(f"     Style custom échoué, fallback simple...")
        cmd_simple = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles={srt_path}",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            output_path
        ]
        result2 = subprocess.run(cmd_simple, capture_output=True)
        if result2.returncode != 0:
            raise Exception(f"Burn-in échoué : {result2.stderr.decode()[:200]}")

    print(f"    Sous-titres incrustés : {output_path}")
    return output_path


# ──────────────────────────────────────────────
# FONCTION PRINCIPALE — UTILISÉE PAR LE PIPELINE
# ──────────────────────────────────────────────

def add_subtitles_to_video(
    video_path: str,
    audio_path: str,
    account: str,
    script_text: str,
    output_path: str = None,
) -> dict:
    """
    Ajoute les sous-titres à une vidéo assemblée.
    Essaie Submagic d'abord, fallback local si indisponible.

    Args:
        video_path  : Vidéo assemblée (output moviepy_builder.py)
        audio_path  : Audio MP3 (pour la durée et transcription)
        account     : Slug du compte
        script_text : Texte du script (pour SRT local)
        output_path : Chemin de sortie (auto si None)

    Returns:
        dict avec chemin de la vidéo finale avec sous-titres
    """
    if output_path is None:
        output_path = video_path.replace(".mp4", "_subtitled.mp4")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Essaie Submagic en priorité
    srt_path = None
    if SUBMAGIC_API_KEY:
        try:
            result = generate_subtitles_submagic(audio_path, account, script_text)
            # Télécharge le SRT si URL
            if result.get("srt_url"):
                srt_path = str(OUTPUT_DIR / f"{account}_submagic.srt")
                srt_resp = requests.get(result["srt_url"], timeout=30)
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(srt_resp.text)
        except Exception as e:
            print(f"     Submagic indisponible ({e}) — fallback local")

    # Fallback local si Submagic échoué
    if not srt_path:
        result = generate_subtitles_local(
            audio_path=audio_path,
            account=account,
            script_text=script_text,
        )
        srt_path = result["srt_path"]

    # Burn-in sur la vidéo
    final_path = burn_subtitles(
        video_path=video_path,
        srt_path=srt_path,
        output_path=output_path,
        account=account,
    )

    file_size = round(os.path.getsize(final_path) / 1_000_000, 1)

    return {
        "account":        account,
        "final_path":     final_path,
        "srt_path":       srt_path,
        "file_size_mb":   file_size,
        "subtitle_source": "submagic" if SUBMAGIC_API_KEY else "local",
        "subtitled_at":   datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--test" in args and len(args) >= 2:
        # Test SRT local depuis un audio
        audio_path = args[1]
        account    = args[2] if len(args) > 2 else "genalternance"

        if not os.path.exists(audio_path):
            print(f" Fichier audio introuvable : {audio_path}")
            sys.exit(1)

        script_test = (
            "Les entreprises recherchent des alternants maintenant. "
            "Voilà comment décrocher ton contrat en 2026 en trois étapes simples. "
            "Suis le compte pour la suite."
        )

        result = generate_subtitles_local(
            audio_path=audio_path,
            account=account,
            script_text=script_test,
        )

        print(f"\n SRT généré : {result['srt_path']}")
        print(f"   Durée    : {result['duration_s']}s")
        print(f"   Lignes   : {result['nb_subtitles']}")
        print(f"\n Aperçu :")
        print(result["srt_content"][:500])

    elif "--burn" in args and len(args) >= 3:
        # Burn-in sur une vidéo existante
        audio_path = args[1]
        video_path = args[2]
        account    = args[3] if len(args) > 3 else "genalternance"
        script     = args[4] if len(args) > 4 else "Texte de test pour les sous-titres."
        output     = video_path.replace(".mp4", "_subtitled.mp4")

        result = add_subtitles_to_video(
            video_path=video_path,
            audio_path=audio_path,
            account=account,
            script_text=script,
            output_path=output,
        )
        print(f"\n Vidéo avec sous-titres : {result['final_path']}")

    else:
        print("Usage :")
        print("  python3 submagic.py --test <audio.mp3> [account]")
        print("  python3 submagic.py --burn <audio.mp3> <video.mp4> [account] [script]")
        print(f"\nComptes : {list(SUBTITLE_STYLE.keys())}")