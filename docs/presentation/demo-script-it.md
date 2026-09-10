# Portfolio DSS — copione per presentazione e demo

Durata prevista: 15 minuti, più domande. Le slide 11 e 12 sono di supporto per il Q&A.

## Preparazione prima della presentazione

1. Seguire i comandi in [`docs/DEMO.md`](../DEMO.md) e avviare API offline e web app.
2. Verificare `http://127.0.0.1:8011/health` e la dicitura **API connected** nella pagina.
3. Aprire in due schede separate i report HTML di Week 11 e Week 9 come fallback.
4. Impostare lo zoom del browser al 100% e mantenere pronta la schermata iniziale del builder.
5. Chiudere notifiche e applicazioni non necessarie.

## Copione delle slide

### 0:00–0:35 — Slide 1, Portfolio DSS

«Portfolio DSS è un sistema di supporto alle decisioni per investitori non esperti. Il progetto aiuta
a leggere un portafoglio, confrontare alternative e capire quali ipotesi sostengono ogni risultato.
Non esegue operazioni e non promette rendimenti futuri.»

### 0:35–1:25 — Slide 2, Problema e confine di Phase B

«Il problema centrale è il compromesso tra rendimento atteso e rischio. Un singolo portafoglio
“ottimo” nasconde preferenze e incertezza, quindi il sistema mostra più alternative comparabili.
Phase B copre analisi, ottimizzazione, simulazione, spiegazioni e valutazione fuori campione. Restano
esclusi costi di transazione, fiscalità, esecuzione automatica e suitability regolamentare.»

### 1:25–2:15 — Slide 3, Due percorsi utente

«L’utente può inserire quantità già possedute oppure partire da capitale e preferenze. Entrambi i
percorsi portano allo stesso tipo di confronto: portafoglio corrente o pesi uguali, tre profili sulla
frontiera efficiente e benchmark SPY quando il confronto è significativo.»

Transizione: «Prima della demo, mostro come questi percorsi restano separati dalle fonti dati e dai
modelli numerici.»

### 2:15–3:15 — Slide 4, Architettura modulare

«Il frontend Next.js comunica con una singola API FastAPI. I servizi applicativi orchestrano casi
d’uso, mentre il dominio contiene contratti e calcoli finanziari. Wikipedia, Yahoo Finance, SQLite,
SciPy e NumPy sono adapter sostituibili. Per la demo sostituisco soltanto gli adapter dati con fixture
deterministiche; API, servizi e dominio restano invariati.»

### 3:15–4:25 — Slide 5, Metodo e convenzioni

«Tutti i confronti usano prezzi adjusted close, rendimenti semplici giornalieri e 252 periodi per
l’annualizzazione. Il rendimento atteso può provenire dalla media storica oppure da una media
esponenziale con half-life di 63 osservazioni. Il rischio usa la covarianza campionaria. L’ottimizzatore
risolve il problema media-varianza con vincoli long-only e somma dei pesi pari a uno.»

### 4:25–5:15 — Slide 6, Alternative e spiegazioni

«I tre profili si collocano al 20%, 50% e 80% dell’intervallo di rendimento raggiungibile. Non sono
percentuali di rischio né categorie universali. Le spiegazioni derivano da fatti tipizzati: variazioni
di rendimento e volatilità, concentrazione, contributi al rischio e vincoli attivi.»

### 5:15–6:15 — Slide 7, Incertezza e valutazione

«La simulazione Monte Carlo mostra distribuzioni, non previsioni certe. Il seed rende riproducibile
la componente casuale a parità di input. Il backtest walk-forward evita il look-ahead: a ogni data di
decisione usa solo informazioni precedenti e confronta i modelli sullo stesso periodo.»

### 6:15–7:25 — Slide 8, Risultati congelati

«Nel campione 2019–2025 il portafoglio a pesi uguali raggiunge il valore terminale più alto. Il
modello storico supera quello esponenziale nella finestra rolling, mentre accade il contrario nella
finestra expanding. SPY mostra la volatilità annualizzata più bassa. Il risultato importante è la
sensibilità al metodo e alla finestra, non la vittoria universale di una strategia.»

### 7:25–8:10 — Slide 9, Riproducibilità

«Il progetto include snapshot, configurazioni, report HTML e JSON con hash del contenuto. La baseline
finale supera 227 test backend e 42 test frontend, oltre a lint, type checking e build. La demo non
richiede rete o preparazione manuale dei dati.»

Transizione: «Ora percorro il flusso che vedrebbe un utente non esperto.»

## Demo live, cinque minuti

### 8:10–8:45 — Confine della demo

Mostrare la schermata iniziale e **API connected**.

«Questa sessione usa dati sintetici deterministici, dichiarati nell’interfaccia. I numeri storici
mostrati prima provengono invece dallo snapshot congelato.»

### 8:45–9:30 — Preferenze e capitale

Selezionare:

- **Balance growth and fluctuations**;
- **Somewhat comfortable**;
- **Reassess before changing exposure**.

Premere **Continue to capital**, inserire `10000`, lasciare **Historical mean** e avviare il calcolo.

«La regola è deterministica: la risposta meno aggressiva determina il profilo suggerito. Il capitale
scala i pesi in importi USD illustrativi, senza generare ordini o quote intere.»

### 9:30–10:45 — Alternative

Mostrare il profilo moderato, quindi selezionare conservative e aggressive.

«Cambiano insieme allocazione, rendimento atteso e volatilità stimata. Il passaggio tra profili non
scarica nuovi prezzi: confrontiamo punti della stessa frontiera e dello stesso campione.»

Aprire le ragioni della raccomandazione.

«Ogni frase rimanda a fatti numerici visibili. Il sistema evita spiegazioni opache o generate senza
traccia degli input.»

### 10:45–11:35 — Evidenza avanzata

Aprire i dettagli avanzati e indicare convenzioni, modelli, vincolo massimo, provenienza e report hash.

«Qui separiamo parametri stimati, ipotesi e diagnostica. Questa parte resta disponibile senza
bloccare il percorso semplice.»

### 11:35–12:40 — Simulazione

Aprire **Explore uncertainty**. Selezionare tre anni, 10.000 percorsi e seed `42`, quindi eseguire.

«La distribuzione confronta lo stesso capitale iniziale. La probabilità di perdita significa valore
finale inferiore al capitale nominale, non drawdown temporaneo. I parametri restano costanti e le
bande non includono l’incertezza di stima.»

### 12:40–13:10 — Chiusura della demo

«La demo mostra la funzione del DSS: rendere visibili alternative, ipotesi e incertezza prima che
l’utente prenda una decisione.»

## Chiusura

### 13:10–14:15 — Slide 10, Limiti e sviluppi futuri

«I limiti principali riguardano membership storica, costi e turnover, stabilità dei parametri e
operatività single-process. Il lavoro futuro segue questi limiti: dati point-in-time, vincoli più
realistici, modelli robusti e segnali multipli. Queste estensioni restano fuori da Phase B.»

### 14:15–15:00 — Conclusione e domande

«Portfolio DSS realizza il problema media-varianza richiesto e lo trasforma in un percorso
comprensibile, verificabile e riproducibile. Il contributo principale è il collegamento tra modello,
alternative, evidenza e spiegazione. Sono disponibile per le domande.»

## Fallback immediato

Se la UI non risponde entro 15 secondi:

1. Aprire `examples/case-studies/week11/report/report.html`.
2. Mostrare il caso guided profiles, la simulazione e le limitazioni.
3. Aprire `examples/backtest/week9/report/report.html` per il confronto walk-forward.
4. Dichiarare che i report sono statici, autonomi e generati dallo stesso dominio applicativo.

## Domande previste

### Perché usare SPY e non l’indice ufficiale?

SPY fornisce una serie adjusted-close accessibile e coerente con il trattamento total-return degli
altri strumenti. Il sistema lo etichetta sempre come proxy ETF, non come indice ufficiale.

### Il profilo moderato rappresenta una suitability finanziaria?

No. La mappatura traduce preferenze illustrative in una posizione relativa sulla frontiera. Non
considera reddito, patrimonio, obiettivi legali o altri requisiti di una valutazione regolamentare.

### Perché il forecast è una media esponenziale semplice?

Permette di verificare la sostituibilità del contratto, mantenere il modello spiegabile e costruire
un confronto fuori campione contro una baseline semplice. Non viene presentato come previsore certo.

### Come viene evitato il look-ahead nel backtest?

Ogni decisione usa una finestra che termina prima della data di esecuzione. Tutte le strategie
condividono le stesse sessioni di valutazione e il codice contiene test espliciti sul timing.

### Perché il portafoglio a pesi uguali ottiene il risultato migliore nel campione?

È un risultato del paniere, del periodo e delle ipotesi scelti. Conferma l’utilità di una baseline e
mostra che maggiore complessità non implica superiorità. Non giustifica una previsione futura.

### Cosa rende riproducibile la demo?

Gli adapter sintetici usano dati e seed deterministici. I report storici usano snapshot e
configurazioni versionate, includono hash del contenuto e non richiedono servizi esterni.

### Perché non sono inclusi costi di transazione e tasse?

Phase B valuta il nucleo del DSS. Costi e turnover cambierebbero l’ottimizzazione e le spiegazioni;
sono il primo sviluppo futuro proposto, non un dettaglio da aggiungere solo alla presentazione.
