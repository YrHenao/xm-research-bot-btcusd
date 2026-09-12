#property strict

string ResearchFolder="BTCResearch";
string J(string s) { StringReplace(s,"\\","\\\\"); StringReplace(s,"\"","\\\""); return "\""+s+"\""; }
string N(double v) { return DoubleToString(v,12); }
bool DemoBTC() {
   return AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO
      && StringFind(Symbol(),"BTCUSD")>=0 && AccountCurrency()=="USD";
}
bool Publish(string temp,string finalName) {
   return FileMove(temp,FILE_COMMON,finalName,FILE_COMMON|FILE_REWRITE);
}
bool NativeFrames(string &result) {
   int frames[3]={15,60,240}; result="{";
   for(int k=0;k<3;k++) {
      MqlRates native[]; ArraySetAsSeries(native,false);
      int copied=CopyRates(Symbol(),frames[k],1,21,native);
      if(copied!=21) { Print("Cargando historial nativo ",frames[k],": ",copied,"/21"); return false; }
      if(k>0) result+=",";
      result+=J(IntegerToString(frames[k]))+":[";
      for(int j=0;j<copied;j++) {
         if(j>0) result+=",";
         result+="["+IntegerToString((int)native[j].time)+","+N(native[j].close)+"]";
      }
      result+="]";
   }
   result+="}"; return true;
}
bool ExportResearch(int maxBars,string stem) {
   if(!DemoBTC()) { Print("Solo BTCUSD en cuenta DEMO USD"); return false; }
   int available=iBars(Symbol(),PERIOD_M1)-1;
   int count=(maxBars>0 ? MathMin(available,maxBars) : available);
   if(count<60) { Print("Historial M1 insuficiente: ",count); return false; }
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int copied=CopyRates(Symbol(),PERIOD_M1,1,count,rates);
   if(copied!=count) { Print("Historial aun cargando: solicitado=",count," recibido=",copied,". Repita la exportacion."); return false; }
   double point=MarketInfo(Symbol(),MODE_POINT);
   double spread=MarketInfo(Symbol(),MODE_SPREAD)*point;
   double size=MarketInfo(Symbol(),MODE_LOTSIZE);
   double tickSize=SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_SIZE);
   double tickValue=SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_VALUE);
   double margin=MarketInfo(Symbol(),MODE_MARGINREQUIRED);
   if(point<=0 || spread<0 || size<=0 || tickSize<=0 || tickValue<=0 || margin<=0) {
      Print("Especificaciones incompletas; espere una cotizacion valida"); return false;
   }
   FolderCreate(ResearchFolder,FILE_COMMON);
   string base=ResearchFolder+"\\"+stem;
   string nativeFrames="";
   if(stem=="live" && !NativeFrames(nativeFrames)) return false;
   int f=FileOpen(base+".csv.tmp",FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(f==INVALID_HANDLE) return false;
   FileWrite(f,"time","open","high","low","close","spread");
   datetime first=0,last=0;
   for(int i=0;i<count;i++) {
      datetime t=rates[i].time;
      double o=rates[i].open, h=rates[i].high;
      double l=rates[i].low, c=rates[i].close;
      if(t<=0 || l<=0 || h<MathMax(o,c) || l>MathMin(o,c)) { FileClose(f); return false; }
      if(first==0) first=t;
      last=t;
      FileWrite(f,(long)t,N(o),N(h),N(l),N(c),N(spread));
   }
   FileFlush(f); FileClose(f);
   if(!Publish(base+".csv.tmp",base+".csv")) return false;
   string metadata="{\"schema\":1,\"mode\":\"demo\",\"symbol\":"+J(Symbol())+
      ",\"server\":"+J(AccountServer())+",\"account_login\":"+IntegerToString(AccountNumber())+",\"account_currency\":"+J(AccountCurrency())+
      ",\"bars\":"+IntegerToString(count)+",\"first_time\":"+IntegerToString((int)first)+
      ",\"last_time\":"+IntegerToString((int)last)+",\"server_time\":"+IntegerToString((int)TimeCurrent())+
      ",\"time_basis\":\"broker_server\",\"spread_source\":\"current_snapshot_assumption\""+
      ",\"spread\":"+N(spread)+",\"contract_size\":"+N(size)+
      ",\"quote_to_account\":"+N(tickValue/(tickSize*size))+
      ",\"volume_min\":"+N(MarketInfo(Symbol(),MODE_MINLOT))+
      ",\"volume_max\":"+N(MarketInfo(Symbol(),MODE_MAXLOT))+
      ",\"volume_step\":"+N(MarketInfo(Symbol(),MODE_LOTSTEP))+
      ",\"min_stop\":"+N(MarketInfo(Symbol(),MODE_STOPLEVEL)*point)+
      ",\"margin_per_lot\":"+N(margin)+",\"tick_size\":"+N(tickSize)+
      ",\"tick_value\":"+N(tickValue)+",\"swap_long\":"+N(MarketInfo(Symbol(),MODE_SWAPLONG))+
      ",\"swap_short\":"+N(MarketInfo(Symbol(),MODE_SWAPSHORT));
   if(stem=="live") metadata+=",\"filter_source\":\"mt4_native_closed\",\"native_frames\":"+nativeFrames;
   metadata+="}";
   f=FileOpen(base+".json.tmp",FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON,0,CP_UTF8);
   if(f==INVALID_HANDLE) return false;
   FileWriteString(f,metadata); FileFlush(f); FileClose(f);
   if(!Publish(base+".json.tmp",base+".json")) return false;
   Print("Exportadas ",count," velas cerradas en Common\\Files\\",base);
   return true;
}
