# Nota della professoressa

## Formulazione del problema

\[
\max_x \quad a^T x - \lambda x^T Q x
\]

dove:

- \(a \in \mathbb{R}^n\): vettore dei **ritorni attesi**
  - stimati a partire da **dati storici**
- \(Q\): matrice di **rischio del portafoglio**
  - da calcolare come matrice di **covarianza**
- \(\lambda\): parametro di **avversione al rischio**
- \(x \in \mathbb{R}^n\): vettore delle **variabili decisionali**

## Dati

- Dati da **Yahoo Finance**
- Universo iniziale: **S&P 500**
- \(Q\) calcolata con **Python**, ad esempio tramite la covarianza dei rendimenti con **pandas**

## Interpretazione

Il problema cerca di trovare un portafoglio che bilanci:

- **rendimento atteso**, rappresentato da \(a^T x\)
- **rischio**, rappresentato da \(x^T Q x\)

Il parametro \(\lambda\) controlla quanto il rischio viene penalizzato rispetto al rendimento atteso.

> Nota: nella foto originale la frase accanto a \(Q\) non è completamente leggibile; il significato sembra essere “matrice di rischio del portafoglio”.
