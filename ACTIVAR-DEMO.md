# Activar BTCUSD demo: lotaje 1,5x y target 3:1

Esta version usa riesgo nominal 0,375 % frente al 0,25 % anterior; equivale
a multiplicar por 1,5 el volumen teorico antes de redondear al paso del broker.
No equivale a usar 1,5 lotes fijos. Target 3:1, spread maximo 40 USD,
stop y timeout desactivados. Esta NO es la configuracion del 100 % anterior.

1. Cierre el puente Python anterior si esta abierto. No se cierran posiciones.
2. En MT4: Archivo > Abrir carpeta de datos > MQL4 > Experts.
3. Copie alli `mt4/BTCResearchDemo.mq4` y `mt4/BTCResearchExport.mqh` de esta version.
4. Abra BTCResearchDemo.mq4 en MetaEditor y pulse F7. Requiere 0 errores.
5. En la cuenta DEMO USD, grafico BTCUSD M1, retire el EA anterior y adjunte
   BTCResearchDemo actualizado. En entradas pulse Restablecer/Reset para no
   conservar parametros antiguos. Compruebe RiskPerTrade=0.00375 y MaxSpread=40.
6. Active `EnableDemoOrders=true`, permita trading en las propiedades del EA
   y active AutoTrading. Sigue rechazando cuentas reales. No necesita DLL.
7. Si existe `STOP` en la carpeta comun BTCResearch, retirarlo permite reanudar
   nuevas entradas. No borre bloqueos de envios inciertos sin revisar el historial.
8. Ejecute `INICIAR-BTC-DEMO.cmd` desde esta carpeta. El lanzador usa
   `config.demo.json` (contrato exportado de XMGlobal-Demo 2), sin necesidad
   de rehacer la importacion. Cambiar de broker o contrato requiere reimportar.

Los snapshots aparecen en `%APPDATA%\MetaQuotes\Terminal\Common\Files\BTCResearch`.
Python emite señales; el EA comprueba de nuevo cuenta, precio, margen y permisos
antes de enviar. Los comandos version 1 (target 2:1) se rechazan y el riesgo de
Python debe coincidir con el del EA. Espera si hay cualquier orden/posicion abierta.

Ctrl+C detiene Python y crea STOP: no cierra posiciones existentes. Mantenga MT4
y Python abiertos. El TP queda en el servidor; no hay cierres por tiempo.

La compilacion e integracion del EA requieren comprobacion en su MetaEditor.
Hasta ver un ticket aceptado en MT4, no se debe afirmar que se ejecuto una orden.
Los costes conservan spread supuesto 40, comision cero y slippage 5; el replay
no incluye swaps ni liquidacion por margen.
