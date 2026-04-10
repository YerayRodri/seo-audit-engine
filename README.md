# seo-audit-claude

Herramienta de auditoría SEO técnica para Claude Code. Transforma exports de Screaming Frog y Google Search Console en un Excel priorizado con backlog P0–P3, listo para SEO, Dev y Contenido.

Desarrollada en [VON — Visibilidad On](https://visibilidadon.com).

---

## Qué hace

A partir de un crawl de Screaming Frog y datos de GSC, genera automáticamente:

- **Hoja Resumen** — métricas del crawl, señales GSC y alertas principales
- **Hoja Tareas** — backlog priorizado P0–P3 con evidencia, causa, pasos y validación
- **Hoja URLs - Prioridad** — tabla de URLs problemáticas cruzada con SF y GSC
- **Hoja Oportunidades GSC** — CTR bajo, posiciones 11–20, canibalización, impresiones sin clics

El Excel se guarda automáticamente en `~/Downloads/auditoria-seo-[dominio]-[fecha].xlsx`.

---

## Qué mejora respecto a ChatGPT

| Capacidad | ChatGPT GPT | Este skill |
|---|---|---|
| Datos GSC | Export manual obligatorio | MCP directo (sin exportar) |
| Enriquecimiento keywords | No | DataForSEO: volumen + dificultad real |
| Datos GA4 / conversiones | Export manual | MCP directo |
| Tamaño de dataset | Limitado (sandbox) | Sin límite (Python real en sistema) |
| Archivo Excel | Descarga manual | Escrito en `~/Downloads/` automáticamente |
| Timeouts | Frecuentes en auditorías grandes | No existen |
| Priorización | Estática | Dinámica: cruzada con señales GSC + GA4 |

---

## Requisitos

- [Claude Code](https://claude.ai/code) instalado
- Python 3.9+ con `pandas`, `openpyxl` instalados:
  ```bash
  pip install pandas openpyxl
  ```
- Screaming Frog con export **Internal All** del sitio a auditar

### Opcionales (mejoran mucho la auditoría)

- **MCP Google Search Console** — evita exportar GSC manualmente y permite Query×Page completo
- **MCP DataForSEO** — añade volumen de búsqueda y keyword difficulty a las oportunidades GSC
- **MCP Google Analytics 4** — cruza URLs con conversiones/revenue para priorizar mejor

Sin MCPs, la herramienta funciona igual con los exports de archivo estándar.

---

## Instalación

```bash
# 1. Clona el repo
git clone https://github.com/tu-usuario/seo-audit-claude.git
cd seo-audit-claude

# 2. Abre Claude Code en la carpeta del repo
claude
```

> **Importante**: Claude Code debe abrirse desde la carpeta raíz del repo para que el skill encuentre los archivos de `knowledge/`.

---

## Uso

Una vez dentro de Claude Code con el repo como directorio de trabajo:

```
/auditoria-seo
```

El skill arranca automáticamente:

1. Carga la base de conocimiento interna
2. Detecta qué MCPs están disponibles (GSC, DataForSEO, GA4)
3. Hace 5 preguntas de contexto del proyecto
4. Pide los archivos necesarios (solo los que falten según MCPs disponibles)
5. Analiza, prioriza y genera el Excel

---

## Archivos que puede pedir

| Archivo | Obligatorio | Cómo exportarlo |
|---|---|---|
| SF — Internal All | Siempre | Screaming Frog → Bulk Export → All Inlinks |
| GSC — Páginas | Si no hay MCP GSC | Search Console → Rendimiento → Páginas → Exportar |
| GSC — Consultas | Si no hay MCP GSC | Search Console → Rendimiento → Consultas → Exportar |
| GSC — Query×Page | Recomendado | Search Console → Rendimiento → exportar con ambas dimensiones |
| GA4 — Landing orgánica | Si no hay MCP GA4 | GA4 → Informes → Adquisición → Orgánico |
| robots.txt | Opcional | Descargar directamente de `dominio.com/robots.txt` |
| sitemap.xml | Opcional | Descargar de `dominio.com/sitemap.xml` |

Acepta archivos `.csv`, `.xlsx` y `.zip` (exports de GSC en ZIP).

---

## Estructura del repositorio

```
seo-audit-claude/
├── .claude/
│   └── skills/
│       └── auditoria-seo.md        ← skill principal (/auditoria-seo)
├── knowledge/
│   ├── CHECKLIST_AUDITORIA_SEO_CORE.md
│   ├── CHECKLIST_AUDITORIA_SEO_SF_GSC.md
│   ├── GUIA_INGESTA_DATOS_SF_GSC.md
│   ├── NOTAS_IMPLEMENTACION_TECNICA_PROMPT.md
│   ├── NOTA_PLANTILLA_EJEMPLO_SALIDA.md
│   └── REGLAS_PRIORIZACION_P0_P3_SEO.md
├── templates/
│   └── EJEMPLO_SALIDA_AUDITORIA_SEO_PLANTILLA.xlsx  ← referencia de formato
└── README.md
```

---

## Qué analiza

- **Rastreo e indexación** — 5xx, noindex accidental, canonicals rotos, sitemap inconsistente
- **Arquitectura e internlinking** — crawl depth, hubs débiles, páginas sin soporte interno
- **Metadatos** — titles/metas duplicados, vacíos o desalineados con la query
- **Headings** — H1 faltante, duplicado, incoherente con title o con intención
- **Contenido** — thin content, duplicidad de plantilla, posiciones 11–20 con potencial
- **GSC** — CTR bajo, impresiones sin clics, canibalización (con Query×Page)
- **Internacional** — hreflang, carpetas legacy, idioma incorrecto en metadatos
- **Ecommerce** — filtros indexables, PLP thin, PDP duplicadas, productos agotados
- **Schema e imágenes** — si los datos de SF lo permiten

---

## Priorización

Cada tarea lleva P0–P3 calculado por impacto, urgencia, esfuerzo y riesgo:

| Prioridad | Descripción | Plazo |
|---|---|---|
| P0 | Bloqueo o riesgo alto inmediato | 0–7 días |
| P1 | Alto impacto en visibilidad o eficiencia | 2–4 semanas |
| P2 | Optimización relevante | 1–3 meses |
| P3 | Mantenimiento o mejora menor | Backlog continuo |

---

## Contribuir

Pull requests bienvenidos. Para cambios grandes, abre un issue primero.

Si mejoras el skill o los docs de knowledge, asegúrate de que:
- El método sigue siendo reproducible y basado en evidencia
- Las reglas de priorización son consistentes
- No se introducen hallazgos sin evidencia mínima (nº URLs + ejemplos + causa + acción + validación)
