#!/usr/bin/env python3
"""
app.py  —  Interfaz web para el motor de auditoría SEO
Uso: streamlit run app.py
"""

import sys
import os
import tempfile
import types
from datetime import datetime
from pathlib import Path

import streamlit as st

# Asegurar que el módulo audit_engine está en el path
sys.path.insert(0, str(Path(__file__).parent))
from audit_engine import run_audit  # noqa: E402

# ──────────────────────────────────────────────────────────────────────────────
# PRESETS POR PLATAFORMA
# ──────────────────────────────────────────────────────────────────────────────

PRESETS = {
    "Shopify": {
        "URL_PATTERNS": [
            ("cart-recommendations", "cart_reco"),
            ("/products/", "product"),
            ("/collections/", "collection"),
            ("/collections", "collections_root"),
            ("/blogs/", "blog"),
            ("/pages/", "page"),
        ],
        "SYSTEM_PATTERNS": ["/cart", "/checkout", "/account", "/search", "/cdn/"],
        "SEO_TYPES": ["product", "collection", "collections_root", "homepage", "blog", "page"],
        "HAS_CART_RECO": True,
        "PAGINATION_PARAMS": ["page"],
        "PAGINATION_PATH_REGEX": None,
    },
    "WooCommerce": {
        "URL_PATTERNS": [
            ("/product/", "product"),
            ("/product-category/", "collection"),
            ("/shop/", "collections_root"),
        ],
        "SYSTEM_PATTERNS": ["/cart", "/checkout", "/my-account", "/?add-to-cart=", "/wp-admin/", "/wp-login.php"],
        "SEO_TYPES": ["product", "collection", "collections_root", "homepage", "blog", "page"],
        "HAS_CART_RECO": False,
        "PAGINATION_PARAMS": ["paged", "page"],
        "PAGINATION_PATH_REGEX": r"/page/\d+",
    },
    "WordPress": {
        "URL_PATTERNS": [
            ("/category/",  "collection"),
            ("/tag/",       "tag"),
        ],
        "SYSTEM_PATTERNS": [
            "/wp-admin/", "/wp-login.php", "/wp-json/",
            "/wp-cron.php", "/xmlrpc.php", "/trackback/", "/?replytocom=",
        ],
        # 'other' incluye posts/entradas de WP (sin prefijo de URL fijo)
        "SEO_TYPES": ["collection", "page", "other", "homepage"],
        "HAS_CART_RECO": False,
        "PAGINATION_PARAMS": ["paged", "page"],
        "PAGINATION_PATH_REGEX": r"/page/\d+",
    },
    "PrestaShop": {
        # PrestaShop tiene URLs configurables — estos son los patrones más comunes.
        # Ajusta según el idioma y la configuración del cliente.
        "URL_PATTERNS": [
            # Inglés (por defecto PS)
            ("/product/",    "product"),
            ("/category/",   "collection"),
            # Español
            ("/producto/",   "product"),
            ("/categoria/",  "collection"),
            # Francés
            ("/produit/",    "product"),
            ("/categorie/",  "collection"),
            # CMS pages
            ("/cms/",        "page"),
            ("/content/",    "page"),
            # Marca / fabricante
            ("/brand/",      "collection"),
            ("/marca/",      "collection"),
            ("/fabricante/", "collection"),
        ],
        "SYSTEM_PATTERNS": [
            "/cart/", "/carrito/", "/checkout/", "/pedido/",
            "/my-account/", "/mi-cuenta/", "/module/", "/modulo/",
            "index.php?controller=cart",
            "index.php?controller=order",
            "index.php?controller=authentication",
            "/api/", "/img/p/", "/img/c/",
        ],
        "SEO_TYPES": ["product", "collection", "page", "homepage"],
        "HAS_CART_RECO": False,
        "PAGINATION_PARAMS": ["p"],
        "PAGINATION_PATH_REGEX": None,
    },
    "Generic": {
        "URL_PATTERNS": [],
        "SYSTEM_PATTERNS": [],
        "SEO_TYPES": ["product", "blog", "page"],
        "HAS_CART_RECO": False,
        "PAGINATION_PARAMS": ["page"],
        "PAGINATION_PATH_REGEX": None,
    },
}

PLATFORM_LABELS = list(PRESETS.keys())
LANG_OPTIONS = ["es", "en", "fr", "de", "it", "pt", "ca", "pl", "nl", "sv", "da", "fi", "ro", "cs", "hu"]

# ──────────────────────────────────────────────────────────────────────────────
# AUTO-DETECCIÓN DE LOCALES
# ──────────────────────────────────────────────────────────────────────────────

import re as _re
import io as _io

_LOCALE_RE = _re.compile(r'https?://[^/]+/([a-z]{2})/', _re.IGNORECASE)
_KNOWN_LANGS = set(LANG_OPTIONS)

def detect_locales_from_csv(file_bytes: bytes) -> list[str]:
    """Lee las primeras 5000 URLs del CSV y detecta subdirectorios /<ll>/ de idioma."""
    found: dict[str, int] = {}
    try:
        sample = file_bytes[:500_000].decode('utf-8', errors='replace')
        # Detectar columna URL (primera columna o columna llamada 'Address')
        lines = sample.splitlines()
        header = lines[0].lower() if lines else ''
        url_col_idx = 0
        for i, col in enumerate(header.split(',')):
            if col.strip().strip('"') in ('address', 'url'):
                url_col_idx = i
                break
        for line in lines[1:5001]:
            parts = line.split(',')
            if url_col_idx < len(parts):
                url = parts[url_col_idx].strip().strip('"')
                m = _LOCALE_RE.match(url)
                if m:
                    lang = m.group(1).lower()
                    if lang in _KNOWN_LANGS:
                        found[lang] = found.get(lang, 0) + 1
    except Exception:
        pass
    # Solo devolver langs con ≥5 URLs
    return sorted(lang for lang, cnt in found.items() if cnt >= 5)


def detect_platform_from_csv(file_bytes: bytes) -> tuple:
    """Detecta la plataforma a partir de señales en las URLs del CSV.

    Returns:
        (platform_name: str, extra: dict)
        extra puede contener 'mixed_info', 'url_patterns', 'system_patterns'
        cuando se detecta una combinación de plataformas.
    """
    try:
        sample = file_bytes[:500_000].decode('utf-8', errors='replace')
        lines = sample.splitlines()
        header = lines[0].lower() if lines else ''
        url_col_idx = 0
        for i, col in enumerate(header.split(',')):
            if col.strip().strip('"') in ('address', 'url'):
                url_col_idx = i
                break
        urls = []
        for line in lines[1:3001]:
            parts = line.split(',')
            if url_col_idx < len(parts):
                url = parts[url_col_idx].strip().strip('"').lower()
                if url:
                    urls.append(url)

        url_blob = ' '.join(urls)

        scores = {'Shopify': 0, 'WooCommerce': 0, 'WordPress': 0, 'PrestaShop': 0}

        # Shopify — señales muy específicas
        if '/products/' in url_blob:           scores['Shopify'] += 3  # plural = Shopify
        if '/collections/' in url_blob:        scores['Shopify'] += 3
        if 'cart-recommendations' in url_blob: scores['Shopify'] += 5
        if 'cdn.shopify.com' in url_blob:      scores['Shopify'] += 10
        if 'myshopify.com' in url_blob:        scores['Shopify'] += 10

        # WooCommerce (corre sobre WordPress)
        if '/product-category/' in url_blob:   scores['WooCommerce'] += 5
        if '?add-to-cart=' in url_blob:        scores['WooCommerce'] += 4
        if '/wp-content/' in url_blob:         scores['WooCommerce'] += 1
        if '/product/' in url_blob and '/products/' not in url_blob:
            scores['WooCommerce'] += 2

        # WordPress
        if '/wp-content/' in url_blob:  scores['WordPress'] += 3
        if '/wp-json/' in url_blob:     scores['WordPress'] += 4
        if '?p=' in url_blob:           scores['WordPress'] += 2
        if '/author/' in url_blob:      scores['WordPress'] += 1

        # PrestaShop — señales muy específicas
        if 'index.php?controller=' in url_blob: scores['PrestaShop'] += 5
        if '/img/p/' in url_blob:               scores['PrestaShop'] += 4
        if '/img/c/' in url_blob:               scores['PrestaShop'] += 3

        # WooCommerce hereda señales WP → neutralizar WP si WC detectado
        if scores['WooCommerce'] >= 3:
            scores['WordPress'] = 0

        THRESHOLD = 2
        detected = [
            p for p, s in sorted(scores.items(), key=lambda x: -x[1])
            if s >= THRESHOLD
        ]

        if not detected:
            return 'Generic', {}

        if len(detected) == 1:
            return detected[0], {}

        # Plataforma mixta — fusionar patrones de ambos presets
        merged_url: dict = {}
        merged_sys: list = []
        for plat in detected:
            if plat in PRESETS:
                for patt, ptype in PRESETS[plat]['URL_PATTERNS']:
                    if patt not in merged_url:
                        merged_url[patt] = ptype
                for sp in PRESETS[plat]['SYSTEM_PATTERNS']:
                    if sp not in merged_sys:
                        merged_sys.append(sp)

        return 'Generic', {
            'mixed_info': ' + '.join(detected),
            'url_patterns': '\n'.join(f'{p},{t}' for p, t in merged_url.items()),
            'system_patterns': '\n'.join(merged_sys),
        }

    except Exception:
        return 'Generic', {}


# ──────────────────────────────────────────────────────────────────────────────
# LAYOUT
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SEO Audit Engine",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS personalizado ────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ─── App background ─── */
.stApp { background: #f0f4f8 !important; }

/* ─── Hero ─── */
.seo-hero {
    background: linear-gradient(135deg, #0f2b4a 0%, #0a4f7e 55%, #085f79 100%);
    border-radius: 16px;
    padding: 30px 36px 26px 36px;
    margin-bottom: 24px;
    color: white;
    box-shadow: 0 4px 20px rgba(15,43,74,0.25);
}
.seo-hero h1 {
    margin: 0 0 8px 0;
    font-size: 1.85rem;
    font-weight: 700;
    letter-spacing: -0.3px;
    color: white !important;
}
.seo-hero p {
    margin: 0;
    opacity: 0.75;
    font-size: 0.95rem;
    color: white !important;
}

/* ─── Section headers ─── */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-bottom: 10px;
    border-bottom: 2px solid #e2e8f0;
    margin-bottom: 18px;
}
.section-number {
    background: linear-gradient(135deg, #0077b6, #00b4d8);
    color: white;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.78rem;
    font-weight: 700;
    flex-shrink: 0;
}
.section-title {
    font-size: 1.0rem;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
}

/* ─── File uploader ─── */
[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #93c5fd !important;
    border-radius: 12px !important;
    background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%) !important;
    transition: border-color 0.2s, background 0.2s;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #0077b6 !important;
    background: #dbeafe !important;
}

/* ─── Primary buttons ─── */
button[data-testid="baseButton-primary"],
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #0077b6 0%, #00b4d8 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    box-shadow: 0 4px 14px rgba(0,119,182,0.35) !important;
    transition: opacity 0.2s, box-shadow 0.2s !important;
}
button[data-testid="baseButton-primary"]:hover:not(:disabled),
.stButton > button[kind="primary"]:hover:not(:disabled) {
    opacity: 0.9 !important;
    box-shadow: 0 6px 18px rgba(0,119,182,0.45) !important;
}
button[data-testid="baseButton-primary"]:disabled,
.stButton > button[kind="primary"]:disabled {
    background: linear-gradient(135deg, #cbd5e1 0%, #94a3b8 100%) !important;
    box-shadow: none !important;
}

/* ─── Download button ─── */
.stDownloadButton > button {
    background: linear-gradient(135deg, #059669 0%, #10b981 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 14px rgba(5,150,105,0.35) !important;
    color: white !important;
}
.stDownloadButton > button:hover { opacity: 0.9 !important; }

/* ─── Métricas resultado ─── */
[data-testid="metric-container"] {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 18px 22px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
}

/* ─── Expanders ─── */
[data-testid="stExpander"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    background: white !important;
    margin-bottom: 10px !important;
    overflow: hidden;
}

/* ─── Dividers ─── */
hr { border-color: #e2e8f0 !important; margin: 20px 0 !important; }

/* ─── Alert boxes ─── */
[data-testid="stAlert"] { border-radius: 10px !important; }

/* ─── Footer ─── */
.seo-footer {
    text-align: center;
    padding: 20px 0 4px 0;
    color: #94a3b8;
    font-size: 0.8rem;
    border-top: 1px solid #e2e8f0;
    margin-top: 40px;
}
</style>
""", unsafe_allow_html=True)

# ── Hero header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="seo-hero">
  <h1>🔍 SEO Audit Engine</h1>
  <p>Sube tu export de Screaming Frog, configura el cliente y descarga el Excel de auditoría.</p>
</div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([1, 1], gap="large")

# ──────────────────────────────────────────────────────────────────────────────
# COLUMNA IZQUIERDA — Upload + Config básica
# ──────────────────────────────────────────────────────────────────────────────

with col_left:
    st.markdown('<div class="section-header"><span class="section-number">1</span><span class="section-title">Export de Screaming Frog</span></div>', unsafe_allow_html=True)
    uploaded_csv = st.file_uploader(
        "Sube el archivo CSV (All Inlinks export o export estándar)",
        type=["csv"],
        help="Export de Screaming Frog en formato CSV. Puede incluir columnas GSC si se integró en SF.",
    )
    if uploaded_csv:
        st.success(f"✅ **{uploaded_csv.name}** cargado ({uploaded_csv.size / 1024:.0f} KB)")
        # Auto-detectar locales y plataforma al subir el CSV (solo una vez por archivo)
        csv_key = f"detected_v2_{uploaded_csv.name}_{uploaded_csv.size}"
        if csv_key not in st.session_state:
            file_bytes = uploaded_csv.getvalue()
            detected_langs = detect_locales_from_csv(file_bytes)
            detected_plat, plat_extra = detect_platform_from_csv(file_bytes)
            st.session_state[csv_key] = True
            # Locales
            if detected_langs:
                st.session_state['_auto_langs'] = detected_langs
                st.session_state['_auto_multilingual'] = True
            else:
                st.session_state.pop('_auto_langs', None)
                st.session_state.pop('_auto_multilingual', None)
            # Plataforma
            st.session_state['_auto_platform'] = detected_plat
            st.session_state['_platform_mixed_info'] = plat_extra.get('mixed_info', '')
            if 'url_patterns' in plat_extra:
                st.session_state['_auto_url_patterns'] = plat_extra['url_patterns']
                st.session_state['_auto_system_patterns'] = plat_extra.get('system_patterns', '')
            else:
                st.session_state.pop('_auto_url_patterns', None)
                st.session_state.pop('_auto_system_patterns', None)

    st.divider()

    st.markdown('<div class="section-header"><span class="section-number">2</span><span class="section-title">Datos del cliente</span></div>', unsafe_allow_html=True)

    domain = st.text_input(
        "Dominio",
        placeholder="ejemplo.com",
        help="Solo el dominio, sin https:// ni www.",
    )

    _auto_platform = st.session_state.get('_auto_platform', 'Shopify')
    _auto_platform_idx = PLATFORM_LABELS.index(_auto_platform) if _auto_platform in PLATFORM_LABELS else 0
    _mixed_info = st.session_state.get('_platform_mixed_info', '')

    if uploaded_csv and '_auto_platform' in st.session_state:
        if _mixed_info:
            st.info(f"🔍 Detectado: **{_mixed_info}** → patrones combinados en 'Generic'")
        elif _auto_platform != 'Generic':
            st.info(f"🔍 Plataforma detectada: **{_auto_platform}**")

    _plat_key = f"plat_sel_{getattr(uploaded_csv, 'name', '')}_{getattr(uploaded_csv, 'size', 0)}"
    platform = st.selectbox(
        "Plataforma",
        options=PLATFORM_LABELS,
        index=_auto_platform_idx,
        key=_plat_key,
        help="Determina los patrones de URL predefinidos. Se auto-detecta al subir el CSV.",
    )

    st.divider()

    st.markdown('<div class="section-header"><span class="section-number">3</span><span class="section-title">Internacionalización</span></div>', unsafe_allow_html=True)

    _auto_multilingual = st.session_state.get('_auto_multilingual', False)
    _auto_langs        = st.session_state.get('_auto_langs', [])

    if _auto_langs:
        st.info(f"🌍 Idiomas detectados automáticamente en el CSV: **{', '.join(f'/{l}/' for l in _auto_langs)}**")

    is_multilingual = st.checkbox("¿El sitio tiene múltiples idiomas?", value=_auto_multilingual)

    site_langs = []
    special_locale = None
    if is_multilingual:
        _default_langs = _auto_langs if _auto_langs else ["en"]
        site_langs = st.multiselect(
            "Idiomas del sitio (subdirectorios /xx/)",
            options=LANG_OPTIONS,
            default=[l for l in _default_langs if l in LANG_OPTIONS],
            help="Selecciona los idiomas que aparecen como subdirectorio en las URLs.",
        )
        special_locale = st.text_input(
            "Locale especial con bloqueo robots.txt (opcional)",
            placeholder="ca",
            help="Si uno de los idiomas está bloqueado en robots.txt, indícalo aquí (ej: ca).",
        ).strip() or None

# ──────────────────────────────────────────────────────────────────────────────
# COLUMNA DERECHA — Config avanzada
# ──────────────────────────────────────────────────────────────────────────────

with col_right:
    st.markdown('<div class="section-header"><span class="section-number">4</span><span class="section-title">Configuración avanzada</span></div>', unsafe_allow_html=True)

    preset = PRESETS[platform]

    with st.expander("🔗 Patrones de URL", expanded=False):
        st.caption("Pares `patrón → tipo`. Cada patrón en una línea: `patrón,tipo`")
        # Mixto: si se detectaron 2 plataformas, usar los patrones fusionados
        if platform == 'Generic' and '_auto_url_patterns' in st.session_state:
            default_patterns = st.session_state['_auto_url_patterns']
        else:
            default_patterns = "\n".join(f"{p},{t}" for p, t in preset["URL_PATTERNS"])
        url_patterns_raw = st.text_area(
            "Patrones de URL",
            value=default_patterns,
            height=200,
            label_visibility="collapsed",
        )
        st.caption("Tipos disponibles: product · collection · collections_root · blog · page · cart_reco · system")

        st.caption("Patrones de sistema (uno por línea) — se clasifican como 'system':")
        if platform == 'Generic' and '_auto_system_patterns' in st.session_state:
            default_sys = st.session_state['_auto_system_patterns']
        else:
            default_sys = "\n".join(preset["SYSTEM_PATTERNS"])
        system_patterns_raw = st.text_area(
            "Patrones de sistema",
            value=default_sys,
            height=100,
            label_visibility="collapsed",
        )

        seo_types_raw = st.text_input(
            "Tipos SEO (separados por coma)",
            value=", ".join(preset["SEO_TYPES"]),
            help="Tipos de URL que se auditan a nivel on-page (meta, H1, etc.)",
        )

        has_cart_reco = st.checkbox("¿El sitio usa cart-recommendations?", value=preset["HAS_CART_RECO"])

    with st.expander("📄 Paginación", expanded=False):
        pagination_params_raw = st.text_input(
            "Parámetros de paginación (separados por coma)",
            value=", ".join(preset["PAGINATION_PARAMS"]),
        )
        pagination_path_regex = st.text_input(
            "Regex de paginación en ruta (opcional)",
            value=preset["PAGINATION_PATH_REGEX"] or "",
            placeholder=r"/page/\d+",
        ).strip() or None

    with st.expander("📊 Umbrales GSC", expanded=False):
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            t_impressions_demand = st.number_input("Min. impresiones (demanda)", value=200, min_value=1)
            t_inlinks_low        = st.number_input("Max. inlinks (bajo enlazado)", value=2, min_value=0)
            t_ctr_low            = st.number_input("CTR bajo (Top 10)", value=0.01, min_value=0.001, max_value=1.0, step=0.005, format="%.3f")
            t_title_short        = st.number_input("Title corto (chars)", value=40, min_value=10)
        with col_t2:
            t_impressions_min_ctr   = st.number_input("Min. impresiones para CTR", value=50, min_value=1)
            t_impressions_no_clicks = st.number_input("Min. impresiones sin clics", value=500, min_value=1)
            t_pos_opp_min = st.number_input("Posición oportunidad MIN", value=11, min_value=1)
            t_pos_opp_max = st.number_input("Posición oportunidad MAX", value=20, min_value=1)

# ──────────────────────────────────────────────────────────────────────────────
# BOTÓN PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────

st.divider()

run_col, _ = st.columns([1, 2])
with run_col:
    run_btn = st.button("🚀 Generar Auditoría", type="primary", use_container_width=True, disabled=not (uploaded_csv and domain))

if not uploaded_csv:
    st.info("📂 Sube un CSV de Screaming Frog para empezar.")
elif not domain:
    st.warning("⚠️ Indica el dominio del cliente.")

# ──────────────────────────────────────────────────────────────────────────────
# EJECUCIÓN
# ──────────────────────────────────────────────────────────────────────────────

if run_btn and uploaded_csv and domain:
    # Parsear patrones desde el textarea
    def parse_url_patterns(raw: str):
        patterns = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if "," in line:
                parts = line.split(",", 1)
                patterns.append((parts[0].strip(), parts[1].strip()))
        return patterns

    def parse_list(raw: str):
        return [x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()]

    url_patterns   = parse_url_patterns(url_patterns_raw)
    system_patterns = parse_list(system_patterns_raw)
    seo_types      = parse_list(seo_types_raw)
    pagination_params = parse_list(pagination_params_raw)

    # Construir objeto cfg como SimpleNamespace
    cfg_obj = types.SimpleNamespace(
        DOMAIN            = domain.strip(),
        PLATFORM          = platform,
        SITE_LANGS        = site_langs,
        IS_MULTILINGUAL   = is_multilingual and bool(site_langs),
        SPECIAL_LOCALE    = special_locale,
        URL_PATTERNS      = url_patterns,
        SYSTEM_PATTERNS   = system_patterns,
        SEO_TYPES         = seo_types,
        HAS_CART_RECO     = has_cart_reco,
        PAGINATION_PARAMS = pagination_params,
        PAGINATION_PATH_REGEX = pagination_path_regex,
        THRESHOLDS        = {
            "impressions_demand":    int(t_impressions_demand),
            "inlinks_low":           int(t_inlinks_low),
            "ctr_low":               float(t_ctr_low),
            "impressions_min_ctr":   int(t_impressions_min_ctr),
            "impressions_no_clicks": int(t_impressions_no_clicks),
            "pos_opportunity_min":   int(t_pos_opp_min),
            "pos_opportunity_max":   int(t_pos_opp_max),
            "title_short_chars":     int(t_title_short),
        },
    )

    # Guardar CSV en fichero temporal
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path    = os.path.join(tmpdir, uploaded_csv.name)
        fecha       = datetime.now().strftime("%Y%m%d")
        output_path = os.path.join(tmpdir, f"auditoria-seo-{domain.strip()}-{fecha}.xlsx")

        with open(csv_path, "wb") as f:
            f.write(uploaded_csv.getvalue())

        # Barra de progreso indeterminada
        with st.spinner(f"⚙️ Analizando **{uploaded_csv.name}** para **{domain}**…"):
            log_lines = []
            try:
                # Capturar el stdout del motor
                import io
                from contextlib import redirect_stdout

                buf = io.StringIO()
                with redirect_stdout(buf):
                    stats = run_audit(cfg_obj, csv_path, output_path)
                log_lines = buf.getvalue().splitlines()

                # Leer el Excel generado antes de que salga del tmpdir
                with open(output_path, "rb") as f:
                    excel_bytes = f.read()

            except Exception as exc:
                st.error(f"❌ Error durante la auditoría: {exc}")
                with st.expander("Detalle del error"):
                    import traceback
                    st.code(traceback.format_exc())
                st.stop()

    # ── Resultados ────────────────────────────────────────────────────────────
    st.success("✅ Auditoría completada")

    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
    r_col1.metric("Tareas generadas",  stats["tasks"])
    r_col2.metric("URLs prioritarias", stats["urls"])
    r_col3.metric("Oportunidades GSC", stats["gsc"])
    r_col4.metric("Filas en Resumen",  stats["resumen"])

    fname = f"auditoria-seo-{domain.strip()}-{fecha}.xlsx"
    st.download_button(
        label="⬇️ Descargar Excel",
        data=excel_bytes,
        file_name=fname,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=False,
    )

    with st.expander("📋 Log del motor"):
        st.code("\n".join(log_lines), language="text")

st.markdown('<div class="seo-footer">SEO Audit Engine &nbsp;·&nbsp; Powered by Screaming Frog + Google Search Console &nbsp;·&nbsp; Hecho por <a href="https://yerayrodri.online/" target="_blank" rel="noopener noreferrer" style="color:#94a3b8;text-decoration:underline;">Yeray Rodriguez</a></div>', unsafe_allow_html=True)
