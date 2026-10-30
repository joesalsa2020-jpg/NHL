import os
import requests
import time
import json
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template_string, redirect, url_for

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TU_TOKEN_AQUI")
CHAT_ID = os.environ.get("CHAT_ID", "TU_CHAT_ID_AQUI")

# Datos iniciales basados en la nueva tabla de efectividad (Pulls, Éxitos, Desastres, Sin Gol)
STATS_INICIALES = {
    "ANA": {"pulls": 2, "exitos": 0, "desastres": 0, "sin_gol": 2}, "BOS": {"pulls": 3, "exitos": 1, "desastres": 1, "sin_gol": 1},
    "BUF": {"pulls": 3, "exitos": 0, "desastres": 1, "sin_gol": 2}, "CAR": {"pulls": 2, "exitos": 0, "desastres": 0, "sin_gol": 2},
    "CBJ": {"pulls": 0, "exitos": 0, "desastres": 0, "sin_gol": 0}, "CGY": {"pulls": 1, "exitos": 0, "desastres": 1, "sin_gol": 0},
    "CHI": {"pulls": 2, "exitos": 0, "desastres": 1, "sin_gol": 1}, "COL": {"pulls": 0, "exitos": 0, "desastres": 0, "sin_gol": 0},
    "DAL": {"pulls": 4, "exitos": 0, "desastres": 2, "sin_gol": 2}, "DET": {"pulls": 3, "exitos": 0, "desastres": 1, "sin_gol": 2},
    "EDM": {"pulls": 2, "exitos": 1, "desastres": 0, "sin_gol": 1}, "FLA": {"pulls": 4, "exitos": 1, "desastres": 0, "sin_gol": 3},
    "LAK": {"pulls": 3, "exitos": 1, "desastres": 0, "sin_gol": 2}, "MIN": {"pulls": 1, "exitos": 0, "desastres": 0, "sin_gol": 1},
    "MTL": {"pulls": 8, "exitos": 3, "desastres": 1, "sin_gol": 4}, "NJD": {"pulls": 2, "exitos": 0, "desastres": 0, "sin_gol": 2},
    "NSH": {"pulls": 3, "exitos": 0, "desastres": 0, "sin_gol": 3}, "NYI": {"pulls": 3, "exitos": 0, "desastres": 2, "sin_gol": 1},
    "NYR": {"pulls": 1, "exitos": 0, "desastres": 1, "sin_gol": 0}, "OTT": {"pulls": 4, "exitos": 0, "desastres": 1, "sin_gol": 3},
    "PHI": {"pulls": 5, "exitos": 0, "desastres": 1, "sin_gol": 4}, "PIT": {"pulls": 3, "exitos": 0, "desastres": 0, "sin_gol": 3},
    "SEA": {"pulls": 1, "exitos": 0, "desastres": 1, "sin_gol": 0}, "SJS": {"pulls": 3, "exitos": 0, "desastres": 0, "sin_gol": 3},
    "STL": {"pulls": 1, "exitos": 0, "desastres": 0, "sin_gol": 0}, "TBL": {"pulls": 3, "exitos": 0, "desastres": 1, "sin_gol": 2},
    "TOR": {"pulls": 6, "exitos": 0, "desastres": 0, "sin_gol": 6}, "UTA": {"pulls": 2, "exitos": 0, "desastres": 1, "sin_gol": 1},
    "VAN": {"pulls": 4, "exitos": 0, "desastres": 0, "sin_gol": 4}, "VGK": {"pulls": 1, "exitos": 0, "desastres": 0, "sin_gol": 1},
    "WPG": {"pulls": 1, "exitos": 0, "desastres": 0, "sin_gol": 1}, "WSH": {"pulls": 4, "exitos": 0, "desastres": 1, "sin_gol": 3}
}

STATS_6V5 = {}
HISTORIAL_SENALES = [] 
RADAR_ACTIVO = True

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
# 🎨 DISEÑO WEB (HTML)
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
        .controls { display: flex; gap: 15px; align-items: center; }
        .status-badge { background-color: {{ '#10b981' if estado == 'ACTIVO' else '#ef4444' }}; color: white; padding: 5px 15px; border-radius: 20px; font-size: 14px; font-weight: bold; }
        .btn { padding: 8px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 14px; transition: 0.3s; color: white; }
        .btn-pause { background-color: #ef4444; } .btn-pause:hover { background-color: #dc2626; }
        .btn-resume { background-color: #10b981; } .btn-resume:hover { background-color: #059669; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .stat-item { text-align: center; } .stat-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; }
        .stat-value { font-size: 28px; font-weight: bold; color: #111827; margin-top: 5px; }
        .signals-title { font-size: 14px; font-weight: bold; color: #6b7280; text-transform: uppercase; margin-bottom: 15px; letter-spacing: 1px; }
        .card { background: white; border-radius: 12px; padding: 15px 20px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-left: 5px solid #10b981; }
        .card.empty-net { border-left-color: #ef4444; }
        .card-header { display: flex; justify-content: space-between; margin-bottom: 10px; }
        .match-name { font-weight: bold; font-size: 16px; } .match-time { color: #6b7280; font-size: 14px; }
        .signal-detail { font-size: 14px; color: #4b5563; margin-bottom: 5px; } .signal-highlight { font-weight: bold; color: #111827; }
    </style>
    {% if estado == 'ACTIVO' %}<meta http-equiv="refresh" content="10">{% endif %}
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏒 Radar NHL</h1>
            <div class="controls">
                <div class="status-badge">{{ estado }}</div>
                <form action="/toggle" method="POST" style="margin:0;">
                    {% if estado == 'ACTIVO' %}<button type="submit" class="btn btn-pause">⏸ Pausar</button>
                    {% else %}<button type="submit" class="btn btn-resume">▶ Reanudar</button>{% endif %}
                </form>
            </div>
        </div>
        <div class="stats-grid">
            <div class="stat-item"><div class="stat-label">Señales Hoy</div><div class="stat-value">{{ historial|length }}</div></div>
            <div class="stat-item"><div class="stat-label">Porteros Quitados</div><div class="stat-value">{{ historial|selectattr('tipo', 'equalto', 'Portero Quitado')|list|length }}</div></div>
            <div class="stat-item"><div class="stat-label">Goles Red Vacía</div><div class="stat-value">{{ historial|selectattr('tipo', 'equalto', 'Gol Red Vacía')|list|length }}</div></div>
            <div class="stat-item"><div class="stat-label">Último Escaneo</div><div class="stat-value" style="font-size: 16px; padding-top: 8px;">{{ ultimo_scan }}</div></div>
        </div>
        <div class="signals-title">Señales Recientes</div>
        {% if historial %}
            {% for senal in historial %}
            <div class="card {{ 'empty-net' if senal.tipo == 'Gol Red Vacía' else '' }}">
                <div class="card-header">
                    <div class="match-name">{{ senal.partido }}</div><div class="match-time">P{{ senal.periodo }} - {{ senal.tiempo }}</div>
                </div>
                <div class="signal-detail">
                    <span class="signal-highlight">{{ senal.tipo|upper }}</span> 
                    {% if senal.tipo == 'Portero Quitado' %}| Ataca: <strong>{{ senal.equipo }}</strong>
                    {% else %}| Anotador: <strong>{{ senal.equipo }}</strong>{% endif %}
                </div>
                {% if senal.tipo == 'Portero Quitado' %}
                <div class="signal-detail" style="font-size: 12px; color: #6b7280;">
                    Historial: {{ senal.pct_exito }}% Éxito | {{ senal.pct_desastre }}% Desastre
                </div>
                {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <div class="card" style="text-align: center; color: #6b7280; border-left-color: #cbd5e1;">No hay señales recientes. Esperando acción en el hielo...</div>
        {% endif %}
    </div>
</body>
</html>
"""

app = Flask(__name__)

@app.route('/')
def home():
    ultimo_scan = datetime.now().strftime('%H:%M:%S') if RADAR_ACTIVO else "Pausado"
    return render_template_string(HTML_TEMPLATE, historial=HISTORIAL_SENALES[::-1][:10], estado="ACTIVO" if RADAR_ACTIVO else "PAUSADO", ultimo_scan=ultimo_scan)

@app.route('/toggle', methods=['POST'])
def toggle():
    global RADAR_ACTIVO
    RADAR_ACTIVO = not RADAR_ACTIVO
    return redirect(url_for('home'))

# ==========================================
# 🧠 RADAR EN VIVO
# ==========================================
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=3)
    except: pass

eventos_alertados = set() 
game_states = {} 

def procesar_partido(juego):
    game_id = juego['id']
    home_team, away_team = juego['homeTeam']['abbrev'], juego['awayTeam']['abbrev']
    
    try:
        pbp_data = requests.get(f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play", timeout=2).json()
        plays = pbp_data.get('plays', [])
        if not plays: return
        
        latest_play = plays[-1]
        latest_sit = latest_play.get('situationCode')
        
        if latest_sit:
            period = latest_play['periodDescriptor']['number']
            if period < 3: return 
                
            if game_id not in game_states: game_states[game_id] = latest_sit
            else:
                prev_sit = game_states[game_id]
                if latest_sit != prev_sit:
                    p_away_g, c_away_g = prev_sit[0], latest_sit[0]
                    p_home_g, c_home_g = prev_sit[3], latest_sit[3]
                    time_str = latest_play['timeInPeriod']
                    
                    # Función auxiliar para calcular porcentajes
                    def get_pcts(equipo):
                        st = STATS_6V5.get(equipo, {'pulls': 1, 'exitos': 0, 'desastres': 0})
                        p = max(1, st['pulls'])
                        return (st['exitos']/p*100), (st['desastres']/p*100)

                    if p_away_g == '1' and c_away_g == '0':
                        pct_e, pct_d = get_pcts(away_team)
                        msg = (f"🚨 *¡PORTERO QUITADO!*\n🏒 *{away_team}* ataca con 6 jugadores.\n"
                               f"⏱️ P{period} - {time_str} | 🆚 {away_team} vs {home_team}\n\n"
                               f"📊 *Historial ({away_team} arriesgando):*\n"
                               f"✅ Anotan: *{pct_e:.1f}%* de las veces\n"
                               f"❌ Reciben: *{pct_d:.1f}%* de las veces")
                        enviar_telegram(msg)
                        HISTORIAL_SENALES.append({'tipo': 'Portero Quitado', 'equipo': away_team, 'partido': f"{away_team} vs {home_team}", 'periodo': period, 'tiempo': time_str, 'pct_exito': round(pct_e, 1), 'pct_desastre': round(pct_d, 1)})
                        
                    elif p_home_g == '1' and c_home_g == '0':
                        pct_e, pct_d = get_pcts(home_team)
                        msg = (f"🚨 *¡PORTERO QUITADO!*\n🏒 *{home_team}* ataca con 6 jugadores.\n"
                               f"⏱️ P{period} - {time_str} | 🆚 {away_team} vs {home_team}\n\n"
                               f"📊 *Historial ({home_team} arriesgando):*\n"
                               f"✅ Anotan: *{pct_e:.1f}%* de las veces\n"
                               f"❌ Reciben: *{pct_d:.1f}%* de las veces")
                        enviar_telegram(msg)
                        HISTORIAL_SENALES.append({'tipo': 'Portero Quitado', 'equipo': home_team, 'partido': f"{away_team} vs {home_team}", 'periodo': period, 'tiempo': time_str, 'pct_exito': round(pct_e, 1), 'pct_desastre': round(pct_d, 1)})
                    game_states[game_id] = latest_sit

        # Alertas de Gol
        for play in plays[-5:]:
            play_id = play['eventId']
            if play_id in eventos_alertados: continue
            if play.get('typeDescKey') == 'goal' and play['periodDescriptor']['number'] >= 3:
                sit = play.get('situationCode')
                if sit:
                    away_g, home_g = sit[0], sit[3]
                    if away_g == '0' or home_g == '0':
                        anotador_id = play['details'].get('eventOwnerTeamId')
                        equipo_gol = away_team if anotador_id == juego['awayTeam']['id'] else home_team
                        msg = (f"⚽ *¡GOL EN RED VACÍA!*\n🏒 Anotador: *{equipo_gol}*\n"
                               f"⏱️ P{play['periodDescriptor']['number']} - {play['timeInPeriod']} | 🆚 {away_team} vs {home_team}")
                        enviar_telegram(msg)
                        HISTORIAL_SENALES.append({'tipo': 'Gol Red Vacía', 'equipo': equipo_gol, 'partido': f"{away_team} vs {home_team}", 'periodo': play['periodDescriptor']['number'], 'tiempo': play['timeInPeriod']})
                    eventos_alertados.add(play_id)
    except: pass

def radar_en_vivo():
    while True:
        if not RADAR_ACTIVO:
            time.sleep(2)
            continue
        try:
            res = requests.get("https://api-web.nhle.com/v1/scoreboard/now", timeout=3).json()
            partidos = [j for d in res.get('gamesByDate', []) for j in d.get('games', []) if j.get('gameState') in ['LIVE', 'CRIT']]
            if partidos:
                with ThreadPoolExecutor(max_workers=len(partidos)) as executor:
                    executor.map(procesar_partido, partidos)
        except: pass
        time.sleep(3)

# ==========================================
# ⏰ ACTUALIZADOR DIARIO (Misma lógica de Pulls)
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
                                if eq not in STATS_6V5: STATS_6V5[eq] = {'pulls': 0, 'exitos': 0, 'desastres': 0, 'sin_gol': 0}
                            
                            active_ht_pull, active_at_pull = None, None
                            
                            def cerrar(eq, p_data):
                                if p_data is not None:
                                    STATS_6V5[eq]['pulls'] += 1
                                    if p_data['gf'] > 0 and p_data['gc'] == 0: STATS_6V5[eq]['exitos'] += 1
                                    elif p_data['gc'] > 0 and p_data['gf'] == 0: STATS_6V5[eq]['desastres'] += 1
                                    elif p_data['gf'] == 0 and p_data['gc'] == 0: STATS_6V5[eq]['sin_gol'] += 1

                            for play in pbp['plays']:
                                if play.get('periodDescriptor', {}).get('number', 1) < 3: continue
                                sit = play.get('situationCode')
                                if not sit: continue
                                
                                ag, hg = sit[0], sit[3]
                                if hg == '0' and active_ht_pull is None: active_ht_pull = {'gf': 0, 'gc': 0}
                                elif hg != '0' and active_ht_pull is not None: cerrar(ht, active_ht_pull); active_ht_pull = None
                                
                                if ag == '0' and active_at_pull is None: active_at_pull = {'gf': 0, 'gc': 0}
                                elif ag != '0' and active_at_pull is not None: cerrar(at, active_at_pull); active_at_pull = None
                                
                                if play.get('typeDescKey') == 'goal':
                                    anotador = play['details'].get('eventOwnerTeamId')
                                    if active_ht_pull is not None:
                                        if anotador == hid: active_ht_pull['gf'] += 1
                                        elif anotador == aid: active_ht_pull['gc'] += 1
                                    if active_at_pull is not None:
                                        if anotador == aid: active_at_pull['gf'] += 1
                                        elif anotador == hid: active_at_pull['gc'] += 1
                            
                            if active_ht_pull is not None: cerrar(ht, active_ht_pull)
                            if active_at_pull is not None: cerrar(at, active_at_pull)

                with open('stats_6v5.json', 'w') as archivo: json.dump(STATS_6V5, archivo, indent=4)
                ultimo_dia = hoy
            except: pass
        time.sleep(3600)

if __name__ == "__main__":
    cargar_json()
    threading.Thread(target=radar_en_vivo, daemon=True).start()
    threading.Thread(target=actualizador_diario, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
