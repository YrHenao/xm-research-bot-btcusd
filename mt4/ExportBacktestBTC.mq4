#property strict
#property script_show_inputs
#include "BTCResearchExport.mqh"
bool ExportFrame(int minutes,string &entry) {
   int count=iBars(Symbol(),minutes)-1;
   if(count<21) { Print("Falta historial M",minutes); return false; }
   MqlRates rows[]; ArraySetAsSeries(rows,false);
   if(CopyRates(Symbol(),minutes,1,count,rows)!=count) { Print("Cargando M",minutes,"; repita el script"); return false; }
   string name=ResearchFolder+"\\btcusd_m"+IntegerToString(minutes)+".csv";
   int f=FileOpen(name+".tmp",FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(f==INVALID_HANDLE) return false;
   FileWrite(f,"time","close");
   for(int i=0;i<count;i++) FileWrite(f,(long)rows[i].time,N(rows[i].close));
   FileFlush(f); FileClose(f);
   if(!Publish(name+".tmp",name)) return false;
   entry=J(IntegerToString(minutes))+":{\"count\":"+IntegerToString(count)+
      ",\"first\":"+IntegerToString((int)rows[0].time)+",\"last\":"+IntegerToString((int)rows[count-1].time)+"}";
   return true;
}
void OnStart() {
   if(!DemoBTC()) { Alert("Solo BTCUSD DEMO USD"); return; }
   if(!ExportResearch(0,"btcusd_m1")) return;
   int frames[3]={15,60,240}; string entries="";
   for(int i=0;i<3;i++) {
      string entry;
      if(!ExportFrame(frames[i],entry)) { Alert("Exportacion incompleta. Revise Expertos y repita."); return; }
      if(i>0) entries+=",";
      entries+=entry;
   }
   string name=ResearchFolder+"\\native_manifest.json";
   int f=FileOpen(name+".tmp",FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON,0,CP_UTF8);
   if(f==INVALID_HANDLE) return;
   string text="{\"schema\":1,\"source\":\"mt4_native_closed\",\"symbol\":"+J(Symbol())+
      ",\"server\":"+J(AccountServer())+",\"time_basis\":\"broker_server\",\"frames\":{"+entries+"}}";
   FileWriteString(f,text); FileFlush(f); FileClose(f);
   if(Publish(name+".tmp",name)) Alert("Listo: 6 archivos en Common\\Files\\BTCResearch: M1, M15, M60, M240 y dos JSON.");
}
