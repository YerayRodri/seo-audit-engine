#!/usr/bin/env python3
"""
profiler_csv.py — Analiza un CSV de Screaming Frog y genera la config
necesaria para audit_engine.py:
  - Idioma de SF (es / en / fr / de / ...)
  - Nombres exactos de columnas clave
  - Formato decimal (coma o punto)
  - Escala CTR (0-1 o 0-100)
  - Presencia de columnas opcionales (inlinks, GSC...)
  - Valores únicos de Indexabilidad y Tipo de contenido
  - Estadísticas básicas del crawl

Uso:
  python3 profiler_csv.py /ruta/al/export.csv
  python3 profiler_csv.py /ruta/al/export.csv --json   # emite JSON para audit_engine
"""

import sys
import json
import argparse
import pandas as pd

# ── MAPEO MULTIIDIOMA ─────────────────────────────────────────────────────────
# Cada key es la columna interna normalizada
# El valor es un dict {idioma: nombre_en_sf}

COLUMN_MAP = {
    'url': {
        'es': 'Dirección',
        'en': 'Address',
        'fr': 'Adresse',
        'de': 'Adresse',
        'it': 'Indirizzo',
        'pt': 'Endereço',
    },
    'status': {
        'es': 'Código de respuesta',
        'en': 'Status Code',
        'fr': 'Code de réponse',
        'de': 'Statuscode',
        'it': 'Codice di risposta',
        'pt': 'Código de resposta',
    },
    'content_type': {
        'es': 'Tipo de contenido',
        'en': 'Content Type',
        'fr': 'Type de contenu',
        'de': 'Inhaltstyp',
        'it': 'Tipo di contenuto',
        'pt': 'Tipo de conteúdo',
    },
    'indexable': {
        'es': 'Indexabilidad',
        'en': 'Indexability',
        'fr': 'Indexabilité',
        'de': 'Indexierbarkeit',
        'it': 'Indicizzabilità',
        'pt': 'Indexabilidade',
    },
    'indexability_status': {
        'es': 'Estado de indexabilidad',
        'en': 'Indexability Status',
        'fr': "Statut d'indexabilité",
        'de': 'Indexierbarkeitsstatus',
        'it': 'Stato di indicizzabilità',
        'pt': 'Status de indexabilidade',
    },
    'title': {
        'es': 'Título 1',
        'en': 'Title 1',
        'fr': 'Titre 1',
        'de': 'Titel 1',
        'it': 'Titolo 1',
        'pt': 'Título 1',
    },
    'title_len': {
        'es': 'Longitud del título 1',
        'en': 'Title 1 Length',
        'fr': 'Longueur du titre 1',
        'de': 'Titellänge 1',
        'it': 'Lunghezza titolo 1',
        'pt': 'Comprimento do título 1',
    },
    'meta_desc': {
        'es': 'Meta description 1',
        'en': 'Meta Description 1',
        'fr': 'Meta description 1',
        'de': 'Meta-Beschreibung 1',
        'it': 'Meta descrizione 1',
        'pt': 'Meta descrição 1',
    },
    'meta_desc_len': {
        'es': 'Longitud de la meta description 1',
        'en': 'Meta Description 1 Length',
        'fr': 'Longueur de la meta description 1',
        'de': 'Meta-Beschreibungslänge 1',
        'it': 'Lunghezza meta descrizione 1',
        'pt': 'Comprimento da meta descrição 1',
    },
    'h1': {
        'es': 'H1-1',
        'en': 'H1-1',
        'fr': 'H1-1',
        'de': 'H1-1',
        'it': 'H1-1',
        'pt': 'H1-1',
    },
    'canonical': {
        'es': 'Elemento de enlace canónico 1',
        'en': 'Canonical Link Element 1',
        'fr': 'Lien canonique 1',
        'de': 'Kanonisches Link-Element 1',
        'it': 'Elemento link canonico 1',
        'pt': 'Elemento de link canônico 1',
    },
    'meta_robots': {
        'es': 'Meta robots 1',
        'en': 'Meta Robots 1',
        'fr': 'Meta robots 1',
        'de': 'Meta-Robots 1',
        'it': 'Meta robots 1',
        'pt': 'Meta robots 1',
    },
    'depth': {
        'es': 'Nivel de profundidad',
        'en': 'Crawl Depth',
        'fr': 'Niveau de profondeur',
        'de': 'Crawl-Tiefe',
        'it': 'Livello di profondità',
        'pt': 'Nível de profundidade',
    },
    'word_count': {
        'es': 'Recuento de palabras',
        'en': 'Word Count',
        'fr': 'Nombre de mots',
        'de': 'Wortanzahl',
        'it': 'Conteggio parole',
        'pt': 'Contagem de palavras',
    },
    'internal_links_out': {
        'es': 'Número de enlaces internos salientes',
        'en': 'Outlinks',
        'fr': "Nombre de liens internes sortants",
        'de': 'Anzahl ausgehender interner Links',
        'it': 'Numero di link interni in uscita',
        'pt': 'Número de links internos de saída',
    },
    'inlinks': {
        'es': 'Número de enlaces entrantes únicos',
        'en': 'Unique Inlinks',
        'fr': "Nombre de liens entrants uniques",
        'de': 'Anzahl eindeutiger eingehender Links',
        'it': 'Numero di link in entrata unici',
        'pt': 'Número de links de entrada únicos',
    },
    'clicks': {
        'es': 'Clics',
        'en': 'Clicks',
        'fr': 'Clics',
        'de': 'Klicks',
        'it': 'Clic',
        'pt': 'Cliques',
    },
    'impressions': {
        'es': 'Impresiones',
        'en': 'Impressions',
        'fr': 'Impressions',
        'de': 'Impressionen',
        'it': 'Impressioni',
        'pt': 'Impressões',
    },
    'ctr': {
        'es': 'Porcentaje de clics',
        'en': 'CTR',
        'fr': 'Taux de clics',
        'de': 'CTR',
        'it': 'CTR',
        'pt': 'CTR',
    },
    'position': {
        'es': 'Posición',
        'en': 'Position',
        'fr': 'Position',
        'de': 'Position',
        'it': 'Posizione',
        'pt': 'Posição',
    },
}

# Columnas que determinan el idioma (las más distintivas)
LANG_PROBES = {
    'es': ['Dirección', 'Código de respuesta', 'Indexabilidad'],
    'en': ['Address', 'Status Code', 'Indexability'],
    'fr': ['Adresse', 'Code de réponse', 'Indexabilité'],
    'de': ['Adresse', 'Statuscode', 'Indexierbarkeit'],
    'it': ['Indirizzo', 'Codice di risposta', 'Indicizzabilità'],
    'pt': ['Endereço', 'Código de resposta', 'Indexabilidade'],
}

HTML_HINT = {
    'es': 'text/html',
    'en': 'text/html',
    'fr': 'text/html',
    'de': 'text/html',
    'it': 'text/html',
    'pt': 'text/html',
}


def detect_language(columns: list) -> str:
    """Devuelve el código de idioma con más columnas probe encontradas."""
    col_set = set(columns)
    scores = {}
    for lang, probes in LANG_PROBES.items():
        scores[lang] = sum(1 for p in probes if p in col_set)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return 'unknown'
    return best


def detect_decimal_format(series: pd.Series) -> str:
    """
    Detecta si los valores numéricos usan coma ('1,5') o punto ('1.5') como decimal.
    Retorna 'comma' o 'dot'.
    """
    sample = series.dropna().astype(str).head(200)
    comma_count = sample.str.contains(r'\d,\d').sum()
    dot_count = sample.str.contains(r'\d\.\d').sum()
    return 'comma' if comma_count > dot_count else 'dot'


def detect_ctr_scale(series: pd.Series, decimal_fmt: str) -> str:
    """
    Detecta si CTR está en escala 0-1 (decimal) o 0-100 (porcentaje).
    Retorna '0-1' o '0-100'.
    """
    s = series.dropna().astype(str)
    if decimal_fmt == 'comma':
        s = s.str.replace(',', '.', regex=False)
    vals = pd.to_numeric(s, errors='coerce').dropna()
    if len(vals) == 0:
        return 'unknown'
    median_val = vals.median()
    # Si la mediana es < 1 asumimos escala 0-1 (excepto si es literalmente 0)
    return '0-1' if median_val < 1.0 else '0-100'


def build_rename_map(lang: str, available_cols: list) -> dict:
    """
    Construye el diccionario RENAME {nombre_sf: nombre_interno}
    para las columnas disponibles en el idioma detectado.
    """
    rename = {}
    for internal, translations in COLUMN_MAP.items():
        sf_name = translations.get(lang)
        if sf_name and sf_name in available_cols:
            rename[sf_name] = internal
    return rename


def profile(csv_path: str, emit_json: bool = False):
    print(f"\n{'='*60}")
    print(f"  PROFILER CSV — Screaming Frog")
    print(f"{'='*60}")
    print(f"  Archivo: {csv_path}\n")

    # Carga con low_memory=False para evitar DtypeWarnings
    df = pd.read_csv(csv_path, low_memory=False, encoding='utf-8')
    total_rows = len(df)
    total_cols = len(df.columns)
    cols = list(df.columns)

    # ── 1. IDIOMA ──────────────────────────────────────────────────────────────
    lang = detect_language(cols)
    print(f"[IDIOMA SF]     {lang.upper()}")

    # ── 2. COLUMNAS CLAVE ──────────────────────────────────────────────────────
    rename = build_rename_map(lang, cols)
    print(f"\n[COLUMNAS CLAVE]  ({len(rename)}/{len(COLUMN_MAP)} mapeadas)")
    missing = []
    for internal, translations in COLUMN_MAP.items():
        sf_name = translations.get(lang, '???')
        found = sf_name in cols
        icon = '✓' if found else '✗'
        print(f"  {icon} {internal:25s} ← {sf_name}")
        if not found:
            missing.append(internal)

    # ── 3. FILAS / TIPO DE CONTENIDO ──────────────────────────────────────────
    content_col = COLUMN_MAP['content_type'].get(lang)
    html_rows = 0
    content_values = []
    if content_col and content_col in df.columns:
        html_rows = df[content_col].str.contains('text/html', na=False).sum()
        content_values = df[content_col].dropna().unique().tolist()[:10]
    print(f"\n[FILAS]")
    print(f"  Total:        {total_rows:,}")
    print(f"  HTML (text/html): {html_rows:,}")
    print(f"  Columnas:     {total_cols}")

    # ── 4. DECIMALES Y CTR ────────────────────────────────────────────────────
    pos_col = COLUMN_MAP['position'].get(lang)
    ctr_col = COLUMN_MAP['ctr'].get(lang)

    decimal_fmt = 'unknown'
    ctr_scale = 'unknown'

    if pos_col and pos_col in df.columns:
        decimal_fmt = detect_decimal_format(df[pos_col])

    if ctr_col and ctr_col in df.columns:
        ctr_scale = detect_ctr_scale(df[ctr_col], decimal_fmt)

    print(f"\n[FORMATO NUMÉRICO]")
    print(f"  Decimal:      {decimal_fmt}  {'⚠ usar .str.replace(chr(44),chr(46))' if decimal_fmt == 'comma' else '✓ punto estándar'}")
    print(f"  CTR escala:   {ctr_scale}  {'(ej: 0.015 = 1.5%)' if ctr_scale == '0-1' else '(ej: 1.5 = 1.5%)' if ctr_scale == '0-100' else ''}")

    # ── 5. COLUMNAS OPCIONALES ────────────────────────────────────────────────
    inlinks_col = COLUMN_MAP['inlinks'].get(lang)
    has_inlinks = bool(inlinks_col and inlinks_col in df.columns)
    has_gsc = bool(ctr_col and ctr_col in df.columns)

    print(f"\n[COLUMNAS OPCIONALES]")
    print(f"  Inlinks:      {'✓ presente' if has_inlinks else '✗ ausente — usar export All Inlinks'}")
    print(f"  Datos GSC:    {'✓ presente (CTR/Clics/Impresiones/Posición)' if has_gsc else '✗ ausente — integrar GSC manualmente'}")

    # ── 6. VALORES INDEXABILIDAD ──────────────────────────────────────────────
    idx_col = COLUMN_MAP['indexable'].get(lang)
    idx_status_col = COLUMN_MAP['indexability_status'].get(lang)
    print(f"\n[INDEXABILIDAD]")
    if idx_col and idx_col in df.columns:
        vals = df[idx_col].dropna().unique().tolist()
        print(f"  '{idx_col}' valores: {vals}")
    if idx_status_col and idx_status_col in df.columns:
        vals2 = df[idx_status_col].value_counts().head(10)
        print(f"  '{idx_status_col}' top 10:")
        for v, c in vals2.items():
            print(f"    {c:>6,}  {v}")

    # ── 7. TIPOS DE CONTENIDO ─────────────────────────────────────────────────
    if content_values:
        print(f"\n[TIPOS DE CONTENIDO (muestra)]")
        for v in content_values:
            print(f"  {v}")

    # ── 8. ALERTA COLUMNAS FALTANTES ─────────────────────────────────────────
    if missing:
        print(f"\n[⚠ COLUMNAS NO ENCONTRADAS]")
        for m in missing:
            print(f"  - {m}")
        print("  → Verifica que SF exportó estas columnas o ajusta el COLUMN_MAP")

    # ── 9. JSON OUTPUT para audit_engine ──────────────────────────────────────
    config = {
        'lang': lang,
        'decimal_format': decimal_fmt,
        'decimal_comma': decimal_fmt == 'comma',
        'ctr_scale': ctr_scale,
        'has_inlinks': has_inlinks,
        'has_gsc': has_gsc,
        'rename': rename,
        'missing_columns': missing,
        'total_rows': total_rows,
        'html_rows': html_rows,
    }

    if emit_json:
        print(f"\n{'='*60}")
        print("  CONFIG JSON (para audit_engine.py)")
        print('='*60)
        print(json.dumps(config, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*60}")
        print("  Para emitir JSON config: --json")
        print('='*60)

    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Profila un CSV de Screaming Frog')
    parser.add_argument('csv', help='Ruta al archivo CSV de SF')
    parser.add_argument('--json', action='store_true', help='Emitir config JSON al final')
    args = parser.parse_args()

    profile(args.csv, emit_json=args.json)
