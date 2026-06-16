"""
Module Idéation — Claude API
JVN Lab TikTok Automation
Fichier : src/ideation/claude_client.py
"""

import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ──────────────────────────────────────────────
# PROMPTS SYSTÈME PAR COMPTE
# ──────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "genalternance": """
Tu es le créateur de contenu TikTok du compte GenAlternance.
Niche : alternance, formation professionnelle, Rush School.
Audience : 16-25 ans, étudiants cherchant une alternance ou une formation qualifiante.
Ton : dynamique, bienveillant, encourageant. Vocabulaire jeune mais professionnel.
Persona : un grand frère bienveillant qui partage ses vraies astuces alternance.
Format : 30-60 secondes, hook percutant dans la 1ère seconde.
Structure : hook (max 10 mots) + corps (3-5 phrases) + CTA engagement.
Tu génères des scripts TikTok viraux en français.
""",

    "lea_beauty": """
Tu es le créateur de contenu TikTok du compte Léa Beauty.
Niche : beauté, skincare, cosmétiques accessibles.
Audience : femmes 18-35 ans, passionnées de beauté, budget conscient.
Ton : chaleureux, expert mais accessible, complice. Comme une amie qui s'y connaît.
Persona : Léa — avatar IA pastel, experte beauté bienveillante.
Format : 30-60 secondes, hook visuel fort + conseil actionnable.
Règle : jamais de promesses médicales, jamais de prix, disclosure IA dans la bio.
Structure : hook (max 10 mots) + conseil concret + CTA doux.
Tu génères des scripts TikTok viraux en français.
""",

    "ia_facile": """
Tu es le créateur de contenu TikTok du compte L'IA Facile.
Niche : intelligence artificielle accessible, outils IA du quotidien.
Audience : 25-55 ans, non-initiés à l'IA — enseignants, artisans, parents, commerçants.
Ton : patient, chaleureux, jamais condescendant. Comme quelqu'un qui explique au café.
Fil rouge : rendre l'IA utile et accessible au quotidien, sans jargon.
Format : 30 secondes maximum — une seule idée, un seul outil, un seul usage.
Règle absolue : zéro jargon technique (pas de LLM, token, neural network, fine-tuning).
Structure : hook simple (max 10 mots) + explication en 2-3 phrases + invitation à essayer.
Tu génères des scripts TikTok viraux en français.
""",

    "maison_neroli": """
Tu es le créateur de contenu TikTok du compte Maison Néroli.
Niche : art de vivre, déco intérieure, parfum, matières nobles, esthétique du quotidien.
Audience : femmes et hommes 28-45 ans, sensibles au beau, cherchant une élégance discrète.
Ton : poétique, sensoriel, contemplatif. Jamais commercial — on inspire, on ne vend pas.
Format : 20-45 secondes — micro-parenthèse esthétique, moment suspendu, rythme lent.
Règle absolue : jamais de prix, jamais de marques en promotion, jamais de rythme rapide.
Structure : évocation sensorielle (hook) + description de la matière/lumière/odeur + invitation douce.
Tu génères des scripts TikTok poétiques et sensuels en français.
""",

    "etrange_mais_vrai": """
Tu es le créateur de contenu TikTok du compte Étrange mais Vrai.
Niche : faits étranges réels, mystères, histoires vraies, storytime tendu.
Audience : 18-35 ans, fans de podcasts, de Reddit, de faits improbables.
Ton : narratif, tendu, factuel. Comme un bon conteur qui ne ment jamais.
Fil rouge : "C'est bizarre, mais c'est réel" — le pacte avec le spectateur.
Format : 45-60 secondes — storytime avec cliffhanger et source citée.
Règle absolue : chaque fait doit être réel et vérifiable — jamais de rumeur.
Structure : hook choc + mise en contexte + fait central + chute/cliffhanger + source.
Tu génères des scripts TikTok narratifs et accrocheurs en français.
""",

    "patron_en_franchise": """
Tu es le créateur de contenu TikTok du compte Patron en Franchise, propulsé par OpenFranchise.
Niche : franchise, entrepreneuriat, quitter le salariat, devenir son propre patron.
Audience : 28-45 ans, salariés frustrés avec apport 30-150k€, cherchant l'indépendance.
Ton : ambitieux, concret, factuel. On inspire ET on informe avec des chiffres réels.
Objectif business : drainer des candidats qualifiés vers la plateforme OpenFranchise.
Format : 40-60 secondes — aspiration + décryptage chiffré + CTA vers OpenFranchise.
CTA systématique : "Découvre les franchises qui recrutent sur OpenFranchise — lien en bio".
Règle : toujours ancrer dans des chiffres réels (coûts, réseaux, rentabilité).
Structure : hook aspiration/chiffre + décryptage concret + preuve d'accessibilité + CTA OpenFranchise.
Tu génères des scripts TikTok viraux en français.
""",
}


# ──────────────────────────────────────────────
# PROMPT UTILISATEUR
# ──────────────────────────────────────────────

def build_user_prompt(trend: str, account: str) -> str:
    return f"""
Tendance TikTok détectée : "{trend}"

Génère exactement 3 idées de scripts TikTok différentes pour cette tendance.
Chaque script doit être adapté au compte {account} selon son prompt système.

Réponds UNIQUEMENT en JSON valide avec ce format exact :
{{
  "scripts": [
    {{
      "id": 1,
      "hook": "La 1ère phrase percutante (max 10 mots, doit accrocher en 1 seconde)",
      "corps": "Le développement du message (3-5 phrases max, conseil ou info clé)",
      "cta": "L'appel à l'action final (ex: Commente, Suis pour la suite, Partage...)",
      "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
      "duree_estimee": "45s",
      "angle": "Description de l'angle éditorial en 1 phrase"
    }},
    {{ "id": 2, "hook": "...", "corps": "...", "cta": "...", "hashtags": [], "duree_estimee": "...", "angle": "..." }},
    {{ "id": 3, "hook": "...", "corps": "...", "cta": "...", "hashtags": [], "duree_estimee": "...", "angle": "..." }}
  ]
}}
"""


# ──────────────────────────────────────────────
# SCORING AUTOMATIQUE
# ──────────────────────────────────────────────

def score_script(script: dict) -> dict:
    """
    Score automatique /10 :
    - Hook      : 4 pts (longueur)
    - Corps     : 3 pts (nombre de phrases)
    - Conformité: 3 pts (CTA + hashtags)
    """
    score   = 0
    details = []

    # Hook (4 pts)
    hook       = script.get("hook", "")
    hook_words = len(hook.split())
    if hook_words <= 8:
        score += 4; details.append(f"Hook excellent ({hook_words} mots) +4")
    elif hook_words <= 10:
        score += 3; details.append(f"Hook bon ({hook_words} mots) +3")
    elif hook_words <= 12:
        score += 2; details.append(f"Hook acceptable ({hook_words} mots) +2")
    else:
        score += 1; details.append(f"Hook trop long ({hook_words} mots) +1")

    # Corps (3 pts)
    corps    = script.get("corps", "")
    phrases  = [p.strip() for p in corps.split(".") if p.strip()]
    nb       = len(phrases)
    if 3 <= nb <= 5:
        score += 3; details.append(f"Corps idéal ({nb} phrases) +3")
    elif nb in [2, 6]:
        score += 2; details.append(f"Corps acceptable ({nb} phrases) +2")
    else:
        score += 1; details.append(f"Corps à retravailler ({nb} phrases) +1")

    # Conformité (3 pts)
    has_cta  = bool(script.get("cta", "").strip())
    hashtags = script.get("hashtags", [])
    if has_cta and len(hashtags) >= 3:
        score += 3; details.append("CTA + hashtags OK +3")
    elif has_cta or len(hashtags) >= 2:
        score += 2; details.append("CTA ou hashtags incomplets +2")
    else:
        score += 1; details.append("CTA et hashtags manquants +1")

    return {
        **script,
        "score":         score,
        "score_details": details,
        "approved":      score >= 7,
    }


# ──────────────────────────────────────────────
# GÉNÉRATION DE SCRIPTS
# ──────────────────────────────────────────────

def generate_scripts(
    trend: str,
    account: str,
    model: str = "claude-haiku-4-5-20251001"
) -> dict:
    """
    Génère 3 scripts TikTok pour une tendance et un compte donnés.

    Args:
        trend   : Tendance détectée (ex: "Les outils IA gratuits de 2026")
        account : Slug du compte (ex: "ia_facile", "patron_en_franchise")
        model   : Modèle Claude (Haiku par défaut)

    Returns:
        dict avec scripts scorés et meilleur script sélectionné
    """
    if account not in SYSTEM_PROMPTS:
        raise ValueError(
            f"Compte inconnu : '{account}'. "
            f"Disponibles : {list(SYSTEM_PROMPTS.keys())}"
        )

    print(f"\n Génération scripts — Compte: {account} | Tendance: {trend}")
    print(f"   Modèle : {model}")

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPTS[account].strip(),
        messages=[
            {"role": "user", "content": build_user_prompt(trend, account)}
        ]
    )

    # Parse JSON
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data    = json.loads(raw)
    scripts = data.get("scripts", [])

    # Scoring
    scored = [score_script(s) for s in scripts]
    best   = max(scored, key=lambda x: x["score"])

    result = {
        "account": account,
        "trend":   trend,
        "model":   model,
        "usage": {
            "input_tokens":      response.usage.input_tokens,
            "output_tokens":     response.usage.output_tokens,
            "cost_eur_estimate": round(
                (response.usage.input_tokens * 0.00025 +
                 response.usage.output_tokens * 0.00125) / 1000 * 0.93,
                5
            )
        },
        "scripts":        scored,
        "best_script":    best,
        "approved_count": sum(1 for s in scored if s["approved"]),
    }

    return result


# ──────────────────────────────────────────────
# TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Teste le compte passé en argument ou genalternance par défaut
    account = sys.argv[1] if len(sys.argv) > 1 else "genalternance"

    # Tendances de test par compte
    test_trends = {
        "genalternance":       "Les entreprises rejettent les CV sans expérience même pour les alternances",
        "lea_beauty":          "La routine skincare minimaliste qui change tout en 30 jours",
        "ia_facile":           "ChatGPT peut maintenant lire et analyser tes photos",
        "maison_neroli":       "La lumière de fin d'après-midi dans un appartement",
        "etrange_mais_vrai":   "En 1962 une ville entière s'est mise à rire sans pouvoir s'arrêter",
        "patron_en_franchise": "90% des franchises survivent après 5 ans contre 50% des créations classiques",
    }

    trend = test_trends.get(account, "Les tendances de 2026")

    print("=" * 60)
    print(f"TEST IDÉATION — {account}")
    print(f"Tendance : {trend}")
    print("=" * 60)

    result = generate_scripts(trend=trend, account=account)

    print(f"\n {len(result['scripts'])} scripts générés")
    print(f" Coût : {result['usage']['cost_eur_estimate']} €")
    print(f" Scripts approuvés : {result['approved_count']}/3")
    print(f"\n Meilleur script (score {result['best_script']['score']}/10) :")
    print(f"   Hook  : {result['best_script']['hook']}")
    print(f"   Corps : {result['best_script']['corps'][:100]}...")
    print(f"   CTA   : {result['best_script']['cta']}")
    print(f"   Score : {result['best_script']['score']}/10 — {result['best_script']['score_details']}")

    # Sauvegarde
    output_file = f"test_ideation_{account}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n Résultat sauvegardé dans {output_file}")