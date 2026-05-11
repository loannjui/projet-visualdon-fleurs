"""
enrich_flora.py
===============
Enrichit le CSV produit par process_flora.py avec :
  - nom_francais   : nom vernaculaire français via l'API GBIF
  - couleur_hex    : couleur de fleur via Wikidata (propriété P2827)
                     fallback sur un dictionnaire par famille botanique

Usage:
    python enrich_flora.py resultat_flora_final.csv enrichi.csv
    python enrich_flora.py resultat_flora_final.csv enrichi.csv --batch-size 100

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

GBIF_MATCH_API    = "https://api.gbif.org/v1/species/match"
GBIF_VERNACULAR_API = "https://api.gbif.org/v1/species/{}/vernacularNames"
WIKIDATA_SPARQL   = "https://query.wikidata.org/sparql"

API_DELAY   = 0.15   # secondes entre requêtes (Wikidata est strict sur le rate-limit)
MAX_RETRIES = 3
BATCH_SIZE  = 100

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Fallback couleurs par famille ──────────────────────────────────────────────
# Couleurs représentatives (pas universelles, mais cohérentes visuellement)

FAMILY_COLORS = {
    "Asteraceae":       "#FFD700",  # jaune (marguerites, tournesols)
    "Rosaceae":         "#FFB6C1",  # rose pâle (roses, cerisiers)
    "Fabaceae":         "#9B59B6",  # violet (trèfles, lupin)
    "Lamiaceae":        "#8A2BE2",  # bleu-violet (lavande, menthe)
    "Orchidaceae":      "#FF69B4",  # rose vif (orchidées)
    "Ranunculaceae":    "#FFFF00",  # jaune (boutons d'or)
    "Brassicaceae":     "#FFFACD",  # jaune pâle (colza, moutarde)
    "Apiaceae":         "#FFFFFF",  # blanc (carotte sauvage, persil)
    "Scrophulariaceae": "#9370DB",  # violet moyen
    "Plantaginaceae":   "#90EE90",  # vert pâle
    "Campanulaceae":    "#6495ED",  # bleu campanule
    "Violaceae":        "#EE82EE",  # violet (violettes)
    "Caryophyllaceae":  "#FF1493",  # rose vif (œillet)
    "Polygonaceae":     "#CD5C5C",  # rouge indien (rumex)
    "Primulaceae":      "#FFD700",  # jaune (primevère)
    "Gentianaceae":     "#1E90FF",  # bleu gentiane
    "Boraginaceae":     "#0000CD",  # bleu vif (myosotis)
    "Liliaceae":        "#FF6347",  # orange-rouge (tulipes)
    "Amaryllidaceae":   "#FFFF00",  # jaune (narcisses)
    "Iridaceae":        "#8B008B",  # violet foncé (iris)
    "Onagraceae":       "#FF69B4",  # rose (épilobe)
    "Papaveraceae":     "#FF0000",  # rouge (coquelicot)
    "Geraniaceae":      "#FF69B4",  # rose (géranium)
    "Ericaceae":        "#FF1493",  # rose vif (bruyère)
    "Saxifragaceae":    "#FFFFFF",  # blanc
    "Dipsacaceae":      "#9370DB",  # violet (scabieuse)
    "Caprifoliaceae":   "#FFFFFF",  # blanc crème (sureau)
    "Rubiaceae":        "#FFFFFF",  # blanc (gaillet)
    "Convolvulaceae":   "#FF69B4",  # rose (liseron)
    "Solanaceae":       "#9370DB",  # violet (morelle)
    "Euphorbiaceae":    "#90EE90",  # vert
    "Urticaceae":       "#228B22",  # vert foncé (ortie)
    "Poaceae":          "#7CFC00",  # vert prairie (graminées)
    "Cyperaceae":       "#556B2F",  # vert olive (carex)
    "Juncaceae":        "#8FBC8F",  # vert mer
    "Salicaceae":       "#9ACD32",  # vert jaune
    "Betulaceae":       "#DEB887",  # brun clair (chatons)
    "Fagaceae":         "#D2691E",  # brun (chêne)
    "Pinaceae":         "#228B22",  # vert foncé (conifères)
    "Aspleniaceae":     "#2E8B57",  # vert mer (fougères)
    "Polypodiaceae":    "#2E8B57",  # vert mer (fougères)
    "Athyriaceae":      "#2E8B57",
    "Dryopteridaceae":  "#2E8B57",
    "Blechnaceae":      "#2E8B57",
    "Equisetaceae":     "#3CB371",  # vert moyen (prêles)
    "Araceae":          "#ADFF2F",  # vert jaune (arum)
    "Balsaminaceae":    "#FF6347",  # orange-rouge (impatiente)
    "Hydrangeaceae":    "#87CEEB",  # bleu ciel (hortensia)
    "Berberidaceae":    "#FFD700",  # jaune (épine-vinette)
    "Apocynaceae":      "#FF69B4",  # rose (pervenche)
    "Acanthaceae":      "#9370DB",  # violet
    "Aquifoliaceae":    "#FFFFFF",  # blanc (houx)
    "Oleaceae":         "#FFFFFF",  # blanc (lilas, troène)
    "Cornaceae":        "#FFFFFF",  # blanc (cornouiller)
    "Crassulaceae":     "#FFD700",  # jaune (orpin)
    "Cistaceae":        "#FFD700",  # jaune (cistus)
    "Thymelaeaceae":    "#FF69B4",  # rose (daphné)
    "Lythraceae":       "#CC0066",  # rose foncé (salicaire)
    "Malvaceae":        "#FF69B4",  # rose (mauve)
    "Hypericaceae":     "#FFD700",  # jaune (millepertuis)
    "Oxalidaceae":      "#FFD700",  # jaune (oxalis)
    "Linaceae":         "#6495ED",  # bleu (lin)
    "Resedaceae":       "#F0E68C",  # jaune kaki (réséda)
    "Fumariaceae":      "#DDA0DD",  # prune (fumeterre)
    "Chenopodiaceae":   "#90EE90",  # vert pâle
    "Amaranthaceae":    "#DC143C",  # rouge cramoisi (amarante)
    "Portulacaceae":    "#FF69B4",  # rose
    "Cactaceae":        "#FFD700",  # jaune
    "Plumbaginaceae":   "#6495ED",  # bleu (statice)
    "Polemoniaceae":    "#6A5ACD",  # bleu ardoise
    "Menyanthaceae":    "#FFFFFF",  # blanc
    "Phrymaceae":       "#FF69B4",  # rose
    "Valerianaceae":    "#DDA0DD",  # lilas (valériane)
    "Adoxaceae":        "#FFFFFF",  # blanc (sureau)
    "Asparagaceae":     "#FFFFFF",  # blanc (jacinthe)
    "Colchicaceae":     "#DDA0DD",  # lilas (colchique)
    "Melanthiaceae":    "#FFFFFF",  # blanc
    "Typhaceae":        "#8B4513",  # brun (massette)
    "Alismataceae":     "#FFFFFF",  # blanc
    "Butomaceae":       "#FF69B4",  # rose
    "Hydrocharitaceae": "#FFFFFF",  # blanc
    "Potamogetonaceae": "#90EE90",  # vert
}

DEFAULT_COLOR = "#CCCCCC"  # gris pour les familles non répertoriées


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


# ── API GBIF : nom français ────────────────────────────────────────────────────

def get_gbif_usagekey(species_name: str) -> int | None:
    """Récupère l'identifiant GBIF (usageKey) d'une espèce."""
    try:
        r = requests.get(
            GBIF_MATCH_API,
            params={"name": species_name, "rank": "SPECIES"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("matchType") not in ("NONE", None):
                return data.get("usageKey")
    except requests.RequestException:
        pass
    return None


def get_french_name_gbif(usage_key: int) -> str | None:
    """Récupère le nom vernaculaire français via l'API GBIF."""
    try:
        r = requests.get(
            GBIF_VERNACULAR_API.format(usage_key),
            params={"limit": 100},
            timeout=10,
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            # Chercher en priorité : français de Suisse, puis français générique
            for lang_pref in ("fra", "fre", "fr"):
                for item in results:
                    if item.get("language", "").lower().startswith(lang_pref[:2]):
                        name = item.get("vernacularName", "").strip()
                        if name:
                            return name
    except requests.RequestException:
        pass
    return None


# ── Wikidata : couleur de fleur ────────────────────────────────────────────────

# Mapping des labels de couleur Wikidata → hex
WIKIDATA_COLOR_MAP = {
    "white":       "#FFFFFF",
    "blanc":       "#FFFFFF",
    "yellow":      "#FFD700",
    "jaune":       "#FFD700",
    "red":         "#FF0000",
    "rouge":       "#FF0000",
    "pink":        "#FF69B4",
    "rose":        "#FF69B4",
    "blue":        "#4169E1",
    "bleu":        "#4169E1",
    "purple":      "#800080",
    "violet":      "#8B008B",
    "mauve":       "#DDA0DD",
    "orange":      "#FFA500",
    "green":       "#228B22",
    "vert":        "#228B22",
    "brown":       "#8B4513",
    "brun":        "#8B4513",
    "cream":       "#FFFDD0",
    "crème":       "#FFFDD0",
    "lilac":       "#C8A2C8",
    "lilas":       "#C8A2C8",
    "magenta":     "#FF00FF",
    "lavender":    "#E6E6FA",
    "lavande":     "#E6E6FA",
}


def get_flower_color_wikidata(species_name: str) -> str | None:
    """
    Interroge Wikidata via SPARQL pour obtenir la couleur de fleur (P2827).
    Retourne un code hex ou None si non trouvé.
    """
    query = f"""
    SELECT ?colorLabel WHERE {{
      ?plant wdt:P225 "{species_name}" .
      ?plant wdt:P2827 ?color .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en" . }}
    }}
    LIMIT 5
    """
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "FloraAltitudeBot/1.0 (research; contact@example.com)",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                WIKIDATA_SPARQL,
                params={"query": query, "format": "json"},
                headers=headers,
                timeout=15,
            )
            if r.status_code == 200:
                bindings = r.json().get("results", {}).get("bindings", [])
                for b in bindings:
                    label = b.get("colorLabel", {}).get("value", "").lower().strip()
                    for key, hex_val in WIKIDATA_COLOR_MAP.items():
                        if key in label:
                            return hex_val
                return None  # Pas de couleur trouvée dans Wikidata
            elif r.status_code == 429:
                wait = 10 * attempt
                log.warning(f"Wikidata rate-limit, attente {wait}s...")
                time.sleep(wait)
            else:
                log.warning(f"Wikidata HTTP {r.status_code} pour '{species_name}', tentative {attempt}")
                time.sleep(2 * attempt)
        except requests.RequestException as ex:
            log.warning(f"Wikidata erreur réseau pour '{species_name}', tentative {attempt} : {ex}")
            time.sleep(2 * attempt)

    return None


# ── Enrichissement d'une espèce ────────────────────────────────────────────────

def enrich_species(species_name: str, family: str) -> dict:
    """
    Retourne un dict avec nom_francais et couleur_hex pour une espèce.
    Ordre de priorité pour la couleur :
      1. Wikidata (propriété P2827 couleur de fleur)
      2. Fallback dictionnaire par famille botanique
      3. Gris par défaut (#CCCCCC)
    """
    result = {"nom_francais": None, "couleur_hex": None}

    # ── Nom français via GBIF ──
    usage_key = get_gbif_usagekey(species_name)
    time.sleep(API_DELAY)
    if usage_key:
        result["nom_francais"] = get_french_name_gbif(usage_key)
        time.sleep(API_DELAY)

    # ── Couleur via Wikidata ──
    result["couleur_hex"] = get_flower_color_wikidata(species_name)
    time.sleep(API_DELAY)

    # ── Fallback famille ──
    if not result["couleur_hex"]:
        result["couleur_hex"] = FAMILY_COLORS.get(family, DEFAULT_COLOR)

    return result


# ── Pipeline principal ─────────────────────────────────────────────────────────

def enrich_dataframe(df: pd.DataFrame, cache_path: Path, batch_size: int) -> pd.DataFrame:
    cache = load_cache(cache_path)

    # Espèces uniques à traiter
    species_family = (
        df[["Species", "Family"]]
        .drop_duplicates(subset="Species")
        .reset_index(drop=True)
    )
    todo = species_family[~species_family["Species"].isin(cache)].copy()
    log.info(f"Espèces uniques : {len(species_family):,}  |  Déjà en cache : {len(species_family) - len(todo):,}  |  Restant : {len(todo):,}")

    n_batches = (len(todo) + batch_size - 1) // batch_size if len(todo) > 0 else 0

    with tqdm(total=len(todo), desc="Enrichissement espèces", unit="sp") as pbar:
        for batch_idx in range(n_batches):
            batch = todo.iloc[batch_idx * batch_size : (batch_idx + 1) * batch_size]

            for _, row in batch.iterrows():
                species = row["Species"]
                family  = row["Family"]
                try:
                    cache[species] = enrich_species(species, family)
                except Exception as ex:
                    log.error(f"Erreur inattendue pour '{species}' : {ex}")
                    cache[species] = {
                        "nom_francais": None,
                        "couleur_hex": FAMILY_COLORS.get(family, DEFAULT_COLOR),
                    }
                pbar.update(1)

            save_cache(cache, cache_path)
            log.info(f"Batch {batch_idx+1}/{n_batches} sauvegardé ✓")

    # Appliquer le cache au DataFrame
    df["nom_francais"] = df["Species"].map(lambda s: (cache.get(s) or {}).get("nom_francais"))
    df["couleur_hex"]  = df["Species"].map(lambda s: (cache.get(s) or {}).get("couleur_hex", DEFAULT_COLOR))

    return df


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enrichissement flora — noms FR + couleurs")
    parser.add_argument("input",  help="CSV produit par process_flora.py")
    parser.add_argument("output", help="CSV enrichi en sortie")
    parser.add_argument(
        "--batch-size", type=int, default=BATCH_SIZE,
        help=f"Espèces traitées par batch avant sauvegarde (défaut: {BATCH_SIZE})"
    )
    parser.add_argument(
        "--cache", type=str, default=None,
        help="Chemin du fichier cache JSON (défaut: <output>.enrich_cache.json)"
    )
    args = parser.parse_args()

    out_path   = Path(args.output)
    cache_path = Path(args.cache) if args.cache else out_path.with_suffix(".enrich_cache.json")

    log.info(f"Chargement de {args.input}")
    df = pd.read_csv(args.input, encoding="utf-8")
    log.info(f"{len(df):,} lignes, {df['Species'].nunique():,} espèces uniques")

    df = enrich_dataframe(df, cache_path, args.batch_size)

    # Réordonner les colonnes pour mettre nom_francais juste après Species
    cols = list(df.columns)
    cols.remove("nom_francais")
    cols.remove("couleur_hex")
    species_idx = cols.index("Species")
    cols.insert(species_idx + 1, "nom_francais")
    cols.insert(species_idx + 2, "couleur_hex")
    df = df[cols]

    df.to_csv(out_path, index=False, encoding="utf-8")
    log.info(f"✅ Fichier enrichi exporté → {out_path}")
    log.info(f"💾 Cache conservé → {cache_path}")

    # Stats
    n_fr    = df["nom_francais"].notna().sum()
    n_wiki  = (df["couleur_hex"].notna() & ~df["couleur_hex"].isin(FAMILY_COLORS.values()) & (df["couleur_hex"] != DEFAULT_COLOR)).sum()
    n_fam   = df["couleur_hex"].isin(FAMILY_COLORS.values()).sum()
    n_def   = (df["couleur_hex"] == DEFAULT_COLOR).sum()
    log.info(f"Noms français trouvés   : {n_fr:,} / {len(df):,}")
    log.info(f"Couleurs Wikidata        : ~{n_wiki:,}")
    log.info(f"Couleurs par famille     : ~{n_fam:,}")
    log.info(f"Couleur par défaut (gris): {n_def:,}")

    print("\n── Aperçu ──")
    print(df[["Species", "nom_francais", "couleur_hex", "altitude_min_m", "altitude_max_m"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
