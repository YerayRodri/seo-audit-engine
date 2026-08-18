#!/usr/bin/env python3
"""
audit_engine.py — Motor genérico de auditoría SEO (Screaming Frog + GSC)

Uso:
  python3 audit_engine.py --config config_newcop.py
  python3 audit_engine.py --config config_clienteX.py --csv /otra/ruta.csv
  python3 audit_engine.py --config config_clienteX.py --output-dir /tmp/

Requiere: profiler_csv.py en el mismo directorio
"""

import sys
import re
import argparse
import importlib.util
import warnings
from datetime import datetime

import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

warnings.filterwarnings('ignore', category=UserWarning)


# ──────────────────────────────────────────────────────────────────────────────
# 1. CLI + CONFIG
# ──────────────────────────────────────────────────────────────────────────────

def load_config(config_path):
    spec = importlib.util.spec_from_file_location('cfg', config_path)
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg


# ──────────────────────────────────────────────────────────────────────────────
# MOTOR PRINCIPAL — llamable desde CLI y desde la UI web
# ──────────────────────────────────────────────────────────────────────────────

def run_audit(cfg, ruta_csv, output_path, ruta_links_csv=None):
    """
    Ejecuta la auditoría SEO completa.

    Args:
        cfg             -- módulo/objeto con los atributos de configuración del cliente
        ruta_csv        -- ruta absoluta al export CSV de Screaming Frog (Internal All)
        output_path     -- ruta completa del Excel de salida (.xlsx)
        ruta_links_csv  -- (opcional) ruta al export "All Links" de SF para enriquecer
                           los Excel de T03/T04 con URL origen, texto ancla y tipo enlace

    Returns:
        dict con claves: tasks, urls, gsc, resumen, output_path, dashboard, detail_dfs
    """
    RUTA_CSV   = ruta_csv
    OUTPUT_PATH = output_path
    DOMAIN     = cfg.DOMAIN
    PLATFORM   = getattr(cfg, 'PLATFORM', 'Generic')

    SITE_LANGS      = getattr(cfg, 'SITE_LANGS', [])
    IS_MULTILINGUAL = getattr(cfg, 'IS_MULTILINGUAL', bool(SITE_LANGS))
    SPECIAL_LOCALE  = getattr(cfg, 'SPECIAL_LOCALE', None)

    URL_PATTERNS    = getattr(cfg, 'URL_PATTERNS', [])
    SYSTEM_PATTERNS = getattr(cfg, 'SYSTEM_PATTERNS', [])
    SEO_TYPES       = getattr(cfg, 'SEO_TYPES', ['product', 'blog', 'page'])
    HAS_CART_RECO   = getattr(cfg, 'HAS_CART_RECO', False)

    PAGINATION_PARAMS     = getattr(cfg, 'PAGINATION_PARAMS', ['page'])
    PAGINATION_PATH_REGEX = getattr(cfg, 'PAGINATION_PATH_REGEX', None)

    THRESHOLDS = getattr(cfg, 'THRESHOLDS', {})
    T_IMPRESSIONS_DEMAND   = THRESHOLDS.get('impressions_demand', 200)
    T_INLINKS_LOW          = THRESHOLDS.get('inlinks_low', 2)
    T_CTR_LOW              = THRESHOLDS.get('ctr_low', 0.01)
    T_IMPRESSIONS_MIN_CTR  = THRESHOLDS.get('impressions_min_ctr', 50)
    T_IMPRESSIONS_NO_CLICKS= THRESHOLDS.get('impressions_no_clicks', 500)
    T_POS_OPP_MIN          = THRESHOLDS.get('pos_opportunity_min', 11)
    T_POS_OPP_MAX          = THRESHOLDS.get('pos_opportunity_max', 20)
    T_TITLE_SHORT_CHARS    = THRESHOLDS.get('title_short_chars', 40)
    T_INLINKS_4XX_CRITICAL = THRESHOLDS.get('inlinks_4xx_critical', 500)
    T_WORD_COUNT_THIN      = THRESHOLDS.get('word_count_thin', 150)
    T_ORPHAN_IMPRESSIONS   = THRESHOLDS.get('orphan_impressions', 100)

    HEADER_BG = getattr(cfg, 'HEADER_BG', '1F4E78')
    P0_BG     = getattr(cfg, 'P0_BG', 'FFDCE0')
    P1_BG     = getattr(cfg, 'P1_BG', 'FFF0D3')
    P2_BG     = getattr(cfg, 'P2_BG', 'FFFACC')
    P3_BG     = getattr(cfg, 'P3_BG', 'E8F5E9')
    ALT_ROW   = getattr(cfg, 'ALT_ROW', 'F5F8FC')
    WHITE     = 'FFFFFF'

    print(f"=== AUDIT ENGINE ===")
    print(f"CSV     : {RUTA_CSV}")
    print(f"Output  : {OUTPUT_PATH}")
    print(f"Platform: {PLATFORM}")



    try:
        import profiler_csv   # noqa: E402  (same directory, dev only)
        print("\nProfiling CSV...")
        pf = profiler_csv.profile(RUTA_CSV, emit_json=False)
    except ModuleNotFoundError:
        pf = {'rename': {}, 'decimal_comma': False, 'has_gsc': False, 'lang': 'en', 'ctr_scale': '0-1'}

    RENAME       = pf['rename']
    DECIMAL_COMMA = pf['decimal_comma']
    HAS_GSC      = pf['has_gsc']
    SF_LANG      = pf['lang']

    print(f"\nLoading CSV ({RUTA_CSV.split('/')[-1]})...")
    df_raw = pd.read_csv(RUTA_CSV, low_memory=False, encoding='utf-8-sig', on_bad_lines='warn')
    # Limpiar BOM y espacios en nombres de columna
    df_raw.columns = [c.strip().lstrip('\ufeff') for c in df_raw.columns]
    df_raw.rename(columns=RENAME, inplace=True)

    # Normalización de columnas Screaming Frog (fallback cuando profiler_csv no aplica)
    SF_COL_MAP = {
        # ── Inglés (SF en inglés) ─────────────────────────────────────────────
        'Address': 'url',
        'Status Code': 'status',
        'Indexability': 'indexable',
        'Title 1': 'title',
        'Title 1 Length': 'title_len',
        'Title 1 Pixel Width': 'title_pixel_width',
        'Meta Description 1': 'meta_desc',
        'Meta Description 1 Length': 'meta_desc_len',
        'Meta Description 1 Pixel Width': 'meta_desc_pixel_width',
        'H1-1': 'h1',
        'H2-1': 'h2',
        'Canonical Link Element 1': 'canonical',
        'Meta Robots 1': 'meta_robots',
        'Crawl Depth': 'depth',
        'Inlinks': 'inlinks',
        'Unique Inlinks': 'unique_inlinks',
        'Is In Sitemap': 'in_sitemap',
        'Content Type': 'content_type',
        'Word Count': 'word_count',
        'Size (bytes)': 'size',
        'Response Time': 'response_time',
        'Indexability Status': 'indexability_status',
        'Structured Data': 'structured_data',
        'Redirect URL': 'redirect_url',
        'Nearest Similarity Match': 'similarity',
        # ── Español (SF en español) ───────────────────────────────────────────
        'Dirección': 'url',
        'Código de respuesta': 'status',
        'Indexabilidad': 'indexable',
        'Estado de indexabilidad': 'indexability_status',
        'Tipo de contenido': 'content_type',
        'Título 1': 'title',
        'Longitud del título 1': 'title_len',
        'Ancho de píxeles del título 1': 'title_pixel_width',
        'Meta description 1': 'meta_desc',
        'Longitud de la meta description 1': 'meta_desc_len',
        'Ancho de píxeles de la meta description 1': 'meta_desc_pixel_width',
        'Meta robots 1': 'meta_robots',
        'Elemento de enlace canónico 1': 'canonical',
        'Nivel de profundidad': 'depth',
        'Enlaces internos': 'inlinks',
        'Enlaces internos únicos': 'unique_inlinks',
        'En el mapa del sitio': 'in_sitemap',
        'Recuento de palabras': 'word_count',
        'Tamaño (bytes)': 'size',
        'Tiempo de respuesta': 'response_time',
        'Datos estructurados': 'structured_data',
        'URL de redirección': 'redirect_url',
        'Coincidencia de similitud más cercana': 'similarity',
        # GSC en español
        'Clics': 'clicks',
        'Impresiones': 'impressions',
        'Porcentaje de clics': 'ctr',
        'Posición': 'position',
        # ── Francés (SF en francés) ───────────────────────────────────────────
        'Adresse': 'url',
        'Code de réponse': 'status',
        'Indexabilité': 'indexable',
        "État d'indexabilité": 'indexability_status',
        'Type de contenu': 'content_type',
        'Titre 1': 'title',
        'Longueur du titre 1': 'title_len',
        'Largeur en pixels du titre 1': 'title_pixel_width',
        'Longueur de la méta description 1': 'meta_desc_len',
        'Largeur en pixels de la méta description 1': 'meta_desc_pixel_width',
        'Élément de lien canonique 1': 'canonical',
        "Profondeur d'exploration": 'depth',
        'Liens entrants': 'inlinks',
        'Liens entrants uniques': 'unique_inlinks',
        'Dans le plan du site': 'in_sitemap',
        'Nombre de mots': 'word_count',
        'Taille (octets)': 'size',
        'Temps de réponse': 'response_time',
        'Données structurées': 'structured_data',
        'URL de redirection': 'redirect_url',
        'Correspondance de similarité la plus proche': 'similarity',
        # GSC en francés
        'Impressions': 'impressions',
        'CTR': 'ctr',
        'Position': 'position',
        # ── Columnas adicionales (mismo nombre en EN/ES salvo indicado) ────────
        'X-Robots-Tag 1': 'x_robots',
        'Meta Refresh 1': 'meta_refresh',
        'H1-2': 'h1_2',
        'H2-2': 'h2_2',
        'Link Score': 'link_score',
        'Hash': 'hash',
        'HTTP Version': 'http_version',
        'Versión HTTP': 'http_version',
        'Redirect Type': 'redirect_type',
        'Tipo de redirección': 'redirect_type',
        'Type de redirection': 'redirect_type',
        'Folder Depth': 'folder_depth',
        'Profundidad de carpeta': 'folder_depth',
        'Text Ratio': 'text_ratio',
        'Proporción de texto': 'text_ratio',
        'Outlinks': 'outlinks',
        'Enlaces salientes': 'outlinks',
        'External Outlinks': 'external_outlinks',
        'Enlaces salientes externos': 'external_outlinks',
        'No. Near Duplicates': 'near_duplicates',
        'Semiduplicados (N.º)': 'near_duplicates',
        'Meta Keywords 1': 'meta_keywords',
    }
    sf_rename = {k: v for k, v in SF_COL_MAP.items() if k in df_raw.columns and v not in df_raw.columns}
    if sf_rename:
        df_raw.rename(columns=sf_rename, inplace=True)
        print(f"  SF columns normalized: {list(sf_rename.keys())}")

    # Guard: columna status imprescindible
    if 'status' not in df_raw.columns:
        _cols_sample = list(df_raw.columns[:10])
        raise ValueError(
            f"No se encontró la columna 'Status Code' en el CSV. "
            f"El CSV parece estar en un idioma no soportado todavía. "
            f"Primeras columnas detectadas: {_cols_sample}. "
            f"Contacta con soporte indicando estos nombres de columna."
        )

    # Auto-detectar GSC (cuando profiler_csv no está disponible, e.g. cloud)
    if not HAS_GSC:
        HAS_GSC = (
            'impressions' in df_raw.columns and
            pd.to_numeric(df_raw['impressions'], errors='coerce').fillna(0).sum() > 0
        )
        if HAS_GSC:
            print("  GSC data auto-detected from columns")

    # Normalizar decimales antes de coerción numérica
    DECIMAL_FIX_COLS = ['ctr', 'position', 'response_time']
    if DECIMAL_COMMA:
        for col in DECIMAL_FIX_COLS:
            if col in df_raw.columns:
                df_raw[col] = df_raw[col].astype(str).str.replace(',', '.', regex=False)

    # Preservar nulos de depth antes del fillna (para detección de huérfanas)
    if 'depth' in df_raw.columns:
        df_raw['_depth_was_null'] = pd.to_numeric(df_raw['depth'], errors='coerce').isna()

    NUM_COLS = ['status', 'inlinks', 'depth', 'word_count', 'size',
                'response_time', 'impressions', 'clicks', 'ctr', 'position', 'title_len',
                'link_score', 'folder_depth', 'outlinks', 'external_outlinks', 'near_duplicates']
    for col in NUM_COLS:
        if col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0)

    # Normalizar CTR 0-100 → 0-1 (auto-detect escala)
    if HAS_GSC and 'ctr' in df_raw.columns:
        _ctr_num = pd.to_numeric(df_raw['ctr'], errors='coerce').fillna(0)
        if _ctr_num.max() > 1:
            df_raw['ctr'] = _ctr_num / 100
            print("  CTR normalizado de escala 0-100 a 0-1")

    # Filtrar HTML
    if 'content_type' in df_raw.columns:
        df = df_raw[df_raw['content_type'].astype(str).str.contains('text/html', na=False)].copy()
    else:
        df = df_raw.copy()

    # Verificar inlinks con datos reales
    HAS_INLINKS_DATA = 'inlinks' in df.columns and df['inlinks'].sum() > 0

    # Señales adicionales de SF — cada una condiciona sus propios checks.
    # Link Score solo se rellena si se ejecutó Crawl Analysis en SF.
    HAS_LINK_SCORE   = 'link_score' in df.columns and df['link_score'].sum() > 0
    HAS_XROBOTS      = 'x_robots' in df.columns
    HAS_META_REFRESH = 'meta_refresh' in df.columns
    HAS_H1_2         = 'h1_2' in df.columns
    HAS_HASH         = 'hash' in df.columns and df['hash'].notna().sum() > 0

    print(f"  Filas raw: {len(df_raw):,} → HTML: {len(df):,}")
    print(f"  GSC: {HAS_GSC} | Inlinks: {HAS_INLINKS_DATA}")

    # ── All Links CSV (opcional — enriquece T03/T04 con origen del enlace) ────────
    HAS_LINKS = False
    HAS_FOLLOW_DATA = False
    HAS_LINK_POSITION = False
    _df_links = None
    if ruta_links_csv:
        try:
            for _enc in ('utf-8', 'latin-1', 'utf-8-sig'):
                try:
                    _links_raw = pd.read_csv(ruta_links_csv, encoding=_enc, low_memory=False, dtype=str, on_bad_lines='warn')
                    break
                except UnicodeDecodeError:
                    continue
            _links_raw.columns = [c.strip().lower().replace(' ', '_') for c in _links_raw.columns]
            print(f"  All Links CSV columnas detectadas: {list(_links_raw.columns[:8])}")
            # Nombres en inglés Y español (SF exporta según idioma de la app)
            _lsrc = next((c for c in _links_raw.columns if c in (
                'source', 'source_url', 'from', 'from_url',
                'fuente', 'origen', 'url_origen', 'desde')), None)
            _ldst = next((c for c in _links_raw.columns if c in (
                'destination', 'destination_url', 'to', 'to_url', 'href',
                'destino', 'url_destino', 'hasta')), None)
            _lanc = next((c for c in _links_raw.columns if c in (
                'anchor', 'anchor_text', 'link_text', 'text',
                'texto_ancla', 'ancla', 'texto_de_ancla', 'texto_anclaje')), None)
            _lalt = next((c for c in _links_raw.columns if c in (
                'alt_text', 'alt', 'image_alt', 'alternative_text',
                'texto_alternativo', 'alt_texto', 'texto_alt')), None)
            _ltyp = next((c for c in _links_raw.columns if c in (
                'type', 'link_type', 'tipo', 'tipo_enlace')), None)
            _ltag = next((c for c in _links_raw.columns if c in (
                'tag', 'element', 'html_tag', 'etiqueta')), None)
            # Follow / nofollow del enlace (SF: "Follow" / "Seguir")
            _lfol = next((c for c in _links_raw.columns if c in (
                'follow', 'seguir', 'suivre')), None)
            # Posición del enlace en el HTML (SF: "Link Position" / "Posición del enlace")
            _lpos = next((c for c in _links_raw.columns if c in (
                'link_position', 'posición_del_enlace', 'posicion_del_enlace',
                'position_du_lien')), None)
            _lrel = next((c for c in _links_raw.columns if c in ('rel', 'atributo_rel')), None)
            print(f"  All Links columnas mapeadas → src:{_lsrc} dst:{_ldst} anc:{_lanc} typ:{_ltyp} "
                  f"follow:{_lfol} pos:{_lpos}")
            if _lsrc and _ldst:
                _rename_l = {_lsrc: 'link_source', _ldst: 'link_dest'}
                if _lanc: _rename_l[_lanc] = 'anchor'
                if _lalt: _rename_l[_lalt] = 'alt_text'
                if _ltyp: _rename_l[_ltyp] = 'link_type'
                if _ltag: _rename_l[_ltag] = 'link_tag'
                if _lfol: _rename_l[_lfol] = 'follow'
                if _lpos: _rename_l[_lpos] = 'link_position'
                if _lrel: _rename_l[_lrel] = 'link_rel'
                _df_links = _links_raw.rename(columns=_rename_l).copy()
                # Normalizar URLs (quitar trailing slash para matching consistente)
                _df_links['link_source'] = _df_links['link_source'].astype(str).str.strip().str.rstrip('/')
                _df_links['link_dest']   = _df_links['link_dest'].astype(str).str.strip().str.rstrip('/')
                # Filtrar a enlaces reales (excluir canonical, hreflang, etc.)
                if 'link_type' in _df_links.columns:
                    _keep = _df_links['link_type'].str.lower().str.strip().isin([
                        'href', 'img', 'image', 'src',
                        'hyperlink', 'enlace', 'imagen',
                        'hipervínculo', 'hipervinculo',
                    ])
                    _df_links = _df_links[_keep].copy()
                # Detectar imagen (vectorizado)
                _img_mask = pd.Series(False, index=_df_links.index)
                if 'link_type' in _df_links.columns:
                    _img_mask |= _df_links['link_type'].str.lower().str.strip().isin(['img', 'image', 'src', 'imagen'])
                if 'link_tag' in _df_links.columns:
                    _img_mask |= _df_links['link_tag'].str.lower().str.strip() == 'img'
                if 'alt_text' in _df_links.columns:
                    _img_mask |= (
                        _df_links['alt_text'].notna() &
                        (_df_links['alt_text'].astype(str).str.strip() != '') &
                        (_df_links['alt_text'].astype(str).str.lower() != 'nan')
                    )
                _df_links['es_imagen'] = _img_mask
                # Follow real del enlace — SF exporta True/False (o Verdadero/Falso)
                if 'follow' in _df_links.columns:
                    _df_links['es_follow'] = ~_df_links['follow'].astype(str).str.strip().str.lower().isin(
                        ['false', 'falso', 'faux', 'no', '0', 'nofollow'])
                # Posición del enlace: solo "Contenido" transmite autoridad editorial;
                # header/footer/nav/head/aside son boilerplate repetido en todo el site.
                if 'link_position' in _df_links.columns:
                    _pos_norm = _df_links['link_position'].astype(str).str.strip().str.lower()
                    _df_links['es_contextual'] = _pos_norm.isin(['content', 'contenido', 'contenu'])
                HAS_FOLLOW_DATA   = 'es_follow' in _df_links.columns
                HAS_LINK_POSITION = 'es_contextual' in _df_links.columns
                HAS_LINKS = True
                print(f"  All Links CSV cargado: {len(_df_links):,} enlaces "
                      f"(follow:{HAS_FOLLOW_DATA} posición:{HAS_LINK_POSITION})")
            else:
                print(f"  All Links CSV: no se encontraron columnas source/destination. Columnas disponibles: {list(_links_raw.columns)}")
        except Exception as _links_err:
            print(f"  Warning: All Links CSV no cargado: {_links_err}")

    # ──────────────────────────────────────────────────────────────────────────────
    # 3. CLASIFICACIÓN DE URLs
    # ──────────────────────────────────────────────────────────────────────────────

    def extract_lang(url):
        """Detecta el subdirectorio de idioma de la URL."""
        if not SITE_LANGS or not isinstance(url, str):
            return 'root'
        for lang in SITE_LANGS:
            if f'/{lang}/' in url or url.rstrip('/').endswith(f'/{lang}'):
                return lang
        return 'root'


    def url_type(url):
        """Clasifica la URL según los patrones del config. First match wins."""
        if not isinstance(url, str):
            return 'other'

        # Extraer path (sin dominio ni query string)
        raw = url.replace('https://', '').replace('http://', '').split('?')[0]
        parts = raw.split('/', 1)
        path = '/' + (parts[1] if len(parts) > 1 else '')

        # Homepage
        if path in ('/', '') or re.fullmatch(r'/+', path):
            return 'homepage'

        # Sistema
        for sp in SYSTEM_PATTERNS:
            if sp in path:
                return 'system'

        # Patrones en orden (first match wins)
        for pattern, ptype in URL_PATTERNS:
            if pattern in path:
                return ptype

        return 'other'


    def is_pagination(url):
        """Detecta paginación por query param o segmento de ruta."""
        if not isinstance(url, str):
            return False
        u = url.lower()
        for param in PAGINATION_PARAMS:
            if f'{param}=' in u or f'/{param}/' in u:
                return True
        if PAGINATION_PATH_REGEX and re.search(PAGINATION_PATH_REGEX, u):
            return True
        return False


    def has_double_slash(url):
        """Detecta // en la ruta (excluye el protocolo)."""
        if not isinstance(url, str):
            return False
        path_part = url.split('://', 1)[-1]
        return '//' in path_part


    df['lang_dir']       = df['url'].apply(extract_lang)
    df['url_type']       = df['url'].apply(url_type)
    df['is_pagination']  = df['url'].apply(is_pagination)
    df['has_double_slash'] = df['url'].apply(has_double_slash)

    print(f"\nURL types: {df['url_type'].value_counts().to_dict()}")


    # ──────────────────────────────────────────────────────────────────────────────
    # 4. INDEXABILIDAD
    # ──────────────────────────────────────────────────────────────────────────────

    # Valores "indexable" positivos por idioma SF
    INDEXABLE_VALUE = {
        'es': 'Indexable', 'en': 'Indexable', 'fr': 'Indexable',
        'de': 'Indexierbar', 'it': 'Indicizzabile', 'pt': 'Indexável',
    }
    idx_pos_val = INDEXABLE_VALUE.get(SF_LANG, 'Indexable')

    if 'indexable' in df.columns:
        df_indexable    = df[df['indexable'].astype(str).str.strip() == idx_pos_val]
        df_no_indexable = df[df['indexable'].astype(str).str.strip() != idx_pos_val]
    else:
        df_indexable    = df[df['status'] == 200]
        df_no_indexable = df[df['status'] != 200]

    total_indexable    = len(df_indexable)
    total_no_indexable = len(df_no_indexable)
    print(f"  Indexable: {total_indexable:,}  /  No indexable: {total_no_indexable:,}")


    # ──────────────────────────────────────────────────────────────────────────────
    # 5. MÉTRICAS
    # ──────────────────────────────────────────────────────────────────────────────
    print("\nCalculando métricas...")

    # Status
    total_html      = len(df)
    status_200      = int((df['status'] == 200).sum())
    status_0        = int((df['status'] == 0).sum())
    status_301_count= int((df['status'] == 301).sum())
    status_404_count= int((df['status'] == 404).sum())
    status_5xx_count= int((df['status'] >= 500).sum())

    # Razones no-indexabilidad
    if 'indexability_status' in df.columns:
        # astype(str): si todas las URLs son indexables la columna llega vacía y
        # pandas la infiere como float → el accesor .str reventaría.
        idx_status = df['indexability_status'].astype(str).value_counts()
        idx_status.index = idx_status.index.astype(str)
        total_blocked_robots = int(idx_status[idx_status.index.str.contains('robots', case=False, na=False)].sum())
        total_canonicalized  = int(idx_status[idx_status.index.str.contains('Canoni', case=False, na=False)].sum())
        total_redirects_idx  = int(idx_status[idx_status.index.str.contains('[Rr]edir', na=False)].sum())
    else:
        total_blocked_robots = total_canonicalized = total_redirects_idx = 0

    # Error sets
    df_503 = df[df['status'] == 503]
    df_5xx = df[df['status'] >= 500]
    df_4xx = df[(df['status'] >= 400) & (df['status'] < 500)]
    df_404 = df[df['status'] == 404]
    df_301 = df[df['status'] == 301]

    # Double slash (todas las HTML, no solo indexables)
    df_double_slash_all       = df[df['has_double_slash']]
    df_double_slash_indexable = df_indexable[df_indexable['has_double_slash']]
    n_ds = len(df_double_slash_all)

    # Paginaciones
    df_paginaciones          = df[df['is_pagination']]
    df_paginaciones_indexable = df_indexable[df_indexable['is_pagination']]
    n_pag_total  = len(df_paginaciones)
    n_pag_index  = len(df_paginaciones_indexable)

    # Cart-reco (auto-detect aunque HAS_CART_RECO=False)
    _mask_cart = (
        (df_indexable['url_type'] == 'cart_reco') |
        (df_indexable['url'].str.contains('cart-recommendations', case=False, na=False))
    )
    df_cart_reco_indexable = df_indexable[_mask_cart]
    if not HAS_CART_RECO and len(df_cart_reco_indexable) > 0:
        HAS_CART_RECO = True  # auto-detectado

    # Locale especial (ej: /ca/)
    if SPECIAL_LOCALE:
        df_ca   = df[df['lang_dir'] == SPECIAL_LOCALE]
        ca_url_count = len(df_ca)
        if 'indexability_status' in df.columns:
            df_ca_blocked = df_ca[df_ca['indexability_status'].astype(str).str.contains('robots', case=False, na=False)]
        else:
            df_ca_blocked = pd.DataFrame(columns=df.columns)
    else:
        df_ca        = pd.DataFrame(columns=df.columns)
        df_ca_blocked = pd.DataFrame(columns=df.columns)
        ca_url_count = 0

    # Breakdown por idioma
    lang_indexable      = {}
    langs_with_indexable = []
    for lang in SITE_LANGS:
        n = len(df_indexable[df_indexable['lang_dir'] == lang])
        lang_indexable[lang] = n
        if n > 0:
            langs_with_indexable.append(lang)
    lang_indexable['root'] = len(df_indexable[df_indexable['lang_dir'] == 'root'])

    # On-page (páginas SEO)
    df_seo = df_indexable[df_indexable['url_type'].isin(SEO_TYPES)]

    meta_col = 'meta_desc'
    if meta_col in df.columns:
        df_no_meta = df_seo[df_seo[meta_col].isna() | (df_seo[meta_col].astype(str).str.strip() == '')]
        n_no_meta_products    = len(df_no_meta[df_no_meta['url_type'] == 'product'])
        n_no_meta_collections = len(df_no_meta[df_no_meta['url_type'].isin(['collection', 'collections_root'])])
        n_no_meta_pages       = len(df_no_meta[df_no_meta['url_type'].isin(['page', 'blog'])])
    else:
        df_no_meta = pd.DataFrame(columns=df.columns)
        n_no_meta_products = n_no_meta_collections = n_no_meta_pages = 0
    n_no_meta = len(df_no_meta)

    h1_col = 'h1'
    if h1_col in df.columns:
        df_no_h1     = df_seo[df_seo[h1_col].isna() | (df_seo[h1_col].astype(str).str.strip() == '')]
        n_no_h1_info = len(df_no_h1[df_no_h1['url_type'].isin(['page', 'blog'])])
    else:
        df_no_h1     = pd.DataFrame(columns=df.columns)
        n_no_h1_info = 0
    n_no_h1 = len(df_no_h1)

    # Titles cortos en colecciones/categorías
    df_seo_collections = df_seo[df_seo['url_type'].isin(['collection', 'collections_root'])]
    if 'title_len' in df.columns:
        df_short_title = df_seo_collections[df_seo_collections['title_len'] < T_TITLE_SHORT_CHARS]
    elif 'title' in df.columns:
        df_short_title = df_seo_collections[df_seo_collections['title'].astype(str).str.len() < T_TITLE_SHORT_CHARS]
    else:
        df_short_title = pd.DataFrame(columns=df.columns)
    n_short_title = len(df_short_title)

    # GSC
    if HAS_GSC:
        df_gsc = df[df['impressions'] > 0]
        total_impressions = int(df_gsc['impressions'].sum())
        total_clicks      = int(df_gsc['clicks'].sum())
        overall_ctr       = total_clicks / total_impressions if total_impressions > 0 else 0

        df_pos_11_20 = df_indexable[
            (df_indexable['position'] >= T_POS_OPP_MIN) &
            (df_indexable['position'] <= T_POS_OPP_MAX) &
            (df_indexable['impressions'] > 0)
        ]
        df_low_ctr = df_indexable[
            (df_indexable['ctr'] < T_CTR_LOW) &
            (df_indexable['impressions'] >= T_IMPRESSIONS_MIN_CTR) &
            (df_indexable['position'] <= 10) &
            (df_indexable['position'] > 0)
        ]
        df_impr_no_clicks = df_indexable[
            (df_indexable['impressions'] >= T_IMPRESSIONS_NO_CLICKS) &
            (df_indexable['clicks'] == 0)
        ]
        if HAS_INLINKS_DATA:
            df_seo_demand = df_indexable[
                (df_indexable['impressions'] >= T_IMPRESSIONS_DEMAND) &
                (df_indexable['inlinks'] <= T_INLINKS_LOW) &
                (df_indexable['url_type'].isin(SEO_TYPES))
            ]
        else:
            df_seo_demand = df_indexable[
                (df_indexable['impressions'] >= T_IMPRESSIONS_DEMAND) &
                (df_indexable['url_type'].isin(SEO_TYPES))
            ]
        n_demand = len(df_seo_demand)
    else:
        df_gsc = df_pos_11_20 = df_low_ctr = df_impr_no_clicks = df_seo_demand = pd.DataFrame(columns=df.columns)
        total_impressions = total_clicks = n_demand = 0
        overall_ctr = 0.0

    print(f"  Métricas calculadas. Demand: {n_demand} | Pos11-20: {len(df_pos_11_20)} | Low CTR: {len(df_low_ctr)}")

    # ── Métricas adicionales ────────────────────────────────────────────────────

    # Redirects 302 (temporales)
    df_302 = df[df['status'] == 302]

    # URLs sensibles indexables (cart, checkout, login, search…)
    _SENSITIVE = [
        '/cart', '/checkout', '/login', '/account/', '/register',
        '/buscar', '/search?', '/cesta', '/carrito', '?q=', '?s=',
        '/wishlist', '/mi-cuenta', '/my-account', '/basket',
        '/carro', '/pedido', '/factura',
    ]
    _mask_sensitive = df_indexable['url'].apply(
        lambda u: any(p in u.lower() for p in _SENSITIVE) if isinstance(u, str) else False
    )
    df_sensitive = df_indexable[_mask_sensitive]

    # Facetas/filtros indexables
    FACET_URL_PATTERNS = getattr(cfg, 'FACET_URL_PATTERNS', [])
    _default_facet_regex = (
        r'-[\d]+-f\b|[?&](filtro|filter|color|colour|marca|brand|precio|price'
        r'|sort|order|talla|size|genero|gender|material|acabado|finish)[=]'
    )
    _extra_facets = '|'.join([re.escape(p) for p in FACET_URL_PATTERNS]) if FACET_URL_PATTERNS else ''
    _facet_combined = _default_facet_regex + ('|' + _extra_facets if _extra_facets else '')
    _mask_facets = df_indexable['url'].apply(
        lambda u: bool(re.search(_facet_combined, u, re.I)) if isinstance(u, str) else False
    )
    df_facets = df_indexable[_mask_facets]

    # Canonical a URL diferente (non-self canonical en páginas indexables)
    if 'canonical' in df.columns:
        _mask_non_self_can = (
            df_indexable['canonical'].notna() &
            (df_indexable['canonical'].astype(str).str.strip() != '') &
            (
                df_indexable['canonical'].astype(str).str.strip()
                != df_indexable['url'].astype(str).str.strip()
            )
        )
        df_non_self_canonical = df_indexable[_mask_non_self_can]
    else:
        df_non_self_canonical = pd.DataFrame(columns=df.columns)

    # Thin content (páginas SEO con word_count muy bajo)
    if 'word_count' in df.columns:
        df_thin = df_indexable[
            (df_indexable['url_type'].isin(SEO_TYPES)) &
            (df_indexable['word_count'] > 0) &
            (df_indexable['word_count'] < T_WORD_COUNT_THIN)
        ]
    else:
        df_thin = pd.DataFrame(columns=df.columns)

    # Huérfanas: HTML+200+indexable sin inlinks internos O sin profundidad de crawl
    # Señal 1: inlinks=0 — ninguna página enlaza a esta URL
    # Señal 2: depth=NaN — solo encontrada via sitemap, sin path de enlace desde home
    _html_mask = (
        df_indexable['content_type'].str.lower().str.contains('html', na=False)
        if 'content_type' in df_indexable.columns
        else pd.Series(True, index=df_indexable.index)
    )
    _base_200_html = df_indexable[_html_mask & (df_indexable['status'] == 200)]
    _orphan_inlinks = (
        _base_200_html[_base_200_html['inlinks'] == 0]
        if HAS_INLINKS_DATA
        else pd.DataFrame(columns=df.columns)
    )
    # Señal depth original=NaN (páginas sin camino de enlaces desde la home)
    # _depth_was_null preserva los nulos antes del fillna(0) aplicado en NUM_COLS
    HAS_DEPTH_FOR_ORPHANS = '_depth_was_null' in _base_200_html.columns
    if HAS_DEPTH_FOR_ORPHANS:
        _orphan_depth = _base_200_html[_base_200_html['_depth_was_null'] == True]
        _orphan_base = pd.concat([_orphan_inlinks, _orphan_depth]).drop_duplicates(subset='url')
    else:
        _orphan_base = _orphan_inlinks
    if HAS_GSC and 'impressions' in _orphan_base.columns and len(_orphan_base) > 0:
        df_orphans = _orphan_base[_orphan_base['impressions'] > T_ORPHAN_IMPRESSIONS]
    else:
        df_orphans = _orphan_base

    print(f"  302: {len(df_302)} | Sensibles: {len(df_sensitive)} | Facetas: {len(df_facets)}")
    print(f"  Non-self canonical: {len(df_non_self_canonical)} | Thin: {len(df_thin)} | Huérfanas: {len(df_orphans)}")

    # ─── PRE-CÓMPUTOS T21–T29 ──────────────────────────────────────────────────

    # Flags de disponibilidad de columnas
    HAS_SITEMAP_DATA   = 'in_sitemap' in df.columns
    HAS_RESPONSE_TIME  = 'response_time' in df.columns
    HAS_TITLE_1        = 'title_1' in df.columns
    HAS_TITLE_LEN      = 'title_1_length' in df.columns
    HAS_CANONICAL_COL  = 'canonical_link_element_1' in df.columns

    # T21 — URLs no-indexables incluidas en el sitemap
    if HAS_SITEMAP_DATA and 'indexable' in df.columns:
        _mask_noindex_sitemap = (
            (df['in_sitemap'] == True) &
            (df['indexable'].astype(str).str.strip() != idx_pos_val)
        )
        df_noindex_in_sitemap = df[_mask_noindex_sitemap].copy()
    elif HAS_SITEMAP_DATA:
        df_noindex_in_sitemap = df[(df['in_sitemap'] == True) & (df['status'] != 200)].copy()
    else:
        df_noindex_in_sitemap = pd.DataFrame(columns=df.columns)

    # T22 — URLs indexables ausentes del sitemap
    if HAS_SITEMAP_DATA and 'indexable' in df.columns:
        _mask_missing_sitemap = (
            (df['in_sitemap'] == False) &
            (df['indexable'].astype(str).str.strip() == idx_pos_val) &
            (df['status'] == 200)
        )
        df_missing_from_sitemap = df[_mask_missing_sitemap].copy()
    elif HAS_SITEMAP_DATA:
        df_missing_from_sitemap = df[(df['in_sitemap'] == False) & (df['status'] == 200)].copy()
    else:
        df_missing_from_sitemap = pd.DataFrame(columns=df.columns)

    # T23 — Páginas con tiempo de respuesta >3 s (solo HTML indexables 200)
    T_SLOW_RESPONSE = 3.0
    if HAS_RESPONSE_TIME:
        df_slow = df_indexable[
            (df_indexable['response_time'] > T_SLOW_RESPONSE) &
            (df_indexable['status'] == 200)
        ].copy()
    else:
        df_slow = pd.DataFrame(columns=df.columns)

    # T24 — URLs con parámetros indexables
    df_parametered = df_indexable[
        df_indexable['url'].str.contains(r'\?', na=False)
    ].copy()

    # T25 — URLs largas (>115 caracteres) indexables
    T_URL_MAX_LEN = 115
    df_long_urls = df_indexable[
        df_indexable['url'].str.len() > T_URL_MAX_LEN
    ].copy()

    # T26 — Titles duplicados entre páginas indexables
    if HAS_TITLE_1:
        _titles_ser = df_indexable['title_1'].dropna()
        _titles_ser = _titles_ser[_titles_ser.str.strip() != '']
        _dup_titles = _titles_ser[_titles_ser.duplicated(keep=False)]
        df_dup_titles = df_indexable[
            df_indexable.index.isin(_dup_titles.index)
        ].copy()
        n_unique_dup_titles = int(df_indexable.loc[
            df_indexable.index.isin(_dup_titles.index), 'title_1'
        ].nunique())
    else:
        df_dup_titles = pd.DataFrame(columns=df.columns)
        n_unique_dup_titles = 0

    # T27 — Páginas noindex con impresiones en GSC
    if HAS_GSC and 'indexable' in df.columns:
        df_noindex_with_gsc = df[
            (df['indexable'].astype(str).str.strip() != idx_pos_val) &
            (df['impressions'] > 0)
        ].copy()
    elif HAS_GSC:
        df_noindex_with_gsc = df[
            (df['status'] != 200) &
            (df['impressions'] > 0)
        ].copy()
    else:
        df_noindex_with_gsc = pd.DataFrame(columns=df.columns)

    # T28 — Titles largos (>60 chars) en páginas indexables
    if HAS_TITLE_LEN:
        df_long_titles = df_indexable[
            df_indexable['title_1_length'] > 60
        ].copy()
    else:
        df_long_titles = pd.DataFrame(columns=df.columns)

    # T29 — Canonical ausente en páginas 200 indexables
    if HAS_CANONICAL_COL:
        df_no_canonical = df_indexable[
            (df_indexable['status'] == 200) &
            (
                df_indexable['canonical_link_element_1'].isna() |
                (df_indexable['canonical_link_element_1'].astype(str).str.strip() == '')
            )
        ].copy()
    else:
        df_no_canonical = pd.DataFrame(columns=df.columns)

    print(f"  Noindex en sitemap: {len(df_noindex_in_sitemap)} | Faltan en sitemap: {len(df_missing_from_sitemap)}")
    print(f"  Lentas >3s: {len(df_slow)} | Parámetros: {len(df_parametered)} | URLs largas: {len(df_long_urls)}")
    print(f"  Titles dup: {len(df_dup_titles)} | Noindex+GSC: {len(df_noindex_with_gsc)} | Sin canonical: {len(df_no_canonical)}")

    # T30 — Sin H2 en páginas indexables SEO
    HAS_H2_COL = 'h2_1' in df.columns
    if HAS_H2_COL:
        df_no_h2 = df_indexable[
            (df_indexable['url_type'].isin(SEO_TYPES)) &
            (
                df_indexable['h2_1'].isna() |
                (df_indexable['h2_1'].astype(str).str.strip() == '')
            )
        ].copy()
    else:
        df_no_h2 = pd.DataFrame(columns=df.columns)

    # T31 — Title = H1 exacto (páginas indexables)
    HAS_H1_COL   = 'h1_1' in df.columns
    if HAS_TITLE_1 and HAS_H1_COL:
        _t1 = df_indexable['title_1'].fillna('').astype(str).str.strip().str.lower()
        _h1 = df_indexable['h1_1'].fillna('').astype(str).str.strip().str.lower()
        df_title_eq_h1 = df_indexable[
            (_t1 != '') & (_h1 != '') & (_t1 == _h1)
        ].copy()
    else:
        df_title_eq_h1 = pd.DataFrame(columns=df.columns)

    # T32 — Crawl depth alto (>4 clicks desde home) en páginas indexables con tráfico
    HAS_DEPTH_COL = 'depth' in df.columns
    T_MAX_DEPTH   = 4
    if HAS_DEPTH_COL:
        _deep_base = df_indexable[df_indexable['depth'] > T_MAX_DEPTH]
        if HAS_GSC and 'impressions' in _deep_base.columns:
            df_deep = _deep_base[_deep_base['impressions'] > 0].copy()
        else:
            df_deep = _deep_base.copy()
    else:
        df_deep = pd.DataFrame(columns=df.columns)

    print(f"  Sin H2: {len(df_no_h2)} | Title=H1: {len(df_title_eq_h1)} | Depth>{T_MAX_DEPTH}: {len(df_deep)}")

    # ── Pre-cómputos T33–T51 ──────────────────────────────────────────────────

    # Columna H1 efectiva (profiler_csv → h1_1, SF_COL_MAP → h1)
    _h1_col = 'h1_1' if 'h1_1' in df.columns else ('h1' if 'h1' in df.columns else None)

    # T33 — H1 duplicado en fichas de producto
    if _h1_col:
        _df_prods_seo = df_indexable[df_indexable['url_type'] == 'product']
        _h1_vals_prod = _df_prods_seo[_h1_col].dropna().astype(str).str.strip()
        _h1_vals_prod = _h1_vals_prod[_h1_vals_prod != '']
        _dup_h1_prod_mask = _h1_vals_prod.str.lower().duplicated(keep=False)
        df_dup_h1_products = _df_prods_seo.loc[_h1_vals_prod[_dup_h1_prod_mask].index].copy()
    else:
        df_dup_h1_products = pd.DataFrame(columns=df.columns)

    # T34 — H1 duplicado en colecciones/categorías
    if _h1_col:
        _coll_types = ['collection', 'collections_root', 'tag']
        _df_colls_seo = df_indexable[df_indexable['url_type'].isin(_coll_types)]
        _h1_vals_coll = _df_colls_seo[_h1_col].dropna().astype(str).str.strip()
        _h1_vals_coll = _h1_vals_coll[_h1_vals_coll != '']
        _dup_h1_coll_mask = _h1_vals_coll.str.lower().duplicated(keep=False)
        df_dup_h1_colls = _df_colls_seo.loc[_h1_vals_coll[_dup_h1_coll_mask].index].copy()
    else:
        df_dup_h1_colls = pd.DataFrame(columns=df.columns)

    # T35 — Meta descriptions duplicadas entre páginas SEO indexables
    if 'meta_desc' in df.columns:
        _meta_vals = df_seo['meta_desc'].dropna().astype(str).str.strip()
        _meta_vals = _meta_vals[_meta_vals != '']
        _dup_meta_mask = _meta_vals.str.lower().duplicated(keep=False)
        df_dup_meta = df_seo.loc[_meta_vals[_dup_meta_mask].index].copy()
        n_unique_dup_meta = int(df_seo.loc[_meta_vals[_dup_meta_mask].index, 'meta_desc'].nunique())
    else:
        df_dup_meta = pd.DataFrame(columns=df.columns)
        n_unique_dup_meta = 0

    # T36 — Links internos apuntando a páginas noindex (gasto de crawl budget)
    if HAS_INLINKS_DATA and 'indexable' in df.columns:
        df_noindex_linked = df_no_indexable[
            (df_no_indexable['inlinks'] > 0) &
            (df_no_indexable['status'] == 200)
        ].copy()
    else:
        df_noindex_linked = pd.DataFrame(columns=df.columns)

    # ── Pre-cómputos Shopify (T37–T41) ───────────────────────────────────────
    IS_SHOPIFY = (PLATFORM == 'Shopify')

    if IS_SHOPIFY:
        df_collections_all = df_indexable[
            df_indexable['url'].str.contains(r'/collections/all(\?|$|/)', case=False, na=False, regex=True)
        ].copy()

        df_system_collections = df_indexable[
            df_indexable['url'].str.contains(
                r'/collections/(vendors|types)(\?|$|/)', case=False, na=False, regex=True
            )
        ].copy()

        df_scoped_products = df_indexable[
            df_indexable['url'].str.contains(
                r'/collections/[^/?#]+/products/', case=False, na=False, regex=True
            )
        ].copy()

        # /collections/{handle}/{tag} — excluye /products/ y URLs de sistema
        df_tag_pages = df_indexable[
            df_indexable['url'].apply(lambda u: bool(
                re.search(r'/collections/[^/?#]+/(?!products)[^/?#]+', u, re.I)
            ) if isinstance(u, str) else False)
        ].copy()
        df_tag_pages = df_tag_pages[
            ~df_tag_pages['url'].str.contains(
                r'/collections/(vendors|types)', case=False, na=False, regex=True
            )
        ]

        df_variants = df_indexable[
            df_indexable['url'].str.contains(r'\?variant=', na=False, regex=False)
        ].copy()
    else:
        df_collections_all = df_system_collections = df_scoped_products = pd.DataFrame(columns=df.columns)
        df_tag_pages = df_variants = pd.DataFrame(columns=df.columns)

    # ── Pre-cómputos Structured Data (T42–T48) ────────────────────────────────
    HAS_SD_COL = 'structured_data' in df.columns

    if HAS_SD_COL:
        def _missing_schema(df_sub, schema_regex):
            return df_sub[
                ~df_sub['structured_data'].astype(str).str.contains(
                    schema_regex, case=False, na=False, regex=True
                )
            ].copy()

        _df_prods_idx   = df_indexable[df_indexable['url_type'] == 'product']
        _df_colls_idx   = df_indexable[df_indexable['url_type'].isin(['collection', 'collections_root'])]
        _df_home_idx    = df_indexable[df_indexable['url_type'] == 'homepage']
        _df_blog_idx    = df_indexable[df_indexable['url_type'] == 'blog']
        _df_bc_scope    = df_indexable[df_indexable['url_type'].isin(['product', 'collection', 'collections_root'])]

        df_no_product_schema    = _missing_schema(_df_prods_idx,  r'Product')
        df_no_rating_products   = _missing_schema(_df_prods_idx,  r'AggregateRating|Review')
        df_no_rating_colls      = _missing_schema(_df_colls_idx,  r'AggregateRating|Review')
        df_no_org_schema        = _missing_schema(_df_home_idx,   r'Organization|WebSite|LocalBusiness')
        df_no_blogpost_schema   = _missing_schema(_df_blog_idx,   r'BlogPosting|Article|NewsArticle')
        df_no_author_schema     = _missing_schema(_df_blog_idx,   r'Person|Author')
        df_no_breadcrumb_schema = _missing_schema(_df_bc_scope,   r'BreadcrumbList')
    else:
        df_no_product_schema = df_no_rating_products = df_no_rating_colls = pd.DataFrame(columns=df.columns)
        df_no_org_schema = df_no_blogpost_schema = df_no_author_schema = pd.DataFrame(columns=df.columns)
        df_no_breadcrumb_schema = pd.DataFrame(columns=df.columns)

    print(f"  H1 dup prods: {len(df_dup_h1_products)} | H1 dup colls: {len(df_dup_h1_colls)} | Meta dup: {len(df_dup_meta)}")
    print(f"  Noindex linked: {len(df_noindex_linked)}")

    # ── Pre-cómputos Tanda 1: señales SF infrautilizadas (T49–T56) ────────────────

    _EMPTY = pd.DataFrame(columns=df.columns)

    # T53 — noindex servido por cabecera HTTP X-Robots-Tag (invisible en meta robots)
    if HAS_XROBOTS:
        df_xrobots_noindex = df[
            df['x_robots'].astype(str).str.contains('noindex', case=False, na=False)
        ]
    else:
        df_xrobots_noindex = _EMPTY

    # T54 — Meta refresh (redirect por HTML, no respetado igual que un 301)
    if HAS_META_REFRESH:
        _mr = df['meta_refresh'].astype(str).str.strip()
        df_meta_refresh = df[df['meta_refresh'].notna() & (_mr != '') & (_mr.str.lower() != 'nan')]
    else:
        df_meta_refresh = _EMPTY

    # T55 — Más de un H1 en páginas SEO indexables
    if HAS_H1_2:
        _h12 = df_seo['h1_2'].astype(str).str.strip()
        df_multi_h1 = df_seo[df_seo['h1_2'].notna() & (_h12 != '') & (_h12.str.lower() != 'nan')]
    else:
        df_multi_h1 = _EMPTY

    # T56 — Contenido byte-idéntico entre páginas indexables (mismo Hash de SF)
    if HAS_HASH:
        _hash_scope = df_indexable[df_indexable['status'] == 200].copy()
        _hv = _hash_scope['hash'].astype(str).str.strip()
        _hash_scope = _hash_scope[(_hv != '') & (_hv.str.lower() != 'nan')]
        df_dup_hash = _hash_scope[_hash_scope['hash'].duplicated(keep=False)]
    else:
        df_dup_hash = _EMPTY

    # ── Checks basados en el All Links: follow y posición del enlace ──────────────
    df_no_contextual = _EMPTY
    _links_pag_follow = _links_facet_follow = _links_sensitive_follow = None
    n_links_contextual = n_links_boilerplate = 0

    if HAS_LINKS and _df_links is not None:
        # Solo hipervínculos reales: las imágenes enlazadas no cuentan como enlace
        # editorial y el heurístico es_imagen usa alt_text, que da falsos positivos.
        _hl = _df_links
        if 'link_type' in _hl.columns:
            _lt = _hl['link_type'].astype(str).str.lower().str.strip()
            _hl = _hl[_lt.isin(['href', 'hyperlink', 'enlace', 'hipervínculo', 'hipervinculo'])]
        else:
            _hl = _hl[~_hl['es_imagen']]

        # T52 — Páginas SEO que solo reciben enlaces de boilerplate (footer/header/nav).
        # No son huérfanas para T20 (tienen inlinks > 0) pero no reciben ni un enlace
        # editorial, que es lo que de verdad transmite relevancia.
        if HAS_LINK_POSITION and len(df_seo) > 0:
            _ctx = _hl[_hl['es_contextual']]
            if HAS_FOLLOW_DATA:
                _ctx = _ctx[_ctx['es_follow']]
            n_links_contextual = len(_hl[_hl['es_contextual']])
            n_links_boilerplate = len(_hl) - n_links_contextual
            _ctx_dests = set(_ctx['link_dest'].tolist())
            # La homepage se enlaza desde el logo (header) en todo el site: que no
            # tenga enlaces contextuales es lo normal, no un problema.
            _scope_ctx = df_seo[df_seo['url_type'] != 'homepage']
            _seo_norm = _scope_ctx['url'].astype(str).str.rstrip('/')
            df_no_contextual = _scope_ctx[~_seo_norm.isin(_ctx_dests)]

        # T49/T50/T51 — enlaces internos que deberían llevar nofollow y no lo llevan
        if HAS_FOLLOW_DATA:
            _fol = _hl[_hl['es_follow']]

            _pag_urls = set(df_paginaciones['url'].astype(str).str.rstrip('/').tolist())
            _links_pag_follow = _fol[_fol['link_dest'].isin(_pag_urls)] if _pag_urls else None

            _mask_facets_all = df['url'].apply(
                lambda u: bool(re.search(_facet_combined, u, re.I)) if isinstance(u, str) else False)
            _facet_urls = set(df[_mask_facets_all]['url'].astype(str).str.rstrip('/').tolist())
            _links_facet_follow = _fol[_fol['link_dest'].isin(_facet_urls)] if _facet_urls else None

            _mask_sens_all = df['url'].apply(
                lambda u: any(x in u.lower() for x in _SENSITIVE) if isinstance(u, str) else False)
            _sens_urls = set(df[_mask_sens_all]['url'].astype(str).str.rstrip('/').tolist())
            _links_sensitive_follow = _fol[_fol['link_dest'].isin(_sens_urls)] if _sens_urls else None

    print(f"  X-Robots noindex: {len(df_xrobots_noindex)} | Meta refresh: {len(df_meta_refresh)} | "
          f"Multi-H1: {len(df_multi_h1)} | Hash dup: {len(df_dup_hash)}")
    if HAS_LINK_POSITION:
        print(f"  Enlaces contextuales: {n_links_contextual:,} | boilerplate: {n_links_boilerplate:,} | "
              f"páginas SEO sin enlace contextual: {len(df_no_contextual)}")
    if IS_SHOPIFY:
        print(f"  Shopify — collections/all: {len(df_collections_all)} | system: {len(df_system_collections)}")
        print(f"  Shopify — scoped: {len(df_scoped_products)} | tags: {len(df_tag_pages)} | variants: {len(df_variants)}")
    if HAS_SD_COL:
        print(f"  SD — no Product: {len(df_no_product_schema)} | no Rating: {len(df_no_rating_products)} | no Org: {len(df_no_org_schema)}")


    # ──────────────────────────────────────────────────────────────────────────────
    # 6. TAREAS
    # ──────────────────────────────────────────────────────────────────────────────
    print("\nBuilding tasks...")

    tasks = []

    def add_task(tid, prioridad, categoria, tarea, desc_corta, evidencia,
                 causa_probable, que_hacer, donde_detectarlo, esfuerzo, impacto,
                 riesgo, responsable, validacion, urls_ejemplo):
        tasks.append({
            'ID': tid, 'Prioridad': prioridad, 'Categoría': categoria,
            'Tarea': tarea, 'Descripción corta': desc_corta, 'Evidencia': evidencia,
            'Causa probable': causa_probable, 'Qué hacer': que_hacer,
            'Dónde detectarlo': donde_detectarlo, 'Esfuerzo': esfuerzo,
            'Impacto': impacto, 'Riesgo': riesgo, 'Responsable': responsable,
            'Validación': validacion, 'URLs ejemplo': urls_ejemplo,
        })


    def sample_urls(df_sub, n=5, sort_by='impressions', ascending=False):
        if len(df_sub) == 0:
            return 'N/D'
        if sort_by in df_sub.columns:
            df_sub = df_sub.sort_values(sort_by, ascending=ascending)
        return '\n'.join(df_sub['url'].head(n).tolist())


    # T01 — Locale especial bloqueado (P0, condicional)
    if SPECIAL_LOCALE and ca_url_count > 0:
        locale_label = f'/{SPECIAL_LOCALE}/'
        add_task(
            'T01', 'P0', f'Indexación / {SPECIAL_LOCALE.upper()}',
            f'Resolver bloqueo de robots.txt para el locale {locale_label}',
            f'El locale {locale_label} tiene {ca_url_count:,} URLs detectadas. '
            f'robots.txt bloquea el rastreo de {locale_label} — SF no puede confirmar el estado real.',
            f'{ca_url_count:,} URL(s) con locale {locale_label} detectadas en el crawl. '
            'robots.txt contiene Disallow para este locale. '
            'SF encontró estas URLs enlazadas internamente pero no puede rastrearlas.',
            f'robots.txt incluye una regla Disallow que cubre {locale_label}. '
            'Si es intencionado: las URLs no indexarán (ni Google puede rastrearlas). '
            'Si es un error de configuración: hay contenido bloqueado involuntariamente.',
            f'1. Confirmar con el equipo si el locale {locale_label} debe indexar. '
            f'2a. Si SÍ: eliminar Disallow: {locale_label} de robots.txt. '
            'Re-crawl con SF para auditar todas las URLs del locale. '
            f'2b. Si NO: mantener el Disallow y añadir canonical en las URLs {locale_label} '
            'apuntando a su equivalente en el idioma principal.',
            f'robots.txt del sitio. SF > Configuración > Robots.txt (deshabilitar y re-crawlear).',
            'Bajo', 'Alto', 'Alto', 'SEO + Dev',
            f'Si se decide indexar: re-crawl confirma todas las URLs {locale_label} en status 200 e indexables. '
            f'Si no indexar: 0 URLs {locale_label} en GSC Cobertura.',
            sample_urls(df_ca, sort_by='impressions')
        )

    # T02 — Errores 5xx (P0, condicional)
    n_5xx = len(df_5xx)
    n_503 = len(df_503)
    if n_5xx > 0:
        add_task(
            'T02', 'P0', 'Técnico / Servidor',
            f'Resolver {n_5xx:,} errores de servidor (5xx) detectados en el crawl',
            f'{n_5xx:,} URLs devolvieron un error de servidor durante el crawl '
            f'({n_503:,} con código 503).',
            f'{n_5xx:,} URLs con status 5xx ({n_503:,} × 503). '
            'Los errores de servidor impiden el rastreo e indexación.',
            'Timeouts del servidor, errores de aplicación o bloqueo a nivel de CDN/firewall para el bot de SF.',
            '1. Verificar en producción si las URLs devuelven 5xx de forma consistente. '
            '2. Si es timeout del crawler: re-crawl en horario valle. '
            '3. Si el error es real: escalar a Dev urgente.',
            'SF > Respuesta > Códigos de respuesta > 5xx.',
            'Bajo', 'Alto', 'Alto', 'Dev + SEO',
            'Re-crawl: 0 URLs con status 5xx o 503.',
            sample_urls(df_503 if n_503 > 0 else df_5xx, sort_by='impressions')
        )

    # T03 — Errores 4xx (P0, condicional)
    n_4xx = len(df_4xx)
    n_404 = len(df_404)
    if n_4xx > 0:
        _404_has_gsc = HAS_GSC and 'impressions' in df_404.columns and n_404 > 0
        top_404_url  = df_404.nlargest(1, 'impressions').iloc[0]['url'] if _404_has_gsc else ''
        top_404_impr = int(df_404['impressions'].max()) if _404_has_gsc else 0

        # Detalle de inlinks cuando está disponible
        if HAS_INLINKS_DATA:
            df_4xx_critical = df_4xx[df_4xx['inlinks'] > T_INLINKS_4XX_CRITICAL]
            n_4xx_critical  = len(df_4xx_critical)
            inlinks_detail = (
                f' De ellas, {n_4xx_critical:,} reciben más de {T_INLINKS_4XX_CRITICAL:,} inlinks internos (prioridad crítica).'
                if n_4xx_critical > 0 else ''
            )
        else:
            df_4xx_critical = pd.DataFrame(columns=df.columns)
            n_4xx_critical  = 0
            inlinks_detail  = ''

        evid_404 = (
            f'{n_4xx:,} URLs con status 4xx (de las cuales {n_404:,} son 404).{inlinks_detail} '
            f'La 404 con más demanda GSC: {top_404_url} ({top_404_impr:,} impresiones).'
            if top_404_url else
            f'{n_4xx:,} URLs con status 4xx (de las cuales {n_404:,} son 404).{inlinks_detail}'
        )
        t03_prioridad = 'P0'
        add_task(
            'T03', t03_prioridad, 'Técnico / Errores',
            f'Corregir {n_4xx:,} URLs con error 4xx ({n_404:,} × 404)',
            f'{n_4xx:,} URLs activas en el crawl devuelven error 4xx. '
            'Pueden estar enlazadas internamente o en sitemaps.',
            evid_404,
            'URLs eliminadas sin redirect. Cambios de URL sin actualizar enlaces internos. '
            'Errores en la generación de URLs dinámicas.',
            '1. Para cada 404 con tráfico GSC: crear redirect 301 a la URL equivalente. '
            + (f'2. URGENTE: las {n_4xx_critical:,} URLs con más de {T_INLINKS_4XX_CRITICAL:,} inlinks tienen máximo impacto en PageRank — resolver primero. '
               if n_4xx_critical > 0 else
               '2. ') +
            'Identificar qué páginas enlazan a las 4xx (SF > All Inlinks). '
            '3. Actualizar los enlaces internos rotos. '
            '4. Eliminar las 4xx de sitemaps XML si están presentes.',
            'SF > Respuesta > Códigos de respuesta > 4xx. GSC > Cobertura > 404.',
            'Medio', 'Alto', 'Alto', 'Dev + SEO',
            'Re-crawl: 0 URLs enlazadas internamente con status 4xx. '
            'GSC Cobertura: reducción de errores 404.',
            sample_urls(
                df_4xx_critical if n_4xx_critical > 0 else df_404,
                sort_by='inlinks' if HAS_INLINKS_DATA else 'impressions'
            )
        )

    # T04 — Redirects 301 (P1, condicional)
    n_301 = len(df_301)
    if n_301 > 0:
        if HAS_INLINKS_DATA:
            df_301_inlinks = df_301[df_301['inlinks'] > 0]
            n_301_inlinks  = len(df_301_inlinks)
            evid_301 = (
                f'{n_301:,} URLs con redirect 301 detectadas en el crawl. '
                f'{n_301_inlinks:,} tienen inlinks internos (actualizar el enlace al destino final). '
                'Los redirects encadenados diluyen PageRank y ralentizan el rastreo.'
            )
            valid_301 = (
                'Re-crawl: 0 URLs con status 301 reciben inlinks internos. '
                'SF > All Inlinks: los enlaces apuntan directamente a las URLs destino.'
            )
        else:
            evid_301 = (
                f'{n_301:,} URLs con redirect 301. '
                'Para ver qué páginas enlazan a estas 301s: usar SF > All Inlinks export.'
            )
            valid_301 = (
                'Re-crawl: 0 URLs con status 301 reciben inlinks internos. '
                'Verificar con SF > All Inlinks export.'
            )
        add_task(
            'T04', 'P1', 'Técnico / Redirects',
            f'Actualizar los {n_301:,} enlaces internos que apuntan a redirects 301',
            f'{n_301:,} URLs indexadas como 301. '
            'Los enlaces internos deben apuntar a la URL final para no perder autoridad.',
            evid_301,
            'Templates y CMS generan enlaces a URLs antiguas que ya redirigen. '
            'Actualizaciones de producto/categoría sin actualizar referencias.',
            '1. Exportar SF > All Inlinks y filtrar por Destination Status = 301. '
            '2. Priorizar las 301s con más inlinks entrantes. '
            '3. Actualizar los enlaces en los templates para apuntar a la URL destino. '
            f'4. En {PLATFORM}: revisar menús, breadcrumbs y templates de navegación.',
            'SF > Respuesta > Redirecciones > 301. SF > All Inlinks.',
            'Medio', 'Alto', 'Bajo', 'Dev + SEO',
            valid_301,
            sample_urls(df_301, sort_by='impressions')
        )

    # T05 — Double slash (P1, condicional)
    if n_ds > 0:
        n_ds_idx = len(df_double_slash_indexable)
        add_task(
            'T05', 'P1', 'Técnico / URLs',
            f'Corregir {n_ds:,} URLs con doble slash (//) en la ruta',
            f'{n_ds:,} URLs detectadas con "//" en su ruta '
            f'({n_ds_idx:,} indexables, el resto canonicalizadas) — posible contenido duplicado.',
            f'{n_ds:,} URLs con // en la ruta: {n_ds_idx:,} indexables + '
            f'{n_ds - n_ds_idx:,} canonicalizadas. '
            'Google puede tratar la versión con // y sin // como URLs distintas → duplicados.',
            f'Error en los templates de {PLATFORM}: concatenación incorrecta de variables de ruta.',
            '1. Identificar el template que genera las URLs con //. '
            '2. Corregir la concatenación en el código. '
            '3. Añadir redirect 301 de la versión con // a la versión normalizada.',
            'SF > All URLs > filtrar columna URL por //.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Re-crawl: 0 URLs con // en la ruta.',
            sample_urls(df_double_slash_all, sort_by='inlinks')
        )

    # T06 — Cart-reco indexable (P1, Shopify-específico)
    if HAS_CART_RECO and len(df_cart_reco_indexable) > 0:
        n_cart = len(df_cart_reco_indexable)
        add_task(
            'T06', 'P1', f'Indexación / {PLATFORM}',
            f'Bloquear la indexación de {n_cart:,} URLs de cart-recommendations',
            f'{n_cart:,} URLs de tipo cart-recommendations son indexables. '
            'Estas páginas técnicas no deben aparecer en Google.',
            f'{n_cart:,} URLs con "cart-recommendations" indexadas en el crawl.',
            f'Las URLs de cart-recommendations son endpoints técnicos de {PLATFORM} '
            'para sugerencias de productos. No tienen contenido editorial propio.',
            '1. Añadir meta robots noindex en el template liquid que genera estas páginas. '
            '2. Alternativamente, añadir Disallow: /recommendations/ en robots.txt.',
            f'SF > Indexabilidad = Indexable > filtrar URL contiene "cart-recommendations".',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Re-crawl: 0 URLs de cart-recommendations con estado Indexable.',
            sample_urls(df_cart_reco_indexable)
        )

    # T07 — Paginaciones indexables (P1, condicional)
    if n_pag_index > 0:
        gsc_pag_count = len(df_paginaciones_indexable[df_paginaciones_indexable['impressions'] > 0]) if HAS_GSC else 0
        add_task(
            'T07', 'P1', 'Indexación / Paginación',
            f'Revisar {n_pag_index:,} páginas de paginación indexables',
            f'{n_pag_index:,} URLs de paginación son indexables. '
            'Las paginaciones raramente deben indexarse ya que diluyen autoridad.',
            f'{n_pag_index:,} URLs de paginación indexadas (de {n_pag_total:,} detectadas). '
            + (f'Con señal GSC activa: {gsc_pag_count} URLs.' if gsc_pag_count > 0 else ''),
            'Ausencia de meta robots canonical o noindex en páginas de paginación.',
            '1. Añadir canonical en /page/2, /page/3... apuntando a la página /1. '
            '2. Evaluar noindex para page/2 en adelante. '
            '3. Excluir paginaciones de los sitemaps XML.',
            'SF > filtrar URL contiene "page=" o "/page/". Columna Indexabilidad.',
            'Bajo', 'Medio', 'Bajo', 'Dev + SEO',
            'Re-crawl: 0 URLs de paginación indexadas sin canonical a la URL base.',
            sample_urls(df_paginaciones_indexable, sort_by='impressions')
        )

    # T08 — Meta descriptions (P1, condicional)
    if n_no_meta > 0:
        add_task(
            'T08', 'P1', 'Metadatos / Meta Description',
            f'Añadir meta description a las {n_no_meta:,} páginas SEO que carecen de ella',
            f'{n_no_meta:,} páginas SEO indexables no tienen meta description. '
            'Google puede generar snippets poco atractivos que reducen el CTR.',
            f'{n_no_meta:,} páginas SEO sin meta description: '
            f'{n_no_meta_products:,} productos, {n_no_meta_collections:,} colecciones/categorías, '
            f'{n_no_meta_pages:,} páginas estáticas.',
            f'Los templates de {PLATFORM} no tienen configurada la meta description por defecto. '
            'Las páginas creadas sin rellenar el campo aparecen sin meta desc.',
            '1. Implementar meta description dinámica por defecto en el template '
            '(ej: [Nombre del producto] — Comprar online. Envío rápido | [Marca]). '
            '2. Priorizar las URLs con más impresiones en GSC. '
            '3. Completar manualmente las meta descriptions de las 20-30 URLs de mayor tráfico.',
            'SF > Meta Description > Ausente + filtrar Indexabilidad = Indexable.',
            'Medio', 'Alto', 'Bajo', 'SEO',
            'Re-crawl: 0 páginas SEO indexadas sin meta description. '
            'GSC: mejora de CTR medio en las URLs actualizadas.',
            sample_urls(df_no_meta, sort_by='impressions')
        )

    # T09 — H1 (P1, condicional)
    if n_no_h1 > 0:
        add_task(
            'T09', 'P1', 'Metadatos / H1',
            f'Añadir H1 a las {n_no_h1:,} páginas SEO sin heading principal',
            f'{n_no_h1:,} páginas SEO indexables carecen de H1. '
            'El H1 es la señal semántica principal del contenido para Google.',
            f'{n_no_h1:,} páginas SEO sin H1: {n_no_h1_info:,} páginas/posts.',
            f'Los templates de {PLATFORM} pueden usar elementos visuales como "título" '
            'sin implementar el tag H1 en el HTML.',
            '1. Auditar el template de cada tipo de página afectada. '
            '2. Asegurarse de que el título principal está envuelto en <h1>. '
            '3. Solo puede haber un H1 por página. '
            '4. El H1 debe incluir la keyword principal.',
            'SF > H1 > Ausente + filtrar Indexabilidad = Indexable.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Re-crawl: 0 páginas SEO indexadas sin H1.',
            sample_urls(df_no_h1, sort_by='impressions')
        )

    # T10 — Interlinking (P2, requiere GSC)
    if HAS_GSC and n_demand > 0:
        if HAS_INLINKS_DATA:
            desc_t10  = (
                f'{n_demand:,} páginas SEO tienen ≥{T_IMPRESSIONS_DEMAND:,} impresiones en GSC '
                f'pero solo 0-{T_INLINKS_LOW} inlinks internos. '
                'Reforzar su enlazado puede mejorar posición y tráfico directamente.'
            )
            evid_t10  = (
                f'{n_demand:,} URLs indexables con ≥{T_IMPRESSIONS_DEMAND:,} impresiones y '
                f'≤{T_INLINKS_LOW} inlinks. '
                f'Total impresiones acumuladas: {int(df_seo_demand["impressions"].sum()):,}.'
            )
            hacer_t10 = (
                '1. Exportar el listado de estas URLs (SF + GSC cruzado). '
                '2. Para cada URL: identificar 3-5 páginas relacionadas con autoridad '
                '(homepage, categorías) que puedan enlazarla con anchor text descriptivo. '
                '3. Añadir los enlaces desde los templates o en el contenido. '
                '4. Usar la estructura de categorías y el menú para distribuir autoridad. '
                '5. Considerar una sección de "más buscado" en la homepage con las 5-10 URLs top.'
            )
        else:
            desc_t10  = (
                f'{n_demand:,} páginas SEO tienen ≥{T_IMPRESSIONS_DEMAND:,} impresiones en GSC. '
                'Revisar su enlazado interno puede mejorar posición y tráfico.'
            )
            evid_t10  = (
                f'{n_demand:,} URLs indexables con ≥{T_IMPRESSIONS_DEMAND:,} impresiones. '
                f'Total impresiones: {int(df_seo_demand["impressions"].sum()):,}. '
                'No hay datos de inlinks en este export; usar SF > All Inlinks para priorizar.'
            )
            hacer_t10 = (
                '1. Exportar SF > All Inlinks y cruzar con estas URLs. '
                '2. Para las URLs con menos inlinks: añadir enlaces desde páginas con autoridad. '
                '3. Considerar una sección de "más buscado" en la homepage.'
            )
        t10_prio = 'P1' if n_demand > 500 else 'P2'
        add_task(
            'T10', t10_prio, 'Enlazado Interno',
            f'Reforzar el enlazado interno de {n_demand:,} páginas con demanda GSC',
            desc_t10, evid_t10,
            'Páginas relevantes para SEO que no reciben suficiente autoridad interna. '
            'El enlazado interno no responde a la demanda real de búsqueda.',
            hacer_t10,
            "GSC > Rendimiento > Páginas > ordenar por Impresiones. Cruzar con SF 'All Inlinks'.",
            'Medio', 'Alto', 'Bajo', 'SEO + Dev',
            'Recrawl: las URLs objetivo tienen ≥5 inlinks internos. '
            'GSC: mejora de posición media y clics en las URLs reforzadas (evaluar a 30-60 días).',
            sample_urls(df_seo_demand.sort_values('impressions', ascending=False))
        )

    # T11 — Posición 11-20 (P1, requiere GSC)
    if HAS_GSC and len(df_pos_11_20) > 0:
        n_11_20       = len(df_pos_11_20)
        top_11_20_url = df_pos_11_20.nlargest(1, 'impressions').iloc[0]['url']
        top_11_20_impr = int(df_pos_11_20['impressions'].max())
        add_task(
            'T11', 'P1', 'GSC / Crecimiento',
            'Empujar a página 1 las URLs en posición 11-20 con mayor demanda',
            f'{n_11_20:,} URLs indexables aparecen en posición 11-20 en Google. '
            'Un empuje a página 1 puede multiplicar los clics por 5-10x.',
            f'{n_11_20:,} URLs en pos {T_POS_OPP_MIN}-{T_POS_OPP_MAX} con impresiones. '
            f'La de mayor volumen: {top_11_20_url} ({top_11_20_impr:,} impresiones). '
            f'Suma de impresiones del grupo: {int(df_pos_11_20["impressions"].sum()):,}.',
            'Contenido indexado pero insuficientemente optimizado (thin content, falta de señales '
            'de autoridad, enlazado interno escaso) para competir en el top 10.',
            '1. Para las 10 URLs con más impresiones: auditar contenido (longitud, keywords en H2, '
            'imágenes con alt text, schema). '
            '2. Reforzar enlazado interno desde páginas con autoridad. '
            '3. Revisar intención de búsqueda: ¿el contenido responde exactamente a lo que busca el usuario? '
            '4. Revisar que el snippet (title + meta) es competitivo vs las URLs en top 5.',
            f'GSC > Rendimiento > Páginas. Filtrar posición {T_POS_OPP_MIN}-{T_POS_OPP_MAX}, ordenar por Impresiones desc.',
            'Alto', 'Alto', 'Bajo', 'SEO',
            'GSC Rendimiento en 30-60 días: aumento de posición media y clics en las URLs trabajadas. '
            'Al menos 5 de las 10 URLs trabajadas deben aparecer en posición ≤10.',
            sample_urls(df_pos_11_20.sort_values('impressions', ascending=False))
        )

    # T12 — CTR bajo en top 10 (P1, requiere GSC)
    if HAS_GSC and len(df_low_ctr) > 0:
        n_low_ctr = len(df_low_ctr)
        add_task(
            'T12', 'P1', 'GSC / Snippet',
            f'Mejorar el CTR de {n_low_ctr:,} URLs en top 10 con tasa de clics inferior al {T_CTR_LOW*100:.0f}%',
            f'{n_low_ctr:,} URLs aparecen en los 10 primeros resultados pero tienen CTR <{T_CTR_LOW*100:.0f}%. '
            'Son impresiones que se muestran pero no se convierten en visitas.',
            f'{n_low_ctr:,} URLs con posición ≤10, CTR <{T_CTR_LOW*100:.0f}% y '
            f'≥{T_IMPRESSIONS_MIN_CTR} impresiones. '
            f'Suma de impresiones desaprovechadas: {int(df_low_ctr["impressions"].sum()):,}. '
            f'Llevando el CTR al {T_CTR_LOW*200:.0f}% se obtendría un incremento estimado de '
            f'{int(df_low_ctr["impressions"].sum() * T_CTR_LOW):,} clics/periodo.',
            'Titles genéricos sin diferenciadores. Meta descriptions ausentes o sin CTA. '
            'Sin datos estructurados (estrellas, precio) que enriquezcan el snippet.',
            '1. Reescribir titles de las 20 URLs con más impresiones: keyword al inicio, '
            'diferenciador (precio, envío gratis) y máximo 60 chars. '
            '2. Añadir/mejorar meta descriptions con CTA directo. '
            '3. Implementar schema de Producto (precio, disponibilidad, valoraciones). '
            '4. Testear variantes de title con GSC durante 30 días.',
            f'GSC > Rendimiento > Páginas. Filtrar posición ≤10 y CTR <{T_CTR_LOW*100:.0f}%, '
            'ordenar por Impresiones desc.',
            'Medio', 'Alto', 'Bajo', 'SEO',
            'GSC Rendimiento: CTR medio del grupo objetivo supera el doble del valor actual '
            'en los 60 días posteriores al cambio.',
            sample_urls(df_low_ctr.sort_values('impressions', ascending=False))
        )

    # T13 — Titles cortos en colecciones/categorías (P2, condicional)
    if n_short_title > 0:
        type_label = 'colecciones' if PLATFORM == 'Shopify' else 'categorías/páginas'
        add_task(
            'T13', 'P2', 'Metadatos / Titles',
            f'Revisar {n_short_title:,} {type_label} con title corto o genérico',
            f'{n_short_title:,} {type_label} tienen title de menos de {T_TITLE_SHORT_CHARS} caracteres. '
            'Los titles cortos suelen ser genéricos con menor capacidad de rankear.',
            f'{n_short_title:,} {type_label} indexadas con title <{T_TITLE_SHORT_CHARS} chars.',
            f'Los templates de {PLATFORM} usan el nombre corto de la categoría como title '
            'sin añadir modificadores SEO.',
            f'1. Para las 15-20 {type_label} más visitadas: reescribir el title incluyendo '
            'keyword principal + modificador (comprar, online) + | {DOMAIN}. '
            f'2. Ejemplo: "Nike" → "Comprar Zapatillas Nike Online | {DOMAIN}". '
            '3. Fórmula: [Keyword principal] [modificador] [año si aplica] | Marca.',
            f'SF > Titles > filtrar Longitud < {T_TITLE_SHORT_CHARS} + Indexabilidad = Indexable.',
            'Bajo', 'Medio', 'Bajo', 'SEO',
            f'Re-crawl: 0 {type_label} indexadas con title <{T_TITLE_SHORT_CHARS} chars.',
            sample_urls(df_short_title.sort_values('impressions', ascending=False) if HAS_GSC and 'impressions' in df_short_title.columns else df_short_title)
        )

    # T14 — Hreflang (P2, solo si multilingual)
    if IS_MULTILINGUAL and SITE_LANGS:
        langs_str  = ', '.join([f'/{l}/' for l in SITE_LANGS])
        n_langs    = len(SITE_LANGS) + 1
        add_task(
            'T14', 'P2', 'Internacional / Hreflang',
            f'Auditar implementación de hreflang para los {n_langs} idiomas',
            'El export de SF no incluye columna de hreflang. Es necesario un crawl específico '
            'para validar los alternates de todos los idiomas.',
            f'{n_langs} versiones de idioma detectadas: {langs_str} + raíz. '
            'No se puede validar hreflang desde el CSV actual. '
            'GSC > Internacional > Errores de hreflang puede mostrar problemas existentes.',
            'El export no incluye la pestaña Hreflang de SF (requiere activar el análisis). '
            'Posibles problemas: falta de x-default, idiomas sin self-referential alternate, '
            'pares no recíprocos.',
            '1. En SF: activar Crawl > Configuration > Spider > Extraction > soporte hreflang. '
            '2. Re-crawlear el sitio y exportar la pestaña Hreflang > All. '
            '3. Verificar: a) cada idioma tiene alternate a sí mismo, b) existe x-default, '
            'c) los pares son recíprocos. '
            '4. Validar en GSC > Configuración > Internacional > Errores de hreflang.',
            'SF > Hreflang > All (requiere re-crawl). '
            'GSC > Configuración > Internacional > Errores de hreflang.',
            'Medio', 'Alto', 'Medio', 'SEO + Dev',
            'SF Hreflang: 0 errores de conflicto, URL no rastreable o falta x-default. '
            'GSC Internacional: 0 errores para las versiones principales.',
            f'https://{DOMAIN}/\n' + '\n'.join([f'https://{DOMAIN}/{l}/' for l in SITE_LANGS])
        )

    # T15 — URLs sensibles indexables (P1, condicional)
    n_sensitive = len(df_sensitive)
    if n_sensitive > 0:
        add_task(
            'T15', 'P1', 'Indexación / Seguridad',
            f'Bloquear indexación de {n_sensitive:,} URLs sensibles (carrito, checkout, login…)',
            f'{n_sensitive:,} URLs de procesos internos o privados son indexables. '
            'Estas páginas no deben aparecer en Google: no aporten valor y exponen lógica interna.',
            f'{n_sensitive:,} URLs con patrones sensibles (cart, checkout, login, account, '
            'search, buscar, cesta…) detectadas como indexables en el crawl.',
            f'Los templates de {PLATFORM} no añaden meta robots noindex por defecto '
            'en estas rutas funcionales. Pueden estar en sitemaps y recibir inlinks internos.',
            '1. Añadir <meta name="robots" content="noindex,nofollow"> en los templates '
            'de carrito, checkout, login, cuenta y búsqueda. '
            '2. Añadir Disallow en robots.txt para las rutas /cart/, /checkout/, /login/, '
            '/account/, /search/. '
            '3. Eliminar estas URLs de sitemaps XML si están presentes. '
            '4. Actualizar los enlaces internos para que no apunten a versiones indexables.',
            'SF > Indexabilidad = Indexable > filtrar URL por cart/checkout/login/account.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Re-crawl: 0 URLs sensibles con estado Indexable. '
            'GSC Cobertura: estas URLs desaparecen del índice en 2-4 semanas.',
            sample_urls(df_sensitive, sort_by='impressions' if HAS_GSC else 'inlinks')
        )

    # T16 — Facetas/filtros indexables (P1, condicional)
    n_facets = len(df_facets)
    if n_facets > 0:
        add_task(
            'T16', 'P1', 'Indexación / Facetas',
            f'Añadir noindex + canonical a {n_facets:,} URLs de facetas/filtros indexables',
            f'{n_facets:,} URLs de navegación facetada (filtros por color, marca, precio, talla…) '
            'son indexables. Generan contenido duplicado y diluyen autoridad.',
            f'{n_facets:,} URLs con patrones de facetas (-f, ?filtro=, ?color=, ?marca=, ?sort=…) '
            'detectadas como indexables. Cada combinación de filtros crea una URL separada '
            'con contenido prácticamente igual al de la categoría base.',
            f'El CMS ({PLATFORM}) no bloquea por defecto la indexación de URLs generadas '
            'por facetas de navegación. Con N filtros y M valores, se generan N×M URLs.',
            '1. Añadir <meta name="robots" content="noindex"> en el template de resultados '
            'de filtrado. '
            '2. Añadir canonical en cada URL de faceta apuntando a la categoría base. '
            '3. Excluir los patrones de facetas del sitemap XML. '
            '4. Si algún filtro tiene volumen de búsqueda propio (ej: "zapatillas rojas"), '
            'crear una landing page dedicada en lugar de usar la URL de faceta.',
            'SF > All URLs > filtrar URL por patrón -f / ?filtro= / ?color=.',
            'Bajo', 'Alto', 'Bajo', 'Dev + SEO',
            'Re-crawl: 0 URLs de facetas con estado Indexable. '
            'GSC Cobertura: reducción de URLs descubiertas mediante exploración.',
            sample_urls(df_facets, sort_by='impressions' if HAS_GSC else 'inlinks')
        )

    # T17 — Canonical a URL diferente (P1, condicional)
    n_non_self_can = len(df_non_self_canonical)
    if n_non_self_can > 0:
        top_can_url    = df_non_self_canonical.iloc[0]['url'] if n_non_self_can > 0 else ''
        top_can_target = df_non_self_canonical.iloc[0]['canonical'] if n_non_self_can > 0 else ''
        add_task(
            'T17', 'P1', 'Canonicals / Indexación',
            f'Revisar {n_non_self_can:,} páginas indexables con canonical apuntando a otra URL',
            f'{n_non_self_can:,} páginas tienen canonical tag configurado hacia una URL diferente '
            'a sí mismas. Puede ser intencional (variantes de producto) o un error.',
            f'{n_non_self_can:,} URLs con canonical ≠ propia URL. '
            f'Ejemplo: {top_can_url} → canonical: {top_can_target}. '
            'Si el canonical es incorrecto, Google indexará la URL equivocada.',
            'Configuración de variantes de producto que apuntan al producto padre. '
            'Error en templates: canonical hardcodeado o calculado incorrectamente. '
            'Migración de URLs sin actualizar los canonicals.',
            '1. Exportar SF > Canonicals > Contains a canonical URL e identificar patrones. '
            '2. Separar los canonicals intencionales (variantes → padre) de los accidentales. '
            '3. Para cada canonical incorrecto: corregir el tag en el template. '
            '4. Si hay variantes legítimas: asegurarse de que la URL canónica es efectivamente '
            'la versión principal y está bien optimizada.',
            'SF > Canonicals > Contains a canonical URL (filtrar Indexabilidad = Indexable).',
            'Medio', 'Alto', 'Medio', 'SEO + Dev',
            'Re-crawl: las URLs intencionales mantienen canonical correcto. '
            'Las URLs con canonical erróneo tienen self-canonical. '
            'GSC: las URLs canónicas declaradas aparecen indexadas correctamente.',
            sample_urls(df_non_self_canonical, sort_by='impressions' if HAS_GSC else 'inlinks')
        )

    # T18 — Thin content (P2, condicional)
    n_thin = len(df_thin)
    if n_thin > 0:
        avg_thin_wc = int(df_thin['word_count'].mean()) if 'word_count' in df_thin.columns else 0
        add_task(
            'T18', 'P2', 'Contenido / Calidad',
            f'Ampliar o eliminar {n_thin:,} páginas SEO con contenido escaso '
            f'(< {T_WORD_COUNT_THIN} palabras)',
            f'{n_thin:,} páginas SEO indexables tienen menos de {T_WORD_COUNT_THIN} palabras. '
            'Google considera este tipo de contenido "thin" y puede penalizarlo.',
            f'{n_thin:,} páginas SEO (productos/colecciones/blog) con menos de '
            f'{T_WORD_COUNT_THIN} palabras (media: {avg_thin_wc} palabras). '
            'Son páginas que rankearán con dificultad y pueden dañar la percepción de calidad del dominio.',
            'Templates vacíos o sin rellenar. Páginas creadas automáticamente sin contenido editorial. '
            'Descripción de producto omitida. Posts de blog en borrador publicados accidentalmente.',
            f'1. Priorizar las {min(20, n_thin)} páginas con más impresiones en GSC. '
            '2. Para productos: añadir descripción detallada (>150 palabras): '
            'características, materiales, uso, beneficios. '
            '3. Para categorías: añadir texto introductorio SEO de 100-200 palabras al inicio y al final. '
            '4. Para posts de blog vacíos: completar o poner en noindex/borrador. '
            '5. Auditar el template para añadir campos de descripción obligatorios.',
            f'SF > All URLs > filtrar Word Count < {T_WORD_COUNT_THIN} + Indexabilidad = Indexable.',
            'Alto', 'Medio', 'Bajo', 'SEO + Contenido',
            f'Re-crawl: 0 páginas SEO con word_count < {T_WORD_COUNT_THIN}. '
            'GSC: mejora de posición en las páginas ampliadas (evaluar a 30-60 días).',
            sample_urls(df_thin, sort_by='impressions' if HAS_GSC else 'word_count')
        )

    # T19 — Redirects 302 (P1, condicional)
    n_302 = len(df_302)
    if n_302 > 0:
        add_task(
            'T19', 'P1', 'Técnico / Redirects',
            f'Convertir {n_302:,} redirects 302 (temporales) en 301 permanentes',
            f'{n_302:,} URLs responden con código 302 (redirect temporal). '
            'Los 302 no transfieren autoridad de forma fiable y confunden a Google.',
            f'{n_302:,} redirects 302 detectados en el crawl. '
            'A diferencia de los 301, los 302 no trasladan PageRank de forma garantizada '
            'y Google puede indexar tanto la URL de origen como la de destino.',
            f'Configuración errónea en {PLATFORM} o en el servidor web/CDN. '
            'Uso de redirecciones temporales para casos que son permanentes '
            '(ej: 302 de la home sin www → con www).',
            '1. Identificar el destino de cada 302 (SF > Response Codes > 3xx). '
            '2. Si la redirección es permanente: cambiar 302 → 301 en el servidor/CMS. '
            '3. Prestar especial atención a 302s hacia la homepage (muy común en '
            'configs de dominio y casos de canonicalización de homepage). '
            '4. Si algún 302 es genuinamente temporal (test A/B): mantenerlo y documentarlo.',
            'SF > Respuesta > Códigos de respuesta > 3xx > filtrar por código 302.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Re-crawl: 0 redirects 302 (salvo los genuinamente temporales documentados). '
            'GSC: mejora de cobertura en las URLs que eran origen de 302.',
            sample_urls(df_302, sort_by='inlinks' if HAS_INLINKS_DATA else 'url')
        )

    # T20 — Huérfanas (P2, requiere inlinks; con GSC prioriza por tráfico)
    n_orphans = len(df_orphans)
    if n_orphans > 0:
        if HAS_GSC and 'impressions' in df_orphans.columns and df_orphans['impressions'].sum() > 0:
            _top_url  = df_orphans.nlargest(1, 'impressions').iloc[0]['url']
            _top_impr = int(df_orphans['impressions'].max())
            _t20_desc = (
                f'{n_orphans:,} páginas SEO tienen impresiones en Google (>{T_ORPHAN_IMPRESSIONS:,}) '
                'pero 0 inlinks internos. Google las encuentra pero el sitio no las enlaza.'
            )
            _t20_evid = (
                f'{n_orphans:,} URLs con más de {T_ORPHAN_IMPRESSIONS:,} impresiones en GSC '
                f'y 0 inlinks internos en SF. '
                f'La de mayor volumen: {_top_url} ({_top_impr:,} impresiones). '
                '0 inlinks = Google trabaja solo para encontrarlas, sin apoyo de la arquitectura.'
            )
            _t20_donde = (
                'SF > All URLs > filtrar Unique Inlinks = 0 + Indexabilidad = Indexable. '
                'Cruzar con GSC > Rendimiento > Páginas ordenado por Impresiones.'
            )
            _t20_sample = sample_urls(df_orphans.sort_values('impressions', ascending=False))
        else:
            _t20_desc = (
                f'{n_orphans:,} páginas SEO (productos, posts, páginas) con 0 inlinks internos. '
                'Ninguna otra página del sitio las enlaza — son invisibles para el crawl de Google.'
            )
            _t20_evid = (
                f'{n_orphans:,} URLs de tipo SEO con Inlinks = 0 en SF. '
                'Sin inlinks internos, Google solo puede descubrirlas por sitemap o GSC. '
                'No reciben PageRank interno ni señal de importancia desde la arquitectura.'
            )
            _t20_donde = (
                'SF > All URLs > filtrar Unique Inlinks = 0 + Indexabilidad = Indexable + '
                'Content Type = text/html.'
            )
            _t20_sample = sample_urls(df_orphans)
        add_task(
            'T20', 'P2', 'Enlazado Interno / Huérfanas',
            f'Enlazar {n_orphans:,} páginas huérfanas sin inlinks internos',
            _t20_desc,
            _t20_evid,
            'Páginas creadas y olvidadas sin actualizar la navegación. '
            'Productos o posts sin categoría asignada. '
            'URLs antiguas que sobrevivieron a una migración sin preservar el enlazado.',
            '1. Exportar este listado y ordenar por impresiones (o inlinks si no hay GSC). '
            '2. Para las 10-15 URLs más importantes: identificar 2-3 páginas '
            'con autoridad (categorías padre, homepage, posts relacionados) que puedan enlazarlas. '
            '3. Añadir los enlaces con anchor text descriptivo y relevante. '
            '4. Si la URL no debería existir (contenido obsoleto): redirigir o añadir noindex.',
            _t20_donde,
            'Bajo', 'Alto', 'Bajo', 'SEO + Dev',
            f'Re-crawl + 30 días: las URLs objetivo tienen ≥3 inlinks internos. '
            'GSC: mejora de posición media en las URLs enlazadas.',
            _t20_sample
        )

    # T21 — URLs no-indexables en el sitemap XML (P1)
    n_noindex_sitemap = len(df_noindex_in_sitemap)
    if HAS_SITEMAP_DATA and n_noindex_sitemap > 0:
        reasons = df_noindex_in_sitemap['indexability_status'].value_counts().head(3).to_dict() if 'indexability_status' in df_noindex_in_sitemap.columns else {}
        reasons_str = ', '.join(f'{v}× {k}' for k, v in reasons.items()) if reasons else 'diversas razones'
        add_task(
            'T21', 'P1', 'Sitemaps / Inconsistencia con indexación',
            f'Eliminar {n_noindex_sitemap:,} URLs no-indexables del sitemap XML',
            f'El sitemap incluye {n_noindex_sitemap:,} URLs que Google no puede indexar '
            f'(noindex, canonicalizada a otra URL, etc.). '
            'Diluye el crawl budget y confunde a los bots.',
            f'{n_noindex_sitemap:,} URLs están en el sitemap pero marcadas como no-indexables en SF. '
            f'Razones principales: {reasons_str}. '
            'Google prioriza el sitemap para descubrir URLs indexables; incluir no-indexables '
            'genera señales contradictorias entre el sitemap y las directivas on-page.',
            'Sitemap generado automáticamente sin filtrar por indexabilidad. '
            'Cambios de indexabilidad posteriores a la generación del sitemap. '
            'Plugin de sitemap sin configuración avanzada.',
            '1. Filtrar el sitemap para incluir solo URLs status 200 + Indexable. '
            '2. Si usas un plugin (Yoast, Rank Math…): excluir noindex/canonicalizadas. '
            '3. Regenerar el sitemap y reenviar en GSC > Sitemaps. '
            '4. Verificar en GSC > Cobertura que desaparecen las URLs excluidas.',
            'SF > Sitemaps > Export all crawled in sitemaps. Filtrar Indexability ≠ Indexable.',
            'Bajo', 'Medio', 'Bajo', 'SEO + Dev',
            'Re-crawl: 0 URLs no-indexables en sitemap. GSC Cobertura: caída en "Excluida - noindex".',
            sample_urls(df_noindex_in_sitemap, sort_by='inlinks' if HAS_INLINKS_DATA else 'url')
        )

    # T22 — URLs indexables ausentes del sitemap (P1)
    n_missing_sitemap = len(df_missing_from_sitemap)
    if HAS_SITEMAP_DATA and n_missing_sitemap > 0:
        add_task(
            'T22', 'P1', 'Sitemaps / Cobertura incompleta',
            f'Añadir {n_missing_sitemap:,} URLs indexables al sitemap XML',
            f'{n_missing_sitemap:,} páginas indexables (status 200) no están en el sitemap. '
            'Google puede tardar más en descubrirlas y recrawlearlas.',
            f'{n_missing_sitemap:,} URLs con status 200 e indexabilidad "Indexable" ausentes del sitemap. '
            'El sitemap actúa como señal de prioridad de rastreo; las URLs fuera de él '
            'dependen exclusivamente del enlazado interno para su descubrimiento.',
            'Sitemap configurado con exclusiones excesivas. '
            'Nuevas secciones del sitio no añadidas al generador de sitemaps. '
            'Sitemap estático no actualizado.',
            '1. Identificar qué tipos de URL faltan (categorías, posts, productos…). '
            '2. Actualizar la configuración del generador de sitemap para incluirlas. '
            '3. Si el sitemap es estático: añadir las URLs manualmente o migrar a generación dinámica. '
            '4. Regenerar y reenviar en GSC > Sitemaps.',
            'SF > Sitemaps > In Sitemap = No. Filtrar Indexability = Indexable + Status 200.',
            'Bajo', 'Medio', 'Bajo', 'SEO + CMS',
            'Re-crawl: todas las URLs indexables aparecen en el sitemap. '
            'GSC > Sitemaps: aumento en el recuento de URLs enviadas.',
            sample_urls(df_missing_from_sitemap, sort_by='inlinks' if HAS_INLINKS_DATA else 'url')
        )

    # T23 — Tiempo de respuesta lento >3 s (P1)
    n_slow = len(df_slow)
    if HAS_RESPONSE_TIME and n_slow > 0:
        avg_slow = round(df_slow['response_time'].mean(), 2) if 'response_time' in df_slow.columns else 0
        top_slow_url = df_slow.sort_values('response_time', ascending=False).iloc[0]['url'] if n_slow > 0 else ''
        top_slow_time = round(df_slow['response_time'].max(), 2) if n_slow > 0 else 0
        add_task(
            'T23', 'P1', 'Técnico / Velocidad',
            f'Optimizar tiempo de respuesta en {n_slow:,} páginas lentas (>{T_SLOW_RESPONSE}s)',
            f'{n_slow:,} páginas indexables superan los {T_SLOW_RESPONSE}s de TTFB durante el crawl. '
            f'Media: {avg_slow}s. Máximo: {top_slow_time}s. Impacta Core Web Vitals y crawl budget.',
            f'{n_slow:,} páginas con response_time >{T_SLOW_RESPONSE}s en SF. '
            f'Tiempo medio de las afectadas: {avg_slow}s. '
            f'URL más lenta: {top_slow_url} ({top_slow_time}s). '
            'Googlebot reduce la frecuencia de rastreo en sitios con TTFB elevado; '
            'además, un TTFB alto es el principal factor del LCP.',
            'Consultas de base de datos sin índices. '
            'Plugins pesados o conflictos de caché. '
            'Hosting infradimensionado. '
            'Procesos de terceros bloqueantes en server-side.',
            f'1. Priorizar las URLs con más tráfico GSC de este listado. '
            '2. Medir TTFB real en PageSpeed Insights y WebPageTest. '
            '3. Activar/corregir caché de página (full-page caching). '
            '4. Revisar queries lentas con herramientas de profiling (Query Monitor, New Relic). '
            '5. Evaluar upgrade de hosting o activar CDN con edge caching.',
            f'SF > All URLs > Columna Response Time > ordenar desc. '
            'Filtrar Content Type = text/html + Status = 200 + Indexability = Indexable.',
            'Bajo', 'Alto', 'Medio', 'Dev + Hosting',
            f'Re-crawl: 0 URLs indexables con response_time >{T_SLOW_RESPONSE}s. '
            'PageSpeed Insights: TTFB <800ms en las URLs objetivo.',
            sample_urls(df_slow.sort_values('response_time', ascending=False))
        )

    # T24 — URLs con parámetros indexables (P2)
    n_parametered = len(df_parametered)
    if n_parametered > 0:
        add_task(
            'T24', 'P2', 'URL / Parámetros indexables',
            f'Revisar {n_parametered:,} URLs con parámetros (?) indexadas por Google',
            f'{n_parametered:,} páginas indexables contienen "?" en la URL. '
            'Pueden generar contenido duplicado y desperdiciar crawl budget.',
            f'{n_parametered:,} URLs indexables con al menos un parámetro en la query string. '
            'Google puede tratar cada combinación de parámetros como una URL única, '
            'multiplicando el contenido duplicado y diluyendo la autoridad de las páginas canónicas.',
            'Filtros de tienda/catálogo sin canonical o noindex. '
            'Tracking UTMs en URLs indexables. '
            'Sistema de sesiones o caches con parámetros no filtrados.',
            '1. Clasificar los parámetros: tracking (UTM→ GSC > Parámetros de URL o canonical). '
            '2. Para parámetros de filtro/orden: añadir canonical a la URL sin parámetros. '
            '3. Para parámetros que cambian contenido: evaluar noindex o consolidar con pagination. '
            '4. Configurar GSC > Parámetros de URL para indicar a Google cuáles ignorar.',
            'SF > All URLs > filtrar URL contains "?". Confirmar Indexability = Indexable.',
            'Bajo', 'Medio', 'Bajo', 'SEO + Dev',
            'Re-crawl: las URLs con parámetros tienen canonical correcta o noindex. '
            'GSC Cobertura: reducción de URLs indexadas con parámetros.',
            sample_urls(df_parametered, sort_by='impressions' if HAS_GSC else 'url')
        )

    # T25 — URLs largas >115 caracteres (P2)
    n_long_urls = len(df_long_urls)
    if n_long_urls > 0:
        max_url_len = df_long_urls['url'].str.len().max()
        add_task(
            'T25', 'P2', 'URL / Estructura',
            f'Acortar {n_long_urls:,} URLs indexables con más de {T_URL_MAX_LEN} caracteres',
            f'{n_long_urls:,} URLs indexables superan los {T_URL_MAX_LEN} caracteres. '
            f'URL más larga: {max_url_len} caracteres. '
            'URLs largas tienen menor CTR y son más difíciles de compartir.',
            f'{n_long_urls:,} URLs con len(url) > {T_URL_MAX_LEN} chars en SF. '
            f'La URL más larga tiene {max_url_len} caracteres. '
            'Google muestra como máximo ~70 chars del slug en el snippet; '
            'las URLs largas se truncan y reducen la legibilidad del resultado.',
            'Slugs generados automáticamente desde títulos largos. '
            'Jerarquías de categorías muy anidadas (/cat1/cat2/cat3/producto). '
            'Parámetros incluidos en el slug.',
            '1. Identificar patrones de URL largas (productos, posts, categorías anidadas). '
            '2. Definir convención de slug: máximo 5 palabras clave, sin stop words. '
            '3. Acortar las URLs más visitadas y añadir 301 desde la URL antigua. '
            '4. Actualizar el CMS para generar slugs cortos por defecto.',
            f'SF > All URLs > añadir columna URL Length > filtrar > {T_URL_MAX_LEN} chars.',
            'Medio', 'Bajo', 'Bajo', 'SEO + CMS',
            f'Re-crawl: porcentaje de URLs >{T_URL_MAX_LEN} chars se reduce en ≥50%. '
            'CTR medio mejora en las URLs acortadas (monitorizar en GSC).',
            sample_urls(df_long_urls.assign(_len=df_long_urls['url'].str.len()).sort_values('_len', ascending=False).drop(columns=['_len']))
        )

    # T26 — Titles duplicados (P1)
    n_dup_titles = len(df_dup_titles)
    if HAS_TITLE_1 and n_dup_titles > 0:
        add_task(
            'T26', 'P1', 'Metadatos / Titles duplicados',
            f'Diversificar {n_dup_titles:,} páginas con title tag duplicado '
            f'({n_unique_dup_titles:,} títulos compartidos por varias URLs)',
            f'{n_dup_titles:,} páginas indexables comparten title tag con al menos otra URL. '
            'Google no puede diferenciar el contenido de cada página y puede mergear señales.',
            f'{n_dup_titles:,} páginas indexables tienen un title_1 idéntico a otra URL del sitio. '
            f'Hay {n_unique_dup_titles:,} títulos distintos afectados. '
            'Los titles duplicados dificultan que Google entienda qué página rankear para cada query; '
            'puede elegir la "equivocada" o reescribir el título automáticamente.',
            'Plantillas de CMS generando el mismo title para múltiples páginas. '
            'Páginas de paginación con el mismo title que la página /1. '
            'Productos de la misma categoría sin diferenciador en el title.',
            '1. Exportar el listado y agrupar por title duplicado para identificar patrones. '
            '2. Para páginas de listing/categoría: añadir el número de página al title (ej. "- Página 2"). '
            '3. Para productos: incluir SKU, talla o color. '
            '4. Actualizar la plantilla del CMS para generar títulos únicos automáticamente.',
            'SF > Page Titles > Duplicate + Missing. Filtrar Indexability = Indexable.',
            'Bajo', 'Alto', 'Bajo', 'SEO + CMS',
            'Re-crawl: 0 titles duplicados en páginas indexables. '
            'GSC: mejora en CTR de las páginas con título diferenciado.',
            sample_urls(df_dup_titles, sort_by='impressions' if HAS_GSC else 'url')
        )

    # T27 — Páginas noindex con impresiones en GSC (P1, requiere GSC)
    n_noindex_gsc = len(df_noindex_with_gsc)
    if HAS_GSC and n_noindex_gsc > 0:
        total_impr_noindex = int(df_noindex_with_gsc['impressions'].sum())
        top_noindex_url   = df_noindex_with_gsc.nlargest(1, 'impressions').iloc[0]['url']
        top_noindex_impr  = int(df_noindex_with_gsc['impressions'].max())
        add_task(
            'T27', 'P1', 'Indexación / GSC vs noindex',
            f'Revisar {n_noindex_gsc:,} páginas bloqueadas a la indexación que tienen '
            f'impresiones en GSC ({total_impr_noindex:,} impresiones en total)',
            f'{n_noindex_gsc:,} URLs están marcadas como no-indexables en SF pero '
            f'aún generan {total_impr_noindex:,} impresiones en Google. '
            'Señal de conflicto entre directivas on-page y el índice real de Google.',
            f'{n_noindex_gsc:,} URLs con indexability ≠ Indexable y impressions GSC > 0. '
            f'Total impresiones perdidas: {total_impr_noindex:,}. '
            f'URL con más impresiones: {top_noindex_url} ({top_noindex_impr:,} impr.). '
            'Esto indica que Google tenía estas URLs indexadas antes de añadir el noindex, '
            'o que el noindex se ha aplicado por error.',
            'Noindex añadido por error (ej. staging copiado a producción). '
            'Cambio de estrategia de indexación sin revisar el impacto en tráfico activo. '
            'Canonical a otra URL en páginas que sí deben indexar.',
            '1. Para cada URL: decidir si el noindex es intencionado o un error. '
            '2. Si es error: eliminar el noindex/canonical y monitorizar re-indexación en GSC. '
            '3. Si es intencionado: redirigir el tráfico residual a una URL equivalente indexable. '
            '4. Revisar el proceso de QA para evitar noindex en producción.',
            'SF > Indexability > Non-Indexable. Cruzar con GSC > Rendimiento. '
            'Filtrar páginas con impressions > 0.',
            'Bajo', 'Alto', 'Bajo', 'SEO',
            'Re-crawl: las URLs con tráfico GSC son Indexable. '
            'GSC Cobertura: reducción de "Excluida - noindex" en URLs con impresiones.',
            sample_urls(df_noindex_with_gsc.sort_values('impressions', ascending=False))
        )

    # T28 — Titles largos >60 chars (P2)
    n_long_titles = len(df_long_titles)
    if HAS_TITLE_LEN and n_long_titles > 0:
        avg_title_len = round(df_long_titles['title_1_length'].mean(), 0) if 'title_1_length' in df_long_titles.columns else 0
        add_task(
            'T28', 'P2', 'Metadatos / Title largo',
            f'Acortar title tag en {n_long_titles:,} páginas indexables (>{60} caracteres)',
            f'{n_long_titles:,} páginas tienen un title de más de 60 caracteres '
            f'(media: {avg_title_len:.0f} chars). Google trunca a ~60 chars y puede reescribir el título.',
            f'{n_long_titles:,} URLs indexables con title_1_length > 60. '
            f'Media de longitud en las afectadas: {avg_title_len:.0f} caracteres. '
            'Google trunca el title en el snippet a ~600 px (≈60 chars); '
            'un title truncado pierde la keyword final y puede bajar el CTR.',
            'Plantillas de CMS usando nombre completo del producto/post sin límite de caracteres. '
            'Textos de title generados manualmente sin revisión de longitud. '
            'Titles con boilerplate al final (ej. "| Nombre de la tienda | Categoría").',
            '1. Exportar el listado y priorizar las páginas con más impresiones. '
            '2. Reescribir el title para que la keyword principal aparezca en los primeros 60 chars. '
            '3. Eliminar boilerplate superfluo o moverlo al inicio si es relevante. '
            '4. Configurar la plantilla del CMS para avisar cuando el title supere 60 chars.',
            'SF > Page Titles > Over 60 Characters (o columna Title 1 Length > 60).',
            'Bajo', 'Medio', 'Bajo', 'SEO',
            'Re-crawl: todas las páginas indexables tienen title_1_length ≤ 60. '
            'GSC: mejora de CTR en las URLs corregidas.',
            sample_urls(df_long_titles.sort_values('title_1_length', ascending=False) if 'title_1_length' in df_long_titles.columns else df_long_titles)
        )

    # T29 — Canonical ausente en páginas 200 indexables (P2)
    n_no_canonical = len(df_no_canonical)
    if HAS_CANONICAL_COL and n_no_canonical > 0:
        add_task(
            'T29', 'P2', 'Canonicals / Ausente',
            f'Añadir canonical self-referencing en {n_no_canonical:,} páginas indexables sin canonical',
            f'{n_no_canonical:,} páginas con status 200 e indexabilidad "Indexable" '
            'no tienen etiqueta canonical. Sin canonical, URLs con parámetros o variantes '
            'pueden generar duplicados no controlados.',
            f'{n_no_canonical:,} URLs con status 200, Indexable y canonical_link_element_1 vacío en SF. '
            'La ausencia de canonical self-referencing permite que variaciones de la URL '
            '(con parámetros de tracking, sesión, UTM…) sean tratadas como URLs independientes '
            'por Googlebot, diluyendo señales de PageRank.',
            'CMS sin implementación de canonical por defecto. '
            'Páginas creadas manualmente fuera del flujo habitual del CMS. '
            'Actualizaciones del CMS que borraron la lógica de canonical.',
            '1. Verificar si el CMS implementa canonical de forma global. '
            '2. Si no: añadir <link rel="canonical" href="{url_actual}"> en el <head> de todas las páginas. '
            '3. Para WordPress/Shopify: activar canonical en el plugin SEO (Yoast, Rank Math, etc.). '
            '4. Re-crawl para confirmar que canonical_link_element_1 = url en todas las páginas.',
            'SF > Canonicals > Missing. Filtrar Status 200 + Indexability = Indexable.',
            'Bajo', 'Medio', 'Bajo', 'Dev + SEO',
            'Re-crawl: 0 páginas indexables sin canonical. '
            'GSC Cobertura: reducción de variantes de URL duplicadas.',
            sample_urls(df_no_canonical, sort_by='impressions' if HAS_GSC else 'url')
        )

    # T30 — Sin H2 en páginas SEO indexables (P2)
    n_no_h2 = len(df_no_h2)
    if HAS_H2_COL and n_no_h2 > 0:
        add_task(
            'T30', 'P2', 'Contenido / Estructura H2',
            f'Añadir H2 a {n_no_h2:,} páginas SEO indexables sin subtítulos',
            f'{n_no_h2:,} páginas de tipo SEO (colecciones, productos, posts) '
            'carecen de etiqueta H2. La ausencia de subtítulos dificulta la comprensión '
            'del contenido por parte de Google.',
            f'{n_no_h2:,} URLs de tipo SEO con h2_1 vacío en SF. '
            'Google usa los H2 para entender la estructura temática de la página '
            'y para generar featured snippets. Sin H2, el contenido es menos escaneable '
            'tanto para usuarios como para bots.',
            'Plantillas de CMS que no incluyen H2 por defecto. '
            'Contenido migrado sin revisar la estructura de headings. '
            'Páginas con contenido mínimo en las que no se añadieron subtítulos.',
            '1. Identificar qué tipos de página afectan más (productos, posts, categorías). '
            '2. Actualizar las plantillas para incluir al menos un H2 con keyword secundaria. '
            '3. Para páginas de alto tráfico: revisar manualmente y redactar subtítulos relevantes. '
            '4. Verificar en re-crawl que h2_1 ya no está vacío.',
            'SF > Headings > H2 Missing or Empty. Filtrar url_type = SEO_TYPES.',
            'Bajo', 'Medio', 'Bajo', 'SEO + CMS',
            'Re-crawl: 0 páginas SEO sin H2. '
            'GSC: mejora en featured snippets y posición media en las URLs corregidas.',
            sample_urls(df_no_h2, sort_by='impressions' if HAS_GSC else 'url')
        )

    # T31 — Title = H1 exacto (P2)
    n_title_eq_h1 = len(df_title_eq_h1)
    if HAS_TITLE_1 and HAS_H1_COL and n_title_eq_h1 > 0:
        add_task(
            'T31', 'P2', 'Metadatos / Title = H1 duplicado',
            f'Diferenciar title tag y H1 en {n_title_eq_h1:,} páginas con texto idéntico',
            f'{n_title_eq_h1:,} páginas tienen el title tag y el H1 con exactamente el mismo texto. '
            'Es una oportunidad perdida: el title puede optimizarse para CTR '
            'y el H1 para la relevancia temática en página.',
            f'{n_title_eq_h1:,} URLs donde title_1 == h1_1 (comparación sin case, sin spaces). '
            'El title se muestra en el SERP y debe maximizar el CTR; el H1 es el heading '
            'principal de la página y debe contextualizar el contenido para el usuario. '
            'Usarlos idénticos no es un error técnico, pero limita la optimización semántica.',
            'Plantillas de CMS que auto-generan el H1 desde el title o viceversa. '
            'Falta de revisión editorial al crear nuevas páginas.',
            '1. Para cada página: redactar el title orientado al CTR en SERP '
            '(incluir número, año, benefit o diferenciador). '
            '2. Mantener el H1 más descriptivo y conversacional para el usuario en página. '
            '3. Ambos deben contener la keyword principal, pero con variación de redacción.',
            'SF > Page Titles > comparar con H1 Headings manualmente o exportar y cruzar en Excel.',
            'Bajo', 'Bajo', 'Bajo', 'SEO',
            'Re-crawl: las páginas corregidas tienen title ≠ H1. '
            'GSC: mejora de CTR en las URLs modificadas.',
            sample_urls(df_title_eq_h1, sort_by='impressions' if HAS_GSC else 'url')
        )

    # T32 — Crawl depth alto >4 con tráfico GSC (P2)
    n_deep = len(df_deep)
    if HAS_DEPTH_COL and n_deep > 0:
        avg_depth = round(df_deep['depth'].mean(), 1) if 'depth' in df_deep.columns else 0
        add_task(
            'T32', 'P2', 'Arquitectura / Crawl Depth',
            f'Reducir profundidad de rastreo en {n_deep:,} URLs importantes (>{T_MAX_DEPTH} clicks)',
            f'{n_deep:,} páginas indexables con señal SEO están a más de {T_MAX_DEPTH} clicks '
            f'de la home (media: {avg_depth} clicks). Googlebot les asigna menor prioridad de rastreo.',
            f'{n_deep:,} URLs con depth > {T_MAX_DEPTH} y señal SEO (impressions > 0 o url_type = SEO_TYPES). '
            f'Profundidad media de las afectadas: {avg_depth} clicks. '
            'Las páginas a más de 4 clicks de la home reciben menos PageRank '
            'y menos frecuencia de rastreo. Regla general: ninguna página importante '
            'debería estar a más de 3-4 clicks.',
            'Arquitectura de categorías muy anidada. '
            'Paginaciones profundas o filtros generando rutas largas. '
            'Enlazado interno insuficiente que no acorta el camino desde la home.',
            '1. Exportar el listado y priorizar por impresiones GSC. '
            '2. Para las URLs más importantes: añadir enlace directo desde la home, '
            'categorías principales o el menú de navegación. '
            '3. Revisar si la estructura de carpetas/categorías puede aplanarse. '
            '4. Añadir las URLs más profundas al sitemap (ya incluidas si T22 se ejecutó).',
            f'SF > All URLs > columna Crawl Depth > filtrar > {T_MAX_DEPTH}. '
            'Cruzar con GSC Rendimiento para priorizar las más vistas.',
            'Bajo', 'Medio', 'Medio', 'SEO + Dev',
            f'Re-crawl: reducción ≥30% de URLs con depth > {T_MAX_DEPTH}. '
            'GSC: mejora de frecuencia de rastreo en las URLs corregidas.',
            sample_urls(df_deep.sort_values('impressions', ascending=False) if HAS_GSC and 'impressions' in df_deep.columns else df_deep)
        )

    # T33 — H1 duplicado en fichas de producto (P2)
    n_dup_h1_products = len(df_dup_h1_products)
    if n_dup_h1_products > 0:
        add_task(
            'T33', 'P2', 'Metadatos / H1 duplicado',
            f'Corregir {n_dup_h1_products:,} fichas de producto con H1 duplicado',
            f'{n_dup_h1_products:,} páginas de producto comparten el mismo H1 con otra ficha. '
            'Google puede confundirse sobre cuál es la página canónica para esa keyword.',
            f'{n_dup_h1_products:,} URLs de /products/ con H1 repetido entre sí. '
            'Indica que el H1 se genera desde el nombre del producto y varios productos comparten nombre o plantilla.',
            f'Los templates de {PLATFORM} suelen usar el nombre del producto como H1. '
            'Si dos productos tienen el mismo nombre (o uno es variante del otro), el H1 queda duplicado.',
            '1. Identificar los grupos de productos con H1 idéntico. '
            '2. Para variantes del mismo producto: consolidar en una sola URL canónica. '
            '3. Para productos distintos: diferenciar el H1 añadiendo el modelo, capacidad, color, etc. '
            '4. Verificar que el H1 incluye la keyword principal de la ficha.',
            f'SF > H1 > filtrar duplicados + filtrar URL contiene /products/.',
            'Bajo', 'Medio', 'Bajo', 'SEO',
            'Re-crawl: 0 fichas de producto con H1 duplicado en el crawl.',
            sample_urls(df_dup_h1_products, sort_by='impressions')
        )

    # T34 — H1 duplicado en colecciones/categorías (P2)
    n_dup_h1_colls = len(df_dup_h1_colls)
    if n_dup_h1_colls > 0:
        add_task(
            'T34', 'P2', 'Metadatos / H1 duplicado',
            f'Corregir {n_dup_h1_colls:,} colecciones/categorías con H1 duplicado',
            f'{n_dup_h1_colls:,} páginas de colección/categoría comparten H1 con otra. '
            'Señal semántica ambigua para Google sobre qué página posicionar para cada categoría.',
            f'{n_dup_h1_colls:,} URLs de colección con H1 repetido entre sí.',
            f'Colecciones padres e hijas con nombres similares, o páginas de paginación que heredan el H1 del template.',
            '1. Revisar el listado y localizar los grupos con H1 idéntico. '
            '2. Diferenciar el H1 añadiendo el contexto de la categoría (ej. "Camisetas" → "Camisetas de Hombre"). '
            '3. Asegurarse de que las páginas de paginación (/page/2) tienen canonical a /page/1 y no duplican el H1.',
            'SF > H1 > filtrar duplicados + filtrar URL contiene /collections/ o /category/.',
            'Bajo', 'Medio', 'Bajo', 'SEO',
            'Re-crawl: 0 colecciones con H1 duplicado entre sí.',
            sample_urls(df_dup_h1_colls, sort_by='impressions')
        )

    # T35 — Meta descriptions duplicadas entre páginas SEO (P2)
    if n_unique_dup_meta > 0:
        n_dup_meta = len(df_dup_meta)
        add_task(
            'T35', 'P2', 'Metadatos / Meta Description duplicada',
            f'Diferenciar {n_dup_meta:,} páginas SEO que comparten meta description',
            f'{n_dup_meta:,} páginas SEO indexables comparten la misma meta description '
            f'({n_unique_dup_meta:,} textos únicos repetidos). '
            'Google puede ignorar estas metas y generar las suyas propias, perdiendo control del snippet.',
            f'{n_dup_meta:,} URLs con meta description duplicada ({n_unique_dup_meta:,} textos distintos usados en más de una página). '
            'Suele ocurrir cuando el template genera una meta description genérica para todos los productos o categorías.',
            f'El template de {PLATFORM} usa una meta description por defecto fija '
            '(ej: "Compra en [tienda]. Envío rápido.") que se repite en todas las páginas sin personalización.',
            '1. Identificar el texto duplicado más frecuente y localizar el template que lo genera. '
            '2. Implementar meta description dinámica: [Keyword página] — [diferenciador]. '
            '3. Priorizar las URLs con más impresiones en GSC para escritura manual. '
            '4. Para el resto: configurar el template con variables de nombre, categoría y marca.',
            'SF > Meta Description > Duplicada + filtrar Indexabilidad = Indexable.',
            'Bajo', 'Medio', 'Bajo', 'SEO',
            'Re-crawl: 0 páginas SEO con meta description compartida con otra URL.',
            sample_urls(df_dup_meta, sort_by='impressions')
        )

    # T36 — Links internos a páginas noindex (P2)
    n_noindex_linked = len(df_noindex_linked)
    if n_noindex_linked > 0:
        total_inlinks_wasted = int(df_noindex_linked['inlinks'].sum()) if 'inlinks' in df_noindex_linked.columns else 0
        add_task(
            'T36', 'P2', 'Rastreo / Crawl Budget',
            f'Eliminar o añadir nofollow a {n_noindex_linked:,} enlaces internos que apuntan a páginas noindex',
            f'{n_noindex_linked:,} páginas con status 200 pero marcadas como noindex reciben '
            f'{total_inlinks_wasted:,} inlinks internos en total. '
            'Cada enlace a una página noindex desperdicia crawl budget sin aportar valor SEO.',
            f'{n_noindex_linked:,} URLs: status 200, noindex, con ≥1 inlink interno. '
            f'Inlinks internos consumidos en estas páginas: {total_inlinks_wasted:,}. '
            'Googlebot sigue estos enlaces y rastrear páginas noindex es tiempo de crawl perdido.',
            'El enlazado interno del site (menú, footer, bloques de categorías, breadcrumbs) '
            'apunta a páginas que se han marcado posteriormente como noindex sin actualizar los enlaces.',
            '1. Exportar el listado completo y cruzar con SF > All Inlinks para localizar las páginas origen. '
            '2. Para cada URL noindex con inlinks: decidir si eliminar el enlace o añadir rel="nofollow". '
            '3. Revisar menú de navegación, footer y breadcrumbs como fuentes más comunes. '
            '4. Opción alternativa: revisar si la página debería seguir siendo noindex.',
            "SF > Filtrar Indexabilidad ≠ Indexable + Status 200 + Inlinks > 0. "
            "SF > All Inlinks para localizar las páginas origen de cada enlace.",
            'Bajo', 'Medio', 'Bajo', 'SEO + Dev',
            'Re-crawl: 0 páginas noindex con inlinks internos follow activos.',
            sample_urls(df_noindex_linked, sort_by='inlinks')
        )

    # T37 — /collections/all indexable (P1, Shopify)
    if IS_SHOPIFY and len(df_collections_all) > 0:
        n_coll_all = len(df_collections_all)
        add_task(
            'T37', 'P1', f'Indexación / {PLATFORM}',
            f'Añadir noindex a /collections/all ({n_coll_all:,} URL indexable)',
            f'/collections/all es una colección automática de Shopify que lista todos los productos '
            'sin estructura ni intención de búsqueda definida. No debe indexarse.',
            f'{n_coll_all:,} URL(s) de /collections/all detectadas como indexables en el crawl.',
            'Shopify genera /collections/all por defecto y no aplica noindex automáticamente. '
            'Esta página compite internamente con las colecciones específicas y no tiene valor SEO propio.',
            '1. En el tema de Shopify, editar el template collection.liquid o sections/collection.liquid. '
            '2. Añadir: {% if collection.handle == "all" %}<meta name="robots" content="noindex">{% endif %}. '
            '3. Alternativa: añadir Disallow: /collections/all en robots.txt. '
            '4. Comprobar que no hay tráfico orgánico significativo en GSC antes de noindexar.',
            'SF > All URLs > filtrar URL contiene /collections/all + Indexabilidad = Indexable.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Re-crawl: /collections/all no aparece como Indexable.',
            sample_urls(df_collections_all)
        )

    # T38 — /collections/vendors y /collections/types indexables (P1, Shopify)
    if IS_SHOPIFY and len(df_system_collections) > 0:
        n_sys_colls = len(df_system_collections)
        add_task(
            'T38', 'P1', f'Indexación / {PLATFORM}',
            f'Añadir noindex a {n_sys_colls:,} colecciones de sistema de Shopify (/vendors, /types)',
            f'{n_sys_colls:,} URL(s) de colecciones de sistema de Shopify son indexables. '
            'Estas páginas automáticas (vendors, types) no tienen valor SEO y diluten la autoridad.',
            f'{n_sys_colls:,} URL(s) con patrón /collections/vendors o /collections/types indexadas.',
            'Shopify genera automáticamente páginas de vendedor (/collections/vendors?q=) y tipo '
            '(/collections/types?q=) que raramente tienen valor SEO propio.',
            '1. Añadir Disallow: /collections/vendors y Disallow: /collections/types en robots.txt. '
            '2. O implementar noindex en el template para estas colecciones. '
            '3. Verificar en GSC que no reciben tráfico orgánico relevante antes de aplicar.',
            'SF > All URLs > filtrar URL contiene /collections/vendors o /collections/types.',
            'Bajo', 'Bajo', 'Bajo', 'Dev',
            'Re-crawl: 0 URLs de /collections/vendors o /collections/types indexables.',
            sample_urls(df_system_collections)
        )

    # T39 — URLs de producto con scope de colección indexables (P1, Shopify)
    if IS_SHOPIFY and len(df_scoped_products) > 0:
        n_scoped = len(df_scoped_products)
        add_task(
            'T39', 'P1', f'Indexación / {PLATFORM}',
            f'Corregir {n_scoped:,} URLs de producto con scope de colección indexables',
            f'{n_scoped:,} URLs siguen el patrón /collections/{{handle}}/products/{{handle}}. '
            'Son duplicados de /products/{{handle}} y pueden generar contenido duplicado si se indexan.',
            f'{n_scoped:,} URLs indexables con patrón /collections/X/products/Y. '
            'Cada una tiene su equivalente canónica en /products/Y.',
            'Los temas de Shopify pueden enlazar a productos usando la URL con contexto de colección '
            '(típico en breadcrumbs y listas de colección). Si el canonical no apunta a /products/, '
            'Google puede indexar ambas versiones.',
            '1. Verificar que el canonical de estas URLs apunta a /products/{handle}. '
            '2. Si el canonical es correcto: revisar los enlaces internos para que apunten a /products/. '
            '3. Actualizar breadcrumbs y templates de colección para generar URLs /products/ directas. '
            '4. Añadir Disallow: /collections/*/products/ en robots.txt como medida de bloqueo.',
            'SF > All URLs > filtrar URL contiene /collections/ y /products/ simultáneamente.',
            'Bajo', 'Alto', 'Medio', 'Dev',
            'Re-crawl: 0 URLs con patrón /collections/X/products/Y con estado Indexable '
            'sin canonical correcto a /products/.',
            sample_urls(df_scoped_products, sort_by='impressions')
        )

    # T40 — Tag pages de colección indexables (P1, Shopify)
    if IS_SHOPIFY and len(df_tag_pages) > 0:
        n_tags = len(df_tag_pages)
        add_task(
            'T40', 'P1', f'Indexación / {PLATFORM}',
            f'Revisar {n_tags:,} páginas de etiqueta de colección indexables',
            f'{n_tags:,} URLs de etiqueta de Shopify (/collections/handle/tag) son indexables. '
            'Estas páginas tienen escaso contenido único y suelen canibalizar las colecciones principales.',
            f'{n_tags:,} URLs con patrón /collections/{{handle}}/{{tag}} detectadas como indexables. '
            'Evaluar si alguna tiene intención de búsqueda real antes de noindexar.',
            'Shopify genera páginas de etiqueta automáticamente para cada tag asignado a productos. '
            'Sin contenido editorial propio, estas páginas son thin content estructural.',
            '1. Auditar en GSC si alguna tag page recibe tráfico orgánico significativo. '
            '2. Para tags sin tráfico: añadir <meta name="robots" content="noindex"> en el template. '
            '3. Revisar si los tags pueden consolidarse como colecciones reales con contenido. '
            '4. Añadir Disallow para tags en robots.txt como alternativa rápida.',
            'SF > All URLs > filtrar URL con patrón /collections/X/Y (doble segmento).',
            'Bajo', 'Medio', 'Bajo', 'SEO + Dev',
            'Re-crawl: 0 tag pages con status Indexable sin intención de búsqueda validada.',
            sample_urls(df_tag_pages, sort_by='impressions')
        )

    # T41 — Variantes de producto indexables (P1, Shopify)
    if IS_SHOPIFY and len(df_variants) > 0:
        n_variants = len(df_variants)
        add_task(
            'T41', 'P1', f'Indexación / {PLATFORM}',
            f'Eliminar indexación de {n_variants:,} URLs de variante de producto (?variant=)',
            f'{n_variants:,} URLs de variante de producto con parámetro ?variant=XXXXX son indexables. '
            'Son duplicados exactos de la ficha de producto base.',
            f'{n_variants:,} URLs indexables con parámetro ?variant= en el crawl. '
            'Cada URL de variante es idéntica a /products/{{handle}} salvo por el selector de variante JS.',
            'Shopify genera URLs únicas por variante de producto. '
            'Si el canonical de estas URLs no apunta a la ficha base, '
            'Google las puede tratar como páginas independientes con contenido duplicado.',
            '1. Verificar que el canonical de las URLs ?variant= apunta a /products/{handle} (sin parámetros). '
            '2. Si el canonical es correcto, el riesgo es menor — pero conviene bloquear en robots. '
            '3. Añadir en robots.txt: Disallow: *?variant=. '
            '4. Revisar en GSC si alguna URL de variante aparece indexada.',
            'SF > All URLs > filtrar URL contiene ?variant= + Indexabilidad = Indexable.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Re-crawl: 0 URLs con ?variant= en estado Indexable.',
            sample_urls(df_variants, sort_by='impressions')
        )

    # T42 — Product schema ausente en fichas de producto (P1)
    if HAS_SD_COL and len(df_no_product_schema) > 0:
        n_no_prod_sd = len(df_no_product_schema)
        add_task(
            'T42', 'P1', 'Datos Estructurados / Product',
            f'Implementar schema Product en {n_no_prod_sd:,} fichas de producto que carecen de él',
            f'{n_no_prod_sd:,} fichas de producto indexables no tienen schema de tipo Product. '
            'Sin este schema Google no puede mostrar rich results de producto (precio, disponibilidad, valoraciones).',
            f'{n_no_prod_sd:,} URLs /products/ sin schema Product detectado por SF. '
            'Los rich results de producto pueden incrementar el CTR un 20-30% en búsquedas de producto.',
            f'El tema de {PLATFORM} no implementa schema Product, lo implementa de forma incompleta, '
            'o lo genera mediante JavaScript (no visible para el crawler de SF).',
            '1. Verificar con el Rich Results Test de Google si la ficha pasa la validación. '
            '2. Implementar JSON-LD con Product incluyendo: name, description, image, sku, offers '
            '(price, priceCurrency, availability, url). '
            '3. Añadir brand y aggregateRating si hay valoraciones. '
            '4. En Shopify: usar la app Schema Plus o implementarlo en el template product.liquid.',
            'SF > Structured Data > filtrar URL /products/ + columna Structured Data no contiene "Product". '
            'Validar con: https://search.google.com/test/rich-results',
            'Medio', 'Alto', 'Bajo', 'Dev',
            'Rich Results Test: todas las fichas de producto pasan la validación de Product schema. '
            'GSC > Mejoras: 0 errores de schema Product.',
            sample_urls(df_no_product_schema, sort_by='impressions')
        )

    # T43 — AggregateRating/Review ausente en fichas de producto (P1)
    if HAS_SD_COL and len(df_no_rating_products) > 0:
        n_no_rating_prod = len(df_no_rating_products)
        add_task(
            'T43', 'P1', 'Datos Estructurados / Reviews',
            f'Implementar schema AggregateRating en {n_no_rating_prod:,} fichas de producto',
            f'{n_no_rating_prod:,} fichas de producto carecen de schema AggregateRating o Review. '
            'Las estrellas de valoración en el snippet SERP pueden incrementar el CTR significativamente.',
            f'{n_no_rating_prod:,} URLs /products/ sin AggregateRating ni Review en Structured Data.',
            'Las valoraciones del producto no están implementadas en el schema JSON-LD, '
            'aunque puedan existir visualmente en la página (app de reviews no integrada en el markup).',
            '1. Integrar la app de reviews (Judge.me, Yotpo, Okendo…) con schema AggregateRating. '
            '2. Añadir al JSON-LD del Product: "aggregateRating": {"@type": "AggregateRating", '
            '"ratingValue": "{{rating}}", "reviewCount": "{{count}}"}. '
            '3. Solo incluir si hay valoraciones reales — Google penaliza el schema con datos falsos. '
            '4. Validar con Rich Results Test.',
            'SF > Structured Data > filtrar URL /products/ + sin AggregateRating.',
            'Medio', 'Alto', 'Bajo', 'Dev',
            'GSC > Mejoras: rich results de producto con estrellas activos. '
            'Rich Results Test: pasa validación con AggregateRating.',
            sample_urls(df_no_rating_products, sort_by='impressions')
        )

    # T44 — AggregateRating/Review ausente en colecciones (P2)
    if HAS_SD_COL and len(df_no_rating_colls) > 0:
        n_no_rating_colls = len(df_no_rating_colls)
        add_task(
            'T44', 'P2', 'Datos Estructurados / Reviews',
            f'Valorar implementar schema AggregateRating en {n_no_rating_colls:,} colecciones',
            f'{n_no_rating_colls:,} páginas de colección no tienen schema de valoración. '
            'Añadir valoraciones agregadas en las colecciones puede mejorar el CTR en búsquedas de categoría.',
            f'{n_no_rating_colls:,} colecciones indexables sin AggregateRating o Review.',
            'Las apps de reviews implementan el schema a nivel de ficha de producto pero no en colecciones.',
            '1. Evaluar si la página de colección muestra valoraciones de los productos listados. '
            '2. Si sí: implementar AggregateRating como media de los productos. '
            '3. Solo aplicar donde el resultado visual sea real y consistente.',
            'SF > Structured Data > filtrar URL /collections/ + sin AggregateRating.',
            'Medio', 'Medio', 'Medio', 'Dev',
            'Rich Results Test: colecciones con AggregateRating pasan validación.',
            sample_urls(df_no_rating_colls, sort_by='impressions')
        )

    # T45 — Organization/WebSite schema ausente en homepage (P1)
    if HAS_SD_COL and len(df_no_org_schema) > 0:
        add_task(
            'T45', 'P1', 'Datos Estructurados / Organización',
            'Implementar schema Organization y WebSite en la homepage',
            'La homepage no tiene schema Organization ni WebSite. '
            'Este schema es imprescindible para el Knowledge Panel y para que Google '
            'entienda la entidad del negocio.',
            '1 homepage indexable sin schema Organization, WebSite ni LocalBusiness.',
            'El tema no implementa schema de entidad en la homepage o se genera por JS.',
            '1. Añadir en la homepage un JSON-LD con Organization: name, url, logo, sameAs '
            '(redes sociales), contactPoint. '
            '2. Añadir WebSite con SearchAction para el sitelinks searchbox si aplica. '
            '3. Si es un negocio local: usar LocalBusiness con address, telephone, openingHours.',
            'SF > Structured Data > filtrar URL = homepage + sin Organization ni WebSite.',
            'Bajo', 'Alto', 'Bajo', 'Dev',
            'GSC > Mejoras: Knowledge Panel enriquecido. Rich Results Test: pasa con Organization.',
            sample_urls(df_no_org_schema)
        )

    # T46 — BlogPosting schema ausente en artículos de blog (P2)
    if HAS_SD_COL and len(df_no_blogpost_schema) > 0:
        n_no_blog_sd = len(df_no_blogpost_schema)
        add_task(
            'T46', 'P2', 'Datos Estructurados / Blog',
            f'Implementar schema BlogPosting/Article en {n_no_blog_sd:,} artículos de blog',
            f'{n_no_blog_sd:,} artículos de blog indexables no tienen schema BlogPosting ni Article. '
            'Este schema mejora la visibilidad en búsquedas de contenido e IA Overviews.',
            f'{n_no_blog_sd:,} URLs de blog sin BlogPosting, Article ni NewsArticle en Structured Data.',
            'El tema no implementa schema editorial en el template de artículos de blog.',
            '1. Añadir JSON-LD BlogPosting en el template de artículo con: headline, datePublished, '
            'dateModified, author (Person), image, description, url, publisher (Organization). '
            '2. Vincular author con schema Person para señales E-E-A-T. '
            '3. Incluir los artículos con más tráfico como prioridad.',
            'SF > Structured Data > filtrar URL contiene /blogs/ + sin BlogPosting.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Rich Results Test: artículos pasan validación BlogPosting.',
            sample_urls(df_no_blogpost_schema, sort_by='impressions')
        )

    # T47 — Person/Author schema ausente en artículos de blog (P2)
    if HAS_SD_COL and len(df_no_author_schema) > 0:
        n_no_author = len(df_no_author_schema)
        add_task(
            'T47', 'P2', 'Datos Estructurados / E-E-A-T',
            f'Implementar schema Person (autor) en {n_no_author:,} artículos de blog',
            f'{n_no_author:,} artículos de blog carecen de schema Person para el autor. '
            'Las señales de autoría son clave para E-E-A-T, especialmente en nichos de salud, '
            'finanzas o cualquier temática YMYL.',
            f'{n_no_author:,} artículos de blog sin schema Person ni Author.',
            'El schema BlogPosting no incluye el nodo Person para el autor, '
            'o los artículos no tienen autoría asignada en el tema.',
            '1. Crear una página de autor por cada redactor del blog con su nombre, bio, '
            'foto y enlaces a redes profesionales (LinkedIn, Twitter). '
            '2. Implementar en el schema BlogPosting: "author": {"@type": "Person", '
            '"name": "...", "url": "...", "sameAs": [...]}. '
            '3. Añadir la "tarjeta de autor" visible en el artículo para reforzar E-E-A-T on-page.',
            'SF > Structured Data > filtrar URL /blogs/ + sin Person.',
            'Bajo', 'Medio', 'Bajo', 'Dev + SEO',
            'Artículos con schema Person validado en Rich Results Test. '
            'Tarjeta de autor visible en el HTML de cada artículo.',
            sample_urls(df_no_author_schema, sort_by='impressions')
        )

    # T48 — BreadcrumbList schema ausente en productos y colecciones (P2)
    if HAS_SD_COL and len(df_no_breadcrumb_schema) > 0:
        n_no_bc = len(df_no_breadcrumb_schema)
        add_task(
            'T48', 'P2', 'Datos Estructurados / Breadcrumb',
            f'Implementar schema BreadcrumbList en {n_no_bc:,} páginas de producto y colección',
            f'{n_no_bc:,} páginas (productos y colecciones) no tienen schema BreadcrumbList. '
            'Los breadcrumbs en los snippets SERP mejoran la comprensión de la arquitectura y el CTR.',
            f'{n_no_bc:,} URLs de /products/ y /collections/ sin BreadcrumbList en Structured Data.',
            'El tema no genera schema de breadcrumb, o lo hace visualmente pero sin JSON-LD.',
            '1. Implementar BreadcrumbList JSON-LD en los templates de producto y colección. '
            '2. La estructura debe reflejar la jerarquía real: Home > Categoría > Subcategoría > Producto. '
            '3. Asegurarse de que los breadcrumbs visuales y el schema coinciden. '
            '4. Validar con Rich Results Test.',
            'SF > Structured Data > filtrar URL /products/ o /collections/ + sin BreadcrumbList.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'GSC > Mejoras: breadcrumbs activos. Rich Results Test: BreadcrumbList validado.',
            sample_urls(df_no_breadcrumb_schema, sort_by='impressions')
        )


    # ──────────────────────────────────────────────────────────────────────────────
    # TANDA 1 — Checks sobre señales SF infrautilizadas (T49–T56)
    # ──────────────────────────────────────────────────────────────────────────────

    def sample_link_dests(df_links_sub, n=5):
        """URLs destino únicas de un subconjunto del All Links."""
        if df_links_sub is None or len(df_links_sub) == 0:
            return 'N/D'
        return '\n'.join(df_links_sub['link_dest'].drop_duplicates().head(n).tolist())

    # T49 — Enlaces a paginación sin nofollow (P2)
    n_pag_links_follow = len(_links_pag_follow) if _links_pag_follow is not None else 0
    if n_pag_links_follow > 0:
        _n_pag_dest = _links_pag_follow['link_dest'].nunique()
        add_task(
            'T49', 'P2', 'Enlazado / Crawl budget',
            f'Añadir nofollow a {n_pag_links_follow:,} enlaces internos hacia paginación',
            f'{n_pag_links_follow:,} enlaces internos apuntan a {_n_pag_dest:,} URLs de paginación '
            'sin atributo rel="nofollow". Cada uno pasa autoridad a páginas que no deberían competir '
            'en búsqueda y consume presupuesto de rastreo.',
            f'All Links: {n_pag_links_follow:,} enlaces con Follow=True hacia URLs de paginación. '
            f'Destinos únicos: {_n_pag_dest:,}.',
            'Los componentes de paginación del tema/plantilla generan enlaces estándar sin nofollow. '
            'Es el comportamiento por defecto de la mayoría de CMS y themes.',
            '1. Localizar el componente/snippet de paginación en la plantilla. '
            '2. Añadir rel="nofollow" a los enlaces de página 2+ (no a la 1). '
            '3. Mantener la paginación rastreable si los productos solo son accesibles desde ella — '
            'nofollow no impide indexar, solo evita transmitir autoridad. '
            '4. Si las páginas 2+ no aportan valor de búsqueda, valorar además noindex,follow.',
            'SF > Exportación en bloque > Enlaces > Enlaces internos Todo. Filtrar Destino por el patrón '
            'de paginación y columna Seguir = True.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Re-export de All Links: 0 enlaces con Follow=True hacia URLs de paginación.',
            sample_link_dests(_links_pag_follow)
        )

    # T50 — Enlaces a facetas/filtros sin nofollow (P1)
    n_facet_links_follow = len(_links_facet_follow) if _links_facet_follow is not None else 0
    if n_facet_links_follow > 0:
        _n_facet_dest = _links_facet_follow['link_dest'].nunique()
        add_task(
            'T50', 'P1', 'Enlazado / Crawl budget',
            f'Añadir nofollow a {n_facet_links_follow:,} enlaces internos hacia filtros y ordenaciones',
            f'{n_facet_links_follow:,} enlaces internos apuntan a {_n_facet_dest:,} URLs de '
            'facetas/filtros/ordenación sin nofollow. Son la principal fuente de rastreo infinito '
            'en ecommerce: cada combinación de filtros genera una URL nueva.',
            f'All Links: {n_facet_links_follow:,} enlaces con Follow=True hacia URLs de filtros. '
            f'Destinos únicos: {_n_facet_dest:,}.',
            'Los widgets de filtrado y los selectores de orden se renderizan como enlaces <a href> '
            'normales, sin nofollow y sin control de qué combinaciones son rastreables.',
            '1. Añadir rel="nofollow" a todos los enlaces de filtro y de ordenación. '
            '2. Valorar renderizarlos como botones con JS (sin href) para que no sean rastreables. '
            '3. Combinar con noindex + canonical a la categoría limpia en las URLs de faceta. '
            '4. Reforzar en robots.txt con Disallow de los parámetros de orden, que nunca aportan valor.',
            'SF > Exportación en bloque > Enlaces > Enlaces internos Todo. Filtrar Destino por parámetros '
            'de filtro/orden y columna Seguir = True.',
            'Medio', 'Alto', 'Medio', 'Dev + SEO',
            'Re-export: 0 enlaces follow a URLs de faceta. GSC > Estadísticas de rastreo: baja el número '
            'de URLs rastreadas por día sin caer las páginas útiles.',
            sample_link_dests(_links_facet_follow)
        )

    # T51 — Enlaces a URLs sensibles sin nofollow (P2)
    n_sens_links_follow = len(_links_sensitive_follow) if _links_sensitive_follow is not None else 0
    if n_sens_links_follow > 0:
        _n_sens_dest = _links_sensitive_follow['link_dest'].nunique()
        add_task(
            'T51', 'P2', 'Enlazado / Crawl budget',
            f'Añadir nofollow a {n_sens_links_follow:,} enlaces hacia carrito, checkout y cuenta',
            f'{n_sens_links_follow:,} enlaces internos apuntan a {_n_sens_dest:,} URLs de sistema '
            '(carrito, checkout, login, cuenta, búsqueda interna) sin nofollow. Están en todas las '
            'plantillas, así que drenan autoridad de forma sistemática en cada página del site.',
            f'All Links: {n_sens_links_follow:,} enlaces con Follow=True hacia URLs sensibles. '
            f'Destinos únicos: {_n_sens_dest:,}.',
            'Los enlaces de cabecera y footer hacia el área de usuario y el carrito se generan sin '
            'nofollow por defecto en prácticamente todos los themes.',
            '1. Añadir rel="nofollow" a los enlaces de carrito, checkout, login, registro y cuenta. '
            '2. Confirmar que esas URLs ya llevan noindex (ver T15). '
            '3. Bloquear las rutas en robots.txt para cerrar también el rastreo.',
            'SF > All Links: filtrar Destino por /cart, /checkout, /login, /account, /carrito con Seguir = True.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Re-export: 0 enlaces follow hacia rutas de sistema.',
            sample_link_dests(_links_sensitive_follow)
        )

    # T52 — Páginas SEO sin ningún enlace contextual (P1)
    n_no_contextual = len(df_no_contextual)
    if n_no_contextual > 0:
        _pct_boiler = (n_links_boilerplate / (n_links_contextual + n_links_boilerplate) * 100
                       if (n_links_contextual + n_links_boilerplate) > 0 else 0)
        add_task(
            'T52', 'P1', 'Enlazado / Arquitectura',
            f'Enlazar desde contenido {n_no_contextual:,} páginas que solo reciben enlaces de plantilla',
            f'{n_no_contextual:,} páginas SEO indexables no reciben ni un solo enlace desde el cuerpo '
            'de otra página: todos sus enlaces entrantes vienen de menú, header o footer. '
            'Para Google son páginas sin respaldo editorial — el enlace de plantilla se repite en todo '
            'el site y apenas transmite relevancia temática.',
            f'All Links por posición: {n_links_contextual:,} enlaces en Contenido frente a '
            f'{n_links_boilerplate:,} en plantilla ({_pct_boiler:.0f}% del enlazado interno es boilerplate). '
            f'{n_no_contextual:,} páginas SEO sin ningún enlace contextual entrante.',
            'El enlazado interno se apoya en el menú y el footer en lugar de en enlaces desde textos, '
            'guías o fichas relacionadas. Es lo que hace que la autoridad interna quede plana: '
            'todas las páginas reciben lo mismo y ninguna destaca.',
            '1. Priorizar las páginas de esta lista con impresiones en GSC — ahí el retorno es inmediato. '
            '2. Añadir enlaces desde el cuerpo de páginas relacionadas: categorías hacia sus productos '
            'destacados, artículos de blog hacia las categorías que resuelven la intención. '
            '3. Usar anchor text descriptivo, no "ver más" ni "aquí". '
            '4. Objetivo razonable: 3+ enlaces contextuales entrantes en las páginas que quieres posicionar. '
            '5. Si una página no merece ni un enlace desde contenido, plantearse si debe existir.',
            'SF > Exportación en bloque > Enlaces > Enlaces internos Todo. Columna "Posición del enlace": '
            'agrupar por Destino y contar cuántos tienen posición = Contenido.',
            'Alto', 'Alto', 'Bajo', 'SEO + Contenidos',
            'Re-crawl: cada página objetivo tiene al menos un enlace entrante con Posición = Contenido. '
            'Subida de Link Score en las páginas trabajadas.',
            sample_urls(df_no_contextual, sort_by='impressions' if HAS_GSC else 'inlinks')
        )

    # T53 — noindex vía cabecera X-Robots-Tag (P1)
    n_xrobots = len(df_xrobots_noindex)
    if n_xrobots > 0:
        _xr_gsc = ''
        if HAS_GSC and 'impressions' in df_xrobots_noindex.columns:
            _xr_imp = int(df_xrobots_noindex['impressions'].sum())
            if _xr_imp > 0:
                _xr_gsc = f' Suman {_xr_imp:,} impresiones en GSC pese a estar bloqueadas.'
        add_task(
            'T53', 'P1', 'Indexación / Cabeceras',
            f'Revisar {n_xrobots:,} URLs con noindex servido por cabecera HTTP X-Robots-Tag',
            f'{n_xrobots:,} URLs devuelven noindex en la cabecera HTTP X-Robots-Tag. '
            'Es un bloqueo invisible al inspeccionar el HTML: no aparece en la meta robots, '
            'así que suele pasar desapercibido durante meses.' + _xr_gsc,
            f'SF > columna X-Robots-Tag 1 contiene "noindex" en {n_xrobots:,} URLs.',
            'Regla a nivel de servidor, CDN o middleware (nginx, Cloudflare, plugin de seguridad) '
            'que añade la cabecera. Muy habitual que se herede de un entorno de staging o de una '
            'configuración temporal que nunca se revirtió.',
            '1. Revisar la lista y separar lo intencionado de lo accidental. '
            '2. Para lo accidental: localizar la regla en servidor/CDN y eliminarla. '
            '3. Verificar con curl -I <url> que ya no aparece X-Robots-Tag: noindex. '
            '4. Solicitar reindexación en GSC de las URLs recuperadas.',
            'SF > Internal > columna X-Robots-Tag 1. También con curl -I o DevTools > Network > Headers.',
            'Bajo', 'Alto', 'Medio', 'Dev + SEO',
            'curl -I no devuelve X-Robots-Tag: noindex. GSC > Inspección de URL: "La URL puede indexarse".',
            sample_urls(df_xrobots_noindex, sort_by='impressions' if HAS_GSC else 'inlinks')
        )

    # T54 — Meta refresh (P2)
    n_meta_refresh = len(df_meta_refresh)
    if n_meta_refresh > 0:
        add_task(
            'T54', 'P2', 'Técnico / Redirects',
            f'Sustituir {n_meta_refresh:,} meta refresh por redirects 301 de servidor',
            f'{n_meta_refresh:,} URLs redirigen mediante <meta http-equiv="refresh">. '
            'Google lo interpreta como una señal débil de redirección: transmite peor la autoridad '
            'que un 301 y puede tardar mucho más en consolidar el cambio.',
            f'SF > columna Meta Refresh 1 con valor en {n_meta_refresh:,} URLs.',
            'Redirecciones implementadas a nivel de plantilla o plugin en lugar de en el servidor, '
            'normalmente porque era más rápido de aplicar sin tocar configuración.',
            '1. Identificar el destino de cada meta refresh. '
            '2. Sustituir por un 301 en servidor (.htaccess, nginx, o el gestor de redirects del CMS). '
            '3. Eliminar la etiqueta meta refresh del HTML. '
            '4. Comprobar que no se generan cadenas: origen → destino final en un solo salto.',
            'SF > Internal > columna Meta Refresh 1.',
            'Bajo', 'Medio', 'Bajo', 'Dev',
            'Re-crawl: 0 URLs con Meta Refresh. Las URLs afectadas devuelven 301 directo al destino final.',
            sample_urls(df_meta_refresh, sort_by='impressions' if HAS_GSC else 'inlinks')
        )

    # T55 — Más de un H1 (P2)
    n_multi_h1 = len(df_multi_h1)
    if n_multi_h1 > 0:
        add_task(
            'T55', 'P2', 'On-page / Encabezados',
            f'Dejar un único H1 en {n_multi_h1:,} páginas SEO con varios',
            f'{n_multi_h1:,} páginas SEO indexables tienen dos o más H1. '
            'Diluye la señal del encabezado principal y suele indicar que el logo, un slider o un '
            'módulo promocional está marcado como H1 sin necesidad.',
            f'SF > columna H1-2 con valor en {n_multi_h1:,} páginas indexables de tipo SEO.',
            'Plantillas que marcan como H1 elementos que no son el título del contenido: logotipo, '
            'banner de cabecera, título de un bloque destacado.',
            '1. Revisar la lista y ver qué elemento genera el segundo H1. '
            '2. Dejar como H1 solo el título principal del contenido. '
            '3. Convertir el resto en H2 o en un elemento sin semántica de encabezado (div/span). '
            '4. Comprobar que el H1 restante contiene la keyword principal de la página.',
            'SF > Internal > columnas H1-1 y H1-2. Filtrar donde H1-2 no esté vacío.',
            'Bajo', 'Bajo', 'Bajo', 'Dev',
            'Re-crawl: columna H1-2 vacía en todas las páginas SEO.',
            sample_urls(df_multi_h1, sort_by='impressions' if HAS_GSC else 'inlinks')
        )

    # T56 — Contenido byte-idéntico (P1)
    n_dup_hash = len(df_dup_hash)
    if n_dup_hash > 0:
        _n_hash_groups = df_dup_hash['hash'].nunique()
        add_task(
            'T56', 'P1', 'Contenido / Duplicados',
            f'Resolver {n_dup_hash:,} páginas indexables con contenido idéntico',
            f'{n_dup_hash:,} URLs indexables comparten contenido byte a byte con otra URL '
            f'({_n_hash_groups:,} grupos de duplicados). No es contenido "parecido": el HTML es '
            'exactamente el mismo, así que Google elegirá una y descartará el resto.',
            f'SF > columna Hash: {n_dup_hash:,} URLs indexables con hash repetido, '
            f'agrupadas en {_n_hash_groups:,} conjuntos.',
            'URLs alternativas que sirven la misma página: con y sin parámetros, con y sin barra final, '
            'variantes de idioma sin traducir, o la misma ficha accesible por varias rutas.',
            '1. Revisar cada grupo del Excel (columna grupo_dup_hash) y decidir la URL canónica. '
            '2. Añadir canonical de las duplicadas hacia la elegida. '
            '3. Si son URLs accesibles por rutas distintas, redirigir con 301 a la canónica. '
            '4. Corregir los enlaces internos para que apunten directamente a la canónica.',
            'SF > Internal > columna Hash. Ordenar por Hash y buscar valores repetidos.',
            'Medio', 'Alto', 'Medio', 'SEO + Dev',
            'Re-crawl: 0 grupos de hash duplicado entre URLs indexables, o todas las duplicadas '
            'con canonical apuntando a la principal.',
            sample_urls(df_dup_hash, sort_by='impressions' if HAS_GSC else 'inlinks')
        )

    print(f"  Total tareas: {len(tasks)}")

    # ── Detail DataFrames por tarea (para descargas en la UI) ─────────────────
    _DETAIL_OPT = [
        'status', 'indexable', 'indexability_status',
        'title', 'title_len',
        'meta_desc', 'meta_desc_len',
        'h1', 'h1_2', 'h2', 'canonical', 'meta_robots', 'x_robots', 'meta_refresh',
        'word_count', 'text_ratio', 'structured_data', 'hash',
        'inlinks', 'link_score', 'depth', 'folder_depth', 'outlinks', 'external_outlinks',
        'redirect_url', 'redirect_type', 'response_time',
        'impressions', 'clicks', 'ctr', 'position',
        'similarity', 'near_duplicates',
    ]

    def _build_detail_df(df_sub):
        if df_sub is None or len(df_sub) == 0:
            return None
        cols = ['url'] + [c for c in _DETAIL_OPT if c in df_sub.columns]
        out = df_sub[cols].reset_index(drop=True)
        if 'impressions' in out.columns:
            out = out.sort_values('impressions', ascending=False)
        return out

    _task_df_map = {
        'T01': df_ca,               'T02': df_5xx,              'T03': df_4xx,
        'T04': df_301,              'T05': df_double_slash_all,
        'T06': df_cart_reco_indexable, 'T07': df_paginaciones_indexable,
        'T08': df_no_meta,          'T09': df_no_h1,
        'T10': df_seo_demand,       'T11': df_pos_11_20,
        'T12': df_low_ctr,          'T13': df_short_title,
        'T15': df_sensitive,        'T16': df_facets,
        'T17': df_non_self_canonical, 'T18': df_thin,
        'T19': df_302,              'T20': df_orphans,
        'T21': df_noindex_in_sitemap, 'T22': df_missing_from_sitemap,
        'T23': df_slow,             'T24': df_parametered,
        'T25': df_long_urls,        'T26': df_dup_titles,
        'T27': df_noindex_with_gsc, 'T28': df_long_titles,
        'T29': df_no_canonical,     'T30': df_no_h2,
        'T31': df_title_eq_h1,      'T32': df_deep,
        'T33': df_dup_h1_products,  'T34': df_dup_h1_colls,
        'T35': df_dup_meta,         'T36': df_noindex_linked,
        'T37': df_collections_all,  'T38': df_system_collections,
        'T39': df_scoped_products,  'T40': df_tag_pages,
        'T41': df_variants,         'T42': df_no_product_schema,
        'T43': df_no_rating_products, 'T44': df_no_rating_colls,
        'T45': df_no_org_schema,    'T46': df_no_blogpost_schema,
        'T47': df_no_author_schema, 'T48': df_no_breadcrumb_schema,
        'T52': df_no_contextual,    'T53': df_xrobots_noindex,
        'T54': df_meta_refresh,     'T55': df_multi_h1,
        'T56': df_dup_hash,
    }

    _task_ids_generated = {t['ID'] for t in tasks}

    # ── DataFrames enriquecidos con All Links (T03/T04) ───────────────────────────
    _prebuilt_detail_dfs = {}
    if HAS_LINKS and _df_links is not None:
        # T03 — 404s: una fila por enlace entrante (origen → 404)
        if 'T03' in _task_ids_generated and len(df_4xx) > 0:
            # Normalizar trailing slash para matching consistente
            _urls_4xx = set(df_4xx['url'].str.rstrip('/').tolist())
            _links_404 = _df_links[_df_links['link_dest'].isin(_urls_4xx)].copy()
            if len(_links_404) > 0:
                _gsc_cols_4xx = [c for c in ['impressions', 'clicks', 'position'] if c in df_4xx.columns]
                _4xx_meta = df_4xx[['url'] + _gsc_cols_4xx].rename(columns={'url': 'link_dest'})
                _links_404 = _links_404.merge(_4xx_meta, on='link_dest', how='left')
                _links_404 = _links_404.rename(columns={
                    'link_dest':   'url_404',
                    'link_source': 'pagina_origen',
                    'anchor':      'texto_ancla',
                    'alt_text':    'texto_alt',
                })
                _out_cols_404 = ['url_404', 'pagina_origen', 'texto_ancla', 'es_imagen']
                if 'texto_alt' in _links_404.columns: _out_cols_404.append('texto_alt')
                _out_cols_404 += [c for c in ['impressions', 'clicks', 'position'] if c in _links_404.columns]
                _links_404 = _links_404[[c for c in _out_cols_404 if c in _links_404.columns]].reset_index(drop=True)
                if 'impressions' in _links_404.columns:
                    _links_404 = _links_404.sort_values('impressions', ascending=False)
                _prebuilt_detail_dfs['T03'] = _links_404
                print(f"  T03 enriquecido: {len(_links_404):,} enlaces a URLs 4xx")

        # T04 — 301s: una fila por enlace entrante (origen → redirect)
        if 'T04' in _task_ids_generated and len(df_301) > 0:
            _urls_301 = set(df_301['url'].str.rstrip('/').tolist())
            _links_301 = _df_links[_df_links['link_dest'].isin(_urls_301)].copy()
            if len(_links_301) > 0:
                _301_extra = ['redirect_url'] if 'redirect_url' in df_301.columns else []
                _301_meta = df_301[['url'] + _301_extra].rename(columns={'url': 'link_dest', 'redirect_url': 'redirige_a'})
                _links_301 = _links_301.merge(_301_meta, on='link_dest', how='left')
                _links_301 = _links_301.rename(columns={
                    'link_dest':   'url_redirect',
                    'link_source': 'pagina_origen',
                    'anchor':      'texto_ancla',
                    'alt_text':    'texto_alt',
                })
                _out_cols_301 = ['url_redirect']
                if 'redirige_a' in _links_301.columns: _out_cols_301.append('redirige_a')
                _out_cols_301 += ['pagina_origen', 'texto_ancla', 'es_imagen']
                if 'texto_alt' in _links_301.columns: _out_cols_301.append('texto_alt')
                _links_301 = _links_301[[c for c in _out_cols_301 if c in _links_301.columns]].reset_index(drop=True)
                _prebuilt_detail_dfs['T04'] = _links_301
                print(f"  T04 enriquecido: {len(_links_301):,} enlaces a URLs 301")

        # T05 — Doble slash: una fila por enlace entrante (quién enlaza a la URL con //)
        if 'T05' in _task_ids_generated and len(df_double_slash_all) > 0:
            _urls_ds = set(df_double_slash_all['url'].str.rstrip('/').tolist())
            _links_ds = _df_links[_df_links['link_dest'].isin(_urls_ds)].copy()
            if len(_links_ds) > 0:
                _links_ds = _links_ds.rename(columns={
                    'link_dest':   'url_doble_slash',
                    'link_source': 'pagina_origen',
                    'anchor':      'texto_ancla',
                    'alt_text':    'texto_alt',
                })
                _out_cols_ds = ['url_doble_slash', 'pagina_origen', 'texto_ancla', 'es_imagen']
                if 'texto_alt' in _links_ds.columns: _out_cols_ds.append('texto_alt')
                _links_ds = _links_ds[[c for c in _out_cols_ds if c in _links_ds.columns]].reset_index(drop=True)
                _prebuilt_detail_dfs['T05'] = _links_ds
                print(f"  T05 enriquecido: {len(_links_ds):,} enlaces a URLs con doble slash")

        # T02 — 5xx: quién enlaza a páginas con error de servidor
        if 'T02' in _task_ids_generated and len(df_5xx) > 0:
            _urls_5xx = set(df_5xx['url'].str.rstrip('/').tolist())
            _links_5xx = _df_links[_df_links['link_dest'].isin(_urls_5xx)].copy()
            if len(_links_5xx) > 0:
                _links_5xx = _links_5xx.rename(columns={
                    'link_dest':   'url_5xx',
                    'link_source': 'pagina_origen',
                    'anchor':      'texto_ancla',
                    'alt_text':    'texto_alt',
                })
                _out_5xx = ['url_5xx', 'pagina_origen', 'texto_ancla', 'es_imagen']
                if 'texto_alt' in _links_5xx.columns: _out_5xx.append('texto_alt')
                _prebuilt_detail_dfs['T02'] = _links_5xx[[c for c in _out_5xx if c in _links_5xx.columns]].reset_index(drop=True)
                print(f"  T02 enriquecido: {len(_links_5xx):,} enlaces a URLs 5xx")

        # T19 — 302s: quién enlaza a redirects temporales (como T04 pero para 302)
        if 'T19' in _task_ids_generated and len(df_302) > 0:
            _urls_302 = set(df_302['url'].str.rstrip('/').tolist())
            _links_302 = _df_links[_df_links['link_dest'].isin(_urls_302)].copy()
            if len(_links_302) > 0:
                _302_extra = ['redirect_url'] if 'redirect_url' in df_302.columns else []
                _302_meta = df_302[['url'] + _302_extra].rename(columns={'url': 'link_dest', 'redirect_url': 'redirige_a'})
                _links_302 = _links_302.merge(_302_meta, on='link_dest', how='left')
                _links_302 = _links_302.rename(columns={
                    'link_dest':   'url_302',
                    'link_source': 'pagina_origen',
                    'anchor':      'texto_ancla',
                    'alt_text':    'texto_alt',
                })
                _out_302 = ['url_302']
                if 'redirige_a' in _links_302.columns: _out_302.append('redirige_a')
                _out_302 += ['pagina_origen', 'texto_ancla', 'es_imagen']
                if 'texto_alt' in _links_302.columns: _out_302.append('texto_alt')
                _prebuilt_detail_dfs['T19'] = _links_302[[c for c in _out_302 if c in _links_302.columns]].reset_index(drop=True)
                print(f"  T19 enriquecido: {len(_links_302):,} enlaces a URLs 302")

        # T25 — URLs largas: actualizar todos los links internos tras renombrar
        if 'T25' in _task_ids_generated and len(df_long_urls) > 0:
            _urls_long = set(df_long_urls['url'].str.rstrip('/').tolist())
            _links_long = _df_links[_df_links['link_dest'].isin(_urls_long)].copy()
            if len(_links_long) > 0:
                _links_long = _links_long.rename(columns={
                    'link_dest':   'url_larga',
                    'link_source': 'pagina_origen',
                    'anchor':      'texto_ancla',
                    'alt_text':    'texto_alt',
                })
                _out_long = ['url_larga', 'pagina_origen', 'texto_ancla', 'es_imagen']
                if 'texto_alt' in _links_long.columns: _out_long.append('texto_alt')
                _prebuilt_detail_dfs['T25'] = _links_long[[c for c in _out_long if c in _links_long.columns]].reset_index(drop=True)
                print(f"  T25 enriquecido: {len(_links_long):,} enlaces a URLs largas")

        # T36 — Links a noindex: el fix ES ir a la página origen y eliminar/nofollow el link
        if 'T36' in _task_ids_generated and len(df_noindex_linked) > 0:
            _urls_noidx = set(df_noindex_linked['url'].str.rstrip('/').tolist())
            _links_noidx = _df_links[_df_links['link_dest'].isin(_urls_noidx)].copy()
            if len(_links_noidx) > 0:
                _noidx_extra = [c for c in ['indexability_status'] if c in df_noindex_linked.columns]
                _noidx_meta = df_noindex_linked[['url'] + _noidx_extra].rename(
                    columns={'url': 'link_dest', 'indexability_status': 'razon_noindex'})
                _links_noidx = _links_noidx.merge(_noidx_meta, on='link_dest', how='left')
                _links_noidx = _links_noidx.rename(columns={
                    'link_dest':   'url_noindex',
                    'link_source': 'pagina_origen',
                    'anchor':      'texto_ancla',
                    'alt_text':    'texto_alt',
                })
                _out_noidx = ['pagina_origen', 'url_noindex']
                if 'razon_noindex' in _links_noidx.columns: _out_noidx.append('razon_noindex')
                _out_noidx += ['texto_ancla', 'es_imagen']
                if 'texto_alt' in _links_noidx.columns: _out_noidx.append('texto_alt')
                _prebuilt_detail_dfs['T36'] = _links_noidx[[c for c in _out_noidx if c in _links_noidx.columns]].sort_values('pagina_origen').reset_index(drop=True)
                print(f"  T36 enriquecido: {len(_links_noidx):,} enlaces a páginas noindex")

        # T07/T16/T24/T32 — URLs indexables problemáticas: saber qué páginas generan esos links
        for _eid, _edf, _ecol in [
            ('T07', df_paginaciones_indexable, 'url_paginacion'),
            ('T16', df_facets,                 'url_faceta'),
            ('T24', df_parametered,            'url_parametro'),
            ('T32', df_deep,                   'url_profunda'),
        ]:
            if _eid in _task_ids_generated and len(_edf) > 0:
                _e_urls = set(_edf['url'].str.rstrip('/').tolist())
                _e_links = _df_links[_df_links['link_dest'].isin(_e_urls)].copy()
                if len(_e_links) > 0:
                    _e_links = _e_links.rename(columns={
                        'link_dest':   _ecol,
                        'link_source': 'pagina_origen',
                        'anchor':      'texto_ancla',
                        'alt_text':    'texto_alt',
                    })
                    _e_out = [_ecol, 'pagina_origen', 'texto_ancla', 'es_imagen']
                    if 'texto_alt' in _e_links.columns: _e_out.append('texto_alt')
                    _prebuilt_detail_dfs[_eid] = _e_links[[c for c in _e_out if c in _e_links.columns]].reset_index(drop=True)
                    print(f"  {_eid} enriquecido: {len(_e_links):,} enlaces")

        # T49/T50/T51 — enlaces que deberían llevar nofollow: el fix se hace en la
        # página origen, así que el Excel se ordena por origen para agrupar el trabajo.
        for _nid, _ndf, _ncol in [
            ('T49', _links_pag_follow,       'url_paginacion'),
            ('T50', _links_facet_follow,     'url_filtro'),
            ('T51', _links_sensitive_follow, 'url_sistema'),
        ]:
            if _nid in _task_ids_generated and _ndf is not None and len(_ndf) > 0:
                _n_links = _ndf.rename(columns={
                    'link_dest':     _ncol,
                    'link_source':   'pagina_origen',
                    'anchor':        'texto_ancla',
                    'link_position': 'posicion_enlace',
                    'link_rel':      'rel_actual',
                })
                _n_out = ['pagina_origen', _ncol, 'texto_ancla', 'posicion_enlace', 'rel_actual']
                _n_out = [c for c in _n_out if c in _n_links.columns]
                _prebuilt_detail_dfs[_nid] = _n_links[_n_out].sort_values('pagina_origen').reset_index(drop=True)
                print(f"  {_nid} enriquecido: {len(_n_links):,} enlaces sin nofollow")

    # ── Detail DFs estándar (resto de tareas) ────────────────────────────────────
    detail_dfs = dict(_prebuilt_detail_dfs)
    for _tid, _df_sub in _task_df_map.items():
        if _tid in detail_dfs:
            continue  # ya tiene versión enriquecida
        if _tid in _task_ids_generated and _df_sub is not None and len(_df_sub) > 0:
            _ddf = _build_detail_df(_df_sub)
            if _ddf is not None:
                detail_dfs[_tid] = _ddf

    print(f"  Detail DFs: {len(detail_dfs)} tareas con URLs exportables")

    # ── Post-procesado: agrupar duplicados para facilitar ejecución ───────────────
    # T26 — Títulos duplicados: agrupar por título + ordenar grupo
    if 'T26' in detail_dfs and 'title' in detail_dfs['T26'].columns:
        _d26 = detail_dfs['T26'].copy()
        _d26['grupo_dup_title'] = _d26.groupby(_d26['title'].str.lower().str.strip()).ngroup() + 1
        _sort_26 = ['grupo_dup_title'] + (['impressions'] if 'impressions' in _d26.columns else ['url'])
        detail_dfs['T26'] = _d26.sort_values(_sort_26, ascending=[True] + [False] * (len(_sort_26) - 1))

    # T56 — Contenido idéntico: agrupar por hash para trabajar grupo a grupo
    if 'T56' in detail_dfs and 'hash' in detail_dfs['T56'].columns:
        _d56 = detail_dfs['T56'].copy()
        _d56['grupo_dup_hash'] = _d56.groupby('hash').ngroup() + 1
        _sort_56 = ['grupo_dup_hash'] + (['impressions'] if 'impressions' in _d56.columns else ['url'])
        detail_dfs['T56'] = _d56.sort_values(_sort_56, ascending=[True] + [False] * (len(_sort_56) - 1))

    # T35 — Meta descriptions duplicadas: agrupar por meta desc
    if 'T35' in detail_dfs and 'meta_desc' in detail_dfs['T35'].columns:
        _d35 = detail_dfs['T35'].copy()
        _d35['grupo_dup_meta'] = _d35.groupby(_d35['meta_desc'].str.lower().str.strip()).ngroup() + 1
        detail_dfs['T35'] = _d35.sort_values('grupo_dup_meta')

    # T33 — H1 duplicado en productos: agrupar por H1
    _h1c = 'h1_1' if 'h1_1' in df.columns else ('h1' if 'h1' in df.columns else None)
    if 'T33' in detail_dfs and _h1c and _h1c in detail_dfs['T33'].columns:
        _d33 = detail_dfs['T33'].copy()
        _d33['grupo_dup_h1'] = _d33.groupby(_d33[_h1c].str.lower().str.strip()).ngroup() + 1
        detail_dfs['T33'] = _d33.sort_values('grupo_dup_h1')

    # T34 — H1 duplicado en colecciones: mismo tratamiento
    if 'T34' in detail_dfs and _h1c and _h1c in detail_dfs['T34'].columns:
        _d34 = detail_dfs['T34'].copy()
        _d34['grupo_dup_h1'] = _d34.groupby(_d34[_h1c].str.lower().str.strip()).ngroup() + 1
        detail_dfs['T34'] = _d34.sort_values('grupo_dup_h1')


    # ──────────────────────────────────────────────────────────────────────────────
    # 7. URLs-PRIORIDAD
    # ──────────────────────────────────────────────────────────────────────────────
    print("\nBuilding URLs-Prioridad...")

    url_prio_rows = []

    def add_url_prio(df_sub, issue_label, prioridad, action, max_n=50, sort_by='impressions'):
        if len(df_sub) == 0:
            return
        df_sub = df_sub.copy()
        if sort_by in df_sub.columns:
            df_sub = df_sub.sort_values(sort_by, ascending=False)
        for _, r in df_sub.head(max_n).iterrows():
            s   = int(r.get('status', 0))
            idx = str(r.get('indexable', r.get('indexability_status', 'N/D')))[:20]
            il  = int(r.get('inlinks', 0))
            d   = int(r.get('depth', 0))
            metrica_sf = f"Status {s} | {idx} | Inlinks {il} | Depth {d}"

            impr    = int(r.get('impressions', 0))
            clicks  = int(r.get('clicks', 0))
            ctr_val = r.get('ctr', 0)
            ctr_pct = ctr_val * 100 if ctr_val <= 1 else ctr_val
            pos     = round(float(r.get('position', 0)), 2)
            gsc_str = f"Impr {impr:,} | Clics {clicks} | CTR {ctr_pct:.1f}% | Pos {pos}" if impr > 0 else "Sin datos GSC"

            url_prio_rows.append({
                'URL': r['url'],
                'Issue principal': issue_label,
                'Prioridad': prioridad,
                'Métricas SF': metrica_sf,
                'Señal GSC': gsc_str,
                'Acción recomendada': action,
            })


    # P0: locale especial
    if SPECIAL_LOCALE and len(df_ca) > 0:
        _sort_ca = 'impressions' if HAS_GSC and 'impressions' in df_ca.columns else None
        add_url_prio(
            df_ca.sort_values(_sort_ca, ascending=False) if _sort_ca else df_ca,
            f'Locale {SPECIAL_LOCALE.upper()} detectado (resto bloqueado por robots.txt)', 'P0',
            f'Confirmar si /{SPECIAL_LOCALE}/ debe indexar. '
            f'Si sí: eliminar Disallow: /{SPECIAL_LOCALE}/ de robots.txt.',
            max_n=5
        )

    # P0: 503
    if n_503 > 0:
        _sort503 = 'inlinks' if HAS_INLINKS_DATA else 'impressions'
        add_url_prio(df_503.sort_values(_sort503, ascending=False) if _sort503 in df_503.columns else df_503,
                     'Error 503 durante crawl', 'P0',
                     'Verificar disponibilidad en producción. Si persiste, escalar a Dev.', max_n=15)

    # P1: 301
    _sort301 = 'inlinks' if HAS_INLINKS_DATA else ('impressions' if HAS_GSC else None)
    add_url_prio(df_301.sort_values(_sort301, ascending=False) if _sort301 and _sort301 in df_301.columns else df_301,
                 'URL redirigida (301) — actualizar enlaces internos', 'P1',
                 'Actualizar enlace(s) para apuntar a la URL destino final.', max_n=30)

    # P1: 404
    _sort404 = 'inlinks' if HAS_INLINKS_DATA else ('impressions' if HAS_GSC else None)
    add_url_prio(df_404.sort_values(_sort404, ascending=False) if _sort404 and _sort404 in df_404.columns else df_404,
                 'URL con error 404 detectada en crawl', 'P1',
                 'Crear redirect 301 a URL equivalente. SF > All Inlinks para priorizar.', max_n=50)

    # P1: double slash (todas las HTML)
    add_url_prio(df_double_slash_all,
                 'URL con doble slash (//) — posible duplicado', 'P1',
                 'Añadir redirect 301 de URL con // a la versión sin //. Corregir en template.', max_n=50, sort_by='inlinks')

    # P1: sin meta desc con impresiones
    if HAS_GSC:
        df_no_meta_impr = df_no_meta[df_no_meta['impressions'] > 0].sort_values('impressions', ascending=False)
        add_url_prio(df_no_meta_impr, 'Sin meta description — URL con tráfico orgánico', 'P1',
                     'Redactar meta description única (120-155 chars) con keyword + CTA.', max_n=30)

    # P1: sin H1 con impresiones
    if HAS_GSC:
        df_no_h1_impr = df_no_h1[df_no_h1['impressions'] > 0].sort_values('impressions', ascending=False)
        add_url_prio(df_no_h1_impr, 'Sin H1 — URL relevante para SEO', 'P1',
                     'Añadir <h1> con keyword principal como primer heading de la página.', max_n=20)

    # P1: cart-reco indexables
    if HAS_CART_RECO and len(df_cart_reco_indexable) > 0:
        add_url_prio(df_cart_reco_indexable,
                     'Cart-recommendations indexable — no debe aparecer en Google', 'P1',
                     'Añadir meta robots noindex o bloquear en robots.txt.', max_n=10)

    # P1: paginations indexables con impresiones
    if HAS_GSC:
        df_pag_gsc = df_paginaciones_indexable[df_paginaciones_indexable['impressions'] > 0]
        if len(df_pag_gsc) > 0:
            add_url_prio(df_pag_gsc, 'Paginación indexada con señal GSC — candidata a canonical', 'P1',
                         'Añadir canonical a la página /1. Evaluar noindex en page/2+.', max_n=20)

    # P1: pos 11-20
    if len(df_pos_11_20) > 0:
        add_url_prio(df_pos_11_20.sort_values('impressions', ascending=False),
                     'Posición 11-20: candidata a página 1', 'P1',
                     'Mejorar contenido, reforzar enlazado interno y optimizar snippet para Top 10.', max_n=30)

    # P1: CTR < umbral en top 10
    if len(df_low_ctr) > 0:
        add_url_prio(df_low_ctr.sort_values('impressions', ascending=False),
                     f'Top 10 con CTR <{T_CTR_LOW*100:.0f}% — snippet poco atractivo', 'P1',
                     'Reescribir title con diferenciador. Meta description con CTA. Evaluar rich snippets.', max_n=25)

    # P1: noindex en sitemap
    if HAS_SITEMAP_DATA and len(df_noindex_in_sitemap) > 0:
        _sort_ni = 'impressions' if HAS_GSC and 'impressions' in df_noindex_in_sitemap.columns else 'inlinks'
        _df_ni = df_noindex_in_sitemap.sort_values(_sort_ni, ascending=False) if _sort_ni in df_noindex_in_sitemap.columns else df_noindex_in_sitemap
        add_url_prio(_df_ni, 'URL no-indexable incluida en sitemap XML', 'P1',
                     'Eliminar URL del sitemap.xml o corregir la directiva noindex/canonical.', max_n=30)

    # P1: noindex con impresiones GSC
    if HAS_GSC and len(df_noindex_with_gsc) > 0:
        add_url_prio(df_noindex_with_gsc.sort_values('impressions', ascending=False),
                     'Página noindex con impresiones orgánicas — posible pérdida de tráfico', 'P1',
                     'Revisar si el noindex es intencional. Si debe indexar: eliminar directiva y añadir al sitemap.', max_n=25)

    # P1: páginas lentas >3s
    if HAS_RESPONSE_TIME and len(df_slow) > 0:
        _sort_slow = 'impressions' if HAS_GSC and 'impressions' in df_slow.columns else 'inlinks'
        _df_slow_s = df_slow.sort_values(_sort_slow, ascending=False) if _sort_slow in df_slow.columns else df_slow
        add_url_prio(_df_slow_s,
                     f'Tiempo de respuesta >{T_SLOW_RESPONSE:.0f}s — penalización Core Web Vitals', 'P1',
                     'Optimizar TTFB: caché servidor, CDN, reducir queries. Objetivo <1.8s.', max_n=20)

    # P1: titles duplicados
    if HAS_TITLE_1 and len(df_dup_titles) > 0:
        _sort_dt = 'impressions' if HAS_GSC and 'impressions' in df_dup_titles.columns else 'inlinks'
        _df_dt = df_dup_titles.sort_values(_sort_dt, ascending=False) if _sort_dt in df_dup_titles.columns else df_dup_titles
        add_url_prio(_df_dt, 'Title duplicado — Google puede ignorar uno de los documentos', 'P1',
                     'Redactar title único por URL con keyword principal diferenciada.', max_n=20)

    # P2: crawl depth alto con tráfico
    if HAS_DEPTH_COL and len(df_deep) > 0:
        _sort_deep = 'impressions' if HAS_GSC and 'impressions' in df_deep.columns else 'inlinks'
        _df_deep_s = df_deep.sort_values(_sort_deep, ascending=False) if _sort_deep in df_deep.columns else df_deep
        add_url_prio(_df_deep_s,
                     f'Crawl depth >{T_MAX_DEPTH} — página importante pero difícil de rastrear', 'P2',
                     'Añadir enlaces internos desde páginas de mayor jerarquía. Revisar arquitectura de categorías.', max_n=20)

    # P2: URLs indexables ausentes del sitemap (muestra las de mayor tráfico)
    if HAS_SITEMAP_DATA and len(df_missing_from_sitemap) > 0:
        _sort_ms = 'impressions' if HAS_GSC and 'impressions' in df_missing_from_sitemap.columns else 'inlinks'
        _df_ms = df_missing_from_sitemap.sort_values(_sort_ms, ascending=False) if _sort_ms in df_missing_from_sitemap.columns else df_missing_from_sitemap
        add_url_prio(_df_ms, 'URL indexable ausente del sitemap XML', 'P2',
                     'Añadir URL al sitemap.xml para facilitar descubrimiento por Googlebot.', max_n=20)

    # P2: H1 duplicado en productos
    if len(df_dup_h1_products) > 0:
        add_url_prio(df_dup_h1_products, 'H1 duplicado — ficha de producto', 'P2',
                     'Diferenciar el H1 añadiendo modelo, variante o característica clave.', max_n=30)

    # P2: H1 duplicado en colecciones
    if len(df_dup_h1_colls) > 0:
        add_url_prio(df_dup_h1_colls, 'H1 duplicado — colección/categoría', 'P2',
                     'Diferenciar el H1 añadiendo contexto de la categoría (ej. "de Hombre", "Outlet").', max_n=30)

    # P2: meta description duplicada con tráfico
    if HAS_GSC and len(df_dup_meta) > 0:
        _df_dup_meta_impr = df_dup_meta[df_dup_meta['impressions'] > 0].sort_values('impressions', ascending=False)
        add_url_prio(_df_dup_meta_impr, 'Meta description duplicada — URL con tráfico', 'P2',
                     'Redactar meta description única (120-155 chars) diferenciada por keyword.', max_n=30)

    # P2: noindex con inlinks
    if len(df_noindex_linked) > 0:
        add_url_prio(df_noindex_linked, 'Página noindex con inlinks internos — crawl budget desperdiciado', 'P2',
                     'Eliminar o añadir nofollow a los enlaces que apuntan a esta URL noindex.', max_n=30, sort_by='inlinks')

    # P1: Shopify — colecciones problemáticas y duplicados
    if IS_SHOPIFY:
        if len(df_collections_all) > 0:
            add_url_prio(df_collections_all, 'Shopify — /collections/all indexable', 'P1',
                         'Añadir noindex en template liquid o Disallow en robots.txt.', max_n=5)
        if len(df_system_collections) > 0:
            add_url_prio(df_system_collections, 'Shopify — colección de sistema indexable (vendors/types)', 'P1',
                         'Añadir Disallow en robots.txt para /collections/vendors y /collections/types.', max_n=10)
        if len(df_scoped_products) > 0:
            add_url_prio(df_scoped_products, 'Shopify — URL producto con scope de colección (/collections/X/products/Y)', 'P1',
                         'Verificar canonical a /products/{handle}. Actualizar enlaces internos.', max_n=30, sort_by='impressions')
        if len(df_tag_pages) > 0:
            add_url_prio(df_tag_pages, 'Shopify — tag page indexable (/collections/handle/tag)', 'P1',
                         'Añadir noindex si no hay intención de búsqueda validada en GSC.', max_n=20, sort_by='impressions')
        if len(df_variants) > 0:
            add_url_prio(df_variants, 'Shopify — URL de variante indexable (?variant=)', 'P1',
                         'Verificar canonical a URL base. Añadir Disallow: *?variant= en robots.txt.', max_n=20, sort_by='impressions')

    # P1: Structured Data críticos
    if HAS_SD_COL:
        if len(df_no_product_schema) > 0:
            add_url_prio(df_no_product_schema, 'Sin schema Product — ficha de producto', 'P1',
                         'Implementar JSON-LD Product con offers, availability y aggregateRating.', max_n=30, sort_by='impressions')
        if len(df_no_rating_products) > 0:
            add_url_prio(df_no_rating_products, 'Sin schema AggregateRating — ficha de producto', 'P1',
                         'Integrar valoraciones de la app de reviews en el JSON-LD del Product.', max_n=30, sort_by='impressions')
        if len(df_no_org_schema) > 0:
            add_url_prio(df_no_org_schema, 'Sin schema Organization/WebSite — homepage', 'P1',
                         'Implementar JSON-LD Organization con name, url, logo y sameAs.', max_n=1)

    # Deduplicar por URL, conservar la de mayor prioridad
    prio_order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
    seen = {}
    for row in url_prio_rows:
        url = row['URL']
        if url not in seen or prio_order.get(row['Prioridad'], 9) < prio_order.get(seen[url]['Prioridad'], 9):
            seen[url] = row

    def _sort_key(r):
        p = prio_order.get(r['Prioridad'], 9)
        if 'Impr' in r['Señal GSC'] and r['Señal GSC'] != 'Sin datos GSC':
            try:
                impr = int(r['Señal GSC'].split('Impr ')[1].split(' |')[0].replace(',', ''))
            except (IndexError, ValueError):
                impr = 0
        else:
            impr = 0
        return (p, -impr)

    url_prio_final = sorted(seen.values(), key=_sort_key)
    print(f"  URLs-Prioridad: {len(url_prio_final)} URLs únicas")


    # ──────────────────────────────────────────────────────────────────────────────
    # 8. OPORTUNIDADES GSC
    # ──────────────────────────────────────────────────────────────────────────────
    print("\nBuilding Oportunidades GSC...")

    gsc_rows = []

    def add_gsc_opp(df_sub, tipo_opp, accion, max_n=80):
        if len(df_sub) == 0:
            return
        for _, r in df_sub.nlargest(max_n, 'impressions').iterrows():
            ctr_val = r.get('ctr', 0)
            ctr_pct = ctr_val * 100 if ctr_val <= 1 else ctr_val
            gsc_rows.append({
                'URL': r['url'],
                'Query': 'N/D (solo GSC por URL en SF)',
                'Impresiones': int(r['impressions']),
                'Clics': int(r['clicks']),
                'CTR': round(ctr_pct / 100, 4),
                'Posición': round(float(r.get('position', 0)), 2),
                'Tipo oportunidad': tipo_opp,
                'Acción recomendada': accion,
            })


    if HAS_GSC:
        add_gsc_opp(df_pos_11_20, 'Posición 11-20',
                    'Optimizar contenido/snippet y reforzar enlazado interno para Top 10.', max_n=80)
        add_gsc_opp(df_low_ctr, f'CTR <{T_CTR_LOW*100:.0f}% en Top 10',
                    'Reescribir title con diferenciador. Meta description con CTA. Considerar schema.', max_n=50)
        add_gsc_opp(df_impr_no_clicks, f'≥{T_IMPRESSIONS_NO_CLICKS} impresiones, 0 clics',
                    'Revisar intent: ¿responde la página a lo que busca el usuario? Mejorar snippet urgente.', max_n=30)

    gsc_seen = {}
    for row in gsc_rows:
        if row['URL'] not in gsc_seen:
            gsc_seen[row['URL']] = row

    gsc_final = sorted(gsc_seen.values(), key=lambda r: -r['Impresiones'])
    print(f"  Oportunidades GSC: {len(gsc_final)} URLs")


    # ──────────────────────────────────────────────────────────────────────────────
    # 9. RESUMEN
    # ──────────────────────────────────────────────────────────────────────────────
    print("\nBuilding Resumen...")

    def r(label, value):
        return {'Métrica': label, 'Valor': value}

    resumen_rows = []

    # Inventario
    resumen_rows += [
        r('▌ INVENTARIO', ''),
        r('Archivo procesado', RUTA_CSV.split('/')[-1]),
        r('Fecha de análisis', datetime.now().strftime('%Y-%m-%d')),
        r('Total filas en CSV', f"{len(df_raw):,}"),
        r('HTML filtradas (text/html)', f"{len(df):,}"),
        r('Datasets disponibles', 'SF + GSC integrado' if HAS_GSC else 'SF (sin datos GSC)'),
        r('', ''),
    ]

    # Cobertura del crawl
    resumen_rows += [
        r('▌ COBERTURA DEL CRAWL', ''),
        r('Total URLs HTML en crawl', f"{total_html:,}"),
        r('Status 200 (OK)', f"{status_200:,}"),
        r('Status 0 (sin respuesta)', f"{status_0:,}"),
        r('Status 301 (redirigidas)', f"{status_301_count:,}"),
        r('Status 404 (no encontradas)', f"{status_404_count:,}"),
        r('Status 5xx (errores servidor)', f"{status_5xx_count:,}"),
        r('', ''),
    ]

    # Indexación
    resumen_rows += [
        r('▌ INDEXACIÓN', ''),
        r('URLs indexables', f"{total_indexable:,}"),
        r('URLs no indexables', f"{total_no_indexable:,}"),
        r('  — Bloqueadas por robots.txt', f"{total_blocked_robots:,}"),
        r('  — Canonicalizadas', f"{total_canonicalized:,}"),
        r('  — Redirigidas', f"{total_redirects_idx:,}"),
        r('  — Con doble slash (//) detectadas', f"{n_ds:,}"),
        r('  — Paginaciones detectadas', f"{n_pag_total:,}"),
        r('  — Paginaciones indexadas', f"{n_pag_index:,}"),
    ]
    if HAS_CART_RECO:
        resumen_rows.append(r('  — Cart-recommendations indexadas', f"{len(df_cart_reco_indexable):,}"))
    resumen_rows.append(r('', ''))

    # Internacional (solo si multilingual)
    if IS_MULTILINGUAL and SITE_LANGS:
        lang_breakdown = ', '.join([f"/{l}/: {lang_indexable.get(l, 0):,}" for l in SITE_LANGS])
        resumen_rows += [
            r('▌ INTERNACIONAL', ''),
            r('Idiomas detectados en crawl', ', '.join(['raíz'] + [f'/{l}/' for l in SITE_LANGS])),
            r('Idiomas con páginas indexables', ', '.join(['root'] + langs_with_indexable)),
            r('Indexables por idioma', f"raíz: {lang_indexable.get('root', 0):,} | {lang_breakdown}"),
        ]
        if SPECIAL_LOCALE:
            resumen_rows += [
                r(f'/{SPECIAL_LOCALE}/ URLs en crawl', f"{ca_url_count:,}"),
                r(f'/{SPECIAL_LOCALE}/ bloqueadas robots.txt', f"N/D — robots.txt bloquea el crawl"),
                r(f'Nota /{SPECIAL_LOCALE}/', f'Ejecutar SF con robots.txt OFF para descubrir todas las URLs /{SPECIAL_LOCALE}/'),
                r('Decisión pendiente', f'Si /{SPECIAL_LOCALE}/ debe indexarse: eliminar Disallow (P0, ver T01)'),
            ]
        resumen_rows.append(r('', ''))

    # Calidad on-page
    resumen_rows += [
        r('▌ CALIDAD ON-PAGE', ''),
        r('Páginas SEO sin meta description', f"{n_no_meta:,}"),
        r('  — Productos sin meta desc', f"{n_no_meta_products:,}"),
        r('  — Colecciones/categorías sin meta desc', f"{n_no_meta_collections:,}"),
        r('  — Páginas estáticas sin meta desc', f"{n_no_meta_pages:,}"),
        r('Páginas SEO sin H1', f"{n_no_h1:,}"),
        r('  — Páginas/posts sin H1', f"{n_no_h1_info:,}"),
        r('Titles cortos (<{} chars) en colecciones'.format(T_TITLE_SHORT_CHARS), f"{n_short_title:,}"),
        r('301 con inlinks (requiere All Inlinks export)', f"{'N/D — exportar SF > All Inlinks' if not HAS_INLINKS_DATA else str(len(df_301[df_301['inlinks'] > 0])) + ' detectadas'}"),
        r('301 total en crawl', f"{status_301_count:,}"),
        r('404 total en crawl', f"{status_404_count:,}"),
        r('', ''),
    ]

    # Señales GSC
    if HAS_GSC:
        resumen_rows += [
            r('▌ SEÑALES GSC', ''),
            r('URLs con datos GSC', f"{len(df_gsc):,}"),
            r('Total impresiones (periodo)', f"{total_impressions:,}"),
            r('Total clics (periodo)', f"{total_clicks:,}"),
            r('CTR global', f"{overall_ctr:.2%}"),
            r(f'URLs en posición {T_POS_OPP_MIN}-{T_POS_OPP_MAX}', f"{len(df_pos_11_20):,}"),
            r(f'URLs top 10 con CTR <{T_CTR_LOW*100:.0f}%', f"{len(df_low_ctr):,}"),
            r(f'URLs con ≥{T_IMPRESSIONS_NO_CLICKS} impr y 0 clics', f"{len(df_impr_no_clicks):,}"),
            r('URLs con demanda y bajo enlazado', f"{n_demand:,}"),
            r('', ''),
        ]

    # Técnico avanzado T21-T32
    resumen_rows.append(r('▌ TÉCNICO AVANZADO (T21–T32)', ''))
    # Sitemaps
    if HAS_SITEMAP_DATA:
        resumen_rows.append(r('URLs noindex incluidas en sitemap', f"{len(df_noindex_in_sitemap):,}"))
        resumen_rows.append(r('URLs indexables ausentes del sitemap', f"{len(df_missing_from_sitemap):,}"))
    else:
        resumen_rows.append(r('Datos de sitemap', 'N/D — activar "Crawl linked XML Sitemaps" en SF'))
    # Velocidad
    if HAS_RESPONSE_TIME:
        resumen_rows.append(r(f'Páginas lentas >{T_SLOW_RESPONSE:.0f}s (status 200 indexable)', f"{len(df_slow):,}"))
    else:
        resumen_rows.append(r('Tiempo de respuesta', 'N/D — activar "Response Time" en SF'))
    # URLs
    resumen_rows.append(r(f'URLs indexables con parámetros (?)', f"{len(df_parametered):,}"))
    resumen_rows.append(r(f'URLs indexables largas (>{T_URL_MAX_LEN} chars)', f"{len(df_long_urls):,}"))
    # Metadatos
    if HAS_TITLE_1:
        resumen_rows.append(r('Páginas con title duplicado', f"{len(df_dup_titles):,} URLs ({n_unique_dup_titles} títulos únicos duplicados)"))
    if HAS_TITLE_LEN:
        resumen_rows.append(r('Titles largos (>60 chars) en indexables', f"{len(df_long_titles):,}"))
    if HAS_TITLE_1 and HAS_H1_COL:
        resumen_rows.append(r('Title = H1 exacto (páginas indexables)', f"{len(df_title_eq_h1):,}"))
    # GSC cruzado
    if HAS_GSC:
        resumen_rows.append(r('Páginas noindex con impresiones GSC', f"{len(df_noindex_with_gsc):,}"))
    # Canonicals / estructura
    if HAS_CANONICAL_COL:
        resumen_rows.append(r('Páginas 200 indexables sin canonical', f"{len(df_no_canonical):,}"))
    # Contenido
    if HAS_H2_COL:
        resumen_rows.append(r('Páginas SEO sin H2', f"{len(df_no_h2):,}"))
    # Arquitectura
    if HAS_DEPTH_COL:
        resumen_rows.append(r(f'Páginas indexables con depth >{T_MAX_DEPTH}', f"{len(df_deep):,}"))
    resumen_rows.append(r('', ''))

    # Top P0
    p0_tasks = [t for t in tasks if t['Prioridad'] == 'P0']
    resumen_rows.append(r('▌ TOP P0 — CRÍTICO (acción inmediata)', ''))
    if p0_tasks:
        for i, t in enumerate(p0_tasks, 1):
            resumen_rows.append(r(f'P0-{i}', f"[{t['ID']}] {t['Tarea']} — {t['Evidencia'][:200]}"))
    else:
        resumen_rows.append(r('P0', 'Sin issues P0 detectados'))
    resumen_rows.append(r('', ''))

    # Top P1
    p1_tasks = [t for t in tasks if t['Prioridad'] == 'P1']
    resumen_rows.append(r('▌ TOP P1 — IMPORTANTE (próximas semanas)', ''))
    for i, t in enumerate(p1_tasks[:6], 1):
        resumen_rows.append(r(f'P1-{i}', f"[{t['ID']}] {t['Tarea']}"))
    resumen_rows.append(r('', ''))

    # Pendientes
    resumen_rows += [
        r('▌ PENDIENTES DE CONFIRMAR (requieren datos adicionales)', ''),
        r('Sitemaps XML', 'No incluido en el export de SF. Verificar en /sitemap.xml.'),
        r('Hreflang', 'Export SF no incluye columna hreflang. Requiere recrawl con opción específica.' if IS_MULTILINGUAL else 'N/A — IS_MULTILINGUAL=False. Activar si el sitio tiene múltiples idiomas.'),
        r('Schema markup', 'No analizable desde SF exports estándar. Verificar con Rich Results Test.'),
        r('Canibalización', 'No analizable sin queries por URL. Requiere export de GSC Search Analytics o herramienta tipo Semrush/Ahrefs.'),
    ]

    print(f"  Resumen: {len(resumen_rows)} filas")

    # Pre-computar nombres de hojas de detalle para hipervínculos en Tareas
    _task_map_by_id = {t['ID']: t for t in tasks}
    _PRIO_TAB_COLORS = {'P0': 'C0392B', 'P1': 'E67E22', 'P2': 'F1C40F', 'P3': '27AE60'}
    _detail_sheet_map = {}  # tid → sheet_name
    for _tid, _ddf in detail_dfs.items():
        if _ddf is None or len(_ddf) == 0:
            continue
        _tinfo = _task_map_by_id.get(_tid)
        if not _tinfo:
            continue
        _raw = f"{_tid} - {_tinfo['Tarea']}"
        _raw = re.sub(r'[/\\*?\[\]:]', '-', _raw)
        _sname = _raw[:31]
        # garantizar nombres únicos
        if _sname in _detail_sheet_map.values():
            _sname = _raw[:28] + str(len(_detail_sheet_map))
        _detail_sheet_map[_tid] = _sname


    # ──────────────────────────────────────────────────────────────────────────────
    # 10. ESCRITURA DEL EXCEL
    # ──────────────────────────────────────────────────────────────────────────────
    print(f"\nGenerating Excel → {OUTPUT_PATH}")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Estilos globales
    header_fill  = PatternFill('solid', fgColor=HEADER_BG)
    header_font  = Font(bold=True, color=WHITE, size=11, name='Calibri')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    body_font    = Font(size=10, name='Calibri')
    wrap_align   = Alignment(vertical='top', wrap_text=True)
    top_align    = Alignment(vertical='top', wrap_text=False)
    thin_side    = Side(style='thin', color='CCCCCC')
    thin_border  = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    PRIO_FILLS = {
        'P0': PatternFill('solid', fgColor=P0_BG),
        'P1': PatternFill('solid', fgColor=P1_BG),
        'P2': PatternFill('solid', fgColor=P2_BG),
        'P3': PatternFill('solid', fgColor=P3_BG),
    }

    def style_header_row(ws, row_num=1, height=28):
        for cell in ws[row_num]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            cell.border = thin_border
        ws.row_dimensions[row_num].height = height

    def set_col_widths(ws, widths_dict):
        for col_letter, width in widths_dict.items():
            ws.column_dimensions[col_letter].width = width

    def alt_fill(row_idx):
        return PatternFill('solid', fgColor='F0F4F8') if row_idx % 2 == 0 else None


    # ── HOJA 1: RESUMEN ──────────────────────────────────────────────────────────
    ws_res = wb.create_sheet('Resumen')
    ws_res.append(['Métrica', 'Valor'])
    style_header_row(ws_res)

    section_fill = PatternFill('solid', fgColor='2C3E50')
    section_font = Font(bold=True, color=WHITE, size=10, name='Calibri')

    for i, row in enumerate(resumen_rows, start=2):
        ws_res.append([row['Métrica'], row['Valor']])
        cell_m = ws_res.cell(row=i, column=1)
        cell_v = ws_res.cell(row=i, column=2)
        if str(row['Métrica']).startswith('▌'):
            cell_m.fill = section_fill
            cell_m.font = section_font
            cell_v.fill = section_fill
            cell_v.font = section_font
        elif row['Métrica'] != '':
            cell_m.font = Font(size=10, name='Calibri')
            cell_v.font = Font(size=10, name='Calibri')
            if i % 2 == 0:
                cell_m.fill = PatternFill('solid', fgColor='F0F4F8')
                cell_v.fill = PatternFill('solid', fgColor='F0F4F8')
        cell_m.alignment = Alignment(vertical='center', wrap_text=False)
        cell_v.alignment = Alignment(vertical='center', wrap_text=True)

    set_col_widths(ws_res, {'A': 45, 'B': 90})
    ws_res.freeze_panes = 'A2'
    ws_res.sheet_properties.tabColor = '1F4E78'


    # ── HOJA 2: TAREAS ───────────────────────────────────────────────────────────
    ws_tar = wb.create_sheet('Tareas')
    task_headers = ['ID', 'Prioridad', 'Categoría', 'Tarea', 'Descripción corta', 'Evidencia',
                    'Causa probable', 'Qué hacer', 'Dónde detectarlo', 'Esfuerzo', 'Impacto',
                    'Riesgo', 'Responsable', 'Validación', 'URLs ejemplo']
    _n_task_cols = len(task_headers)
    _link_col_idx = _n_task_cols + 1  # columna P
    ws_tar.append(task_headers + ['Ver datos →'])
    style_header_row(ws_tar)
    # Estilo cabecera columna enlace
    _lhc = ws_tar.cell(row=1, column=_link_col_idx)
    _lhc.fill = PatternFill('solid', fgColor='27AE60')
    _lhc.font = Font(bold=True, color=WHITE, size=11, name='Calibri')
    _lhc.alignment = Alignment(horizontal='center', vertical='center')

    for i, task in enumerate(tasks, start=2):
        row_data = [task[h] for h in task_headers]
        ws_tar.append(row_data)
        prio = task['Prioridad']
        fill = PRIO_FILLS.get(prio)
        for col_idx in range(1, _n_task_cols + 1):
            cell = ws_tar.cell(row=i, column=col_idx)
            if fill:
                cell.fill = fill
            cell.font = body_font
            cell.border = thin_border
            col_letter = get_column_letter(col_idx)
            if col_letter == 'O':
                cell.alignment = Alignment(vertical='top', wrap_text=True)
                cell.font = Font(size=9, name='Calibri', color='1155CC')
            else:
                cell.alignment = wrap_align
        # Columna hipervínculo a hoja de detalle
        _lc = ws_tar.cell(row=i, column=_link_col_idx)
        _tid = task['ID']
        if _tid in _detail_sheet_map:
            _lc.value = '→ Ver datos'
            _lc.hyperlink = f"#'{_detail_sheet_map[_tid]}'!A1"
            _lc.font = Font(size=10, name='Calibri', color='1155CC', underline='single')
        else:
            _lc.value = '—'
            _lc.font = Font(size=10, name='Calibri', color='999999')
        if fill:
            _lc.fill = fill
        _lc.border = thin_border
        _lc.alignment = Alignment(vertical='center', horizontal='center')
        ws_tar.row_dimensions[i].height = 90

    set_col_widths(ws_tar, {
        'A': 8, 'B': 10, 'C': 24, 'D': 28, 'E': 34,
        'F': 42, 'G': 28, 'H': 46, 'I': 28, 'J': 10,
        'K': 10, 'L': 10, 'M': 16, 'N': 28, 'O': 60, 'P': 14,
    })
    ws_tar.freeze_panes = 'C2'
    ws_tar.sheet_properties.tabColor = 'C0392B'


    # ── HOJA 3: URLs-PRIORIDAD ───────────────────────────────────────────────────
    ws_url = wb.create_sheet('URLs - Prioridad')
    url_headers = ['URL', 'Issue principal', 'Prioridad', 'Métricas SF', 'Señal GSC', 'Acción recomendada']
    ws_url.append(url_headers)
    style_header_row(ws_url)

    for i, row in enumerate(url_prio_final, start=2):
        ws_url.append([row[h] for h in url_headers])
        prio = row['Prioridad']
        fill = PRIO_FILLS.get(prio)
        for col_idx in range(1, len(url_headers) + 1):
            cell = ws_url.cell(row=i, column=col_idx)
            if fill:
                cell.fill = fill
            cell.font = body_font
            cell.border = thin_border
            col_letter = get_column_letter(col_idx)
            if col_letter == 'A':
                cell.font = Font(size=9, name='Calibri', color='1155CC')
            cell.alignment = top_align
        ws_url.row_dimensions[i].height = 18

    set_col_widths(ws_url, {'A': 70, 'B': 34, 'C': 10, 'D': 36, 'E': 36, 'F': 42})
    ws_url.freeze_panes = 'A2'
    ws_url.sheet_properties.tabColor = 'E67E22'


    # ── HOJA 4: OPORTUNIDADES GSC ────────────────────────────────────────────────
    ws_gsc = wb.create_sheet('Oportunidades GSC')
    gsc_headers = ['URL', 'Query', 'Impresiones', 'Clics', 'CTR', 'Posición', 'Tipo oportunidad', 'Acción recomendada']
    ws_gsc.append(gsc_headers)
    style_header_row(ws_gsc)

    for i, row in enumerate(gsc_final, start=2):
        ws_gsc.append([row[h] for h in gsc_headers])
        for col_idx in range(1, len(gsc_headers) + 1):
            cell = ws_gsc.cell(row=i, column=col_idx)
            cell.border = thin_border
            col_letter = get_column_letter(col_idx)
            if i % 2 == 0:
                cell.fill = PatternFill('solid', fgColor='F0F4F8')
            if col_letter == 'A':
                cell.font = Font(size=9, name='Calibri', color='1155CC')
                cell.alignment = top_align
            else:
                cell.font = body_font
                cell.alignment = top_align
        ws_gsc.row_dimensions[i].height = 18

    set_col_widths(ws_gsc, {'A': 70, 'B': 35, 'C': 12, 'D': 10, 'E': 10, 'F': 12, 'G': 28, 'H': 50})
    ws_gsc.freeze_panes = 'A2'
    ws_gsc.sheet_properties.tabColor = '27AE60'


    # ── HOJAS DE DETALLE POR TAREA ───────────────────────────────────────────────
    _FICHA_FIELDS = [
        'ID', 'Prioridad', 'Categoría', 'Tarea', 'Descripción corta',
        'Causa probable', 'Qué hacer', 'Dónde detectarlo',
        'Esfuerzo', 'Impacto', 'Riesgo', 'Responsable', 'Validación', 'Evidencia',
    ]
    _det_section_fill = PatternFill('solid', fgColor='2C3E50')
    _det_section_font = Font(bold=True, color=WHITE, size=10, name='Calibri')
    _det_key_font     = Font(bold=True, size=9, name='Calibri')
    _det_val_font     = Font(size=9, name='Calibri')
    _det_val_wrap     = Alignment(vertical='top', wrap_text=True)
    _det_data_font    = Font(size=9, name='Calibri')
    _det_url_font     = Font(size=9, name='Calibri', color='1155CC')
    _det_alt_fill     = PatternFill('solid', fgColor='F0F4F8')
    _det_head_font    = Font(bold=True, color=WHITE, size=9, name='Calibri')
    _det_head_align   = Alignment(horizontal='center', vertical='center', wrap_text=True)

    for _tid, _sname in _detail_sheet_map.items():
        _ddf    = detail_dfs[_tid]
        _tinfo  = _task_map_by_id[_tid]
        _prio   = _tinfo.get('Prioridad', 'P2')
        _n_data_cols = len(_ddf.columns)

        ws_det = wb.create_sheet(_sname)
        ws_det.sheet_properties.tabColor = _PRIO_TAB_COLORS.get(_prio, '27AE60')

        # Cabecera de sección — FICHA DE TAREA
        ws_det.cell(row=1, column=1, value='▌ FICHA DE TAREA').fill = _det_section_fill
        ws_det.cell(row=1, column=1).font  = _det_section_font
        ws_det.cell(row=1, column=1).alignment = Alignment(vertical='center')
        ws_det.cell(row=1, column=2, value='').fill = _det_section_fill
        ws_det.row_dimensions[1].height = 22

        # Ficha clave-valor (filas 2 a N+1)
        for _fi, _fkey in enumerate(_FICHA_FIELDS, start=2):
            _fval = _tinfo.get(_fkey, '')
            _kc   = ws_det.cell(row=_fi, column=1, value=_fkey)
            _vc   = ws_det.cell(row=_fi, column=2, value=str(_fval) if _fval else '')
            _kc.font   = _det_key_font
            _vc.font   = _det_val_font
            _kc.alignment = _det_val_wrap
            _vc.alignment = _det_val_wrap
            _kc.border = thin_border
            _vc.border = thin_border
            if _fi % 2 == 0:
                _kc.fill = _det_alt_fill
                _vc.fill = _det_alt_fill

        _ficha_end_row = len(_FICHA_FIELDS) + 1  # última fila de ficha

        # Fila separadora + cabecera sección URLs
        _sec_row   = _ficha_end_row + 2
        _head_row  = _sec_row + 1
        _data_row0 = _head_row + 1

        ws_det.cell(row=_sec_row, column=1, value='▌ URLs AFECTADAS').fill = _det_section_fill
        ws_det.cell(row=_sec_row, column=1).font  = _det_section_font
        ws_det.cell(row=_sec_row, column=1).alignment = Alignment(vertical='center')
        for _mc in range(2, _n_data_cols + 1):
            ws_det.cell(row=_sec_row, column=_mc, value='').fill = _det_section_fill
        ws_det.row_dimensions[_sec_row].height = 22

        # Cabeceras de datos
        _dcols = list(_ddf.columns)
        for _ci, _cn in enumerate(_dcols, start=1):
            _hc = ws_det.cell(row=_head_row, column=_ci, value=_cn)
            _hc.fill      = PatternFill('solid', fgColor=HEADER_BG)
            _hc.font      = _det_head_font
            _hc.alignment = _det_head_align
            _hc.border    = thin_border
        ws_det.row_dimensions[_head_row].height = 24

        # Filas de datos
        for _ri, _row in enumerate(_ddf.itertuples(index=False), start=_data_row0):
            for _ci, _val in enumerate(_row, start=1):
                _dc = ws_det.cell(row=_ri, column=_ci, value=_val)
                _dc.border    = thin_border
                _dc.alignment = Alignment(vertical='top', wrap_text=False)
                if _ri % 2 == 0:
                    _dc.fill = _det_alt_fill
                # columna URL (primera columna): azul
                if _ci == 1:
                    _dc.font = _det_url_font
                else:
                    _dc.font = _det_data_font
            ws_det.row_dimensions[_ri].height = 16

        ws_det.freeze_panes = f'A{_data_row0}'
        # Anchos: col A/B según contenido habitual
        ws_det.column_dimensions['A'].width = 16
        ws_det.column_dimensions['B'].width = 70
        for _ci in range(3, _n_data_cols + 1):
            ws_det.column_dimensions[get_column_letter(_ci)].width = 28

    print(f"  Hojas de detalle: {len(_detail_sheet_map)} tareas")

    # Guardar
    wb.save(OUTPUT_PATH)
    print(f"\n✅ Excel guardado: {OUTPUT_PATH}")
    print(f"\nResumen final:")
    print(f"  Hoja 'Resumen':           {len(resumen_rows) + 1} filas")
    print(f"  Hoja 'Tareas':            {len(tasks) + 1} filas ({len(tasks)} tareas)")
    print(f"  Hoja 'URLs-Prioridad':    {len(url_prio_final) + 1} filas")
    print(f"  Hoja 'Oportunidades GSC': {len(gsc_final) + 1} filas")
    print(f"  Hojas de detalle:         {len(_detail_sheet_map)} tareas")

    # Health score (0-100)
    _p0 = len([t for t in tasks if t['Prioridad'] == 'P0'])
    _p1 = len([t for t in tasks if t['Prioridad'] == 'P1'])
    _p2 = len([t for t in tasks if t['Prioridad'] == 'P2'])
    _health_score = max(0, 100 - min(36, _p0 * 12) - min(24, _p1 * 3) - min(10, _p2 * 1))
    _gsc_top_cols = [c for c in ['url', 'impressions', 'clicks', 'ctr', 'position'] if c in df.columns]

    return {
        'tasks':       len(tasks),
        'urls':        len(url_prio_final),
        'gsc':         len(gsc_final),
        'resumen':     len(resumen_rows),
        'output_path': output_path,
        'dashboard': {
            # Inventario
            'total_html':           total_html,
            'total_indexable':      total_indexable,
            'total_no_indexable':   total_no_indexable,
            'url_type_dist':        df['url_type'].value_counts().to_dict(),
            'indexable_type_dist':  df_indexable['url_type'].value_counts().to_dict(),
            # HTTP Status
            'status_200':  status_200,
            'status_301':  status_301_count,
            'status_404':  status_404_count,
            'status_5xx':  status_5xx_count,
            'status_0':    status_0,
            # Razones no-indexabilidad
            'blocked_robots': total_blocked_robots,
            'canonicalized':  total_canonicalized,
            'redirects_idx':  total_redirects_idx,
            # On-page quality
            'n_no_meta':      n_no_meta,
            'n_no_h1':        n_no_h1,
            'n_seo_pages':    len(df_seo),
            'n_dup_titles':   len(df_dup_titles),
            'n_long_titles':  len(df_long_titles),
            'n_title_eq_h1':  len(df_title_eq_h1),
            'n_no_h2':        len(df_no_h2),
            'n_no_canonical': len(df_no_canonical),
            'n_thin':         len(df_thin),
            # Enlazado interno (Tanda 1 — requiere All Links con Posición del enlace)
            'has_link_position':      HAS_LINK_POSITION,
            'has_follow_data':        HAS_FOLLOW_DATA,
            'has_link_score':         HAS_LINK_SCORE,
            'n_links_contextual':     n_links_contextual,
            'n_links_boilerplate':    n_links_boilerplate,
            'n_no_contextual':        len(df_no_contextual),
            'link_score_median':      float(df_seo['link_score'].median()) if HAS_LINK_SCORE and len(df_seo) > 0 else None,
            'n_low_link_score':       int((df_seo['link_score'] < 10).sum()) if HAS_LINK_SCORE and len(df_seo) > 0 else 0,
            # Técnico
            'has_sitemap_data':       HAS_SITEMAP_DATA,
            'has_response_time':      HAS_RESPONSE_TIME,
            'n_slow':                 len(df_slow),
            'n_parametered':          len(df_parametered),
            'n_long_urls':            len(df_long_urls),
            'n_deep':                 len(df_deep),
            'n_double_slash':         len(df_double_slash_indexable),
            'n_pag_indexable':        n_pag_index,
            'n_noindex_in_sitemap':   len(df_noindex_in_sitemap),
            'n_missing_from_sitemap': len(df_missing_from_sitemap),
            'n_noindex_with_gsc':     len(df_noindex_with_gsc),
            # GSC
            'has_gsc':           HAS_GSC,
            'total_impressions':  total_impressions,
            'total_clicks':       total_clicks,
            'overall_ctr':        overall_ctr,
            'n_pos_11_20':        len(df_pos_11_20),
            'n_low_ctr':          len(df_low_ctr),
            'n_impr_no_clicks':   len(df_impr_no_clicks),
            'n_demand':           n_demand,
            'top_gsc_pages': (
                df_gsc.nlargest(10, 'impressions')[_gsc_top_cols].to_dict('records')
                if HAS_GSC and len(df_gsc) > 0 else []
            ),
            # Tareas
            'tasks_list': [
                {
                    'id':          t['ID'],
                    'priority':    t['Prioridad'],
                    'category':    t['Categoría'],
                    'task':        t['Tarea'],
                    'description': t['Descripción corta'],
                    'evidence':    t['Evidencia'],
                    'cause':       t['Causa probable'],
                    'todo':        t['Qué hacer'],
                    'where':       t['Dónde detectarlo'],
                    'effort':      t['Esfuerzo'],
                    'impact':      t['Impacto'],
                    'risk':        t['Riesgo'],
                    'responsible': t['Responsable'],
                    'validation':  t['Validación'],
                    'urls_sample': t['URLs ejemplo'],
                }
                for t in tasks
            ],
            'tasks_by_priority': {
                p: len([t for t in tasks if t['Prioridad'] == p])
                for p in ['P0', 'P1', 'P2', 'P3']
            },
            # Health score
            'health_score': _health_score,
        },
        'detail_dfs': detail_dfs,
    }


# ──────────────────────────────────────────────────────────────────────────────
# CLI — solo se ejecuta cuando se llama directamente como script
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Motor de auditoría SEO genérico')
    parser.add_argument('--config',     required=True, help='Ruta al archivo config_*.py')
    parser.add_argument('--csv',        help='Ruta al CSV (sobreescribe el del config)')
    parser.add_argument('--links-csv',  help='Ruta al All Links CSV de SF (opcional)')
    parser.add_argument('--output-dir', help='Directorio de salida (sobreescribe el del config)')
    args = parser.parse_args()

    _cfg        = load_config(args.config)
    _ruta_csv   = args.csv or _cfg.RUTA_CSV
    _output_dir = (args.output_dir or _cfg.OUTPUT_DIR).rstrip('/')
    _domain     = _cfg.DOMAIN
    _fecha      = datetime.now().strftime('%Y%m%d')
    _output_path = f"{_output_dir}/auditoria-seo-{_domain}-{_fecha}.xlsx"
    _ruta_links = args.links_csv or getattr(_cfg, 'RUTA_LINKS_CSV', None)

    print(f"Config  : {args.config}")
    run_audit(_cfg, _ruta_csv, _output_path, ruta_links_csv=_ruta_links)
