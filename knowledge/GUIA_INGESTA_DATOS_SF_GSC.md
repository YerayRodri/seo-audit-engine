# GUIA_INGESTA_DATOS_SF_GSC

> Uso: guía para pedir, aceptar y mapear inputs del usuario con la menor fricción posible.

## 1) Qué pedir al usuario
### Obligatorio
- Screaming Frog: **Internal All**
- GSC: export tal cual de **Páginas** y **Consultas**
- Ideal: **Query × Page**

### Opcional
- GA4 landing orgánica + conversiones/revenue
- robots.txt
- sitemap.xml
- exports secundarios de SF si ya los tiene

## 2) Cómo pedirlo
Pedirlo de forma simple:
- “Sube el export **Internal All** de Screaming Frog”
- “Sube los exports de GSC tal cual: **Páginas** y **Consultas**”
- “Si tienes **Query × Page**, súbelo también; mejora mucho la detección de canibalización”
- “Si no tienes más archivos, no pasa nada: analizaré lo disponible”

## 3) Qué no hacer
- No exigir muchos exports separados si ya existe Internal All
- No pedir al usuario que limpie o transforme GSC manualmente
- No bloquear el análisis por no tener Inlinks, Directives o Structured Data
- No pedir de nuevo información ya deducible

## 4) Mapeo mínimo esperado
### Internal All
Buscar equivalentes de:
- Address / URL
- Status Code
- Indexability
- Title 1
- Meta Description 1
- H1-1
- H2-1
- Canonical Link Element 1
- Meta Robots 1
- Crawl Depth
- Inlinks
- Is In Sitemap
- Content Type
- Lang / Hreflang si existe

### GSC Páginas
- Page / URL
- Clicks
- Impressions
- CTR
- Position

### GSC Consultas
- Query
- Clicks
- Impressions
- CTR
- Position

### GSC Query × Page
- Query
- Page
- Clicks
- Impressions
- CTR
- Position

## 5) Decisiones rápidas por disponibilidad
### Si solo hay Internal All
- hacer auditoría técnica y estructural
- dejar GSC como pendiente

### Si hay Internal All + GSC Pages/Queries
- hacer auditoría completa sin canibalización real
- detectar CTR bajo, 11–20, impresiones sin clics

### Si además hay Query × Page
- añadir canibalización real y oportunidades por query-url

### Si además hay GA4
- subir prioridad de URLs con revenue/conversión

## 6) Alertas de interpretación
- Internal All suele ser suficiente para un primer backlog muy sólido
- GSC “tal cual” es válido; no exigir pivots
- Query × Page es el único dataset fiable para canibalización real
