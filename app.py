import os
import requests
import time
import json
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template_string

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TU_TOKEN_AQUI")
CHAT_ID = os.environ.get("CHAT_ID", "TU_CHAT_ID_AQUI")

STATS_INICIALES = {
    "ANA": {"gf": 1, "gc": 2}, "BOS": {"gf": 5, "gc": 1}, "BUF": {"gf": 1, "gc": 1},
    "CAR": {"gf": 3, "gc": 0}, "CBJ": {"gf": 1, "gc": 2}, "CGY": {"gf": 3, "gc": 1},
    "CHI": {"gf": 3, "gc": 3}, "COL": {"gf": 1, "gc": 2}, "DAL": {"gf": 0, "gc": 2},
    "DET": {"gf": 1, "gc": 1}, "EDM": {"gf": 2, "gc": 2}, "FLA": {"gf": 1, "gc": 2},
    "LAK": {"gf": 2, "gc": 4}, "MIN": {"gf": 4, "gc": 0}, "MTL": {"gf": 1, "gc": 3},
    "NJD": {"gf": 3, "gc": 1}, "NSH": {"gf": 2, "gc": 0}, "NYI": {"gf": 2, "gc": 3},
    "NYR": {"gf": 6, "gc": 4}, "OTT": {"gf": 3, "gc": 6}, "PHI": {"gf": 1, "gc": 2},
    "PIT": {"gf": 1, "gc": 2}, "SEA": {"gf": 1, "gc": 2}, "SJS": {"gf": 2, "gc": 4},
    "STL": {"gf": 3, "gc": 2}, "TBL": {"gf": 3, "gc": 3}, "TOR": {"gf": 3, "gc": 3},
    "UTA": {"gf": 1, "gc": 2}, "VAN": {"gf": 1, "gc": 1}, "VGK": {"gf": 4, "gc": 1},
    "WPG": {"gf": 0, "gc": 1}, "WSH": {"gf": 2, "gc": 3}
}

STATS_6V5 = {}
HISTORIAL_SENALES = [] # Aquí guardaremos las alertas para la web
ESTADO_RADAR = "ACTIVO"

def cargar_json():
    global STATS_6V5
    if not os.path.exists('stats_6v5.json'):
        with open('stats_6v5.json', 'w') as archivo:
            json.dump(STATS_INICIALES, archivo, indent=4)
    try:
        with open('stats_6v5.json', 'r') as archivo:
            STATS_6V5 = json.load(archivo)
    except:
        STATS_6V5 = STATS_INICIALES

# ==========================================
# 🎨 DISEÑO DE LA PÁGINA WEB (HTML + CSS)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Radar NHL</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; color: #333; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 24px; display: flex; align-items: center; gap: 10px; }
        .status-badge { background-color: #10b981; color: white; padding: 5px 15px; border-radius: 20px; font-size: 14px; font-weight: bold; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .stat-item { text-align: center; }
        .stat-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; }
        .stat-value { font-size: 28px; font-weight: bold; color: #111827; margin-top: 5px; }
        .signals-title { font-size: 14px; font-weight: bold; color: #6b7280; text-transform: uppercase; margin-bottom: 15px; letter-spacing: 1px; }
        .card { background: white; border-radius: 12px; padding: 15px 20px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-left: 5px solid #10b981; }
        .card.empty-net { border-left-color: #ef4444; }
        .card-header { display: flex; justify-content: space-between; margin-bottom: 10px; }
        .match-name { font-weight: bold; font-size: 16px; }
        .match-time { color: #6b7280; font-size: 14px; }
        .signal-detail { font-size: 14px; color: #4b5563; margin-bottom: 5px; }
        .signal-highlight { font-weight: bold; color: #111827; }
    </style>
    <meta http-equiv="refresh" content="10"> <!-- Recarga la página cada 10 segundos -->
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏒 Radar NHL</h1>
            <div class="status-badge">{{ estado }}</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-label">Señales Hoy</div>
                <div class="stat-value">{{ historial|length }}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Porteros Quitados</div>
                <div class="stat-value">{{ historial|selectattr('tipo', 'equalto', 'Portero Quitado')|list|length }}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Goles Red Vacía</div>
                <div class="stat-value">{{ historial|selectattr('tipo', 'equalto', 'Gol Red Vacía')|list|length }}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Último Escaneo</div>
                <div class="stat-value" style="font-size: 16px; padding-top: 8px;">{{ ultimo_scan }}</div>
            </div>
        </div>

        <div class="signals-title">Señales Recientes</div>
        
        {% if historial %}
            {% for senal in historial %}
            <div class="card {{ 'empty-net' if senal.tipo == 'Gol Red Vacía' else '' }}">
                <div class="card-header">
                    <div class="match-name">{{ senal.partido }}</div>
                    <div class="match-time">P{{ senal.periodo }} - {{ senal.tiempo }}</div>
                </div>
                <div class="signal-detail">
                    <span class="signal-highlight">{{ senal.tipo|upper }}</span> 
                    {% if senal.tipo == 'Portero Quitado' %}
                    | Ataca: <strong>{{ senal.equipo }}</strong>
                    {% else %}
                    | Anotador: <strong>{{ senal.equipo }}</strong>
                    {% endif %}
                </div>
                {% if senal.tipo == 'Portero Quitado' %}
                <div class="signal-detail" style="font-size: 12px; color: #6b7280;">
                    Stats: Si hay gol, {{ senal.pct_favor }}% es de {{ senal.equipo }} | {{ senal.pct_contra }}% es en red vacía.
                </div>
                {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <div class="card" style="text-align: center; color: #6b7280; border-left-color: #cbd5e1;">
                No hay señales recientes. Esperando acción en el hielo...
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

app = Flask(__name__)

@app.route('/')
def home():
    # Calculamos la hora del último escaneo para mostrarla en la web
    ultimo_scan = datetime.now().strftime('%H:%M:%S')
    return render_template_string(HTML_TEMPLATE, 
                                  historial=HISTORIAL_SENALES[::-1][:10], # Muestra las últimas 10, la más nueva primero
                                  estado=ESTADO_RADAR,
                                  ultimo_scan=ultimo_scan)

# ==========================================
# 🧠 LÓGICA DEL RADAR
# ==========================================
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=3)
    except Exception as e:
        print("Error Telegram:", e)

eventos_alertados = set() 
game_states = {} 

def procesar_partido(juego):
    game_id = juego['id']
    home_team = juego['homeTeam']['abbrev']
    away_team = juego['awayTeam']['abbrev']
    home_id = juego['homeTeam']['id']
    away_id = juego['awayTeam']['id']
    
    url_pbp = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
    try:
        pbp_data = requests.get(url_pbp, timeout=2).json()
    except:
        return
    
    plays = pbp_data.get('plays', [])
    if not plays: return
    
    latest_play = plays[-1]
    latest_sit = latest_play.get('situationCode')
    
    if latest_sit:
        period = latest_play['periodDescriptor']['number']
        if period < 3: return 
            
        if game_id not in game_states:
            game_states[game_id] = latest_sit
        else:
            prev_sit = game_states[game_id]
            if latest_sit != prev_sit:
                p_away_g, c_away_g = prev_sit[0], latest_sit[0]
                p_home_g, c_home_g = prev_sit[3], latest_sit[3]
                time_str = latest_play['timeInPeriod']
                
                if p_away_g == '1' and c_away_g == '0':
                    stats = STATS_6V5.get(away_team, {'gf': 0, 'gc': 0})
                    total = stats['gf'] + stats['gc']
                    pct_gf = (stats['gf'] / total * 100) if total > 0 else 0
                    pct_gc = (stats['gc'] / total * 100) if total > 0 else 0
                    
                    msg = (f"🚨 *¡PORTERO QUITADO!*\n🏒 *{away_team}* ataca con 6 jugadores.\n"
                           f"⏱️ P{period} - {time_str} | 🆚 {away_team} vs {home_team}\n\n"
                           f"📊 *Stats ({away_team} atacando):*\n"
                           f"⚔️ Si hay gol, *{pct_gf:.1f}%* es de {away_team}.\n"
                           f"🥅 Si hay gol, *{pct_gc:.1f}%* es en red vacía (anota {home_team}).")
                    enviar_telegram(msg)
                    
                    # GUARDAR EN EL HISTORIAL WEB
                    HISTORIAL_SENALES.append({
                        'tipo': 'Portero Quitado', 'equipo': away_team, 'partido': f"{away_team} vs {home_team}",
                        'periodo': period, 'tiempo': time_str, 'pct_favor': round(pct_gf, 1), 'pct_contra': round(pct_gc, 1)
                    })
                    
                elif p_home_g == '1' and c_home_g == '0':
                    stats = STATS_6V5.get(home_team, {'gf': 0, 'gc': 0})
                    total = stats['gf'] + stats['gc']
                    pct_gf = (stats['gf'] / total * 100) if total > 0 else 0
                    pct_gc = (stats['gc'] / total * 100) if total > 0 else 0
                    
                    msg = (f"🚨 *¡PORTERO QUITADO!*\n🏒 *{home_team}* ataca con 6 jugadores.\n"
                           f"⏱️ P{period} - {time_str} | 🆚 {away_team} vs {home_team}\n\n"
                           f"📊 *Stats ({home_team} atacando):*\n"
                           f"⚔️ Si hay gol, *{pct_gf:.1f}%* es de {home_team}.\n"
                           f"🥅 Si hay gol, *{pct_gc:.1f}%* es en red vacía (anota {away_team}).")
                    enviar_telegram(msg)
                    
                    # GUARDAR EN EL HISTORIAL WEB
                    HISTORIAL_SENALES.append({
                        'tipo': 'Portero Quitado', 'equipo': home_team, 'partido': f"{away_team} vs {home_team}",
                        'periodo': period, 'tiempo': time_str, 'pct_favor': round(pct_gf, 1), 'pct_contra': round(pct_gc, 1)
                    })
                game_states[game_id] = latest_sit

    for play in plays[-5:]:
        play_id = play['eventId']
        if play_id in eventos_alertados: continue
        if play.get('typeDescKey') == 'goal' and play['periodDescriptor']['number'] >= 3:
            sit = play.get('situationCode')
            anotador_id = play['details'].get('eventOwnerTeamId')
            if sit:
                away_g, home_g = sit[0], sit[3]
                if away_g == '0' or home_g == '0':
                    equipo_gol = away_team if anotador_id == away_id else home_team
                    time_str = play['timeInPeriod']
                    
                    msg = (f"⚽ *¡GOL EN RED VACÍA!*\n🏒 Anotador: *{equipo_gol}*\n"
                           f"⏱️ P{play['periodDescriptor']['number']} - {time_str} | 🆚 {away_team} vs {home_team}")
                    enviar_telegram(msg)
                    
                    # GUARDAR EN EL HISTORIAL WEB
                    HISTORIAL_SENALES.append({
                        'tipo': 'Gol Red Vacía', 'equipo': equipo_gol, 'partido': f"{away_team} vs {home_team}",
                        'periodo': play['periodDescriptor']['number'], 'tiempo': time_str
                    })
                eventos_alertados.add(play_id)

def radar_en_vivo():
    while True:
        try:
            res = requests.get("https://api-web.nhle.com/v1/scoreboard/now", timeout=3).json()
            partidos = [j for d in res.get('gamesByDate', []) for j in d.get('games', []) if j.get('gameState') in ['LIVE', 'CRIT']]
            if partidos:
                with ThreadPoolExecutor(max_workers=len(partidos)) as executor:
                    executor.map(procesar_partido, partidos)
        except: pass
        time.sleep(3)

# ==========================================
# ⏰ ACTUALIZADOR DIARIO
# ==========================================
def actualizador_diario():
    ultimo_dia = ""
    while True:
        hoy = datetime.now().strftime("%Y-%m-%d")
        if hoy != ultimo_dia:
            ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            try:
                data = requests.get(f"https://api-web.nhle.com/v1/schedule/{ayer}", timeout=5).json()
                for dia in data.get('gameWeek', []):
                    if dia['date'] == ayer:
                        for juego in dia.get('games', []):
                            if juego.get('gameState') not in ['FINAL', 'OFF']: continue
                            pbp = requests.get(f"https://api-web.nhle.com/v1/gamecenter/{juego['id']}/play-by-play", timeout=5).json()
                            if 'plays' not in pbp: continue
                            
                            ht, at = pbp['homeTeam']['abbrev'], pbp['awayTeam']['abbrev']
                            hid, aid = pbp['homeTeam']['id'], pbp['awayTeam']['id']
                            for eq in [ht, at]:
                                if eq not in STATS_6V5: STATS_6V5[eq] = {'gf': 0, 'gc': 0}
                            
                            for play in pbp['plays']:
                                if play.get('periodDescriptor', {}).get('number', 1) < 3: continue
                                if play.get('typeDescKey') == 'goal':
                                    sit = play.get('situationCode')
                                    anotador = play['details'].get('eventOwnerTeamId')
                                    if sit:
                                        if sit[3] == '0' and anotador == aid:
                                            STATS_6V5[at]['gf'] += 1; STATS_6V5[ht]['gc'] += 1
                                        elif sit[0] == '0' and anotador == hid:
                                            STATS_6V5[ht]['gf'] += 1; STATS_6V5[at]['gc'] += 1
                with open('stats_6v5.json', 'w') as archivo: json.dump(STATS_6V5, archivo, indent=4)
                ultimo_dia = hoy
            except Exception as e: pass
        time.sleep(3600)

# ==========================================
# ▶️ INICIO
# ==========================================
if __name__ == "__main__":
    cargar_json()
    threading.Thread(target=radar_en_vivo, daemon=True).start()
    threading.Thread(target=actualizador_diario, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
