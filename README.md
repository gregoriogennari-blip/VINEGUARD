# VINEGUARD

VineGuard è un progetto di monitoraggio intelligente per vigneto che unisce sensori ambientali, backend Django, database InfluxDB e dashboard web in tempo reale.

## Cosa fa

- Raccoglie dati da sensori come temperatura aria, umidità aria, umidità del suolo e pioggia.
- Riceve i dati tramite API Django.
- Salva le misure su InfluxDB.
- Mostra i valori più recenti in una dashboard web.
- Supporta notifiche di emergenza via Telegram.
- Integra una logica di rischio/ML per stimare il livello di attenzione del vigneto.

## Stack usato

- **Backend:** Django
- **Database time-series:** InfluxDB
- **Frontend:** HTML, CSS, JavaScript
- **Alerting:** Telegram Bot API
- **Analytics / rischio:** Machine Learning + regole applicative

## Flusso del progetto

```text
Sensori nel vigneto
   -> Invio dati
   -> Backend Django
   -> InfluxDB
   -> Dashboard web
   -> Alert / analisi rischio
```

## Obiettivo

L'obiettivo di VineGuard è aiutare il monitoraggio del vigneto in modo semplice e centralizzato, rendendo più facile controllare i parametri ambientali e individuare situazioni critiche.

## Avvio rapido

```bash
git clone https://github.com/gregoriogennari-blip/VINEGUARD.git
cd VINEGUARD
pip install -r requirements.txt
python manage.py runserver
```

## Note

Il progetto è pensato come prototipo scolastico ma con una struttura reale, espandibile con nodi sensore aggiuntivi, modelli ML migliori e una dashboard sempre più completa.
