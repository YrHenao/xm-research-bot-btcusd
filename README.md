# BTCUSD — investigación y prueba demo en XM MT4

Actualizacion: historial de entrada ampliado de 7.000 a 20.000 velas M1,
actualizacion del snapshot cada 30 segundos y diagnosticos compactos de filtros.
Se conservan los requisitos de bloques completos y frescura; no se rellenan huecos.
Los resultados historicos previos corresponden a la ventana anterior de 7.000.

Adaptación del núcleo de `xm-research-bot` de oro para BTCUSD. Mantiene los seis
detectores Python, filtros M15/H1/H4, riesgo nominal 0,375 %, target 3:1, noticias
desactivadas y stop/timeout opcionales (ambos desactivados en el ejemplo).

**Version actual:** lotaje teorico 1,5x (antes de redondeo), target 3:1 y spread
maximo 40 USD. [Activacion demo paso a paso](ACTIVAR-DEMO.md).
Se exportaron 65.269 velas de XM. La configuracion anterior (0,25 %, 2:1) tuvo
nueve operaciones positivas; ese resultado no corresponde a esta configuracion.
Los archivos MQL4 necesitan compilarse y verificarse en MetaEditor. Todavia no
se ha confirmado una operacion MT4 ejecutada con este proyecto.

## 1. Exportar todo el historial disponible en MT4

1. Use la cuenta **demo USD** y el gráfico del símbolo BTCUSD exacto del bróker
   (se admite sufijo). Seleccione M1.
2. En Herramientas → Opciones → Gráficos aumente los límites de barras del
   historial y del gráfico; cargue el historial hacia atrás con Inicio/Home.
   La cantidad final depende de lo que el servidor y el terminal proporcionen.
   Si utiliza el Centro de historiales, documente el origen: una descarga externa
   puede no coincidir con los precios de su servidor XM.
3. Archivo → Abrir carpeta de datos → MQL4 → Scripts. Copie allí
   `mt4/ExportBTCUSD.mq4` y `mt4/BTCResearchExport.mqh`.
4. Abra `ExportBTCUSD.mq4` en MetaEditor y compile con F7. Requiere **0 errores**.
5. Ejecute el script sobre BTCUSD. `MaxBars=0` exporta todas las velas M1 cargadas,
   salvo la vela abierta. No existe un tope fijo de 20.000.
6. Los dos archivos quedan en la carpeta común de MetaTrader:
   `%APPDATA%\MetaQuotes\Terminal\Common\Files\BTCResearch\btcusd_m1.csv`
   y `btcusd_m1.json`. Copie ambos a la carpeta `data` del proyecto o compártalos
   con quien ejecute el análisis. Contienen información del servidor y cuenta;
   no se versionan en Git.

El exportador es solo lectura de mercado: no contiene OrderSend.

## 2. Instalar y probar

Requiere Python 3.11 o superior; el núcleo no tiene dependencias externas.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 3. Backtesting reproducible

Importe el contrato real antes de ejecutar. El ejemplo siguiente asume comisión
cero; sustitúyala por el coste ida/vuelta por lote de su cuenta. No se interpreta
un dato desconocido como coste cero automáticamente.

```powershell
.\.venv\Scripts\python.exe -m bot.mt4_import --data data/btcusd_m1.csv --metadata data/btcusd_m1.json --commission-roundtrip 0
.\.venv\Scripts\python.exe -m bot.compare --data data/btcusd_m1.csv
```

El segundo comando usa **todas las velas del CSV**, sin recortar a 20.000, y genera
en `reports` tres replays y `summary.json`:

| Variante | Stop loss | Timeout de 60 minutos |
|---|---|---|
| stop_timeout | activo | activo |
| no_stop | desactivado | activo |
| no_stop_no_timeout | desactivado | desactivado |

Incluye P&L, aciertos, profit factor, drawdown, mayor pérdida flotante al cierre
M1, margen supuesto, duración máxima y motivos de cierre. `end` liquida
contablemente al terminar los datos, no representa una orden en vivo.

Para la evaluación exploratoria 70/30 y cada detector:

```powershell
.\.venv\Scripts\python.exe -m bot evaluate --config config.mt4.json --data bitcoin=data/btcusd_m1.csv --out reports/evaluation.json
```

Los valores actuales para BTC son spread máximo 40 y
slippage 5, en unidades de precio. Son supuestos configurables, no condiciones
verificadas de XM. El contrato importado y margen corresponden al momento de
exportación. Las velas usan hora del servidor, **no se etiquetan como UTC**:
esto también fija los límites diarios y de los marcos superiores.

El spread histórico no queda verificado por esta exportación: se aplica a todas
las velas el spread observado al exportar, explícitamente etiquetado como
supuesto. No se modelan swaps, cambios históricos de margen, stop-out ni extremos
intravela de equity. Un backtest sin stop puede ocultar una liquidación que sí
ocurriría en una cuenta real. Los resultados se deben leer con esos límites.

## 4. Prueba demo MT4, después de revisar el backtest

MT4 usa un EA MQL4 como puente y los mismos detectores Python, no la API MT5.
No requiere DLL, WebRequest ni contraseñas en archivos.

1. Copie `mt4/BTCResearchDemo.mq4` y `mt4/BTCResearchExport.mqh` a
   MQL4/Experts y compile el EA con F7. No continúe si hay errores.
2. Adjunte el EA a BTCUSD M1 en cuenta demo USD. Empiece con
   `EnableDemoOrders=false`: exporta snapshots pero no envía órdenes.
3. Con el contrato importado en `config.mt4.json`, ejecute:

```powershell
.\.venv\Scripts\python.exe -m bot.mt4_bridge --folder "$env:APPDATA\MetaQuotes\Terminal\Common\Files\BTCResearch"
```

4. Solo tras verificar snapshots y señales, habilite AutoTrading en MT4 y
   `EnableDemoOrders=true` en el EA. Confirme sus entradas de riesgo, spread,
   slippage y comisión: **los parámetros de costes/riesgo del EA se configuran
   en MT4**, no se transfieren desde JSON. Deben coincidir con el backtest.

El EA acepta únicamente cuenta demo USD, BTCUSD, target 3:1 y señales recientes.
Comprueba identidad de cuenta, spread, margen y ausencia de posiciones u órdenes
antes de abrir. Conserva stop nominal para dimensionar los lotes y envía SL=0
cuando se desactiva. No implementa cierre por timeout ni modifica operaciones
manuales. Una respuesta de envío fallida/incierta bloquea nuevos envíos hasta
revisión manual del historial; nunca borre ese bloqueo sin reconciliarlo.

Ctrl+C en Python crea `BTCResearch/STOP`. Esto bloquea nuevas entradas; las
posiciones siguen abiertas con su target. Para reanudar, retire STOP únicamente
cuando lo decida y reinicie Python. Mantenga MT4 y Python abiertos. Use solo una
copia del puente y un solo EA; el archivo de bloqueo evita EA simultáneos.

## Referencias técnicas

- [Archivos MQL4 y carpeta común](https://docs.mql4.com/files/fileopen)
- [OrderSend en MT4](https://docs.mql4.com/trading/ordersend)
- [Tipo de cuenta](https://docs.mql4.com/account/accountinfointeger)
