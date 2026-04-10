# CHECKLIST_AUDITORIA_SEO_CORE

> Uso: lista de control operativa para auditorías SEO basadas en Screaming Frog + GSC.
> Objetivo: convertir datasets reales en backlog P0–P3 + URLs priorizadas + oportunidades GSC.

## 1) Inputs mínimos y filosofía
### Inputs mínimos obligatorios
- Screaming Frog: **Internal All**
- GSC: export tal cual de **Páginas** y **Consultas**
- Ideal: **Query × Page**
- Opcional: GA4 landing orgánica + conversiones/revenue, robots.txt, sitemap.xml

### Regla clave
- No bloquear la auditoría por faltar exports secundarios.
- Si falta algo, marcar **pendiente de confirmar** y seguir.

## 2) Inventario inicial
Antes de analizar:
- Confirmar qué archivos existen
- Detectar hojas/columnas disponibles
- Localizar columnas equivalentes aunque cambien de idioma o naming
- Identificar limitaciones del dataset

## 3) Normalización obligatoria
Antes de cruzar SF con GSC:
- quitar `#fragment`
- separar path y querystring
- normalizar slash final
- unificar esquema y host cuando aplique
- decodificar `%xx` si procede
- detectar idioma/carpeta/mercado
- crear `url_normalizada`
- evitar duplicados falsos por formato

## 4) Clasificación de URLs
Clasificar al menos en:
- home
- categoría / colección / listing
- producto / ficha
- página informativa
- blog / post
- búsqueda interna
- cuenta / login / registro
- carrito / checkout
- filtros / facetas / parámetros
- paginación
- otras

## 5) Módulos de análisis
### A. Rastreo e indexación
- status codes 2xx / 3xx / 4xx / 5xx
- indexable vs noindex
- páginas que no deberían indexarse
- URLs en sitemap vs fuera
- errores en páginas con señales GSC o negocio
- redirecciones internas relevantes

### B. Arquitectura e internlinking
- crawl depth
- páginas objetivo demasiado profundas
- enlazado insuficiente hacia categorías/productos/landings core
- páginas con señales GSC y poco soporte interno
- hubs débiles

### C. Metadatos
- titles faltantes / duplicados / débiles
- metas faltantes / duplicadas / pobres
- idioma incorrecto
- patrones masivos de plantilla

### D. Headings
- H1 faltante / duplicado / poco descriptivo
- incoherencia H1–Title
- headings no alineados con query e intención

### E. Contenido
- thin content
- baja aportación en plantillas core
- duplicidad de plantilla
- páginas con impresiones y cobertura deficiente
- URLs 11–20 con oportunidad de upgrade

### F. GSC
- CTR bajo
- posiciones 11–20
- impresiones sin clics
- queries con potencial
- canibalización solo con Query × Page

### G. Internacional
- estructura por idioma/mercado
- versiones legacy
- duplicidades entre países/idiomas
- idioma incorrecto en títulos/H1
- señales hreflang/canonical si el dataset las permite

### H. Ecommerce
- colecciones/categorías
- productos estratégicos
- filtros/facetas indexables
- ordenación
- páginas tipo /all o equivalentes
- PLP thin
- PDP débiles
- duplicidad por variantes/mercados

### I. Schema e imágenes
Solo si hay datos suficientes.
Si no, marcar pendiente.

## 6) Regla de canibalización
Sin Query × Page:
- sí detectar sospechas y dejarlo como oportunidad
- no afirmar canibalización real

Con Query × Page:
- sí detectar solapamiento por query
- sí recomendar consolidación, diferenciación o reintento interno

## 7) Evidencia mínima por hallazgo
Cada hallazgo debe poder transformarse en tarea con:
- nº de URLs afectadas
- 1–5 ejemplos
- señal GSC si aplica
- causa probable
- pasos concretos
- validación

## 8) Criterio de calidad
Si una observación no incluye “qué hacer” y “cómo validarlo”, todavía no es backlog.
