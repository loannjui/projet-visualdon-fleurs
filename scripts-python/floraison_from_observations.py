"""
floraison_from_observations.py
==============================
Déduit les mois de floraison (début/fin) depuis les observations GBIF
et comble les trous dans le CSV enrichi (floraison_debut/fin à NULL).

Lit le fichier d'origine par chunks pour gérer les 5M de lignes
sans saturer la mémoire.

Usage:
    python floraison_from_observations.py occurrences.csv enrichi_final2.csv output.csv

Requirements:
    pip install pandas tqdm
"""

import logging
import argparse
from pathlib import Path

import pandas as pd
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

CHUNK_SIZE = 200_000


def detect_separator(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        first_line = f.readline()
    return "\t" if first_line.count("\t") > first_line.count(",") else ","


def extract_flowering_months(occurrences_path: str) -> pd.DataFrame:
    """
    Lit le fichier d'occurrences par chunks et calcule pour chaque espèce :
    - le mois minimum d'observation (= début floraison empirique)
    - le mois maximum d'observation (= fin floraison empirique)

    On exclut les mois 1 et 12 des extrêmes si possible, car les observations
    hivernales sont souvent des relevés de feuillage, pas de floraison.
    """
    sep = detect_separator(occurrences_path)
    log.info(f"Lecture de {occurrences_path} par chunks de {CHUNK_SIZE:,}...")

    # Accumulateur : pour chaque espèce, ensemble des mois observés
    species_months: dict[str, set] = {}

    reader = pd.read_csv(
        occurrences_path,
        sep=sep,
        encoding="utf-8",
        on_bad_lines="skip",
        low_memory=False,
        chunksize=CHUNK_SIZE,
        usecols=lambda c: c in ["species", "Species", "month"],
    )

    for i, chunk in enumerate(tqdm(reader, desc="Chunks lus", unit="chunk")):
        # Normaliser le nom de colonne species
        chunk.columns = [c.lower() for c in chunk.columns]
        if "species" not in chunk.columns or "month" not in chunk.columns:
            log.error(f"Colonnes manquantes dans le chunk {i+1}. Colonnes trouvées : {list(chunk.columns)}")
            continue

        chunk = chunk.dropna(subset=["species", "month"])
        chunk["month"] = pd.to_numeric(chunk["month"], errors="coerce")
        chunk = chunk[chunk["month"].between(1, 12)]

        for species, group in chunk.groupby("species"):
            months = set(group["month"].astype(int).tolist())
            if species in species_months:
                species_months[species].update(months)
            else:
                species_months[species] = months

        log.info(f"  chunk {i+1} — {len(species_months):,} espèces vues jusqu'ici")

    # Construire le DataFrame résultat
    rows = []
    for species, months in species_months.items():
        sorted_months = sorted(months)

        # Heuristique : si on a plus de 2 mois distincts, on ignore
        # janvier (1) et décembre (12) comme bornes si d'autres mois existent
        # (évite que des relevés hivernaux de feuillage faussent la floraison)
        if len(sorted_months) > 2:
            filtered = [m for m in sorted_months if m not in (1, 12)]
            if len(filtered) >= 2:
                sorted_months = filtered

        rows.append({
            "Species":           species,
            "floraison_debut_obs": sorted_months[0],
            "floraison_fin_obs":   sorted_months[-1],
            "nb_mois_obs":         len(months),
        })

    df_months = pd.DataFrame(rows)
    log.info(f"Espèces avec mois d'observation : {len(df_months):,}")
    return df_months


def merge_and_fill(enriched_path: str, df_months: pd.DataFrame, output_path: str) -> None:
    """
    Joint les mois empiriques au CSV enrichi et comble uniquement
    les lignes où floraison_debut / floraison_fin sont NULL.
    """
    log.info(f"Chargement de {enriched_path}...")
    df = pd.read_csv(enriched_path, encoding="utf-8")

    before_debut = df["floraison_debut"].notna().sum()
    before_fin   = df["floraison_fin"].notna().sum()

    df = df.merge(df_months[["Species", "floraison_debut_obs", "floraison_fin_obs", "nb_mois_obs"]],
                  on="Species", how="left")

    # Combler uniquement les NULL
    mask_debut = df["floraison_debut"].isna() & df["floraison_debut_obs"].notna()
    mask_fin   = df["floraison_fin"].isna()   & df["floraison_fin_obs"].notna()

    df.loc[mask_debut, "floraison_debut"] = df.loc[mask_debut, "floraison_debut_obs"]
    df.loc[mask_fin,   "floraison_fin"]   = df.loc[mask_fin,   "floraison_fin_obs"]

    # Nettoyer les colonnes temporaires
    df = df.drop(columns=["floraison_debut_obs", "floraison_fin_obs", "nb_mois_obs"])

    # Repasser en Int64 propre
    df["floraison_debut"] = pd.array(df["floraison_debut"], dtype="Int64")
    df["floraison_fin"]   = pd.array(df["floraison_fin"],   dtype="Int64")

    after_debut = df["floraison_debut"].notna().sum()
    after_fin   = df["floraison_fin"].notna().sum()
    total       = len(df)

    log.info(f"floraison_debut : {before_debut:,} → {after_debut:,} / {total:,}  (+{after_debut - before_debut:,} comblés)")
    log.info(f"floraison_fin   : {before_fin:,} → {after_fin:,} / {total:,}  (+{after_fin - before_fin:,} comblés)")

    # Espèces encore sans floraison
    still_missing = df[df["floraison_debut"].isna()]["Species"].nunique()
    log.info(f"Espèces encore sans floraison : {still_missing:,}")

    df.to_csv(output_path, index=False, encoding="utf-8")
    log.info(f"✅ Fichier exporté → {output_path}")


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Floraison empirique depuis observations GBIF")
    parser.add_argument("occurrences", help="Fichier d'occurrences original (5M lignes)")
    parser.add_argument("enriched",    help="CSV enrichi_final2.csv (avec floraison Wikidata)")
    parser.add_argument("output",      help="CSV final de sortie")
    args = parser.parse_args()

    df_months = extract_flowering_months(args.occurrences)
    merge_and_fill(args.enriched, df_months, args.output)


if __name__ == "__main__":
    main()
