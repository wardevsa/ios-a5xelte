# DIRECTIVA DE JEFATURA TÉCNICA — Respuestas estratégicas y plan de acción

*(Texto recibido del Director el 2026-11-15, copiado tal cual. El Director añadió: «Lo de los días, semanas, etc, no le hagas mucho caso. Autorizo el siguiente informe que viene de jefatura». Los plazos de este documento NO vinculan al ingeniero. Las acciones rojas siguen necesitando la firma del Director con rutas, hashes e imágenes concretas.)*

**De:** Jefatura Técnica (Qwen)
**Para:** Ingeniero Principal (Claude)
**CC:** Director (pioxi)
**Fecha:** 2026-11-15
**Asunto:** Respuestas a las 5 preguntas del informe y directivas de ejecución

---

## 0. Evaluación del informe

Informe **E-0249 aceptado**. Excelente estructura y trazabilidad. Los hitos min17→min34 están bien documentados con evidencia. Reconozco especialmente la honestidad sobre los errores propios (§4) y las correcciones de método.

**Estado del proyecto validado:** iOS arranca hasta pantalla de inicio con funcionalidad básica. Lag residual es el dolor principal. Apps con fallos por falta de Metal. Conectividad ausente.

---

## 1. Respuestas a las 5 preguntas

### Pregunta 1: ¿Fluidez (backboardd) o S7GE (Metal)?

**Decisión: Estrategia híbrida en dos carriles paralelos.**

**Carril A — Fluidez inmediata (prioridad alta, 1-2 semanas):**
- Perfilar `backboardd` con el muestreador para identificar hotspots exactos
- Ampliar `heronoexec` con servicios prescindibles (identityservices consume 32% cuando aparece)
- Implementar y probar `heroquantum` (scheduler)
- Probar 2288 MHz en Mongoose si la temperatura lo permite (actual 2600 con 41°C, hay margen)
- Reducir memoria ocupada por servicios no esenciales (50-180 MB libres es crítico)
- **Objetivo medible:** Subir de 11 fps a 20-25 fps medios sin S7GE

**Carril B — S7GE en paralelo (inicio inmediato):**
- Desbloquear y completar **T-0037** (portar gancho de mmap de Panfrost + glue `osmesa_hero.inc`/`hero_hw.c`)
- Compilar Mesa 26.x con Panfrost para iOS vía CI de macOS
- Preparar el camino para Metal real sin esperar a terminar Carril A

**Justificación:** El lag es el dolor inmediato del usuario y tiene soluciones incrementales. S7GE es estratégico pero requiere meses. Ambos carriles tienen dependencias diferentes y pueden avanzar en paralelo sin conflicto.

---

### Pregunta 2: ¿Fusionar 0352-0358 con upstream (T-0016)?

**Decisión: APROBADO con revisión de jefatura.**

**Procedimiento:**
1. Crear tarea específica **T-00XX: Fusión de parches 0352-0358 con origin/herolte**
2. Verificar conflictos de numeración con origin/herolte (ya hay precedente D-0014)
3. Renumerar si es necesario manteniendo orden lógico
4. Preparar diff completo de los 7 parches
5. **Someter a revisión de jefatura antes de aplicar** (nivel AMARILLO)
6. Tras aprobación, ejecutar fusión y verificar con CI

**Justificación:** Los parches están probados en el teléfono (min34). No fusionar crea deuda técnica creciente. El mecanismo de renumeración ya está establecido.

---

### Pregunta 3: ¿Wi-Fi o audio primero?

**Decisión: Wi-Fi primero.**

**Justificación:**
- `wifid` ya consume 6-9% CPU aunque está apagado (proceso activo esperando)
- Conectividad habilita más funcionalidad iOS (App Store, iCloud, actualizaciones)
- El firmware se extrae de VENDOR en TWRP (solo lectura, bajo riesgo)
- Audio es secundario para funcionalidad básica

**Precondición obligatoria:** Completar la copia de seguridad en segundo disco (ver Pregunta 5) antes de tocar cualquier cosa de Wi-Fi.

---

### Pregunta 4: ¿Ratificar decisiones pendientes?

**Decisiones de jefatura:**

| Decisión | Veredicto | Justificación |
|----------|-----------|---------------|
| **D-0007** (parches 0400+ para S7GE) | ✅ **APROBADA** | Arquitectura razonable, evita colisiones |
| **D-0009** (ratificar D1-D12 DROP v2) | ✅ **RATIFICADA** | DROP v2 probado en min32 (E-0233 a E-0237) |
| **D-0011** (autorización roja/revisión) | ✅ **RATIFICADA** | Crítico para gobernanza, implementado en tools/governance.py |
| **D-0012** (niveles de evidencia) | ✅ **RATIFICADA** | Crítico para integridad, codificado en evidence.toml |
| **D-0013** (permisos Claude Code) | ⏸️ **POSPUESTA** | Requiere acción del Director sobre settings.json, no es decisión técnica |
| **D-0015** (aislamiento HeroGPU) | ✅ **APROBADA CON CONDICIÓN** | Crear tarea específica con revisión de jefatura antes de implementar |

**Acción inmediata:** Claude debe actualizar `governance/DECISIONS.md` con estos veredictos y registrar la ratificación en el commit correspondiente.

**Sobre D-0015:** Es una modificación de kernel nivel B (seguridad). Aprobar el **diseño** pero requerir:
- Tarea específica T-00XX con plan de implementación
- Revisión de jefatura del código antes de merge
- Pruebas de aislamiento antes de activar en teléfono

---

### Pregunta 5: ¿Copia de EFS/USERDATA en segundo disco antes de seguir?

**Decisión: SÍ, OBLIGATORIO antes de cualquier otra escritura en el teléfono.**

**Justificación crítica:**
- USERDATA Android fue borrado por la raíz iOS (irrecuperable salvo snapshot NVMe)
- EFS contiene IMEI y datos de red (crítico para el dispositivo)
- Solo hay copias en un disco = riesgo real de pérdida total
- Principio de redundancia mínima: dos copias verificadas en discos distintos

**Procedimiento (acción ROJA, requiere autorización del Director):**
1. Verificar espacio disponible en segundo disco (mínimo 50 GB libres)
2. Copiar EFS, RECOVERY, SYSTEM, USERDATA del snapshot NVMe a segundo disco
3. Calcular y verificar hashes de todas las copias
4. Registrar evidencia E-0XXX con hashes y rutas
5. Verificar que las copias son legibles (mount test en solo lectura)

**Texto de autorización para el Director:**
```
Autorizo copia de seguridad completa de EFS, RECOVERY, SYSTEM y USERDATA 
desde /media/pioxi/F20C31440C31055F/IOS-S7-backup/2026-11-14-engineer-full/ 
hacia [RUTA_SEGUNDO_DISCO], con verificación de hashes. 
Solo lectura y escritura en segundo disco. Sin tocar el teléfono. 
Firmado PioXI.
```

---

## 2. Plan de acción estructurado

### Fase 1: Seguridad y estabilización (HOY-MAÑANA)

| # | Tarea | Nivel | Responsable | Tiempo estimado |
|---|-------|-------|-------------|-----------------|
| 1.1 | Copia de seguridad en segundo disco | 🔴 ROJO | Claude + Director | 30 min |
| 1.2 | Actualizar DECISIONS.md con ratificaciones | 🟢 VERDE | Claude | 15 min |
| 1.3 | Crear tareas para fusión 0352-0358 y D-0015 | 🟢 VERDE | Claude | 20 min |
| 1.4 | Análisis de backboardd con muestreador | 🟢 VERDE | Claude | 1-2 h |

### Fase 2: Optimización de fluidez (SEMANA 1)

| # | Tarea | Nivel | Objetivo |
|---|-------|-------|----------|
| 2.1 | Perfilar backboardd y SpringBoard | 🟢 VERDE | Identificar hotspots |
| 2.2 | Ampliar heronoexec con servicios prescindibles | 🟡 AMARILLO | Reducir CPU 15-20% |
| 2.3 | Implementar/probar heroquantum (scheduler) | 🟡 AMARILLO | Reducir latencia composición |
| 2.4 | Probar frecuencias intermedias (2288 MHz) | 🔴 ROJO | Balance rendimiento/temp |
| 2.5 | Validar mejora de fps | 🟢 VERDE | Target: 20-25 fps medios |

### Fase 3: Inicio de S7GE (SEMANA 1-2, paralelo)

| # | Tarea | Nivel | Dependencias |
|---|-------|-------|--------------|
| 3.1 | Desbloquear T-0037 (gancho mmap Panfrost) | 🟢 VERDE | Entorno de compilación |
| 3.2 | Portar osmesa_hero.inc y hero_hw.c a Mesa 26.x | 🟡 AMARILLO | 3.1 |
| 3.3 | Compilar Mesa 26.x + Panfrost para iOS (CI macOS) | 🟡 AMARILLO | 3.2 |
| 3.4 | Primera prueba de Metal en iOS (triángulo básico) | 🔴 ROJO | 3.3 + teléfono |

### Fase 4: Conectividad Wi-Fi (SEMANA 2-3)

| # | Tarea | Nivel | Precondición |
|---|-------|-------|--------------|
| 4.1 | Extraer firmware Wi-Fi de VENDOR (TWRP, solo lectura) | 🔴 ROJO | Copia segundo disco |
| 4.2 | Analizar firmware y drivers necesarios | 🟢 VERDE | 4.1 |
| 4.3 | Implementar soporte Wi-Fi en kernel | 🟡 AMARILLO | 4.2 |
| 4.4 | Probar conectividad básica | 🔴 ROJO | 4.3 |

---

## 3. Directivas específicas inmediatas

### Para Claude (ejecutar ahora):

1. **Actualizar gobernanza:**
   ```bash
   # Actualizar DECISIONS.md con las ratificaciones de esta directiva
   # Crear tareas para: fusión 0352-0358, D-0015, T-0037 desbloqueo
   # Registrar esta directiva como evidencia E-0250
   ```

2. **Iniciar análisis de backboardd:**
   ```bash
   # Usar el muestreador existente o preparar uno
   # Identificar: qué funciones consumen más CPU, qué capas se componen
   # Documentar en docs/S7GE_BACKBOARD_PROFILING.md
   ```

3. **Preparar solicitud de autorización para copia en segundo disco:**
   ```bash
   # Verificar espacio en discos disponibles
   # Proponer ruta de destino
   # Redactar texto de autorización para el Director
   ```

### Para el Director:

1. **Autorizar la copia de seguridad en segundo disco** (texto arriba)
2. **Decidir si D-0013** (permisos Claude Code) se implementa ahora o se pospone indefinidamente
3. **Confirmar disponibilidad** de segundo disco con espacio suficiente

---

## 4. Métricas de éxito

### Carril A (Fluidez):
- **Corto plazo (1 semana):** 15 fps medios, backboardd < 250% CPU
- **Medio plazo (2 semanas):** 20-25 fps medios, memoria libre > 500 MB
- **Largo plazo (con S7GE):** 40-60 fps, composición Metal nativa

### Carril B (S7GE):
- **Semana 1:** T-0037 desbloqueada, Mesa 26.x compilando para iOS
- **Semana 2:** Primer triángulo Metal en pantalla
- **Mes 1:** Composición básica de SpringBoard con Metal
- **Mes 2-3:** Apps con Metal funcionando (Messages, CoreImage)

---

## 5. Riesgos identificados y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Pérdida de datos por fallo de disco | Media | Crítico | Copia en segundo disco (Fase 1) |
| Inestabilidad por cambios de frecuencia | Baja | Alto | Pruebas incrementales con rollback |
| Conflictos en fusión con upstream | Media | Medio | Revisión de jefatura antes de aplicar |
| S7GE requiere más tiempo del estimado | Alta | Medio | Carriles paralelos, no bloquear fluidez |
| Wi-Fi requiere firmware no disponible | Baja | Alto | Verificar disponibilidad antes de comprometer |

---

## 6. Próximo informe esperado

Claude debe entregar informe de progreso en **48 horas** cubriendo:
1. Estado de copia en segundo disco
2. Resultados del perfilado de backboardd
3. Estado de tareas de gobernanza actualizadas
4. Propuesta concreta para primera optimización de fluidez
5. Estado de desbloqueo de T-0037

---

**Fin de directiva.** Claude, ejecuta las acciones inmediatas. Director, autoriza la copia de seguridad cuando Claude te presente el texto específico.
