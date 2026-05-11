"""
fix_floraison_inat.py
=====================
Corrige les floraisons suspectes (février→novembre) en interrogeant
l'API iNaturalist qui fournit la distribution mensuelle des observations
pour chaque espèce en Suisse.

La floraison est déduite en cherchant les mois avec un pic d'observations
significatif (au-dessus d'un seuil de 10% du max).

Usage:
    python fix_floraison_inat.py enrichi_final_floraison_img_v2.csv output.csv
    python fix_floraison_inat.py enrichi_final_floraison_img_v2.csv output.csv --batch-size 30

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

# ── Configuration ──────────────────────────────────────────────────────────────

INAT_API       = "https://api.inaturalist.org/v1/observations/histogram"
INAT_TAXON_API = "https://api.inaturalist.org/v1/taxa"
API_DELAY      = 0.5
MAX_RETRIES    = 3
BATCH_SIZE     = 50

# Seuil : un mois est considéré "en floraison" s'il représente
# au moins X% du mois le plus observé
PEAK_THRESHOLD = 0.15  # 15%

# Place ID Suisse sur iNaturalist
SWITZERLAND_PLACE_ID = 6883

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "FloraResearchBot/1.0 (scientific research)",
    "Accept": "application/json",
}


# ── Cache disque ───────────────────────────────────────────────────────────────

def load_cache(cache_path: Path) -> dict:
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        log.info(f"Cache chargé : {len(cache):,} espèces ({cache_path})")
        return cache
    return {}


def save_cache(cache: dict, cache_path: Path) -> None:
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ── API iNaturalist ────────────────────────────────────────────────────────────

def get_taxon_id(species_name: str) -> int | None:
    """Récupère l'ID iNaturalist d'une espèce depuis son nom latin."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                INAT_TAXON_API,
                params={"q": species_name, "rank": "species", "per_page": 1},
                headers=HEADERS,
                timeout=10,
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    return results[0]["id"]
                return None
            elif r.status_code == 429:
                time.sleep(10 * attempt)
            else:
                time.sleep(2 * attempt)
        except requests.RequestException as ex:
            log.warning(f"Taxon ID erreur pour '{species_name}', tentative {attempt} : {ex}")
            time.sleep(3 * attempt)
    return None


def get_monthly_histogram(taxon_id: int) -> dict | None:
    """
    Récupère l'histogramme mensuel des observations en Suisse.
    Retourne un dict {mois: nb_observations} ou None.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                INAT_API,
                params={
                    "taxon_id":   taxon_id,
                    "place_id":   SWITZERLAND_PLACE_ID,
                    "date_field": "observed",
                    "interval":   "month_of_year",
                    "quality_grade": "research",  # observations validées uniquement
                },
                headers=HEADERS,
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                # La réponse est un dict {"results": {"month_of_year": {"1": N, "2": N, ...}}}
                histogram = data.get("results", {}).get("month_of_year", {})
                if histogram:
                    return {int(k): int(v) for k, v in histogram.items() if int(v) > 0}
                return None
            elif r.status_code == 429:
                time.sleep(10 * attempt)
            else:
                time.sleep(2 * attempt)
        except requests.RequestException as ex:
            log.warning(f"Histogram erreur pour taxon {taxon_id}, tentative {attempt} : {ex}")
            time.sleep(3 * attempt)
    return None


def histogram_to_flowering(histogram: dict) -> tuple[int | None, int | None]:
    """
    Convertit un histogramme mensuel en période de floraison (début, fin).

    Stratégie :
    1. Trouver le pic maximum
    2. Garder tous les mois >= PEAK_THRESHOLD * max
    3. Le début = mois le plus précoce significatif
       La fin   = mois le plus tardif significatif

    Gère les espèces à floraison chevauchant janvier (ex: nov→jan→fév)
    en détectant les pics en fin/début d'année.
    """
    if not histogram:
        return None, None

    max_obs = max(histogram.values())
    if max_obs == 0:
        return None, None

    significant = sorted([m for m, v in histogram.items() if v >= PEAK_THRESHOLD * max_obs])

    if not significant:
        return None, None

    # Cas simple : pas de chevauchement sur janvier
    return significant[0], significant[-1]


# ── Pipeline principal ─────────────────────────────────────────────────────────

def fix_flowering(df: pd.DataFrame, cache_path: Path, batch_size: int) -> pd.DataFrame:
    cache = load_cache(cache_path)

    # Identifier les espèces suspectes (floraison 2→11)
    suspect_mask = (df["floraison_debut"] == 2) & (df["floraison_fin"] == 11)
    suspect_species = df[suspect_mask]["Species"].unique().tolist()

    todo = [s for s in suspect_species if s not in cache]
    log.info(f"Espèces suspectes : {len(suspect_species):,}  |  Déjà en cache : {len(suspect_species)-len(todo):,}  |  Restant : {len(todo):,}")

    n_batches = (len(todo) + batch_size - 1) // batch_size if todo else 0

    with tqdm(total=len(todo), desc="iNaturalist floraison", unit="sp") as pbar:
        for i in range(n_batches):
            batch = todo[i * batch_size : (i + 1) * batch_size]

            for species in batch:
                try:
                    taxon_id = get_taxon_id(species)
                    time.sleep(API_DELAY)

                    if taxon_id:
                        histogram = get_monthly_histogram(taxon_id)
                        time.sleep(API_DELAY)
                        debut, fin = histogram_to_flowering(histogram) if histogram else (None, None)
                    else:
                        debut, fin = None, None

                    cache[species] = {"floraison_debut": debut, "floraison_fin": fin}

                except Exception as ex:
                    log.error(f"Erreur inattendue pour '{species}' : {ex}")
                    cache[species] = {"floraison_debut": None, "floraison_fin": None}

                pbar.update(1)

            save_cache(cache, cache_path)
            log.info(f"Batch {i+1}/{n_batches} sauvegardé ✓")

    # Appliquer les corrections
    n_fixed_debut = 0
    n_fixed_fin   = 0
    n_not_found   = 0

    for idx, row in df[suspect_mask].iterrows():
        species = row["Species"]
        result  = cache.get(species, {})
        new_debut = result.get("floraison_debut")
        new_fin   = result.get("floraison_fin")

        if new_debut is not None:
            df.at[idx, "floraison_debut"] = new_debut
            n_fixed_debut += 1
        if new_fin is not None:
            df.at[idx, "floraison_fin"] = new_fin
            n_fixed_fin += 1
        if new_debut is None and new_fin is None:
            # iNaturalist n'a rien trouvé non plus → mettre NULL
            # (mieux que de garder le biais 2→11)
            df.at[idx, "floraison_debut"] = None
            df.at[idx, "floraison_fin"]   = None
            n_not_found += 1

    log.info(f"Floraisons corrigées : {n_fixed_debut:,}")
    log.info(f"Mis à NULL (iNat sans données) : {n_not_found:,}")

    df["floraison_debut"] = pd.array(df["floraison_debut"], dtype="Int64")
    df["floraison_fin"]   = pd.array(df["floraison_fin"],   dtype="Int64")

    return df


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Correction floraison via iNaturalist")
    parser.add_argument("input",  help="CSV avec floraisons suspectes (enrichi_final_floraison_img_v2.csv)")
    parser.add_argument("output", help="CSV corrigé en sortie")
    parser.add_argument(
        "--batch-size", type=int, default=BATCH_SIZE,
        help=f"Espèces traitées par batch avant sauvegarde (défaut: {BATCH_SIZE})"
    )
    parser.add_argument(
        "--cache", type=str, default=None,
        help="Chemin du cache JSON (défaut: <output>.inat_cache.json)"
    )
    args = parser.parse_args()

    out_path   = Path(args.output)
    cache_path = Path(args.cache) if args.cache else out_path.with_suffix(".inat_cache.json")

    df = pd.read_csv(args.input, encoding="utf-8")
    log.info(f"{len(df):,} espèces chargées")

    df = fix_flowering(df, cache_path, args.batch_size)

    # Stats finales
    total = len(df)
    n_debut  = df["floraison_debut"].notna().sum()
    n_null   = df["floraison_debut"].isna().sum()
    still_suspect = ((df["floraison_debut"] == 2) & (df["floraison_fin"] == 11)).sum()
    log.info(f"floraison_debut renseignée : {n_debut:,} / {total:,}")
    log.info(f"floraison_debut NULL       : {n_null:,} / {total:,}")
    log.info(f"Encore suspectes (2→11)    : {still_suspect:,}")

    df.to_csv(out_path, index=False, encoding="utf-8")
    log.info(f"✅ Fichier exporté → {out_path}")
    log.info(f"💾 Cache conservé  → {cache_path}")

    print("\n── Aperçu espèces corrigées ──")
    corrected = df[df["Species"].isin(["Erigeron annuus", "Picea abies", "Trifolium pratense",
                                        "Gentiana acaulis", "Bellis perennis", "Dactylis glomerata"])]
    print(corrected[["Species", "nom_francais", "floraison_debut", "floraison_fin"]].to_string(index=False))


if __name__ == "__main__":
    main()
