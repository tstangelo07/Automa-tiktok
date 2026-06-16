"""
Module Assemblage Vidéo — FFmpeg
JVN Lab TikTok Automation
Fichier : src/assembly/moviepy_builder.py

Pipeline :
  1. Resize clips en 1080x1920 (9:16 TikTok)
  2. Concatène les clips
  3. Boucle si vidéo trop courte par rapport à l'audio
  4. Synchronise la voix off
  5. Ajoute le watermark discret
  6. Injecte les métadonnées EXIF uniques
  7. Exporte en MP4 1080p optimisé TikTok

Usage :
  python3 src/assembly/moviepy_builder.py --check
  python3 src/assembly/moviepy_builder.py --test genalternance
  python3 src/assembly/moviepy_builder.py --assemble config.json
"""

import os
import sys
import json
import random
import hashlib
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path("output/final")
TEMP_DIR   = Path("output/temp")

# ──────────────────────────────────────────────
# CONFIGURATION PAR COMPTE
# ──────────────────────────────────────────────

ACCOUNT_CONFIG = {
    "genalternance": {
        "watermark_text":     "GenAlternance",
        "watermark_position": "bottom_right",
        "watermark_opacity":  0.3,
    },
    "lea_beauty": {
        "watermark_text":     "Léa Beauty • Avatar IA",
        "watermark_position": "bottom_center",
        "watermark_opacity":  0.25,
    },
    "ia_facile": {
        "watermark_text":     "L'IA Facile",
        "watermark_position": "bottom_right",
        "watermark_opacity":  0.3,
    },
    "maison_neroli": {
        "watermark_text":     "Maison Néroli",
        "watermark_position": "bottom_center",
        "watermark_opacity":  0.2,
    },
    "etrange_mais_vrai": {
        "watermark_text":     "Étrange mais Vrai",
        "watermark_position": "bottom_right",
        "watermark_opacity":  0.3,
    },
    "patron_en_franchise": {
        "watermark_text":     "Patron en Franchise",
        "watermark_position": "bottom_right",
        "watermark_opacity":  0.3,
    },
}

TIKTOK_SPECS = {
    "width":         1080,
    "height":        1920,
    "fps":           30,
    "codec":         "libx264",
    "audio_codec":   "aac",
    "bitrate":       "8000k",
    "audio_bitrate": "192k",
    "preset":        "medium",
    "crf":           23,
}


# ──────────────────────────────────────────────
# UTILITAIRES
# ──────────────────────────────────────────────

def check_dependencies() -> bool:
    ok = True
    for tool in ["ffmpeg", "ffprobe"]:
        try:
            result = subprocess.run([tool, "-version"], capture_output=True, text=True)
            version = result.stdout.split("\n")[0]
            print(f"    {tool} : {version[:60]}")
        except FileNotFoundError:
            print(f"    {tool} non trouvé — sudo apt install ffmpeg")
            ok = False
    return ok


def get_duration(path: str) -> float:
    """Retourne la durée d'un fichier audio/vidéo en secondes"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 5.0


def get_file_size_mb(path: str) -> float:
    return round(os.path.getsize(path) / 1_000_000, 1)


# ──────────────────────────────────────────────
# ÉTAPES D'ASSEMBLAGE
# ──────────────────────────────────────────────

def step_resize(input_path: str, output_path: str):
    """Resize + crop un clip en 1080x1920 avec transitions douces"""
    w = TIKTOK_SPECS["width"]
    h = TIKTOK_SPECS["height"]
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},"
            f"fps={TIKTOK_SPECS['fps']}"
        ),
        "-c:v", TIKTOK_SPECS["codec"],
        "-preset", TIKTOK_SPECS["preset"],
        "-crf", str(TIKTOK_SPECS["crf"]),
        "-r", str(TIKTOK_SPECS["fps"]),
        "-pix_fmt", "yuv420p",
        "-an",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception(f"Resize échoué : {result.stderr.decode()[:200]}")


def step_concat(clip_paths: list, output_path: str):
    """Concatène les clips dans l'ordre avec re-encodage pour fluidité"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    list_file = TEMP_DIR / "concat_list.txt"
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", TIKTOK_SPECS["codec"],
        "-preset", TIKTOK_SPECS["preset"],
        "-crf", str(TIKTOK_SPECS["crf"]),
        "-r", str(TIKTOK_SPECS["fps"]),
        "-pix_fmt", "yuv420p",
        "-an",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception(f"Concat échoué : {result.stderr.decode()[:200]}")


def step_loop_to_duration(
    video_path: str,
    target_duration: float,
    output_path: str
):
    """
    Boucle la vidéo pour atteindre la durée cible.
    Évite la dernière frame figée quand l'audio est plus long que la vidéo.
    """
    video_dur = get_duration(video_path)

    if video_dur >= target_duration:
        shutil.copy2(video_path, output_path)
        return output_path

    # Calcule le nombre de répétitions nécessaires
    loops     = int(target_duration / video_dur) + 2
    list_file = str(TEMP_DIR / "loop_list.txt")

    with open(list_file, "w") as f:
        for _ in range(loops):
            f.write(f"file '{os.path.abspath(video_path)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-t", str(target_duration + 0.5),  # +0.5s de marge
        "-c:v", TIKTOK_SPECS["codec"],
        "-preset", TIKTOK_SPECS["preset"],
        "-crf", str(TIKTOK_SPECS["crf"]),
        "-r", str(TIKTOK_SPECS["fps"]),
        "-pix_fmt", "yuv420p",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception(f"Loop échoué : {result.stderr.decode()[:200]}")

    new_dur = get_duration(output_path)
    print(f"    Vidéo bouclée : {video_dur:.1f}s → {new_dur:.1f}s")
    return output_path


def step_add_audio(
    video_path: str,
    audio_path: str,
    output_path: str
) -> float:
    """
    Synchronise la voix off sur la vidéo.
    Durée finale = durée de l'audio.
    """
    audio_dur = get_duration(audio_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", TIKTOK_SPECS["codec"],
        "-preset", TIKTOK_SPECS["preset"],
        "-crf", str(TIKTOK_SPECS["crf"]),
        "-r", str(TIKTOK_SPECS["fps"]),
        "-pix_fmt", "yuv420p",
        "-c:a", TIKTOK_SPECS["audio_codec"],
        "-b:a", TIKTOK_SPECS["audio_bitrate"],
        "-t", str(audio_dur),
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception(f"Audio sync échoué : {result.stderr.decode()[:200]}")

    return audio_dur


def step_watermark(
    video_path: str,
    output_path: str,
    account: str
):
    """Ajoute un watermark texte discret par compte"""
    config   = ACCOUNT_CONFIG.get(account, ACCOUNT_CONFIG["genalternance"])
    text     = config["watermark_text"].replace("'", "\\'")
    opacity  = config["watermark_opacity"]
    pos_map  = {
        "bottom_right":  "x=w-tw-30:y=h-th-80",
        "bottom_center": "x=(w-tw)/2:y=h-th-80",
        "bottom_left":   "x=30:y=h-th-80",
    }
    position = pos_map.get(config["watermark_position"], pos_map["bottom_right"])

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", (
            f"drawtext=text='{text}':"
            f"fontcolor=white@{opacity}:"
            f"fontsize=28:"
            f"{position}:"
            f"shadowcolor=black@0.3:"
            f"shadowx=1:shadowy=1"
        ),
        "-c:a", "copy",
        "-c:v", TIKTOK_SPECS["codec"],
        "-preset", TIKTOK_SPECS["preset"],
        "-crf", str(TIKTOK_SPECS["crf"]),
        "-pix_fmt", "yuv420p",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception(f"Watermark échoué : {result.stderr.decode()[:200]}")


def step_inject_metadata(
    video_path: str,
    account: str,
    script_hash: str
) -> str:
    """
    Injecte des métadonnées EXIF uniques.
    Anti-perceptual hashing TikTok — chaque vidéo est unique.
    """
    unique_id  = hashlib.md5(
        f"{account}{script_hash}{datetime.now().isoformat()}{random.random()}".encode()
    ).hexdigest()[:12]
    created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    temp_path  = video_path.replace(".mp4", f"_tmp.mp4")

    base_bitrate  = int(TIKTOK_SPECS["bitrate"].replace("k", ""))
    bitrate_var   = random.randint(-300, 300)
    final_bitrate = base_bitrate + bitrate_var

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-metadata", f"title=JVNLab_{account}_{unique_id}",
        "-metadata", f"creation_time={created_at}",
        "-metadata", f"comment=JVN-{unique_id}",
        "-c:v", TIKTOK_SPECS["codec"],
        "-b:v", f"{final_bitrate}k",
        "-preset", TIKTOK_SPECS["preset"],
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        temp_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise Exception(f"Metadata échoué : {result.stderr.decode()[:200]}")

    os.replace(temp_path, video_path)
    return unique_id


# ──────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ──────────────────────────────────────────────

def assemble_video(
    clips: list,
    audio_path: str,
    account: str,
    script_text: str = "",
    video_id: int = None,
) -> dict:
    """
    Assemble une vidéo TikTok complète depuis les clips et l'audio.

    Args:
        clips       : Liste de chemins MP4 dans l'ordre (hook, body_1, body_2, cta)
        audio_path  : Chemin vers le MP3 (voix off ElevenLabs)
        account     : Slug du compte
        script_text : Texte du script (pour hash d'unicité)
        video_id    : ID en base de données

    Returns:
        dict avec chemin final et métadonnées
    """
    start_time  = datetime.now()
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_hash = hashlib.md5(script_text.encode()).hexdigest()[:8]

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    final_name = f"{account}_video{video_id or 'test'}_{timestamp}.mp4"
    final_path = str(OUTPUT_DIR / final_name)

    print(f"\n{'='*55}")
    print(f" ASSEMBLAGE VIDÉO — {account.upper()}")
    print(f"   {len(clips)} clips | Audio : {Path(audio_path).name}")
    print(f"{'='*55}")

    # ── 1. Resize ──
    print(f"\n[1/6] Resize clips en {TIKTOK_SPECS['width']}x{TIKTOK_SPECS['height']}...")
    resized = []
    for i, clip in enumerate(clips):
        if not os.path.exists(clip):
            print(f"     Clip {i+1} manquant : {clip}")
            continue
        out = str(TEMP_DIR / f"r{i}.mp4")
        step_resize(clip, out)
        dur = get_duration(out)
        resized.append(out)
        print(f"    Clip {i+1} resizé ({dur:.1f}s)")

    if not resized:
        raise Exception("Aucun clip valide")

    # ── 2. Concat ──
    print(f"\n[2/6] Concaténation ({len(resized)} clips)...")
    concat_path = str(TEMP_DIR / "concat.mp4")
    step_concat(resized, concat_path)
    total_dur = get_duration(concat_path)
    print(f"    Timeline vidéo : {total_dur:.1f}s")

    # ── 3. Boucle si vidéo trop courte ──
    audio_dur = get_duration(audio_path)
    if total_dur < audio_dur:
        print(f"\n[3/6] Boucle vidéo ({total_dur:.1f}s < audio {audio_dur:.1f}s)...")
        looped_path = str(TEMP_DIR / "looped.mp4")
        step_loop_to_duration(concat_path, audio_dur, looped_path)
        concat_path = looped_path
    else:
        print(f"\n[3/6] Pas de boucle nécessaire ({total_dur:.1f}s ≥ {audio_dur:.1f}s) ✅")

    # ── 4. Audio ──
    print(f"\n[4/6] Synchronisation voix off ({audio_dur:.1f}s)...")
    audio_out = str(TEMP_DIR / "with_audio.mp4")
    final_audio_dur = step_add_audio(concat_path, audio_path, audio_out)
    print(f"    Audio synchronisé — durée finale : {final_audio_dur:.1f}s")

    # ── 5. Watermark ──
    wm_config = ACCOUNT_CONFIG.get(account, {})
    print(f"\n[5/6] Watermark '{wm_config.get('watermark_text', account)}'...")
    wm_path = str(TEMP_DIR / "with_wm.mp4")
    step_watermark(audio_out, wm_path, account)
    print(f"    Watermark ajouté")

    # ── 6. Métadonnées ──
    print(f"\n[6/6] Métadonnées EXIF uniques...")
    shutil.copy2(wm_path, final_path)
    unique_id = step_inject_metadata(final_path, account, script_hash)
    print(f"    ID unique : {unique_id}")

    # ── Nettoyage ──
    for f in TEMP_DIR.glob("*.mp4"):
        f.unlink()
    for f in TEMP_DIR.glob("*.txt"):
        f.unlink()

    # ── Résultat ──
    assembly_s   = (datetime.now() - start_time).seconds
    file_size_mb = get_file_size_mb(final_path)
    video_dur    = get_duration(final_path)

    result = {
        "account":          account,
        "video_id":         video_id,
        "final_path":       final_path,
        "file_size_mb":     file_size_mb,
        "video_duration_s": round(video_dur, 1),
        "audio_duration_s": round(final_audio_dur, 1),
        "clips_used":       len(resized),
        "unique_id":        unique_id,
        "assembly_time_s":  assembly_s,
        "assembled_at":     datetime.now().isoformat(),
        "status":           "assembled",
        "ready_for_qa":     True,
    }

    print(f"\n{'='*55}")
    print(f" VIDÉO ASSEMBLÉE !")
    print(f"   Fichier  : {final_path}")
    print(f"   Taille   : {file_size_mb} MB")
    print(f"   Durée    : {video_dur:.1f}s")
    print(f"   Assemblage : {assembly_s}s")
    print(f"{'='*55}")

    return result


# ──────────────────────────────────────────────
# TEST AUTOMATIQUE
# ──────────────────────────────────────────────

def run_test(account: str = "genalternance"):
    """Test avec les fichiers les plus récents dans output/"""
    print(f"\n TEST ASSEMBLAGE — {account}")
    print("=" * 55)

    print("\n Vérification dépendances...")
    if not check_dependencies():
        return

    video_dir = Path("output/video")
    audio_dir = Path("output/audio")

    # Récupère les clips triés par type
    all_clips = sorted(video_dir.glob(f"{account}_*.mp4")) if video_dir.exists() else []
    audios    = sorted(audio_dir.glob(f"{account}_*.mp3")) if audio_dir.exists() else []

    if not all_clips:
        print(f"\n Aucun clip MP4 pour '{account}' dans output/video/")
        return

    if not audios:
        print(f"\n Aucun audio MP3 pour '{account}' dans output/audio/")
        return

    # Prend les 4 derniers clips dans l'ordre
    clips_to_use = [str(c) for c in all_clips[-4:]]

    print(f"\n Fichiers sélectionnés :")
    for c in clips_to_use:
        dur = get_duration(c)
        print(f"    {Path(c).name} ({dur:.1f}s)")
    print(f"     {audios[-1].name} ({get_duration(str(audios[-1])):.1f}s)")

    result = assemble_video(
        clips=clips_to_use,
        audio_path=str(audios[-1]),
        account=account,
        script_text="test_assembly_jvnlab",
    )

    print(f"\n Pour visionner :")
    print(f"   cd output/final && python3 -m http.server 8080")
    print(f"   → http://212.47.231.204:8080/{Path(result['final_path']).name}")

    return result


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--check" in args:
        print("\n VÉRIFICATION DÉPENDANCES")
        check_dependencies()

    elif "--test" in args:
        idx     = args.index("--test")
        account = args[idx + 1] if len(args) > idx + 1 else "genalternance"
        run_test(account)

    elif "--assemble" in args:
        idx      = args.index("--assemble")
        cfg_path = args[idx + 1]
        with open(cfg_path) as f:
            config = json.load(f)
        result = assemble_video(
            clips=config["clips"],
            audio_path=config["audio"],
            account=config["account"],
            script_text=config.get("script_text", ""),
            video_id=config.get("video_id"),
        )
        print(json.dumps(result, indent=2))

    else:
        print("Usage :")
        print("  python3 moviepy_builder.py --check")
        print("  python3 moviepy_builder.py --test genalternance")
        print("  python3 moviepy_builder.py --assemble config.json")
        print(f"\nComptes : {list(ACCOUNT_CONFIG.keys())}")