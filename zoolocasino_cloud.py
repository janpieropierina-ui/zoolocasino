"""
Zolo Casino v8.0 - Sistema Completo
Panel Admin y POS con todas las funcionalidades
"""

from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify
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

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
SUPABASE_URL = "https://iykyfwegvcjstinykwhk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml5a3lmd2VndmNqc3Rpbnlrd2hrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDE1MTgwODIsImV4cCI6MjA1NzA5NDA4Mn0.0QL8Jem1xJ0g8A3m3JjNGKA4S6n0ZAKT6KK5w4V0E3Y"
ZONA_HORARIA_OFFSET = -5  # Perú UTC-5

# ============================================================================
# USUARIOS LOCALES (HARDCODEADOS - Funcionan inmediatamente)
# ============================================================================
USUARIOS = {
    "admin": {
        "password": "admin123",
        "nombre": "Administrador",
        "es_admin": True,
        "agencia_codigo": "ADMIN",
        "agencia_nombre": "Oficina Principal"
    },
    "agencia01": {
        "password": "agencia01",
        "nombre": "Agencia 01",
        "es_admin": False,
        "agencia_codigo": "AGENCIA01",
        "agencia_nombre": "Agencia Principal"
    },
    "agencia02": {
        "password": "agencia02",
        "nombre": "Agencia 02",
        "es_admin": False,
        "agencia_codigo": "AGENCIA02",
        "agencia_nombre": "Agencia Secundaria"
    },
    "vendedor1": {
        "password": "vendedor1",
        "nombre": "Vendedor 1",
        "es_admin": False,
        "agencia_codigo": "AGENCIA01",
        "agencia_nombre": "Agencia Principal"
    }
}

# ============================================================================
# DATOS DE ANIMALES (0-40)
# ============================================================================
ANIMALES = {
    0: {"nombre": "Ballena", "color": "rojo"},
    1: {"nombre": "Delfín", "color": "negro"},
    2: {"nombre": "Carnero", "color": "rojo"},
    3: {"nombre": "Toro", "color": "negro"},
    4: {"nombre": "Cienpies", "color": "rojo"},
    5: {"nombre": "León", "color": "negro"},
    6: {"nombre": "Rana", "color": "rojo"},
    7: {"nombre": "Perico", "color": "negro"},
    8: {"nombre": "Ratón", "color": "rojo"},
    9: {"nombre": "Águila", "color": "negro"},
    10: {"nombre": "Tigre", "color": "rojo"},
    11: {"nombre": "Gato", "color": "negro"},
    12: {"nombre": "Caballo", "color": "rojo"},
    13: {"nombre": "Mono", "color": "negro"},
    14: {"nombre": "Paloma", "color": "rojo"},
    15: {"nombre": "Zorro", "color": "negro"},
    16: {"nombre": "Oso", "color": "rojo"},
    17: {"nombre": "Pavo", "color": "negro"},
    18: {"nombre": "Burro", "color": "rojo"},
    19: {"nombre": "Chivo", "color": "negro"},
    20: {"nombre": "Cochino", "color": "rojo"},
    21: {"nombre": "Gallo", "color": "negro"},
    22: {"nombre": "Camello", "color": "rojo"},
    23: {"nombre": "Cebra", "color": "negro"},
    24: {"nombre": "Iguana", "color": "rojo"},
    25: {"nombre": "Gallina", "color": "negro"},
    26: {"nombre": "Vaca", "color": "rojo"},
    27: {"nombre": "Perro", "color": "negro"},
    28: {"nombre": "Zamuro", "color": "rojo"},
    29: {"nombre": "Elefante", "color": "negro"},
    30: {"nombre": "Caimán", "color": "rojo"},
    31: {"nombre": "Lapa", "color": "negro"},
    32: {"nombre": "Ardilla", "color": "rojo"},
    33: {"nombre": "Pescado", "color": "negro"},
    34: {"nombre": "Venado", "color": "rojo"},
    35: {"nombre": "Jirafa", "color": "negro"},
    36: {"nombre": "Culebra", "color": "rojo"},
    37: {"nombre": "Avispa", "color": "negro"},
    38: {"nombre": "Conejo", "color": "rojo"},
    39: {"nombre": "Tortuga", "color": "negro"},
    40: {"nombre": "Lechuza", "color": "rojo"},
}

# Horarios de sorteos
HORARIOS_SORTEO = [
    "08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
    "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM",
    "06:00 PM", "07:00 PM", "08:00 PM", "09:00 PM", "10:00 PM"
]

# ============================================================================
# FUNCIONES UTILITARIAS
# ============================================================================
def ahora_peru():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=ZONA_HORARIA_OFFSET)

def generar_serial():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def formatear_monto(monto):
    try:
        monto_float = float(monto)
        if monto_float == int(monto_float):
            return str(int(monto_float))
        return str(monto_float)
    except:
        return str(monto)

# ============================================================================
# SUPABASE REQUEST (FIX CRÍTICO - Headers separados)
# ============================================================================
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
            elif k.endswith('__order'):
                filter_params.append(f"order={v}")
            elif k.endswith('__limit'):
                filter_params.append(f"limit={v}")
            else:
                filter_params.append(f"{k}=eq.{urllib.parse.quote(str(v))}")
        
        if not any('limit=' in p for p in filter_params):
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
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers_write, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        elif method == "PATCH":
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers_write, method="PATCH")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        elif method == "DELETE":
            req = urllib.request.Request(url, headers=headers_get, method="DELETE")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return True
    except Exception as e:
        print(f"Error {method} en {table}: {e}")
        return None
    return None

# ============================================================================
# DECORADORES
# ============================================================================
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

gba(255, 215, 0, 0.3);
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo h1 {
            color: #ffd700;
            font-size: 2em;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            color: #fff;
            margin-bottom: 8px;
            font-size: 14px;
        }
        .form-group input {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid #444;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 16px;
        }
        .form-group input:focus {
            outline: none;
            border-color: #ffd700;
        }
        .btn-login {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 8px;
            background: linear-gradient(135deg, #ffd700, #ffaa00);
            color: #000;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(255, 215, 0, 0.4);
        }
        .version {
            text-align: center;
            color: #888;
            margin-top: 20px;
            font-size: 12px;
        }
        .flash-message {
            background: rgba(231, 76, 60, 0.2);
            color: #e74c3c;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>🎰 ZOOLO CASINO</h1>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash-message">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST" action="{{ url_for('login') }}">
            <div class="form-group">
                <label>Usuario</label>
                <input type="text" name="username" required placeholder="Ingrese su usuario">
            </div>
            <div class="form-group">
                <label>Contraseña</label>
                <input type="password" name="password" required placeholder="Ingrese su contraseña">
            </div>
            <button type="submit" class="btn-login">INICIAR SESIÓN</button>
        </form>
        <div class="version">Sistema ZOOLO CASINO v8.0<br>Tripleta x60 - Nueva Horario Perú</div>
    </div>
</body>
</html>
"""


# ============================================================================
# TEMPLATE ADMIN PANEL COMPLETO
# ============================================================================
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PANEL ADMIN - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0d0d1a 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #ffd700;
        }
        .header h1 {
            color: #ffd700;
            font-size: 1.3em;
        }
        .header-actions {
            display: flex;
            gap: 10px;
        }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            font-size: 13px;
        }
        .btn-primary { background: linear-gradient(135deg, #ffd700, #ffaa00); color: #000; }
        .btn-secondary { background: rgba(255, 255, 255, 0.1); color: #fff; }
        .btn-success { background: linear-gradient(135deg, #00c853, #00a344); color: #fff; }
        .btn-danger { background: linear-gradient(135deg, #ff5252, #d32f2f); color: #fff; }
        .btn-warning { background: linear-gradient(135deg, #ffb300, #ff8f00); color: #000; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        
        .tabs-container {
            display: flex;
            background: rgba(0,0,0,0.3);
            border-bottom: 1px solid rgba(255,215,0,0.2);
            overflow-x: auto;
        }
        .tab {
            padding: 12px 20px;
            background: transparent;
            border: none;
            color: #aaa;
            cursor: pointer;
            font-size: 13px;
            white-space: nowrap;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .tab:hover { color: #fff; background: rgba(255,255,255,0.05); }
        .tab.active { 
            color: #ffd700; 
            border-bottom: 2px solid #ffd700;
            background: rgba(255,215,0,0.1);
        }
        
        .content {
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        .info-banner {
            background: linear-gradient(135deg, rgba(255,215,0,0.1), rgba(255,170,0,0.1));
            border: 1px solid rgba(255,215,0,0.3);
            border-radius: 8px;
            padding: 10px 15px;
            margin-bottom: 20px;
            font-size: 12px;
            color: #ffd700;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: linear-gradient(135deg, rgba(26,26,46,0.8), rgba(22,33,62,0.8));
            border: 1px solid rgba(255,215,0,0.2);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        .stat-card h3 {
            color: #888;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        .stat-card .value {
            color: #ffd700;
            font-size: 2em;
            font-weight: bold;
        }
        
        .panel {
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .panel h2 {
            color: #ffd700;
            font-size: 16px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            color: #aaa;
            font-size: 12px;
            margin-bottom: 5px;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px;
            border: 1px solid #444;
            border-radius: 6px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 14px;
        }
        
        .results-list {
            display: grid;
            gap: 10px;
        }
        .result-item {
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            padding: 15px;
            display: grid;
            grid-template-columns: 100px 1fr auto;
            align-items: center;
            gap: 15px;
        }
        .result-time {
            color: #ffd700;
            font-weight: bold;
        }
        .result-animal {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .animal-number {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 14px;
        }
        .animal-number.rojo { background: linear-gradient(135deg, #ff5252, #d32f2f); }
        .animal-number.negro { background: linear-gradient(135deg, #444, #222); }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th {
            color: #ffd700;
            font-size: 12px;
            text-transform: uppercase;
        }
        td { color: #aaa; font-size: 13px; }
        tr:hover td { color: #fff; background: rgba(255,255,255,0.05); }
        
        .badge {
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge-success { background: rgba(0,200,83,0.2); color: #00c853; }
        .badge-danger { background: rgba(255,82,82,0.2); color: #ff5252; }
        .badge-warning { background: rgba(255,179,0,0.2); color: #ffb300; }
        
        .actions-cell { display: flex; gap: 5px; }
        .btn-small { padding: 5px 10px; font-size: 11px; }
        
        .quick-actions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }
        .quick-btn {
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .quick-btn:hover { transform: translateY(-2px); }
        
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border: 1px solid rgba(255,215,0,0.3);
            border-radius: 12px;
            padding: 25px;
            max-width: 500px;
            width: 90%;
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .modal-header h3 { color: #ffd700; }
        .close-btn {
            background: none;
            border: none;
            color: #fff;
            font-size: 24px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>👑 PANEL ADMIN - ZOOLO CASINO</h1>
        <div class="header-actions">
            <a href="{{ url_for('pos') }}" class="btn btn-secondary">Ir al POS</a>
            <a href="{{ url_for('logout') }}" class="btn btn-primary">Salir</a>
        </div>
    </div>
    
    <div class="tabs-container">
        <button class="tab active" onclick="showTab('dashboard')">📊 Dashboard</button>
        <button class="tab" onclick="showTab('resultados')">📝 Resultados</button>
        <button class="tab" onclick="showTab('riesgo')">⚠️ Riesgo</button>
        <button class="tab" onclick="showTab('tripletas')">🎲 Tripletas</button>
        <button class="tab" onclick="showTab('reporte')">📈 Reporte</button>
        <button class="tab" onclick="showTab('historico')">📚 Histórico</button>
        <button class="tab" onclick="showTab('agencias')">🏢 Agencias</button>
        <button class="tab" onclick="showTab('operaciones')">⚙️ Operaciones</button>
    </div>
    
    <div class="content">
        <!-- DASHBOARD -->
        <div id="dashboard" class="tab-content active">
            <div class="info-banner">
                🔥 REGLAS: Animales (00-39) = x35 | Lechuza (40) = x70 | Especiales = x2 | Tripleta = x60
            </div>
            <div class="info-banner">
                ⏰ Zona Horaria Perú (UTC-5): Los resultados son editables hasta 2 horas después del sorteo
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>💰 Ventas</h3>
                    <div class="value" id="dash-ventas">S/0</div>
                </div>
                <div class="stat-card">
                    <h3>🏆 Premios Pagados</h3>
                    <div class="value" id="dash-premios">S/0</div>
                </div>
                <div class="stat-card">
                    <h3>📊 Balance</h3>
                    <div class="value" id="dash-balance">S/0</div>
                </div>
                <div class="stat-card">
                    <h3>🎫 Tickets</h3>
                    <div class="value" id="dash-tickets">0</div>
                </div>
            </div>
            
            <div class="panel">
                <h2>⚡ Acciones Rápidas</h2>
                <div class="quick-actions">
                    <button class="quick-btn btn-success" onclick="showTab('riesgo')">Ver Riesgo</button>
                    <button class="quick-btn btn-warning" onclick="showTab('tripletas')">Ver Tripletas</button>
                </div>
            </div>
        </div>
        
        <!-- RESULTADOS -->
        <div id="resultados" class="tab-content">
            <div class="info-banner">
                🔥 REGLAS: Animales (00-39) = x35 | Lechuza (40) = x70 | Especiales = x2 | Tripleta = x60
            </div>
            
            <div class="panel">
                <h2>🔍 Consultar Resultados</h2>
                <div class="form-row">
                    <div class="form-group">
                        <input type="date" id="res-fecha-consulta" class="form-control">
                    </div>
                    <div class="form-group">
                        <button class="btn btn-success" onclick="consultarResultados()">CONSULTAR</button>
                    </div>
                </div>
                <p style="color: #ffd700; text-align: right;">HOY - <span id="fecha-hoy"></span></p>
            </div>
            
            <div class="panel">
                <h2>📋 Resultados Cargados</h2>
                <div class="info-banner" style="font-size: 11px;">
                    ℹ️ Los resultados solo son editables hasta 2 horas después de su horario de sorteo
                </div>
                <div id="resultados-lista" class="results-list">
                    <!-- Resultados se cargan aquí -->
                </div>
            </div>
            
            <div class="panel">
                <h2>✏️ Cargar/Editar Resultado</h2>
                <div class="form-row">
                    <div class="form-group">
                        <label>Hora Sorteo</label>
                        <select id="res-hora">
                            {% for h in horarios %}
                            <option value="{{ h }}">{{ h }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Animal Ganador</label>
                        <select id="res-animal">
                            {% for num, data in animales.items() %}
                            <option value="{{ num }}">{{ num }} - {{ data.nombre }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>&nbsp;</label>
                        <button class="btn btn-success" onclick="guardarResultado()">GUARDAR</button>
                    </div>
                </div>
                <p style="color: #888; font-size: 11px;">
                    ℹ️ Si el resultado ya existe, se actualizará automáticamente (dentro de la ventana de 2 horas)
                </p>
            </div>
        </div>
        
        <!-- RIESGO -->
        <div id="riesgo" class="tab-content">
            <div class="panel">
                <h2>🏢 Seleccionar Agencia</h2>
                <div class="form-row">
                    <div class="form-group">
                        <select id="riesgo-agencia" onchange="cargarRiesgo()">
                            <option value="">TODAS LAS AGENCIAS</option>
                        </select>
                    </div>
                </div>
                <p style="color: #ffd700;">Mostrando riesgo para: <span id="riesgo-agencia-nombre">TODAS LAS AGENCIAS</span></p>
            </div>
            
            <div class="panel">
                <h2>🎯 Sorteo en Curso / Próximo</h2>
                <div style="text-align: center; padding: 30px;">
                    <div style="font-size: 24px; color: #ffd700;" id="riesgo-sorteo">08:00 AM</div>
                    <p style="color: #888; font-size: 12px;">Riesgo calculado para este horario específico</p>
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>💵 Apuestas</h3>
                    <div class="value" id="riesgo-apuestas">S/0</div>
                </div>
                <div class="stat-card">
                    <h3>⚠️ Riesgo Máx</h3>
                    <div class="value" id="riesgo-max">S/0</div>
                </div>
                <div class="stat-card">
                    <h3>✅ Exposición</h3>
                    <div class="value" id="riesgo-exposicion">0%</div>
                </div>
            </div>
            
            <div class="info-banner" style="background: rgba(255,179,0,0.1); border-color: rgba(255,179,0,0.3);">
                ⚠️ El riesgo se resetea automáticamente cuando cambia el sorteo
            </div>
        </div>
        
        <!-- TRIPLETAS -->
        <div id="tripletas" class="tab-content">
            <div class="panel">
                <h2>🎲 Tripletas de Hoy (Paga x60)</h2>
                <button class="btn btn-secondary" onclick="actualizarTripletas()">🔄 Actualizar</button>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total Tripletas</h3>
                    <div class="value" id="trip-total">0</div>
                </div>
                <div class="stat-card">
                    <h3>Ganadoras</h3>
                    <div class="value" id="trip-ganadoras">0</div>
                </div>
                <div class="stat-card">
                    <h3>Premios</h3>
                    <div class="value" id="trip-premios">S/0</div>
                </div>
            </div>
            
            <div class="panel">
                <h2>📋 Detalle de Tripletas</h2>
                <div id="tripletas-lista">
                    <p style="color: #888; text-align: center; padding: 30px;">Cargando tripletas...</p>
                </div>
            </div>
        </div>
        
        <!-- REPORTE -->
        <div id="reporte" class="tab-content">
            <div class="panel">
                <h2>📊 Generar Reporte</h2>
                <div class="form-row">
                    <div class="form-group">
                        <label>Fecha Inicio</label>
                        <input type="date" id="rep-inicio">
                    </div>
                    <div class="form-group">
                        <label>Fecha Fin</label>
                        <input type="date" id="rep-fin">
                    </div>
                    <div class="form-group">
                        <label>Agencia</label>
                        <select id="rep-agencia">
                            <option value="">Todas</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>&nbsp;</label>
                        <button class="btn btn-success" onclick="generarReporte()">GENERAR</button>
                    </div>
                </div>
            </div>
            
            <div id="reporte-resultado"></div>
        </div>
        
        <!-- HISTORICO -->
        <div id="historico" class="tab-content">
            <div class="panel">
                <h2>📚 Consulta Histórica</h2>
                <div class="form-row">
                    <div class="form-group">
                        <input type="date" id="hist-fecha" class="form-control">
                    </div>
                    <div class="form-group">
                        <button class="btn btn-success" onclick="consultarHistorico()">CONSULTAR</button>
                    </div>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 10px;">
                    <button class="btn btn-secondary btn-small" onclick="setHistFecha('ayer')">Ayer</button>
                    <button class="btn btn-secondary btn-small" onclick="setHistFecha('7dias')">7 días</button>
                    <button class="btn btn-secondary btn-small" onclick="setHistFecha('mes')">Mes</button>
                </div>
            </div>
            
            <div id="historico-resultado"></div>
        </div>
        
        <!-- AGENCIAS -->
        <div id="agencias" class="tab-content">
            <div class="panel">
                <h2>➕ Crear Nueva Agencia</h2>
                <div class="form-row">
                    <div class="form-group">
                        <input type="text" id="ag-codigo" placeholder="Código de agencia">
                    </div>
                    <div class="form-group">
                        <input type="text" id="ag-nombre" placeholder="Nombre de la Agencia">
                    </div>
                    <div class="form-group">
                        <input type="number" id="ag-comision" placeholder="Comisión %" value="15">
                    </div>
                    <div class="form-group">
                        <button class="btn btn-success" onclick="crearAgencia()">CREAR AGENCIA</button>
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <h2>🏢 Agencias Existentes</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Código</th>
                            <th>Nombre</th>
                            <th>Comisión</th>
                            <th>Acciones</th>
                        </tr>
                    </thead>
                    <tbody id="agencias-lista">
                        <!-- Agencias se cargan aquí -->
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- OPERACIONES -->
        <div id="operaciones" class="tab-content">
            <div class="panel">
                <h2>💰 Pagar Ticket</h2>
                <div class="form-row">
                    <div class="form-group">
                        <input type="text" id="pagar-serial" placeholder="Ingrese SERIAL del ticket">
                    </div>
                    <div class="form-group">
                        <button class="btn btn-success" onclick="verificarYPagar()">VERIFICAR Y PAGAR</button>
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <h2>❌ Anular Ticket</h2>
                <div class="form-row">
                    <div class="form-group">
                        <input type="text" id="anular-serial" placeholder="Ingrese SERIAL del ticket">
                    </div>
                    <div class="form-group">
                        <button class="btn btn-danger" onclick="anularTicket()">ANULAR</button>
                    </div>
                </div>
                <p style="color: #888; font-size: 11px;">
                    ⚠️ Solo se pueden anular tickets que no estén pagados y cuyo sorteo no haya iniciado.
                </p>
            </div>
        </div>
    </div>
    
    <script>
        // Inicializar
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('fecha-hoy').textContent = new Date().toLocaleDateString('es-PE');
            document.getElementById('res-fecha-consulta').valueAsDate = new Date();
            document.getElementById('rep-inicio').valueAsDate = new Date();
            document.getElementById('rep-fin').valueAsDate = new Date();
            document.getElementById('hist-fecha').valueAsDate = new Date();
            
            cargarDashboard();
            cargarAgenciasSelect();
            cargarResultados();
        });
        
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
            
            if (tabName === 'dashboard') cargarDashboard();
            if (tabName === 'resultados') cargarResultados();
            if (tabName === 'agencias') cargarAgencias();
            if (tabName === 'tripletas') actualizarTripletas();
        }
        
        function cargarDashboard() {
            fetch('/api/admin/dashboard')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('dash-ventas').textContent = 'S/' + data.ventas.toFixed(0);
                        document.getElementById('dash-premios').textContent = 'S/' + data.premios.toFixed(0);
                        document.getElementById('dash-balance').textContent = 'S/' + (data.ventas - data.premios).toFixed(0);
                        document.getElementById('dash-tickets').textContent = data.tickets;
                    }
                });
        }
        
        function cargarResultados() {
            const fecha = document.getElementById('res-fecha-consulta').value;
            fetch('/api/resultados?fecha=' + fecha)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const container = document.getElementById('resultados-lista');
                        if (data.resultados.length === 0) {
                            container.innerHTML = '<p style="color: #888; text-align: center;">No hay resultados registrados</p>';
                            return;
                        }
                        container.innerHTML = data.resultados.map(r => {
                            const animal = {{ animales | tojson }}[r.animal_ganador];
                            return `
                                <div class="result-item">
                                    <div class="result-time">${r.hora_sorteo}</div>
                                    <div class="result-animal">
                                        <div class="animal-number ${animal.color}">${r.animal_ganador}</div>
                                        <span>${animal.nombre}</span>
                                    </div>
                                    <button class="btn btn-warning btn-small" onclick="editarResultado('${r.id}', '${r.hora_sorteo}')">Editar</button>
                                </div>
                            `;
                        }).join('');
                    }
                });
        }
        
        function consultarResultados() {
            cargarResultados();
        }
        
        function guardarResultado() {
            const hora = document.getElementById('res-hora').value;
            const animal = document.getElementById('res-animal').value;
            const fecha = document.getElementById('res-fecha-consulta').value;
            
            fetch('/api/resultados', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fecha: fecha, hora_sorteo: hora, animal_ganador: animal })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Resultado guardado exitosamente');
                    cargarResultados();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function editarResultado(id, hora) {
            const nuevoAnimal = prompt('Editar animal para ' + hora + ' (0-40):');
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
                    cargarResultados();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function cargarAgenciasSelect() {
            fetch('/api/admin/agencias')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const select = document.getElementById('riesgo-agencia');
                        const selectRep = document.getElementById('rep-agencia');
                        data.agencias.forEach(a => {
                            select.innerHTML += `<option value="${a.codigo}">${a.nombre}</option>`;
                            selectRep.innerHTML += `<option value="${a.codigo}">${a.nombre}</option>`;
                        });
                    }
                });
        }
        
        function cargarAgencias() {
            fetch('/api/admin/agencias')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const tbody = document.getElementById('agencias-lista');
                        tbody.innerHTML = data.agencias.map(a => `
                            <tr>
                                <td>${a.id}</td>
                                <td>${a.codigo}</td>
                                <td>${a.nombre}</td>
                                <td>${a.comision}%</td>
                                <td class="actions-cell">
                                    <button class="btn btn-warning btn-small">Editar</button>
                                </td>
                            </tr>
                        `).join('');
                    }
                });
        }
        
        function crearAgencia() {
            const codigo = document.getElementById('ag-codigo').value;
            const nombre = document.getElementById('ag-nombre').value;
            const comision = document.getElementById('ag-comision').value;
            
            if (!codigo || !nombre) {
                alert('Complete todos los campos');
                return;
            }
            
            fetch('/api/admin/agencias', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ codigo, nombre, comision })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Agencia creada exitosamente');
                    cargarAgencias();
                    cargarAgenciasSelect();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function cargarRiesgo() {
            const agencia = document.getElementById('riesgo-agencia').value;
            document.getElementById('riesgo-agencia-nombre').textContent = agencia || 'TODAS LAS AGENCIAS';
            
            fetch('/api/admin/riesgo?agencia=' + agencia)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('riesgo-apuestas').textContent = 'S/' + data.apuestas.toFixed(0);
                        document.getElementById('riesgo-max').textContent = 'S/' + data.riesgo_max.toFixed(0);
                        document.getElementById('riesgo-exposicion').textContent = data.exposicion + '%';
                    }
                });
        }
        
        function actualizarTripletas() {
            fetch('/api/admin/tripletas')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('trip-total').textContent = data.total;
                        document.getElementById('trip-ganadoras').textContent = data.ganadoras;
                        document.getElementById('trip-premios').textContent = 'S/' + data.premios.toFixed(0);
                        
                        const container = document.getElementById('tripletas-lista');
                        if (data.tripletas.length === 0) {
                            container.innerHTML = '<p style="color: #888; text-align: center;">No hay tripletas registradas</p>';
                            return;
                        }
                        // Mostrar detalle de tripletas
                    }
                });
        }
        
        function generarReporte() {
            const inicio = document.getElementById('rep-inicio').value;
            const fin = document.getElementById('rep-fin').value;
            const agencia = document.getElementById('rep-agencia').value;
            
            fetch(`/api/admin/reporte?inicio=${inicio}&fin=${fin}&agencia=${agencia}`)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('reporte-resultado').innerHTML = `
                            <div class="stats-grid">
                                <div class="stat-card">
                                    <h3>Ventas</h3>
                                    <div class="value">S/${data.totales.ventas.toFixed(0)}</div>
                                </div>
                                <div class="stat-card">
                                    <h3>Premios</h3>
                                    <div class="value">S/${data.totales.premios.toFixed(0)}</div>
                                </div>
                                <div class="stat-card">
                                    <h3>Tickets</h3>
                                    <div class="value">${data.totales.tickets}</div>
                                </div>
                                <div class="stat-card">
                                    <h3>Balance</h3>
                                    <div class="value">S/${data.totales.balance.toFixed(0)}</div>
                                </div>
                            </div>
                        `;
                    }
                });
        }
        
        function verificarYPagar() {
            const serial = document.getElementById('pagar-serial').value;
            if (!serial) return;
            
            fetch('/api/tickets/pagar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Ticket pagado exitosamente');
                    document.getElementById('pagar-serial').value = '';
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function anularTicket() {
            const serial = document.getElementById('anular-serial').value;
            if (!serial) return;
            
            if (!confirm('¿Está seguro de anular este ticket?')) return;
            
            fetch('/api/tickets/anular', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Ticket anulado exitosamente');
                    document.getElementById('anular-serial').value = '';
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function setHistFecha(tipo) {
            const hoy = new Date();
            if (tipo === 'ayer') {
                hoy.setDate(hoy.getDate() - 1);
                document.getElementById('hist-fecha').valueAsDate = hoy;
            } else if (tipo === '7dias') {
                // Lógica para 7 días
            }
        }
        
        function consultarHistorico() {
            const fecha = document.getElementById('hist-fecha').value;
            // Implementar consulta histórica
        }
        
        // Auto refresh dashboard cada 30 segundos
        setInterval(() => {
            if (document.getElementById('dashboard').classList.contains('active')) {
                cargarDashboard();
            }
        }, 30000);
    </script>
</body>
</html>
"""


# ============================================================================
# TEMPLATE POS (PANEL DE VENTAS)
# ============================================================================
POS_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agencia {{ session.agencia_nombre }} - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0d0d1a 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
        }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #ffd700;
        }
        .header-left {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .logo {
            color: #ffd700;
            font-size: 1.2em;
            font-weight: bold;
        }
        .header-info {
            display: flex;
            gap: 15px;
            font-size: 12px;
            color: #aaa;
        }
        .menu-container {
            display: flex;
            gap: 20px;
        }
        .menu-item {
            position: relative;
        }
        .menu-btn {
            background: transparent;
            border: none;
            color: #fff;
            cursor: pointer;
            font-size: 13px;
            padding: 5px 10px;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .menu-btn:hover { color: #ffd700; }
        .dropdown {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            background: #1a1a2e;
            border: 1px solid rgba(255,215,0,0.3);
            border-radius: 8px;
            min-width: 200px;
            z-index: 100;
        }
        .menu-item:hover .dropdown { display: block; }
        .dropdown-item {
            padding: 10px 15px;
            color: #fff;
            font-size: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .dropdown-item:hover { background: rgba(255,215,0,0.1); color: #ffd700; }
        
        /* Filtros */
        .filters {
            display: flex;
            gap: 10px;
            padding: 10px 20px;
            background: rgba(0,0,0,0.2);
        }
        .filter-btn {
            padding: 8px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            font-size: 12px;
            transition: all 0.3s ease;
        }
        .filter-btn.rojo { background: linear-gradient(135deg, #ff5252, #d32f2f); color: #fff; }
        .filter-btn.negro { background: linear-gradient(135deg, #444, #222); color: #fff; }
        .filter-btn.par { background: linear-gradient(135deg, #00bcd4, #0097a7); color: #fff; }
        .filter-btn.impar { background: linear-gradient(135deg, #9c27b0, #7b1fa2); color: #fff; }
        .filter-btn:hover { transform: scale(1.05); }
        .filter-btn.active { box-shadow: 0 0 15px currentColor; }
        
        /* Main Content */
        .main-content {
            display: grid;
            grid-template-columns: 1fr 320px;
            gap: 15px;
            padding: 15px;
        }
        
        /* Grid de Animalitos */
        .animals-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
        }
        .animal-card {
            aspect-ratio: 1;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 2px solid transparent;
            position: relative;
        }
        .animal-card:hover { transform: scale(1.05); }
        .animal-card.selected { 
            border-color: #ffd700; 
            box-shadow: 0 0 20px rgba(255,215,0,0.5);
        }
        .animal-card.rojo { background: linear-gradient(135deg, rgba(255,82,82,0.3), rgba(211,47,47,0.3)); }
        .animal-card.negro { background: linear-gradient(135deg, rgba(68,68,68,0.3), rgba(34,34,34,0.3)); }
        .animal-card.hidden { display: none; }
        
        .animal-number {
            font-size: 24px;
            font-weight: bold;
            color: #fff;
        }
        .animal-name {
            font-size: 11px;
            color: #aaa;
            text-align: center;
        }
        .animal-card.selected .animal-name { color: #ffd700; }
        
        /* Sidebar */
        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        /* Horarios */
        .horarios-container {
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-bottom: 10px;
        }
        .horario-btn {
            padding: 6px 10px;
            border: 1px solid #444;
            border-radius: 4px;
            background: rgba(0,0,0,0.3);
            color: #aaa;
            font-size: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .horario-btn:hover { border-color: #ffd700; color: #ffd700; }
        .horario-btn.active { 
            background: linear-gradient(135deg, #00c853, #00a344); 
            color: #fff;
            border-color: #00c853;
        }
        
        /* Ticket Preview */
        .ticket-preview {
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,215,0,0.2);
            border-radius: 10px;
            padding: 15px;
            flex: 1;
        }
        .ticket-preview h3 {
            color: #ffd700;
            font-size: 14px;
            margin-bottom: 10px;
            text-align: center;
        }
        .ticket-items {
            max-height: 200px;
            overflow-y: auto;
            margin-bottom: 10px;
        }
        .ticket-item {
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            font-size: 12px;
        }
        .ticket-total {
            display: flex;
            justify-content: space-between;
            padding-top: 10px;
            border-top: 2px solid rgba(255,215,0,0.3);
            font-weight: bold;
            color: #ffd700;
        }
        
        /* Botones de Acción */
        .action-buttons {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }
        .action-btn {
            padding: 12px;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
        }
        .action-btn:hover { transform: translateY(-2px); }
        .action-btn.full { grid-column: span 2; }
        
        .btn-agregar { background: linear-gradient(135deg, #00c853, #00a344); color: #fff; }
        .btn-whatsapp { background: linear-gradient(135deg, #00bcd4, #0097a7); color: #fff; }
        .btn-resultados { background: linear-gradient(135deg, #ff9800, #f57c00); color: #fff; }
        .btn-caja { background: linear-gradient(135deg, #9c27b0, #7b1fa2); color: #fff; }
        .btn-pagar { background: linear-gradient(135deg, #4caf50, #388e3c); color: #fff; }
        .btn-tripleta { background: linear-gradient(135deg, #ffeb3b, #fbc02d); color: #000; }
        .btn-anular { background: linear-gradient(135deg, #ff5252, #d32f2f); color: #fff; }
        .btn-borrar { background: linear-gradient(135deg, #607d8b, #455a64); color: #fff; }
        .btn-cerrar { background: linear-gradient(135deg, #795548, #5d4037); color: #fff; }
        
        /* Monto Input */
        .monto-container {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
        }
        .monto-label {
            color: #ffd700;
            font-weight: bold;
        }
        .monto-input {
            flex: 1;
            padding: 10px;
            border: 1px solid #444;
            border-radius: 6px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 18px;
            text-align: center;
        }
        
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border: 1px solid rgba(255,215,0,0.3);
            border-radius: 12px;
            padding: 25px;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .modal-header h3 { color: #ffd700; }
        .close-btn {
            background: #ff5252;
            border: none;
            color: #fff;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 16px;
        }
        
        /* Responsive */
        @media (max-width: 900px) {
            .main-content { grid-template-columns: 1fr; }
            .animals-grid { grid-template-columns: repeat(4, 1fr); }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <div class="logo">🎰 {{ session.agencia_nombre }}</div>
            <div class="header-info">
                <span>📅 {{ fecha_actual }}</span>
                <span>⏰ {{ hora_actual }}</span>
            </div>
        </div>
        <div class="menu-container">
            <div class="menu-item">
                <button class="menu-btn">📁 Archivo</button>
                <div class="dropdown">
                    <div class="dropdown-item" onclick="mostrarCajaDelDia()">💰 Caja del Día</div>
                    <div class="dropdown-item" onclick="mostrarHistorialCaja()">📊 Historial de Caja</div>
                    <div class="dropdown-item" onclick="mostrarCalculadora()">🧮 Calculadora de Premios</div>
                </div>
            </div>
            <div class="menu-item">
                <button class="menu-btn">🔍 Consultas</button>
                <div class="dropdown">
                    <div class="dropdown-item" onclick="mostrarMisTickets()">🎫 Mis Tickets Vendidos</div>
                    <div class="dropdown-item" onclick="mostrarBuscarTicket()">🔎 Buscar Ticket por Serial</div>
                    <div class="dropdown-item" onclick="mostrarTicketsPorCobrar()">💵 Tickets por Cobrar</div>
                    <div class="dropdown-item" onclick="mostrarResultadosHoy()">🏆 Resultados de Hoy</div>
                </div>
            </div>
            <div class="menu-item">
                <button class="menu-btn">❓ Ayuda</button>
                <div class="dropdown">
                    <div class="dropdown-item" onclick="mostrarAyuda()">📖 Manual de Usuario</div>
                    <div class="dropdown-item" onclick="mostrarReglas()">📋 Reglas del Juego</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="filters">
        <button class="filter-btn rojo active" onclick="filtrarAnimales('rojo')">ROJO</button>
        <button class="filter-btn negro active" onclick="filtrarAnimales('negro')">NEGRO</button>
        <button class="filter-btn par active" onclick="filtrarAnimales('par')">PAR</button>
        <button class="filter-btn impar active" onclick="filtrarAnimales('impar')">IMPAR</button>
    </div>
    
    <div class="main-content">
        <div class="animals-grid" id="animals-grid">
            {% for num, data in animales.items() %}
            <div class="animal-card {{ data.color }}" 
                 data-number="{{ num }}" 
                 data-name="{{ data.nombre }}"
                 data-color="{{ data.color }}"
                 onclick="seleccionarAnimal({{ num }}, '{{ data.nombre }}')">
                <div class="animal-number">{{ num }}</div>
                <div class="animal-name">{{ data.nombre }}</div>
            </div>
            {% endfor %}
        </div>
        
        <div class="sidebar">
            <div class="horarios-container" id="horarios-container">
                {% for h in horarios %}
                <button class="horario-btn" onclick="seleccionarHorario('{{ h }}')" data-hora="{{ h }}">{{ h }}</button>
                {% endfor %}
            </div>
            
            <div class="monto-container">
                <span class="monto-label">S/</span>
                <input type="number" class="monto-input" id="monto" placeholder="0.00" step="0.5" min="0.5">
            </div>
            
            <div class="ticket-preview">
                <h3>🎫 TICKET</h3>
                <div class="ticket-items" id="ticket-items">
                    <p style="color: #888; text-align: center; font-size: 12px;">Selecciona animales y horarios...</p>
                </div>
                <div class="ticket-total">
                    <span>TOTAL:</span>
                    <span id="ticket-total">S/0.00</span>
                </div>
            </div>
            
            <div class="action-buttons">
                <button class="action-btn btn-agregar full" onclick="agregarAlTicket()">AGREGAR AL TICKET</button>
                <button class="action-btn btn-whatsapp full" onclick="enviarPorWhatsApp()">ENVIAR POR WHATSAPP</button>
                <button class="action-btn btn-resultados" onclick="mostrarResultados()">RESULTADOS</button>
                <button class="action-btn btn-caja" onclick="mostrarCaja()">CAJA</button>
                <button class="action-btn btn-pagar" onclick="pagarTicket()">PAGAR</button>
                <button class="action-btn btn-tripleta" onclick="activarTripleta()">TRIPLETA</button>
                <button class="action-btn btn-anular" onclick="anularTicket()">ANULAR</button>
                <button class="action-btn btn-borrar" onclick="borrarTodo()">BORRAR TODO</button>
                <button class="action-btn btn-cerrar full" onclick="cerrarSesion()">CERRAR SESIÓN</button>
            </div>
        </div>
    </div>
    
    <!-- Modal -->
    <div class="modal" id="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modal-title">Título</h3>
                <button class="close-btn" onclick="cerrarModal()">×</button>
            </div>
            <div id="modal-body"></div>
        </div>
    </div>
    
    <script>
        let animalesSeleccionados = [];
        let horarioSeleccionado = null;
        let modoTripleta = false;
        let ticketItems = [];
        
        // Inicializar
        document.addEventListener('DOMContentLoaded', function() {
            // Seleccionar primer horario por defecto
            const primerHorario = document.querySelector('.horario-btn');
            if (primerHorario) seleccionarHorario(primerHorario.dataset.hora);
        });
        
        function filtrarAnimales(tipo) {
            const btn = event.target;
            btn.classList.toggle('active');
            
            const mostrarRojo = document.querySelector('.filter-btn.rojo').classList.contains('active');
            const mostrarNegro = document.querySelector('.filter-btn.negro').classList.contains('active');
            const mostrarPar = document.querySelector('.filter-btn.par').classList.contains('active');
            const mostrarImpar = document.querySelector('.filter-btn.impar').classList.contains('active');
            
            document.querySelectorAll('.animal-card').forEach(card => {
                const color = card.dataset.color;
                const numero = parseInt(card.dataset.number);
                const esPar = numero % 2 === 0;
                
                let mostrar = true;
                if (!mostrarRojo && color === 'rojo') mostrar = false;
                if (!mostrarNegro && color === 'negro') mostrar = false;
                if (!mostrarPar && esPar) mostrar = false;
                if (!mostrarImpar && !esPar) mostrar = false;
                
                card.classList.toggle('hidden', !mostrar);
            });
        }
        
        function seleccionarAnimal(num, nombre) {
            const card = document.querySelector(`.animal-card[data-number="${num}"]`);
            
            if (modoTripleta) {
                // Modo tripleta - permitir hasta 3 animales
                const index = animalesSeleccionados.findIndex(a => a.num === num);
                if (index > -1) {
                    animalesSeleccionados.splice(index, 1);
                    card.classList.remove('selected');
                } else {
                    if (animalesSeleccionados.length >= 3) {
                        alert('Solo puedes seleccionar 3 animales para una tripleta');
                        return;
                    }
                    animalesSeleccionados.push({ num, nombre });
                    card.classList.add('selected');
                }
            } else {
                // Modo normal - solo 1 animal
                document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('selected'));
                animalesSeleccionados = [{ num, nombre }];
                card.classList.add('selected');
            }
            
            actualizarPreview();
        }
        
        function seleccionarHorario(hora) {
            horarioSeleccionado = hora;
            document.querySelectorAll('.horario-btn').forEach(h => h.classList.remove('active'));
            document.querySelector(`.horario-btn[data-hora="${hora}"]`).classList.add('active');
            actualizarPreview();
        }
        
        function actualizarPreview() {
            const container = document.getElementById('ticket-items');
            
            if (animalesSeleccionados.length === 0 || !horarioSeleccionado) {
                container.innerHTML = '<p style="color: #888; text-align: center; font-size: 12px;">Selecciona animales y horarios...</p>';
                document.getElementById('ticket-total').textContent = 'S/0.00';
                return;
            }
            
            const monto = parseFloat(document.getElementById('monto').value) || 0;
            const tipo = modoTripleta ? 'Tripleta (x60)' : 'Directo (x35)';
            const multiplicador = modoTripleta ? 60 : 35;
            const premio = monto * multiplicador;
            
            let html = '';
            animalesSeleccionados.forEach(a => {
                html += `<div class="ticket-item">
                    <span>${a.num} - ${a.nombre}</span>
                    <span>S/${monto.toFixed(2)}</span>
                </div>`;
            });
            html += `<div class="ticket-item" style="color: #ffd700;">
                <span>${tipo} - ${horarioSeleccionado}</span>
                <span>Posible: S/${premio.toFixed(2)}</span>
            </div>`;
            
            container.innerHTML = html;
            document.getElementById('ticket-total').textContent = 'S/' + monto.toFixed(2);
        }
        
        function agregarAlTicket() {
            const monto = parseFloat(document.getElementById('monto').value);
            
            if (animalesSeleccionados.length === 0) {
                alert('Selecciona al menos un animal');
                return;
            }
            if (!horarioSeleccionado) {
                alert('Selecciona un horario');
                return;
            }
            if (!monto || monto <= 0) {
                alert('Ingresa un monto válido');
                return;
            }
            
            // Agregar al ticket
            ticketItems.push({
                animales: [...animalesSeleccionados],
                horario: horarioSeleccionado,
                monto: monto,
                tipo: modoTripleta ? 'tripleta' : 'directo'
            });
            
            // Limpiar selección
            animalesSeleccionados = [];
            document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('selected'));
            
            actualizarTicketFinal();
            alert('Agregado al ticket');
        }
        
        function actualizarTicketFinal() {
            const container = document.getElementById('ticket-items');
            let total = 0;
            let html = '';
            
            ticketItems.forEach((item, idx) => {
                const animalesStr = item.animales.map(a => `${a.num}-${a.nombre}`).join(', ');
                html += `<div class="ticket-item">
                    <span>${item.tipo.toUpperCase()}: ${animalesStr} (${item.horario})</span>
                    <span>S/${item.monto.toFixed(2)}</span>
                </div>`;
                total += item.monto;
            });
            
            container.innerHTML = html || '<p style="color: #888; text-align: center; font-size: 12px;">Selecciona animales y horarios...</p>';
            document.getElementById('ticket-total').textContent = 'S/' + total.toFixed(2);
        }
        
        function activarTripleta() {
            modoTripleta = !modoTripleta;
            const btn = event.target;
            
            if (modoTripleta) {
                btn.style.background = 'linear-gradient(135deg, #ffd700, #ffaa00)';
                btn.textContent = 'TRIPLETA (ACTIVADO)';
            } else {
                btn.style.background = 'linear-gradient(135deg, #ffeb3b, #fbc02d)';
                btn.textContent = 'TRIPLETA';
            }
            
            // Limpiar selección
            animalesSeleccionados = [];
            document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('selected'));
            actualizarPreview();
        }
        
        function borrarTodo() {
            animalesSeleccionados = [];
            ticketItems = [];
            document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('selected'));
            document.getElementById('monto').value = '';
            actualizarPreview();
        }
        
        function procesarVenta() {
            if (ticketItems.length === 0) {
                alert('No hay items en el ticket');
                return;
            }
            
            fetch('/api/venta', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items: ticketItems })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Ticket generado: ' + data.serial);
                    imprimirTicket(data.ticket);
                    borrarTodo();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function imprimirTicket(ticket) {
            const ventana = window.open('', '_blank');
            let html = `<html><head><style>
                body { font-family: monospace; width: 80mm; margin: 0; padding: 10px; }
                .center { text-align: center; }
                .line { border-top: 1px dashed #000; margin: 10px 0; }
                .bold { font-weight: bold; }
            </style></head><body>
                <div class="center bold">ZOOLO CASINO</div>
                <div class="center">{{ session.agencia_nombre }}</div>
                <div class="line"></div>
                <div>Ticket: ${ticket.serial}</div>
                <div>Fecha: ${new Date().toLocaleString()}</div>
                <div class="line"></div>
                <div class="bold">APUESTAS:</div>`;
            
            ticket.items.forEach(item => {
                const animales = item.animales.map(a => a.num).join('-');
                html += `<div>${item.tipo}: ${animales} - S/${item.monto}</div>`;
            });
            
            html += `<div class="line"></div>
                <div class="bold">Total: S/${ticket.total}</div>
                <div class="center" style="margin-top: 20px;">Buena Suerte!</div>
            </body></html>`;
            
            ventana.document.write(html);
            ventana.document.close();
            ventana.print();
        }
        
        function enviarPorWhatsApp() {
            if (ticketItems.length === 0) {
                alert('No hay items en el ticket');
                return;
            }
            // Implementar envío por WhatsApp
            alert('Función de WhatsApp en desarrollo');
        }
        
        function mostrarResultados() {
            fetch('/api/resultados?fecha=hoy')
                .then(r => r.json())
                .then(data => {
                    let html = '<div style="max-height: 300px; overflow-y: auto;">';
                    if (data.resultados) {
                        data.resultados.forEach(r => {
                            html += `<div style="padding: 8px; border-bottom: 1px solid #444;">
                                <strong>${r.hora_sorteo}</strong> - ${r.animal_ganador} 
                            </div>`;
                        });
                    }
                    html += '</div>';
                    mostrarModal('Resultados de Hoy', html);
                });
        }
        
        function mostrarCaja() {
            mostrarModal('Caja', '<p>Función en desarrollo</p>');
        }
        
        function pagarTicket() {
            const serial = prompt('Ingrese el SERIAL del ticket a pagar:');
            if (!serial) return;
            
            fetch('/api/tickets/pagar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Ticket pagado exitosamente');
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function anularTicket() {
            const serial = prompt('Ingrese el SERIAL del ticket a anular:');
            if (!serial) return;
            
            if (!confirm('¿Está seguro de anular este ticket?')) return;
            
            fetch('/api/tickets/anular', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Ticket anulado exitosamente');
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function mostrarMisTickets() {
            mostrarModal('Mis Tickets Vendidos', `
                <div class="form-row">
                    <input type="date" id="tickets-fecha-inicio" value="{{ fecha_iso }}">
                    <input type="date" id="tickets-fecha-fin" value="{{ fecha_iso }}">
                    <select id="tickets-filtro">
                        <option value="todos">Todos</option>
                        <option value="pagados">Pagados</option>
                        <option value="pendientes">Pendientes</option>
                    </select>
                </div>
                <button class="btn btn-success" onclick="buscarMisTickets()" style="width: 100%; margin-top: 10px;">BUSCAR</button>
                <div id="mis-tickets-result"></div>
            `);
        }
        
        function buscarMisTickets() {
            const inicio = document.getElementById('tickets-fecha-inicio').value;
            const fin = document.getElementById('tickets-fecha-fin').value;
            
            fetch(`/api/tickets?inicio=${inicio}&fin=${fin}`)
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('mis-tickets-result');
                    if (data.tickets && data.tickets.length > 0) {
                        let html = '<table style="width: 100%; margin-top: 15px;"><tr><th>Serial</th><th>Fecha</th><th>Total</th><th>Estado</th></tr>';
                        data.tickets.forEach(t => {
                            html += `<tr><td>${t.serial}</td><td>${t.fecha}</td><td>S/${t.total}</td><td>${t.estado}</td></tr>`;
                        });
                        html += '</table>';
                        container.innerHTML = html;
                    } else {
                        container.innerHTML = '<p style="color: #888; text-align: center; margin-top: 20px;">No se encontraron tickets</p>';
                    }
                });
        }
        
        function mostrarBuscarTicket() {
            const serial = prompt('Ingrese el SERIAL del ticket:');
            if (!serial) return;
            
            fetch('/api/tickets/' + serial)
                .then(r => r.json())
                .then(data => {
                    if (data.ticket) {
                        mostrarModal('Ticket Encontrado', `
                            <p><strong>Serial:</strong> ${data.ticket.serial}</p>
                            <p><strong>Fecha:</strong> ${data.ticket.fecha}</p>
                            <p><strong>Total:</strong> S/${data.ticket.total}</p>
                            <p><strong>Estado:</strong> ${data.ticket.estado}</p>
                        `);
                    } else {
                        alert('Ticket no encontrado');
                    }
                });
        }
        
        function mostrarTicketsPorCobrar() {
            mostrarModal('Tickets por Cobrar', '<p>Función en desarrollo</p>');
        }
        
        function mostrarResultadosHoy() {
            mostrarResultados();
        }
        
        function mostrarCajaDelDia() {
            mostrarModal('Caja del Día', '<p>Función en desarrollo</p>');
        }
        
        function mostrarHistorialCaja() {
            mostrarModal('Historial de Caja', '<p>Función en desarrollo</p>');
        }
        
        function mostrarCalculadora() {
            mostrarModal('Calculadora de Premios', '<p>Función en desarrollo</p>');
        }
        
        function mostrarAyuda() {
            mostrarModal('Ayuda', '<p>Manual de usuario en desarrollo</p>');
        }
        
        function mostrarReglas() {
            mostrarModal('Reglas del Juego', `
                <p><strong>Animales (00-39):</strong> Paga x35</p>
                <p><strong>Lechuza (40):</strong> Paga x70</p>
                <p><strong>Especiales:</strong> Paga x2</p>
                <p><strong>Tripleta:</strong> Paga x60</p>
            `);
        }
        
        function mostrarModal(titulo, contenido) {
            document.getElementById('modal-title').textContent = titulo;
            document.getElementById('modal-body').innerHTML = contenido;
            document.getElementById('modal').classList.add('active');
        }
        
        function cerrarModal() {
            document.getElementById('modal').classList.remove('active');
        }
        
        function cerrarSesion() {
            if (confirm('¿Desea cerrar sesión?')) {
                window.location.href = '{{ url_for('logout') }}';
            }
        }
        
        // Cerrar modal al hacer clic fuera
        document.getElementById('modal').addEventListener('click', function(e) {
            if (e.target === this) cerrarModal();
        });
    </script>
</body>
</html>
"""


# ============================================================================
# RUTAS DE LA APLICACIÓN
# ============================================================================

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
        
        # Verificar credenciales en Supabase
        usuarios = supabase_request("usuarios", filters={"username": username, "__limit": 1})
        
        if usuarios and len(usuarios) > 0:
            usuario = usuarios[0]
            # Verificar contraseña (en producción usar hash)
            if usuario.get('password') == password:
                session['user_id'] = usuario['id']
                session['username'] = usuario['username']
                session['nombre'] = usuario['nombre']
                session['es_admin'] = usuario.get('es_admin', False)
                session['agencia'] = usuario.get('agencia_codigo', 'SIN_AGENCIA')
                session['agencia_nombre'] = usuario.get('agencia_nombre', 'Sin Agencia')
                
                if usuario.get('es_admin', False):
                    return redirect(url_for('admin'))
                return redirect(url_for('pos'))
        
        flash("Usuario o contraseña incorrectos", "error")
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def admin():
    return render_template_string(ADMIN_TEMPLATE, 
                                  animales=ANIMALES, 
                                  horarios=HORARIOS_SORTEO)

@app.route('/pos')
@login_required
def pos():
    ahora = ahora_peru()
    return render_template_string(POS_TEMPLATE, 
                                  animales=ANIMALES,
                                  horarios=HORARIOS_SORTEO,
                                  fecha_actual=ahora.strftime("%d/%m/%Y"),
                                  fecha_iso=ahora.strftime("%Y-%m-%d"),
                                  hora_actual=ahora.strftime("%I:%M %p"))

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/venta', methods=['POST'])
@login_required
def api_venta():
    try:
        data = request.json
        items = data.get('items', [])
        
        if not items:
            return jsonify({"success": False, "error": "No hay items en el ticket"})
        
        # Calcular total
        total = sum(item.get('monto', 0) for item in items)
        
        # Generar serial
        serial = generar_serial()
        fecha_actual = ahora_peru()
        fecha_str = fecha_actual.strftime("%d/%m/%Y")
        hora_str = fecha_actual.strftime("%H:%M:%S")
        
        # Crear ticket en Supabase
        ticket_data = {
            "serial": serial,
            "fecha": fecha_str,
            "hora": hora_str,
            "agencia_codigo": session.get('agencia', 'SIN_AGENCIA'),
            "agencia_nombre": session.get('agencia_nombre', 'Sin Agencia'),
            "vendedor_id": session.get('user_id'),
            "vendedor_nombre": session.get('nombre'),
            "items": json.dumps(items),
            "total": total,
            "estado": "activo",
            "creado_en": fecha_actual.isoformat()
        }
        
        resultado = supabase_request("tickets", method="POST", data=ticket_data)
        
        if resultado:
            return jsonify({
                "success": True,
                "serial": serial,
                "ticket": {
                    "serial": serial,
                    "items": items,
                    "total": total
                }
            })
        else:
            return jsonify({"success": False, "error": "Error al guardar el ticket"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/tickets')
@login_required
def api_get_tickets():
    try:
        fecha = request.args.get('fecha')
        inicio = request.args.get('inicio')
        fin = request.args.get('fin')
        
        filters = {"__limit": 5000, "__order": "creado_en.desc"}
        
        if not session.get('es_admin', False):
            filters["vendedor_id"] = session.get('user_id')
        
        if fecha:
            filters["fecha"] = fecha
        
        tickets = supabase_request("tickets", filters=filters)
        
        if tickets is None:
            tickets = []
        
        # Filtrar por rango si se especifica
        if inicio and fin:
            tickets = [t for t in tickets if inicio <= t.get('fecha', '') <= fin]
        
        return jsonify({"success": True, "tickets": tickets})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/tickets/<serial>')
@login_required
def api_get_ticket(serial):
    try:
        tickets = supabase_request("tickets", filters={"serial": serial, "__limit": 1})
        
        if tickets and len(tickets) > 0:
            return jsonify({"success": True, "ticket": tickets[0]})
        else:
            return jsonify({"success": False, "error": "Ticket no encontrado"})
    
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
            return jsonify({"success": False, "error": "El ticket no está activo"})
        
        resultado = supabase_request(
            "tickets",
            method="PATCH",
            data={
                "estado": "pagado",
                "pagado_en": ahora_peru().isoformat(),
                "pagado_por": session.get('nombre')
            },
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
            data={
                "estado": "anulado",
                "anulado_en": ahora_peru().isoformat(),
                "anulado_por": session.get('nombre')
            },
            filters={"serial": serial}
        )
        
        if resultado:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Error al anular el ticket"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

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
        
        # Verificar si ya existe
        existentes = supabase_request("resultados", filters={
            "fecha": fecha,
            "hora_sorteo": hora_sorteo,
            "__limit": 1
        })
        
        resultado_data = {
            "fecha": fecha,
            "hora_sorteo": hora_sorteo,
            "animal_ganador": animal_ganador,
            "creado_en": ahora_peru().isoformat(),
            "creado_por": session.get('nombre')
        }
        
        if existentes and len(existentes) > 0:
            resultado = supabase_request(
                "resultados",
                method="PATCH",
                data=resultado_data,
                filters={"id": existentes[0]['id']}
            )
        else:
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

# ============================================================================
# API ADMIN
# ============================================================================

@app.route('/api/admin/dashboard')
@admin_required
def api_dashboard():
    try:
        fecha_hoy = ahora_peru().strftime("%d/%m/%Y")
        
        tickets = supabase_request("tickets", filters={
            "fecha": fecha_hoy,
            "__limit": 5000
        })
        
        if tickets is None:
            tickets = []
        
        ventas = sum(float(t.get('total', 0)) for t in tickets)
        premios = sum(float(t.get('total', 0)) for t in tickets if t.get('estado') == 'pagado')
        
        return jsonify({
            "success": True,
            "ventas": ventas,
            "premios": premios,
            "tickets": len(tickets),
            "balance": ventas - premios
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/agencias', methods=['GET'])
@admin_required
def api_get_agencias():
    try:
        agencias = supabase_request("agencias", filters={"__limit": 5000})
        
        if agencias is None:
            agencias = []
        
        return jsonify({"success": True, "agencias": agencias})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/agencias', methods=['POST'])
@admin_required
def api_crear_agencia():
    try:
        data = request.json
        
        agencia_data = {
            "codigo": data.get('codigo'),
            "nombre": data.get('nombre'),
            "comision": data.get('comision', 15),
            "creado_en": ahora_peru().isoformat()
        }
        
        resultado = supabase_request("agencias", method="POST", data=agencia_data)
        
        if resultado:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Error al crear la agencia"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/riesgo')
@admin_required
def api_riesgo():
    try:
        agencia = request.args.get('agencia')
        
        filters = {"__limit": 5000}
        if agencia:
            filters["agencia_codigo"] = agencia
        
        tickets = supabase_request("tickets", filters=filters)
        
        if tickets is None:
            tickets = []
        
        apuestas = sum(float(t.get('total', 0)) for t in tickets if t.get('estado') == 'activo')
        riesgo_max = apuestas * 35  # Multiplicador máximo
        
        return jsonify({
            "success": True,
            "apuestas": apuestas,
            "riesgo_max": riesgo_max,
            "exposicion": 0
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/tripletas')
@admin_required
def api_tripletas():
    try:
        tickets = supabase_request("tickets", filters={"__limit": 5000})
        
        if tickets is None:
            tickets = []
        
        # Filtrar tripletas
        tripletas = [t for t in tickets if 'tripleta' in t.get('items', '')]
        
        return jsonify({
            "success": True,
            "total": len(tripletas),
            "ganadoras": 0,
            "premios": 0,
            "tripletas": tripletas
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
        
        filters = {"__limit": 5000}
        if agencia:
            filters["agencia_codigo"] = agencia
        
        tickets = supabase_request("tickets", filters=filters)
        
        if tickets is None:
            tickets = []
        
        ventas = sum(float(t.get('total', 0)) for t in tickets)
        premios = sum(float(t.get('total', 0)) for t in tickets if t.get('estado') == 'pagado')
        
        return jsonify({
            "success": True,
            "totales": {
                "ventas": ventas,
                "premios": premios,
                "tickets": len(tickets),
                "balance": ventas - premios
            }
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ============================================================================
# INICIO DE LA APLICACIÓN
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# ============================================================================
# TEMPLATE LOGIN
# ============================================================================
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZOOLO CASINO - Login</title>
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
            background: rgba(0, 0, 0, 0.4);
            border: 2px solid #ffd700;
            border-radius: 20px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
            box-shadow: 0 0 30px rgba(255, 215, 0, 0.3);
        }
        .logo { text-align: center; margin-bottom: 30px; }
        .logo h1 { color: #ffd700; font-size: 2em; text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5); }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; color: #fff; margin-bottom: 8px; font-size: 14px; }
        .form-group input {
            width: 100%; padding: 12px 15px; border: 1px solid #444; border-radius: 8px;
            background: rgba(255, 255, 255, 0.1); color: #fff; font-size: 16px;
        }
        .form-group input:focus { outline: none; border-color: #ffd700; }
        .btn-login {
            width: 100%; padding: 15px; border: none; border-radius: 8px;
            background: linear-gradient(135deg, #ffd700, #ffaa00); color: #000;
            font-size: 16px; font-weight: bold; cursor: pointer; transition: all 0.3s ease;
        }
        .btn-login:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(255, 215, 0, 0.4); }
        .version { text-align: center; color: #888; margin-top: 20px; font-size: 12px; }
        .flash-message {
            background: rgba(231, 76, 60, 0.2); color: #e74c3c;
            padding: 10px; border-radius: 8px; margin-bottom: 15px; text-align: center;
        }
        .usuarios-info {
            margin-top: 20px;
            padding: 15px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            font-size: 11px;
            color: #888;
        }
        .usuarios-info strong { color: #ffd700; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>🎰 ZOOLO CASINO</h1>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash-message">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST" action="{{ url_for('login') }}">
            <div class="form-group">
                <label>Usuario</label>
                <input type="text" name="username" required placeholder="Ingrese su usuario">
            </div>
            <div class="form-group">
                <label>Contraseña</label>
                <input type="password" name="password" required placeholder="Ingrese su contraseña">
            </div>
            <button type="submit" class="btn-login">INICIAR SESIÓN</button>
        </form>
        <div class="usuarios-info">
            <strong>Usuarios de prueba:</strong><br>
            👑 Admin: admin / admin123<br>
            🏢 Agencia: agencia01 / agencia01<br>
            🏢 Agencia: agencia02 / agencia02<br>
            👤 Vendedor: vendedor1 / vendedor1
        </div>
        <div class="version">Sistema ZOOLO CASINO v8.0<br>Tripleta x60 - Nueva Horario Perú</div>
    </div>
</body>
</html>
"""


# ============================================================================
# TEMPLATE ADMIN PANEL COMPLETO
# ============================================================================
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PANEL ADMIN - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0d0d1a 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #ffd700;
        }
        .header h1 { color: #ffd700; font-size: 1.3em; }
        .header-actions { display: flex; gap: 10px; }
        .btn {
            padding: 8px 16px; border: none; border-radius: 6px;
            cursor: pointer; font-weight: 600; transition: all 0.3s ease;
            text-decoration: none; display: inline-block; font-size: 13px;
        }
        .btn-primary { background: linear-gradient(135deg, #ffd700, #ffaa00); color: #000; }
        .btn-secondary { background: rgba(255, 255, 255, 0.1); color: #fff; }
        .btn-success { background: linear-gradient(135deg, #00c853, #00a344); color: #fff; }
        .btn-danger { background: linear-gradient(135deg, #ff5252, #d32f2f); color: #fff; }
        .btn-warning { background: linear-gradient(135deg, #ffb300, #ff8f00); color: #000; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        
        .tabs-container {
            display: flex; background: rgba(0,0,0,0.3);
            border-bottom: 1px solid rgba(255,215,0,0.2); overflow-x: auto;
        }
        .tab {
            padding: 12px 20px; background: transparent; border: none;
            color: #aaa; cursor: pointer; font-size: 13px; white-space: nowrap;
            transition: all 0.3s ease; display: flex; align-items: center; gap: 6px;
        }
        .tab:hover { color: #fff; background: rgba(255,255,255,0.05); }
        .tab.active { 
            color: #ffd700; border-bottom: 2px solid #ffd700;
            background: rgba(255,215,0,0.1);
        }
        
        .content { padding: 20px; max-width: 1400px; margin: 0 auto; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        .info-banner {
            background: linear-gradient(135deg, rgba(255,215,0,0.1), rgba(255,170,0,0.1));
            border: 1px solid rgba(255,215,0,0.3); border-radius: 8px;
            padding: 10px 15px; margin-bottom: 20px; font-size: 12px; color: #ffd700;
        }
        
        .stats-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: linear-gradient(135deg, rgba(26,26,46,0.8), rgba(22,33,62,0.8));
            border: 1px solid rgba(255,215,0,0.2); border-radius: 12px; padding: 20px; text-align: center;
        }
        .stat-card h3 { color: #888; font-size: 12px; text-transform: uppercase; margin-bottom: 10px; }
        .stat-card .value { color: #ffd700; font-size: 2em; font-weight: bold; }
        
        .panel {
            background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px; padding: 20px; margin-bottom: 20px;
        }
        .panel h2 { color: #ffd700; font-size: 16px; margin-bottom: 15px; display: flex; align-items: center; gap: 8px; }
        
        .form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 15px; }
        .form-group label { display: block; color: #aaa; font-size: 12px; margin-bottom: 5px; }
        .form-group input, .form-group select {
            width: 100%; padding: 10px; border: 1px solid #444; border-radius: 6px;
            background: rgba(0,0,0,0.3); color: #fff; font-size: 14px;
        }
        
        .results-list { display: grid; gap: 10px; }
        .result-item {
            background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px; padding: 15px;
            display: grid; grid-template-columns: 100px 1fr auto; align-items: center; gap: 15px;
        }
        .result-time { color: #ffd700; font-weight: bold; }
        .result-animal { display: flex; align-items: center; gap: 10px; }
        .animal-number {
            width: 40px; height: 40px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-weight: bold; font-size: 14px;
        }
        .animal-number.rojo { background: linear-gradient(135deg, #ff5252, #d32f2f); }
        .animal-number.negro { background: linear-gradient(135deg, #444, #222); }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { color: #ffd700; font-size: 12px; text-transform: uppercase; }
        td { color: #aaa; font-size: 13px; }
        tr:hover td { color: #fff; background: rgba(255,255,255,0.05); }
        
        .badge { padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .badge-success { background: rgba(0,200,83,0.2); color: #00c853; }
        .badge-danger { background: rgba(255,82,82,0.2); color: #ff5252; }
        .badge-warning { background: rgba(255,179,0,0.2); color: #ffb300; }
        
        .actions-cell { display: flex; gap: 5px; }
        .btn-small { padding: 5px 10px; font-size: 11px; }
        
        .quick-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
        .quick-btn { padding: 15px; border-radius: 8px; text-align: center; cursor: pointer; transition: all 0.3s ease; }
        .quick-btn:hover { transform: translateY(-2px); }
        
        .modal {
            display: none; position: fixed; top: 0; left: 0;
            width: 100%; height: 100%; background: rgba(0,0,0,0.8);
            z-index: 1000; justify-content: center; align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border: 1px solid rgba(255,215,0,0.3); border-radius: 12px;
            padding: 25px; max-width: 500px; width: 90%;
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h3 { color: #ffd700; }
        .close-btn { background: none; border: none; color: #fff; font-size: 24px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="header">
        <h1>👑 PANEL ADMIN - ZOOLO CASINO</h1>
        <div class="header-actions">
            <a href="{{ url_for('pos') }}" class="btn btn-secondary">Ir al POS</a>
            <a href="{{ url_for('logout') }}" class="btn btn-primary">Salir</a>
        </div>
    </div>
    
    <div class="tabs-container">
        <button class="tab active" onclick="showTab('dashboard')">📊 Dashboard</button>
        <button class="tab" onclick="showTab('resultados')">📝 Resultados</button>
        <button class="tab" onclick="showTab('riesgo')">⚠️ Riesgo</button>
        <button class="tab" onclick="showTab('tripletas')">🎲 Tripletas</button>
        <button class="tab" onclick="showTab('reporte')">📈 Reporte</button>
        <button class="tab" onclick="showTab('historico')">📚 Histórico</button>
        <button class="tab" onclick="showTab('agencias')">🏢 Agencias</button>
        <button class="tab" onclick="showTab('operaciones')">⚙️ Operaciones</button>
    </div>
    
    <div class="content">
        <!-- DASHBOARD -->
        <div id="dashboard" class="tab-content active">
            <div class="info-banner">
                🔥 REGLAS: Animales (00-39) = x35 | Lechuza (40) = x70 | Especiales = x2 | Tripleta = x60
            </div>
            <div class="info-banner">
                ⏰ Zona Horaria Perú (UTC-5): Los resultados son editables hasta 2 horas después del sorteo
            </div>
            
            <div class="stats-grid">
                <div class="stat-card"><h3>💰 Ventas</h3><div class="value" id="dash-ventas">S/0</div></div>
                <div class="stat-card"><h3>🏆 Premios Pagados</h3><div class="value" id="dash-premios">S/0</div></div>
                <div class="stat-card"><h3>📊 Balance</h3><div class="value" id="dash-balance">S/0</div></div>
                <div class="stat-card"><h3>🎫 Tickets</h3><div class="value" id="dash-tickets">0</div></div>
            </div>
            
            <div class="panel">
                <h2>⚡ Acciones Rápidas</h2>
                <div class="quick-actions">
                    <button class="quick-btn btn-success" onclick="showTab('riesgo')">Ver Riesgo</button>
                    <button class="quick-btn btn-warning" onclick="showTab('tripletas')">Ver Tripletas</button>
                </div>
            </div>
        </div>
        
        <!-- RESULTADOS -->
        <div id="resultados" class="tab-content">
            <div class="info-banner">
                🔥 REGLAS: Animales (00-39) = x35 | Lechuza (40) = x70 | Especiales = x2 | Tripleta = x60
            </div>
            
            <div class="panel">
                <h2>🔍 Consultar Resultados</h2>
                <div class="form-row">
                    <div class="form-group">
                        <input type="date" id="res-fecha-consulta" class="form-control">
                    </div>
                    <div class="form-group">
                        <button class="btn btn-success" onclick="consultarResultados()">CONSULTAR</button>
                    </div>
                </div>
                <p style="color: #ffd700; text-align: right;">HOY - <span id="fecha-hoy"></span></p>
            </div>
            
            <div class="panel">
                <h2>📋 Resultados Cargados</h2>
                <div class="info-banner" style="font-size: 11px;">
                    ℹ️ Los resultados solo son editables hasta 2 horas después de su horario de sorteo
                </div>
                <div id="resultados-lista" class="results-list"></div>
            </div>
            
            <div class="panel">
                <h2>✏️ Cargar/Editar Resultado</h2>
                <div class="form-row">
                    <div class="form-group">
                        <label>Hora Sorteo</label>
                        <select id="res-hora">
                            {% for h in horarios %}<option value="{{ h }}">{{ h }}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Animal Ganador</label>
                        <select id="res-animal">
                            {% for num, data in animales.items() %}
                            <option value="{{ num }}">{{ num }} - {{ data.nombre }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>&nbsp;</label>
                        <button class="btn btn-success" onclick="guardarResultado()">GUARDAR</button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- RIESGO -->
        <div id="riesgo" class="tab-content">
            <div class="panel">
                <h2>🏢 Seleccionar Agencia</h2>
                <div class="form-row">
                    <div class="form-group">
                        <select id="riesgo-agencia" onchange="cargarRiesgo()">
                            <option value="">TODAS LAS AGENCIAS</option>
                        </select>
                    </div>
                </div>
                <p style="color: #ffd700;">Mostrando riesgo para: <span id="riesgo-agencia-nombre">TODAS LAS AGENCIAS</span></p>
            </div>
            
            <div class="panel">
                <h2>🎯 Sorteo en Curso / Próximo</h2>
                <div style="text-align: center; padding: 30px;">
                    <div style="font-size: 24px; color: #ffd700;" id="riesgo-sorteo">08:00 AM</div>
                    <p style="color: #888; font-size: 12px;">Riesgo calculado para este horario específico</p>
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card"><h3>💵 Apuestas</h3><div class="value" id="riesgo-apuestas">S/0</div></div>
                <div class="stat-card"><h3>⚠️ Riesgo Máx</h3><div class="value" id="riesgo-max">S/0</div></div>
                <div class="stat-card"><h3>✅ Exposición</h3><div class="value" id="riesgo-exposicion">0%</div></div>
            </div>
        </div>
        
        <!-- TRIPLETAS -->
        <div id="tripletas" class="tab-content">
            <div class="panel">
                <h2>🎲 Tripletas de Hoy (Paga x60)</h2>
                <button class="btn btn-secondary" onclick="actualizarTripletas()">🔄 Actualizar</button>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card"><h3>Total Tripletas</h3><div class="value" id="trip-total">0</div></div>
                <div class="stat-card"><h3>Ganadoras</h3><div class="value" id="trip-ganadoras">0</div></div>
                <div class="stat-card"><h3>Premios</h3><div class="value" id="trip-premios">S/0</div></div>
            </div>
            
            <div class="panel">
                <h2>📋 Detalle de Tripletas</h2>
                <div id="tripletas-lista">
                    <p style="color: #888; text-align: center; padding: 30px;">Cargando tripletas...</p>
                </div>
            </div>
        </div>
        
        <!-- REPORTE -->
        <div id="reporte" class="tab-content">
            <div class="panel">
                <h2>📊 Generar Reporte</h2>
                <div class="form-row">
                    <div class="form-group"><label>Fecha Inicio</label><input type="date" id="rep-inicio"></div>
                    <div class="form-group"><label>Fecha Fin</label><input type="date" id="rep-fin"></div>
                    <div class="form-group"><label>Agencia</label><select id="rep-agencia"><option value="">Todas</option></select></div>
                    <div class="form-group"><label>&nbsp;</label><button class="btn btn-success" onclick="generarReporte()">GENERAR</button></div>
                </div>
            </div>
            <div id="reporte-resultado"></div>
        </div>
        
        <!-- HISTORICO -->
        <div id="historico" class="tab-content">
            <div class="panel">
                <h2>📚 Consulta Histórica</h2>
                <div class="form-row">
                    <div class="form-group"><input type="date" id="hist-fecha" class="form-control"></div>
                    <div class="form-group"><button class="btn btn-success" onclick="consultarHistorico()">CONSULTAR</button></div>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 10px;">
                    <button class="btn btn-secondary btn-small" onclick="setHistFecha('ayer')">Ayer</button>
                    <button class="btn btn-secondary btn-small" onclick="setHistFecha('7dias')">7 días</button>
                    <button class="btn btn-secondary btn-small" onclick="setHistFecha('mes')">Mes</button>
                </div>
            </div>
            <div id="historico-resultado"></div>
        </div>
        
        <!-- AGENCIAS -->
        <div id="agencias" class="tab-content">
            <div class="panel">
                <h2>➕ Crear Nueva Agencia</h2>
                <div class="form-row">
                    <div class="form-group"><input type="text" id="ag-codigo" placeholder="Código de agencia"></div>
                    <div class="form-group"><input type="text" id="ag-nombre" placeholder="Nombre de la Agencia"></div>
                    <div class="form-group"><input type="number" id="ag-comision" placeholder="Comisión %" value="15"></div>
                    <div class="form-group"><button class="btn btn-success" onclick="crearAgencia()">CREAR AGENCIA</button></div>
                </div>
            </div>
            
            <div class="panel">
                <h2>🏢 Agencias Existentes</h2>
                <table>
                    <thead><tr><th>ID</th><th>Código</th><th>Nombre</th><th>Comisión</th><th>Acciones</th></tr></thead>
                    <tbody id="agencias-lista"></tbody>
                </table>
            </div>
        </div>
        
        <!-- OPERACIONES -->
        <div id="operaciones" class="tab-content">
            <div class="panel">
                <h2>💰 Pagar Ticket</h2>
                <div class="form-row">
                    <div class="form-group"><input type="text" id="pagar-serial" placeholder="Ingrese SERIAL del ticket"></div>
                    <div class="form-group"><button class="btn btn-success" onclick="verificarYPagar()">VERIFICAR Y PAGAR</button></div>
                </div>
            </div>
            
            <div class="panel">
                <h2>❌ Anular Ticket</h2>
                <div class="form-row">
                    <div class="form-group"><input type="text" id="anular-serial" placeholder="Ingrese SERIAL del ticket"></div>
                    <div class="form-group"><button class="btn btn-danger" onclick="anularTicket()">ANULAR</button></div>
                </div>
                <p style="color: #888; font-size: 11px;">
                    ⚠️ Solo se pueden anular tickets que no estén pagados y cuyo sorteo no haya iniciado.
                </p>
            </div>
        </div>
    </div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('fecha-hoy').textContent = new Date().toLocaleDateString('es-PE');
            document.getElementById('res-fecha-consulta').valueAsDate = new Date();
            document.getElementById('rep-inicio').valueAsDate = new Date();
            document.getElementById('rep-fin').valueAsDate = new Date();
            document.getElementById('hist-fecha').valueAsDate = new Date();
            
            cargarDashboard();
            cargarAgenciasSelect();
            cargarResultados();
        });
        
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
            
            if (tabName === 'dashboard') cargarDashboard();
            if (tabName === 'resultados') cargarResultados();
            if (tabName === 'agencias') cargarAgencias();
            if (tabName === 'tripletas') actualizarTripletas();
        }
        
        function cargarDashboard() {
            fetch('/api/admin/dashboard')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('dash-ventas').textContent = 'S/' + data.ventas.toFixed(0);
                        document.getElementById('dash-premios').textContent = 'S/' + data.premios.toFixed(0);
                        document.getElementById('dash-balance').textContent = 'S/' + (data.ventas - data.premios).toFixed(0);
                        document.getElementById('dash-tickets').textContent = data.tickets;
                    }
                });
        }
        
        function cargarResultados() {
            const fecha = document.getElementById('res-fecha-consulta').value;
            fetch('/api/resultados?fecha=' + fecha)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const container = document.getElementById('resultados-lista');
                        if (data.resultados.length === 0) {
                            container.innerHTML = '<p style="color: #888; text-align: center;">No hay resultados registrados</p>';
                            return;
                        }
                        const animales = {{ animales | tojson }};
                        container.innerHTML = data.resultados.map(r => {
                            const animal = animales[r.animal_ganador];
                            return `
                                <div class="result-item">
                                    <div class="result-time">${r.hora_sorteo}</div>
                                    <div class="result-animal">
                                        <div class="animal-number ${animal.color}">${r.animal_ganador}</div>
                                        <span>${animal.nombre}</span>
                                    </div>
                                    <button class="btn btn-warning btn-small" onclick="editarResultado('${r.id}', '${r.hora_sorteo}')">Editar</button>
                                </div>
                            `;
                        }).join('');
                    }
                });
        }
        
        function consultarResultados() { cargarResultados(); }
        
        function guardarResultado() {
            const hora = document.getElementById('res-hora').value;
            const animal = document.getElementById('res-animal').value;
            const fecha = document.getElementById('res-fecha-consulta').value;
            
            fetch('/api/resultados', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fecha: fecha, hora_sorteo: hora, animal_ganador: animal })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Resultado guardado exitosamente');
                    cargarResultados();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function editarResultado(id, hora) {
            const nuevoAnimal = prompt('Editar animal para ' + hora + ' (0-40):');
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
                    cargarResultados();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function cargarAgenciasSelect() {
            fetch('/api/admin/agencias')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const select = document.getElementById('riesgo-agencia');
                        const selectRep = document.getElementById('rep-agencia');
                        data.agencias.forEach(a => {
                            select.innerHTML += `<option value="${a.codigo}">${a.nombre}</option>`;
                            selectRep.innerHTML += `<option value="${a.codigo}">${a.nombre}</option>`;
                        });
                    }
                });
        }
        
        function cargarAgencias() {
            fetch('/api/admin/agencias')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const tbody = document.getElementById('agencias-lista');
                        tbody.innerHTML = data.agencias.map(a => `
                            <tr>
                                <td>${a.id || '-'}</td>
                                <td>${a.codigo}</td>
                                <td>${a.nombre}</td>
                                <td>${a.comision || 15}%</td>
                                <td class="actions-cell">
                                    <button class="btn btn-warning btn-small">Editar</button>
                                </td>
                            </tr>
                        `).join('');
                    }
                });
        }
        
        function crearAgencia() {
            const codigo = document.getElementById('ag-codigo').value;
            const nombre = document.getElementById('ag-nombre').value;
            const comision = document.getElementById('ag-comision').value;
            
            if (!codigo || !nombre) { alert('Complete todos los campos'); return; }
            
            fetch('/api/admin/agencias', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ codigo, nombre, comision })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Agencia creada exitosamente');
                    cargarAgencias();
                    cargarAgenciasSelect();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function cargarRiesgo() {
            const agencia = document.getElementById('riesgo-agencia').value;
            document.getElementById('riesgo-agencia-nombre').textContent = agencia || 'TODAS LAS AGENCIAS';
            
            fetch('/api/admin/riesgo?agencia=' + agencia)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('riesgo-apuestas').textContent = 'S/' + data.apuestas.toFixed(0);
                        document.getElementById('riesgo-max').textContent = 'S/' + data.riesgo_max.toFixed(0);
                        document.getElementById('riesgo-exposicion').textContent = data.exposicion + '%';
                    }
                });
        }
        
        function actualizarTripletas() {
            fetch('/api/admin/tripletas')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('trip-total').textContent = data.total;
                        document.getElementById('trip-ganadoras').textContent = data.ganadoras;
                        document.getElementById('trip-premios').textContent = 'S/' + data.premios.toFixed(0);
                    }
                });
        }
        
        function generarReporte() {
            const inicio = document.getElementById('rep-inicio').value;
            const fin = document.getElementById('rep-fin').value;
            const agencia = document.getElementById('rep-agencia').value;
            
            fetch(`/api/admin/reporte?inicio=${inicio}&fin=${fin}&agencia=${agencia}`)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('reporte-resultado').innerHTML = `
                            <div class="stats-grid">
                                <div class="stat-card"><h3>Ventas</h3><div class="value">S/${data.totales.ventas.toFixed(0)}</div></div>
                                <div class="stat-card"><h3>Premios</h3><div class="value">S/${data.totales.premios.toFixed(0)}</div></div>
                                <div class="stat-card"><h3>Tickets</h3><div class="value">${data.totales.tickets}</div></div>
                                <div class="stat-card"><h3>Balance</h3><div class="value">S/${data.totales.balance.toFixed(0)}</div></div>
                            </div>
                        `;
                    }
                });
        }
        
        function verificarYPagar() {
            const serial = document.getElementById('pagar-serial').value;
            if (!serial) return;
            
            fetch('/api/tickets/pagar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Ticket pagado exitosamente');
                    document.getElementById('pagar-serial').value = '';
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function anularTicket() {
            const serial = document.getElementById('anular-serial').value;
            if (!serial) return;
            if (!confirm('¿Está seguro de anular este ticket?')) return;
            
            fetch('/api/tickets/anular', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Ticket anulado exitosamente');
                    document.getElementById('anular-serial').value = '';
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }
        
        function setHistFecha(tipo) {
            const hoy = new Date();
            if (tipo === 'ayer') {
                hoy.setDate(hoy.getDate() - 1);
                document.getElementById('hist-fecha').valueAsDate = hoy;
            }
        }
        
        function consultarHistorico() {
            const fecha = document.getElementById('hist-fecha').value;
            alert('Consultando histórico para: ' + fecha);
        }
        
        setInterval(() => {
            if (document.getElementById('dashboard').classList.contains('active')) {
                cargarDashboard();
            }
        }, 30000);
    </script>
</body>
</html>
"""


# ============================================================================
# TEMPLATE POS (PANEL DE VENTAS)
# ============================================================================
POS_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agencia {{ session.agencia_nombre }} - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0d0d1a 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
        }
        
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #ffd700;
        }
        .header-left { display: flex; align-items: center; gap: 20px; }
        .logo { color: #ffd700; font-size: 1.2em; font-weight: bold; }
        .header-info { display: flex; gap: 15px; font-size: 12px; color: #aaa; }
        .menu-container { display: flex; gap: 20px; }
        .menu-item { position: relative; }
        .menu-btn {
            background: transparent; border: none; color: #fff;
            cursor: pointer; font-size: 13px; padding: 5px 10px;
            display: flex; align-items: center; gap: 5px;
        }
        .menu-btn:hover { color: #ffd700; }
        .dropdown {
            display: none; position: absolute; top: 100%; left: 0;
            background: #1a1a2e; border: 1px solid rgba(255,215,0,0.3);
            border-radius: 8px; min-width: 200px; z-index: 100;
        }
        .menu-item:hover .dropdown { display: block; }
        .dropdown-item {
            padding: 10px 15px; color: #fff; font-size: 12px;
            cursor: pointer; display: flex; align-items: center; gap: 8px;
        }
        .dropdown-item:hover { background: rgba(255,215,0,0.1); color: #ffd700; }
        
        .filters {
            display: flex; gap: 10px; padding: 10px 20px;
            background: rgba(0,0,0,0.2);
        }
        .filter-btn {
            padding: 8px 20px; border: none; border-radius: 6px;
            cursor: pointer; font-weight: bold; font-size: 12px;
            transition: all 0.3s ease;
        }
        .filter-btn.rojo { background: linear-gradient(135deg, #ff5252, #d32f2f); color: #fff; }
        .filter-btn.negro { background: linear-gradient(135deg, #444, #222); color: #fff; }
        .filter-btn.par { background: linear-gradient(135deg, #00bcd4, #0097a7); color: #fff; }
        .filter-btn.impar { background: linear-gradient(135deg, #9c27b0, #7b1fa2); color: #fff; }
        .filter-btn:hover { transform: scale(1.05); }
        .filter-btn.active { box-shadow: 0 0 15px currentColor; }
        
        .main-content {
            display: grid; grid-template-columns: 1fr 320px; gap: 15px; padding: 15px;
        }
        
        .animals-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
        .animal-card {
            aspect-ratio: 1; border-radius: 10px;
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            cursor: pointer; transition: all 0.3s ease;
            border: 2px solid transparent; position: relative;
        }
        .animal-card:hover { transform: scale(1.05); }
        .animal-card.selected { 
            border-color: #ffd700; 
            box-shadow: 0 0 20px rgba(255,215,0,0.5);
        }
        .animal-card.rojo { background: linear-gradient(135deg, rgba(255,82,82,0.3), rgba(211,47,47,0.3)); }
        .animal-card.negro { background: linear-gradient(135deg, rgba(68,68,68,0.3), rgba(34,34,34,0.3)); }
        .animal-card.hidden { display: none; }
        
        .animal-number { font-size: 24px; font-weight: bold; color: #fff; }
        .animal-name { font-size: 11px; color: #aaa; text-align: center; }
        .animal-card.selected .animal-name { color: #ffd700; }
        
        .sidebar { display: flex; flex-direction: column; gap: 10px; }
        
        .horarios-container { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px; }
        .horario-btn {
            padding: 6px 10px; border: 1px solid #444; border-radius: 4px;
            background: rgba(0,0,0,0.3); color: #aaa; font-size: 10px;
            cursor: pointer; transition: all 0.3s ease;
        }
        .horario-btn:hover { border-color: #ffd700; color: #ffd700; }
        .horario-btn.active { 
            background: linear-gradient(135deg, #00c853, #00a344); 
            color: #fff; border-color: #00c853;
        }
        
        .ticket-preview {
            background: rgba(0,0,0,0.3); border: 1px solid rgba(255,215,0,0.2);
            border-radius: 10px; padding: 15px; flex: 1;
        }
        .ticket-preview h3 { color: #ffd700; font-size: 14px; margin-bottom: 10px; text-align: center; }
        .ticket-items { max-height: 200px; overflow-y: auto; margin-bottom: 10px; }
        .ticket-item { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.1); font-size: 12px; }
        .ticket-total { display: flex; justify-content: space-between; padding-top: 10px; border-top: 2px solid rgba(255,215,0,0.3); font-weight: bold; color: #ffd700; }
        
        .action-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .action-btn {
            padding: 12px; border: none; border-radius: 8px;
            font-weight: bold; font-size: 11px; cursor: pointer;
            transition: all 0.3s ease; text-transform: uppercase;
        }
        .action-btn:hover { transform: translateY(-2px); }
        .action-btn.full { grid-column: span 2; }
        
        .btn-agregar { background: linear-gradient(135deg, #00c853, #00a344); color: #fff; }
        .btn-whatsapp { background: linear-gradient(135deg, #00bcd4, #0097a7); color: #fff; }
        .btn-resultados { background: linear-gradient(135deg, #ff9800, #f57c00); color: #fff; }
        .btn-caja { background: linear-gradient(135deg, #9c27b0, #7b1fa2); color: #fff; }
        .btn-pagar { background: linear-gradient(135deg, #4caf50, #388e3c); color: #fff; }
        .btn-tripleta { background: linear-gradient(135deg, #ffeb3b, #fbc02d); color: #000; }
        .btn-anular { background: linear-gradient(135deg, #ff5252, #d32f2f); color: #fff; }
        .btn-borrar { background: linear-gradient(135deg, #607d8b, #455a64); color: #fff; }
        .btn-cerrar { background: linear-gradient(135deg, #795548, #5d4037); color: #fff; }
        
        .monto-container { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
        .monto-label { color: #ffd700; font-weight: bold; }
        .monto-input {
            flex: 1; padding: 10px; border: 1px solid #444; border-radius: 6px;
            background: rgba(0,0,0,0.3); color: #fff; font-size: 18px; text-align: center;
        }
        
        .modal {
            display: none; position: fixed; top: 0; left: 0;
            width: 100%; height: 100%; background: rgba(0,0,0,0.8);
            z-index: 1000; justify-content: center; align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border: 1px solid rgba(255,215,0,0.3); border-radius: 12px;
            padding: 25px; max-width: 500px; width: 90%; max-height: 80vh; overflow-y: auto;
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h3 { color: #ffd700; }
        .close-btn { background: #ff5252; border: none; color: #fff; width: 30px; height: 30px; border-radius: 50%; cursor: pointer; font-size: 16px; }
        
        @media (max-width: 900px) {
            .main-content { grid-template-columns: 1fr; }
            .animals-grid { grid-template-columns: repeat(4, 1fr); }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <div class="logo">🎰 {{ session.agencia_nombre }}</div>
            <div class="header-info">
                <span>📅 {{ fecha_actual }}</span>
                <span>⏰ {{ hora_actual }}</span>
            </div>
        </div>
        <div class="menu-container">
            <div class="menu-item">
                <button class="menu-btn">📁 Archivo</button>
                <div class="dropdown">
                    <div class="dropdown-item" onclick="mostrarCajaDelDia()">💰 Caja del Día</div>
                    <div class="dropdown-item" onclick="mostrarHistorialCaja()">📊 Historial de Caja</div>
                    <div class="dropdown-item" onclick="mostrarCalculadora()">🧮 Calculadora de Premios</div>
                </div>
            </div>
            <div class="menu-item">
                <button class="menu-btn">🔍 Consultas</button>
                <div class="dropdown">
                    <div class="dropdown-item" onclick="mostrarMisTickets()">🎫 Mis Tickets Vendidos</div>
                    <div class="dropdown-item" onclick="mostrarBuscarTicket()">🔎 Buscar Ticket por Serial</div>
                    <div class="dropdown-item" onclick="mostrarTicketsPorCobrar()">💵 Tickets por Cobrar</div>
                    <div class="dropdown-item" onclick="mostrarResultadosHoy()">🏆 Resultados de Hoy</div>
                </div>
            </div>
            <div class="menu-item">
                <button class="menu-btn">❓ Ayuda</button>
                <div class="dropdown">
                    <div class="dropdown-item" onclick="mostrarAyuda()">📖 Manual de Usuario</div>
                    <div class="dropdown-item" onclick="mostrarReglas()">📋 Reglas del Juego</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="filters">
        <button class="filter-btn rojo active" onclick="filtrarAnimales('rojo')">ROJO</button>
        <button class="filter-btn negro active" onclick="filtrarAnimales('negro')">NEGRO</button>
        <button class="filter-btn par active" onclick="filtrarAnimales('par')">PAR</button>
        <button class="filter-btn impar active" onclick="filtrarAnimales('impar')">IMPAR</button>
    </div>
    
    <div class="main-content">
        <div class="animals-grid" id="animals-grid">
            {% for num, data in animales.items() %}
            <div class="animal-card {{ data.color }}" 
                 data-number="{{ num }}" 
                 data-name="{{ data.nombre }}"
                 data-color="{{ data.color }}"
                 onclick="seleccionarAnimal({{ num }}, '{{ data.nombre }}')">
                <div class="animal-number">{{ num }}</div>
                <div class="animal-name">{{ data.nombre }}</div>
            </div>
            {% endfor %}
        </div>
        
        <div class="sidebar">
            <div class="horarios-container" id="horarios-container">
                {% for h in horarios %}
                <button class="horario-btn" onclick="seleccionarHorario('{{ h }}')" data-hora="{{ h }}">{{ h }}</button>
                {% endfor %}
            </div>
            
            <div class="monto-container">
                <span class="monto-label">S/</span>
                <input type="number" class="monto-input" id="monto" placeholder="0.00" step="0.5" min="0.5">
            </div>
            
            <div class="ticket-preview">
                <h3>🎫 TICKET</h3>
                <div class="ticket-items" id="ticket-items">
                    <p style="color: #888; text-align: center; font-size: 12px;">Selecciona animales y horarios...</p>
                </div>
                <div class="ticket-total">
                    <span>TOTAL:</span>
                    <span id="ticket-total">S/0.00</span>
                </div>
            </div>
            
            <div class="action-buttons">
                <button class="action-btn btn-agregar full" onclick="agregarAlTicket()">AGREGAR AL TICKET</button>
                <button class="action-btn btn-whatsapp full" onclick="enviarPorWhatsApp()">ENVIAR POR WHATSAPP</button>
                <button class="action-btn btn-resultados" onclick="mostrarResultados()">RESULTADOS</button>
                <button class="action-btn btn-caja" onclick="mostrarCaja()">CAJA</button>
                <button class="action-btn btn-pagar" onclick="pagarTicket()">PAGAR</button>
                <button class="action-btn btn-tripleta" onclick="activarTripleta()">TRIPLETA</button>
                <button class="action-btn btn-anular" onclick="anularTicket()">ANULAR</button>
                <button class="action-btn btn-borrar" onclick="borrarTodo()">BORRAR TODO</button>
                <button class="action-btn btn-cerrar full" onclick="cerrarSesion()">CERRAR SESIÓN</button>
            </div>
        </div>
    </div>
    
    <div class="modal" id="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modal-title">Título</h3>
                <button class="close-btn" onclick="cerrarModal()">×</button>
            </div>
            <div id="modal-body"></div>
        </div>
    </div>
    
    <script>
        let animalesSeleccionados = [];
        let horarioSeleccionado = null;
        let modoTripleta = false;
        let ticketItems = [];
        
        document.addEventListener('DOMContentLoaded', function() {
            const primerHorario = document.querySelector('.horario-btn');
            if (primerHorario) seleccionarHorario(primerHorario.dataset.hora);
        });
        
        function filtrarAnimales(tipo) {
            const btn = event.target;
            btn.classList.toggle('active');
            
            const mostrarRojo = document.querySelector('.filter-btn.rojo').classList.contains('active');
            const mostrarNegro = document.querySelector('.filter-btn.negro').classList.contains('active');
            const mostrarPar = document.querySelector('.filter-btn.par').classList.contains('active');
            const mostrarImpar = document.querySelector('.filter-btn.impar').classList.contains('active');
            
            document.querySelectorAll('.animal-card').forEach(card => {
                const color = card.dataset.color;
                const numero = parseInt(card.dataset.number);
                const esPar = numero % 2 === 0;
                
                let mostrar = true;
                if (!mostrarRojo && color === 'rojo') mostrar = false;
                if (!mostrarNegro && color === 'negro') mostrar = false;
                if (!mostrarPar && esPar) mostrar = false;
                if (!mostrarImpar && !esPar) mostrar = false;
                
                card.classList.toggle('hidden', !mostrar);
            });
        }
        
        function seleccionarAnimal(num, nombre) {
            const card = document.querySelector(`.animal-card[data-number="${num}"]`);
            
            if (modoTripleta) {
                const index = animalesSeleccionados.findIndex(a => a.num === num);
                if (index > -1) {
                    animalesSeleccionados.splice(index, 1);
                    card.classList.remove('selected');
                } else {
                    if (animalesSeleccionados.length >= 3) {
                        alert('Solo puedes seleccionar 3 animales para tripleta');
                        return;
                    }
                    animalesSeleccionados.push({ num, nombre });
                    card.classList.add('selected');
                }
            } else {
                document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('selected'));
                animalesSeleccionados = [{ num, nombre }];
                card.classList.add('selected');
            }
            actualizarPreview();
        }
        
        function seleccionarHorario(hora) {
            horarioSeleccionado = hora;
            document.querySelectorAll('.horario-btn').forEach(h => h.classList.remove('active'));
            document.querySelector(`.horario-btn[data-hora="${hora}"]`).classList.add('active');
            actualizarPreview();
        }
        
        function actualizarPreview() {
            const container = document.getElementById('ticket-items');
            
            if (animalesSeleccionados.length === 0 || !horarioSeleccionado) {
                container.innerHTML = '<p style="color: #888; text-align: center; font-size: 12px;">Selecciona animales y horarios...</p>';
                document.getElementById('ticket-total').textContent = 'S/0.00';
                return;
            }
            
            const monto = parseFloat(document.getElementById('monto').value) || 0;
            const tipo = modoTripleta ? 'Tripleta (x60)' : 'Directo (x35)';
            const multiplicador = modoTripleta ? 60 : 35;
            const premio = monto * multiplicador;
            
            let html = '';
            animalesSeleccionados.forEach(a => {
                html += `<div class="ticket-item"><span>${a.num} - ${a.nombre}</span><span>S/${monto.toFixed(2)}</span></div>`;
            });
            html += `<div class="ticket-item" style="color: #ffd700;"><span>${tipo} - ${horarioSeleccionado}</span><span>Posible: S/${premio.toFixed(2)}</span></div>`;
            
            container.innerHTML = html;
            document.getElementById('ticket-total').textContent = 'S/' + monto.toFixed(2);
        }
        
        function agregarAlTicket() {
            const monto = parseFloat(document.getElementById('monto').value);
            
            if (animalesSeleccionados.length === 0) { alert('Selecciona al menos un animal'); return; }
            if (!horarioSeleccionado) { alert('Selecciona un horario'); return; }
            if (!monto || monto <= 0) { alert('Ingresa un monto válido'); return; }
            
            ticketItems.push({
                animales: [...animalesSeleccionados],
                horario: horarioSeleccionado,
                monto: monto,
                tipo: modoTripleta ? 'tripleta' : 'directo'
            });
            
            animalesSeleccionados = [];
            document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('selected'));
            actualizarTicketFinal();
            alert('Agregado al ticket');
        }
        
        function actualizarTicketFinal() {
            const container = document.getElementById('ticket-items');
            let total = 0;
            let html = '';
            
            ticketItems.forEach((item, idx) => {
                const animalesStr = item.animales.map(a => `${a.num}-${a.nombre}`).join(', ');
                html += `<div class="ticket-item"><span>${item.tipo.toUpperCase()}: ${animalesStr} (${item.horario})</span><span>S/${item.monto.toFixed(2)}</span></div>`;
                total += item.monto;
            });
            
            container.innerHTML = html || '<p style="color: #888; text-align: center; font-size: 12px;">Selecciona animales y horarios...</p>';
            document.getElementById('ticket-total').textContent = 'S/' + total.toFixed(2);
        }
        
        function activarTripleta() {
            modoTripleta = !modoTripleta;
            const btn = event.target;
            
            if (modoTripleta) {
                btn.style.background = 'linear-gradient(135deg, #ffd700, #ffaa00)';
                btn.textContent = 'TRIPLETA (ACTIVADO)';
            } else {
                btn.style.background = 'linear-gradient(135deg, #ffeb3b, #fbc02d)';
                btn.textContent = 'TRIPLETA';
            }
            
            animalesSeleccionados = [];
            document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('selected'));
            actualizarPreview();
        }
        
        function borrarTodo() {
            animalesSeleccionados = [];
            ticketItems = [];
            document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('selected'));
            document.getElementById('monto').value = '';
            actualizarPreview();
        }
        
        function mostrarResultados() {
            fetch('/api/resultados?fecha=hoy')
                .then(r => r.json())
                .then(data => {
                    let html = '<div style="max-height: 300px; overflow-y: auto;">';
                    if (data.resultados) {
                        data.resultados.forEach(r => {
                            html += `<div style="padding: 8px; border-bottom: 1px solid #444;"><strong>${r.hora_sorteo}</strong> - ${r.animal_ganador}</div>`;
                        });
                    }
                    html += '</div>';
                    mostrarModal('Resultados de Hoy', html);
                });
        }
        
        function mostrarCaja() {
            mostrarModal('Caja', '<p>Función en desarrollo</p>');
        }
        
        function pagarTicket() {
            const serial = prompt('Ingrese el SERIAL del ticket a pagar:');
            if (!serial) return;
            
            fetch('/api/tickets/pagar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) alert('Ticket pagado exitosamente');
                else alert('Error: ' + data.error);
            });
        }
        
        function anularTicket() {
            const serial = prompt('Ingrese el SERIAL del ticket a anular:');
            if (!serial) return;
            if (!confirm('¿Está seguro de anular este ticket?')) return;
            
            fetch('/api/tickets/anular', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) alert('Ticket anulado exitosamente');
                else alert('Error: ' + data.error);
            });
        }
        
        function mostrarMisTickets() {
            mostrarModal('Mis Tickets', '<p>Función en desarrollo</p>');
        }
        
        function mostrarBuscarTicket() {
            const serial = prompt('Ingrese el SERIAL del ticket:');
            if (!serial) return;
            
            fetch('/api/tickets/' + serial)
                .then(r => r.json())
                .then(data => {
                    if (data.ticket) {
                        mostrarModal('Ticket Encontrado', `
                            <p><strong>Serial:</strong> ${data.ticket.serial}</p>
                            <p><strong>Fecha:</strong> ${data.ticket.fecha}</p>
                            <p><strong>Total:</strong> S/${data.ticket.total}</p>
                            <p><strong>Estado:</strong> ${data.ticket.estado}</p>
                        `);
                    } else {
                        alert('Ticket no encontrado');
                    }
                });
        }
        
        function mostrarTicketsPorCobrar() {
            mostrarModal('Tickets por Cobrar', '<p>Función en desarrollo</p>');
        }
        
        function mostrarResultadosHoy() {
            mostrarResultados();
        }
        
        function mostrarCajaDelDia() {
            mostrarModal('Caja del Día', '<p>Función en desarrollo</p>');
        }
        
        function mostrarHistorialCaja() {
            mostrarModal('Historial de Caja', '<p>Función en desarrollo</p>');
        }
        
        function mostrarCalculadora() {
            mostrarModal('Calculadora', '<p>Función en desarrollo</p>');
        }
        
        function mostrarAyuda() {
            mostrarModal('Ayuda', '<p>Manual en desarrollo</p>');
        }
        
        function mostrarReglas() {
            mostrarModal('Reglas', `
                <p><strong>Animales (00-39):</strong> Paga x35</p>
                <p><strong>Lechuza (40):</strong> Paga x70</p>
                <p><strong>Especiales:</strong> Paga x2</p>
                <p><strong>Tripleta:</strong> Paga x60</p>
            `);
        }
        
        function mostrarModal(titulo, contenido) {
            document.getElementById('modal-title').textContent = titulo;
            document.getElementById('modal-body').innerHTML = contenido;
            document.getElementById('modal').classList.add('active');
        }
        
        function cerrarModal() {
            document.getElementById('modal').classList.remove('active');
        }
        
        function cerrarSesion() {
            if (confirm('¿Desea cerrar sesión?')) {
                window.location.href = '{{ url_for('logout') }}';
            }
        }
        
        function enviarPorWhatsApp() {
            alert('Función de WhatsApp en desarrollo');
        }
        
        document.getElementById('modal').addEventListener('click', function(e) {
            if (e.target === this) cerrarModal();
        });
    </script>
</body>
</html>
"""


# ============================================================================
# RUTAS DE LA APLICACIÓN
# ============================================================================

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
        
        # Verificar en usuarios locales
        if username in USUARIOS and USUARIOS[username]['password'] == password:
            user = USUARIOS[username]
            session['user_id'] = username
            session['username'] = username
            session['nombre'] = user['nombre']
            session['es_admin'] = user['es_admin']
            session['agencia'] = user['agencia_codigo']
            session['agencia_nombre'] = user['agencia_nombre']
            
            if user['es_admin']:
                return redirect(url_for('admin'))
            return redirect(url_for('pos'))
        else:
            flash("Usuario o contraseña incorrectos", "error")
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def admin():
    return render_template_string(ADMIN_TEMPLATE, 
                                  animales=ANIMALES, 
                                  horarios=HORARIOS_SORTEO)

@app.route('/pos')
@login_required
def pos():
    ahora = ahora_peru()
    return render_template_string(POS_TEMPLATE, 
                                  animales=ANIMALES,
                                  horarios=HORARIOS_SORTEO,
                                  fecha_actual=ahora.strftime("%d/%m/%Y"),
                                  fecha_iso=ahora.strftime("%Y-%m-%d"),
                                  hora_actual=ahora.strftime("%I:%M %p"))

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/tickets/<serial>')
@login_required
def api_get_ticket(serial):
    try:
        tickets = supabase_request("tickets", filters={"serial": serial, "__limit": 1})
        if tickets and len(tickets) > 0:
            return jsonify({"success": True, "ticket": tickets[0]})
        return jsonify({"success": False, "error": "Ticket no encontrado"})
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
            return jsonify({"success": False, "error": "El ticket no está activo"})
        
        resultado = supabase_request(
            "tickets",
            method="PATCH",
            data={
                "estado": "pagado",
                "pagado_en": ahora_peru().isoformat(),
                "pagado_por": session.get('nombre')
            },
            filters={"serial": serial}
        )
        
        if resultado:
            return jsonify({"success": True})
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
            data={
                "estado": "anulado",
                "anulado_en": ahora_peru().isoformat(),
                "anulado_por": session.get('nombre')
            },
            filters={"serial": serial}
        )
        
        if resultado:
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Error al anular el ticket"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

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
        
        existentes = supabase_request("resultados", filters={
            "fecha": fecha,
            "hora_sorteo": hora_sorteo,
            "__limit": 1
        })
        
        resultado_data = {
            "fecha": fecha,
            "hora_sorteo": hora_sorteo,
            "animal_ganador": animal_ganador,
            "creado_en": ahora_peru().isoformat(),
            "creado_por": session.get('nombre')
        }
        
        if existentes and len(existentes) > 0:
            resultado = supabase_request(
                "resultados",
                method="PATCH",
                data=resultado_data,
                filters={"id": existentes[0]['id']}
            )
        else:
            resultado = supabase_request("resultados", method="POST", data=resultado_data)
        
        if resultado:
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Error al guardar el resultado"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/resultados/<id>', methods=['PATCH'])
@admin_required
def api_editar_resultado(id):
    try:
        data = request.json
        resultado = supabase_request(
            "resultados",
            method="PATCH",
            data=data,
            filters={"id": id}
        )
        
        if resultado:
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Error al actualizar el resultado"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ============================================================================
# API ADMIN
# ============================================================================

@app.route('/api/admin/dashboard')
@admin_required
def api_dashboard():
    try:
        fecha_hoy = ahora_peru().strftime("%d/%m/%Y")
        tickets = supabase_request("tickets", filters={"fecha": fecha_hoy, "__limit": 5000})
        
        if tickets is None:
            tickets = []
        
        ventas = sum(float(t.get('total', 0)) for t in tickets)
        premios = sum(float(t.get('total', 0)) for t in tickets if t.get('estado') == 'pagado')
        
        return jsonify({
            "success": True,
            "ventas": ventas,
            "premios": premios,
            "tickets": len(tickets),
            "balance": ventas - premios
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/agencias', methods=['GET'])
@admin_required
def api_get_agencias():
    try:
        agencias = supabase_request("agencias", filters={"__limit": 5000})
        if agencias is None:
            agencias = []
        return jsonify({"success": True, "agencias": agencias})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/agencias', methods=['POST'])
@admin_required
def api_crear_agencia():
    try:
        data = request.json
        agencia_data = {
            "codigo": data.get('codigo'),
            "nombre": data.get('nombre'),
            "comision": data.get('comision', 15),
            "creado_en": ahora_peru().isoformat()
        }
        
        resultado = supabase_request("agencias", method="POST", data=agencia_data)
        
        if resultado:
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Error al crear la agencia"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/riesgo')
@admin_required
def api_riesgo():
    try:
        agencia = request.args.get('agencia')
        filters = {"__limit": 5000}
        if agencia:
            filters["agencia_codigo"] = agencia
        
        tickets = supabase_request("tickets", filters=filters)
        if tickets is None:
            tickets = []
        
        apuestas = sum(float(t.get('total', 0)) for t in tickets if t.get('estado') == 'activo')
        riesgo_max = apuestas * 35
        
        return jsonify({
            "success": True,
            "apuestas": apuestas,
            "riesgo_max": riesgo_max,
            "exposicion": 0
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/tripletas')
@admin_required
def api_tripletas():
    try:
        tickets = supabase_request("tickets", filters={"__limit": 5000})
        if tickets is None:
            tickets = []
        
        tripletas = [t for t in tickets if 'tripleta' in str(t.get('items', ''))]
        
        return jsonify({
            "success": True,
            "total": len(tripletas),
            "ganadoras": 0,
            "premios": 0,
            "tripletas": tripletas
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
        
        filters = {"__limit": 5000}
        if agencia:
            filters["agencia_codigo"] = agencia
        
        tickets = supabase_request("tickets", filters=filters)
        if tickets is None:
            tickets = []
        
        ventas = sum(float(t.get('total', 0)) for t in tickets)
        premios = sum(float(t.get('total', 0)) for t in tickets if t.get('estado') == 'pagado')
        
        return jsonify({
            "success": True,
            "totales": {
                "ventas": ventas,
                "premios": premios,
                "tickets": len(tickets),
                "balance": ventas - premios
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ============================================================================
# INICIO DE LA APLICACIÓN
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
