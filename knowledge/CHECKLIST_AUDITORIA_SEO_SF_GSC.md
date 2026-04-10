# Checklist de auditoría SEO (Screaming Frog + GSC)

> **Uso**: lista de control para auditorías técnicas y de contenido basadas en SF + GSC.  
> **Salida esperada**: hallazgos + backlog P0–P3 + URLs priorizadas + oportunidades GSC.

---

## 0) Inputs mínimos
- [ ] Export SF (crawl completo): Internal, Response Codes, Titles, Meta, H1, Canonicals, Directives, Inlinks/Outlinks, Sitemaps, Structured Data/Validation, Images
- [ ] Export GSC: Páginas y Consultas (ideal 3/6/12 meses)
- [ ] (Opcional) robots.txt, sitemap.xml, GA4

---

## 1) Rastreo (Crawlability)
### 1.1 Status codes
- [ ] 5xx: patrón por sección/plantilla + comprobar si es intermitente
- [ ] 4xx: separar 404 con inlinks internos vs sin inlinks
- [ ] 3xx: identificar redirects con alto volumen y/o alto inlinking
- [ ] Cadenas 301 (2+ saltos): priorizar si hay inlinks o señales GSC
- [ ] Soft 404: 200 con contenido “vacío” o mensaje de error

**Tareas típicas**
- P0: 5xx, bloqueos robots, noindex accidental, canonicals erróneos
- P1: limpieza 404 con inlinks, eliminar enlazado a 301, reducir cadenas

---

## 2) Indexación (qué entra en Google)
### 2.1 Directives / meta robots
- [ ] Indexable vs noindex: ¿cuadra con la estrategia?
- [ ] Noindex en páginas objetivo ⇒ P0
- [ ] Indexable en páginas que NO deberían indexarse (gracias/login/filtros/búsqueda) ⇒ P1

### 2.2 Canonicals
- [ ] Self-canonical en páginas objetivo
- [ ] Canonical cruzado a URL no equivalente ⇒ P0/P1
- [ ] Canonical a URL con 3xx/4xx/5xx ⇒ P0
- [ ] Canonicals inconsistentes entre idiomas/países ⇒ P0/P1

### 2.3 Sitemap
- [ ] URLs en sitemap que no son indexables (noindex, 3xx, 4xx, canonicalizadas) ⇒ P1
- [ ] URLs indexables importantes fuera del sitemap ⇒ P2/P1 según impacto
- [ ] Sitemaps por idioma/país si internacional/multidioma ⇒ P1

---

## 3) Arquitectura e internlinking
### 3.1 Profundidad
- [ ] Páginas objetivo a >3 clics ⇒ P1/P2
- [ ] Secciones sin hubs (pocas rutas de acceso) ⇒ P1

### 3.2 Inlinks a 301/4xx
- [ ] 301 con muchos inlinks ⇒ P1 (actualizar enlaces al 200 final)
- [ ] 404 con inlinks ⇒ P1 (reparar enlace o redirigir)

### 3.3 Huérfanas (si hay datos)
- [ ] URLs en sitemap sin inlinks ⇒ P2/P1 si son core

---

## 4) Metadatos (Title & Meta description)
### 4.1 Titles
- [ ] Faltantes / duplicados / muy largos / muy cortos
- [ ] Titles no alineados con intención (GSC query)
- [ ] Idioma incorrecto en carpetas multiidioma ⇒ P1

### 4.2 Meta descriptions
- [ ] Faltantes / duplicadas masivas
- [ ] Oportunidades CTR: impresiones altas + CTR bajo ⇒ P1

---

## 5) Headings (H1/H2)
- [ ] H1 faltante / múltiple / duplicado masivo
- [ ] H1 poco descriptivo en páginas objetivo
- [ ] Coherencia H1–Title–Query (GSC) ⇒ P1

---

## 6) Contenido (calidad, duplicidad, canibalización)
### 6.1 Thin / baja aportación
- [ ] Poco texto + sin cobertura de intención
- [ ] URLs con impresiones en 11–20 ⇒ P1 (ampliar + intent match)

### 6.2 Duplicidad por ubicación/idioma/taxonomías
- [ ] Titles/H1 muy similares entre landings ⇒ revisar canibalización
- [ ] Contenido repetido en ubicaciones (solo cambia topónimo) ⇒ P1/P2
- [ ] Tags/autor/categorías indexadas sin valor (publisher) ⇒ P1

### 6.3 Canibalización (GSC)
- [ ] Misma query con múltiples URLs alternándose ⇒ consolidar/diferenciar intención

---

## 7) Internacional / multidioma (si aplica)
- [ ] Hreflang correcto y recíproco
- [ ] `x-default` si procede
- [ ] Canonicals coherentes con hreflang (no romper alternates)
- [ ] Titles/metas/H1 en idioma correcto por carpeta/host
- [ ] Sitemaps por idioma/país si escala ⇒ P1

---

## 8) Datos estructurados (Schema)
- [ ] Schema presente en plantillas core
- [ ] Errores de validación (si se exportan)
- [ ] Tipos típicos:
  - Servicios: `LocalBusiness`, `Service`, `FAQPage` (si procede), `BreadcrumbList`
  - Ecommerce: `Product`, `Offer`, `AggregateRating` (si aplica), `BreadcrumbList`
  - Publisher: `Article`/`NewsArticle`, `BreadcrumbList`
- [ ] Breadcrumb schema coherente con arquitectura

---

## 9) Imágenes
- [ ] Imágenes 404 o con redirects
- [ ] ALT faltante en plantillas relevantes
- [ ] Peso excesivo en páginas core (si SF lo reporta) ⇒ P2/P1 si afecta CWV

---

## 10) Ecommerce (si aplica)
- [ ] Facetas/filtros: indexación no controlada (parámetros) ⇒ P0/P1
- [ ] Paginación: canonicals/noindex según estrategia ⇒ P1
- [ ] Productos agotados: estrategia clara ⇒ P1
- [ ] Variantes: evitar duplicados por parámetros/URLs ⇒ P1
- [ ] Categorías thin: ampliar + hubs ⇒ P1

---

## 11) Servicios (si aplica)
- [ ] Landings por servicio/ubicación: evitar duplicidad “solo cambia ciudad”
- [ ] Hubs por intención (qué/para quién/cómo/precio/zonas) ⇒ P1/P2
- [ ] Enlazado cruzado: servicio ↔ ubicaciones ↔ recursos/blog ⇒ P1

---

## 12) Publisher/Medio (si aplica)
- [ ] Taxonomías indexadas sin valor (tags infinitos) ⇒ P1
- [ ] Paginaciones indexadas innecesarias ⇒ P1/P2
- [ ] Duplicados por autor/categoría ⇒ P1

---

## 13) GSC: oportunidades
- [ ] CTR: impresiones altas + CTR bajo ⇒ Title/Meta + intent match
- [ ] Rankings 11–20 con impresiones ⇒ empuje top10 (contenido + enlaces internos + snippet)
- [ ] Canibalización por query ⇒ consolidación/reestructura

---

## 14) Convertir checklist en Excel
- [ ] Hoja “Resumen” (crawl + señales GSC)
- [ ] Hoja “Tareas” (P0–P3 con evidencia + pasos + validación)
- [ ] Hoja “URLs - Prioridad”
- [ ] Hoja “Oportunidades GSC”

**Regla final**
- Si una “tarea” no tiene “qué hacer” y “cómo validar”, no es tarea: es una nota. Convierte notas en tareas.
