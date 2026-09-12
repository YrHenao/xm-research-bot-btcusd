#property strict
#include "BTCResearchExport.mqh"
input bool EnableDemoOrders=false;
input int HistoryBars=20000;
input double RiskPerTrade=0.00375; // 1.5 x presupuesto anterior 0.0025, redondeo a paso del broker
input double DailyLoss=0.02;
input double MaxSpread=40.0;
input double SlippagePrice=5.0;
input double CommissionRoundtrip=0.0; // Supuesto explicito USD/lote, confirmar con broker
int accountId,lockHandle=INVALID_HANDLE;
string serverId,uncertain;
datetime exported=0;
uint lastExport=0;

int OnInit() {
   if(!DemoBTC() || HistoryBars<7000 || RiskPerTrade<=0 || RiskPerTrade>0.005 || DailyLoss<=0 || DailyLoss>=1
      || MaxSpread<0 || SlippagePrice<0 || CommissionRoundtrip<0) return INIT_FAILED;
   accountId=AccountNumber(); serverId=AccountServer();
   FolderCreate(ResearchFolder,FILE_COMMON);
   lockHandle=FileOpen(ResearchFolder+"\\bridge.lock",FILE_WRITE|FILE_BIN|FILE_COMMON);
   if(lockHandle==INVALID_HANDLE) { Print("Otro puente activo"); return INIT_FAILED; }
   uncertain="BTCResearch_uncertain_"+IntegerToString(accountId);
   EventSetTimer(2);
   Print("Puente BTCUSD demo. Envio habilitado: ",EnableDemoOrders);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { EventKillTimer(); if(lockHandle!=INVALID_HANDLE) FileClose(lockHandle); }
bool SameDemo() { return DemoBTC() && AccountNumber()==accountId && AccountServer()==serverId; }
void OnTimer() {
   if(!SameDemo() || !IsConnected()) return;
   datetime closed=iTime(Symbol(),PERIOD_M1,1)+60;
   if(closed>60 && (closed!=exported || (uint)(GetTickCount()-lastExport)>=30000)) {
      if(ExportResearch(HistoryBars,"live")) { exported=closed; lastExport=GetTickCount(); }
   }
   if(!EnableDemoOrders || !IsTradeAllowed() || OrdersTotal()!=0 || GlobalVariableCheck(uncertain)) return;
   if(FileIsExist(ResearchFolder+"\\STOP",FILE_COMMON)) return;
   int f=FileOpen(ResearchFolder+"\\command.csv",FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(f==INVALID_HANDLE) return;
   int version=(int)FileReadNumber(f), login=(int)FileReadNumber(f);
   string server=FileReadString(f), symbol=FileReadString(f);
   datetime bar=(datetime)FileReadNumber(f);
   int side=(int)FileReadNumber(f);
   double distance=FileReadNumber(f), ratio=FileReadNumber(f);
   int stopEnabled=(int)FileReadNumber(f);
   double requestedRisk=FileReadNumber(f);
   FileClose(f);
   if(version!=3 || login!=accountId || server!=serverId || symbol!=Symbol() || bar!=closed
      || (side!=1 && side!=-1) || !MathIsValidNumber(distance) || distance<=0
      || !MathIsValidNumber(ratio) || ratio!=3.0 || (stopEnabled!=0 && stopEnabled!=1)
      || !MathIsValidNumber(requestedRisk) || MathAbs(requestedRisk-RiskPerTrade)>0.000000001) return;
   datetime now=TimeCurrent(),tickTime=(datetime)MarketInfo(Symbol(),MODE_TIME);
   if(now<bar || now-bar>90 || now<tickTime || now-tickTime>90) return;
   string key="BTCResearch_bar_"+IntegerToString(accountId)+"_"+IntegerToString((int)bar);
   if(GlobalVariableCheck(key)) return;
   RefreshRates();
   double bid=MarketInfo(Symbol(),MODE_BID),ask=MarketInfo(Symbol(),MODE_ASK);
   if(bid<=0 || ask<bid || ask-bid>MaxSpread) return;
   datetime midnight=StringToTime(TimeToString(now,TIME_DATE));
   double today=0;
   for(int i=0;i<OrdersHistoryTotal();i++) {
      if(!OrderSelect(i,SELECT_BY_POS,MODE_HISTORY)) return;
      if(OrderType()<=OP_SELL && OrderCloseTime()>=midnight) today+=OrderProfit()+OrderSwap()+OrderCommission();
   }
   double dayStart=AccountBalance()-today;
   if(dayStart<=0 || AccountEquity()<=dayStart*(1-DailyLoss)) return;
   double tick=SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_SIZE);
   double value=SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_VALUE);
   double point=MarketInfo(Symbol(),MODE_POINT),step=MarketInfo(Symbol(),MODE_LOTSTEP);
   if(tick<=0 || value<=0 || point<=0 || step<=0) return;
   double minimum=MarketInfo(Symbol(),MODE_STOPLEVEL)*point;
   distance=MathMax(distance,minimum);
   double entry=(side>0?ask:bid);
   double stop=MathRound((entry-side*distance)/tick)*tick;
   double target=MathRound((entry+side*distance*ratio)/tick)*tick;
   double loss=(MathAbs(entry-stop)+SlippagePrice)/tick*value+CommissionRoundtrip;
   if(loss<=0 || target<=0 || stop<=0) return;
   double lots=MathFloor(MathMin(AccountEquity()*RiskPerTrade/loss,MarketInfo(Symbol(),MODE_MAXLOT))/step)*step;
   lots=NormalizeDouble(lots,8);
   if(lots<MarketInfo(Symbol(),MODE_MINLOT)) return;
   int type=(side>0?OP_BUY:OP_SELL);
   ResetLastError();
   if(AccountFreeMarginCheck(Symbol(),type,lots)<=0 || GetLastError()==134) return;
   double reference=(side>0?bid:ask);
   if(side*(target-reference)<minimum || (stopEnabled==1 && side*(reference-stop)<minimum)) return;
   if(!SameDemo() || OrdersTotal()!=0 || !IsTradeAllowed() || FileIsExist(ResearchFolder+"\\STOP",FILE_COMMON)) return;
   // Persist BEFORE submission; never retry ambiguous responses automatically.
   if(GlobalVariableSet(key,1)==0 || GlobalVariableSet(uncertain,1)==0) return;
   GlobalVariablesFlush();
   int digits=(int)MarketInfo(Symbol(),MODE_DIGITS);
   int ticket=OrderSend(Symbol(),type,lots,NormalizeDouble(entry,digits),(int)MathFloor(SlippagePrice/point),
      stopEnabled==1?NormalizeDouble(stop,digits):0,NormalizeDouble(target,digits),"BTC research demo",260912,0,clrNONE);
   if(ticket<0) { Print("Envio incierto/rechazado. REVISAR MT4; bloqueo activo: ",GetLastError()); return; }
   GlobalVariableDel(uncertain); GlobalVariablesFlush();
   Print("Orden DEMO enviada ticket=",ticket," lotes=",lots," TP=",target," SL=",stopEnabled==1?stop:0);
}
