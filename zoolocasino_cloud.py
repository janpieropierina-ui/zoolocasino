#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v6.0 - FIX COMPLETO
"""

import os
import sys
import json
import csv
import io
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template_string, request, session, redirect, jsonify, Response
from collections import defaultdict

# ==================== CONFIGURACION ====================
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://iuwgbtmhkqnqulwgcgkk.supabase.co').strip()
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml1d2didG1oa3FucXVsd2djZ2trIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEwMTM0OTQsImV4cCI6MjA4NjU4OTQ5NH0.HJGQk5JppC34OHWhQY9Goou617uxB1QVuIQLD72NLgE').strip()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'zoolo_casino_cloud_2025_seguro')

# Configuracion de negocio
PAGO_ANIMAL_NORMAL = 35      
PAGO_LECHUZA = 70           
PAGO_ESPECIAL = 2           
COMISION_AGENCIA = 0.15
MINUTOS_BLOQUEO = 5
HORAS_EDICION_RESULTADO = 2

# Horarios
HORARIOS_PERU = [
    "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
    "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM",
    "05:00 PM", "06:00 PM", "07:00 PM"
]

HORARIOS_VENEZUELA = [
    "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM",
    "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM",
    "06:00 PM", "07:00 PM", "08:00 PM"
]

# 42 Animales
ANIMALES = {
    "00": "Ballena", "0": "Delfin", "1": "Carnero", "2": "Toro",
    "3": "Ciempies", "4": "Alacran", "5": "Leon", "6": "Rana",
    "7": "Perico", "8": "Raton", "9": "Aguila", "10": "Tigre",
    "11": "Gato", "12": "Caballo", "13": "Mono", "14": "Paloma",
    "15": "Zorro", "16": "Oso", "17": "Pavo", "18": "Burro",
    "19": "Chivo", "20": "Cochino", "21": "Gallo", "22": "Camello",
    "23": "Cebra", "24": "Iguana", "25": "Gallina", "26": "Vaca",
    "27": "Perro", "28": "Zamuro", "29": "Elefante", "30": "Caiman",
    "31": "Lapa", "32": "Ardilla", "33": "Pescado", "34": "Venado",
    "35": "Jirafa", "36": "Culebra", "37": "Aviapa", "38": "Conejo",
    "39": "Tortuga", "40": "Lechuza"
}

ROJOS = ["1", "3", "5", "7", "9", "12", "14", "16", "18", "19", 
         "21", "23", "25", "27", "30", "32", "34", "36", "37", "39"]

# ==================== FUNCIONES ZONA HORARIA ====================
def ahora_peru():
    return datetime.utcnow() - timedelta(hours=5)

def fecha_peru_actual():
    return ahora_peru().strftime("%d/%m/%Y")

def hora_actual_peru_minutos():
    ahora = ahora_peru()
    return ahora.hour * 60 + ahora.minute

def parse_fecha_ticket(fecha_str):
    formatos = ["%d/%m/%Y %I:%M %p", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
    for fmt in formatos:
        try:
            return datetime.strptime(fecha_str, fmt)
        except:
            continue
    return None

def fecha_iso_a_peru(fecha_iso):
    try:
        return datetime.strptime(fecha_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return fecha_peru_actual()

def get_color(num):
    if num in ["0", "00"]: return "#27ae60"
    if num in ROJOS: return "#c0392b"
    return "#2c3e50"

def generar_serial():
    return str(int(ahora_peru().timestamp() * 1000))

def verificar_horario_bloqueo(hora_sorteo):
    minutos_sorteo = hora_a_minutos(hora_sorteo)
    actual_minutos = hora_actual_peru_minutos()
    return (minutos_sorteo - actual_minutos) > MINUTOS_BLOQUEO

def calcular_premio_animal(monto_apostado, numero_animal):
    return monto_apostado * PAGO_LECHUZA if str(numero_animal) == "40" else monto_apostado * PAGO_ANIMAL_NORMAL

def hora_a_minutos(hora_str):
    try:
        partes = hora_str.replace(':', ' ').split()
        hora = int(partes[0])
        minuto = int(partes[1])
        ampm = partes[2]
        if ampm == 'PM' and hora != 12: hora += 12
        elif ampm == 'AM' and hora == 12: hora = 0
        return hora * 60 + minuto
    except:
        return 0

def puede_editar_resultado(hora_sorteo, fecha_str=None):
    ahora = ahora_peru()
    hoy_peru = ahora.strftime("%d/%m/%Y")
    if fecha_str and fecha_str != hoy_peru: return False
    minutos_sorteo = hora_a_minutos(hora_sorteo)
    minutos_actual = ahora.hour * 60 + ahora.minute
    return minutos_actual <= (minutos_sorteo + (HORAS_EDICION_RESULTADO * 60))

def supabase_request(table, method="GET", data=None, filters=None, timeout=30):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if filters:
        filter_params = []
        for k, v in filters.items():
            if k.endswith('__like'): filter_params.append(f"{k.replace('__like', '')}=like.{urllib.parse.quote(str(v))}")
            elif k.endswith('__gte'): filter_params.append(f"{k.replace('__gte', '')}=gte.{urllib.parse.quote(str(v))}")
            elif k.endswith('__lte'): filter_params.append(f"{k.replace('__lte', '')}=lte.{urllib.parse.quote(str(v))}")
            else: filter_params.append(f"{k}=eq.{urllib.parse.quote(str(v))}")
        url += "?" + "&".join(filter_params)
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        if method == "GET":
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        elif method == "POST":
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        elif method == "PATCH":
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="PATCH")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return True if response.status in [200, 201, 204] else False
            except urllib.error.HTTPError as e:
                return False if e.code == 404 else None
    except Exception as e:
        print(f"[ERROR] Supabase: {e}")
        return None

# ==================== DECORADORES ====================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or not session.get('es_admin'): return "No autorizado", 403
        return f(*args, **kwargs)
    return decorated

def agencia_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return jsonify({'error': 'Login requerido'}), 403
        if session.get('es_admin'): return jsonify({'error': 'Admin no puede vender'}), 403
        return f(*args, **kwargs)
    return decorated

# ==================== RUTAS ====================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/admin' if session.get('es_admin') else '/pos')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ""
    if request.method == 'POST':
        u = request.form.get('usuario', '').strip().lower()
        p = request.form.get('password', '').strip()
        try:
            users = supabase_request("agencias", filters={"usuario": u, "password": p, "activa": "true"})
            if users and len(users) > 0:
                user = users[0]
                session['user_id'] = user['id']
                session['nombre_agencia'] = user['nombre_agencia']
                session['es_admin'] = user['es_admin']
                return redirect('/')
            else: error = "Usuario o clave incorrecta"
        except Exception as e: error = f"Error de conexión: {str(e)}"
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/pos')
@login_required
def pos():
    if session.get('es_admin'): return redirect('/admin')
    return render_template_string(POS_HTML, agencia=session['nombre_agencia'], animales=ANIMALES,
        horarios_peru=HORARIOS_PERU, horarios_venezuela=HORARIOS_VENEZUELA, get_color=get_color)

@app.route('/admin')
@admin_required
def admin():
    return render_template_string(ADMIN_HTML, animales=ANIMALES, horarios=HORARIOS_PERU)

# ==================== API POS (Simplificada) ====================
@app.route('/api/resultados-hoy')
@login_required
def resultados_hoy():
    try:
        hoy = fecha_peru_actual()
        resultados_list = supabase_request("resultados", filters={"fecha": hoy})
        resultados_dict = {r['hora']: {'animal': r['animal'], 'nombre': ANIMALES.get(r['animal'], 'Desconocido')} for r in resultados_list} if resultados_list else {}
        for hora in HORARIOS_PERU:
            if hora not in resultados_dict: resultados_dict[hora] = None
        return jsonify({'status': 'ok', 'fecha': hoy, 'resultados': resultados_dict})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/procesar-venta', methods=['POST'])
@agencia_required
def procesar_venta():
    try:
        data = request.get_json()
        jugadas = data.get('jugadas', [])
        if not jugadas: return jsonify({'error': 'Ticket vacio'}), 400
        
        for j in jugadas:
            if not verificar_horario_bloqueo(j['hora']): return jsonify({'error': f"El sorteo {j['hora']} ya cerro"}), 400
        
        serial = generar_serial()
        fecha = ahora_peru().strftime("%d/%m/%Y %I:%M %p")
        total = sum(j['monto'] for j in jugadas)
        
        ticket_data = {"serial": serial, "agencia_id": session['user_id'], "fecha": fecha, "total": total, "pagado": False, "anulado": False}
        result = supabase_request("tickets", method="POST", data=ticket_data)
        if not result: return jsonify({'error': 'Error al crear ticket'}), 500
        
        ticket_id = result[0]['id']
        for j in jugadas:
            jugada_data = {"ticket_id": ticket_id, "hora": j['hora'], "seleccion": j['seleccion'], "monto": j['monto'], "tipo": j['tipo']}
            supabase_request("jugadas", method="POST", data=jugada_data)
        
        # Generar mensaje WhatsApp
        jugadas_por_hora = defaultdict(list)
        for j in jugadas: jugadas_por_hora[j['hora']].append(j)
        
        lineas = [f"*{session['nombre_agencia']}*", f"*TICKET:* #{ticket_id}", f"*SERIAL:* {serial}", fecha, "------------------------", ""]
        
        for hora_peru in HORARIOS_PERU:
            if hora_peru not in jugadas_por_hora: continue
            idx = HORARIOS_PERU.index(hora_peru)
            hora_ven = HORARIOS_VENEZUELA[idx]
            hora_peru_corta = hora_peru.replace(' ', '').replace('00', '').lower()
            hora_ven_corta = hora_ven.replace(' ', '').replace('00', '').lower()
            lineas.append(f"*ZOOLO.PERU/{hora_peru_corta}...VZLA/{hora_ven_corta}*")
            
            jugadas_hora = jugadas_por_hora[hora_peru]
            texto_jugadas = []
            for j in jugadas_hora:
                if j['tipo'] == 'animal':
                    nombre_corto = ANIMALES.get(j['seleccion'], '')[0:3].upper()
                    texto_jugadas.append(f"{nombre_corto}{j['seleccion']}x{int(j['monto'])}")
                else: texto_jugadas.append(f"{j['seleccion'][0:3]}x{int(j['monto'])}")
            lineas.append(" ".join(texto_jugadas))
            lineas.append("")
        
        lineas.extend(["------------------------", f"*TOTAL: S/{int(total)}*", "", "Buena Suerte! 🍀", "El ticket vence a los 3 dias"])
        url_whatsapp = f"https://wa.me/?text={urllib.parse.quote(chr(10).join(lineas))}"
        
        return jsonify({'status': 'ok', 'serial': serial, 'ticket_id': ticket_id, 'total': total, 'url_whatsapp': url_whatsapp})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/anular-ticket', methods=['POST'])
@login_required
def anular_ticket():
    try:
        serial = request.json.get('serial')
        tickets = supabase_request("tickets", filters={"serial": serial})
        if not tickets: return jsonify({'error': 'Ticket no existe'})
        ticket = tickets[0]
        if ticket['pagado']: return jsonify({'error': 'Ya esta pagado, no se puede anular'})
        if ticket['anulado']: return jsonify({'error': 'Ya esta anulado'})
        
        # Verificar tiempo
        if not session.get('es_admin'):
            fecha_ticket = parse_fecha_ticket(ticket['fecha'])
            if fecha_ticket:
                minutos_transcurridos = (ahora_peru() - fecha_ticket).total_seconds() / 60
                if minutos_transcurridos > 5: return jsonify({'error': 'Solo puede anular dentro de 5 minutos'})
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?id=eq.{urllib.parse.quote(str(ticket['id']))}"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
        req = urllib.request.Request(url, data=json.dumps({"anulado": True}).encode(), headers=headers, method="PATCH")
        urllib.request.urlopen(req, timeout=15)
        return jsonify({'status': 'ok', 'mensaje': 'Ticket anulado correctamente'})
    except Exception as e: return jsonify({'error': str(e)}), 500

# ==================== TEMPLATES HTML ====================
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%); color: white; font-family: Arial, sans-serif; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .login-box { background: rgba(255,255,255,0.05); padding: 40px; border-radius: 20px; border: 2px solid #ffd700; width: 100%; max-width: 400px; text-align: center; }
        .login-box h2 { color: #ffd700; margin-bottom: 30px; font-size: 1.8rem; }
        .form-group { margin-bottom: 20px; text-align: left; }
        .form-group label { display: block; margin-bottom: 8px; color: #aaa; font-size: 0.9rem; }
        .form-group input { width: 100%; padding: 15px; border: 1px solid #444; border-radius: 10px; background: rgba(0,0,0,0.5); color: white; font-size: 1rem; }
        .btn-login { width: 100%; padding: 16px; background: linear-gradient(45deg, #ffd700, #ffed4e); color: black; border: none; border-radius: 10px; font-size: 1.1rem; font-weight: bold; cursor: pointer; margin-top: 10px; }
        .error { background: rgba(255,0,0,0.2); color: #ff6b6b; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🦁 ZOOLO CASINO</h2>
        {% if error %}<div class="error">{{error}}</div>{% endif %}
        <form method="POST">
            <div class="form-group">
                <label>Usuario</label>
                <input type="text" name="usuario" required autofocus>
            </div>
            <div class="form-group">
                <label>Contraseña</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="btn-login">INICIAR SESIÓN</button>
        </form>
    </div>
</body>
</html>
"""

POS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
    <title>POS - {{agencia}}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0a0a0a; color: white; font-family: Arial, sans-serif; min-height: 100vh; display: flex; flex-direction: column; }
        .header { background: linear-gradient(90deg, #1a1a2e, #16213e); padding: 10px 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #ffd700; }
        .header h3 { color: #ffd700; font-size: 1rem; }
        .monto-box { display: flex; align-items: center; gap: 8px; background: rgba(0,0,0,0.3); padding: 6px 12px; border-radius: 20px; }
        .monto-box span { font-size: 0.8rem; font-weight: bold; color: #ffd700; }
        .monto-box input { width: 60px; padding: 6px; border: 2px solid #ffd700; border-radius: 6px; background: #000; color: #ffd700; text-align: center; font-weight: bold; }
        .main-container { display: flex; flex-direction: column; flex: 1; height: calc(100vh - 60px); overflow: hidden; }
        @media (min-width: 1024px) { .main-container { flex-direction: row; } }
        .left-panel { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
        .special-btns { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; padding: 10px; background: #111; }
        .btn-esp { padding: 12px 4px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; color: white; font-size: 0.8rem; min-height: 44px; }
        .btn-rojo { background: linear-gradient(135deg, #c0392b, #e74c3c); }
        .btn-negro { background: linear-gradient(135deg, #2c3e50, #34495e); }
        .btn-par { background: linear-gradient(135deg, #2980b9, #3498db); }
        .btn-impar { background: linear-gradient(135deg, #8e44ad, #9b59b6); }
        .btn-esp.active { box-shadow: 0 0 15px rgba(255,255,255,0.5); border: 2px solid white; }
        .animals-grid { flex: 1; display: grid; grid-template-columns: repeat(auto-fill, minmax(70px, 1fr)); gap: 5px; padding: 10px; overflow-y: auto; }
        @media (min-width: 768px) { .animals-grid { grid-template-columns: repeat(7, 1fr); } }
        .animal-card { background: linear-gradient(135deg, #1a1a2e, #16213e); border: 2px solid; border-radius: 10px; padding: 10px 2px; text-align: center; cursor: pointer; min-height: 70px; display: flex; flex-direction: column; justify-content: center; user-select: none; }
        .animal-card.active { box-shadow: 0 0 15px rgba(255,215,0,0.6); border-color: #ffd700 !important; background: linear-gradient(135deg, #2a2a4e, #1a1a3e); transform: scale(1.05); z-index: 10; }
        .animal-card .num { font-size: 1.2rem; font-weight: bold; }
        .animal-card .name { font-size: 0.7rem; color: #aaa; margin-top: 4px; }
        .right-panel { background: #111; border-top: 2px solid #333; display: flex; flex-direction: column; height: 45vh; }
        @media (min-width: 1024px) { .right-panel { width: 380px; height: auto; border-left: 2px solid #333; border-top: none; } }
        .horarios { display: flex; gap: 6px; padding: 10px; overflow-x: auto; flex-shrink: 0; background: #0a0a0a; }
        .btn-hora { flex: 0 0 auto; min-width: 85px; padding: 10px 6px; background: #222; border: 1px solid #444; border-radius: 8px; color: #ccc; cursor: pointer; font-size: 0.75rem; text-align: center; }
        .btn-hora.active { background: linear-gradient(135deg, #27ae60, #229954); color: white; font-weight: bold; border-color: #27ae60; }
        .btn-hora.expired { background: #300; color: #666; text-decoration: line-through; pointer-events: none; opacity: 0.5; }
        .ticket-display { flex: 1; background: #000; margin: 0 10px 10px; border-radius: 10px; padding: 12px; border: 1px solid #333; overflow-y: auto; font-size: 0.85rem; }
        .ticket-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
        .ticket-table th { background: #1a1a2e; color: #ffd700; padding: 8px; text-align: left; position: sticky; top: 0; }
        .ticket-table td { padding: 8px; border-bottom: 1px solid #222; }
        .ticket-total { margin-top: 12px; padding-top: 12px; border-top: 2px solid #ffd700; text-align: right; font-size: 1.2rem; font-weight: bold; color: #ffd700; }
        .action-btns { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; padding: 10px; background: #0a0a0a; flex-shrink: 0; }
        .action-btns button { padding: 14px 5px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 0.75rem; min-height: 48px; color: white; }
        .btn-agregar { background: linear-gradient(135deg, #27ae60, #229954); grid-column: span 4; font-size: 1.1rem; }
        .btn-vender { background: linear-gradient(135deg, #2980b9, #2573a7); grid-column: span 2; font-size: 0.9rem; }
        .btn-caja { background: #16a085; }
        .btn-pagar { background: #8e44ad; }
        .btn-anular { background: #c0392b; }
        .btn-salir { background: #333; grid-column: span 2; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 1000; overflow-y: auto; }
        .modal-content { background: #1a1a2e; margin: 10px; padding: 20px; border-radius: 15px; border: 2px solid #ffd700; max-width: 600px; margin-left: auto; margin-right: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333; }
        .modal h3 { color: #ffd700; font-size: 1.3rem; }
        .btn-close { background: #c0392b; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; color: #888; font-size: 0.9rem; margin-bottom: 6px; }
        .form-group input, .form-group select { width: 100%; padding: 12px; background: #000; border: 1px solid #444; color: white; border-radius: 8px; font-size: 1rem; }
        .btn-consultar { background: linear-gradient(135deg, #27ae60, #229954); color: white; border: none; padding: 14px; width: 100%; border-radius: 8px; font-weight: bold; cursor: pointer; margin-top: 10px; font-size: 1rem; }
        .toast { position: fixed; top: 80px; left: 50%; transform: translateX(-50%); padding: 14px 24px; border-radius: 30px; font-size: 0.95rem; z-index: 10000; box-shadow: 0 6px 20px rgba(0,0,0,0.5); max-width: 90%; text-align: center; font-weight: bold; background: #2980b9; color: white; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h3>{{agencia}}</h3>
            <small id="reloj" style="color:#888;">--:--</small>
        </div>
        <div class="monto-box">
            <span>S/:</span>
            <input type="number" id="monto" value="5" min="1">
        </div>
    </div>
    
    <div class="main-container">
        <div class="left-panel">
            <div class="special-btns">
                <button class="btn-esp btn-rojo" onclick="toggleEsp('ROJO')">ROJO</button>
                <button class="btn-esp btn-negro" onclick="toggleEsp('NEGRO')">NEGRO</button>
                <button class="btn-esp btn-par" onclick="toggleEsp('PAR')">PAR</button>
                <button class="btn-esp btn-impar" onclick="toggleEsp('IMPAR')">IMPAR</button>
            </div>
            <div class="animals-grid" id="animals-grid">
                {% for k, v in animales.items() %}
                <div class="animal-card" id="ani-{{k}}" style="border-color: {{get_color(k)}}" onclick="toggleAni('{{k}}', '{{v}}')">
                    <div class="num">{{k}}</div>
                    <div class="name">{{v}}</div>
                </div>
                {% endfor %}
            </div>
        </div>
        <div class="right-panel">
            <div class="horarios" id="horarios">
                {% for h in horarios_peru %}
                <div class="btn-hora" id="hora-{{loop.index}}" onclick="toggleHora('{{h}}', '{{loop.index}}')">
                    {{h}}<br><small>{{horarios_venezuela[loop.index0]}}</small>
                </div>
                {% endfor %}
            </div>
            <div class="ticket-display" id="ticket-display">
                <div style="text-align:center; color:#666; padding:20px;">Selecciona animales y horarios...</div>
            </div>
            <div class="action-btns">
                <button class="btn-agregar" onclick="agregar()">AGREGAR AL TICKET</button>
                <button class="btn-vender" onclick="vender()">ENVIAR POR WHATSAPP</button>
                <button class="btn-caja" onclick="abrirCaja()">CAJA</button>
                <button class="btn-pagar" onclick="pagar()">PAGAR</button>
                <button class="btn-anular" onclick="anular()">ANULAR</button>
                <button class="btn-salir" onclick="location.href='/logout'">SALIR</button>
            </div>
        </div>
    </div>

    <div class="modal" id="modal-caja" onclick="if(event.target==this)cerrarModal('modal-caja')">
        <div class="modal-content">
            <div class="modal-header">
                <h3>ESTADO DE CAJA</h3>
                <button class="btn-close" onclick="cerrarModal('modal-caja')">X</button>
            </div>
            <div style="background: #0a0a0a; padding: 20px; border-radius: 10px; margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #333;">
                    <span style="color: #888;">Ventas:</span>
                    <span id="caja-ventas" style="color: #ffd700; font-weight: bold;">S/0.00</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #333;">
                    <span style="color: #888;">Premios:</span>
                    <span id="caja-premios" style="color: #c0392b; font-weight: bold;">S/0.00</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #333;">
                    <span style="color: #888;">Comisión:</span>
                    <span id="caja-comision" style="color: #ffd700; font-weight: bold;">S/0.00</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 10px 0; margin-top: 10px;">
                    <span style="color: #888; font-size: 1.1rem;">BALANCE:</span>
                    <span id="caja-balance" style="color: #27ae60; font-weight: bold; font-size: 1.2rem;">S/0.00</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        let seleccionados = [], especiales = [], horariosSel = [], carrito = [];
        let horasPeru = {{horarios_peru|tojson}};
        
        function showToast(msg, type='info') {
            const t = document.createElement('div');
            t.className = 'toast';
            t.style.background = type === 'error' ? '#c0392b' : type === 'success' ? '#27ae60' : '#2980b9';
            t.textContent = msg;
            document.body.appendChild(t);
            setTimeout(() => t.remove(), 3000);
        }
        
        function updateReloj() {
            let now = new Date();
            let peruTime = new Date(now.toLocaleString("en-US", {timeZone: "America/Lima"}));
            document.getElementById('reloj').textContent = peruTime.toLocaleString('es-PE', {hour: '2-digit', minute:'2-digit', hour12: true, timeZone: 'America/Lima'});
            
            let horaActual = peruTime.getHours() * 60 + peruTime.getMinutes();
            horasPeru.forEach((h, idx) => {
                let partes = h.split(/[: ]/);
                let hora = parseInt(partes[0]);
                let minuto = parseInt(partes[1]);
                let ampm = partes[2];
                if (ampm === 'PM' && hora !== 12) hora += 12;
                if (ampm === 'AM' && hora === 12) hora = 0;
                let sorteoMinutos = hora * 60 + minuto;
                let btn = document.getElementById('hora-' + (idx + 1));
                if (btn && horaActual > sorteoMinutos - 5) btn.classList.add('expired');
            });
        }
        setInterval(updateReloj, 30000);
        updateReloj();
        
        function toggleAni(k, nombre) {
            let idx = seleccionados.findIndex(a => a.k === k);
            let el = document.getElementById('ani-' + k);
            if (idx >= 0) {
                seleccionados.splice(idx, 1);
                el.classList.remove('active');
            } else {
                seleccionados.push({k, nombre});
                el.classList.add('active');
            }
            updateTicket();
        }
        
        function toggleEsp(tipo) {
            let idx = especiales.indexOf(tipo);
            let el = document.querySelector('.btn-' + tipo.toLowerCase());
            if (idx >= 0) {
                especiales.splice(idx, 1);
                el.classList.remove('active');
            } else {
                especiales.push(tipo);
                el.classList.add('active');
            }
            updateTicket();
        }
        
        function toggleHora(hora, id) {
            let btn = document.getElementById('hora-' + id);
            if (btn.classList.contains('expired')) { showToast('Este sorteo ya cerró', 'error'); return; }
            let idx = horariosSel.indexOf(hora);
            if (idx >= 0) { horariosSel.splice(idx, 1); btn.classList.remove('active'); }
            else { horariosSel.push(hora); btn.classList.add('active'); }
            updateTicket();
        }
        
        function updateTicket() {
            const display = document.getElementById('ticket-display');
            let total = 0;
            let html = '<table class="ticket-table"><thead><tr><th>Hora</th><th>Apuesta</th><th>S/</th></tr></thead><tbody>';
            for (let item of carrito) {
                let nom = item.tipo === 'animal' ? item.nombre.substring(0,10) : item.seleccion;
                let color = item.tipo === 'animal' ? '#ffd700' : '#3498db';
                html += `<tr><td style="color:#aaa; font-size:0.75rem">${item.hora}</td><td style="color:${color}; font-weight:bold; font-size:0.8rem">${item.seleccion} ${nom}</td><td style="text-align:right; font-weight:bold">${item.monto}</td></tr>`;
                total += item.monto;
            }
            if (horariosSel.length > 0 && (seleccionados.length > 0 || especiales.length > 0)) {
                let monto = parseFloat(document.getElementById('monto').value) || 5;
                for (let h of horariosSel) {
                    for (let a of seleccionados) html += `<tr style="opacity:0.7"><td style="color:#ffd700">${h}</td><td style="color:#ffd700">${a.k} ${a.nombre}</td><td style="text-align:right; color:#ffd700">${monto}</td></tr>`;
                    for (let e of especiales) html += `<tr style="opacity:0.7"><td style="color:#3498db">${h}</td><td style="color:#3498db">${e}</td><td style="text-align:right; color:#3498db">${monto}</td></tr>`;
                }
            }
            html += '</tbody></table>';
            if (carrito.length === 0 && (seleccionados.length === 0 && especiales.length === 0)) html = '<div style="text-align:center; color:#666; padding:20px;">Selecciona animales y horarios...</div>';
            if (total > 0) html += `<div class="ticket-total">TOTAL: S/${total}</div>`;
            display.innerHTML = html;
        }
        
        function agregar() {
            if (horariosSel.length === 0 || (seleccionados.length === 0 && especiales.length === 0)) { showToast('Selecciona horario y apuesta', 'error'); return; }
            let monto = parseFloat(document.getElementById('monto').value) || 5;
            for (let h of horariosSel) {
                for (let a of seleccionados) carrito.push({hora: h, seleccion: a.k, nombre: a.nombre, monto: monto, tipo: 'animal'});
                for (let e of especiales) carrito.push({hora: h, seleccion: e, nombre: e, monto: monto, tipo: 'especial'});
            }
            seleccionados = []; especiales = []; horariosSel = [];
            document.querySelectorAll('.animal-card.active, .btn-esp.active, .btn-hora.active').forEach(el => el.classList.remove('active'));
            updateTicket();
            showToast('Jugadas agregadas', 'success');
        }
        
        async function vender() {
            if (carrito.length === 0) { showToast('Carrito vacío', 'error'); return; }
            try {
                let jugadas = carrito.map(c => ({hora: c.hora, seleccion: c.seleccion, monto: c.monto, tipo: c.tipo}));
                const response = await fetch('/api/procesar-venta', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({jugadas: jugadas})});
                const data = await response.json();
                if (data.error) showToast(data.error, 'error');
                else {
                    window.open(data.url_whatsapp, '_blank');
                    carrito = []; updateTicket();
                    showToast('Ticket generado', 'success');
                }
            } catch (e) { showToast('Error de conexión', 'error'); }
        }

        function abrirCaja() {
            fetch('/api/caja').then(r => r.json()).then(d => {
                if (d.error) { showToast(d.error, 'error'); return; }
                document.getElementById('caja-ventas').textContent = 'S/' + d.ventas.toFixed(2);
                document.getElementById('caja-premios').textContent = 'S/' + d.premios.toFixed(2);
                document.getElementById('caja-comision').textContent = 'S/' + d.comision.toFixed(2);
                document.getElementById('caja-balance').textContent = 'S/' + d.balance.toFixed(2);
                document.getElementById('modal-caja').style.display = 'block';
            });
        }
        
        function cerrarModal(id) { document.getElementById(id).style.display = 'none'; }
        
        async function pagar() {
            let serial = prompt('Ingrese SERIAL del ticket:'); if (!serial) return;
            try {
                const response = await fetch('/api/verificar-ticket', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({serial: serial})});
                const d = await response.json();
                if (d.error) { showToast(d.error, 'error'); return; }
                if (d.total_ganado > 0 && confirm(`Ganado: S/${d.total_ganado.toFixed(2)}\\n¿Pagar?`)) {
                    await fetch('/api/pagar-ticket', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ticket_id: d.ticket_id})});
                    showToast('Ticket pagado', 'success');
                } else if (d.total_ganado === 0) showToast('No ganador', 'info');
            } catch (e) { showToast('Error', 'error'); }
        }
        
        async function anular() {
            let serial = prompt('SERIAL a anular:'); if (!serial) return;
            if (!confirm('¿Anular ' + serial + '?')) return;
            try {
                const response = await fetch('/api/anular-ticket', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({serial: serial})});
                const d = await response.json();
                if (d.error) showToast(d.error, 'error');
                else showToast(d.mensaje, 'success');
            } catch (e) { showToast('Error', 'error'); }
        }
    </script>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0a0a0a; color: white; font-family: Arial, sans-serif; }
        .admin-header { background: linear-gradient(90deg, #1a1a2e, #16213e); padding: 15px; border-bottom: 2px solid #ffd700; display: flex; justify-content: space-between; align-items: center; }
        .admin-title { color: #ffd700; font-size: 1.2rem; font-weight: bold; }
        .logout-btn { background: #c0392b; color: white; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .admin-tabs { display: flex; background: #1a1a2e; border-bottom: 1px solid #333; overflow-x: auto; }
        .admin-tab { flex: 1; min-width: 100px; padding: 15px 10px; background: transparent; border: none; color: #888; cursor: pointer; font-size: 0.85rem; border-bottom: 3px solid transparent; }
        .admin-tab.active { color: #ffd700; border-bottom-color: #ffd700; font-weight: bold; }
        .content { padding: 20px; max-width: 1200px; margin: 0 auto; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .form-box { background: #1a1a2e; padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #333; }
        .form-box h3 { color: #ffd700; margin-bottom: 15px; font-size: 1.1rem; }
        .form-row { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
        .form-row input, .form-row select { flex: 1; min-width: 120px; padding: 12px; background: #000; border: 1px solid #444; color: white; border-radius: 8px; font-size: 1rem; }
        .btn-submit { background: linear-gradient(135deg, #27ae60, #229954); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.95rem; }
        .btn-danger { background: linear-gradient(135deg, #c0392b, #e74c3c); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; }
        .btn-csv { background: linear-gradient(135deg, #f39c12, #e67e22); color: black; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; }
        .stat-card { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 12px; border: 1px solid #ffd700; text-align: center; margin-bottom: 10px; }
        .stat-card h3 { color: #888; font-size: 0.75rem; margin-bottom: 8px; text-transform: uppercase; }
        .stat-card p { color: #ffd700; font-size: 1.4rem; font-weight: bold; }
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px; }
        @media (min-width: 768px) { .stats-grid { grid-template-columns: repeat(4, 1fr); } }
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; background: #1a1a2e; border-radius: 8px; overflow: hidden; }
        th, td { padding: 12px 10px; text-align: left; border-bottom: 1px solid #333; }
        th { background: linear-gradient(135deg, #ffd700, #ffed4e); color: black; font-weight: bold; }
        tr:hover { background: rgba(255,215,0,0.05); }
        .riesgo-item { background: #1a1a2e; padding: 15px; margin-bottom: 10px; border-radius: 8px; border-left: 4px solid #c0392b; }
        .riesgo-item b { color: #ffd700; }
        .resultado-item { background: #0a0a0a; padding: 15px; margin: 8px 0; border-radius: 10px; border-left: 4px solid #27ae60; display: flex; justify-content: space-between; align-items: center; }
        .resultado-numero { color: #ffd700; font-weight: bold; font-size: 1.3rem; }
        .mensaje { padding: 15px; margin: 15px 0; border-radius: 8px; display: none; text-align: center; }
        .mensaje.success { background: rgba(39,174,96,0.2); border: 1px solid #27ae60; color: #27ae60; display: block; }
        .mensaje.error { background: rgba(192,57,43,0.2); border: 1px solid #c0392b; color: #c0392b; display: block; }
    </style>
</head>
<body>
    <div class="admin-header">
        <div class="admin-title">👑 PANEL ADMIN</div>
        <button onclick="location.href='/logout'" class="logout-btn">SALIR</button>
    </div>
    <div class="admin-tabs">
        <button class="admin-tab active" onclick="showTab('dashboard')">📊 Dashboard</button>
        <button class="admin-tab" onclick="showTab('resultados')">📋 Resultados</button>
        <button class="admin-tab" onclick="showTab('riesgo')">⚠️ Riesgo</button>
        <button class="admin-tab" onclick="showTab('reporte')">🏢 Reporte</button>
        <button class="admin-tab" onclick="showTab('agencias')">🏪 Agencias</button>
    </div>
    <div class="content">
        <div id="mensaje" class="mensaje"></div>
        
        <div id="dashboard" class="tab-content active">
            <div class="stats-grid">
                <div class="stat-card"><h3>VENTAS</h3><p id="stat-ventas">S/0</p></div>
                <div class="stat-card"><h3>PREMIOS</h3><p id="stat-premios">S/0</p></div>
                <div class="stat-card"><h3>COMISIONES</h3><p id="stat-comisiones">S/0</p></div>
                <div class="stat-card"><h3>BALANCE</h3><p id="stat-balance">S/0</p></div>
            </div>
        </div>

        <div id="resultados" class="tab-content">
            <div class="form-box">
                <h3>Cargar Resultado</h3>
                <div class="form-row">
                    <select id="res-hora">{% for h in horarios %}<option value="{{h}}">{{h}}</option>{% endfor %}</select>
                    <select id="res-animal">{% for k, v in animales.items() %}<option value="{{k}}">{{k}} - {{v}}</option>{% endfor %}</select>
                    <button class="btn-submit" onclick="guardarResultado()">GUARDAR</button>
                </div>
            </div>
            <div id="lista-resultados" style="margin-top: 20px;"></div>
        </div>

        <div id="riesgo" class="tab-content">
            <div class="form-box">
                <h3>Riesgo del Sorteo Actual</h3>
                <div id="lista-riesgo"><p style="color: #888;">Cargando...</p></div>
            </div>
        </div>

        <div id="reporte" class="tab-content">
            <div class="form-box">
                <h3>Reporte por Agencias</h3>
                <div class="form-row">
                    <input type="date" id="reporte-fecha-inicio">
                    <input type="date" id="reporte-fecha-fin">
                    <button class="btn-submit" onclick="consultarReporte()">GENERAR</button>
                    <button class="btn-csv" onclick="exportarCSV()">CSV</button>
                </div>
                <div id="tabla-reporte" style="margin-top: 20px; overflow-x: auto;"></div>
            </div>
        </div>

        <div id="agencias" class="tab-content">
            <div class="form-box">
                <h3>Crear Agencia</h3>
                <div class="form-row">
                    <input type="text" id="new-usuario" placeholder="Usuario">
                    <input type="password" id="new-password" placeholder="Contraseña">
                    <input type="text" id="new-nombre" placeholder="Nombre Agencia">
                    <button class="btn-submit" onclick="crearAgencia()">CREAR</button>
                </div>
            </div>
            <div id="tabla-agencias" style="overflow-x: auto;"></div>
        </div>
    </div>

    <script>
        const HORARIOS_ORDEN = {{horarios|tojson}};
        
        function showTab(tab) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.admin-tab').forEach(b => b.classList.remove('active'));
            document.getElementById(tab).classList.add('active');
            event.target.classList.add('active');
            if (tab === 'dashboard') cargarDashboard();
            if (tab === 'riesgo') cargarRiesgo();
            if (tab === 'agencias') cargarAgencias();
            if (tab === 'resultados') cargarResultados();
        }
        
        function showMensaje(msg, tipo) {
            let div = document.getElementById('mensaje');
            div.textContent = msg;
            div.className = 'mensaje ' + tipo;
            setTimeout(() => div.className = 'mensaje', 4000);
        }
        
        function cargarDashboard() {
            fetch('/admin/reporte-agencias').then(r => r.json()).then(d => {
                if (d.global) {
                    document.getElementById('stat-ventas').textContent = 'S/' + d.global.ventas.toFixed(0);
                    document.getElementById('stat-premios').textContent = 'S/' + d.global.pagos.toFixed(0);
                    document.getElementById('stat-comisiones').textContent = 'S/' + d.global.comisiones.toFixed(0);
                    document.getElementById('stat-balance').textContent = 'S/' + d.global.balance.toFixed(0);
                }
            });
        }
        
        function cargarRiesgo() {
            fetch('/admin/riesgo').then(r => r.json()).then(d => {
                let html = '';
                if (d.riesgo && Object.keys(d.riesgo).length > 0) {
                    for (let [k, v] of Object.entries(d.riesgo)) {
                        html += `<div class="riesgo-item"><b>${k}</b><br>Apostado: S/${v.apostado.toFixed(2)} • Pagaría: S/${v.pagaria.toFixed(2)}</div>`;
                    }
                } else html = '<p style="color: #888;">No hay apuestas registradas</p>';
                document.getElementById('lista-riesgo').innerHTML = html;
            });
        }
        
        function cargarResultados() {
            fetch('/admin/resultados-hoy').then(r => r.json()).then(d => {
                let html = '';
                for (let hora of HORARIOS_ORDEN) {
                    let r = d.resultados[hora];
                    if (r) html += `<div class="resultado-item"><span style="color:#ffd700">${hora}</span><span class="resultado-numero">${r.animal} - ${r.nombre}</span></div>`;
                    else html += `<div class="resultado-item" style="border-left-color:#666; opacity:0.7;"><span style="color:#ffd700">${hora}</span><span style="color:#666">Pendiente</span></div>`;
                }
                document.getElementById('lista-resultados').innerHTML = html;
            });
        }
        
        function guardarResultado() {
            let form = new FormData();
            form.append('hora', document.getElementById('res-hora').value);
            form.append('animal', document.getElementById('res-animal').value);
            fetch('/admin/guardar-resultado', {method: 'POST', body: form}).then(r => r.json()).then(d => {
                if (d.status === 'ok') { showMensaje(d.mensaje, 'success'); cargarResultados(); }
                else showMensaje(d.error || 'Error', 'error');
            });
        }
        
        function consultarReporte() {
            let inicio = document.getElementById('reporte-fecha-inicio').value;
            let fin = document.getElementById('reporte-fecha-fin').value;
            if (!inicio || !fin) { showMensaje('Seleccione fechas', 'error'); return; }
            fetch('/admin/reporte-agencias-rango', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})})
            .then(r => r.json()).then(d => {
                if (d.error) { showMensaje(d.error, 'error'); return; }
                let html = '<table><thead><tr><th>Agencia</th><th>Tickets</th><th>Ventas</th><th>Premios</th><th>Balance</th></tr></thead><tbody>';
                d.agencias.forEach(ag => {
                    html += `<tr><td>${ag.nombre}</td><td>${ag.tickets}</td><td>S/${ag.ventas.toFixed(0)}</td><td>S/${ag.premios.toFixed(0)}</td><td style="color:${ag.balance >= 0 ? '#27ae60' : '#c0392b'}">S/${ag.balance.toFixed(0)}</td></tr>`;
                });
                html += '</tbody></table>';
                document.getElementById('tabla-reporte').innerHTML = html;
            });
        }
        
        function crearAgencia() {
            let form = new FormData();
            form.append('usuario', document.getElementById('new-usuario').value.trim());
            form.append('password', document.getElementById('new-password').value.trim());
            form.append('nombre', document.getElementById('new-nombre').value.trim());
            fetch('/admin/crear-agencia', {method: 'POST', body: form}).then(r => r.json()).then(d => {
                if (d.status === 'ok') { showMensaje(d.mensaje, 'success'); cargarAgencias(); }
                else showMensaje(d.error, 'error');
            });
        }
        
        function cargarAgencias() {
            fetch('/admin/lista-agencias').then(r => r.json()).then(d => {
                let html = '<table><thead><tr><th>ID</th><th>Usuario</th><th>Nombre</th><th>Comisión</th></tr></thead><tbody>';
                d.forEach(a => html += `<tr><td>${a.id}</td><td>${a.usuario}</td><td>${a.nombre_agencia}</td><td>${(a.comision * 100).toFixed(0)}%</td></tr>`);
                html += '</tbody></table>';
                document.getElementById('tabla-agencias').innerHTML = html;
            });
        }
        
        function exportarCSV() {
            showMensaje('Función CSV en desarrollo', 'info');
        }
        
        document.addEventListener('DOMContentLoaded', () => {
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('reporte-fecha-inicio').value = hoy;
            document.getElementById('reporte-fecha-fin').value = hoy;
            cargarDashboard();
        });
    </script>
</body>
</html>
"""

# ==================== MAIN ====================
if __name__ == '__main__':
    print("=" * 60)
    print("  ZOOLO CASINO CLOUD v6.0 - SISTEMA FUNCIONAL")
    print("=" * 60)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
