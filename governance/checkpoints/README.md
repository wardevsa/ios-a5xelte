# Checkpoints

Un checkpoint es una **nota de reanudación**: lo que haría falta para continuar el trabajo sin la conversación que lo produjo. Se **añaden**, nunca se editan ni se borran (Constitución I-7, I-17).

Nombre: `AAAA-MM-DD-T-NNNN-NN.md` (fecha, tarea, secuencia). Contenido mínimo:
```
# Checkpoint AAAA-MM-DD T-NNNN #NN
- Hora y modelo/sesión:
- Objetivo de la tarea (una línea) y criterio de aceptación:
- Hecho hasta ahora (con comandos y commits):
- Evidencias nuevas (ids de evidence.toml o rutas con SHA-256):
- Pendiente, en orden, y el siguiente paso exacto:
- Procesos en marcha (PID, comando, fichero de log) y cómo comprobarlos:
- Riesgos y decisiones abiertas:
- Cómo verificar el estado: comandos que dan "listo" o "roto":
```
Cuándo escribir uno: al empezar una tarea, antes de cualquier trabajo largo o en segundo plano, al cambiar de plan, al terminar y **siempre antes de que la sesión pueda cortarse** (disco, tiempo, contexto).
Al reanudar: leer el último checkpoint de la tarea, ejecutar sus comandos de verificación y comprobar que el estado real coincide con lo que dice; si no, **gana el estado real** y se anota la discrepancia.
