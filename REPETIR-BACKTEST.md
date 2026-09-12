# Repetir con filtros nativos MT4

La prueba nueva requiere seis archivos: btcusd_m1.csv, btcusd_m1.json,
btcusd_m15.csv, btcusd_m60.csv, btcusd_m240.csv y native_manifest.json.
No utilice live.json: solo contiene 21 velas por filtro y no todo el historial.

1. Copie mt4/ExportBacktestBTC.ex4 a MQL4/Scripts de su terminal MT4.
   El binario local esta compilado; desde GitHub compile ExportBacktestBTC.mq4
   junto a BTCResearchExport.mqh con MetaEditor.
2. Abra BTCUSD en M1, M15, H1 y H4 para cargar el historial del broker.
   Use los limites de barras ampliados y cargue hacia atras con Inicio/Home.
3. Navegador > Scripts > Actualizar; arrastre ExportBacktestBTC al grafico BTCUSD.
   Es solo exportacion; no necesita permiso de trading ni envia ordenes.
4. Espere el mensaje Listo. Si indica Cargando, espere la descarga y repita.
5. Copie los seis archivos de la carpeta comun BTCResearch a data/ del proyecto.
6. Desde el proyecto:

```powershell
.\.venv\Scripts\python.exe -m bot.native_replay --folder data --config config.demo.json --out reports/native-replay.json
```

Mantiene el lotaje nominal actual 0,375 %, target 3:1, spread maximo 40,
stop/timeout desactivados. Usa todo el CSV M1 y selecciona las ultimas 21 velas
nativas cerradas en cada instante; nunca usa velas aun abiertas o futuras.
Bloquea puntos con historial nativo insuficiente o atrasado y reporta los conteos.
Los precios historicos nativos deben provenir del mismo servidor y simbolo.

Costes: spread constante del nuevo snapshot, comision configurada, margen
actual fijo; no incluye swaps ni stop-out. Si el spread exportado supera 40,
el filtro de spread puede impedir entradas. Esto debe informarse, no ocultarse.

Validacion: 39 tests Python aprobados; exportador compilado con 0 errores y
0 advertencias. Pendiente recibir la nueva exportacion para resultados de mercado.
