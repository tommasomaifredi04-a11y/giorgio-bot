# Giorgio Bot — Setup su Render.com

## Cosa ti serve
- Account GitHub (gratuito)
- Account Render.com (gratuito)
- Token Telegram Bot (già hai: 8534016617:AAETUWq6iE2gKJE3-TRigvmKkZWLVXzMm-w)
- API Key Anthropic (già hai)
- Il tuo Telegram User ID

## Step 1 — Carica su GitHub

1. Vai su github.com → New repository
2. Nome: `giorgio-bot`
3. Carica i 3 file: main.py, requirements.txt, render.yaml

## Step 2 — Deploy su Render

1. Vai su render.com → New → Web Service
2. Collega il repository GitHub `giorgio-bot`
3. Render rileva automaticamente render.yaml

## Step 3 — Variabili d'ambiente

Nel pannello Render, aggiungi queste variabili:

| Nome | Valore |
|------|--------|
| TELEGRAM_TOKEN | 8534016617:AAETUWq6iE2gKJE3-... (il tuo token completo) |
| ANTHROPIC_API_KEY | sk-ant-api03-... (la tua chiave) |
| ALLOWED_USER_ID | Il tuo Telegram User ID (vedi sotto) |

## Come trovare il tuo Telegram User ID

Su Telegram cerca @userinfobot e mandagli /start — ti dice il tuo ID numerico.

## Step 4 — Avvia

Render fa partire il bot automaticamente. Apri Telegram, cerca @GiorgioSocialOs_bot e scrivi /start.

## Comandi disponibili

- /start — Presentazione
- /briefing — Briefing del giorno
- /stato — Stato piattaforma
- /reset — Resetta conversazione

## Utilizzo normale

Scrivi o manda un vocale (trascrizione automatica):
- "Ciao Giorgio, cosa devo fare oggi?"
- "Ho registrato il video delle borse"
- "Nuovo prospect: Pizzeria Da Mario, Brescia, 030123456"
- "Appuntamento con Pizzeria Da Mario giovedì alle 15"
- "Aggiungi video: Il cuoio italiano, per Laboratorio Borse, Instagram, data 10 maggio"
