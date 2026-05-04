import os
import logging
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "0"))

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# In-memory storage (persists while bot is running)
conversation_history = []
platform_data = {
    "clients": [
        {"id": "c1", "name": "Laboratorio Borse", "sector": "Artigianato", "phase": 2,
         "instagram": "@laboratorioborse", "tiktok": "@laboratorioborse",
         "videoStyle": "Nel laboratorio, mani che lavorano il cuoio, 30-60 sec, tono autentico",
         "goal": "Aumentare visibilità Instagram e TikTok"},
        {"id": "c2", "name": "Centro Estetico", "sector": "Bellezza", "phase": 1,
         "instagram": "@centroestetico", "tiktok": "",
         "videoStyle": "Video brevi e dinamici, prima/dopo, promozioni",
         "goal": "Riempire agenda con nuove clienti"}
    ],
    "videos": [],
    "pipeline": [],
    "appointments": [],
    "metrics": {}
}

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_system_prompt():
    today = datetime.now().strftime("%A %d %B %Y")
    
    # Build context from platform data
    clients_ctx = "\n".join([
        f"• {c['name']} [ID:{c['id']}] — {c['sector']}, Fase {c['phase']}/6, "
        f"IG:{c.get('instagram','—')}, TT:{c.get('tiktok','—')}\n"
        f"  Stile: {c.get('videoStyle','—')}\n"
        f"  Obiettivo: {c.get('goal','—')}"
        for c in platform_data["clients"]
    ]) or "Nessuno"
    
    towrite = [v for v in platform_data["videos"] if v["stato"] == "da scrivere"]
    torecord = [v for v in platform_data["videos"] if v["stato"] == "da registrare"]
    toedit = [v for v in platform_data["videos"] if v["stato"] == "in editing"]
    toreview = [v for v in platform_data["videos"] if v["stato"] == "da revisionare"]
    topost = [v for v in platform_data["videos"] if v["stato"] == "pronto"]
    
    def vlist(lst):
        if not lst: return "—"
        return ", ".join([f'"{v["title"]}" [{next((c["name"] for c in platform_data["clients"] if c["id"]==v["clientId"]), "?")}]' for v in lst])
    
    tod_appts = [a for a in platform_data["appointments"] if a["date"] == get_today() and a["status"] == "Da fare"]
    fups = [p for p in platform_data["pipeline"] if p.get("followUp", "") <= get_today() and p["stato"] not in ["Chiuso", "Non interessato"] and p.get("followUp")]
    active_pipe = [p for p in platform_data["pipeline"] if p["stato"] not in ["Chiuso", "Non interessato"]]
    
    return f"""Sei Giorgio, l'assistente personale di Tommaso Maifredi.

IDENTITÀ:
- Social media manager freelance, zona Brescia-Bergamo
- Gestisce Reel Instagram, TikTok, Facebook Reel per attività locali
- 4-6 video/settimana per cliente, registrati settimanalmente
- 2 clienti ora, obiettivo 10. Contatta prospect via WA/email/IG DM, target 20/giorno
- Ha un profilo personale agenzia: video acquisizione POV, percorso agenzia, dietro le quinte

OGGI — {today}

CLIENTI ({len(platform_data["clients"])}):
{clients_ctx}

VIDEO:
• ✍️ Da scrivere ({len(towrite)}): {vlist(towrite)}
• 🎬 Da registrare ({len(torecord)}): {vlist(torecord)}
• ✂️ In editing ({len(toedit)}): {vlist(toedit)}
• 👁 Da revisionare ({len(toreview)}): {vlist(toreview)}
• ✅ Pronti da pubblicare ({len(topost)}): {vlist(topost)}

APPUNTAMENTI OGGI ({len(tod_appts)}):
{chr(10).join([f'• {a["time"]} — {a["title"]}' for a in tod_appts]) or "Nessuno"}

PIPELINE ({len(active_pipe)} attivi):
{chr(10).join([f'• "{p["nome"]}" — {p["stato"]}{" 📱"+p["telefono"] if p.get("telefono") else ""}{" ⏰"+p["followUp"] if p.get("followUp") else ""}' for p in platform_data["pipeline"]]) or "Nessuno"}

FOLLOW-UP OGGI: {", ".join([p["nome"] for p in fups]) or "Nessuno"}

AZIONI PIATTAFORMA — usa questi tag nel tuo testo per aggiornare automaticamente:
[[ADD_VIDEO|titolo:...|clienteId:c1|piattaforma:Instagram|stato:da scrivere|data:YYYY-MM-DD|note:...]]
[[UPD_VIDEO|titolo:...|stato:da registrare]]
[[ADD_APPT|titolo:...|data:YYYY-MM-DD|ora:HH:MM|tipo:Call|con:NOME]]
[[DONE_APPT|titolo:...]]
[[ADD_PIPE|nome:...|settore:...|citta:...|tel:...|followup:YYYY-MM-DD]]
[[UPD_PIPE|nome:...|stato:Contattato]]
[[ADD_CLIENT|nome:...|settore:...|instagram:@...|obiettivo:...]]
[[UPD_METRICS|clienteId:c1|follower:N|views:N|lead:N]]

LINKS UTILI — includili quando serve:
- WhatsApp diretto: https://wa.me/39NUMERO (senza spazi, es: wa.me/393401234567)
- Instagram profilo: https://instagram.com/handle

STILE:
- Italiano, diretto, concreto, professionale
- Risposte brevi (max 6-8 righe) salvo briefing mattina
- Agisci subito senza chiedere conferma per cose ovvie
- "ho fatto X" → aggiorna stato video
- "nuovo contatto: nome, settore, città, numero" → aggiungi pipeline
- "appuntamento con X giovedì alle 15" → crea appuntamento
- Quando mandi link WA, formattali così: 👉 [Apri WhatsApp con Nome](wa.me/39...)

OGNI MATTINA quando Tommaso saluta, dai subito:
1. Priorità del giorno (numerata)
2. Video da gestire (per stato)
3. Appuntamenti del giorno
4. Follow-up scaduti con link WA diretto
5. Target prospect (20/giorno)"""

def execute_commands(text):
    """Parse and execute [[CMD]] tags from Giorgio's response"""
    import re
    uid_counter = [int(datetime.now().timestamp())]
    
    def new_id():
        uid_counter[0] += 1
        return f"id_{uid_counter[0]}"
    
    def parse_params(param_str):
        params = {}
        for part in param_str.split("|"):
            if ":" in part:
                k, v = part.split(":", 1)
                params[k.strip()] = v.strip()
        return params
    
    pattern = r'\[\[([A-Z_]+)\|([^\]]+)\]\]'
    matches = re.findall(pattern, text)
    executed = []
    
    for cmd, params_str in matches:
        p = parse_params(params_str)
        
        if cmd == "ADD_VIDEO":
            video = {
                "id": new_id(),
                "clientId": p.get("clienteId", p.get("cliente", "")),
                "title": p.get("titolo", p.get("title", "Video")),
                "platform": p.get("piattaforma", p.get("platform", "Instagram")),
                "stato": p.get("stato", "da scrivere"),
                "pubDate": p.get("data", p.get("pubDate", "")),
                "notes": p.get("note", p.get("notes", "")),
                "script": "", "caption": "", "checklist": [],
                "createdAt": get_today()
            }
            platform_data["videos"].append(video)
            executed.append(f"✅ Video aggiunto: \"{video['title']}\"")
            
        elif cmd == "UPD_VIDEO":
            title = p.get("titolo", p.get("title", "")).lower()
            for v in platform_data["videos"]:
                if title in v["title"].lower():
                    if "stato" in p: v["stato"] = p["stato"]
                    if "data" in p: v["pubDate"] = p["data"]
                    if "note" in p: v["notes"] = p["note"]
                    executed.append(f"✅ Video aggiornato: \"{v['title']}\" → {p.get('stato', 'aggiornato')}")
                    break
                    
        elif cmd == "ADD_APPT":
            appt = {
                "id": new_id(),
                "title": p.get("titolo", p.get("title", "Appuntamento")),
                "date": p.get("data", p.get("date", get_today())),
                "time": p.get("ora", p.get("time", "")),
                "type": p.get("tipo", p.get("type", "Call")),
                "status": "Da fare",
                "notes": p.get("note", ""),
                "clientId": "", "pipelineId": ""
            }
            # Try to link to pipeline
            con = p.get("con", "")
            if con:
                for pipe in platform_data["pipeline"]:
                    if con.lower() in pipe["nome"].lower():
                        appt["pipelineId"] = pipe["id"]
                        break
            platform_data["appointments"].append(appt)
            executed.append(f"✅ Appuntamento: \"{appt['title']}\" il {appt['date']}{' alle '+appt['time'] if appt['time'] else ''}")
            
        elif cmd == "DONE_APPT":
            title = p.get("titolo", "").lower()
            for a in platform_data["appointments"]:
                if title in a["title"].lower():
                    a["status"] = "Fatto"
                    executed.append(f"✅ Appuntamento completato: \"{a['title']}\"")
                    break
                    
        elif cmd == "ADD_PIPE":
            lead = {
                "id": new_id(),
                "nome": p.get("nome", p.get("name", "Lead")),
                "settore": p.get("settore", ""),
                "citta": p.get("citta", ""),
                "telefono": p.get("tel", p.get("telefono", "")),
                "email": p.get("email", ""),
                "instagram": p.get("instagram", ""),
                "stato": p.get("stato", "Nuovo lead"),
                "note": p.get("note", ""),
                "followUp": p.get("followup", p.get("followUp", "")),
                "salvato": get_today()
            }
            platform_data["pipeline"].append(lead)
            executed.append(f"✅ Lead aggiunto: \"{lead['nome']}\"")
            
        elif cmd == "UPD_PIPE":
            nome = p.get("nome", "").lower()
            for pipe in platform_data["pipeline"]:
                if nome in pipe["nome"].lower():
                    if "stato" in p: pipe["stato"] = p["stato"]
                    if "note" in p: pipe["note"] = p["note"]
                    if "followup" in p: pipe["followUp"] = p["followup"]
                    executed.append(f"✅ Lead aggiornato: \"{pipe['nome']}\" → {p.get('stato', 'aggiornato')}")
                    break
                    
        elif cmd == "ADD_CLIENT":
            av = "".join([w[0].upper() for w in p.get("nome", "?").split() if w])[:2]
            c = {
                "id": new_id(),
                "name": p.get("nome", p.get("name", "Cliente")),
                "avatar": av,
                "sector": p.get("settore", ""),
                "phase": int(p.get("fase", "1")),
                "goal": p.get("obiettivo", ""),
                "instagram": p.get("instagram", ""),
                "tiktok": p.get("tiktok", ""),
                "videoStyle": p.get("stile", "")
            }
            platform_data["clients"].append(c)
            executed.append(f"✅ Cliente aggiunto: \"{c['name']}\"")
            
        elif cmd == "UPD_METRICS":
            cid = p.get("clienteId", p.get("clientId", ""))
            if cid not in platform_data["metrics"]:
                platform_data["metrics"][cid] = {}
            m = platform_data["metrics"][cid]
            for key in ["follower", "followers", "views", "like", "likes", "lead", "leads", "vendite", "sales"]:
                if key in p:
                    canonical = key.rstrip("s") if key.endswith("s") else key
                    m[canonical] = int(p[key])
            name = next((c["name"] for c in platform_data["clients"] if c["id"]==cid), cid)
            executed.append(f"✅ Metriche aggiornate: {name}")
    
    # Remove command tags from text
    clean = re.sub(r'\[\[[A-Z_]+\|[^\]]+\]\]', '', text).strip()
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    return clean, executed

def get_platform_status():
    """Get a summary of current platform state"""
    videos_by_status = {}
    for v in platform_data["videos"]:
        videos_by_status[v["stato"]] = videos_by_status.get(v["stato"], 0) + 1
    
    active_pipe = [p for p in platform_data["pipeline"] if p["stato"] not in ["Chiuso", "Non interessato"]]
    
    return (
        f"📊 *Stato SocialOS*\n\n"
        f"👥 Clienti: {len(platform_data['clients'])}\n"
        f"🎬 Video:\n" +
        "\n".join([f"  • {s}: {n}" for s, n in videos_by_status.items()]) +
        f"\n📋 Pipeline: {len(active_pipe)} attivi\n"
        f"📅 Appuntamenti: {len([a for a in platform_data['appointments'] if a['status']=='Da fare'])} da fare"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        return
    await update.message.reply_text(
        "👋 Ciao Tommaso! Sono Giorgio, il tuo assistente personale.\n\n"
        "Posso aiutarti a gestire:\n"
        "• 🎬 Video (stati, script, pubblicazioni)\n"
        "• 👥 Clienti e prospect\n"
        "• 📅 Appuntamenti e follow-up\n"
        "• 📊 Metriche\n\n"
        "Parla normalmente o mandami un messaggio vocale!\n\n"
        "Comandi rapidi:\n"
        "/briefing — Briefing del giorno\n"
        "/stato — Stato piattaforma\n"
        "/reset — Resetta conversazione"
    )

async def briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        return
    await handle_text(update, context, override_text="Dammi il briefing completo della giornata di oggi.")

async def stato_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        return
    await update.message.reply_text(get_platform_status(), parse_mode="Markdown")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        return
    global conversation_history
    conversation_history = []
    await update.message.reply_text("✅ Conversazione resettata. Ciao di nuovo!")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        return
    await update.message.reply_text(
        "🎤 Ho ricevuto il tuo vocale!\n\n"
        "Per ora scrivi il messaggio come testo — la trascrizione vocale "
        "sarà disponibile nella prossima versione.\n\n"
        "Scrivi quello che volevi dire e rispondo subito! 💬"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE, override_text=None):
    if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
        return
    
    user_text = override_text or update.message.text
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )
    
    # Add to history
    conversation_history.append({"role": "user", "content": user_text})
    
    # Keep last 20 messages
    history = conversation_history[-20:]
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1600,
            system=get_system_prompt(),
            messages=history
        )
        
        raw_response = response.content[0].text
        clean_response, executed = execute_commands(raw_response)
        
        # Add to history
        conversation_history.append({"role": "assistant", "content": raw_response})
        
        # Send main response
        if clean_response:
            # Split long messages
            if len(clean_response) > 4096:
                parts = [clean_response[i:i+4000] for i in range(0, len(clean_response), 4000)]
                for part in parts:
                    await update.message.reply_text(part)
            else:
                await update.message.reply_text(clean_response)
        
        # Send executed actions summary if any
        if executed:
            actions_text = "📋 *Aggiornato in SocialOS:*\n" + "\n".join(executed)
            await update.message.reply_text(actions_text, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Errore: {str(e)}\n\nControlla la API key.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("briefing", briefing_command))
    app.add_handler(CommandHandler("stato", stato_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("Giorgio Bot avviato!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
