#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v5.7 - MENU DESPLEGABLE + FIX ZONA HORARIA PERU
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

# ==================== CONFIGURACION SUPABASE ====================
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://iuwgbtmhkqnqulwgcgkk.supabase.co').strip()
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...').strip()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'zoolo_casino_cloud_2025_seguro')

# Configuracion de negocio
PAGO_ANIMAL_NORMAL = 35      
PAGO_LECHUZA = 70           
PAGO_ESPECIAL = 2           
COMISION_AGENCIA = 0.15
MINUTOS_BLOQUEO = 5

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

# ==================== FUNCIONES AUXILIARES ====================
def ahora_peru():
    """Retorna la hora actual en Peru (UTC-5)"""
    return datetime.utcnow() - timedelta(hours=5)

def parse_fecha_ticket(fecha_str):
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y %I:%M %p")
    except:
        try:
            return datetime.strptime(fecha_str, "%d/%m/%Y")
        except:
            return None

def get_color(num):
    if num in ["0", "00"]: 
        return "#27ae60"
    if num in ROJOS: 
        return "#c0392b"
    return "#2c3e50"

def generar_serial():
    return str(int(ahora_peru().timestamp() * 1000))

def verificar_horario_bloqueo(hora_sorteo):
    """Verifica si el sorteo esta bloqueado para ventas (5 minutos antes)"""
    ahora = ahora_peru()
    try:
        partes = hora_sorteo.replace(':', ' ').split()
        hora = int(partes[0])
        minuto = int(partes[1])
        ampm = partes[2]
        
        if ampm == 'PM' and hora != 12:
            hora += 12
        elif ampm == 'AM' and hora == 12:
            hora = 0
        
        sorteo_minutos = hora * 60 + minuto
        actual_minutos = ahora.hour * 60 + ahora.minute
        
        return (sorteo_minutos - actual_minutos) > MINUTOS_BLOQUEO
    except:
        return True

def puede_editar_resultado(hora_sorteo):
    """
    NUEVO: Determina si un resultado puede ser editado por el admin.
    Permite editar hasta 2 horas despues del sorteo (para Peru: 7 PM editable hasta 8 PM)
    """
    ahora = ahora_peru()
    try:
        partes = hora_sorteo.replace(':', ' ').split()
        hora = int(partes[0])
        minuto = int(partes[1])
        ampm = partes[2]
        
        if ampm == 'PM' and hora != 12:
            hora += 12
        elif ampm == 'AM' and hora == 12:
            hora = 0
        
        sorteo_dt = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        
        # Si el sorteo ya paso, verificar que no hayan pasado mas de 2 horas
        if ahora > sorteo_dt:
            diferencia = ahora - sorteo_dt
            return diferencia.total_seconds() < (2 * 3600)  # 2 horas
        
        # Si el sorteo es futuro, siempre se puede editar (precarga)
        return True
    except:
        return False

def calcular_premio_animal(monto_apostado, numero_animal):
    if str(numero_animal) == "40":
        return monto_apostado * PAGO_LECHUZA
    else:
        return monto_apostado * PAGO_ANIMAL_NORMAL

def supabase_request(table, method="GET", data=None, filters=None, timeout=30):
    """Funcion mejorada con manejo de errores robusto"""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    if filters:
        filter_params = []
        for k, v in filters.items():
            if k.endswith('__like'):
                filter_params.append(f"{k.replace('__like', '')}=like.{urllib.parse.quote(str(v))}")
            else:
                filter_params.append(f"{k}=eq.{urllib.parse.quote(str(v))}")
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
                    if response.status in [200, 201, 204]:
                        return True
                    return False
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    print(f"[ERROR PATCH] Registro no encontrado: {url}")
                    return False
                raise e
                
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.read().decode()}")
        return None
    except Exception as e:
        print(f"[ERROR] Supabase: {e}")
        return None

def obtener_proximo_sorteo():
    """Devuelve el proximo horario de sorteo disponible"""
    ahora = ahora_peru()
    actual_minutos = ahora.hour * 60 + ahora.minute
    
    for hora_str in HORARIOS_PERU:
        partes = hora_str.replace(':', ' ').split()
        hora = int(partes[0])
        minuto = int(partes[1])
        ampm = partes[2]
        
        if ampm == 'PM' and hora != 12:
            hora += 12
        elif ampm == 'AM' and hora == 12:
            hora = 0
            
        sorteo_minutos = hora * 60 + minuto
        
        if (sorteo_minutos - actual_minutos) > MINUTOS_BLOQUEO:
            return hora_str
    
    return None

def obtener_sorteo_en_curso():
    """
    MODIFICADO: Devuelve el sorteo que esta actualmente en curso o el mas reciente pasado
    (hasta 2 horas despues) para permitir edicion tardia
    """
    ahora = ahora_peru()
    actual_minutos = ahora.hour * 60 + ahora.minute
    
    sorteo_mas_reciente = None
    
    for hora_str in HORARIOS_PERU:
        partes = hora_str.replace(':', ' ').split()
        hora = int(partes[0])
        minuto = int(partes[1])
        ampm = partes[2]
        
        if ampm == 'PM' and hora != 12:
            hora += 12
        elif ampm == 'AM' and hora == 12:
            hora = 0
            
        sorteo_minutos = hora * 60 + minuto
        
        # Si estamos dentro del sorteo (hora actual entre inicio y +60 min)
        if actual_minutos >= sorteo_minutos and actual_minutos < (sorteo_minutos + 60):
            return hora_str
        
        # Si paso hace menos de 2 horas, lo guardamos como candidato
        if actual_minutos >= sorteo_minutos:
            diferencia_min = actual_minutos - sorteo_minutos
            if diferencia_min <= 120:  # 2 horas
                sorteo_mas_reciente = hora_str
    
    return sorteo_mas_reciente or obtener_proximo_sorteo()

# ==================== DECORADORES ====================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or not session.get('es_admin'):
            return "No autorizado", 403
        return f(*args, **kwargs)
    return decorated

def agencia_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login requerido'}), 403
        if session.get('es_admin'):
            return jsonify({'error': 'Admin no puede vender'}), 403
        return f(*args, **kwargs)
    return decorated

# ==================== RUTAS ====================
@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('es_admin'):
            return redirect('/admin')
        return redirect('/pos')
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
            else:
                error = "Usuario o clave incorrecta"
        except Exception as e:
            error = f"Error de conexion: {str(e)}"
    
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/pos')
@login_required
def pos():
    if session.get('es_admin'):
        return redirect('/admin')
    
    return render_template_string(POS_HTML,
        agencia=session['nombre_agencia'],
        animales=ANIMALES,
        horarios_peru=HORARIOS_PERU,
        horarios_venezuela=HORARIOS_VENEZUELA,
        get_color=get_color
    )

@app.route('/admin')
@admin_required
def admin():
    return render_template_string(ADMIN_HTML,
        animales=ANIMALES,
        horarios=HORARIOS_PERU
    )
    <!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
    <title>Panel Admin - ZOOLO CASINO</title>
    <style>
        /* ... [CSS anterior se mantiene] ... */
        
        /* ==================== NUEVO: MENU DESPLEGABLE ==================== */
        .menu-bar {
            background: linear-gradient(to bottom, #f0f0f0, #d4d4d4);
            border-bottom: 2px solid #999;
            display: flex;
            align-items: center;
            padding: 0;
            position: sticky;
            top: 0;
            z-index: 1000;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }
        
        /* Botón Hamburguesa (Mobile) */
        .menu-toggle {
            display: none;
            background: none;
            border: none;
            font-size: 1.8rem;
            padding: 10px 15px;
            cursor: pointer;
            color: #333;
        }
        
        /* Menú Desktop */
        .menu-items {
            display: flex;
            list-style: none;
            margin: 0;
            padding: 0;
            flex: 1;
        }
        
        .menu-item {
            position: relative;
        }
        
        .menu-btn {
            background: none;
            border: none;
            padding: 12px 20px;
            cursor: pointer;
            font-weight: bold;
            color: #333;
            font-size: 0.95rem;
            border-right: 1px solid #bbb;
            transition: all 0.2s;
        }
        
        .menu-btn:hover {
            background: rgba(255,215,0,0.3);
            color: #000;
        }
        
        /* Submenú Desktop */
        .submenu {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            background: #f9f9f9;
            border: 1px solid #999;
            border-top: 2px solid #ffd700;
            min-width: 220px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            z-index: 1001;
        }
        
        .menu-item:hover .submenu {
            display: block;
            animation: fadeIn 0.2s;
        }
        
        .submenu-item {
            display: block;
            padding: 12px 20px;
            color: #333;
            text-decoration: none;
            border-bottom: 1px solid #ddd;
            font-size: 0.9rem;
            transition: all 0.2s;
        }
        
        .submenu-item:hover {
            background: #ffd700;
            color: #000;
            padding-left: 25px;
        }
        
        .submenu-item i {
            margin-right: 10px;
            width: 20px;
            display: inline-block;
        }
        
        /* Menú Móvil Lateral */
        @media (max-width: 768px) {
            .menu-toggle {
                display: block;
            }
            
            .menu-items {
                position: fixed;
                top: 0;
                left: -100%;
                width: 80%;
                max-width: 300px;
                height: 100vh;
                background: #1a1a2e;
                flex-direction: column;
                padding-top: 60px;
                transition: left 0.3s;
                border-right: 3px solid #ffd700;
                overflow-y: auto;
            }
            
            .menu-items.active {
                left: 0;
            }
            
            .menu-item {
                width: 100%;
                border-bottom: 1px solid #333;
            }
            
            .menu-btn {
                width: 100%;
                text-align: left;
                border: none;
                color: white;
                padding: 15px 20px;
                border-bottom: 1px solid #333;
            }
            
            .submenu {
                position: static;
                display: none;
                background: #0a0a0a;
                border: none;
                box-shadow: none;
                width: 100%;
            }
            
            .menu-item.active .submenu {
                display: block;
            }
            
            .submenu-item {
                color: #ccc;
                border-bottom: 1px solid #222;
                padding-left: 40px;
            }
            
            .overlay {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.7);
                z-index: 999;
            }
            
            .overlay.active {
                display: block;
            }
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-5px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body>
    <!-- Overlay para cerrar menú en móvil -->
    <div class="overlay" onclick="cerrarMenu()"></div>
    
    <!-- Barra de Menú Estilo Windows -->
    <div class="menu-bar">
        <button class="menu-toggle" onclick="toggleMenu()">☰</button>
        
        <ul class="menu-items" id="menuItems">
            <li class="menu-item">
                <button class="menu-btn" onclick="toggleSubmenu(this)">📁 Archivo</button>
                <div class="submenu">
                    <a href="#" class="submenu-item" onclick="showTab('dashboard'); return false;">📊 Dashboard</a>
                    <a href="#" class="submenu-item" onclick="verAuditor(); return false;">📋 Ver Auditor</a>
                    <a href="#" class="submenu-item" onclick="calcularPremio(); return false;">🧮 Calcular Premio</a>
                    <a href="#" class="submenu-item" onclick="showTab('parametros'); return false;">⚙️ Parámetros</a>
                </div>
            </li>
            
            <li class="menu-item">
                <button class="menu-btn" onclick="toggleSubmenu(this)">💰 Movimientos</button>
                <div class="submenu">
                    <a href="#" class="submenu-item" onclick="eliminarListas(); return false;">🗑️ Eliminar Listas</a>
                    <a href="#" class="submenu-item" onclick="showTab('anular'); return false;">❌ Borrar Tickets</a>
                    <a href="#" class="submenu-item" onclick="showTab('pagos'); return false;">💵 Pagar Ticket</a>
                </div>
            </li>
            
            <li class="menu-item">
                <button class="menu-btn" onclick="toggleSubmenu(this)">🔍 Consultas</button>
                <div class="submenu">
                    <a href="#" class="submenu-item" onclick="showTab('resultados'); return false;">🎯 Resultados</a>
                    <a href="#" class="submenu-item" onclick="consultarStatusTickets(); return false;">📑 Status Tickets</a>
                    <a href="#" class="submenu-item" onclick="consultarPorPagar(); return false;">💳 Tickets Por Pagar</a>
                    <a href="#" class="submenu-item" onclick="consultarPagados(); return false;">✅ Tickets Pagados</a>
                    <a href="#" class="submenu-item" onclick="consultarAnulados(); return false;">🚫 Tickets Anulados</a>
                </div>
            </li>
            
            <li class="menu-item">
                <button class="menu-btn" onclick="toggleSubmenu(this)">❓ Ayuda</button>
                <div class="submenu">
                    <a href="#" class="submenu-item" onclick="mostrarReglas(); return false;">📜 Reglas de Pago</a>
                    <a href="#" class="submenu-item" onclick="acercaDe(); return false;">ℹ️ Acerca de</a>
                </div>
            </li>
        </ul>
        
        <button onclick="location.href='/logout'" style="background:#c0392b; color:white; border:none; padding:10px 20px; cursor:pointer; font-weight:bold;">
            🚪 Salir
        </button>
    </div>
    
    <!-- [Resto del contenido del admin...] -->
    
    <script>
        // Funciones del Menú
        function toggleMenu() {
            document.getElementById('menuItems').classList.toggle('active');
            document.querySelector('.overlay').classList.toggle('active');
        }
        
        function cerrarMenu() {
            document.getElementById('menuItems').classList.remove('active');
            document.querySelector('.overlay').classList.remove('active');
            document.querySelectorAll('.menu-item').forEach(item => {
                item.classList.remove('active');
            });
        }
        
        function toggleSubmenu(btn) {
            if (window.innerWidth <= 768) {
                const menuItem = btn.parentElement;
                menuItem.classList.toggle('active');
            }
        }
        
        // Funciones de las opciones del menú
        function eliminarListas() {
            if (confirm('¿Eliminar todas las listas temporales?')) {
                showMensaje('Listas eliminadas', 'success');
            }
        }
        
        function verAuditor() {
            showMensaje('Función Auditor: En desarrollo', 'success');
            // Aquí puedes agregar la lógica para ver logs
        }
        
        function calcularPremio() {
            const monto = prompt('Monto apostado:');
            const animal = prompt('Número ganador:');
            if (monto && animal) {
                const premio = animal === "40" ? monto * 70 : monto * 35;
                alert(`El premio sería: S/${premio}`);
            }
        }
        
        function consultarStatusTickets() {
            showTab('reporte');
            showMensaje('Mostrando status de tickets...', 'success');
        }
        
        function consultarPorPagar() {
            showMensaje('Consultando tickets por pagar...', 'success');
            // Lógica adicional para filtrar por pagar
        }
        
        function consultarPagados() {
            showMensaje('Consultando tickets pagados...', 'success');
        }
        
        function consultarAnulados() {
            showMensaje('Consultando tickets anulados...', 'success');
        }
        
        function mostrarReglas() {
            alert('REGLAS DE PAGO:\\n\\n' +
                  '🦁 Animales 00-39: x35\\n' +
                  '🦉 Lechuza (40): x70\\n' +
                  '🔴 Rojo/Negro/Par/Impar: x2\\n\\n' +
                  'Sorteos cada hora desde 9 AM hasta 7 PM (Perú)');
        }
        
        function acercaDe() {
            alert('ZOOLO CASINO v5.7\\nSistema de Gestión de Lotería\\n\\nDesarrollado con Flask + Supabase');
        }
        
        // Cerrar menú al hacer click en un enlace (mobile)
        document.querySelectorAll('.submenu-item').forEach(item => {
            item.addEventListener('click', () => {
                if (window.innerWidth <= 768) {
                    cerrarMenu();
                }
            });
        });
    </script>
</body>
</html>

# [CONTINÚAN TODAS LAS APIS...]
