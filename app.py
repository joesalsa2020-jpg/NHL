import os
import requests
import time
import json
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from flask import Flask

# ==========================================
# ⚙️ CONFIGURACIÓN DE SEGURIDAD
# ==========================================
# En Render se configurarán como Variables de Entorno. 
# En tu PC, puedes cambiarlas aquí para probar.
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TU_TOKEN_AQUI")
CHAT_ID = os.environ.get("CHAT_ID", "TU_CHAT_ID_AQUI")

# Variable global para las estadísticas
STATS_6V5 = {}

# Cargar la base de datos JSON al arrancar
def cargar_json():
    global STATS_6V5
    try:
        with open('stats_6v5.json', 'r') as archivo:
            STATS_6V5 = json.load(archivo)
            print("✅ Base de datos JSON cargada correctamente.")
    except Exception as e:
        print("⚠️ No se encontró stats_6v5.json, iniciando con base de datos vacía.")
        STATS_6V5 = {}

# ==========================================
# 🚀 SERVIDOR WEB (Para mantener Render despierto)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "📡 Radar de Portero Extra ACTIVO 24/7"

# ==========================================
# 🧠 LÓGICA DEL RADAR EN VIVO
# ==========================================
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=3)
    except Exception as e:
        print("Error enviando a Telegram:", e)

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
    
    # --- 1. TRANSICIONES (Portero Quitado) ---
    if latest_sit:
        period = latest_play['periodDescriptor']['number']
        
        # FILTRO: Solo 3er Periodo (3) o Prórroga (4, 5)
        if period < 3:
            return 
            
        if game_id not in game_states:
            game_states[game_id] = latest_sit
        else:
            prev_sit = game_states[game_id]
            
            if latest_sit != prev_sit:
                p_away_g, c_away_g = prev_sit[0], latest_sit[0]
                p_home_g, c_home_g = prev_sit[3], latest_sit[3]
                time_str = latest_play['timeInPeriod']
                
                if p_away_g == '1' and c_away_g == '0':
                    stats_away = STATS_6V5.get(away_team, {'gf': 0, 'gc': 0})
                    total = stats_away['gf'] + stats_away['gc']
                    pct_gf = (stats_away['gf'] / total * 100) if total > 0 else 0
                    pct_gc = (stats_away['gc'] / total * 100) if total > 0 else 0
                    
                    msg = (f"🚨 *¡PORTERO QUITADO!*\n"
                           f"🏒 *{away_team}* ataca con 6 jugadores.\n"
                           f"⏱️ P{period} - {time_str} | 🆚 {away_team} vs {home_team}\n\n"
                           f"📊 *Stats ({away_team} atacando):*\n"
                           f"⚔️ Si hay gol, *{pct_gf:.1f}%* es de {away_team}.\n"
                           f"🥅 Si hay gol, *{pct_gc:.1f}%* es en red vacía (anota {home_team}).")
                    enviar_telegram(msg)
                    
                elif p_home_g == '1' and c_home_g == '0':
                    stats_home = STATS_6V5.get(home_team, {'gf': 0, 'gc': 0})
                    total = stats_home['gf'] + stats_home['gc']
                    pct_gf = (stats_home['gf'] / total * 100) if total > 0 else 0
                    pct_gc = (stats_home['gc'] / total * 100) if total > 0 else 0
                    
                    msg = (f"🚨 *¡PORTERO QUITADO!*\n"
                           f"🏒 *{home_team}* ataca con 6 jugadores.\n"
                           f"⏱️ P{period} - {time_str} | 🆚 {away_team} vs {home_team}\n\n"
                           f"📊 *Stats ({home_team} atacando):*\n"
                           f"⚔️ Si hay gol, *{pct_gf:.1f}%* es de {home_team}.\n"
                           f"🥅 Si hay gol, *{pct_gc:.1f}%* es en red vacía (anota {away_team}).")
                    enviar_telegram(msg)
                
                game_states[game_id] = latest_sit

    # --- 2. GOLES EN RED VACÍA ---
    for play in plays[-5:]:
        play_id = play['eventId']
        if play_id in eventos_alertados:
            continue
            
        tipo = play.get('typeDescKey', '')
        period = play['periodDescriptor']['number']
        
        if tipo == 'goal' and period >= 3:
            sit = play.get('situationCode')
            anotador_id = play['details'].get('eventOwnerTeamId')
            
            if sit:
                away_g, home_g = sit[0], sit[3]
                if away_g == '0' or home_g == '0':
                    equipo_gol = away_team if anotador_id == away_id else home_team
                    time_str = play['timeInPeriod']
                    msg = (f"⚽ *¡GOL EN RED VACÍA!*\n"
                           f"🏒 Anotador: *{equipo_gol}*\n"
                           f"⏱️ P{period} - {time_str} | 🆚 {away_team} vs {home_team}")
                    enviar_telegram(msg)
                eventos_alertados.add(play_id)

def radar_en_vivo():
    print("📡 RADAR INICIADO EN SEGUNDO PLANO...")
    while True:
        url_live = "https://api-web.nhle.com/v1/scoreboard/now"
        try:
            res = requests.get(url_live, timeout=3).json()
        except:
            time.sleep(3)
            continue

        partidos_en_vivo = []
        for dia in res.get('gamesByDate', []):
            for juego in dia.get('games', []):
                if juego.get('gameState') in ['LIVE', 'CRIT']:
                    partidos_en_vivo.append(juego)

        if partidos_en_vivo:
            with ThreadPoolExecutor(max_workers=len(partidos_en_vivo)) as executor:
                executor.map(procesar_partido, partidos_en_vivo)

        time.sleep(3)

# ==========================================
# 🧠 LÓGICA DEL ACTUALIZADOR AUTOMÁTICO
# ==========================================
def actualizador_diario():
    print("⏰ ACTUALIZADOR DIARIO INICIADO...")
    ultimo_dia_actualizado = ""
    
    while True:
        hoy = datetime.now().strftime("%Y-%m-%d")
        
        # Si cambiamos de día (ej. pasó la medianoche), actualizamos
        if hoy != ultimo_dia_actualizado:
            print(f"🔄 Nuevo día detectado ({hoy}). Actualizando base de datos de ayer...")
            
            ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            url_schedule = f"https://api-web.nhle.com/v1/schedule/{ayer}"
            
            try:
                data = requests.get(url_schedule, timeout=5).json()
                for dia in data.get('gameWeek', []):
                    if dia['date'] == ayer:
                        for juego in dia.get('games', []):
                            if juego.get('gameState') not in ['FINAL', 'OFF']: continue
                            
                            pbp_url = f"https://api-web.nhle.com/v1/gamecenter/{juego['id']}/play-by-play"
                            pbp = requests.get(pbp_url, timeout=5).json()
                            
                            if 'plays' not in pbp: continue
                            
                            home_team = pbp['homeTeam']['abbrev']
                            away_team = pbp['awayTeam']['abbrev']
                            home_id = pbp['homeTeam']['id']
                            away_id = pbp['awayTeam']['id']
                            
                            for eq in [home_team, away_team]:
                                if eq not in STATS_6V5:
                                    STATS_6V5[eq] = {'gf': 0, 'gc': 0}
                                    
                            for play in pbp['plays']:
                                if play.get('periodDescriptor', {}).get('number', 1) < 3: continue
                                if play.get('typeDescKey') == 'goal':
                                    sit = play.get('situationCode')
                                    anotador_id = play['details'].get('eventOwnerTeamId')
                                    if sit:
                                        away_g, home_g = sit[0], sit[3]
                                        if home_g == '0' and anotador_id == away_id:
                                            STATS_6V5[away_team]['gf'] += 1
                                            STATS_6V5[home_team]['gc'] += 1
                                        elif away_g == '0' and anotador_id == home_id:
                                            STATS_6V5[home_team]['gf'] += 1
                                            STATS_6V5[away_team]['gc'] += 1
                                            
                # Guardar el archivo actualizado
                with open('stats_6v5.json', 'w') as archivo:
                    json.dump(STATS_6V5, archivo, indent=4)
                    
                print(f"✅ Base de datos actualizada con los partidos del {ayer}.")
                ultimo_dia_actualizado = hoy
                
            except Exception as e:
                print(f"❌ Error en actualizador diario: {e}")
                
        time.sleep(3600) # Revisar cada 1 hora si cambió el día

# ==========================================
# ▶️ EJECUCIÓN PRINCIPAL
# ==========================================
if __name__ == "__main__":
    cargar_json() # Cargar stats antes de arrancar
    
    # 1. Arrancar Radar en un hilo
    hilo_radar = threading.Thread(target=radar_en_vivo, daemon=True)
    hilo_radar.start()
    
    # 2. Arrancar Actualizador en otro hilo
    hilo_actualizador = threading.Thread(target=actualizador_diario, daemon=True)
    hilo_actualizador.start()
    
    # 3. Arrancar Flask (Servidor Web)
    puerto = int(os.environ.get("PORT", 10000))
    print(f"🌐 Servidor Web escuchando en el puerto {puerto}...")
    app.run(host="0.0.0.0", port=puerto)
