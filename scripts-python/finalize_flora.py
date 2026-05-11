"""
finalize_flora.py
=================
Deux corrections finales :

1. Floraison NULL → 2/11 uniquement pour les plantes à fleurs
   (exclut fougères, conifères, lycopodes, prêles)

2. Noms français manquants → API Wikipedia (recherche de la page fr
   correspondant au nom latin, puis extraction du titre français)

Usage:
    python finalize_flora.py enrichi_final_v4.csv enrichi_final_v5.csv

Requirements:
    pip install pandas requests tqdm
"""

import json
import time
import logging
import argparse
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Classes sans floraison réelle → ne pas remplir avec 2/11
NON_FLOWERING_CLASSES = {
    "Polypodiopsida",   # fougères
    "Pinopsida",        # conifères
    "Lycopodiopsida",   # lycopodes
    "Gnetopsida",       # éphèdres
    "Equisetopsida",    # prêles
}

WIKIPEDIA_API = "https://fr.wikipedia.org/w/api.php"
API_DELAY     = 0.2
MAX_RETRIES   = 3


# ── Cache disque ───────────────────────────────────────────────────────────────

def load_cache(cache_path: Path) -> dict:
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        log.info(f"Cache Wikipedia chargé : {len(cache):,} entrées ({cache_path})")
        return cache
    return {}


def save_cache(cache: dict, cache_path: Path) -> None:
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ── 1. Remplissage floraison ───────────────────────────────────────────────────

def fill_flowering(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remplit floraison_debut=2 et floraison_fin=11 uniquement pour
    les plantes à fleurs (Magnoliopsida, Liliopsida, etc.)
    avec floraison encore NULL.
    """
    mask_null     = df["floraison_debut"].isna()
    mask_flowering = ~df["Class"].isin(NON_FLOWERING_CLASSES)
    mask_fill     = mask_null & mask_flowering

    n_fill    = mask_fill.sum()
    n_skipped = (mask_null & ~mask_flowering).sum()

    df.loc[mask_fill, "floraison_debut"] = 2
    df.loc[mask_fill, "floraison_fin"]   = 11

    df["floraison_debut"] = pd.array(df["floraison_debut"], dtype="Int64")
    df["floraison_fin"]   = pd.array(df["floraison_fin"],   dtype="Int64")

    log.info(f"Floraison remplie (2→11)       : {n_fill:,} espèces")
    log.info(f"Floraison laissée NULL (non-fl): {n_skipped:,} espèces")
    return df


# ── 2. Noms français via Wikipedia ────────────────────────────────────────────

def get_french_name_wikipedia(species_name: str) -> str | None:
    """
    Stratégie en deux étapes :

    Étape 1 : cherche la page Wikipedia française correspondant au nom latin.
    On utilise l'API de recherche avec le nom latin — Wikipedia redirige
    souvent automatiquement vers la page française si elle existe.

    Étape 2 : si la page trouvée a un titre différent du nom latin,
    c'est le nom français. Si le titre = nom latin, on extrait le premier
    nom commun depuis les catégories ou le premier paragraphe.
    """

    # Étape 1 : recherche directe du nom latin sur Wikipedia FR
    params_search = {
        "action":   "query",
        "titles":   species_name,
        "prop":     "pageprops|extracts",
        "exintro":  True,
        "exsentences": 1,
        "redirects": True,
        "format":   "json",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(WIKIPEDIA_API, params=params_search, timeout=10)
            if r.status_code == 200:
                data  = r.json()
                pages = data.get("query", {}).get("pages", {})

                for page_id, page in pages.items():
                    if page_id == "-1":
                        # Page introuvable → essayer via la recherche fulltext
                        return search_wikipedia_fulltext(species_name)

                    title = page.get("title", "")

                    # Si le titre est différent du nom latin → c'est le nom FR
                    if title.lower() != species_name.lower():
                        # Exclure les titres qui contiennent encore le nom latin
                        # (ex: "Bellis perennis — Pâquerette" → prendre la partie après)
                        if "—" in title:
                            return title.split("—")[-1].strip()
                        if "(" in title:
                            return title.split("(")[0].strip()
                        return title.strip()

                    # Titre = nom latin → extraire depuis le résumé
                    extract = page.get("extract", "")
                    if extract:
                        name = extract_name_from_extract(extract, species_name)
                        if name:
                            return name

                return None

            time.sleep(2 * attempt)

        except requests.RequestException as ex:
            log.warning(f"Wikipedia erreur pour '{species_name}', tentative {attempt} : {ex}")
            time.sleep(3 * attempt)

    return None


def search_wikipedia_fulltext(species_name: str) -> str | None:
    """Recherche fulltext Wikipedia FR quand la page directe n'existe pas."""
    params = {
        "action":   "query",
        "list":     "search",
        "srsearch": species_name,
        "srlimit":  1,
        "format":   "json",
    }
    try:
        r = requests.get(WIKIPEDIA_API, params=params, timeout=10)
        if r.status_code == 200:
            results = r.json().get("query", {}).get("search", [])
            if results:
                title = results[0].get("title", "")
                if title.lower() != species_name.lower():
                    if "(" in title:
                        return title.split("(")[0].strip()
                    return title.strip()
    except requests.RequestException:
        pass
    return None


def extract_name_from_extract(extract: str, species_name: str) -> str | None:
    """
    Tente d'extraire un nom commun français depuis le premier extrait Wikipedia.
    Ex: "La Pâquerette vivace (Bellis perennis) est une..."
        → "Pâquerette vivace"
    """
    # Pattern : "La/Le/Les NomFrançais (NomLatin)"
    import re
    pattern = rf'(?:La|Le|Les|L\'|Un|Une)\s+([A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ][^(,\n]{{3,40}})\s*\({re.escape(species_name)}'
    match = re.search(pattern, extract, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Pattern alternatif : "(NomLatin), appelé NomFrançais"
    pattern2 = rf'\({re.escape(species_name)}\)[^,]{{0,20}},?\s+(?:appelé|dit|nommé|connu sous le nom de)\s+([^\.,\n]{{3,50}})'
    match2 = re.search(pattern2, extract, re.IGNORECASE)
    if match2:
        return match2.group(1).strip()

    return None


# ── Pipeline noms français ─────────────────────────────────────────────────────

def fill_french_names(df: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    cache = load_cache(cache_path)

    missing_mask    = df["nom_francais"].isna()
    missing_species = df[missing_mask]["Species"].unique().tolist()
    todo            = [s for s in missing_species if s not in cache]

    log.info(f"Noms français manquants : {len(missing_species):,}  |  Cache : {len(missing_species)-len(todo):,}  |  Restant : {len(todo):,}")

    BATCH = 50
    n_batches = (len(todo) + BATCH - 1) // BATCH if todo else 0

    with tqdm(total=len(todo), desc="Noms FR Wikipedia", unit="sp") as pbar:
        for i in range(n_batches):
            batch = todo[i * BATCH : (i + 1) * BATCH]
            for species in batch:
                try:
                    name = get_french_name_wikipedia(species)
                    cache[species] = name
                    time.sleep(API_DELAY)
                except Exception as ex:
                    log.error(f"Erreur pour '{species}' : {ex}")
                    cache[species] = None
                pbar.update(1)

            save_cache(cache, cache_path)
            n_found = sum(1 for s in batch if cache.get(s))
            log.info(f"Batch {i+1}/{n_batches} — {n_found}/{len(batch)} noms trouvés ✓")

    # Appliquer uniquement sur les NULL
    filled = 0
    for idx, row in df[missing_mask].iterrows():
        name = cache.get(row["Species"])
        if name:
            df.at[idx, "nom_francais"] = name
            filled += 1

    log.info(f"Noms français comblés    : {filled:,}")
    log.info(f"Encore sans nom français : {missing_mask.sum() - filled:,}")
    return df


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Finalisation flora — floraison + noms FR")
    parser.add_argument("input",  help="CSV enrichi_final_v4.csv")
    parser.add_argument("output", help="CSV de sortie")
    parser.add_argument(
        "--cache", type=str, default=None,
        help="Cache JSON Wikipedia (défaut: <o>.wiki_cache.json)"
    )
    args = parser.parse_args()

    out_path   = Path(args.output)
    cache_path = Path(args.cache) if args.cache else out_path.with_suffix(".wiki_cache.json")

    df = pd.read_csv(args.input, encoding="utf-8")
    log.info(f"{len(df):,} espèces chargées")

    # ── Étape 1 : floraison ──
    log.info("── Étape 1 : remplissage floraison ──")
    df = fill_flowering(df)

    # ── Étape 2 : noms français ──
    log.info("── Étape 2 : noms français Wikipedia ──")
    df = fill_french_names(df, cache_path)

    # ── Stats finales ──
    total    = len(df)
    n_fr     = df["nom_francais"].notna().sum()
    n_debut  = df["floraison_debut"].notna().sum()
    n_images = df["image_url"].notna().sum()

    log.info(f"\n{'='*40}")
    log.info(f"Noms français  : {n_fr:,} / {total:,} ({n_fr/total*100:.1f}%)")
    log.info(f"Floraison      : {n_debut:,} / {total:,} ({n_debut/total*100:.1f}%)")
    log.info(f"Images         : {n_images:,} / {total:,} ({n_images/total*100:.1f}%)")
    log.info(f"{'='*40}")

    df.to_csv(out_path, index=False, encoding="utf-8")
    log.info(f"✅ Fichier exporté → {out_path}")
    log.info(f"💾 Cache Wikipedia → {cache_path}")

    print("\n── Aperçu noms récupérés ──")
    recovered = df[df["nom_francais"].notna() & df["Species"].isin(
        ["Bistorta officinalis", "Salix alba", "Clinopodium alpinum",
         "Symphoricarpos albus", "Myricaria germanica", "Cerastium holosteoides"]
    )]
    print(recovered[["Species", "nom_francais", "floraison_debut", "floraison_fin"]].to_string(index=False))


if __name__ == "__main__":
    main()
