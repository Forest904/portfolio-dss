# Portfolio DSS — copione della presentazione e della demo

Durata prevista:

- presentazione: circa 15 minuti;
- demo guidata: circa 7 minuti e 40 secondi;
- slide A1–A5: supporto matematico per le domande.

## Preparazione

1. Avviare l’API offline e l’applicazione seguendo [`docs/DEMO.md`](../DEMO.md).
2. Verificare `http://127.0.0.1:8011/health` e la dicitura **API connected**.
3. Aprire la pagina iniziale del builder in una scheda dedicata.
4. Aprire come fallback:
   - `examples/case-studies/week11/report/report.html`;
   - `examples/backtest/week9/report/report.html`.
5. Impostare lo zoom del browser al 100% e chiudere notifiche e applicazioni non necessarie.
6. Non eseguire una seconda ottimizzazione durante la demo. Il confronto tra stimatori sugli stessi pesi è già incluso nel risultato.

## Presentazione — 15 minuti

### 0:00–0:25 — Slide 1, Teoria di portafoglio e supporto decisionale

«Portfolio DSS nasce da un problema finanziario classico: allocare un capitale tra più attività quando rendimento e rischio sono incerti. Il progetto trasforma il modello media-varianza in un processo di supporto alla decisione. Non esegue investimenti e non promette risultati futuri.»

### 0:25–1:15 — Slide 2, La decisione reale dell’investitore

«L’investitore dispone di capitale limitato e deve scegliere oggi sulla base di informazioni imperfette. Ogni peso assegnato a un titolo riduce il capitale disponibile per gli altri. I rendimenti futuri non sono noti e il rischio dipende anche dalle relazioni tra le attività. Inoltre, persone diverse accettano compromessi diversi. Per questo la domanda non è quale portafoglio sia migliore in assoluto, ma quale alternativa sia coerente con la decisione considerata.»

### 1:15–2:10 — Slide 3, Il ruolo di un Decision Support System

«Un Decision Support System parte da dati osservati, applica un modello analitico e produce alternative confrontabili. Deve poi rendere l’evidenza comprensibile e lasciare la scelta finale alla persona. Portfolio DSS segue esattamente questo ciclo: prezzi e periodo costituiscono i dati, il modello quantifica rendimento e rischio, la frontiera genera alternative e le spiegazioni rendono visibili ipotesi e conseguenze. Il risultato supporta il giudizio umano, senza sostituirlo.»

Transizione: «Per capire il modello centrale servono prima alcuni concetti finanziari.»

### 2:10–2:55 — Slide 4, Capitale, attività e pesi

«Il vettore x contiene i pesi del portafoglio. Ogni x con indice i rappresenta la quota di capitale assegnata all’attività i. Moltiplicando il peso per il capitale otteniamo un importo illustrativo. La somma dei pesi vale uno perché il portafoglio è interamente investito. Nella versione realizzata i pesi sono non negativi: il portafoglio è long-only e non usa vendite allo scoperto.»

### 2:55–3:50 — Slide 5, Dai prezzi ai rendimenti

«Il calcolo parte dai prezzi adjusted close. Il rendimento semplice giornaliero è il rapporto tra il prezzo corrente e quello precedente, meno uno. Prima di confrontare titoli e benchmark, il sistema usa le stesse date e non inventa osservazioni mancanti. Le stime giornaliere vengono annualizzate con 252 periodi. Queste convenzioni non sono dettagli: se cambiano periodo, frequenza o trattamento dei dati, cambia anche il significato del confronto.»

### 3:50–4:50 — Slide 6, Rendimento atteso e rischio stimato

«Il rendimento atteso di ogni attività è inizialmente stimato con la media aritmetica dei rendimenti giornalieri, moltiplicata per 252. Il rischio usa la covarianza campionaria annualizzata sugli stessi rendimenti allineati. La diagonale descrive la variabilità delle singole attività; gli altri elementi descrivono come si muovono insieme. È importante distinguere questa media stimata dal CAGR, che descrive un percorso storico composto. Nessuna delle due grandezze garantisce il futuro.»

### 4:50–5:40 — Slide 7, Diversificazione e rischio di portafoglio

«Il rendimento atteso del portafoglio è la media ponderata x trasposto per mu. La varianza è x trasposto Sigma x e la volatilità è la sua radice quadrata. Nella varianza compaiono sia i rischi individuali sia tutte le covarianze. Per questo non basta scegliere titoli con bassa volatilità separatamente: conta la combinazione. La diversificazione è una proprietà del portafoglio nel suo insieme.»

### 5:40–6:55 — Slide 8, Il problema media-varianza

«Questa è la formulazione centrale indicata dalla professoressa. Il modello massimizza il rendimento atteso del portafoglio e sottrae una penalizzazione proporzionale alla varianza. Mu contiene i rendimenti attesi, Sigma la matrice di covarianza, x i pesi e lambda l’avversione al rischio. Se lambda aumenta, il modello penalizza maggiormente la varianza. Se diminuisce, attribuisce più importanza al rendimento atteso. Il termine “ottimo” ha quindi senso soltanto dopo avere dichiarato preferenza, dati, stime e vincoli.»

### 6:55–7:40 — Slide 9, Vincoli e insieme ammissibile

«La somma dei pesi uguale a uno impone il budget. I pesi non negativi escludono le posizioni corte. Il limite superiore u controlla la concentrazione massima su un titolo. I vincoli definiscono l’insieme dei portafogli realmente considerati dal modello. Se un limite rende impossibile finanziare l’intero portafoglio, il sistema segnala l’infattibilità invece di produrre una soluzione apparente.»

### 7:40–8:45 — Slide 10, Frontiera efficiente

«Per mostrare più alternative, il progetto usa anche una formulazione equivalente a rendimento obiettivo. Per ogni target tau minimizza la varianza mantenendo rendimento, budget e vincoli. Ripetendo il calcolo tra il portafoglio di minima varianza e il massimo rendimento raggiungibile si ottiene la frontiera efficiente. Il grafico usa un caso congelato del progetto. Ogni punto è Pareto-efficiente: per aumentare il rendimento stimato bisogna accettare più rischio, e non esiste un punto che domini tutti gli altri.»

### 8:45–9:35 — Slide 11, Dalla preferenza alla frontiera

«L’utente non deve scegliere direttamente lambda. I tre profili selezionano il 20, il 50 e l’80 per cento dell’intervallo di rendimento raggiungibile tra i due estremi. Conservative, moderate e aggressive descrivono quindi posizioni relative sulla stessa frontiera. Non sono probabilità di perdita, categorie universali o una valutazione regolamentare della persona.»

### 9:35–10:35 — Slide 12, Incertezza e valutazione

«L’ottimizzazione usa parametri stimati, quindi il DSS aggiunge due tipi di evidenza. Monte Carlo traduce rendimento e volatilità in distribuzioni condizionate a quelle stime; le bande non includono l’incertezza dei parametri. Il walk-forward ricalcola invece ogni decisione usando solo le informazioni disponibili prima della data di esecuzione. Il risultato congelato mostra il punto essenziale: con finestra rolling la media storica termina sopra l’esponenziale, mentre con finestra expanding accade il contrario. Il ranking si inverte, quindi nessuno stimatore vince universalmente.»

Transizione: «A questo punto il modello matematico è completo. Posso mostrare le scelte con cui l’ho trasformato in un DSS utilizzabile.»

### 10:35–11:35 — Slide 13, Dal modello al processo decisionale

«Il processo implementato mantiene una catena esplicita. Prima costruisce un campione coerente, poi stima mu e Sigma, genera la frontiera e confronta le alternative con baseline comuni. Dai risultati numerici ricava spiegazioni verificabili e infine restituisce la scelta all’utente. Il contributo non coincide con un singolo algoritmo: consiste nel mantenere coerenti dati, modelli, alternative ed evidenza durante tutto il percorso.»

### 11:35–13:00 — Slide 14, Scelte che rendono affidabile il DSS

«Tutte le alternative condividono la stessa finestra, gli stessi rendimenti e le stesse convenzioni. La sorgente di rendimento atteso può cambiare senza modificare il problema di ottimizzazione. Dopo la soluzione numerica, il sistema ricalcola le metriche e verifica in modo indipendente budget, pesi e limite di concentrazione. I dati mancanti non vengono riempiti silenziosamente. Le spiegazioni rimandano a fatti numerici identificabili. Seed e hash permettono di ripetere simulazioni e report. Se una soluzione non supera i controlli, il sistema mostra un errore e non una raccomandazione.»

### 13:00–15:00 — Slide 15, Perché è un buon sistema di supporto

«Possiamo ora confrontare il risultato con il ciclo iniziale. Il sistema informa mostrando periodo, dati e convenzioni. Confronta profili, pesi uguali e benchmark. Separa osservazioni storiche, parametri stimati, simulazioni ed evidenza fuori campione. Spiega risultati, vincoli e limiti. Soprattutto, non esegue ordini e non presenta una previsione come certezza. Queste proprietà rendono Portfolio DSS un sistema di supporto alla decisione, non un generatore automatico di portafogli. Nella demo seguirò lo stesso ciclo: preferenza, alternative, spiegazioni, incertezza e scelta.»

## Demo guidata — circa 7 minuti e 40 secondi

### 0:00–0:35 — Confine e provenienza

Mostrare la schermata iniziale e **API connected**.

«La demo usa prezzi sintetici deterministici, dichiarati nell’interfaccia, così il percorso rimane riproducibile e non dipende dalla rete. I risultati storici citati nella presentazione provengono invece dai report congelati. Anche qui il sistema supporta una decisione educativa e non esegue operazioni.»

### 0:35–1:25 — Preferenza e capitale

Selezionare:

- **Balance growth and fluctuations**;
- **Somewhat comfortable**;
- **Reassess before changing exposure**.

Premere **Continue to capital**, inserire `10000` e mantenere **Historical mean**.

«Le tre risposte esprimono una preferenza. La regola usa la risposta meno aggressiva e suggerisce quindi il profilo moderate. Inserisco diecimila dollari: il capitale serve soltanto a tradurre i pesi in importi illustrativi. Mantengo la media storica come sorgente del rendimento atteso.»

Premere **Get recommendation**.

### 1:25–2:20 — Campione e ipotesi comuni

Mostrare **Your starting point**, profilo suggerito, copertura, finestra e massimo 10%.

«Prima del risultato vediamo il contesto della decisione. Tutte le alternative condividono lo stesso periodo e le stesse osservazioni. Il sistema dichiara quanti titoli risultano eleggibili, quali vincoli applica e quali semplificazioni restano fuori dal modello. Anche conservative rimane un portafoglio azionario e non implica protezione del capitale.»

### 2:20–3:35 — Alternative sulla stessa frontiera

Mostrare moderate, poi selezionare conservative e aggressive. Indicare posizione sulla frontiera, rendimento annuo stimato, volatilità e allocazione.

«Questi tre pulsanti non richiamano nuovi prezzi. Selezionano punti diversi della stessa frontiera costruita con lo stesso campione. Muovendoci verso aggressive cambiano insieme rendimento obiettivo, volatilità e pesi. Il DSS rende visibile il costo della preferenza invece di presentare una sola soluzione come inevitabile.»

Tornare su **Moderate**.

### 3:35–4:35 — Spiegazioni verificabili

Aprire **Why this portfolio?** e indicare le ragioni principali e i fatti collegati.

«La spiegazione parte dal confronto con i pesi uguali, che rappresentano la baseline del percorso guidato. Ogni frase usa differenze numeriche di rendimento, volatilità, allocazione, concentrazione o contributo al rischio. Un titolo che raggiunge il limite massimo viene indicato come vincolo attivo. Il testo contestualizza una soluzione congiunta: non sostiene che un singolo indicatore abbia causato da solo un determinato peso.»

### 4:35–5:25 — Sensibilità allo stimatore

Mostrare **Historical vs forecast expected returns** senza cambiare lo stimatore selezionato.

«Qui gli stessi pesi vengono valutati con due stime del rendimento atteso: media storica uniforme e media esponenziale, che attribuisce più peso alle osservazioni recenti. Le differenze dipendono dal modello di rendimento, non da una seconda allocazione. Questo confronto mostra sensibilità metodologica senza dichiarare che uno stimatore sia universalmente superiore.»

### 5:25–7:10 — Esplorazione dell’incertezza

Aprire **Explore possible outcomes**. Impostare:

- orizzonte: **3 years**;
- confronto: **Equal weight**;
- percorsi: **10,000**;
- seed: `42`.

Eseguire la simulazione e mostrare mediana, P5, bande e probabilità di perdita.

«Ogni alternativa parte dagli stessi diecimila dollari. La linea mostra la mediana; le bande interne e esterne mostrano percentili della distribuzione simulata. Il P5 rappresenta un esito di coda del modello. La probabilità di perdita significa terminare sotto il capitale nominale iniziale dopo tre anni, non subire una perdita temporanea durante il percorso. I parametri e i pesi restano costanti e le bande non includono l’errore con cui mu e Sigma sono stati stimati.»

### 7:10–7:40 — Chiusura

Tornare al confronto dei profili.

«La demo ha seguito il ciclo del DSS: ha raccolto una preferenza, costruito alternative comparabili, spiegato le differenze ed esposto l’incertezza. Il sistema organizza l’evidenza; la decisione rimane all’utente.»

## Estensione facoltativa fino a dieci minuti

Se rimangono circa due minuti, aprire i dettagli avanzati e mostrare soltanto:

1. convenzioni finanziarie e intervallo effettivo;
2. limite massimo e diagnostica dei punti della frontiera;
3. provenienza dei dati, seed, report hash e result hash.

Dire:

«Questi dettagli permettono di ricostruire il significato del risultato e di ripetere lo stesso esperimento. Non modifico lo stimatore e non avvio una nuova ottimizzazione durante la demo, perché il confronto già mostrato è sufficiente a discutere la sensibilità del modello.»

## Fallback immediato

Se l’interfaccia non risponde entro 15 secondi:

1. Aprire `examples/case-studies/week11/report/report.html`.
2. Usare il caso **Risk-profile choices across five sectors** per mostrare stessa finestra e stessi vincoli, quindi confrontare conservative, moderate e aggressive.
3. Mostrare la simulazione congelata del profilo moderate e le relative limitazioni.
4. Aprire `examples/backtest/week9/report/report.html` e confrontare media storica, media esponenziale, pesi uguali e SPY proxy.
5. Concludere che i report sono autonomi, riproducibili e generati dagli stessi contratti matematici usati dal percorso interattivo.

## Uso delle appendici

- **A1 — Stima del rendimento atteso:** normalizzazione dei pesi esponenziali e half-life di 63 osservazioni.
- **A2 — Covarianza, correlazione e concentrazione:** differenza tra covarianza e correlazione, HHI ed effective count.
- **A3 — Contributi al rischio:** attribuzione di Eulero e contributi negativi come effetto di diversificazione.
- **A4 — Monte Carlo:** drift, volatilità, passo mensile, percentili e ipotesi di parametri costanti.
- **A5 — Backtest walk-forward:** risultati completi e formule delle metriche realizzate.

## Domande previste

### Perché questo progetto è un DSS e non soltanto un ottimizzatore?

Perché il processo comprende dati espliciti, alternative, baseline, preferenze, spiegazioni, incertezza e valutazione. L’ottimizzatore è un componente del modello; il DSS organizza l’intero processo e mantiene la decisione sotto il controllo dell’utente.

### Perché non viene mostrato un solo portafoglio ottimo?

La soluzione dipende dalla preferenza per il rischio e da parametri stimati. La frontiera rende visibili più compromessi Pareto-efficienti e permette all’utente di confrontarli con convenzioni comuni.

### Il profilo moderate rappresenta una suitability finanziaria?

No. La mappatura traduce tre preferenze illustrative in una posizione relativa sulla frontiera. Non considera reddito, patrimonio, obiettivi legali o altri requisiti di una valutazione regolamentare.

### Perché usare la varianza come misura di rischio?

È la misura richiesta dalla formulazione media-varianza e consente di rappresentare la diversificazione tramite la covarianza. Rimane una semplificazione: penalizza nello stesso modo oscillazioni positive e negative e non descrive tutti i rischi rilevanti.

### Perché rendimento atteso e covarianza devono usare lo stesso campione?

Il confronto richiede unità, frequenza e periodo compatibili. Mescolare finestre o convenzioni diverse renderebbe incoerenti sia il valore dell’obiettivo sia la posizione dei portafogli sulla frontiera.

### Perché usare SPY invece dell’indice ufficiale?

SPY fornisce una serie adjusted-close coerente con il trattamento total-return degli altri strumenti. Il progetto lo etichetta come proxy ETF e non come indice ufficiale.

### Perché il forecast è una media esponenziale semplice?

Serve a verificare la sostituibilità del segnale di rendimento atteso e a studiare la sensibilità delle decisioni con un modello comprensibile e deterministico. Non viene presentato come previsore certo.

### Come viene evitato il look-ahead nel backtest?

Ogni stima termina prima della data di esecuzione. Dopo l’allocazione, il portafoglio guadagna soltanto i rendimenti osservati successivamente. Tutte le strategie condividono le stesse sessioni di valutazione.

### Perché i pesi uguali ottengono il risultato migliore nel campione?

È un risultato del paniere, del periodo e delle ipotesi scelti. Mostra l’utilità di una baseline semplice e conferma che maggiore complessità non implica superiorità. Non giustifica una previsione futura.

### Cosa rende riproducibili demo e report?

La demo usa dati sintetici deterministici. Simulazioni e report registrano configurazione, convenzioni, versioni del modello, seed, provenienza e hash del contenuto. La riproducibilità richiede gli stessi input e lo stesso ambiente numerico.

### Perché non sono inclusi costi, tasse e turnover?

Phase B verifica il nucleo del DSS e la formulazione richiesta. Costi e turnover modificherebbero insieme ottimizzazione, valutazione ed explanation layer; costituiscono un’estensione del modello, non una semplice voce da sottrarre alla fine.
