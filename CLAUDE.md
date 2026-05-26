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

| Archivo | Líneas | Responsabilidad |
|---|---|---|
| `app.py` | ~1089 | UI Streamlit: formulario, CSS, dashboard, tabs |
| `audit_engine.py` | ~2227 | Motor de análisis: T01–T32, output Excel |
| `requirements.txt` | — | Dependencias |
| `config_newcop.py` | — | Config de cliente de ejemplo |
| `knowledge/` | — | Checklists, guías, reglas de priorización |
| `templates/` | — | Plantillas Excel de salida |
| `DEVELOPMENT_LOG.md` | — | Historial detallado de bugs, decisiones y commits |

**Archivos legacy sin uso activo:** `audit_newcop.py`, `audit_newcop_v2.py`, `audit_step1.py`, `_refactor.py`

---

## Flujo de la herramienta

1. Usuario sube CSV de Screaming Frog (Internal All) — obligatorio
2. Usuario sube ZIPs de GSC (páginas, consultas, query×page) — opcionales
3. Se auto-detecta plataforma (Shopify / WooCommerce / WordPress / Generic) y locales
4. `run_audit(cfg, ruta_csv, output_path)` ejecuta los 48 checks (T01–T48)
5. Genera Excel de 4 hojas: Resumen, Tareas, URLs-Prioridad, Oportunidades GSC
6. Dashboard visual con Health Score + KPIs

---

## Arquitectura de `audit_engine.py`

Dos funciones públicas en [audit_engine.py](audit_engine.py):

```python
def load_config(config_path): ...   # línea 32 — carga config de cliente
def run_audit(cfg, ruta_csv, output_path): ...  # línea 43 — ejecuta T01–T48, escribe Excel
```

`run_audit` retorna `dict` con claves: `tasks`, `urls`, `gsc`, `resumen`, `output_path`

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

La columna SF `Structured Data` se normaliza como **`structured_data`** (añadida en SF_COL_MAP).

La columna `H1-1` se normaliza como `h1` vía SF_COL_MAP, pero `profiler_csv` puede renombrarla como `h1_1`. Los checks T33/T34 usan `_h1_col` que detecta ambas automáticamente.

El mapa completo está en `SF_COL_MAP` dentro de [audit_engine.py](audit_engine.py) (~línea 119).

### Flags de disponibilidad de columnas (al inicio de los pre-cómputos)

```python
HAS_SITEMAP_DATA   # 'in_sitemap' in df.columns
HAS_RESPONSE_TIME  # 'response_time' in df.columns
HAS_INLINKS_DATA   # 'inlinks' in df.columns and sum > 0
HAS_GSC            # columnas GSC presentes y con datos
HAS_SD_COL         # 'structured_data' in df.columns  ← NUEVO
IS_SHOPIFY         # PLATFORM == 'Shopify'             ← NUEVO
```

Todos los checks comprueban su flag antes de ejecutarse — si la columna no existe, el check no genera tarea (sin errores, sin falsos positivos).

---

## Arquitectura de `app.py`

Funciones relevantes en [app.py](app.py):

- `detect_locales_from_csv(file_bytes)` — línea 125
- `detect_platform_from_csv(file_bytes)` — línea 153

### Estructura de la UI (por líneas)

```
Línea ~21    — PRESETS por plataforma (Shopify, WooCommerce, WordPress, Generic)
Línea ~256   — CSS personalizado (Inter font, .kpi-card, .seo-hero, expanders)
Línea ~536   — Hero header HTML
Línea ~547   — Formulario: columna izquierda (uploads) / derecha (config)
Línea ~641   — Botón "Generar Auditoría" + llamada a run_audit()
Línea ~709   — Tabs de resultado: tab_dl / tab_log / tab_dash
Línea ~726   — Dashboard: Health Score, KPI cards, inventario, on-page, técnico, GSC, plan
```

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

### Posibles fallos en los nuevos checks (T33–T48)

- **T33/T34 — H1 duplicados**: si tanto `h1` como `h1_1` están en el df, `_h1_col` usa `h1_1`. Si ninguno existe, el check no se ejecuta silenciosamente.
- **T37–T41 — Shopify**: solo se ejecutan si `PLATFORM == 'Shopify'`. Si la auto-detección de plataforma falla, estos checks no aparecen aunque el site sea Shopify. Verificar con `detect_platform_from_csv()` en `app.py`.
- **T42–T48 — Structured Data**: SF no exporta la columna `Structured Data` en todos los modos de crawl. Si el CSV no la trae, todos los checks SD son silenciosos. Para habilitarla: SF → Configuration → Spider → Extraction → Structured Data → activar.
- **T39 — Scoped products**: el regex `/collections/[^/?#]+/products/` puede producir falsos positivos si la URL tiene ese patrón por otro motivo. Revisar si aparecen URLs inesperadas.

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

### Bloque 4 — Nofollow (requiere nuevo upload: All Links CSV)
Añadir un tercer upload opcional en `app.py` para el export "All Links" de SF.

| ID | Check | Lógica |
|---|---|---|
| T49 | Links de paginación sin nofollow | `?page=` / `/page/X` con `follow=true` |
| T50 | Links de ordenación/filtros sin nofollow | `?sort_by=`, `?filter.` con `follow=true` |
| T51 | Links a carrito/checkout sin nofollow | `/cart`, `/checkout` con `follow=true` |
| — | Links internos duplicados en misma página | misma URL origen→destino más de una vez |

### Bloque 5 — WordPress-específico (ninguno implementado aún)
Misma metodología que los Shopify. Activar con `IS_WORDPRESS = (PLATFORM == 'WordPress')`.

Checks habituales: páginas de autor indexables, archivos año/mes indexables, `/?p=XXXX` indexable, feeds indexables, páginas de adjuntos indexables, tags/categorías sin contenido.

### Bloque 6 — Checks desde columnas SF ya disponibles pero no usadas
- **Cadenas de redirect**: columna `Redirect URL` ya en Internal All → construir grafo A→B→C
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
