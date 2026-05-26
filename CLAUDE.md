# seo-audit-claude — Contexto para Claude

Herramienta Streamlit de auditoría SEO técnica para uso interno en VON (Visibilidad ON).

## Arrancar el entorno

```bash
cd /Users/yerayrodriguez/Proyectos-Claude/VON/seo-audit-claude
source .venv/bin/activate
streamlit run app.py
```

Stack: Python 3.9+, Streamlit 1.56.0, pandas 3.0.2, openpyxl 3.1.5

---

## Archivos del proyecto

| Archivo | Líneas aprox. | Responsabilidad |
|---|---|---|
| `app.py` | ~1220 | UI Streamlit: formulario, CSS, dashboard, 4 tabs |
| `audit_engine.py` | ~2850 | Motor de análisis: T01–T48, output Excel, detail_dfs |
| `requirements.txt` | — | Dependencias |
| `config_newcop.py` | — | Config de cliente de ejemplo |
| `knowledge/` | — | Checklists, guías, reglas de priorización |
| `templates/` | — | Plantillas Excel de salida |
| `DEVELOPMENT_LOG.md` | — | Historial detallado de bugs, decisiones y commits |

**Archivos legacy sin uso activo:** `audit_newcop.py`, `audit_newcop_v2.py`, `audit_step1.py`, `_refactor.py`

---

## Flujo de la herramienta

1. Usuario sube CSV de Screaming Frog (Internal All) — obligatorio
2. Usuario sube All Links CSV de SF (Bulk Export → All Links) — opcional, enriquece T03/T04
3. Se auto-detecta plataforma (Shopify / WooCommerce / WordPress / Generic) y locales
4. `run_audit(cfg, ruta_csv, output_path, ruta_links_csv=None)` ejecuta los 48 checks (T01–T48)
5. Genera Excel de 4 hojas: Resumen, Tareas, URLs-Prioridad, Oportunidades GSC
6. Dashboard visual con Health Score + KPIs + pestaña Plan de Tareas con Excel por tarea

---

## Arquitectura de `audit_engine.py`

Dos funciones públicas en [audit_engine.py](audit_engine.py):

```python
def load_config(config_path): ...   # línea 32 — carga config de cliente
def run_audit(cfg, ruta_csv, output_path, ruta_links_csv=None): ...  # línea 43 — ejecuta T01–T48
```

`run_audit` retorna `dict` con claves:
- `tasks`, `urls`, `gsc`, `resumen`, `output_path`
- `dashboard` — dict con todos los KPIs y `tasks_list` (lista con todos los campos de cada tarea)
- `detail_dfs` — dict `{task_id: DataFrame}` con URLs afectadas por tarea (para Excel descargables)

### Checks T01–T48

| Rango | Categoría | Plataforma | Prioridad |
|---|---|---|---|
| T01–T03 | Bloqueos críticos: robots, 5xx, 4xx | Todas | P0 |
| T04–T07 | Redirects, doble slash, cart, paginación | Todas | P1 |
| T08–T14 | Meta descriptions, H1, titles, canonicals | Todas | P1–P2 |
| T15–T20 | Thin content, hreflang, interlinking | Todas | P1–P2 |
| T21–T32 | Sitemaps, speed, params, URLs largas, depth | Todas | P1–P2 |
| T33 | H1 duplicado en fichas de producto | Todas | P2 |
| T34 | H1 duplicado en colecciones/categorías | Todas | P2 |
| T35 | Meta descriptions duplicadas entre páginas SEO | Todas | P2 |
| T36 | Links internos apuntando a páginas noindex | Todas | P2 |
| T37 | `/collections/all` indexable | **Shopify** | P1 |
| T38 | `/collections/vendors`, `/collections/types` indexables | **Shopify** | P1 |
| T39 | URLs de producto con scope de colección indexables (`/collections/X/products/Y`) | **Shopify** | P1 |
| T40 | Tag pages de colección indexables (`/collections/handle/tag`) | **Shopify** | P1 |
| T41 | Variantes de producto indexables (`?variant=`) | **Shopify** | P1 |
| T42 | Product schema ausente en fichas de producto | Todas* | P1 |
| T43 | AggregateRating/Review ausente en fichas de producto | Todas* | P1 |
| T44 | AggregateRating/Review ausente en colecciones | Todas* | P2 |
| T45 | Organization/WebSite schema ausente en homepage | Todas* | P1 |
| T46 | BlogPosting schema ausente en artículos de blog | Todas* | P2 |
| T47 | Person/Author schema ausente en artículos de blog | Todas* | P2 |
| T48 | BreadcrumbList ausente en productos y colecciones | Todas* | P2 |

*T42–T48 solo se ejecutan si el CSV exporta la columna `Structured Data` (SF la incluye cuando se habilita en la configuración del crawl).

### Health Score

```python
score = max(0, 100 - min(36, P0×12) - min(24, P1×3) - min(10, P2×1))
```

### Convención de columnas — CRÍTICO

La columna SF `Indexability` se normaliza internamente como **`indexable`**:
- Correcto: `df['indexable']`
- Incorrecto: `df['indexability']` → KeyError

SF_COL_MAP completo (~línea 119 de audit_engine.py):

| SF column | Nombre interno |
|---|---|
| `Address` | `url` |
| `Status Code` | `status` |
| `Indexability` | `indexable` |
| `Title 1` | `title` |
| `Title 1 Length` | `title_len` |
| `Meta Description 1` | `meta_desc` |
| `Meta Description 1 Length` | `meta_desc_len` |
| `H1-1` | `h1` |
| `H2-1` | `h2` |
| `Canonical Link Element 1` | `canonical` |
| `Meta Robots 1` | `meta_robots` |
| `Crawl Depth` | `depth` |
| `Inlinks` | `inlinks` |
| `Is In Sitemap` | `in_sitemap` |
| `Content Type` | `content_type` |
| `Word Count` | `word_count` |
| `Size (bytes)` | `size` |
| `Response Time` | `response_time` |
| `Indexability Status` | `indexability_status` |
| `Structured Data` | `structured_data` |
| `Redirect URL` | `redirect_url` |

La columna `H1-1` se normaliza como `h1` vía SF_COL_MAP, pero `profiler_csv` puede renombrarla como `h1_1`. Los checks T33/T34 usan `_h1_col` que detecta ambas automáticamente.

### Flags de disponibilidad de columnas

```python
HAS_SITEMAP_DATA   # 'in_sitemap' in df.columns
HAS_RESPONSE_TIME  # 'response_time' in df.columns
HAS_INLINKS_DATA   # 'inlinks' in df.columns and sum > 0
HAS_GSC            # columnas GSC presentes y con datos
HAS_SD_COL         # 'structured_data' in df.columns
IS_SHOPIFY         # PLATFORM == 'Shopify'
HAS_LINKS          # All Links CSV cargado correctamente
```

Todos los checks comprueban su flag antes de ejecutarse — si la columna no existe, el check no genera tarea (sin errores, sin falsos positivos).

### detail_dfs — DataFrames por tarea

Tras ejecutar todos los checks se construye `detail_dfs = {task_id: DataFrame}`.  
Columnas base de cada DataFrame (`_DETAIL_OPT`):

```python
['status', 'indexable', 'indexability_status',
 'title', 'title_len', 'meta_desc', 'meta_desc_len',
 'h1', 'h2', 'canonical', 'meta_robots', 'word_count', 'structured_data',
 'inlinks', 'depth', 'redirect_url', 'response_time',
 'impressions', 'clicks', 'ctr', 'position']
```

Solo se incluyen las columnas que existen en el DataFrame fuente.

**Post-procesado de duplicados** (aplicado antes de guardar en detail_dfs):
- `T26` (dup titles): columna `grupo_dup_title` — todas las URLs con el mismo título juntas
- `T35` (dup meta): columna `grupo_dup_meta`
- `T33` (dup H1 productos): columna `grupo_dup_h1`
- `T34` (dup H1 colecciones): columna `grupo_dup_h1`

**Enriquecimiento con All Links CSV** (cuando `ruta_links_csv` se pasa a `run_audit`):
- `T03` (404s): una fila por enlace entrante → columnas `url_404`, `pagina_origen`, `texto_ancla`, `es_imagen`, `texto_alt` + GSC si disponible
- `T04` (301s): una fila por enlace entrante → columnas `url_redirect`, `redirige_a`, `pagina_origen`, `texto_ancla`, `es_imagen`, `texto_alt`

El All Links CSV se exporta desde SF → Bulk Export → All Links. Parsing flexible (detecta `Source`/`Destination`/`Anchor`/`Alt Text`/`Type`/`Tag` con varias variantes de nombre).

---

## Arquitectura de `app.py`

Funciones relevantes en [app.py](app.py):

- `detect_locales_from_csv(file_bytes)` — ~línea 125
- `detect_platform_from_csv(file_bytes)` — ~línea 153

### Estructura de la UI

```
~Línea 21    — PRESETS por plataforma (Shopify, WooCommerce, WordPress, Generic)
~Línea 256   — CSS personalizado (Inter font, .kpi-card, .seo-hero, expanders)
~Línea 536   — Hero header HTML
~Línea 547   — Sección 1: upload Internal All CSV
~Línea 584   — Sección 1b: upload All Links CSV (opcional)
~Línea 598   — Sección 2: datos del cliente (dominio, plataforma)
~Línea 615   — Sección 3: internacionalización
~Línea 646   — Sección 4: configuración avanzada
~Línea 726   — Botón "Generar Auditoría" + llamada a run_audit()
~Línea 810   — Tabs de resultado:
               tab_dash   — Dashboard SEO
               tab_tasks  — Plan de Tareas (expanders + Excel por tarea)
               tab_dl     — Descargar Excel completo
               tab_log    — Log de ejecución
~Línea 836   — Dashboard: Health Score, KPIs, inventario, on-page, técnico, GSC
~Línea 1066  — Resumen Plan de Acción (4 contadores P0/P1/P2/P3)
~Línea 1089  — TAB Plan de Tareas: expanders + _make_task_excel()
```

### Tab Plan de Tareas

Cada tarea se muestra en un `st.expander` con:
- Columna izquierda: categoría, descripción, causa, qué hacer, dónde detectarlo
- Columna derecha: esfuerzo, impacto, riesgo, responsable
- Evidencia y URLs de ejemplo en `st.code`
- Botón "⬇️ Descargar Excel — TXX" si la tarea tiene DataFrame en `detail_dfs`

El Excel generado (`_make_task_excel`) tiene dos hojas:
1. **"URLs afectadas"** — DataFrame completo con todas las columnas relevantes
2. **"Ficha tarea"** — campos: ID, Prioridad, Categoría, Tarea, Descripción, Causa, Qué hacer, Dónde, Esfuerzo, Impacto, Riesgo, Responsable, Validación, Evidencia

### Helper `_tc_card(label, value, warn=False, na=False)`

Definido dentro del bloque `with tab_dash:`. Devuelve HTML con `.kpi-card`. Si genera problemas de re-render, moverlo a nivel de módulo.

---

## Design system CSS — reglas críticas

### Fuente Inter — selector correcto

```css
html, body, .stApp, .block-container { font-family: 'Inter', ...; }
input, textarea, select, button { font-family: inherit !important; }
```

**Nunca usar `*` ni `span`** — rompen los web components de Streamlit:
- `* { font-family }` → texto "uploadupload" duplicado en file uploader
- `span { font-family }` → mismo efecto

### Expanders — selector correcto

```css
/* Solo el contenedor, sin overflow:hidden */
[data-testid="stExpander"] { border, border-radius, background, margin, box-shadow }
```

**Nunca** añadir CSS a `[data-testid="stExpander"] [role="button"]` sin combinator `>` → aparece texto `"_arr"` en el header.  
**Nunca** poner `overflow: hidden` en expanders → colapsa el flex layout del header.

### Clases CSS disponibles

| Clase | Uso |
|---|---|
| `.seo-hero` | Hero oscuro con gradiente y efectos radiales |
| `.seo-hero-badge` | Pill "⚡ Technical SEO Tool" |
| `.dash-section` | Header de sección en el dashboard |
| `.section-header` / `.section-number` | Headers del formulario numerados |
| `.kpi-card` | Card blanca con hover — contiene `.kpi-label`, `.kpi-value`, `.kpi-sub` |
| `.seo-footer` | Footer centrado con borde top |

---

## Bugs históricos resueltos

| Bug | Causa | Solución |
|---|---|---|
| `"uploadupload"` en file uploader | `* { font-family }` en CSS | Usar solo contenedores html/body/.stApp |
| `"_arr"` en expanders | Selector sin `>` en role="button" | Nunca estilizar el header del expander |
| `overflow:hidden` rompe expanders | Colapsa flex layout interno | Eliminar overflow:hidden del contenedor |
| `KeyError: indexability` | Nombre normalizado distinto | Siempre usar `df['indexable']` |
| `NameError: pd` en app.py | Faltaba import | `import pandas as pd` ya añadido |
| `KeyError: 'impressions'` en T03 | `nlargest('impressions')` sin guard GSC | Guard `_404_has_gsc` antes de nlargest |

### Posibles fallos en los nuevos checks (T33–T48)

- **T33/T34 — H1 duplicados**: si tanto `h1` como `h1_1` están en el df, `_h1_col` usa `h1_1`. Si ninguno existe, el check no se ejecuta silenciosamente.
- **T37–T41 — Shopify**: solo se ejecutan si `PLATFORM == 'Shopify'`. Si la auto-detección de plataforma falla, estos checks no aparecen aunque el site sea Shopify.
- **T42–T48 — Structured Data**: SF no exporta la columna `Structured Data` en todos los modos de crawl. Para habilitarla: SF → Configuration → Spider → Extraction → Structured Data → activar.
- **T39 — Scoped products**: el regex `/collections/[^/?#]+/products/` puede producir falsos positivos. Revisar si aparecen URLs inesperadas.
- **All Links CSV — T03/T04**: si SF exporta el All Links con nombres de columna distintos a `Source`/`Destination`/`Anchor`/`Alt Text`/`Type`, el parser flexible intenta detectarlos pero puede fallar silenciosamente (HAS_LINKS queda False, se usa fallback sin origen).

---

## Documentación de referencia en `knowledge/`

- [CHECKLIST_AUDITORIA_SEO_CORE.md](knowledge/CHECKLIST_AUDITORIA_SEO_CORE.md)
- [CHECKLIST_AUDITORIA_SEO_SF_GSC.md](knowledge/CHECKLIST_AUDITORIA_SEO_SF_GSC.md)
- [GUIA_INGESTA_DATOS_SF_GSC.md](knowledge/GUIA_INGESTA_DATOS_SF_GSC.md)
- [NOTAS_IMPLEMENTACION_TECNICA_PROMPT.md](knowledge/NOTAS_IMPLEMENTACION_TECNICA_PROMPT.md)
- [NOTA_PLANTILLA_EJEMPLO_SALIDA.md](knowledge/NOTA_PLANTILLA_EJEMPLO_SALIDA.md)
- [REGLAS_PRIORIZACION_P0_P3_SEO.md](knowledge/REGLAS_PRIORIZACION_P0_P3_SEO.md)

Para entender el formato de salida del Excel ver [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md).

---

## Pendiente de implementar (diseñado, no codificado)

### Bloque 4 — Nofollow (All Links CSV ya disponible en el upload)

El upload de All Links CSV ya existe en `app.py` (~línea 584). Usar `_df_links` en audit_engine para estos checks:

| ID | Check | Lógica |
|---|---|---|
| T49 | Links de paginación sin nofollow | `?page=` / `/page/X` con `follow=true` en `_df_links` |
| T50 | Links de ordenación/filtros sin nofollow | `?sort_by=`, `?filter.` con `follow=true` |
| T51 | Links a carrito/checkout sin nofollow | `/cart`, `/checkout` con `follow=true` |
| — | Links internos duplicados en misma página | misma URL origen→destino más de una vez |

### Bloque 5 — WordPress-específico (ninguno implementado aún)

Misma metodología que los Shopify. Activar con `IS_WORDPRESS = (PLATFORM == 'WordPress')`.

Checks habituales: páginas de autor indexables, archivos año/mes indexables, `/?p=XXXX` indexable, feeds indexables, páginas de adjuntos indexables, tags/categorías sin contenido.

### Bloque 6 — Checks desde columnas SF ya disponibles pero no usadas

- **Cadenas de redirect**: columna `redirect_url` ya en Internal All (ya en SF_COL_MAP) → construir grafo A→B→C
- **Canonical chains/loops**: cruzar columna `canonical` consigo misma → detectar loops y cadenas

### Mejoras de arquitectura pendientes

- Unificar archivos legacy (`audit_newcop.py`, `audit_newcop_v2.py`, `audit_step1.py`)
- Mover `_tc_card()` a nivel de módulo en `app.py`
- Tests unitarios para los checks T01–T48
- Responsive: ajustar `st.columns([1.8, 1, 1, 1, 1])` en pantallas estrechas

### Ideas para más adelante (requieren integración externa)

- Canibalización: query×page GSC → múltiples URLs compitiendo por misma keyword
- Enriquecimiento con DataForSEO: dificultad de keyword y volumen por URL
- Conexión directa GSC vía MCP en lugar de upload de ZIPs
- SF MCP (`mcp__screaming-frog__*`): redirect chains, hreflang validation, canonical issues sin CSV adicional
