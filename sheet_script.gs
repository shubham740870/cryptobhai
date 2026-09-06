/**
 * ═══════════════════════════════════════════════════════════════
 *  CRYPTOBHAI ADVANCED TRADING JOURNAL — Google Apps Script
 *  Ye script tumhari sheet ko PRO trading journal bana deti hai:
 *  - Trade Log (auto P&L, R-multiple, result)
 *  - Dashboard (live colored stats)
 *  - Stats (coin-wise, long/short, monthly)
 *  - Risk Calculator
 *  - Bot endpoint (live prices har ghante)
 *
 *  SETUP:
 *  1. Ye pura code paste karo (Code.gs me)
 *  2. Save (Ctrl+S)
 *  3. buildAll() function ek baar run karo (authorize karna padega)
 *  4. Deploy → New deployment → Web app
 *     - Execute as: Me
 *     - Who has access: Anyone
 *  5. Jo URL mile wo bot ko de do
 * ═══════════════════════════════════════════════════════════════
 */

var COLORS = {
  bg: "#0d1117", panel: "#161b22", fg: "#e6edf3", gray: "#8b949e",
  green: "#26a641", red: "#f85149", blue: "#58a6ff", gold: "#e3b341",
  grid: "#30363d", greenBg: "#0f2e18", redBg: "#3a1214"
};

// ═══════════════ MAIN BUILD ═══════════════

function buildAll() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  buildTradeLog(ss);
  buildDashboard(ss);
  buildStats(ss);
  buildRiskCalc(ss);
  formatTradeLog(ss);
  tidyOldTabs(ss);
}

// ═══════════════ TRADE LOG ═══════════════

function buildTradeLog(ss) {
  var sh = ss.getSheetByName("Trade Log");
  if (!sh) {
    // Purana journal tab reuse karo (A1=Date, B1=Coin/Symbol ho to rename)
    var sheets = ss.getSheets();
    for (var i = 0; i < sheets.length; i++) {
      var s = sheets[i];
      var a1 = String(s.getRange(1, 1).getValue() || "").trim().toLowerCase();
      var b1 = String(s.getRange(1, 2).getValue() || "").trim().toLowerCase();
      if (a1 === "date" && (b1 === "coin" || b1 === "symbol")) {
        s.setName("Trade Log");
        sh = s;
        break;
      }
    }
  }
  if (!sh) sh = ss.insertSheet("Trade Log", 1);
  var today = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd");
  if (sh.getLastRow() < 2) {
    // headers + example row (delete kar sakte ho)
    sh.getRange(1, 1, 1, 15).setValues([[
      "Date", "Coin", "Side", "Entry", "SL", "Target", "Qty", "Lev",
      "Notes", "Exit Price", "P&L %", "P&L $", "R-Multiple", "Result", "Live Price"
    ]]);
    sh.getRange(2, 1, 1, 14).setValues([[
      today, "BTC", "LONG", 78000, 74000, 88000, 0.01, 1,
      "example — delete this row", "", "", "", "", ""
    ]]);
  } else if (String(sh.getRange(1, 15).getValue() || "").trim() === "") {
    sh.getRange(1, 15).setValue("Live Price");
  }
}

function formatTradeLog(ss) {
  var sh = ss.getSheetByName("Trade Log");
  if (!sh) return;
  sh.getRange(1, 1, 1, 15)
    .setBackground(COLORS.bg).setFontColor(COLORS.fg)
    .setFontSize(10).setFontWeight("bold");
  sh.getRange(1, 15).setFontColor(COLORS.gold);
  sh.setFrozenRows(1);
  var widths = [90, 70, 60, 90, 90, 90, 70, 55, 180, 90, 80, 90, 90, 110, 90];
  for (var i = 0; i < widths.length; i++) sh.setColumnWidth(i + 1, widths[i]);
  var last = Math.max(sh.getLastRow(), 2);
  var body = sh.getRange(2, 1, last - 1, 14);
  body.setFontColor(COLORS.fg).setBackground(COLORS.panel);
  applyLogFormulas(sh);
  sh.getRange(2, 11, last - 1, 1).setNumberFormat("0.00");       // K = P&L %
  sh.getRange(2, 12, last - 1, 1).setNumberFormat("$#,##0.00");  // L = P&L $
  sh.getRange(2, 13, last - 1, 1).setNumberFormat("0.00");       // M = R
  sh.getRange(2, 15, last - 1, 1).setNumberFormat("#,##0.####"); // O = Live Price
}

// Auto formulas: K=P&L%, L=P&L$, M=R, N=Result  (J = Exit/Live price)
function applyLogFormulas(sh) {
  var last = Math.max(sh.getLastRow(), 2);
  var n = last - 1;
  if (n < 1) return;
  // P&L% = Exit (J) se; Exit khali to Live Price (O) se; Lev = H col
  var dir = 'IF(C2:C="SHORT",-1,1)';
  var lev = 'IF(H2:H="",1,H2:H)';
  var fK = 'ARRAYFORMULA(IF((B2:B="")+(D2:D=""),"",'
         + 'IF(J2:J<>"", ((J2:J-D2:D)/D2:D)*100*' + dir + '*' + lev + ','
         + 'IF(O2:O<>"", ((O2:O-D2:D)/D2:D)*100*' + dir + '*' + lev + ', ""))))';
  var fL = 'ARRAYFORMULA(IF((B2:B="")+(D2:D=""),"",'
         + 'IF(K2:K="", "", K2:K/100*D2:D*G2:G)))';
  var fM = 'ARRAYFORMULA(IF((B2:B="")+(D2:D="")+(E2:E=""),"",'
         + '((IF(J2:J<>"",J2:J,IF(O2:O<>"",O2:O,D2:D))-D2:D)*' + dir + ')'
         + '/ABS(D2:D-E2:E)))';
  var fN = 'ARRAYFORMULA(IF(B2:B="","",'
         + 'IF(J2:J<>"", IF(K2:K>=0,"✅ WIN","❌ LOSS"),'
         + 'IF((F2:F<>"")*(O2:O<>"")*IF(C2:C="SHORT",O2:O<=F2:F,O2:O>=F2:F),"🎯 TP HIT",'
         + 'IF((E2:E<>"")*(O2:O<>"")*IF(C2:C="SHORT",O2:O>=E2:E,O2:O<=E2:E),"🛑 SL HIT",'
         + '"⏳ OPEN")))))';
  sh.getRange(2, 11).setFormula(fK);   // K = P&L %
  sh.getRange(2, 12).setFormula(fL);   // L = P&L $
  sh.getRange(2, 13).setFormula(fM);   // M = R-multiple
  sh.getRange(2, 14).setFormula(fN);   // N = Result
}

// ═══════════════ DASHBOARD ═══════════════

function buildDashboard(ss) {
  var f = ss.getSheetByName("Dashboard") || ss.insertSheet("Dashboard", 0);
  f.clear();
  ss.setActiveSheet(f);

  f.getRange(1, 1, 1, 6).merge()
    .setValue("🤖 CRYPTOBHAI — TRADING JOURNAL")
    .setFontSize(20).setFontWeight("bold")
    .setBackground(COLORS.bg).setFontColor(COLORS.fg)
    .setHorizontalAlignment("center");
  f.getRange(2, 1, 1, 6).merge()
    .setValue("Live stats · bot har ghante update karta hai · Trade Log me trades bharo")
    .setFontSize(9).setFontColor(COLORS.gray)
    .setBackground(COLORS.bg).setHorizontalAlignment("center");

  var rows = [
    ["💰 TOTAL P&L", '=IF(COUNT(\'Trade Log\'!L2:L1000)=0,"—",SUM(\'Trade Log\'!L2:L1000))', "USD"],
    ["📊 CLOSED TRADES", '=COUNTIF(\'Trade Log\'!N2:N1000,"✅*")+COUNTIF(\'Trade Log\'!N2:N1000,"❌*")', ""],
    ["✅ WINS", '=COUNTIF(\'Trade Log\'!N2:N1000,"✅*")', ""],
    ["❌ LOSSES", '=COUNTIF(\'Trade Log\'!N2:N1000,"❌*")', ""],
    ["🔄 OPEN", '=COUNTA(\'Trade Log\'!B2:B1000)-C5-C6', ""],
    ["🎯 WIN RATE", '=IF(C6+C7=0,"—",TEXT(C6/(C6+C7)*100,"0.0")&"%")', ""],
    ["⚡ PROFIT FACTOR", '=IF(SUMIF(\'Trade Log\'!L2:L1000,"<0")=0,"∞",'
      + 'TEXT(SUMIF(\'Trade Log\'!L2:L1000,">0")/ABS(SUMIF(\'Trade Log\'!L2:L1000,"<0")),"0.00"))', ""],
    ["🏆 BEST TRADE", '=IF(COUNT(\'Trade Log\'!L2:L1000)=0,"—",MAX(\'Trade Log\'!L2:L1000,0))', "USD"],
    ["💀 WORST TRADE", '=IF(COUNT(\'Trade Log\'!L2:L1000)=0,"—",MIN(\'Trade Log\'!L2:L1000,0))', "USD"],
    ["📈 AVG WIN", '=IFERROR(AVERAGEIF(\'Trade Log\'!L2:L1000,">0"),"—")', "USD"],
    ["📉 AVG LOSS", '=IFERROR(AVERAGEIF(\'Trade Log\'!L2:L1000,"<0"),"—")', "USD"],
    ["🧮 TOTAL R", '=IFERROR(TEXT(SUM(\'Trade Log\'!M2:M1000),"0.00")&"R","—")', ""]
  ];
  f.getRange(4, 1, rows.length, 3).setValues(rows);

  f.setColumnWidth(1, 200); f.setColumnWidth(2, 150); f.setColumnWidth(3, 60);
  var block = f.getRange(4, 1, rows.length, 3);
  block.setBackground(COLORS.panel).setFontColor(COLORS.fg).setFontSize(11);
  f.getRange(4, 1, rows.length, 1).setFontWeight("bold").setFontColor(COLORS.gray);
  f.getRange(4, 2, rows.length, 1).setFontWeight("bold").setFontSize(13);

  // conditional colors
  f.getRange("B4").setNumberFormat("$#,##0.00");
  f.getRange("B9").setNumberFormat("$#,##0.00");
  f.getRange("B10").setNumberFormat("$#,##0.00");
  f.getRange("B11").setNumberFormat("$#,##0.00");
  f.getRange("B12").setNumberFormat("$#,##0.00");

  f.getRange(4, 1, 1, 2).setBackground(COLORS.greenBg);
  f.getRange(5, 1, 1, 2).setBackground(COLORS.panel);
  f.getRange(7, 1, 1, 2).setBackground(COLORS.greenBg);
  f.getRange(8, 1, 1, 2).setBackground(COLORS.redBg);

  f.getRange(18, 1).setValue("📊 COIN PERFORMANCE (auto)")
    .setFontWeight("bold").setFontColor(COLORS.gold);
  var coinRows = [
    ["Coin", "Trades", "Wins", "Win%", "P&L $"],
    ['=IFERROR(UNIQUE(FILTER(\'Trade Log\'!B2:B1000,\'Trade Log\'!B2:B1000<>"")),"")',
     "", "", "", ""]
  ];
  f.getRange(19, 1, 2, 5).setValues(coinRows);
  f.getRange(20, 1, 20, 5).setFormulas(buildCoinFormulas());
  f.getRange(19, 1, 1, 5).setBackground(COLORS.grid).setFontColor(COLORS.fg);

  f.getRange(41, 1).setValue("📅 MONTHLY P&L (auto)")
    .setFontWeight("bold").setFontColor(COLORS.gold);
  f.getRange(42, 1, 1, 4).setValues([["Month", "Trades", "Wins", "P&L $"]])
    .setBackground(COLORS.grid).setFontColor(COLORS.fg);
  f.getRange(43, 1, 12, 4).setFormulas(buildMonthFormulas());
}

function buildCoinFormulas() {
  var out = [];
  for (var i = 0; i < 20; i++) {
    var r = 20 + i;
    out.push([
      '=IF(A' + r + '="","",A' + r + ')',
      '=IF(A' + r + '="","",COUNTIF(\'Trade Log\'!B:B,A' + r + '))',
      '=IF(A' + r + '="","",COUNTIFS(\'Trade Log\'!B:B,A' + r + ',\'Trade Log\'!N:N,"✅*"))',
      '=IF(A' + r + '="","",TEXT(IFERROR(C' + r + '/B' + r + '*100,0),"0")&"%")',
      '=IF(A' + r + '="","",SUMIF(\'Trade Log\'!B:B,A' + r + ',\'Trade Log\'!L:L))'
    ]);
  }
  return out;
}

function buildMonthFormulas() {
  var out = [];
  var TL = "'Trade Log'!";
  for (var i = 0; i < 12; i++) {
    var r = 43 + i;
    var m = 'ROW()-42';
    var mo = '(IFERROR(MONTH(DATEVALUE(' + TL + 'A2:A1000&"")),0)=' + m + ')';
    var guard = '(' + TL + 'A2:A1000<>"")';
    out.push([
      '=IF(' + m + '>MONTH(TODAY()),"",TEXT(DATE(YEAR(TODAY()),' + m + ',1),"MMM YYYY"))',
      '=IF(A' + r + '="","",SUMPRODUCT(' + guard + '*' + mo + '))',
      '=IF(A' + r + '="","",SUMPRODUCT(' + guard + '*' + mo
        + '*ISNUMBER(SEARCH("✅",' + TL + 'N2:N1000))))',
      '=IF(A' + r + '="","",SUMPRODUCT(' + guard + '*' + mo
        + '*IFERROR(' + TL + 'L2:L1000,0)))'
    ]);
  }
  return out;
}

// ═══════════════ STATS ═══════════════

function buildStats(ss) {
  var f = ss.getSheetByName("Stats") || ss.insertSheet("Stats", 2);
  f.clear();

  f.getRange(1, 1, 1, 4).merge()
    .setValue("📈 DEEP STATISTICS")
    .setFontSize(16).setFontWeight("bold")
    .setBackground(COLORS.bg).setFontColor(COLORS.fg)
    .setHorizontalAlignment("center");

  var sections = [
    ["LONG vs SHORT", 3, [
      ["Side", "Trades", "Wins", "Win%", "P&L $"],
      ["LONG", '=COUNTIF(\'Trade Log\'!C:C,"LONG")',
       '=COUNTIFS(\'Trade Log\'!C:C,"LONG",\'Trade Log\'!N:N,"✅*")',
       '=IFERROR(TEXT(C5/B5*100,"0")&"%","—")',
       '=SUMIF(\'Trade Log\'!C:C,"LONG",\'Trade Log\'!L:L)'],
      ["SHORT", '=COUNTIF(\'Trade Log\'!C:C,"SHORT")',
       '=COUNTIFS(\'Trade Log\'!C:C,"SHORT",\'Trade Log\'!N:N,"✅*")',
       '=IFERROR(TEXT(C6/B6*100,"0")&"%","—")',
       '=SUMIF(\'Trade Log\'!C:C,"SHORT",\'Trade Log\'!L:L)']
    ]],
    ["LEVERAGE PERFORMANCE", 9, [
      ["Lev", "Trades", "P&L $"],
      ["1x", '=COUNTIF(\'Trade Log\'!H:H,1)', '=SUMIF(\'Trade Log\'!H:H,1,\'Trade Log\'!L:L)'],
      ["2x", '=COUNTIF(\'Trade Log\'!H:H,2)', '=SUMIF(\'Trade Log\'!H:H,2,\'Trade Log\'!L:L)'],
      ["3x", '=COUNTIF(\'Trade Log\'!H:H,3)', '=SUMIF(\'Trade Log\'!H:H,3,\'Trade Log\'!L:L)'],
      ["5x", '=COUNTIF(\'Trade Log\'!H:H,5)', '=SUMIF(\'Trade Log\'!H:H,5,\'Trade Log\'!L:L)'],
      ["10x", '=COUNTIF(\'Trade Log\'!H:H,10)', '=SUMIF(\'Trade Log\'!H:H,10,\'Trade Log\'!L:L)']
    ]],
    ["DURATION INSIGHTS", 17, [
      ["Metric", "Value"],
      ["Avg R (wins)", '=IFERROR(TEXT(AVERAGEIFS(\'Trade Log\'!M2:M1000,\'Trade Log\'!L2:L1000,">0"),"0.00")&"R","—")'],
      ["Avg R (losses)", '=IFERROR(TEXT(AVERAGEIFS(\'Trade Log\'!M2:M1000,\'Trade Log\'!L2:L1000,"<0"),"0.00")&"R","—")'],
      ["Expectancy (per trade)", '=IFERROR(TEXT(AVERAGE(\'Trade Log\'!L2:L1000),"$0.00"),"—")'],
      ["Max Drawdown streak", "— (manual)"]
    ]]
  ];

  var row = 3;
  sections.forEach(function(sec) {
    f.getRange(row, 1).setValue("【 " + sec[0] + " 】")
      .setFontWeight("bold").setFontColor(COLORS.blue).setFontSize(12);
    row++;
    var data = sec[2];
    f.getRange(row, 1, data.length, data[0].length).setValues(data);
    f.getRange(row, 1, 1, data[0].length)
      .setBackground(COLORS.grid).setFontColor(COLORS.fg).setFontWeight("bold");
    f.getRange(row + 1, 1, data.length - 1, data[0].length)
      .setBackground(COLORS.panel).setFontColor(COLORS.fg);
    row += data.length + 2;
  });

  for (var c = 1; c <= 5; c++) f.setColumnWidth(c, 130);
}

// ═══════════════ RISK CALCULATOR ═══════════════

function buildRiskCalc(ss) {
  var f = ss.getSheetByName("Risk Calc") || ss.insertSheet("Risk Calc", 3);
  f.clear();

  f.getRange(1, 1, 1, 2).merge()
    .setValue("🧮 POSITION SIZE CALCULATOR")
    .setFontSize(16).setFontWeight("bold")
    .setBackground(COLORS.bg).setFontColor(COLORS.fg)
    .setHorizontalAlignment("center");

  var inputs = [
    ["💵 Capital (USD)", 1000, "← apna capital daalo"],
    ["⚠️ Risk per trade (%)", 2, "← 1-2% safe hai"],
    ["📍 Entry Price", 78000, ""],
    ["🛑 Stop-Loss", 74000, ""],
    ["🎯 Target", 88000, ""],
    ["⚡ Leverage", 1, "← 1 = spot"]
  ];
  f.getRange(3, 1, inputs.length, 3).setValues(inputs);
  f.getRange(3, 1, inputs.length, 1).setFontWeight("bold").setFontColor(COLORS.gray);
  f.getRange(3, 2, inputs.length, 1).setBackground("#1c2128").setFontColor(COLORS.gold)
    .setFontSize(12).setNumberFormat("#,##0.##");
  f.getRange(3, 3, inputs.length, 1).setFontColor(COLORS.gray).setFontSize(9);

  var outs = [
    ["💰 Risk Amount", "=B4*B5/100", "USD — itna max gawao ge"],
    ["📦 Position Size (qty)", "=ABS(B6-B7)>0?B8/ABS(B6-B7):0", "coins"],
    ["💵 Position Value", "=B10*B6", "USD"],
    ["⚡ Margin Needed", "=IF(B9>1,B11/B9,B11)", "USD"],
    ["🎯 Profit at Target", "=ABS(B8-B10*B6)", "USD"],
    ["⚖️ Risk:Reward", "=IF(B12>0,TEXT(B14/B8,\"0.0\")&\" : 1\",\"—\")", ""],
    ["📉 Loss at SL", "=-B8", "USD"]
  ];
  f.getRange(11, 1, outs.length, 3).setValues(outs);
  f.getRange(11, 1, outs.length, 1).setFontWeight("bold").setFontColor(COLORS.fg);
  f.getRange(11, 2, outs.length, 1).setBackground(COLORS.panel)
    .setFontColor(COLORS.green).setFontSize(13).setFontWeight("bold");
  f.getRange(11, 3, outs.length, 1).setFontColor(COLORS.gray).setFontSize(9);

  f.setColumnWidth(1, 200); f.setColumnWidth(2, 140); f.setColumnWidth(3, 220);
  f.getRange(11, 1, 1, 3).setBackground(COLORS.greenBg);
}

// Purane orphan tabs clean karo (khali ya sirf-header wale — data kabhi nahi)
function tidyOldTabs(ss) {
  var keep = { "Dashboard": 1, "Trade Log": 1, "Stats": 1, "Risk Calc": 1 };
  var sheets = ss.getSheets();
  for (var i = sheets.length - 1; i >= 0; i--) {
    var s = sheets[i];
    if (keep[s.getName()]) continue;
    var a1 = String(s.getRange(1, 1).getValue() || "").trim().toLowerCase();
    if (s.getLastRow() <= 1 && (a1 === "" || a1 === "date")) {
      ss.deleteSheet(s);
    }
  }
}

// ═══════════════ BOT ENDPOINT (live price updates) ═══════════════

/**
 * Bot isko call karega:  /exec?action=update&prices=BTC:79690,ETH:2480,SOL:105.9
 * Trade Log ke O column (Live Price) me price daal dega jisse
 * P&L formulas live calc karein (exit bhara ho to override nahi karega).
 */
function updateLivePrices(pricesStr) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName("Trade Log");
  if (!sh || !pricesStr) return "no data";
  var pairs = String(pricesStr).split(",");
  var map = {};
  pairs.forEach(function(p) {
    var kv = p.split(":");
    if (kv.length === 2) map[kv[0].trim().toUpperCase()] = parseFloat(kv[1]);
  });
  var last = Math.max(sh.getLastRow(), 2);
  var syms = sh.getRange(2, 2, last - 1, 1).getValues();
  var exits = sh.getRange(2, 10, last - 1, 1).getValues();
  var updated = 0;
  for (var i = 0; i < syms.length; i++) {
    var sym = String(syms[i][0]).toUpperCase();
    if (map[sym] && !exits[i][0]) {
      sh.getRange(i + 2, 15).setValue(map[sym]);   // O col = Live Price
      updated++;
    }
  }
  return "updated:" + updated;
}

function handle(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var action = e.parameter.action || "ping";
    if (action === "update") {
      var msg = updateLivePrices(e.parameter.prices);
      return ContentService.createTextOutput("OK: " + msg);
    }
    if (action === "build") {
      buildAll();
      return ContentService.createTextOutput("OK: built");
    }
    return ContentService.createTextOutput("OK: ping");
  } catch (err) {
    return ContentService.createTextOutput("ERROR: " + err);
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) { return handle(e); }
function doPost(e) { return handle(e); }
