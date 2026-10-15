"""
config_padelproshop.py — Configuración para padelproshop.com (Shopify)
"""

DOMAIN     = 'padelproshop.com'
RUTA_CSV   = '/Volumes/Discodurom2/ScreamigFrogData/internos_todopadelproshop.csv'
OUTPUT_DIR = '/Volumes/Discodurom2/ScreamigFrogData/'
PLATFORM   = 'Shopify'

SITE_LANGS      = []
IS_MULTILINGUAL = False
SPECIAL_LOCALE  = None

URL_PATTERNS = [
    ('cart-recommendations', 'cart_reco'),
    ('/products/',           'product'),
    ('/policies/',           'policy'),
    ('/pages/',              'page'),
    ('/blogs/',              'blog'),
    ('/collections/',        'collection'),
    ('/collections',         'collections_root'),
]

SYSTEM_PATTERNS = ['/cart', '/checkout', '/account', '/search', '/orders', '/wishlist']

SEO_TYPES = ['product', 'collection', 'collections_root', 'homepage', 'blog', 'page', 'policy']

HAS_CART_RECO = True

PAGINATION_PARAMS = ['page']
PAGINATION_PATH_REGEX = r'/page/\d+'

THRESHOLDS = {
    'impressions_demand':   200,
    'inlinks_low':            2,
    'ctr_low':             0.01,
    'impressions_min_ctr':   50,
    'impressions_no_clicks': 500,
    'pos_opportunity_min':   11,
    'pos_opportunity_max':   20,
    'title_short_chars':     40,
}

HEADER_BG = '1F4E78'
P0_BG     = 'FFDCE0'
P1_BG     = 'FFF0D3'
P2_BG     = 'FFFACC'
P3_BG     = 'E8F5E9'
ALT_ROW   = 'F5F8FC'
