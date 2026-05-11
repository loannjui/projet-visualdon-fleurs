"""
fix_images_inat.py
==================
Comble les images manquantes (image_url = NULL) via l'API iNaturalist.

Usage:
    python fix_images_inat.py enrichi_final_v5.csv enrichi_final_v6.csv

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

INAT_TAXA_API = "https://api.inaturalist.org/v1/taxa"
API_DELAY     = 0.5
MAX_RETRIES   = 3
BATCH_SIZE    = 20  # réduit pour plus de fiabilité

HEADERS = {
    "User-Agent": "FloraResearchBot/1.0",
    "Accept":     "application/json",
}


# ── Test de connexion ──────────────────────────────────────────────────────────

def test_connection() -> bool:
    """Vérifie que l'API iNaturalist est accessible avant de commencer."""
    try:
        r = requests.get(
            INAT_TAXA_API,
            params={"q": "Bellis perennis", "rank": "species", "per_page": 1},
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                photo = results[0].get("default_photo", {})
                url   = photo.get("medium_url") or photo.get("url", "")
                log.info(f"✅ Connexion iNaturalist OK — ex: {url[:60]}...")
                return True
        log.error(f"❌ iNaturalist répond HTTP {r.status_code}")
        return False
    except requests.RequestException as ex:
        log.error(f"❌ Impossible de joindre iNaturalist : {ex}")
        return False


# ── Cache disque ───────────────────────────────────────────────────────────────

def load_cache(cache_path: Path) -> dict:
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        log.info(f"Cache chargé : {len(cache):,} entrées ({cache_path})")
        return cache
    return {}


def save_cache(cache: dict, cache_path: Path) -> None:
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ── API iNaturalist ────────────────────────────────────────────────────────────

def fetch_image_for_species(species_name: str) -> str | None:
    """
    Récupère l'image de référence iNaturalist pour une espèce.
    Fait une requête par espèce pour maximiser la précision du matching.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                INAT_TAXA_API,
                params={
                    "q":        species_name,
                    "rank":     "species",
                    "per_page": 5,  # quelques résultats pour trouver le bon
                },
                headers=HEADERS,
                timeout=15,
            )

            if r.status_code == 200:
                results = r.json().get("results", [])

                # Chercher le taxon dont le nom correspond exactement
                for taxon in results:
                    if taxon.get("name", "").lower() == species_name.lower():
                        photo = taxon.get("default_photo")
                        if photo:
                            url = photo.get("medium_url") or photo.get("url")
                            if url and "/square." in url:
                                url = url.replace("/square.", "/medium.")
                            return url
                        return None  # Taxon trouvé mais pas de photo

                # Aucun match exact → prendre le premier résultat s'il existe
                if results:
                    photo = results[0].get("default_photo")
                    if photo:
                        url = photo.get("medium_url") or photo.get("url")
                        if url and "/square." in url:
                            url = url.replace("/square.", "/medium.")
                        return url

                return None  # Aucun résultat

            elif r.status_code == 429:
                wait = 15 * attempt
                log.warning(f"Rate-limit iNat, attente {wait}s...")
                time.sleep(wait)
            else:
                log.warning(f"HTTP {r.status_code} pour '{species_name}', tentative {attempt}")
                time.sleep(3 * attempt)

        except requests.RequestException as ex:
            log.warning(f"Erreur réseau pour '{species_name}', tentative {attempt} : {ex}")
            time.sleep(5 * attempt)

    return None


# ── Pipeline principal ─────────────────────────────────────────────────────────

def fix_images(df: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    cache = load_cache(cache_path)

    missing_mask    = df["image_url"].isna()
    missing_species = df[missing_mask]["Species"].unique().tolist()
    todo            = [s for s in missing_species if s not in cache]

    log.info(f"Images manquantes : {len(missing_species):,}")
    log.info(f"Déjà en cache     : {len(missing_species) - len(todo):,}")
    log.info(f"À récupérer       : {len(todo):,}")

    n_found_total = 0

    with tqdm(total=len(todo), desc="Images iNaturalist", unit="sp") as pbar:
        for i, species in enumerate(todo):
            try:
                url = fetch_image_for_species(species)
                cache[species] = url
                if url:
                    n_found_total += 1
            except Exception as ex:
                log.error(f"Erreur inattendue pour '{species}' : {ex}")
                cache[species] = None

            pbar.update(1)
            time.sleep(API_DELAY)

            # Sauvegarde tous les BATCH_SIZE espèces
            if (i + 1) % BATCH_SIZE == 0:
                save_cache(cache, cache_path)
                log.info(f"  {i+1}/{len(todo)} traités — {n_found_total} images trouvées jusqu'ici")

    # Sauvegarde finale
    save_cache(cache, cache_path)

    # Appliquer au DataFrame
    filled = 0
    for idx, row in df[missing_mask].iterrows():
        url = cache.get(row["Species"])
        if url:
            df.at[idx, "image_url"] = url
            filled += 1

    log.info(f"\nImages comblées   : {filled:,} / {len(missing_species):,}")
    log.info(f"Encore sans image : {len(missing_species) - filled:,}")
    return df


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Complétion images iNaturalist")
    parser.add_argument("input",  help="CSV en entrée")
    parser.add_argument("output", help="CSV de sortie")
    parser.add_argument(
        "--cache", type=str, default=None,
        help="Cache JSON (défaut: <output>.img_cache.json)"
    )
    parser.add_argument(
        "--skip-test", action="store_true",
        help="Ne pas tester la connexion au démarrage"
    )
    args = parser.parse_args()

    out_path   = Path(args.output)
    cache_path = Path(args.cache) if args.cache else out_path.with_suffix(".img_cache.json")

    # Test de connexion
    if not args.skip_test:
        log.info("Test de connexion iNaturalist...")
        if not test_connection():
            log.error("Impossible de joindre l'API iNaturalist. Vérifiez votre connexion internet.")
            return

    df = pd.read_csv(args.input, encoding="utf-8")
    n_missing = df["image_url"].isna().sum()
    log.info(f"{len(df):,} espèces chargées — {n_missing:,} images manquantes")

    if n_missing == 0:
        log.info("Aucune image manquante, rien à faire.")
        df.to_csv(out_path, index=False, encoding="utf-8")
        return

    df = fix_images(df, cache_path)

    total    = len(df)
    n_images = df["image_url"].notna().sum()
    log.info(f"\nCouverture finale : {n_images:,} / {total:,} ({n_images/total*100:.1f}%)")

    # Résumé des sources
    wiki = df["image_url"].str.contains("wikimedia", na=False).sum()
    inat = df["image_url"].str.contains("inaturalist", na=False).sum()
    log.info(f"  Wikimedia   : {wiki:,}")
    log.info(f"  iNaturalist : {inat:,}")

    df.to_csv(out_path, index=False, encoding="utf-8")
    log.info(f"✅ Fichier exporté → {out_path}")
    log.info(f"💾 Cache conservé  → {cache_path}")

    # Aperçu
    inat_sample = df[df["image_url"].str.contains("inaturalist", na=False)][["Species", "nom_francais", "image_url"]].head(5)
    if len(inat_sample):
        print("\n── Exemples images iNaturalist ──")
        print(inat_sample.to_string(index=False))


if __name__ == "__main__":
    main()
