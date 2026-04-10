# NOTAS_IMPLEMENTACION_TECNICA — Claude Code

> Uso: referencia técnica para que Claude Code ejecute auditorías SEO de forma robusta y eficiente.
> Esta versión reemplaza la anterior orientada a ChatGPT/Code Interpreter.

---

## 1) Entorno de ejecución

Claude Code ejecuta Python directamente en el sistema mediante la herramienta Bash.
No hay sandbox, no hay límites de memoria artificiales, no hay timeouts de sesión.

**Ventajas respecto a ChatGPT Code Interpreter:**
- Datasets grandes (>100k filas) sin problemas de memoria
- Escritura directa de archivos en el sistema (`~/Downloads/`)
- Acceso a MCPs para datos en tiempo real (GSC, DataForSEO, GA4)
- Sin resets de sesión ni pérdida de variables entre pasos

---

## 2) Librerías Python disponibles

### Core (siempre disponibles en macOS/pip estándar)
- `pandas` — lectura, joins, groupby, pivots, reglas vectorizadas, export final
- `numpy` — flags, condiciones y cálculos auxiliares
- `re` — regex para clasificar URLs y detectar patrones
- `urllib.parse` — normalización segura de URLs
- `pathlib` / `os` — manejo de rutas del sistema
- `zipfile` / `glob` — lectura de exports comprimidos y búsqueda de archivos
- `openpyxl` — escritura y formato del Excel final con estilos completos
- `datetime` — timestamping del output

### Instalar si no está disponible
```bash
pip install pandas openpyxl tldextract
```

### Opcionales
- `tldextract` — útil para multidominio complejo
- `networkx` — solo si hay inlinks fiables y se quiere análisis de grafo real
- `chardet` — para detectar encoding de CSVs problemáticos

---

## 3) Patrones de código que funcionan bien

### A) Lectura robusta de CSVs con encoding desconocido
```python
def leer_csv_robusto(ruta):
    for enc in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
        try:
            return pd.read_csv(ruta, low_memory=False, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo leer {ruta}")
```

### B) Lectura de ZIP de GSC
```python
import zipfile, io
def leer_zip_gsc(ruta_zip):
    with zipfile.ZipFile(ruta_zip) as z:
        csvs = [f for f in z.namelist() if f.endswith('.csv')]
        return {os.path.basename(f): pd.read_csv(z.open(f)) for f in csvs}
```

### C) Normalización de URLs (usar siempre antes de merge)
```python
from urllib.parse import urlparse, unquote
def normalize_url(url):
    if pd.isna(url): return url
    url = unquote(str(url)).strip().lower()
    parsed = urlparse(url if url.startswith('http') else 'https://' + url)
    path = parsed.path.rstrip('/') or '/'
    return f"https://{parsed.netloc}{path}"
```

### D) Reglas vectorizadas (evitar loops)
```python
# Bien: vectorizado
df['es_thin'] = (df['word_count'].fillna(0) < 200) & df['tipo_url'].isin(['categoria','servicio'])

# Mal: loop fila a fila
for i, row in df.iterrows():
    if row['word_count'] < 200: ...  # lento en datasets grandes
```

### E) Formato Excel con openpyxl
```python
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

def autofit_columns(ws, min_w=10, max_w=50):
    for col in ws.columns:
        width = max((len(str(c.value or '')) for c in col), default=min_w)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(width + 2, min_w), max_w)
```

---

## 4) Fuentes de datos: MCP vs archivos

### GSC vía MCP (`mcp__google-search-console__search_analytics`)
- Ventaja: datos frescos, sin límite de export manual, acceso a más de 1000 filas
- Usar `rowLimit: 25000` para cubrir sitios grandes
- Dimensiones disponibles: `page`, `query`, `country`, `device`, `date`
- Para Query×Page: `dimensions: ["query", "page"]`

### DataForSEO vía MCP
- `dataforseo_labs_google_keyword_overview` — volumen, KD, CPC por keyword
- `backlinks_summary` — perfil de backlinks si se necesita
- `serp_organic_live_advanced` — SERP real para queries concretas
- Usar batches de 10 keywords para no superar rate limits

### GA4 vía MCP (`mcp__analytics-vonX__run_report`)
- Métricas útiles: `sessions`, `conversions`, `totalRevenue`
- Dimensión: `landingPage` cruzada con `sessionDefaultChannelGroup = 'Organic Search'`
- Usar para subir prioridad de URLs con revenue

### Fallback a archivos
- Screaming Frog: siempre obligatorio como archivo (no hay MCP para SF)
- GSC exports: válidos si no hay MCP; aceptar ZIP tal cual
- GA4: export de landing pages con canal orgánico

---

## 5) Secuencia de ejecución optimizada

```
1. Carga knowledge files (Read en paralelo)
2. Detección MCPs (llamadas en paralelo, silenciosas)
3. Onboarding (5 preguntas + archivos)
4. Inventario del dataset
5. Normalización URLs
6. Clasificación URLs
7. Módulos de diagnóstico A–H (por orden de impacto)
8. Enriquecimiento DataForSEO (si disponible)
9. Priorización P0–P3
10. Generación Excel (~/Downloads/)
11. Resumen textual
```

---

## 6) Heurísticas de calidad

### Priorización
Subir prioridad cuando coinciden:
- Página transaccional o core (tipo: categoria, servicio, producto, landing, home)
- Error técnico o duplicidad fuerte (status ≠ 200, noindex, canonical roto)
- Señales GSC (impresiones > 100, posición < 30)
- Revenue/conversión si hay GA4

### 404
- Con inlinks internos o impresiones GSC → P1
- Sin señales → P2/P3

### 3xx
Priorizar: cadenas, enlazados internamente, en sitemap, con señales GSC

### Thin content
- Solo reportar si hay datos de word_count en SF o cruce con posición GSC débil
- No inferir thin content sin evidencia del dataset

### Internacional
- Detectar automáticamente carpetas `/es/`, `/en/`, `/fr/`, etc.
- No asumir hreflang si SF no lo exportó
- Señalar idioma incorrecto en titles/H1 si la carpeta y el contenido no coinciden

---

## 7) Regla de robustez

Si una parte del análisis no puede demostrarse con el dataset disponible:
- No inventarla
- Añadir hallazgo con `prioridad: 'pendiente'` y `causa: 'dataset insuficiente'`
- Continuar con el resto del análisis

El backlog final solo contiene lo que el dataset soporta.
