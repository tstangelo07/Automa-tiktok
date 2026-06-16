"""
Module Sous-titres — Whisper (sync précise) + Submagic API
JVN Lab TikTok Automation
Fichier : src/assembly/submagic.py

Modes :
  1. Submagic API (si clé dispo) — sous-titres animés premium
  2. Whisper local (fallback) — transcription précise + burn-in FFmpeg

Usage :
  python3 src/assembly/submagic.py --test output/audio/test.mp3 genalternance
  python3 src/assembly/submagic.py --burn output/audio/test.mp3 output/final/video.mp4 genalternance
"""

import os
import sys
import json
import time
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
        "font":         "Arial",
        "fontsize":     25,
        "color":        "white",
        "stroke":       "black",
        "stroke_width": 2,
        "max_words":    3,
        "animation":    "pop",
        "description":  "Blanc gras, impact, style social media"
    },
    "lea_beauty": {
        "font":         "Arial",
        "fontsize":     26,
        "color":        "#FFE4E1",
        "stroke":       "#8B0000",
        "stroke_width": 1,
        "max_words":    5,
        "animation":    "fade",
        "description":  "Rose pastel, élégant, style beauté"
    },
    "ia_facile": {
        "font":         "Arial",
        "fontsize":     38,
        "color":        "#00FF88",
        "stroke":       "black",
        "stroke_width": 2,
        "max_words":    4,
        "animation":    "pop",
        "description":  "Vert tech, dynamique, style numérique"
    },
    "maison_neroli": {
        "font":         "Arial",
        "fontsize":     34,
        "color":        "#F5E6D0",
        "stroke":       "#5C4033",
        "stroke_width": 1,
        "max_words":    5,
        "animation":    "fade",
        "description":  "Beige chaud, élégant, style lifestyle"
    },
    "etrange_mais_vrai": {
        "font":         "Arial",
        "fontsize":     38,
        "color":        "#FF4444",
        "stroke":       "black",
        "stroke_width": 3,
        "max_words":    4,
        "animation":    "slide",
        "description":  "Rouge tendu, dramatique, style mystère"
    },
    "pause_douce": {
        "font":         "Arial",
        "fontsize":     34,
        "color":        "#FFF8F0",
        "stroke":       "#8B7355",
        "stroke_width": 1,
        "max_words":    5,
        "animation":    "fade",
        "description":  "Crème doux, apaisant, style bien-être"
    },
}


# ──────────────────────────────────────────────
# UTILITAIRES
# ──────────────────────────────────────────────

def seconds_to_srt_time(seconds: float) -> str:
    """Convertit des secondes en format SRT HH:MM:SS,mmm"""
    hours   = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs    = int(seconds % 60)
    millis  = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def hex_to_ass_color(hex_color: str) -> str:
    """Convertit une couleur hex en format ASS pour FFmpeg"""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H00{b}{g}{r}"
    return "&H00FFFFFF"


def get_audio_duration(audio_path: str) -> float:
    """Récupère la durée d'un fichier audio via ffprobe"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 30.0


# ──────────────────────────────────────────────
# TRANSCRIPTION WHISPER (sync précise)
# ──────────────────────────────────────────────

def transcribe_with_whisper(audio_path: str, language: str = "fr") -> list:
    """
    Transcrit un audio avec Whisper et retourne les segments
    avec timestamps précis.

    Returns:
        Liste de segments : [{"start": float, "end": float, "text": str}]
    """
    try:
        import whisper
    except ImportError:
        raise ImportError("Whisper non installé — pip install openai-whisper")

    print(f"     Transcription Whisper (modèle 'base')...")
    model  = whisper.load_model("base")
    result = model.transcribe(
        audio_path,
        language=language,
        word_timestamps=True,
        verbose=False
    )

    # Extraction des segments mot par mot
    word_segments = []
    for segment in result.get("segments", []):
        for word_info in segment.get("words", []):
            word_segments.append({
                "start": word_info["start"],
                "end":   word_info["end"],
                "text":  word_info["word"].strip()
            })

    print(f"    {len(word_segments)} mots transcrits")
    return word_segments


def words_to_srt(word_segments: list, max_words: int = 4) -> str:
    """
    Regroupe les mots en chunks de max_words et génère le SRT
    avec les vrais timestamps Whisper.

    Args:
        word_segments : Liste de mots avec timestamps
        max_words     : Mots max par sous-titre

    Returns:
        Contenu SRT formaté et synchronisé
    """
    if not word_segments:
        return ""

    # Regroupe les mots en chunks
    chunks = []
    for i in range(0, len(word_segments), max_words):
        group = word_segments[i:i + max_words]
        chunks.append({
            "start": group[0]["start"],
            "end":   group[-1]["end"],
            "text":  " ".join(w["text"] for w in group).strip()
        })

    # Génère le SRT
    srt_lines = []
    for i, chunk in enumerate(chunks):
        # Petit gap entre sous-titres
        end_time = min(chunk["end"], chunk["end"] - 0.05)
        srt_lines.append(str(i + 1))
        srt_lines.append(
            f"{seconds_to_srt_time(chunk['start'])} --> "
            f"{seconds_to_srt_time(end_time)}"
        )
        srt_lines.append(chunk["text"])
        srt_lines.append("")

    return "\n".join(srt_lines)


# ──────────────────────────────────────────────
# FALLBACK — SRT depuis texte (sans Whisper)
# ──────────────────────────────────────────────

def text_to_srt_basic(
    text: str,
    audio_duration: float,
    max_words: int = 4
) -> str:
    """
    Génère un SRT basique depuis le texte (sans Whisper).
    Moins précis mais fonctionne sans GPU ni modèle IA.
    """
    import re
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    words = clean.split()

    if not words:
        return ""

    chunks = [
        " ".join(words[i:i + max_words])
        for i in range(0, len(words), max_words)
    ]

    time_per = audio_duration / len(chunks)
    lines    = []

    for i, chunk in enumerate(chunks):
        start = i * time_per
        end   = (i + 1) * time_per - 0.1
        lines.append(str(i + 1))
        lines.append(
            f"{seconds_to_srt_time(start)} --> "
            f"{seconds_to_srt_time(end)}"
        )
        lines.append(chunk)
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# GÉNÉRATION SRT PRINCIPALE
# ──────────────────────────────────────────────

def generate_srt(
    audio_path: str,
    account: str,
    script_text: str = "",
    use_whisper: bool = True,
) -> dict:
    """
    Génère un fichier SRT synchronisé.
    Essaie Whisper en priorité, fallback texte si indisponible.

    Args:
        audio_path  : Chemin vers le fichier MP3
        account     : Slug du compte (pour le style)
        script_text : Texte du script (pour le fallback)
        use_whisper : Utiliser Whisper (True par défaut)

    Returns:
        dict avec srt_path, nb_subtitles, source
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    style     = SUBTITLE_STYLE.get(account, SUBTITLE_STYLE["genalternance"])
    max_words = style["max_words"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    srt_path  = str(OUTPUT_DIR / f"{account}_{timestamp}.srt")

    srt_content = ""
    source      = "unknown"

    # Mode 1 — Whisper (synchronisation précise)
    if use_whisper:
        try:
            print(f"\n Génération SRT Whisper — {account}")
            word_segments = transcribe_with_whisper(audio_path)
            srt_content   = words_to_srt(word_segments, max_words)
            source        = "whisper"
        except ImportError:
            print("     Whisper non installé — fallback texte")
            print("    Pour installer : pip install openai-whisper")
            use_whisper = False
        except Exception as e:
            print(f"    Whisper erreur ({e}) — fallback texte")
            use_whisper = False

    # Mode 2 — Fallback texte (moins précis)
    if not use_whisper or not srt_content:
        print(f"\n Génération SRT basique — {account}")
        audio_dur   = get_audio_duration(audio_path)
        srt_content = text_to_srt_basic(script_text, audio_dur, max_words)
        source      = "text_basic"

    if not srt_content:
        raise Exception("Impossible de générer le SRT")

    # Sauvegarde
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    nb_subs = srt_content.count("\n\n")
    print(f"    SRT généré : {srt_path} ({nb_subs} sous-titres) [{source}]")

    return {
        "srt_path":     srt_path,
        "srt_content":  srt_content,
        "nb_subtitles": nb_subs,
        "source":       source,
        "style":        style["description"],
    }


# ──────────────────────────────────────────────
# BURN-IN SUR LA VIDÉO
# ──────────────────────────────────────────────

def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
    account: str,
) -> str:
    """
    Incruste les sous-titres SRT sur la vidéo via FFmpeg.
    Style visuel adapté par compte.
    """
    style        = SUBTITLE_STYLE.get(account, SUBTITLE_STYLE["genalternance"])
    font_name    = style["font"]
    fontsize     = style["fontsize"]
    stroke_width = style["stroke_width"]

    # Couleurs
    color  = style["color"]
    stroke = style["stroke"]

    if color.startswith("#"):
        font_color = hex_to_ass_color(color)
    else:
        font_color = "&H00FFFFFF"  # blanc par défaut

    if stroke.startswith("#"):
        stroke_color = hex_to_ass_color(stroke)
    else:
        stroke_color = "&H00000000"  # noir par défaut

    # Chemin SRT absolu (requis par FFmpeg)
    srt_abs = os.path.abspath(srt_path)

    # Filter complexe avec style
    vf_filter = (
        f"subtitles={srt_abs}:force_style="
        f"'FontName={font_name},"
        f"FontSize={fontsize},"
        f"PrimaryColour={font_color},"
        f"OutlineColour={stroke_color},"
        f"Outline={stroke_width},"
        f"Shadow=1,"
        f"Alignment=2,"
        f"MarginV=80'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "copy",
        output_path
    ]

    print(f"\n Burn-in sous-titres — {account}")
    print(f"   Style    : {style['description']}")
    print(f"   Fonte    : {font_name} {fontsize}px")

    result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0:
        # Fallback simple sans style custom
        print(f"     Style custom échoué — fallback sans style")
        cmd_simple = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles={srt_abs}",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            output_path
        ]
        result2 = subprocess.run(cmd_simple, capture_output=True)
        if result2.returncode != 0:
            raise Exception(
                f"Burn-in échoué :\n{result2.stderr.decode()[:300]}"
            )
        print(f"    Sous-titres incrustés (style basique)")
    else:
        print(f"    Sous-titres incrustés")

    return output_path


# ──────────────────────────────────────────────
# FONCTION PRINCIPALE PIPELINE
# ──────────────────────────────────────────────

def add_subtitles_to_video(
    video_path: str,
    audio_path: str,
    account: str,
    script_text: str = "",
    output_path: str = None,
    use_whisper: bool = True,
) -> dict:
    """
    Pipeline complet : génère le SRT puis l'incruste sur la vidéo.
    Utilisé par pipeline.py et moviepy_builder.py.
    """
    if output_path is None:
        output_path = video_path.replace(".mp4", "_subtitled.mp4")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Génération SRT
    srt_result = generate_srt(
        audio_path=audio_path,
        account=account,
        script_text=script_text,
        use_whisper=use_whisper,
    )

    # Burn-in
    burn_subtitles(
        video_path=video_path,
        srt_path=srt_result["srt_path"],
        output_path=output_path,
        account=account,
    )

    file_size = round(os.path.getsize(output_path) / 1_000_000, 1)

    return {
        "account":         account,
        "final_path":      output_path,
        "srt_path":        srt_result["srt_path"],
        "srt_source":      srt_result["source"],
        "nb_subtitles":    srt_result["nb_subtitles"],
        "file_size_mb":    file_size,
        "subtitled_at":    datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--test" in args and len(args) >= 2:
        idx        = args.index("--test")
        audio_path = args[idx + 1]
        account    = args[idx + 2] if len(args) > idx + 2 else "genalternance"

        if not os.path.exists(audio_path):
            print(f" Audio introuvable : {audio_path}")
            sys.exit(1)

        result = generate_srt(
            audio_path=audio_path,
            account=account,
            script_text="",
            use_whisper=True,
        )
        print(f"\n SRT : {result['srt_path']}")
        print(f"   Source  : {result['source']}")
        print(f"   Lignes  : {result['nb_subtitles']}")
        print(f"\n Aperçu :\n{result['srt_content'][:600]}")

    elif "--burn" in args and len(args) >= 3:
        idx        = args.index("--burn")
        audio_path = args[idx + 1]
        video_path = args[idx + 2]
        account    = args[idx + 3] if len(args) > idx + 3 else "genalternance"
        script     = args[idx + 4] if len(args) > idx + 4 else ""
        output     = video_path.replace(".mp4", "_subtitled.mp4")

        result = add_subtitles_to_video(
            video_path=video_path,
            audio_path=audio_path,
            account=account,
            script_text=script,
            output_path=output,
            use_whisper=True,
        )
        print(f"\n Vidéo finale : {result['final_path']}")
        print(f"   Taille  : {result['file_size_mb']} MB")
        print(f"   Source  : {result['srt_source']}")
        print(f"   Lignes  : {result['nb_subtitles']}")

    else:
        print("Usage :")
        print("  python3 submagic.py --test <audio.mp3> [account]")
        print("  python3 submagic.py --burn <audio.mp3> <video.mp4> [account]")
        print(f"\nComptes : {list(SUBTITLE_STYLE.keys())}")