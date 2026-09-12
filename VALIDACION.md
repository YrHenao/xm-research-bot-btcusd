# Validación

Suite local: **32 tests Python aprobados** con Python 3.12, incluido lotaje 1,5x y target 3:1.

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
