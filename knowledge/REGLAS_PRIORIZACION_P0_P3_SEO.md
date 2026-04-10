# Guía interna de priorización SEO (P0–P3)

> **Uso**: Este documento define cómo priorizamos tareas SEO en auditorías basadas en **Screaming Frog (SF)** y **Google Search Console (GSC)**.  
> **Objetivo**: producir un backlog consistente, accionable y comparable entre proyectos.

---

## 1) Definición de prioridades

### P0 — Bloqueo / Riesgo alto inmediato
**Qué es**
- Problemas que **impiden** rastreo/indexación correcta o pueden causar pérdida notable de tráfico/ventas/leads.
- Errores críticos a nivel técnico o de plantilla que afectan a gran parte del sitio.

**Ejemplos típicos**
- 5xx masivos o intermitentes
- Robots.txt bloqueando secciones relevantes
- `noindex` en plantillas clave (home, categorías, servicios, landings principales)
- Canonicals incorrectos a URLs no equivalentes
- Hreflang roto que genera indexación errónea por país/idioma
- 404/410 en URLs con tráfico o enlaces internos importantes
- Cadenas 301 con mucho inlinking (desperdicio de señales + crawl)

**Plazo recomendado**
- **0–7 días**

---

### P1 — Alto impacto (crecimiento y eficiencia)
**Qué es**
- Tareas que mejoran visibilidad y captación de forma clara, sin ser bloqueo total.
- Correcciones masivas que elevan calidad y relevancia del sitio.

**Ejemplos típicos**
- Titles/metas duplicadas o faltantes en plantillas importantes
- Contenido thin en landings/categorías con impresiones en GSC
- Canibalización evidente entre URLs (misma intención)
- Enlazado interno insuficiente hacia páginas objetivo
- Datos estructurados ausentes/incorrectos en plantillas clave

**Plazo recomendado**
- **2–4 semanas**

---

### P2 — Optimización (impacto medio)
**Qué es**
- Mejoras incrementales: limpiezas, refinamientos de arquitectura y contenido, ajustes puntuales de CTR.

**Ejemplos**
- Ajustes de H1/H2, mejora de legibilidad, ampliaciones moderadas
- Optimización de imágenes (ALT, peso) en páginas relevantes
- Ajustes de paginación y facetas con bajo riesgo
- Mejoras de enlazado interno secundarias

**Plazo recomendado**
- **1–3 meses**

---

### P3 — Mantenimiento / Experimentación
**Qué es**
- Acciones de mejora continua, experimentos o tareas con impacto incierto.

**Ejemplos**
- Tests A/B de titles
- Refuerzos de enlazado interno de baja prioridad
- Refrescos de contenido sin señales claras en GSC

**Plazo recomendado**
- **Backlog continuo**

---

## 2) Cómo calculamos prioridad (método rápido)

Asignamos 4 valores: **Impacto**, **Urgencia**, **Esfuerzo**, **Riesgo**.

### Escalas (1–3)
**Impacto**
- 1 = Bajo (afecta pocas URLs o poca relevancia)
- 2 = Medio (afecta URLs relevantes o muchas URLs con poca importancia)
- 3 = Alto (afecta plantillas/páginas core o URLs con tráfico/impresiones altas)

**Urgencia**
- 1 = Puede esperar
- 2 = Recomendable este mes
- 3 = Hay pérdida/daño activo o riesgo alto

**Esfuerzo**
- 1 = Bajo (cambio simple, 1–2h, sin dependencias)
- 2 = Medio (requiere dev/cambios de plantilla, validación)
- 3 = Alto (re-arquitectura, migración, múltiples equipos)

**Riesgo (SEO/Negocio)**
- 1 = Bajo (cambio seguro)
- 2 = Medio (requiere QA)
- 3 = Alto (posibles efectos colaterales; plan de rollback)

### Regla de decisión
- **P0**: (Impacto=3 y Urgencia=3) o cualquier caso con **riesgo de desindexación / 5xx / bloqueo**.
- **P1**: Impacto≥2 y Urgencia≥2.
- **P2**: Impacto=2 con urgencia baja, o impacto bajo con buena relación esfuerzo.
- **P3**: Impacto=1 y urgencia=1 o experimentación.

**Atajo numérico (opcional)**
- **Score** = (Impacto × Urgencia) − (Esfuerzo − 1)
  - 8–9 ⇒ P0
  - 5–7 ⇒ P1
  - 3–4 ⇒ P2
  - 1–2 ⇒ P3

---

## 3) Evidencia mínima obligatoria por tarea

Cada tarea debe incluir SIEMPRE:
- **Evidencia cuantitativa**: nº de URLs afectadas (SF) y/o señales GSC (impresiones, CTR, posición).
- **Ejemplos**: 1–5 URLs representativas.
- **Causa probable**: plantilla, configuración, contenido, enlazado, etc.
- **Qué hacer**: pasos concretos.
- **Validación**: cómo comprobar (SF/GSC/inspección URL).

---

## 4) Estándar de redacción (para Excel)

### Columnas obligatorias (mínimo)
- ID
- Prioridad (P0–P3)
- Categoría (Rastreo/Indexación, Metadatos, Contenido, Estructurados, Internlinking, Internacional, Rendimiento, KPIs…)
- Tarea (breve)
- Descripción corta
- Evidencia (nº URLs + señales GSC)
- Causa probable
- Qué hacer (pasos concretos)
- Dónde detectarlo (SF/GSC)
- Esfuerzo (Bajo/Medio/Alto)
- Impacto (Bajo/Medio/Alto)
- Riesgo (Bajo/Medio/Alto)
- Responsable sugerido (SEO/Dev/Contenido)
- Validación (cómo comprobar)
- URLs ejemplo

### Mini-plantilla de tarea
- **Tarea**: …
- **Evidencia**: …
- **Qué hacer**: …
- **Validación**: …

---

## 5) Definition of Done (DoD)

Una tarea se considera finalizada cuando:
- El cambio está en producción
- Se ha pasado **recrawl** (SF) y el problema desaparece (o queda bajo umbral)
- Si afecta indexación: validación en **GSC (Inspección de URL / Sitemaps / indexación)**
- Si afecta CTR/rankings: registrar fecha de despliegue y revisar en 14–28 días

---

## 6) Umbrales rápidos (para decidir urgencia)

- `noindex` en páginas objetivo ⇒ **P0**
- Canonical a URL no equivalente o con 3xx/4xx/5xx ⇒ **P0/P1**
- Hreflang roto con indexación cruzada ⇒ **P0/P1**
- 5xx recurrentes ⇒ **P0**
- 404 con inlinks internos o señales GSC ⇒ **P1**
- Impresiones altas + CTR bajo ⇒ **P1**
- Posición media 11–20 con impresiones ⇒ **P1**

---

## 7) Categorías estándar (para filtrar)

- Rastreo
- Indexación
- Arquitectura / Estructura
- Internlinking
- Metadatos (Title/Meta)
- Headings (H1/H2)
- Contenido (thin, duplicado, intención, EEAT)
- Datos estructurados (Schema)
- Internacional / Idiomas (hreflang)
- Rendimiento / CWV
- Ecommerce (facetas, paginación, stock, variantes)
- KPIs / Medición
