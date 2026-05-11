"""
process_flora.py
================
Traite un fichier CSV/TSV de données floristiques (format GBIF/SwissNBD),
groupe les occurrences par taxonomie complète (Kingdom→Species),
récupère l'altitude via l'API SwissTopo (coordonnées MN95/LV95),
et produit un CSV avec altitude_min/max par taxon.

Fonctionnalités :
  - Conversion WGS84 → MN95 (LV95) pour l'API SwissTopo
  - Traitement par batch avec sauvegarde intermédiaire (reprise automatique)
  - Cache disque des altitudes déjà récupérées

Usage:
    python process_flora.py input.csv output.csv
    python process_flora.py input.csv output.csv --only-switzerland
    python process_flora.py input.csv output.csv --batch-size 500
    python process_flora.py input.csv output.csv --coord-precision 4

Requirements:
    pip install pandas requests tqdm
"""

import csv
import json
import time
import logging
import argparse
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

# ── Configuration ──────────────────────────────────────────────────────────────

SWISSTOPO_HEIGHT_API = "https://api3.geo.admin.ch/rest/services/height"
SWISSTOPO_REFRAME_API = "https://geodesy.geo.admin.ch/reframe/wgs84tolv95"

API_DELAY   = 0.05   # secondes entre requêtes
MAX_RETRIES = 3
BATCH_SIZE  = 500    # points traités par batch avant sauvegarde intermédiaire

COL_LAT     = "decimalLatitude"
COL_LON     = "decimalLongitude"
COL_COUNTRY = "countryCode"

TAXONOMY_COLS = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species"]

COORD_PRECISION = 3  # 3 décimales ≈ 100m, 4 décimales ≈ 11m

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Chargement ─────────────────────────────────────────────────────────────────

def detect_separator(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        first_line = f.readline()
    return "\t" if first_line.count("\t") > first_line.count(",") else ","


def load_data(path: str) -> pd.DataFrame:
    sep = detect_separator(path)
    log.info(f"Chargement de {path}  (séparateur: {'TAB' if sep == chr(9) else 'virgule'})")

    chunks = []
    for i, chunk in enumerate(pd.read_csv(
        path, sep=sep, encoding="utf-8",
        on_bad_lines="skip", low_memory=False, chunksize=200_000
    )):
        chunks.append(chunk)
        log.info(f"  chunk {i+1} — {len(chunk):,} lignes")

    df = pd.concat(chunks, ignore_index=True)
    log.info(f"Total : {len(df):,} lignes, {len(df.columns)} colonnes")
    return df


# ── Normalisation des colonnes ─────────────────────────────────────────────────

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes vers les noms standard, insensible à la casse."""
    global TAXONOMY_COLS
    lower_cols = {c.lower(): c for c in df.columns}
    col_map = {}

    for target, candidates in {
        COL_LAT: ["decimallatitude", "latitude", "lat", "y"],
        COL_LON: ["decimallongitude", "longitude", "lon", "lng", "x"],
    }.items():
        for c in candidates:
            if c in lower_cols:
                col_map[lower_cols[c]] = target
                break

    for tax in TAXONOMY_COLS:
        if tax not in df.columns and tax.lower() in lower_cols:
            col_map[lower_cols[tax.lower()]] = tax

    df = df.rename(columns=col_map)

    missing_coords = [c for c in [COL_LAT, COL_LON] if c not in df.columns]
    if missing_coords:
        raise ValueError(
            f"Colonnes de coordonnées introuvables : {missing_coords}\n"
            f"Colonnes disponibles : {list(df.columns)[:20]}"
        )

    missing_tax = [c for c in TAXONOMY_COLS if c not in df.columns]
    if missing_tax:
        log.warning(f"Colonnes taxonomiques absentes : {missing_tax} — ignorées")

    TAXONOMY_COLS = [c for c in TAXONOMY_COLS if c in df.columns]
    log.info(f"Colonnes taxonomiques utilisées : {TAXONOMY_COLS}")
    return df


# ── Nettoyage des coordonnées ──────────────────────────────────────────────────

def clean_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    df[COL_LAT] = pd.to_numeric(df[COL_LAT], errors="coerce")
    df[COL_LON] = pd.to_numeric(df[COL_LON], errors="coerce")

    before = len(df)
    df = df.dropna(subset=[COL_LAT, COL_LON] + TAXONOMY_COLS)
    df = df[(df[COL_LAT].between(-90, 90)) & (df[COL_LON].between(-180, 180))]
    log.info(f"Lignes conservées après nettoyage : {len(df):,} / {before:,}")

    df = df.copy()
    df["lat_r"] = df[COL_LAT].round(COORD_PRECISION)
    df["lon_r"] = df[COL_LON].round(COORD_PRECISION)
    return df


# ── Conversion WGS84 → MN95 (LV95) ────────────────────────────────────────────

def wgs84_to_mn95(lat: float, lon: float) -> tuple[float, float] | tuple[None, None]:
    """
    Convertit des coordonnées WGS84 (lat, lon) en MN95/LV95 (E, N)
    via l'API de reprojection SwissTopo.
    Retourne (None, None) si le point est hors Suisse ou en cas d'erreur.

    Doc : https://geodesy.geo.admin.ch/reframe/
    """
    params = {"easting": lon, "northing": lat, "format": "json"}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(SWISSTOPO_REFRAME_API, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                # Réponse : {"easting": 2600000.0, "northing": 1200000.0}
                e = data.get("easting")
                n = data.get("northing")
                if e is not None and n is not None:
                    return float(e), float(n)
                return None, None
            elif r.status_code in (400, 404):
                # Hors couverture Suisse
                return None, None
            else:
                log.warning(f"Reframe HTTP {r.status_code} pour ({lat},{lon}), tentative {attempt}")
        except requests.RequestException as ex:
            log.warning(f"Reframe erreur réseau pour ({lat},{lon}), tentative {attempt} : {ex}")
            time.sleep(1 * attempt)

    return None, None


# ── API SwissTopo Altitude ─────────────────────────────────────────────────────

def get_altitude_mn95(easting: float, northing: float) -> float | None:
    """
    Altitude en mètres via l'API SwissTopo avec coordonnées MN95/LV95.
    Retourne None en cas d'erreur.

    Doc : https://api3.geo.admin.ch/services/sdiservices.html#height
    """
    # L'API height attend easting=E (longitude CH), northing=N (latitude CH), sr=2056 (LV95)
    params = {"easting": easting, "northing": northing, "sr": 2056}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(SWISSTOPO_HEIGHT_API, params=params, timeout=10)
            if r.status_code == 200:
                alt = r.json().get("height")
                return float(alt) if alt is not None else None
            elif r.status_code == 400:
                return None
            else:
                log.warning(f"Height HTTP {r.status_code} pour E={easting},N={northing}, tentative {attempt}")
        except requests.RequestException as ex:
            log.warning(f"Height erreur réseau pour E={easting},N={northing}, tentative {attempt} : {ex}")
            time.sleep(1 * attempt)

    return None


# ── Cache disque ───────────────────────────────────────────────────────────────

def load_cache(cache_path: Path) -> dict:
    """Charge le cache JSON des altitudes déjà récupérées."""
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # Les clés JSON sont des strings ; on les reconvertit en tuples float
        cache = {tuple(map(float, k.split("|"))): v for k, v in raw.items()}
        log.info(f"Cache chargé : {len(cache):,} altitudes déjà connues ({cache_path})")
        return cache
    return {}


def save_cache(cache: dict, cache_path: Path) -> None:
    """Sauvegarde le cache JSON sur disque."""
    raw = {f"{k[0]}|{k[1]}": v for k, v in cache.items()}
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(raw, f)


# ── Récupération des altitudes par batch ───────────────────────────────────────

def fetch_unique_altitudes(df: pd.DataFrame, cache_path: Path, batch_size: int) -> pd.DataFrame:
    """
    Récupère l'altitude pour chaque coordonnée unique (arrondie).
    - Convertit WGS84 → MN95 via l'API SwissTopo Reframe
    - Interroge l'API Height avec les coordonnées MN95
    - Sauvegarde le cache sur disque à chaque batch (reprise en cas de crash)
    """
    unique_coords = df[["lat_r", "lon_r"]].drop_duplicates().copy().reset_index(drop=True)
    total = len(unique_coords)
    log.info(f"Coordonnées uniques à interroger : {total:,}  (batch size: {batch_size})")

    cache = load_cache(cache_path)

    # Séparer ce qui est déjà en cache et ce qui reste à faire
    todo_mask = unique_coords.apply(
        lambda row: (row["lat_r"], row["lon_r"]) not in cache, axis=1
    )
    todo = unique_coords[todo_mask].copy()
    log.info(f"  Déjà en cache : {total - len(todo):,}  |  Restant : {len(todo):,}")

    # Traitement par batch
    n_batches = (len(todo) + batch_size - 1) // batch_size if len(todo) > 0 else 0

    with tqdm(total=len(todo), desc="Altitudes SwissTopo", unit="pts") as pbar:
        for batch_idx in range(n_batches):
            batch = todo.iloc[batch_idx * batch_size : (batch_idx + 1) * batch_size]
            errors_in_batch = 0

            for _, row in batch.iterrows():
                lat, lon = row["lat_r"], row["lon_r"]
                key = (lat, lon)

                try:
                    # Étape 1 : conversion WGS84 → MN95
                    e, n = wgs84_to_mn95(lat, lon)
                    if e is None:
                        cache[key] = None  # Hors Suisse
                    else:
                        # Étape 2 : altitude via MN95
                        cache[key] = get_altitude_mn95(e, n)
                    time.sleep(API_DELAY)

                except Exception as ex:
                    log.error(f"Erreur inattendue pour ({lat},{lon}) : {ex}")
                    cache[key] = None
                    errors_in_batch += 1

                pbar.update(1)

            # Sauvegarde du cache après chaque batch
            save_cache(cache, cache_path)
            if errors_in_batch:
                log.warning(f"Batch {batch_idx+1}/{n_batches} — {errors_in_batch} erreurs (altitudes à None)")
            else:
                log.info(f"Batch {batch_idx+1}/{n_batches} sauvegardé ✓")

    # Construire le DataFrame résultat depuis le cache
    unique_coords["altitude_m"] = unique_coords.apply(
        lambda row: cache.get((row["lat_r"], row["lon_r"])), axis=1
    )

    n_ok  = unique_coords["altitude_m"].notna().sum()
    n_nok = unique_coords["altitude_m"].isna().sum()
    log.info(f"  ✓ {n_ok:,} altitudes obtenues  |  {n_nok:,} hors couverture ou erreur")
    return unique_coords


# ── Agrégation ─────────────────────────────────────────────────────────────────

def build_summary(df: pd.DataFrame, altitudes: pd.DataFrame) -> pd.DataFrame:
    df = df.merge(altitudes, on=["lat_r", "lon_r"], how="left")

    agg = (
        df.groupby(TAXONOMY_COLS, dropna=False)
        .agg(
            nb_occurrences      = (COL_LAT,      "count"),
            nb_coordonnees_uniq = ("lat_r",       "nunique"),
            altitude_min_m      = ("altitude_m",  "min"),
            altitude_max_m      = ("altitude_m",  "max"),
            altitude_moy_m      = ("altitude_m",  "mean"),
            latitude_min        = (COL_LAT,       "min"),
            latitude_max        = (COL_LAT,       "max"),
            longitude_min       = (COL_LON,       "min"),
            longitude_max       = (COL_LON,       "max"),
        )
        .reset_index()
    )

    agg["altitude_min_m"] = agg["altitude_min_m"].round(0).astype("Int64")
    agg["altitude_max_m"] = agg["altitude_max_m"].round(0).astype("Int64")
    agg["altitude_moy_m"] = agg["altitude_moy_m"].round(1)

    return agg.sort_values("nb_occurrences", ascending=False)


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def main():
    global COORD_PRECISION, BATCH_SIZE

    parser = argparse.ArgumentParser(description="Flora altitude aggregator — SwissTopo MN95")
    parser.add_argument("input",  help="Fichier CSV/TSV en entrée")
    parser.add_argument("output", help="Fichier CSV de sortie")
    parser.add_argument(
        "--only-switzerland", action="store_true",
        help="Filtrer uniquement les occurrences en Suisse (CH)"
    )
    parser.add_argument(
        "--coord-precision", type=int, default=COORD_PRECISION,
        help=f"Décimales pour dédupliquer les coords (défaut: {COORD_PRECISION})"
    )
    parser.add_argument(
        "--batch-size", type=int, default=BATCH_SIZE,
        help=f"Points traités par batch avant sauvegarde (défaut: {BATCH_SIZE})"
    )
    parser.add_argument(
        "--cache", type=str, default=None,
        help="Chemin du fichier cache JSON (défaut: <output>.cache.json)"
    )
    args = parser.parse_args()

    COORD_PRECISION = args.coord_precision
    BATCH_SIZE      = args.batch_size

    out_path   = Path(args.output)
    cache_path = Path(args.cache) if args.cache else out_path.with_suffix(".cache.json")

    df = load_data(args.input)
    df = normalize_columns(df)

    if args.only_switzerland and COL_COUNTRY in df.columns:
        before = len(df)
        df = df[df[COL_COUNTRY].str.upper() == "CH"]
        log.info(f"Filtre Suisse : {len(df):,} / {before:,} lignes conservées")

    df = clean_coordinates(df)
    altitudes = fetch_unique_altitudes(df, cache_path, BATCH_SIZE)
    summary   = build_summary(df, altitudes)

    log.info(f"Taxons uniques : {len(summary):,}")
    summary.to_csv(out_path, index=False, encoding="utf-8")
    log.info(f"✅ Résultat exporté → {out_path}")
    log.info(f"💾 Cache conservé  → {cache_path}  (relancer pour reprendre)")

    print("\n── Aperçu des 10 premières lignes ──")
    print(summary.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
