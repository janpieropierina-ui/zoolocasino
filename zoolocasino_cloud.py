"""
Zolo Casino v7.1 - FUNCIONAL
Sistema de Apuestas de Animalitos
Arreglos aplicados:
1. Headers separados para GET vs POST/PATCH (Fix critico para que carguen resultados)
2. Limite aumentado a 5000 registros
3. Eliminada restriccion de tiempo para editar resultados
4. Soporte para decimales en montos
"""

from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify, make_response
import urllib.request
import urllib.parse
import json
import random
import string
import datetime
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuracion de Supabase
SUPABASE_URL = "https://iykyfwegvcjstinykwhk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml5a3lmd2VndmNqc3Rpbnlrd2hrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDE1MTgwODIsImV4cCI6MjA1NzA5NDA4Mn0.0QL8Jem1xJ0g8A3m3JjNGKA4S6n0ZAKT6KK5w4V0E3Y"

# Configuracion de zona horaria (Peru UTC-5)
ZONA_HORARIA_OFFSET = -5

# Configuracion de horarios de sorteos
HORARIOS_SORTEOS = [
    {"hora": "10:00 AM", "sorteo": "Lotto Activo"},
    {"hora": "11:00 AM", "sorteo": "Lotto Activo"},
    {"hora": "12:00 PM", "sorteo": "Lotto Activo"},
    {"hora": "01:00 PM", "sorteo": "Lotto Activo"},
    {"hora": "03:00 PM", "sorteo": "Lotto Activo"},
    {"hora": "04:00 PM", "sorteo": "Lotto Activo"},
    {"hora": "05:00 PM", "sorteo": "Lotto Activo"},
    {"hora": "06:00 PM", "sorteo": "Lotto Activo"},
    {"hora": "07:00 PM", "sorteo": "Lotto Activo"},
]

# Animales y numeros
ANIMALES = {
    0: "Delfin", 1: "Carnero", 2: "Toro", 3: "Cienpies", 4: "Alacran",
    5: "Leon", 6: "Rana", 7: "Perico", 8: "Raton", 9: "Aguila",
    10: "Tigre", 11: "Gato", 12: "Caballo", 13: "Mono", 14: "Paloma",
    15: "Zorro", 16: "Oso", 17: "Pavo", 18: "Burro", 19: "Chivo",
    20: "Cochino", 21: "Gallo", 22: "Camello", 23: "Cebra", 24: "Iguana",
    25: "Gallina", 26: "Vaca", 27: "Perro", 28: "Zamuro", 29: "Elefante",
    30: "Pantera", 31: "Ciervo", 32: "Jirafa", 33: "Caiman", 34: "Ballena",
    35: "Bufalo", 36: "Mariposa"
}

# Configuracion de agencias
AGENCIAS = {
    "AGENCIA01": {"nombre": "Agencia Principal", "limite_venta": 10000},
    "AGENCIA02": {"nombre": "Agencia Secundaria", "limite_venta": 8000},
}

# Configuracion de cuentas
def get_cuentas():
    return {
        "admin": {
            "password": "admin123",
            "nombre": "Administrador",
            "es_admin": True,
            "agencia": None
        },
        "vendedor1": {
            "password": "ven123",
            "nombre": "Vendedor 1",
            "es_admin": False,
            "agencia": "AGENCIA01"
        },
        "vendedor2": {
            "password": "ven123",
            "nombre": "Vendedor 2",
            "es_admin": False,
            "agencia": "AGENCIA02"
        }
    }

# Funciones de utilidad
def ahora_peru():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=ZONA_HORARIA_OFFSET)

def formatear_fecha(fecha):
    if isinstance(fecha, datetime.datetime):
        return fecha.strftime("%d/%m/%Y")
    return fecha

def formatear_hora(hora):
    if isinstance(hora, datetime.datetime):
        return hora.strftime("%I:%M %p")
    return hora

def generar_serial():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def formatear_monto(monto):
    try:
        monto_float = float(monto)
        if monto_float == int(monto_float):
            return str(int(monto_float))
        else:
            return str(monto_float)
    except:
        return str(monto)

def hora_a_minutos(hora_str):
    try:
        hora_str = hora_str.strip().upper()
        partes = hora_str.split(':')
        hora = int(partes[0])
        minutos_parte = partes[1].split()
        minutos = int(minutos_parte[0])
        ampm = minutos_parte[1] if len(minutos_parte) > 1 else "AM"
        if ampm == "PM" and hora != 12:
            hora += 12
        elif ampm == "AM" and hora == 12:
            hora = 0
        return hora * 60 + minutos
    except:
        return 0

def obtener_sorteo_actual():
    ahora = ahora_peru()
    minutos_actual = ahora.hour * 60 + ahora.minute
    sorteo_actual = None
    for sorteo in HORARIOS_SORTEOS:
        minutos_sorteo = hora_a_minutos(sorteo["hora"])
        if minutos_actual >= minutos_sorteo - 5:
            sorteo_actual = sorteo
    return sorteo_actual if sorteo_actual else HORARIOS_SORTEOS[0]

def puede_editar_resultado(hora_sorteo, fecha_str=None):
    return True

# FIX CRITICO: Headers separados para GET vs POST/PATCH
def supabase_request(table, method="GET", data=None, filters=None, timeout=30):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    if filters:
        filter_params = []
        for k, v in filters.items():
            if k.endswith('__like'):
                filter_params.append(f"{k.replace('__like', '')}=like.{urllib.parse.quote(str(v))}")
            elif k.endswith('__gte'):
                filter_params.append(f"{k.replace('__gte', '')}=gte.{urllib.parse.quote(str(v))}")
            elif k.endswith('__lte'):
                filter_params.append(f"{k.replace('__lte', '')}=lte.{urllib.parse.quote(str(v))}")
            elif k.endswith('__in'):
                valores = ','.join([str(x) for x in v])
                filter_params.append(f"{k.replace('__in', '')}=in.({valores})")
            elif k.endswith('__order'):
                filter_params.append(f"order={v}")
            elif k.endswith('__limit'):
                filter_params.append(f"limit={v}")
            else:
                filter_params.append(f"{k}=eq.{urllib.parse.quote(str(v))}")
        
        tiene_limit = any('limit=' in p for p in filter_params)
        if not tiene_limit:
            filter_params.append("limit=5000")
        
        url += "?" + "&".join(filter_params)
    else:
        url += "?limit=5000"
    
    headers_get = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    headers_write = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        if method == "GET":
            req = urllib.request.Request(url, headers=headers_get)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        
        elif method == "POST":
            req = urllib.request.Request(
                url, 
                data=json.dumps(data).encode(), 
                headers=headers_write,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        
        elif method == "PATCH":
            req = urllib.request.Request(
                url, 
                data=json.dumps(data).encode(), 
                headers=headers_write,
                method="PATCH"
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        
        elif method == "DELETE":
            req = urllib.request.Request(url, headers=headers_get, method="DELETE")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return True
                
    except urllib.error.HTTPError as e:
        print(f"Error HTTP {method} en {table}: {e.code} - {e.read().decode()}")
        return None
    except Exception as e:
        print(f"Error {method} en {table}: {str(e)}")
        return None
    
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('es_admin', False):
            flash("No tienes permisos de administrador", "error")
            return redirect(url_for('pos'))
        return f(*args, **kwargs)
    return decorated_function


# TEMPLATES HTML

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zolo Casino - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .logo { text-align: center; margin-bottom: 30px; }
        .logo h1 { color: #e94560; font-size: 2.5em; text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3); }
        .logo p { color: #aaa; margin-top: 5px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; color: #fff; margin-bottom: 8px; font-weight: 500; }
        .form-group input {
            width: 100%; padding: 12px 15px; border: none; border-radius: 10px;
            background: rgba(255, 255, 255, 0.1); color: #fff; font-size: 16px;
            transition: all 0.3s ease;
        }
        .form-group input:focus { outline: none; background: rgba(255, 255, 255, 0.2); box-shadow: 0 0 10px rgba(233, 69, 96, 0.3); }
        .btn-login {
            width: 100%; padding: 15px; border: none; border-radius: 10px;
            background: linear-gradient(135deg, #e94560, #c73e54); color: #fff;
            font-size: 18px; font-weight: 600; cursor: pointer; transition: all 0.3s ease;
        }
        .btn-login:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(233, 69, 96, 0.4); }
        .flash-messages { margin-bottom: 20px; }
        .flash-message {
            padding: 10px 15px; border-radius: 8px; margin-bottom: 10px; font-size: 14px;
        }
        .flash-message.error { background: rgba(231, 76, 60, 0.2); color: #e74c3c; border: 1px solid rgba(231, 76, 60, 0.3); }
        .flash-message.success { background: rgba(46, 204, 113, 0.2); color: #2ecc71; border: 1px solid rgba(46, 204, 113, 0.3); }
        .version { text-align: center; color: #666; margin-top: 20px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>Zolo Casino</h1>
            <p>Sistema de Apuestas</p>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash-message {{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        <form method="POST" action="{{ url_for('login') }}">
            <div class="form-group">
                <label for="username">Usuario</label>
                <input type="text" id="username" name="username" required placeholder="Ingrese su usuario">
            </div>
            <div class="form-group">
                <label for="password">Contraseña</label>
                <input type="password" id="password" name="password" required placeholder="Ingrese su contraseña">
            </div>
            <button type="submit" class="btn-login">Iniciar Sesion</button>
        </form>
        <div class="version">Version 7.1 FUNCIONAL</div>
    </div>
</body>
</html>
"""

POS_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zolo Casino - Terminal de Ventas</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a; color: #fff; min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 15px 20px; display: flex; justify-content: space-between;
            align-items: center; border-bottom: 2px solid #e94560;
        }
        .header-left { display: flex; align-items: center; gap: 20px; }
        .header h1 { color: #e94560; font-size: 1.5em; }
        .header-info { display: flex; gap: 20px; font-size: 14px; color: #aaa; }
        .header-info span { color: #fff; font-weight: 600; }
        .header-actions { display: flex; gap: 10px; }
        .btn {
            padding: 10px 20px; border: none; border-radius: 8px;
            cursor: pointer; font-weight: 600; transition: all 0.3s ease;
            text-decoration: none; display: inline-block;
        }
        .btn-primary { background: linear-gradient(135deg, #e94560, #c73e54); color: #fff; }
        .btn-secondary { background: rgba(255, 255, 255, 0.1); color: #fff; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3); }
        .main-container {
            display: grid; grid-template-columns: 1fr 350px; gap: 20px;
            padding: 20px; max-width: 1400px; margin: 0 auto;
        }
        .panel {
            background: rgba(255, 255, 255, 0.05); border-radius: 15px;
            padding: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .panel h2 { color: #e94560; margin-bottom: 15px; font-size: 1.2em; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 10px; }
        .animals-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 20px; }
        .animal-btn {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border: 2px solid rgba(255, 255, 255, 0.1); border-radius: 10px;
            padding: 15px 5px; cursor: pointer; transition: all 0.3s ease; text-align: center;
        }
        .animal-btn:hover { border-color: #e94560; transform: scale(1.05); }
        .animal-btn.selected { background: linear-gradient(135deg, #e94560, #c73e54); border-color: #e94560; }
        .animal-number { font-size: 1.5em; font-weight: bold; color: #fff; }
        .animal-name { font-size: 0.75em; color: #aaa; margin-top: 5px; }
        .animal-btn.selected .animal-name { color: #fff; }
        .bet-section { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }
        .bet-type {
            background: rgba(255, 255, 255, 0.05); border: 2px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px; padding: 15px; cursor: pointer; transition: all 0.3s ease; text-align: center;
        }
        .bet-type:hover { border-color: #e94560; }
        .bet-type.selected { background: linear-gradient(135deg, #e94560, #c73e54); border-color: #e94560; }
        .bet-type h3 { font-size: 1em; margin-bottom: 5px; }
        .bet-type p { font-size: 0.8em; color: #aaa; }
        .bet-type.selected p { color: rgba(255, 255, 255, 0.8); }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #aaa; font-size: 14px; }
        .form-group input, .form-group select {
            width: 100%; padding: 12px; border: none; border-radius: 8px;
            background: rgba(255, 255, 255, 0.1); color: #fff; font-size: 16px;
        }
        .form-group input:focus { outline: none; background: rgba(255, 255, 255, 0.15); }
        .ticket-preview {
            background: #fff; color: #000; border-radius: 10px;
            padding: 15px; font-family: 'Courier New', monospace; font-size: 12px; margin-top: 15px;
        }
        .ticket-preview h4 { text-align: center; border-bottom: 1px dashed #000; padding-bottom: 10px; margin-bottom: 10px; }
        .ticket-item { display: flex; justify-content: space-between; margin-bottom: 5px; }
        .ticket-total { border-top: 1px dashed #000; margin-top: 10px; padding-top: 10px; font-weight: bold; text-align: right; }
        .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }
        .btn-full { grid-column: span 2; }
        .modal {
            display: none; position: fixed; top: 0; left: 0;
            width: 100%; height: 100%; background: rgba(0, 0, 0, 0.8);
            z-index: 1000; justify-content: center; align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: #1a1a2e; border-radius: 15px; padding: 30px;
            max-width: 500px; width: 90%; max-height: 80vh; overflow-y: auto;
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h2 { color: #e94560; }
        .close-btn { background: none; border: none; color: #fff; font-size: 24px; cursor: pointer; }
        .search-box { display: flex; gap: 10px; margin-bottom: 15px; }
        .search-box input { flex: 1; padding: 10px; border: none; border-radius: 8px; background: rgba(255, 255, 255, 0.1); color: #fff; }
        .tickets-list { max-height: 300px; overflow-y: auto; }
        .ticket-item-list {
            background: rgba(255, 255, 255, 0.05); border-radius: 8px;
            padding: 10px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;
        }
        .ticket-item-list.paid { border-left: 3px solid #2ecc71; }
        .ticket-item-list.cancelled { border-left: 3px solid #e74c3c; opacity: 0.6; }
        .ticket-info h4 { color: #fff; margin-bottom: 5px; }
        .ticket-info p { color: #aaa; font-size: 12px; }
        .ticket-actions { display: flex; gap: 5px; }
        .btn-small { padding: 5px 10px; font-size: 12px; }
        .flash-messages { position: fixed; top: 80px; right: 20px; z-index: 1001; }
        .flash-message {
            padding: 15px 20px; border-radius: 8px; margin-bottom: 10px; animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .flash-message.error { background: rgba(231, 76, 60, 0.9); color: #fff; }
        .flash-message.success { background: rgba(46, 204, 113, 0.9); color: #fff; }
        .flash-message.info { background: rgba(52, 152, 219, 0.9); color: #fff; }
        @media print {
            body * { visibility: hidden; }
            .ticket-print, .ticket-print * { visibility: visible; }
            .ticket-print { position: absolute; left: 50%; top: 0; transform: translateX(-50%); width: 80mm; }
        }
        .quick-amounts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin-top: 5px; }
        .quick-amount { padding: 8px; background: rgba(255, 255, 255, 0.1); border: none; border-radius: 5px; color: #fff; cursor: pointer; font-size: 12px; }
        .quick-amount:hover { background: #e94560; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <h1>Zolo Casino</h1>
            <div class="header-info">
                <div>Usuario: <span>{{ session.nombre }}</span></div>
                <div>Agencia: <span>{{ session.agencia }}</span></div>
                <div>Fecha: <span id="current-date"></span></div>
                <div>Hora: <span id="current-time"></span></div>
            </div>
        </div>
        <div class="header-actions">
            {% if session.es_admin %}
            <a href="{{ url_for('admin') }}" class="btn btn-secondary">Panel Admin</a>
            {% endif %}
            <button class="btn btn-secondary" onclick="openConsultModal()">Consultar</button>
            <button class="btn btn-secondary" onclick="openReprintModal()">Reimprimir</button>
            <a href="{{ url_for('logout') }}" class="btn btn-primary">Salir</a>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="flash-messages">
                {% for category, message in messages %}
                    <div class="flash-message {{ category }}">{{ message }}</div>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}
    <div class="main-container">
        <div class="left-panel">
            <div class="panel">
                <h2>Selecciona los Animalitos</h2>
                <div class="animals-grid" id="animals-grid">
                    {% for num, nombre in animales.items() %}
                    <div class="animal-btn" data-number="{{ num }}" data-name="{{ nombre }}" onclick="selectAnimal({{ num }}, '{{ nombre }}')">
                        <div class="animal-number">{{ num }}</div>
                        <div class="animal-name">{{ nombre }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            <div class="panel">
                <h2>Tipo de Apuesta</h2>
                <div class="bet-section">
                    <div class="bet-type" data-type="directo" onclick="selectBetType('directo')">
                        <h3>Directo</h3><p>x30</p>
                    </div>
                    <div class="bet-type" data-type="dupleta" onclick="selectBetType('dupleta')">
                        <h3>Dupleta</h3><p>x200</p>
                    </div>
                    <div class="bet-type" data-type="tripleta" onclick="selectBetType('tripleta')">
                        <h3>Tripleta</h3><p>x600</p>
                    </div>
                </div>
            </div>
        </div>
        <div class="right-panel">
            <div class="panel">
                <h2>Detalle de Apuesta</h2>
                <div class="form-group">
                    <label>Sorteo</label>
                    <select id="sorteo" onchange="updatePreview()">
                        {% for s in sorteos %}
                        <option value="{{ s.hora }}|{{ s.sorteo }}">{{ s.hora }} - {{ s.sorteo }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group">
                    <label>Animalitos Seleccionados</label>
                    <input type="text" id="selected-animals" readonly placeholder="Selecciona animalitos">
                </div>
                <div class="form-group">
                    <label>Monto a Apostar (S/)</label>
                    <input type="number" id="monto" step="0.10" min="0.5" placeholder="0.00" oninput="updatePreview()">
                    <div class="quick-amounts">
                        <button class="quick-amount" onclick="setAmount(0.5)">S/0.5</button>
                        <button class="quick-amount" onclick="setAmount(1)">S/1</button>
                        <button class="quick-amount" onclick="setAmount(2)">S/2</button>
                        <button class="quick-amount" onclick="setAmount(5)">S/5</button>
                        <button class="quick-amount" onclick="setAmount(10)">S/10</button>
                        <button class="quick-amount" onclick="setAmount(20)">S/20</button>
                        <button class="quick-amount" onclick="setAmount(50)">S/50</button>
                        <button class="quick-amount" onclick="setAmount(100)">S/100</button>
                    </div>
                </div>
                <div class="ticket-preview" id="ticket-preview">
                    <h4>Zolo Casino</h4>
                    <div id="preview-content"><p style="text-align: center; color: #666;">Selecciona animalitos y tipo de apuesta</p></div>
                </div>
                <div class="actions">
                    <button class="btn btn-secondary" onclick="clearSelection()">Limpiar</button>
                    <button class="btn btn-primary btn-full" onclick="processTicket()">Procesar Ticket</button>
                </div>
            </div>
        </div>
    </div>
    <!-- Modal Consultar -->
    <div class="modal" id="consult-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>Consultar Tickets</h2>
                <button class="close-btn" onclick="closeConsultModal()">&times;</button>
            </div>
            <div class="search-box">
                <input type="text" id="search-serial" placeholder="Numero de ticket o serial">
                <button class="btn btn-primary" onclick="searchTickets()">Buscar</button>
            </div>
            <div class="tickets-list" id="tickets-list"></div>
        </div>
    </div>
    <!-- Modal Reimprimir -->
    <div class="modal" id="reprint-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>Reimprimir Ticket</h2>
                <button class="close-btn" onclick="closeReprintModal()">&times;</button>
            </div>
            <div class="search-box">
                <input type="text" id="reprint-serial" placeholder="Numero de ticket">
                <button class="btn btn-primary" onclick="searchReprint()">Buscar</button>
            </div>
            <div id="reprint-result"></div>
        </div>
    </div>
    <!-- Modal Pagar -->
    <div class="modal" id="pay-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>Pagar Premio</h2>
                <button class="close-btn" onclick="closePayModal()">&times;</button>
            </div>
            <div id="pay-content"></div>
        </div>
    </div>
    <script>
        let selectedAnimals = [];
        let selectedBetType = null;
        const animales = {{ animales | tojson }};
        
        function updateDateTime() {
            const now = new Date();
            document.getElementById('current-date').textContent = now.toLocaleDateString('es-PE');
            document.getElementById('current-time').textContent = now.toLocaleTimeString('es-PE');
        }
        setInterval(updateDateTime, 1000);
        updateDateTime();
        
        function selectAnimal(num, name) {
            const btn = document.querySelector(`.animal-btn[data-number="${num}"]`);
            if (selectedBetType === 'directo') {
                document.querySelectorAll('.animal-btn').forEach(b => b.classList.remove('selected'));
                selectedAnimals = [];
            }
            const index = selectedAnimals.findIndex(a => a.num === num);
            if (index > -1) {
                selectedAnimals.splice(index, 1);
                btn.classList.remove('selected');
            } else {
                if (selectedBetType === 'dupleta' && selectedAnimals.length >= 2) {
                    alert('Solo puedes seleccionar 2 animalitos para dupleta'); return;
                }
                if (selectedBetType === 'tripleta' && selectedAnimals.length >= 3) {
                    alert('Solo puedes seleccionar 3 animalitos para tripleta'); return;
                }
                selectedAnimals.push({ num, name });
                btn.classList.add('selected');
            }
            updateSelectedAnimalsDisplay();
            updatePreview();
        }
        
        function selectBetType(type) {
            selectedBetType = type;
            document.querySelectorAll('.bet-type').forEach(bt => bt.classList.remove('selected'));
            document.querySelector(`.bet-type[data-type="${type}"]`).classList.add('selected');
            document.querySelectorAll('.animal-btn').forEach(b => b.classList.remove('selected'));
            selectedAnimals = [];
            updateSelectedAnimalsDisplay();
            updatePreview();
        }
        
        function updateSelectedAnimalsDisplay() {
            const display = selectedAnimals.map(a => `${a.num}-${a.name}`).join(', ');
            document.getElementById('selected-animals').value = display;
        }
        
        function setAmount(amount) {
            document.getElementById('monto').value = amount;
            updatePreview();
        }
        
        function updatePreview() {
            const monto = parseFloat(document.getElementById('monto').value) || 0;
            const sorteo = document.getElementById('sorteo').value;
            const preview = document.getElementById('preview-content');
            if (selectedAnimals.length === 0 || !selectedBetType || monto <= 0) {
                preview.innerHTML = '<p style="text-align: center; color: #666;">Selecciona animalitos y tipo de apuesta</p>';
                return;
            }
            let html = '';
            html += `<div class="ticket-item"><span>Sorteo:</span><span>${sorteo}</span></div>`;
            html += `<div class="ticket-item"><span>Fecha:</span><span>${new Date().toLocaleDateString('es-PE')}</span></div>`;
            html += '<div style="margin: 10px 0; border-top: 1px dashed #000;"></div>';
            let multiplicador = selectedBetType === 'directo' ? 30 : selectedBetType === 'dupleta' ? 200 : 600;
            let premio = monto * multiplicador;
            selectedAnimals.forEach(a => {
                html += `<div class="ticket-item"><span>${a.num} - ${a.name}</span><span>S/${monto.toFixed(2)}</span></div>`;
            });
            html += '<div style="margin: 10px 0; border-top: 1px dashed #000;"></div>';
            html += `<div class="ticket-item"><span>Tipo:</span><span>${selectedBetType.toUpperCase()} (x${multiplicador})</span></div>`;
            html += `<div class="ticket-total">Total: S/${monto.toFixed(2)} | Premio: S/${premio.toFixed(2)}</div>`;
            preview.innerHTML = html;
        }
        
        function clearSelection() {
            selectedAnimals = [];
            selectedBetType = null;
            document.querySelectorAll('.animal-btn').forEach(b => b.classList.remove('selected'));
            document.querySelectorAll('.bet-type').forEach(bt => bt.classList.remove('selected'));
            document.getElementById('selected-animals').value = '';
            document.getElementById('monto').value = '';
            updatePreview();
        }
        
        function processTicket() {
            if (selectedAnimals.length === 0) { alert('Selecciona al menos un animalito'); return; }
            if (!selectedBetType) { alert('Selecciona el tipo de apuesta'); return; }
            const monto = parseFloat(document.getElementById('monto').value);
            if (!monto || monto <= 0) { alert('Ingresa un monto valido'); return; }
            const sorteoValue = document.getElementById('sorteo').value;
            const [hora, nombre] = sorteoValue.split('|');
            const data = {
                tipo_apuesta: selectedBetType,
                seleccion: selectedAnimals.map(a => a.num).join(','),
                nombres: selectedAnimals.map(a => a.name).join(','),
                monto: monto,
                hora_sorteo: hora,
                nombre_sorteo: nombre
            };
            fetch('/api/venta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Ticket generado: ' + data.ticket.serial);
                    printTicket(data.ticket);
                    clearSelection();
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(e => alert('Error: ' + e));
        }
        
        function printTicket(ticket) {
            const ventana = window.open('', '_blank');
            const fecha = new Date().toLocaleDateString('es-PE');
            const hora = new Date().toLocaleTimeString('es-PE');
            let html = `<html><head><style>
                body { font-family: monospace; width: 80mm; margin: 0; padding: 10px; }
                .center { text-align: center; } .line { border-top: 1px dashed #000; margin: 10px 0; }
                .bold { font-weight: bold; }
            </style></head><body>
                <div class="center bold">Zolo Casino</div>
                <div class="center">{{ session.agencia }}</div>
                <div class="line"></div>
                <div>Ticket: ${ticket.serial}</div>
                <div>Fecha: ${fecha} ${hora}</div>
                <div>Sorteo: ${ticket.hora_sorteo}</div>
                <div class="line"></div>
                <div class="bold">APUESTAS:</div>`;
            ticket.jugadas.forEach(j => {
                html += `<div>${j.seleccion} - S/${j.monto}</div>`;
            });
            html += `<div class="line"></div>
                <div class="bold">Total: S/${ticket.total}</div>
                <div class="center" style="margin-top: 20px;">Buena Suerte!</div>
                <div class="center" style="font-size: 10px; margin-top: 10px;">Valido solo para el sorteo indicado</div>
            </body></html>`;
            ventana.document.write(html);
            ventana.document.close();
            ventana.print();
        }
        
        function openConsultModal() { document.getElementById('consult-modal').classList.add('active'); document.getElementById('search-serial').focus(); }
        function closeConsultModal() { document.getElementById('consult-modal').classList.remove('active'); }
        function openReprintModal() { document.getElementById('reprint-modal').classList.add('active'); document.getElementById('reprint-serial').focus(); }
        function closeReprintModal() { document.getElementById('reprint-modal').classList.remove('active'); }
        function closePayModal() { document.getElementById('pay-modal').classList.remove('active'); }
        
        function searchTickets() {
            const serial = document.getElementById('search-serial').value;
            if (!serial) return;
            fetch('/api/tickets/buscar?q=' + encodeURIComponent(serial))
                .then(r => r.json())
                .then(data => {
                    const list = document.getElementById('tickets-list');
                    if (data.tickets && data.tickets.length > 0) {
                        list.innerHTML = data.tickets.map(t => `
                            <div class="ticket-item-list ${t.estado}">
                                <div class="ticket-info">
                                    <h4>Ticket: ${t.serial}</h4>
                                    <p>${t.fecha} - S/${t.total} - ${t.estado}</p>
                                </div>
                                <div class="ticket-actions">
                                    ${t.estado === 'activo' ? `<button class="btn btn-primary btn-small" onclick="payTicket('${t.serial}')">Pagar</button>` : ''}
                                    <button class="btn btn-secondary btn-small" onclick="viewTicket('${t.serial}')">Ver</button>
                                </div>
                            </div>
                        `).join('');
                    } else {
                        list.innerHTML = '<p style="text-align: center; color: #aaa;">No se encontraron tickets</p>';
                    }
                });
        }
        
        function searchReprint() {
            const serial = document.getElementById('reprint-serial').value;
            if (!serial) return;
            fetch('/api/tickets/' + encodeURIComponent(serial))
                .then(r => r.json())
                .then(data => {
                    const result = document.getElementById('reprint-result');
                    if (data.ticket) {
                        result.innerHTML = `
                            <div class="ticket-item-list">
                                <div class="ticket-info">
                                    <h4>Ticket: ${data.ticket.serial}</h4>
                                    <p>${data.ticket.fecha} - S/${data.ticket.total}</p>
                                </div>
                                <button class="btn btn-primary" onclick='printTicket(${JSON.stringify(data.ticket)})'>Reimprimir</button>
                            </div>
                        `;
                    } else {
                        result.innerHTML = '<p style="text-align: center; color: #aaa;">Ticket no encontrado</p>';
                    }
                });
        }
        
        function viewTicket(serial) {
            fetch('/api/tickets/' + encodeURIComponent(serial))
                .then(r => r.json())
                .then(data => { if (data.ticket) printTicket(data.ticket); });
        }
        
        function payTicket(serial) {
            fetch('/api/tickets/' + encodeURIComponent(serial))
                .then(r => r.json())
                .then(data => {
                    if (data.ticket) {
                        const content = document.getElementById('pay-content');
                        content.innerHTML = `
                            <div class="ticket-item-list">
                                <div class="ticket-info">
                                    <h4>Ticket: ${data.ticket.serial}</h4>
                                    <p>Total apostado: S/${data.ticket.total}</p>
                                    <p>Jugadas: ${data.ticket.jugadas.length}</p>
                                </div>
                            </div>
                            <div style="margin-top: 20px;">
                                <button class="btn btn-primary btn-full" onclick="confirmPay('${serial}')">Confirmar Pago</button>
                            </div>
                        `;
                        document.getElementById('pay-modal').classList.add('active');
                    }
                });
        }
        
        function confirmPay(serial) {
            fetch('/api/tickets/pagar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial: serial })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Ticket pagado exitosamente');
                    closePayModal();
                    closeConsultModal();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeConsultModal();
                closeReprintModal();
                closePayModal();
            }
        });
    </script>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zolo Casino - Panel de Administracion</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0a0a0a; color: #fff; min-height: 100vh; }
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 15px 20px; display: flex; justify-content: space-between;
            align-items: center; border-bottom: 2px solid #e94560;
        }
        .header h1 { color: #e94560; font-size: 1.5em; }
        .header-actions { display: flex; gap: 10px; }
        .btn {
            padding: 10px 20px; border: none; border-radius: 8px;
            cursor: pointer; font-weight: 600; transition: all 0.3s ease;
            text-decoration: none; display: inline-block;
        }
        .btn-primary { background: linear-gradient(135deg, #e94560, #c73e54); color: #fff; }
        .btn-secondary { background: rgba(255, 255, 255, 0.1); color: #fff; }
        .btn-success { background: linear-gradient(135deg, #2ecc71, #27ae60); color: #fff; }
        .btn-warning { background: linear-gradient(135deg, #f39c12, #e67e22); color: #fff; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3); }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 10px; }
        .tab { padding: 10px 20px; background: rgba(255, 255, 255, 0.05); border: none; border-radius: 8px; color: #aaa; cursor: pointer; transition: all 0.3s ease; }
        .tab:hover { background: rgba(255, 255, 255, 0.1); }
        .tab.active { background: linear-gradient(135deg, #e94560, #c73e54); color: #fff; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .panel { background: rgba(255, 255, 255, 0.05); border-radius: 15px; padding: 20px; border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 20px; }
        .panel h2 { color: #e94560; margin-bottom: 15px; font-size: 1.2em; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 10px; padding: 20px; text-align: center; border: 1px solid rgba(255, 255, 255, 0.1); }
        .stat-card h3 { color: #aaa; font-size: 0.9em; margin-bottom: 10px; }
        .stat-card .value { color: #fff; font-size: 2em; font-weight: bold; }
        .stat-card.success .value { color: #2ecc71; }
        .stat-card.danger .value { color: #e74c3c; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #aaa; font-size: 14px; }
        .form-group input, .form-group select { width: 100%; padding: 12px; border: none; border-radius: 8px; background: rgba(255, 255, 255, 0.1); color: #fff; font-size: 16px; }
        .form-group input:focus { outline: none; background: rgba(255, 255, 255, 0.15); }
        .form-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
        th { color: #e94560; font-weight: 600; }
        td { color: #aaa; }
        tr:hover td { color: #fff; background: rgba(255, 255, 255, 0.05); }
        .badge { padding: 5px 10px; border-radius: 5px; font-size: 12px; font-weight: 600; }
        .badge-success { background: rgba(46, 204, 113, 0.2); color: #2ecc71; }
        .badge-danger { background: rgba(231, 76, 60, 0.2); color: #e74c3c; }
        .badge-warning { background: rgba(243, 156, 18, 0.2); color: #f39c12; }
        .actions-cell { display: flex; gap: 5px; }
        .btn-small { padding: 5px 10px; font-size: 12px; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.8); z-index: 1000; justify-content: center; align-items: center; }
        .modal.active { display: flex; }
        .modal-content { background: #1a1a2e; border-radius: 15px; padding: 30px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h2 { color: #e94560; }
        .close-btn { background: none; border: none; color: #fff; font-size: 24px; cursor: pointer; }
        .flash-messages { position: fixed; top: 80px; right: 20px; z-index: 1001; }
        .flash-message { padding: 15px 20px; border-radius: 8px; margin-bottom: 10px; animation: slideIn 0.3s ease; }
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        .flash-message.error { background: rgba(231, 76, 60, 0.9); color: #fff; }
        .flash-message.success { background: rgba(46, 204, 113, 0.9); color: #fff; }
        .results-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }
        .result-item { background: rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 15px; }
        .result-item h4 { color: #e94560; margin-bottom: 10px; }
        .animal-result { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
        .animal-number { width: 40px; height: 40px; background: linear-gradient(135deg, #e94560, #c73e54); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; }
        @media (max-width: 768px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } .form-row { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>Zolo Casino - Panel Admin</h1>
        <div class="header-actions">
            <a href="{{ url_for('pos') }}" class="btn btn-secondary">Volver al POS</a>
            <a href="{{ url_for('logout') }}" class="btn btn-primary">Salir</a>
        </div>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="flash-messages">
                {% for category, message in messages %}
                    <div class="flash-message {{ category }}">{{ message }}</div>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}
    <div class="container">
        <div class="tabs">
            <button class="tab active" onclick="showTab('dashboard')">Dashboard</button>
            <button class="tab" onclick="showTab('resultados')">Resultados</button>
            <button class="tab" onclick="showTab('tickets')">Tickets</button>
            <button class="tab" onclick="showTab('reportes')">Reportes</button>
            <button class="tab" onclick="showTab('agencias')">Agencias</button>
        </div>
        <!-- Dashboard -->
        <div id="dashboard" class="tab-content active">
            <div class="stats-grid">
                <div class="stat-card"><h3>Ventas Hoy</h3><div class="value" id="ventas-hoy">S/0.00</div></div>
                <div class="stat-card success"><h3>Premios Pagados</h3><div class="value" id="premios-hoy">S/0.00</div></div>
                <div class="stat-card"><h3>Tickets Vendidos</h3><div class="value" id="tickets-hoy">0</div></div>
                <div class="stat-card danger"><h3>Balance</h3><div class="value" id="balance-hoy">S/0.00</div></div>
            </div>
            <div class="panel">
                <h2>Resumen del Dia</h2>
                <div id="resumen-dia"><p style="color: #666;">Cargando datos...</p></div>
            </div>
        </div>
        <!-- Resultados -->
        <div id="resultados" class="tab-content">
            <div class="panel">
                <h2>Registrar Resultado</h2>
                <form id="resultado-form" onsubmit="registrarResultado(event)">
                    <div class="form-row">
                        <div class="form-group"><label>Fecha</label><input type="date" id="res-fecha" required></div>
                        <div class="form-group"><label>Hora Sorteo</label><select id="res-hora" required>{% for s in sorteos %}<option value="{{ s.hora }}">{{ s.hora }} - {{ s.sorteo }}</option>{% endfor %}</select></div>
                        <div class="form-group"><label>Animal Ganador</label><select id="res-animal" required>{% for num, nombre in animales.items() %}<option value="{{ num }}">{{ num }} - {{ nombre }}</option>{% endfor %}</select></div>
                    </div>
                    <button type="submit" class="btn btn-success">Guardar Resultado</button>
                </form>
            </div>
            <div class="panel">
                <h2>Resultados Registrados</h2>
                <div id="resultados-lista"><p style="color: #666;">Cargando resultados...</p></div>
            </div>
        </div>
        <!-- Tickets -->
        <div id="tickets" class="tab-content">
            <div class="panel">
                <h2>Buscar Tickets</h2>
                <div class="form-row">
                    <div class="form-group"><input type="text" id="ticket-search" placeholder="Serial o numero de ticket"></div>
                    <div class="form-group"><input type="date" id="ticket-fecha"></div>
                    <div class="form-group"><button class="btn btn-primary" onclick="buscarTicketsAdmin()">Buscar</button></div>
                </div>
            </div>
            <div class="panel">
                <h2>Tickets</h2>
                <div style="overflow-x: auto;">
                    <table>
                        <thead><tr><th>Serial</th><th>Fecha</th><th>Sorteo</th><th>Total</th><th>Estado</th><th>Acciones</th></tr></thead>
                        <tbody id="tickets-table-body"><tr><td colspan="6" style="text-align: center; color: #666;">Cargando tickets...</td></tr></tbody>
                    </table>
                </div>
            </div>
        </div>
        <!-- Reportes -->
        <div id="reportes" class="tab-content">
            <div class="panel">
                <h2>Reportes</h2>
                <div class="form-row">
                    <div class="form-group"><label>Fecha Inicio</label><input type="date" id="rep-inicio"></div>
                    <div class="form-group"><label>Fecha Fin</label><input type="date" id="rep-fin"></div>
                    <div class="form-group"><label>Agencia</label><select id="rep-agencia"><option value="">Todas</option>{% for codigo, info in agencias.items() %}<option value="{{ codigo }}">{{ info.nombre }}</option>{% endfor %}</select></div>
                </div>
                <div style="margin-top: 15px;">
                    <button class="btn btn-primary" onclick="generarReporte()">Generar Reporte</button>
                    <button class="btn btn-secondary" onclick="exportarExcel()">Exportar Excel</button>
                </div>
            </div>
            <div class="panel">
                <h2>Resultado del Reporte</h2>
                <div id="reporte-resultado"><p style="color: #666;">Selecciona fechas y genera el reporte</p></div>
            </div>
        </div>
        <!-- Agencias -->
        <div id="agencias" class="tab-content">
            <div class="panel">
                <h2>Gestion de Agencias</h2>
                <div id="agencias-lista"><p style="color: #666;">Cargando agencias...</p></div>
            </div>
        </div>
    </div>
    <!-- Modal Ver Ticket -->
    <div class="modal" id="ticket-modal">
        <div class="modal-content">
            <div class="modal-header"><h2>Detalle del Ticket</h2><button class="close-btn" onclick="closeTicketModal()">&times;</button></div>
            <div id="ticket-detail"></div>
        </div>
    </div>
    <script>
        document.getElementById('res-fecha').valueAsDate = new Date();
        document.getElementById('rep-inicio').valueAsDate = new Date();
        document.getElementById('rep-fin').valueAsDate = new Date();
        
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
            if (tabName === 'dashboard') loadDashboard();
            if (tabName === 'resultados') loadResultados();
            if (tabName === 'tickets') loadTickets();
            if (tabName === 'agencias') loadAgencias();
        }
        
        function loadDashboard() {
            fetch('/api/admin/dashboard')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('ventas-hoy').textContent = 'S/' + data.ventas.toFixed(2);
                        document.getElementById('premios-hoy').textContent = 'S/' + data.premios.toFixed(2);
                        document.getElementById('tickets-hoy').textContent = data.tickets;
                        document.getElementById('balance-hoy').textContent = 'S/' + data.balance.toFixed(2);
                        let html = '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">';
                        html += '<div><h4 style="color: #e94560; margin-bottom: 10px;">Ventas por Sorteo</h4>';
                        for (let s in data.ventas_por_sorteo) {
                            html += `<p>${s}: S/${data.ventas_por_sorteo[s].toFixed(2)}</p>`;
                        }
                        html += '</div><div><h4 style="color: #e94560; margin-bottom: 10px;">Tickets por Estado</h4>';
                        html += `<p>Activos: ${data.tickets_activos}</p>`;
                        html += `<p>Pagados: ${data.tickets_pagados}</p>`;
                        html += `<p>Anulados: ${data.tickets_anulados}</p>`;
                        html += '</div></div>';
                        document.getElementById('resumen-dia').innerHTML = html;
                    }
                });
        }
        
        function loadResultados() {
            fetch('/api/resultados?limit=5000')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        let html = '<table><thead><tr><th>Fecha</th><th>Hora</th><th>Animal</th><th>Acciones</th></tr></thead><tbody>';
                        data.resultados.forEach(res => {
                            html += `<tr>
                                <td>${res.fecha}</td>
                                <td>${res.hora_sorteo}</td>
                                <td>${res.animal_ganador} - ${res.nombre_animal || ''}</td>
                                <td class="actions-cell">
                                    <button class="btn btn-warning btn-small" onclick="editarResultado('${res.id}', '${res.animal_ganador}')">Editar</button>
                                </td>
                            </tr>`;
                        });
                        html += '</tbody></table>';
                        document.getElementById('resultados-lista').innerHTML = html;
                    } else {
                        document.getElementById('resultados-lista').innerHTML = '<p style="color: #e74c3c;">Error cargando resultados: ' + (data.error || 'Desconocido') + '</p>';
                    }
                })
                .catch(e => {
                    document.getElementById('resultados-lista').innerHTML = '<p style="color: #e74c3c;">Error de conexion: ' + e.message + '</p>';
                });
        }
        
        function registrarResultado(e) {
            e.preventDefault();
            const data = {
                fecha: document.getElementById('res-fecha').value,
                hora_sorteo: document.getElementById('res-hora').value,
                animal_ganador: document.getElementById('res-animal').value
            };
            fetch('/api/resultados', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Resultado registrado exitosamente');
                    loadResultados();
                    document.getElementById('resultado-form').reset();
                    document.getElementById('res-fecha').valueAsDate = new Date();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function editarResultado(id, animalActual) {
            const nuevoAnimal = prompt('Editar animal ganador (0-36):', animalActual);
            if (nuevoAnimal === null) return;
            fetch('/api/resultados/' + id, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ animal_ganador: parseInt(nuevoAnimal) })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Resultado actualizado');
                    loadResultados();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function loadTickets() {
            fetch('/api/tickets?limit=5000')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const tbody = document.getElementById('tickets-table-body');
                        if (data.tickets.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #666;">No hay tickets</td></tr>';
                            return;
                        }
                        tbody.innerHTML = data.tickets.map(t => {
                            let badgeClass = t.estado === 'activo' ? 'badge-success' : t.estado === 'pagado' ? 'badge-warning' : 'badge-danger';
                            return `<tr>
                                <td>${t.serial}</td>
                                <td>${t.fecha}</td>
                                <td>${t.hora_sorteo}</td>
                                <td>S/${parseFloat(t.total).toFixed(2)}</td>
                                <td><span class="badge ${badgeClass}">${t.estado}</span></td>
                                <td class="actions-cell">
                                    <button class="btn btn-secondary btn-small" onclick="verTicket('${t.serial}')">Ver</button>
                                    ${t.estado === 'activo' ? `<button class="btn btn-danger btn-small" onclick="anularTicket('${t.serial}')">Anular</button>` : ''}
                                </td>
                            </tr>`;
                        }).join('');
                    }
                });
        }
        
        function buscarTicketsAdmin() {
            const q = document.getElementById('ticket-search').value;
            const fecha = document.getElementById('ticket-fecha').value;
            let url = '/api/tickets?limit=5000';
            if (q) url += '&q=' + encodeURIComponent(q);
            if (fecha) url += '&fecha=' + encodeURIComponent(fecha);
            fetch(url)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const tbody = document.getElementById('tickets-table-body');
                        if (data.tickets.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #666;">No se encontraron tickets</td></tr>';
                            return;
                        }
                        tbody.innerHTML = data.tickets.map(t => {
                            let badgeClass = t.estado === 'activo' ? 'badge-success' : t.estado === 'pagado' ? 'badge-warning' : 'badge-danger';
                            return `<tr>
                                <td>${t.serial}</td>
                                <td>${t.fecha}</td>
                                <td>${t.hora_sorteo}</td>
                                <td>S/${parseFloat(t.total).toFixed(2)}</td>
                                <td><span class="badge ${badgeClass}">${t.estado}</span></td>
                                <td class="actions-cell">
                                    <button class="btn btn-secondary btn-small" onclick="verTicket('${t.serial}')">Ver</button>
                                    ${t.estado === 'activo' ? `<button class="btn btn-danger btn-small" onclick="anularTicket('${t.serial}')">Anular</button>` : ''}
                                </td>
                            </tr>`;
                        }).join('');
                    }
                });
        }
        
        function verTicket(serial) {
            fetch('/api/tickets/' + encodeURIComponent(serial))
                .then(r => r.json())
                .then(data => {
                    if (data.ticket) {
                        const t = data.ticket;
                        let html = `<div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; margin-bottom: 15px;">
                            <p><strong>Serial:</strong> ${t.serial}</p>
                            <p><strong>Fecha:</strong> ${t.fecha}</p>
                            <p><strong>Sorteo:</strong> ${t.hora_sorteo}</p>
                            <p><strong>Estado:</strong> ${t.estado}</p>
                            <p><strong>Total:</strong> S/${parseFloat(t.total).toFixed(2)}</p>
                        </div>
                        <h4 style="color: #e94560; margin-bottom: 10px;">Jugadas:</h4>`;
                        t.jugadas.forEach(j => {
                            html += `<p>${j.tipo_apuesta}: ${j.seleccion} - S/${parseFloat(j.monto).toFixed(2)}</p>`;
                        });
                        document.getElementById('ticket-detail').innerHTML = html;
                        document.getElementById('ticket-modal').classList.add('active');
                    }
                });
        }
        
        function closeTicketModal() { document.getElementById('ticket-modal').classList.remove('active'); }
        
        function anularTicket(serial) {
            if (!confirm('Estas seguro de anular este ticket?')) return;
            fetch('/api/tickets/anular', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial: serial })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Ticket anulado exitosamente');
                    loadTickets();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function generarReporte() {
            const inicio = document.getElementById('rep-inicio').value;
            const fin = document.getElementById('rep-fin').value;
            const agencia = document.getElementById('rep-agencia').value;
            let url = '/api/admin/reporte?inicio=' + inicio + '&fin=' + fin + '&limit=5000';
            if (agencia) url += '&agencia=' + encodeURIComponent(agencia);
            fetch(url)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        let html = `<div class="stats-grid">
                            <div class="stat-card"><h3>Total Ventas</h3><div class="value">S/${data.totales.ventas.toFixed(2)}</div></div>
                            <div class="stat-card success"><h3>Total Premios</h3><div class="value">S/${data.totales.premios.toFixed(2)}</div></div>
                            <div class="stat-card"><h3>Total Tickets</h3><div class="value">${data.totales.tickets}</div></div>
                            <div class="stat-card danger"><h3>Balance</h3><div class="value">S/${data.totales.balance.toFixed(2)}</div></div>
                        </div>`;
                        document.getElementById('reporte-resultado').innerHTML = html;
                    }
                });
        }
        
        function exportarExcel() { alert('Funcion de exportacion en desarrollo'); }
        
        function loadAgencias() {
            fetch('/api/admin/agencias')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        let html = '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">';
                        data.agencias.forEach(a => {
                            html += `<div class="result-item">
                                <h4>${a.codigo}</h4>
                                <p>Nombre: ${a.nombre}</p>
                                <p>Limite: S/${a.limite_venta}</p>
                                <p>Ventas hoy: S/${a.ventas_hoy || 0}</p>
                            </div>`;
                        });
                        html += '</div>';
                        document.getElementById('agencias-lista').innerHTML = html;
                    }
                });
        }
        
        loadDashboard();
        setInterval(() => {
            if (document.getElementById('dashboard').classList.contains('active')) {
                loadDashboard();
            }
        }, 30000);
    </script>
</body>
</html>
"""


# RUTAS DE LA APLICACION

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('es_admin', False):
            return redirect(url_for('admin'))
        return redirect(url_for('pos'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        cuentas = get_cuentas()
        if username in cuentas and cuentas[username]['password'] == password:
            session['user_id'] = username
            session['nombre'] = cuentas[username]['nombre']
            session['es_admin'] = cuentas[username]['es_admin']
            session['agencia'] = cuentas[username].get('agencia', 'ADMIN')
            flash(f"Bienvenido, {cuentas[username]['nombre']}!", "success")
            if cuentas[username]['es_admin']:
                return redirect(url_for('admin'))
            return redirect(url_for('pos'))
        else:
            flash("Usuario o contrasena incorrectos", "error")
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    session.clear()
    flash("Sesion cerrada exitosamente", "success")
    return redirect(url_for('login'))

@app.route('/pos')
@login_required
def pos():
    return render_template_string(POS_HTML, animales=ANIMALES, sorteos=HORARIOS_SORTEOS)

@app.route('/admin')
@admin_required
def admin():
    return render_template_string(ADMIN_HTML, animales=ANIMALES, sorteos=HORARIOS_SORTEOS, agencias=AGENCIAS)

# API ENDPOINTS - VENTAS

@app.route('/api/venta', methods=['POST'])
@login_required
def api_venta():
    try:
        data = request.json
        tipo_apuesta = data.get('tipo_apuesta')
        seleccion = data.get('seleccion')
        nombres = data.get('nombres')
        monto = float(data.get('monto', 0))
        hora_sorteo = data.get('hora_sorteo')
        nombre_sorteo = data.get('nombre_sorteo')
        
        if not all([tipo_apuesta, seleccion, monto, hora_sorteo]):
            return jsonify({"success": False, "error": "Faltan datos requeridos"})
        
        if monto <= 0:
            return jsonify({"success": False, "error": "El monto debe ser mayor a 0"})
        
        serial = generar_serial()
        fecha_actual = ahora_peru()
        fecha_str = fecha_actual.strftime("%d/%m/%Y")
        hora_str = fecha_actual.strftime("%H:%M:%S")
        
        ticket_data = {
            "serial": serial,
            "fecha": fecha_str,
            "hora": hora_str,
            "agencia": session.get('agencia', 'SIN_AGENCIA'),
            "vendedor": session.get('nombre', 'SIN_NOMBRE'),
            "hora_sorteo": hora_sorteo,
            "nombre_sorteo": nombre_sorteo,
            "tipo_apuesta": tipo_apuesta,
            "seleccion": seleccion,
            "nombres": nombres,
            "monto": monto,
            "total": monto,
            "estado": "activo",
            "creado_en": fecha_actual.isoformat()
        }
        
        resultado = supabase_request("tickets", method="POST", data=ticket_data)
        
        if resultado:
            return jsonify({
                "success": True,
                "ticket": {
                    "serial": serial,
                    "fecha": fecha_str,
                    "hora": hora_str,
                    "hora_sorteo": hora_sorteo,
                    "total": monto,
                    "jugadas": [{
                        "tipo_apuesta": tipo_apuesta,
                        "seleccion": seleccion,
                        "monto": monto
                    }]
                }
            })
        else:
            return jsonify({"success": False, "error": "Error al guardar el ticket"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/tickets/buscar')
@login_required
def api_buscar_tickets():
    try:
        q = request.args.get('q', '')
        if not q:
            return jsonify({"success": False, "error": "Ingrese termino de busqueda"})
        
        tickets = supabase_request("tickets", filters={
            "serial__like": f"*{q}*",
            "__limit": 5000,
            "__order": "creado_en.desc"
        })
        
        if tickets is None:
            tickets = []
        
        return jsonify({"success": True, "tickets": tickets})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/tickets/<serial>')
@login_required
def api_get_ticket(serial):
    try:
        tickets = supabase_request("tickets", filters={"serial": serial, "__limit": 1})
        
        if tickets and len(tickets) > 0:
            ticket = tickets[0]
            # Asegurar que jugadas sea una lista
            if 'jugadas' not in ticket:
                ticket['jugadas'] = [{
                    'tipo_apuesta': ticket.get('tipo_apuesta', 'directo'),
                    'seleccion': ticket.get('seleccion', ''),
                    'monto': ticket.get('monto', 0)
                }]
            return jsonify({"success": True, "ticket": ticket})
        else:
            return jsonify({"success": False, "error": "Ticket no encontrado"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/tickets')
@login_required
def api_get_tickets():
    try:
        fecha = request.args.get('fecha')
        q = request.args.get('q')
        
        filters = {"__limit": 5000, "__order": "creado_en.desc"}
        
        if fecha:
            filters["fecha"] = fecha
        
        tickets = supabase_request("tickets", filters=filters)
        
        if tickets is None:
            tickets = []
        
        if q:
            tickets = [t for t in tickets if q.lower() in t.get('serial', '').lower()]
        
        # Asegurar que cada ticket tenga jugadas
        for t in tickets:
            if 'jugadas' not in t:
                t['jugadas'] = [{
                    'tipo_apuesta': t.get('tipo_apuesta', 'directo'),
                    'seleccion': t.get('seleccion', ''),
                    'monto': t.get('monto', 0)
                }]
        
        return jsonify({"success": True, "tickets": tickets})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/tickets/pagar', methods=['POST'])
@login_required
def api_pagar_ticket():
    try:
        data = request.json
        serial = data.get('serial')
        
        if not serial:
            return jsonify({"success": False, "error": "Serial requerido"})
        
        tickets = supabase_request("tickets", filters={"serial": serial, "__limit": 1})
        
        if not tickets or len(tickets) == 0:
            return jsonify({"success": False, "error": "Ticket no encontrado"})
        
        ticket = tickets[0]
        
        if ticket.get('estado') != 'activo':
            return jsonify({"success": False, "error": "El ticket no esta activo"})
        
        resultado = supabase_request(
            "tickets",
            method="PATCH",
            data={"estado": "pagado", "pagado_en": ahora_peru().isoformat(), "pagado_por": session.get('nombre')},
            filters={"serial": serial}
        )
        
        if resultado:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Error al pagar el ticket"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/tickets/anular', methods=['POST'])
@login_required
def api_anular_ticket():
    try:
        data = request.json
        serial = data.get('serial')
        
        if not serial:
            return jsonify({"success": False, "error": "Serial requerido"})
        
        tickets = supabase_request("tickets", filters={"serial": serial, "__limit": 1})
        
        if not tickets or len(tickets) == 0:
            return jsonify({"success": False, "error": "Ticket no encontrado"})
        
        ticket = tickets[0]
        
        if ticket.get('estado') != 'activo':
            return jsonify({"success": False, "error": "El ticket no puede ser anulado"})
        
        resultado = supabase_request(
            "tickets",
            method="PATCH",
            data={"estado": "anulado", "anulado_en": ahora_peru().isoformat(), "anulado_por": session.get('nombre')},
            filters={"serial": serial}
        )
        
        if resultado:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Error al anular el ticket"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# API RESULTADOS

@app.route('/api/resultados', methods=['GET'])
@login_required
def api_get_resultados():
    try:
        fecha = request.args.get('fecha')
        
        filters = {"__limit": 5000, "__order": "creado_en.desc"}
        
        if fecha:
            filters["fecha"] = fecha
        
        resultados = supabase_request("resultados", filters=filters)
        
        if resultados is None:
            resultados = []
        
        # Agregar nombre del animal
        for r in resultados:
            r['nombre_animal'] = ANIMALES.get(int(r.get('animal_ganador', 0)), 'Desconocido')
        
        return jsonify({"success": True, "resultados": resultados})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/resultados', methods=['POST'])
@admin_required
def api_registrar_resultado():
    try:
        data = request.json
        
        fecha = data.get('fecha')
        hora_sorteo = data.get('hora_sorteo')
        animal_ganador = int(data.get('animal_ganador', 0))
        
        if not all([fecha, hora_sorteo]):
            return jsonify({"success": False, "error": "Faltan datos requeridos"})
        
        # Verificar si ya existe un resultado para este sorteo
        existentes = supabase_request("resultados", filters={
            "fecha": fecha,
            "hora_sorteo": hora_sorteo,
            "__limit": 1
        })
        
        resultado_data = {
            "fecha": fecha,
            "hora_sorteo": hora_sorteo,
            "animal_ganador": animal_ganador,
            "nombre_sorteo": "Lotto Activo",
            "creado_en": ahora_peru().isoformat(),
            "creado_por": session.get('nombre')
        }
        
        if existentes and len(existentes) > 0:
            # Actualizar resultado existente
            resultado = supabase_request(
                "resultados",
                method="PATCH",
                data=resultado_data,
                filters={"id": existentes[0]['id']}
            )
        else:
            # Crear nuevo resultado
            resultado = supabase_request("resultados", method="POST", data=resultado_data)
        
        if resultado:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Error al guardar el resultado"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/resultados/<id>', methods=['PATCH'])
@admin_required
def api_editar_resultado(id):
    try:
        data = request.json
        
        # FIX: Ya no hay restriccion de tiempo - puede_editar_resultado siempre retorna True
        resultado = supabase_request(
            "resultados",
            method="PATCH",
            data=data,
            filters={"id": id}
        )
        
        if resultado:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Error al actualizar el resultado"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# API ADMIN - DASHBOARD Y REPORTES

@app.route('/api/admin/dashboard')
@admin_required
def api_dashboard():
    try:
        fecha_hoy = ahora_peru().strftime("%d/%m/%Y")
        
        # Obtener tickets de hoy
        tickets = supabase_request("tickets", filters={
            "fecha": fecha_hoy,
            "__limit": 5000
        })
        
        if tickets is None:
            tickets = []
        
        ventas = sum(float(t.get('total', 0)) for t in tickets)
        tickets_activos = len([t for t in tickets if t.get('estado') == 'activo'])
        tickets_pagados = len([t for t in tickets if t.get('estado') == 'pagado'])
        tickets_anulados = len([t for t in tickets if t.get('estado') == 'anulado'])
        
        # Calcular premios pagados
        premios = sum(float(t.get('total', 0)) for t in tickets if t.get('estado') == 'pagado')
        
        # Ventas por sorteo
        ventas_por_sorteo = {}
        for t in tickets:
            sorteo = t.get('hora_sorteo', 'Desconocido')
            ventas_por_sorteo[sorteo] = ventas_por_sorteo.get(sorteo, 0) + float(t.get('total', 0))
        
        return jsonify({
            "success": True,
            "ventas": ventas,
            "premios": premios,
            "tickets": len(tickets),
            "balance": ventas - premios,
            "tickets_activos": tickets_activos,
            "tickets_pagados": tickets_pagados,
            "tickets_anulados": tickets_anulados,
            "ventas_por_sorteo": ventas_por_sorteo
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/reporte')
@admin_required
def api_reporte():
    try:
        inicio = request.args.get('inicio')
        fin = request.args.get('fin')
        agencia = request.args.get('agencia')
        
        if not inicio or not fin:
            return jsonify({"success": False, "error": "Fechas requeridas"})
        
        # Convertir fechas para comparacion
        fecha_inicio = datetime.datetime.strptime(inicio, "%Y-%m-%d")
        fecha_fin = datetime.datetime.strptime(fin, "%Y-%m-%d")
        
        # Obtener todos los tickets
        filters = {"__limit": 5000}
        if agencia:
            filters["agencia"] = agencia
        
        tickets = supabase_request("tickets", filters=filters)
        
        if tickets is None:
            tickets = []
        
        # Filtrar por rango de fechas
        tickets_filtrados = []
        for t in tickets:
            try:
                fecha_ticket = datetime.datetime.strptime(t.get('fecha', ''), "%d/%m/%Y")
                if fecha_inicio <= fecha_ticket <= fecha_fin:
                    tickets_filtrados.append(t)
            except:
                pass
        
        ventas = sum(float(t.get('total', 0)) for t in tickets_filtrados)
        premios = sum(float(t.get('total', 0)) for t in tickets_filtrados if t.get('estado') == 'pagado')
        
        return jsonify({
            "success": True,
            "totales": {
                "ventas": ventas,
                "premios": premios,
                "tickets": len(tickets_filtrados),
                "balance": ventas - premios
            },
            "tickets": tickets_filtrados
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/agencias')
@admin_required
def api_agencias():
    try:
        fecha_hoy = ahora_peru().strftime("%d/%m/%Y")
        
        # Obtener ventas por agencia
        tickets = supabase_request("tickets", filters={
            "fecha": fecha_hoy,
            "__limit": 5000
        })
        
        if tickets is None:
            tickets = []
        
        ventas_por_agencia = {}
        for t in tickets:
            agencia = t.get('agencia', 'SIN_AGENCIA')
            ventas_por_agencia[agencia] = ventas_por_agencia.get(agencia, 0) + float(t.get('total', 0))
        
        agencias_list = []
        for codigo, info in AGENCIAS.items():
            agencias_list.append({
                "codigo": codigo,
                "nombre": info['nombre'],
                "limite_venta": info['limite_venta'],
                "ventas_hoy": ventas_por_agencia.get(codigo, 0)
            })
        
        return jsonify({"success": True, "agencias": agencias_list})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# INICIO DE LA APLICACION

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
