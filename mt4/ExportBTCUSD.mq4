#property strict
#property script_show_inputs
#include "BTCResearchExport.mqh"
input int MaxBars=0; // 0 = todas las velas M1 cargadas, sin tope de 20.000
void OnStart() {
   if(!ExportResearch(MaxBars,"btcusd_m1"))
      Alert("Exportacion incompleta. Revise Expertos; cargue mas historial M1 y repita.");
   else Alert("Exportacion lista: Terminal Common\\Files\\BTCResearch\\btcusd_m1.csv y .json");
}
