# Development Log — SEO Audit Engine

> Documento de contexto para IAs (Copilot, Claude Code, Claude) que retomen el proyecto.  
> Actualizado: abril 2026.

---

## Resumen del proyecto

Herramienta Streamlit de auditoría SEO técnica. Lee exports de **Screaming Frog** (Internal All CSV) y opcionales de **Google Search Console** (páginas, consultas, query×page), ejecuta 32 checks (T01–T32), genera un **Excel de 4 hojas** priorizado P0–P3, y muestra un **dashboard visual** con Health Score.

| Archivo | Tamaño | Responsabilidad |
|---|---|---|
| `app.py` | ~1090 líneas | UI Streamlit: formulario, tabs, dashboard, CSS |
| `audit_engine.py` | ~2227 líneas | Motor de análisis: T01–T32, Excel output |
| `requirements.txt` | — | `streamlit==1.56.0`, `pandas==3.0.2`, `openpyxl==3.1.5` |
| `knowledge/` | — | Checklists, guías de priorización (uso del skill Claude Code) |

Stack: Python 3.9+, Streamlit 1.56.0, pandas 3.0.2, openpyxl 3.1.5  
Repo: `https://github.com/YerayRodri/seo-audit-engine` · branch `main`  
venv: `.venv/` en la raíz del repo

---

## Arquitectura de `audit_engine.py`

Solo dos funciones públicas:

```python
def load_config(config_path): ...  # carga config YAML/dict
def run_audit(cfg, ruta_csv, output_path): ...  # ejecuta T01–T32, escribe Excel
```

### Checks implementados (T01–T32)

| Rango | Categoría | Prioridad típica |
|---|---|---|
| T01–T03 | Bloqueos críticos (robots, 5xx, 4xx) | P0 |
| T04–T07 | Redirects, doble slash, cart, paginación | P1 |
| T08–T14 | Meta descriptions, H1, titles, canonicals | P1–P2 |
| T15–T20 | Thin content, hreflang, internlinking, CSS/JS | P1–P2 |
| T21–T32 | Sitemaps, speed, params, URLs largas, depth | P1–P2 |

### Convenciones de columnas (CRÍTICO)

La columna de Screaming Frog `Indexability` se normaliza internamente como **`indexable`** (nunca `indexability`).

Columna correcta → `df['indexable']`  
Columna incorrecta → ❌ `df['indexability']` → KeyError

El mapa completo vive en `SF_COL_MAP` dentro de `audit_engine.py`.

### Health Score

```python
score = max(0, 100 - min(36, P0×12) - min(24, P1×3) - min(10, P2×1))
```

---

## Arquitectura de `app.py`

### Estructura principal

```
CSS (líneas ~258–553)
Hero HTML (línea ~555)
Formulario (col_left / col_right)
  └─ Upload SF CSV (obligatorio)
  └─ Upload GSC ZIPs (opcionales)
  └─ Config: dominio, threshold speed, umbral CTR, etc.
Botón "Generar Auditoría"
  └─ run_audit() → guarda Excel en ~/Downloads/
Tabs resultado:
  ├─ tab_dl   → descarga Excel
  ├─ tab_log  → log de checks ejecutados
  └─ tab_dash → dashboard visual
        ├─ Health Score + 4 KPI cards HTML (.kpi-card)
        ├─ Inventario del Crawl (métricas SF)
        ├─ Calidad On-Page (st.metric nativo)
        ├─ Técnico (_tc_card() HTML helper)
        ├─ Señales GSC (.kpi-card HTML, solo si has_gsc)
        └─ Plan de Acción (expanders P0–P3)
Footer Visibilidad ON
```

### Helper `_tc_card()` (definido dentro de `with tab_dash:`)

```python
def _tc_card(label, value, warn=False, na=False):
    # Devuelve HTML div con borde ámbar si warn=True, gris italic si na=True
    # font-size 1.75rem weight 800, label uppercase
```

**Ojo:** está definido dentro del bloque `with tab_dash:`. Si causa problemas de re-render, moverlo a nivel de módulo.

---

## Design system CSS (en `app.py`)

### Principio fundamental

La fuente **NO** se aplica con `*` ni `span` — esos selectores rompen los web components internos de Streamlit produciendo:
- `"uploadupload"` (texto del file uploader duplicado)
- `"_arr"` prefijando los títulos de expanders

**Selector correcto:**
```css
html, body, .stApp, .block-container {
    font-family: 'Inter', ...;
}
input, textarea, select, button { font-family: inherit !important; }
```

### Clases CSS disponibles

| Clase | Uso |
|---|---|
| `.seo-hero` | Hero oscuro gradiente con efectos radiales |
| `.seo-hero-badge` | Pill "⚡ Technical SEO Tool" |
| `.dash-section` | Header de sección en el dashboard (flex, border-bottom) |
| `.section-header` / `.section-number` | Headers del formulario con número en pill |
| `.kpi-card` | Card blanca con hover. Contiene `.kpi-label`, `.kpi-value`, `.kpi-sub` |
| `.seo-footer` | Footer centrado con borde top |

### Expanders — regla crítica

**NUNCA** añadir CSS a `[data-testid="stExpander"] [role="button"]` sin combinator `>`.  
El selector sin `>` matchea un span oculto interno y lo hace visible con texto "_arr".

Solo estilizar el contenedor:
```css
[data-testid="stExpander"] {
    border, border-radius, background, margin, box-shadow
    /* SIN overflow:hidden — rompe el layout flex del header */
}
```

---

## Historial de commits significativos

| Commit | Descripción |
|---|---|
| `14f1946` | Initial commit |
| `4df349c` | Dashboard visual con tabs — Health Score, inventario, on-page, técnico, GSC, tareas |
| `9d705cd` | Footer Visibilidad ON |
| `06283d8` | Fix KeyError: `indexability` → `indexable` en T21, T22, T27 |
| `ecc0269` | Fix NameError: `import pandas as pd` faltaba en app.py |
| `681a5f3` | Aesthetic overhaul: Inter, `.kpi-card`, hero mejorado, `.dash-section` |
| `c6b5a84` | Fix solapamiento textos: selector font acotado, expander overflow hidden eliminado |
| `c49331d` | Fix definitivo: fuente solo en contenedores, header expander sin tocar |

HEAD actual: `c49331d`

---

## Bugs conocidos y sus soluciones

### "uploadupload" — Texto duplicado en file uploader

**Causa:** `* { font-family }` o `span { font-family }` inyectan la fuente en el shadow DOM del componente web de Streamlit, duplicando el texto del label.  
**Solución:** Usar solo `html, body, .stApp, .block-container` + `input, textarea, select, button { font-family: inherit }`.

### "_arr" prefijando expanders

**Causa:** `[data-testid="stExpander"] [role="button"]` (sin `>`) matchea un span interno de la chevron SVG container que tiene texto "_arr".  
**Solución:** Nunca añadir CSS al header del expander. Solo estilizar el contenedor `[data-testid="stExpander"]`.

### `overflow: hidden` en expanders

**Causa:** `overflow: hidden` en el contenedor del expander colapsa el flex layout del header y la flecha se renderiza encima del texto.  
**Solución:** Eliminar `overflow: hidden` del selector `[data-testid="stExpander"]`.

### KeyError `indexability`

**Causa:** La columna de SF se llama `Indexability` (mayúscula) pero el motor la normaliza a `indexable` (lower, sin `-ity`). Cualquier código nuevo que use `df['indexability']` falla.  
**Solución:** Siempre usar `df['indexable']`.

### NameError `pd` en `app.py`

**Causa:** `app.py` importa funciones de `audit_engine` que usan pandas, pero no tenía `import pandas as pd` propio.  
**Solución:** Añadir `import pandas as pd` al bloque de imports de `app.py`.

---

## Cómo arrancar el entorno

```bash
cd /Users/yerayrodriguez/Proyectos-Claude/VON/seo-audit-claude
source .venv/bin/activate
streamlit run app.py
```

---

## Próximos pasos posibles (sin implementar)

- Unificar `audit_newcop.py`, `audit_newcop_v2.py`, `audit_step1.py` (archivos legacy sin uso activo)
- Mover `_tc_card()` a nivel de módulo
- Responsive: ajustar `st.columns([1.8, 1, 1, 1, 1])` en pantallas estrechas
- Tests unitarios para los checks T01–T32
