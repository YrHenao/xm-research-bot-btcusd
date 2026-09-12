# Validación

Suite local: **31 tests Python aprobados** con Python 3.12.

Los tests Python verifican el motor común, las opciones stop/timeout, importación
del contrato, emparejamiento CSV/metadatos, cuenta demo, rechazo de datos antiguos,
señales y separación de pérdidas flotantes/realizadas. Los datos de los tests son
fixtures sintéticos y no representan mercado.

Pendiente de integración: compilación MQL4 en MetaEditor, exportación del máximo
historial M1 cargado en XM, importación de costes y ejecución del backtest real.
El puente demo no está validado mediante órdenes ejecutadas en MT4.

Antes de permitir envíos demo, verificar en MT4 rechazo de cuenta no demo,
duplicados, STOP, reinicio tras error, cotización antigua, spread alto y órdenes
existentes. La prueba de cuenta real debe hacerse con mocks/Strategy Tester;
no habilitar órdenes en una cuenta real para probar un bloqueo.
