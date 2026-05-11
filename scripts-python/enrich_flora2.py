"""
enrich_flora2.py
================
Enrichit le CSV avec deux nouvelles colonnes :
  - floraison_debut  : mois de début de floraison (1-12)
  - floraison_fin    : mois de fin de floraison (1-12)
  - image_url        : lien vers l'image Wikimedia Commons

Source : Wikidata SPARQL
  - P2777 : période de floraison (valeur ordinale 1-12)
  - P18   : image principale

Usage:
    python enrich_flora2.py enrichi_final.csv enrichi_final2.csv
    python enrich_flora2.py enrichi_final.csv enrichi_final2.csv --batch-size 50

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

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
API_DELAY       = 0.5    # Wikidata est strict sur le rate-limit, on est prudent
MAX_RETRIES     = 3
BATCH_SIZE      = 50     # Nombre d'espèces par requête SPARQL (VALUES batch)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "FloraAltitudeResearch/2.0 (scientific research; contact@example.com)",
}

# Mapping des labels de mois Wikidata → entier 1-12
# Wikidata stocke les mois comme des items QID avec des labels
MONTH_LABELS = {
    "january": 1, "janvier": 1, "januar": 1,
    "february": 2, "février": 2, "februar": 2,
    "march": 3, "mars": 3, "märz": 3,
    "april": 4, "avril": 4,
    "may": 5, "mai": 5,
    "june": 6, "juin": 6, "juni": 6,
    "july": 7, "juillet": 7, "juli": 7,
    "august": 8, "août": 8,
    "september": 9, "septembre": 9,
    "october": 10, "octobre": 10, "oktober": 10,
    "november": 11, "novembre": 11,
    "december": 12, "décembre": 12, "dezember": 12,
}


# ── Cache disque ───────────────────────────────────────────────────────────────

def load_cache(cache_path: Path) -> dict:
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        log.info(f"Cache chargé : {len(cache):,} espèces déjà traitées ({cache_path})")
        return cache
    return {}


def save_cache(cache: dict, cache_path: Path) -> None:
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ── Wikidata SPARQL ────────────────────────────────────────────────────────────

def parse_month(label: str) -> int | None:
    """Convertit un label de mois (en/fr/de) en entier 1-12."""
    if not label:
        return None
    return MONTH_LABELS.get(label.lower().strip())


def query_wikidata_batch(species_list: list[str]) -> dict:
    """
    Interroge Wikidata pour un batch d'espèces en une seule requête SPARQL.
    Retourne un dict { species_name: { floraison_debut, floraison_fin, image_url } }

    Propriétés utilisées :
      P225  : nom taxon scientifique
      P2777 : période de floraison (item de mois)
      P18   : image principale

    Note sur P2777 : Wikidata stocke souvent début et fin comme deux valeurs
    distinctes de la même propriété, avec qualificatifs P580 (début) et P582 (fin).
    On récupère les labels des mois et on trie pour extraire min/max.
    """
    # Formater la liste VALUES pour SPARQL
    values_str = " ".join(f'"{s}"' for s in species_list)

    query = f"""
    SELECT ?taxon ?monthLabel ?image WHERE {{
      VALUES ?taxon {{ {values_str} }}
      ?plant wdt:P225 ?taxon .
      OPTIONAL {{
        ?plant wdt:P2777 ?month .
        SERVICE wikibase:label {{
          bd:serviceParam wikibase:language "fr,en,de" .
          ?month rdfs:label ?monthLabel .
        }}
      }}
      OPTIONAL {{ ?plant wdt:P18 ?image . }}
    }}
    """

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                WIKIDATA_SPARQL,
                params={"query": query, "format": "json"},
                headers=HEADERS,
                timeout=30,
            )
            if r.status_code == 200:
                bindings = r.json().get("results", {}).get("bindings", [])
                return parse_batch_results(bindings, species_list)

            elif r.status_code == 429:
                wait = 15 * attempt
                log.warning(f"Wikidata rate-limit, attente {wait}s...")
                time.sleep(wait)

            elif r.status_code == 500:
                # Erreur serveur Wikidata, souvent temporaire
                log.warning(f"Wikidata erreur 500, tentative {attempt}/{MAX_RETRIES}")
                time.sleep(5 * attempt)

            else:
                log.warning(f"Wikidata HTTP {r.status_code}, tentative {attempt}/{MAX_RETRIES}")
                time.sleep(3 * attempt)

        except requests.RequestException as ex:
            log.warning(f"Erreur réseau Wikidata, tentative {attempt}/{MAX_RETRIES} : {ex}")
            time.sleep(5 * attempt)

    # Échec total : retourner des None pour toutes les espèces du batch
    log.error(f"Batch échoué après {MAX_RETRIES} tentatives")
    return {s: {"floraison_debut": None, "floraison_fin": None, "image_url": None}
            for s in species_list}


def parse_batch_results(bindings: list, species_list: list[str]) -> dict:
    """
    Parse les résultats SPARQL et extrait floraison min/max et image par espèce.
    Plusieurs lignes peuvent exister pour la même espèce (plusieurs mois retournés).
    """
    # Initialiser avec None pour toutes les espèces
    results = {
        s: {"months": [], "image_url": None}
        for s in species_list
    }

    for b in bindings:
        taxon = b.get("taxon", {}).get("value")
        if taxon not in results:
            continue

        # Mois de floraison
        month_label = b.get("monthLabel", {}).get("value", "")
        month_num = parse_month(month_label)
        if month_num and month_num not in results[taxon]["months"]:
            results[taxon]["months"].append(month_num)

        # Image (on garde la première trouvée)
        image = b.get("image", {}).get("value")
        if image and not results[taxon]["image_url"]:
            results[taxon]["image_url"] = image

    # Convertir les listes de mois en début/fin
    final = {}
    for species, data in results.items():
        months = sorted(data["months"])
        final[species] = {
            "floraison_debut": months[0] if months else None,
            "floraison_fin":   months[-1] if months else None,
            "image_url":       data["image_url"],
        }

    return final


# ── Pipeline principal ─────────────────────────────────────────────────────────

def enrich_dataframe(df: pd.DataFrame, cache_path: Path, batch_size: int) -> pd.DataFrame:
    cache = load_cache(cache_path)

    # Espèces uniques à traiter
    all_species = df["Species"].unique().tolist()
    todo = [s for s in all_species if s not in cache]
    log.info(f"Espèces uniques : {len(all_species):,}  |  Déjà en cache : {len(all_species)-len(todo):,}  |  Restant : {len(todo):,}")

    # Traitement par batch SPARQL
    n_batches = (len(todo) + batch_size - 1) // batch_size if todo else 0

    with tqdm(total=len(todo), desc="Floraison + images Wikidata", unit="sp") as pbar:
        for i in range(n_batches):
            batch = todo[i * batch_size : (i + 1) * batch_size]

            try:
                results = query_wikidata_batch(batch)
                cache.update(results)
            except Exception as ex:
                log.error(f"Erreur inattendue sur batch {i+1} : {ex}")
                # Marquer toutes les espèces du batch comme traitées avec None
                for s in batch:
                    cache[s] = {"floraison_debut": None, "floraison_fin": None, "image_url": None}

            pbar.update(len(batch))
            save_cache(cache, cache_path)
            log.info(f"Batch {i+1}/{n_batches} sauvegardé ✓")
            time.sleep(API_DELAY)

    # Appliquer le cache au DataFrame
    df["floraison_debut"] = df["Species"].map(lambda s: (cache.get(s) or {}).get("floraison_debut"))
    df["floraison_fin"]   = df["Species"].map(lambda s: (cache.get(s) or {}).get("floraison_fin"))
    df["image_url"]       = df["Species"].map(lambda s: (cache.get(s) or {}).get("image_url"))

    # Convertir en Int64 pour avoir des entiers propres (pas de 3.0)
    df["floraison_debut"] = pd.array(df["floraison_debut"], dtype="Int64")
    df["floraison_fin"]   = pd.array(df["floraison_fin"],   dtype="Int64")

    return df


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enrichissement floraison + image Wikimedia")
    parser.add_argument("input",  help="CSV enrichi_final.csv")
    parser.add_argument("output", help="CSV de sortie")
    parser.add_argument(
        "--batch-size", type=int, default=BATCH_SIZE,
        help=f"Espèces par requête SPARQL (défaut: {BATCH_SIZE})"
    )
    parser.add_argument(
        "--cache", type=str, default=None,
        help="Chemin du cache JSON (défaut: <output>.flora2_cache.json)"
    )
    args = parser.parse_args()

    out_path   = Path(args.output)
    cache_path = Path(args.cache) if args.cache else out_path.with_suffix(".flora2_cache.json")

    log.info(f"Chargement de {args.input}")
    df = pd.read_csv(args.input, encoding="utf-8")
    log.info(f"{len(df):,} lignes, {df['Species'].nunique():,} espèces uniques")

    df = enrich_dataframe(df, cache_path, args.batch_size)

    # Réordonner : mettre les nouvelles colonnes après couleur_hex
    cols = list(df.columns)
    for col in ["floraison_debut", "floraison_fin", "image_url"]:
        if col in cols:
            cols.remove(col)
    insert_after = cols.index("couleur_hex") + 1
    for col in reversed(["floraison_debut", "floraison_fin", "image_url"]):
        cols.insert(insert_after, col)
    df = df[cols]

    df.to_csv(out_path, index=False, encoding="utf-8")
    log.info(f"✅ Résultat exporté → {out_path}")
    log.info(f"💾 Cache conservé  → {cache_path}")

    # Stats
    n_debut  = df["floraison_debut"].notna().sum()
    n_fin    = df["floraison_fin"].notna().sum()
    n_images = df["image_url"].notna().sum()
    total    = len(df)
    log.info(f"Floraison début trouvée : {n_debut:,} / {total:,} ({n_debut/total*100:.1f}%)")
    log.info(f"Floraison fin trouvée   : {n_fin:,} / {total:,} ({n_fin/total*100:.1f}%)")
    log.info(f"Images trouvées         : {n_images:,} / {total:,} ({n_images/total*100:.1f}%)")

    print("\n── Aperçu ──")
    print(df[["Species", "nom_francais", "floraison_debut", "floraison_fin", "image_url"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
