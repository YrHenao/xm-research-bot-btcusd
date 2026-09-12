# Validación

Correccion nativa: **36 tests Python aprobados**. Comprueba filtros alcistas y
bajistas con huecos en M1, rechazo de velas futuras/abiertas, filtros antiguos
y snapshots de versiones previas. MetaEditor: **0 errores, 0 advertencias**.
Pendiente: verificar la exportacion nativa del EA adjunto en MT4 y repetir
backtesting con datos nativos historicos. Los resultados previos no son validacion
de esta fuente nueva. Las pruebas no enviaron ordenes.

Suite local: **34 tests Python aprobados** con Python 3.12, incluidos lotaje 1,5x,
target 3:1, diagnostico de historial y rechazo de velas antiguas.
EA actualizado compilado con MetaEditor XM MT4: **0 errores, 0 advertencias**.
Ventana ampliada a 20.000 M1: en el historico disponible hay 29 H4 completas,
frente a 8 con 7.000. La validacion de ejecucion demo sigue pendiente.

Los tests Python verifican el motor común, las opciones stop/timeout, importación
del contrato, emparejamiento CSV/metadatos, cuenta demo, rechazo de datos antiguos,
señales y separación de pérdidas flotantes/realizadas. Los datos de los tests son
fixtures sintéticos y no representan mercado.

Historial exportado e importado: 65.269 velas XM. Configuracion actual 1,5x y
target 3:1; los resultados anteriores de 2:1 no se atribuyen a esta version.
Pendiente de integración: compilación MQL4 en MetaEditor y validacion de ejecucion.
El puente demo no está validado mediante órdenes ejecutadas en MT4.

Antes de permitir envíos demo, verificar en MT4 rechazo de cuenta no demo,
duplicados, STOP, reinicio tras error, cotización antigua, spread alto y órdenes
existentes. La prueba de cuenta real debe hacerse con mocks/Strategy Tester;
no habilitar órdenes en una cuenta real para probar un bloqueo.
