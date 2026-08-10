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
| `audit_engine.py` | ~2870 | Motor de análisis: T01–T48, output Excel, detail_dfs |
| `requirements.txt` | — | Dependencias |
| `config_newcop.py` | — | Config de cliente de ejemplo |
| `knowledge/` | — | Checklists, guías, reglas de priorización |
| `templates/` | — | Plantillas Excel de salida |
| `DEVELOPMENT_LOG.md` | — | Historial detallado de bugs, decisiones y commits |

**Archivos legacy sin uso activo:** `audit_newcop.py`, `audit_newcop_v2.py`, `audit_step1.py`, `_refactor.py`

---

## Flujo de la herramienta

1. Usuario sube CSV de Screaming Frog (Internal All) — obligatorio
2. Usuario sube All Links CSV de SF (Bulk Export → All Links) — opcional, enriquece T02/T03/T04/T05/T07/T16/T19/T24/T25/T32/T36
3. Se auto-detecta plataforma (Shopify / WooCommerce / WordPress / Generic) y locales
4. `run_audit(cfg, ruta_csv, output_path, ruta_links_csv=None)` ejecuta los 48 checks (T01–T48)
5. Genera Excel con 4 hojas base + N hojas de detalle (una por tarea con datos):
   - **Resumen** — KPIs y top tareas P0/P1
   - **Tareas** — listado completo; columna P "Ver datos →" con hipervínculo a la hoja de detalle correspondiente
   - **URLs - Prioridad** — todas las URLs con su issue principal
   - **Oportunidades GSC** — URLs con potencial de mejora
   - **[TXX - Nombre...]** — una hoja por cada tarea que tenga URLs afectadas: ficha de tarea arriba + listado de URLs/enlaces abajo
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
| T15–T20 | Thin content, hreflang, interlinking, huérfanas | Todas | P1–P2 |
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

SF_COL_MAP completo (~línea 121 de audit_engine.py). Soporta **inglés, español y francés** — SF exporta en el idioma de la app:

| SF inglés | SF español | SF francés | Nombre interno |
|---|---|---|---|
| `Address` | `Dirección` | `Adresse` | `url` |
| `Status Code` | `Código de respuesta` | `Code de réponse` | `status` |
| `Indexability` | `Indexabilidad` | `Indexabilité` | `indexable` |
| `Indexability Status` | `Estado de indexabilidad` | `État d'indexabilité` | `indexability_status` |
| `Content Type` | `Tipo de contenido` | `Type de contenu` | `content_type` |
| `Title 1` | `Título 1` | `Titre 1` | `title` |
| `Title 1 Length` | `Longitud del título 1` | `Longueur du titre 1` | `title_len` |
| `Title 1 Pixel Width` | `Ancho de píxeles del título 1` | `Largeur en pixels du titre 1` | `title_pixel_width` |
| `Meta Description 1` | `Meta description 1` | `Meta Description 1` | `meta_desc` |
| `Meta Description 1 Length` | `Longitud de la meta description 1` | `Longueur de la méta description 1` | `meta_desc_len` |
| `Meta Description 1 Pixel Width` | `Ancho de píxeles de la meta description 1` | `Largeur en pixels de la méta description 1` | `meta_desc_pixel_width` |
| `H1-1` | `H1-1` | `H1-1` | `h1` |
| `H2-1` | `H2-1` | `H2-1` | `h2` |
| `Canonical Link Element 1` | `Elemento de enlace canónico 1` | `Élément de lien canonique 1` | `canonical` |
| `Meta Robots 1` | `Meta robots 1` | `Meta Robots 1` | `meta_robots` |
| `Crawl Depth` | `Nivel de profundidad` | `Profondeur d'exploration` | `depth` |
| `Inlinks` | `Inlinks` | `Liens entrants` | `inlinks` |
| `Unique Inlinks` | `Inlinks únicos` | `Liens entrants uniques` | `unique_inlinks` |
| `Is In Sitemap` | `En el mapa del sitio` | `Dans le plan du site` | `in_sitemap` |
| `Word Count` | `Recuento de palabras` | `Nombre de mots` | `word_count` |
| `Size (bytes)` | `Tamaño (bytes)` | `Taille (octets)` | `size` |
| `Response Time` | `Tiempo de respuesta` | `Temps de réponse` | `response_time` |
| `Structured Data` | `Datos estructurados` | `Données structurées` | `structured_data` |
| `Redirect URL` | `URL de redirección` | `URL de redirection` | `redirect_url` |
| `Nearest Similarity Match` | `Coincidencia de similitud más cercana` | `Correspondance de similarité la plus proche` | `similarity` |
| — | `Clics` / `Clicks` | `Clics` | `clicks` |
| — | `Impresiones` / `Impressions` | `Impressions` | `impressions` |
| — | `Porcentaje de clics` / `CTR` | `CTR` | `ctr` |
| — | `Posición` / `Position` | `Position` | `position` |

**Guard de columnas críticas**: si tras el renombrado no existe `status`, la app lanza un `ValueError` con las primeras 10 columnas detectadas para facilitar el diagnóstico.

**CRÍTICO**: Con SF en español en cloud (sin `profiler_csv.py`), el SF_COL_MAP es el único mecanismo de renombrado. Antes del commit `aba754e` los exports en español no detectaban GSC ni inlinks en cloud.

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
 'impressions', 'clicks', 'ctr', 'position',
 'similarity']  # opcional — si SF exporta "Nearest Similarity Match"
```

Solo se incluyen las columnas que existen en el DataFrame fuente.

**Post-procesado de duplicados** (aplicado antes de guardar en detail_dfs):
- `T26` (dup titles): columna `grupo_dup_title` — todas las URLs con el mismo título juntas
- `T35` (dup meta): columna `grupo_dup_meta`
- `T33` (dup H1 productos): columna `grupo_dup_h1`
- `T34` (dup H1 colecciones): columna `grupo_dup_h1`

**Enriquecimiento con All Links CSV** (cuando `ruta_links_csv` se pasa a `run_audit`):

Criterio de selección: solo se enriquecen tareas donde conocer el origen del link es necesario para ejecutar el fix. Las tareas de metadatos (T08, T09, T13, etc.) no se enriquecen porque el fix se ejecuta sobre la URL directamente.

| Tarea | Columnas del Excel enriquecido | Razón |
|---|---|---|
| T02 (5xx) | `url_5xx`, `pagina_origen`, `texto_ancla`, `es_imagen` | Limpiar/avisar sobre links rotos |
| T03 (404s) | `url_404`, `pagina_origen`, `texto_ancla`, `es_imagen`, `texto_alt` + GSC | Fix: actualizar o eliminar el link |
| T04 (301s) | `url_redirect`, `redirige_a`, `pagina_origen`, `texto_ancla`, `es_imagen` | Fix: apuntar el link directamente al destino |
| T05 (doble slash) | `url_doble_slash`, `pagina_origen`, `texto_ancla`, `es_imagen` | Identificar el template que genera el link con // |
| T07 (paginación idx.) | `url_paginacion`, `pagina_origen`, `texto_ancla`, `es_imagen` | Añadir nofollow a los links de paginación |
| T16 (facetas idx.) | `url_faceta`, `pagina_origen`, `texto_ancla`, `es_imagen` | Añadir nofollow a los links de filtros |
| T19 (302s) | `url_302`, `redirige_a`, `pagina_origen`, `texto_ancla`, `es_imagen` | Igual que T04 pero para redirects temporales |
| T24 (params idx.) | `url_parametro`, `pagina_origen`, `texto_ancla`, `es_imagen` | Añadir nofollow a links con parámetros |
| T25 (URLs largas) | `url_larga`, `pagina_origen`, `texto_ancla`, `es_imagen` | Tras renombrar URL, actualizar todos los links internos |
| T32 (depth > 4) | `url_profunda`, `pagina_origen`, `texto_ancla`, `es_imagen` | Ver el path actual para diseñar el shortcut |
| T36 (links a noindex) | `pagina_origen`, `url_noindex`, `razon_noindex`, `texto_ancla`, `es_imagen` | El fix ES ir a la página origen y eliminar/nofollow; ordenado por `pagina_origen` para agrupar |

El All Links CSV se exporta desde SF → Exportación en bloque → Enlaces → "Enlaces internos Todo". Parsing flexible (detecta columnas en inglés Y español: `Source`/`Fuente`, `Destination`/`Destino`, `Anchor`/`Ancla`, `Alt Text`/`Texto ALT`, `Type`/`Tipo`).

**CRÍTICO — filtro de tipos**: SF español exporta el tipo de enlace como `Hipervínculo`. El filtro incluye `hipervínculo` e `hipervinculo` (sin tilde). Si SF exporta en otro idioma con un tipo distinto, añadirlo a la lista en la línea ~233 de audit_engine.py.

---

## Arquitectura de `app.py`

Funciones relevantes en [app.py](app.py):

- `detect_locales_from_csv(file_bytes)` — ~línea 125
- `detect_platform_from_csv(file_bytes)` — ~línea 153

### Session state — resultados persistentes

Los resultados de la auditoría se guardan en `st.session_state.audit_results` justo después de que `run_audit()` completa. Esto evita que descargar un Excel (o cualquier interacción con widgets) resetee la app y obligue a re-ejecutar la auditoría.

```python
st.session_state.audit_results = {
    'stats': stats, 'excel_bytes': excel_bytes,
    'log_lines': log_lines, 'domain_name': domain.strip(), 'fecha': fecha,
}
```

El bloque de display (tabs, dashboard, plan de tareas) se activa con `if st.session_state.get('audit_results'):` — completamente separado del `if run_btn:` que ejecuta la auditoría. El botón "🔄 Nueva auditoría" limpia `st.session_state.audit_results` y llama a `st.rerun()`.

### Estructura de la UI

```
~Línea 21    — PRESETS por plataforma (Shopify, WooCommerce, WordPress, Generic)
~Línea 260   — CSS personalizado (Inter font, .kpi-card, .seo-hero, expanders)
~Línea 540   — Hero header HTML
~Línea 551   — Sección 1: upload Internal All CSV
~Línea 588   — Sección 1b: upload All Links CSV (opcional)
~Línea 602   — Sección 2: datos del cliente (dominio, plataforma)
~Línea 619   — Sección 3: internacionalización
~Línea 650   — Sección 4: configuración avanzada
~Línea 730   — Botón "Generar Auditoría" + llamada a run_audit()
               → guarda en st.session_state.audit_results
~Línea 845   — if st.session_state.get('audit_results'): → display completo
               Botón "🔄 Nueva auditoría" + tabs de resultado:
               tab_dash   — Dashboard SEO
               tab_tasks  — Plan de Tareas (expanders + Excel por tarea)
               tab_dl     — Descargar Excel completo
               tab_log    — Log de ejecución
~Línea 870   — Dashboard: Health Score, KPIs, inventario, on-page, técnico, GSC
~Línea 1100  — Resumen Plan de Acción (4 contadores P0/P1/P2/P3)
~Línea 1125  — TAB Plan de Tareas: expanders + _make_task_excel()
```

### Tab Plan de Tareas

Cada tarea se muestra en un `st.expander` con:
- **Label del expander**: `{icono_prioridad} [TXX] Nombre de la tarea · N URLs`
- Columna izquierda (3/4): descripción, causa, qué hacer, dónde
- Columna derecha (1/4): esfuerzo/impacto/riesgo/responsable como **pills de color** (rojo=Alto, amarillo=Medio, verde=Bajo)
- Validación como caption, evidencia en `st.code`
- Si la tarea tiene Excel: botón de descarga + métrica "URLs afectadas" al lado

La función `_pill(lbl, val)` se define dentro de `with tab_tasks:` justo antes del loop de prioridades.

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
| `TypeError: unexpected keyword argument 'ruta_links_csv'` | Cloud tenía audit_engine.py viejo | Reboot en Streamlit Cloud |
| All Links `src:None` — 0 matches | SF español exporta `fuente` no `origen` | Añadido `fuente` al parser (`73bf9df`) |
| All Links `0 matches` pese a columnas OK | SF español exporta tipo como `Hipervínculo` (con tilde), no `hyperlink` — todos los links eran filtrados | Añadido `hipervínculo` e `hipervinculo` al filtro de tipos (`c895d5b`) |
| `Error tokenizing data. Expected N fields, saw M` | SF exporta CSV con columnas extra (GSC + GA4 juntos) o celdas con comas sin escapar — el C parser de pandas falla | `on_bad_lines='warn'` en ambos `read_csv` (Internal All y All Links): filas malformadas se saltan con aviso, la auditoría continúa (`813408e`) |
| GSC no detectado / inlinks=0 con SF en español en cloud | SF en español exporta `Impresiones`, `Clics`, `Inlinks`, `Nivel de profundidad`, etc. — SF_COL_MAP solo tenía nombres en inglés, así que en cloud ninguna columna española se mapeaba | SF_COL_MAP ampliado con todas las columnas en español (`aba754e`) — ver tabla completa en sección Convención de columnas |
| `KeyError: 'status'` con SF en francés | SF en francés exporta `Code de réponse` en lugar de `Status Code` — no estaba en SF_COL_MAP | SF_COL_MAP ampliado con columnas en francés + guard `ValueError` con columnas detectadas si `status` sigue ausente |
| `ValueError: Invalid character / found in sheet title` | El nombre de hoja de detalle se construye como `"{TXX} - {Tarea}"` y openpyxl prohíbe `/ \ * ? [ ] :`. T34 ("…colecciones/categorías con H1 duplicado") mete un `/` dentro de los 31 primeros caracteres. También afectaría a T37 (`/collections/all`) | `re.sub(r'[/\\*?\[\]:]', '-', _raw)` antes de truncar a 31 chars (~línea 2924 de audit_engine.py) |

### T20 — Huérfanas: comportamiento actual y pendiente

**Comportamiento actual (commit `aba754e`):**
- Detecta páginas HTML indexables con `inlinks = 0` (columna `Inlinks` / `Inlinks`)
- Con GSC: solo muestra las que tienen impresiones > T_ORPHAN_IMPRESSIONS (100)
- Sin GSC: muestra TODAS las páginas HTML+200+indexable con inlinks=0
- Usa `content_type` contains 'html' en lugar de `url_type` para funcionar con cualquier plataforma e idioma

**Pendiente / limitación conocida:**
- Si TODOS los HTML tienen inlinks ≥ 1, T20 no se activa — es correcto (no hay huérfanas por inlinks)
- La detección por `depth = null` (como hace el Colab) todavía NO está implementada
  - `depth = null` detecta páginas encontradas solo vía sitemap XML sin path de enlace interno
  - Puede ser un tipo diferente de huérfana que `inlinks = 0` no captura
  - **Fix pendiente**: añadir a T20 la señal `depth.isna()` para HTML+200+indexable donde la columna `depth` esté disponible

### Posibles fallos en los nuevos checks (T33–T48)

- **T33/T34 — H1 duplicados**: si tanto `h1` como `h1_1` están en el df, `_h1_col` usa `h1_1`. Si ninguno existe, el check no se ejecuta silenciosamente.
- **T37–T41 — Shopify**: solo se ejecutan si `PLATFORM == 'Shopify'`. Si la auto-detección de plataforma falla, estos checks no aparecen aunque el site sea Shopify.
- **T42–T48 — Structured Data**: SF no exporta la columna `Structured Data` en todos los modos de crawl. Para habilitarla: SF → Configuration → Spider → Extraction → Structured Data → activar.
- **T39 — Scoped products**: el regex `/collections/[^/?#]+/products/` puede producir falsos positivos. Revisar si aparecen URLs inesperadas.
- **All Links CSV — T02–T36**: si SF exporta el All Links con nombres de columna distintos a los esperados, el parser flexible intenta detectarlos (inglés y español) pero puede fallar silenciosamente (HAS_LINKS queda False, se usa fallback sin origen). Verificar en el log: "All Links CSV cargado: N enlaces". Si N=0 o "no se encontraron columnas", revisar el parser (~línea 201 audit_engine.py).
- **All Links filtro de tipos**: SF puede exportar con tipos en otros idiomas. Si HAS_LINKS=True pero los matches son 0, revisar si el tipo de enlace está en la lista de la línea ~233 de audit_engine.py.

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
- **Similaridad de contenido**: columna `similarity` ya mapeada (`Nearest Similarity Match` / `Coincidencia de similitud más cercana`). Páginas con `similarity > 90` son near-duplicates. Requiere que SF exporte con opción "Near Duplicates" activada: SF → Configuration → Spider → Content → Near Duplicates.

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
