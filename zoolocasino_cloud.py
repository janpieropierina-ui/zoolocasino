#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v7.0 - SISTEMA COMPLETO
Código completo con setup inicial para admin y agencias
"""

import os
import sys
import json
import csv
import io
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, render_template_string, request, session, redirect, jsonify, Response
from collections import defaultdict

# ==================== CONFIGURACIÓN OBLIGATORIA ====================
# Configura estas variables de entorno antes de iniciar:
# export SUPABASE_URL="tu_url_de_supabase"
# export SUPABASE_KEY="tu_service_role_key_o_anon_key"
# export SECRET_KEY="una_clave_secreta_segura_para_flask"

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '').strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: Debes configurar SUPABASE_URL y SUPABASE_KEY como variables de entorno")
    print("Ejemplo: export SUPABASE_URL='https://tu-proyecto.supabase.co'")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'zoolo_casino_cloud_2025_seguro_cambiar_en_produccion')

# ==================== CONFIGURACIÓN DE NEGOCIO ====================
PAGO_ANIMAL_NORMAL = 35      
PAGO_LECHUZA = 70           
PAGO_ESPECIAL = 2            
PAGO_TRIPLETA = 60          
COMISION_AGENCIA = 0.15
MINUTOS_BLOQUEO = 5
HORAS_EDICION_RESULTADO = 2

# ==================== HORARIOS ====================
HORARIOS_PERU = [
    "08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
    "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM"
]

HORARIOS_VENEZUELA = [
    "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM",
    "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM"
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
    """Retorna datetime actual de Perú (UTC-5)"""
    try:
        return datetime.now(timezone.utc) - timedelta(hours=5)
    except:
        return datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(hours=5)

def parse_fecha_ticket(fecha_str):
    """Parsea fechas en formato dd/mm/YYYY o dd/mm/YYYY HH:MM AM/PM"""
    if not fecha_str:
        return None
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y %I:%M %p")
    except:
        try:
            return datetime.strptime(fecha_str, "%d/%m/%Y")
        except:
            try:
                return datetime.strptime(fecha_str, "%Y-%m-%d")
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

def formatear_monto(monto):
    try:
        monto_float = float(monto)
        if monto_float == int(monto_float):
            return str(int(monto_float))
        else:
            return str(monto_float)
    except:
        return str(monto)

def verificar_horario_bloqueo(hora_sorteo):
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

def calcular_premio_animal(monto_apostado, numero_animal):
    if str(numero_animal) == "40":
        return monto_apostado * PAGO_LECHUZA
    else:
        return monto_apostado * PAGO_ANIMAL_NORMAL

def hora_a_minutos(hora_str):
    try:
        partes = hora_str.replace(':', ' ').split()
        hora = int(partes[0])
        minuto = int(partes[1])
        ampm = partes[2]
        
        if ampm == 'PM' and hora != 12:
            hora += 12
        elif ampm == 'AM' and hora == 12:
            hora = 0
            
        return hora * 60 + minuto
    except:
        return 0

def puede_editar_resultado(hora_sorteo, fecha_str=None):
    return True  # Sin restricción temporal

def obtener_sorteo_en_curso():
    ahora = ahora_peru()
    actual_minutos = ahora.hour * 60 + ahora.minute
    
    for hora_str in HORARIOS_PERU:
        minutos_sorteo = hora_a_minutos(hora_str)
        if actual_minutos >= minutos_sorteo and actual_minutos < (minutos_sorteo + 60):
            return hora_str
    
    ultimo_sorteo = HORARIOS_PERU[-1]
    minutos_ultimo = hora_a_minutos(ultimo_sorteo)
    
    if actual_minutos > minutos_ultimo and actual_minutos <= (minutos_ultimo + (HORAS_EDICION_RESULTADO * 60)):
        return ultimo_sorteo
    
    return None

def obtener_proximo_sorteo():
    ahora = ahora_peru()
    actual_minutos = ahora.hour * 60 + ahora.minute
    
    for hora_str in HORARIOS_PERU:
        minutos_sorteo = hora_a_minutos(hora_str)
        if (minutos_sorteo - actual_minutos) > MINUTOS_BLOQUEO:
            return hora_str
    
    return HORARIOS_PERU[0]

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
            else:
                filter_params.append(f"{k}=eq.{urllib.parse.quote(str(v))}")
        url += "?" + "&".join(filter_params)
    
    if "?" in url:
        url += "&limit=5000"
    else:
        url += "?limit=5000"
    
    headers_get = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
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

# ==================== RUTAS DE SETUP INICIAL ====================
@app.route('/setup-first-admin', methods=['GET', 'POST'])
def setup_first_admin():
    """Endpoint especial para crear el primer administrador si no existe ninguno"""
    try:
        # Verificar si ya existe algún admin
        existing = supabase_request("agencias", filters={"es_admin": "true"})
        if existing and len(existing) > 0:
            return "Ya existe al menos un administrador en el sistema. No se puede usar este endpoint."
        
        if request.method == 'POST':
            usuario = request.form.get('usuario', '').strip().lower()
            password = request.form.get('password', '').strip()
            nombre = request.form.get('nombre', '').strip()
            
            if not usuario or not password or not nombre:
                return "Todos los campos son obligatorios", 400
            
            data = {
                "usuario": usuario,
                "password": password,  # En producción, usar hash
                "nombre_agencia": nombre,
                "es_admin": True,
                "comision": 0,
                "activa": True
            }
            
            result = supabase_request("agencias", method="POST", data=data)
            if result:
                return f"""
                <h2>✅ Admin creado exitosamente</h2>
                <p>Usuario: {usuario}</p>
                <p>Nombre: {nombre}</p>
                <p><a href="/login">Ir al Login</a></p>
                <hr>
                <p><strong>IMPORTANTE:</strong> Después de crear el admin, este endpoint se bloqueará automáticamente.</p>
                """
            else:
                return "Error al crear administrador", 500
        
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Setup Inicial - Primer Admin</title>
            <style>
                body { font-family: Arial; max-width: 400px; margin: 50px auto; padding: 20px; background: #1a1a2e; color: white; }
                h2 { color: #ffd700; }
                input { width: 100%; padding: 10px; margin: 5px 0; border-radius: 5px; border: 1px solid #444; background: #222; color: white; }
                button { width: 100%; padding: 15px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; margin-top: 10px; }
                .warning { background: #e74c3c; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-size: 0.9rem; }
            </style>
        </head>
        <body>
            <h2>🎰 ZOOLO CASINO - Setup Inicial</h2>
            <div class="warning">
                Este endpoint solo funciona si NO existe ningún administrador en el sistema.
                Se usará una sola vez para crear el primer admin.
            </div>
            <form method="POST">
                <label>Nombre del Administrador:</label>
                <input type="text" name="nombre" placeholder="Ej: Admin Principal" required>
                
                <label>Usuario (login):</label>
                <input type="text" name="usuario" placeholder="Ej: admin" required>
                
                <label>Contraseña:</label>
                <input type="password" name="password" placeholder="Contraseña segura" required>
                
                <button type="submit">Crear Primer Administrador</button>
            </form>
        </body>
        </html>
        '''
    except Exception as e:
        return f"Error: {str(e)}", 500

# ==================== RUTAS PRINCIPALES ====================
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
                session['es_admin'] = user.get('es_admin', False)
                return redirect('/')
            else:
                error = "Usuario o clave incorrecta"
        except Exception as e:
            error = f"Error de conexión: {str(e)}"
    
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

# ==================== API POS (COMPLETAS) ====================
@app.route('/api/resultados-hoy')
@login_required
def resultados_hoy():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        resultados_list = supabase_request("resultados", filters={"fecha": hoy})
        
        resultados_dict = {}
        if resultados_list:
            for r in resultados_list:
                resultados_dict[r['hora']] = {
                    'animal': r['animal'],
                    'nombre': ANIMALES.get(r['animal'], 'Desconocido')
                }
        
        for hora in HORARIOS_PERU:
            if hora not in resultados_dict:
                resultados_dict[hora] = None
                
        return jsonify({
            'status': 'ok',
            'fecha': hoy,
            'resultados': resultados_dict
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/resultados-fecha', methods=['POST'])
@login_required
def resultados_fecha():
    try:
        data = request.get_json() or {}
        fecha_str = data.get('fecha')
        
        if not fecha_str:
            fecha_obj = ahora_peru()
        else:
            fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d")
        
        fecha_busqueda = fecha_obj.strftime("%d/%m/%Y")
        
        resultados_list = supabase_request("resultados", filters={"fecha": fecha_busqueda})
        
        resultados_dict = {}
        if resultados_list:
            for r in resultados_list:
                resultados_dict[r['hora']] = {
                    'animal': r['animal'],
                    'nombre': ANIMALES.get(r['animal'], 'Desconocido')
                }
        
        for hora in HORARIOS_PERU:
            if hora not in resultados_dict:
                resultados_dict[hora] = None
                
        return jsonify({
            'status': 'ok',
            'fecha_consulta': fecha_busqueda,
            'fecha_input': fecha_str,
            'resultados': resultados_dict
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/procesar-venta', methods=['POST'])
@agencia_required
def procesar_venta():
    try:
        data = request.get_json()
        jugadas = data.get('jugadas', [])
        
        if not jugadas:
            return jsonify({'error': 'Ticket vacio'}), 400
        
        for j in jugadas:
            if j['tipo'] != 'tripleta' and not verificar_horario_bloqueo(j['hora']):
                return jsonify({'error': f"El sorteo {j['hora']} ya cerro"}), 400
        
        serial = generar_serial()
        fecha = ahora_peru().strftime("%d/%m/%Y %I:%M %p")
        total = sum(j['monto'] for j in jugadas)
        
        ticket_data = {
            "serial": serial,
            "agencia_id": session['user_id'],
            "fecha": fecha,
            "total": total,
            "pagado": False,
            "anulado": False
        }
        
        result = supabase_request("tickets", method="POST", data=ticket_data)
        if not result:
            return jsonify({'error': 'Error al crear ticket'}), 500
        
        ticket_id = result[0]['id']
        
        for j in jugadas:
            if j['tipo'] == 'tripleta':
                nums = j['seleccion'].split(',')
                tripleta_data = {
                    "ticket_id": ticket_id,
                    "animal1": nums[0],
                    "animal2": nums[1],
                    "animal3": nums[2],
                    "monto": j['monto'],
                    "fecha": fecha.split(' ')[0],
                    "pagado": False
                }
                supabase_request("tripletas", method="POST", data=tripleta_data)
            else:
                jugada_data = {
                    "ticket_id": ticket_id,
                    "hora": j['hora'],
                    "seleccion": j['seleccion'],
                    "monto": j['monto'],
                    "tipo": j['tipo']
                }
                supabase_request("jugadas", method="POST", data=jugada_data)
        
        jugadas_por_hora = defaultdict(list)
        for j in jugadas:
            if j['tipo'] != 'tripleta':
                jugadas_por_hora[j['hora']].append(j)
        
        lineas = [
            f"*{session['nombre_agencia']}*",
            f"*TICKET:* #{ticket_id}",
            f"*SERIAL:* {serial}",
            fecha,
            "------------------------",
            ""
        ]
        
        for hora_peru in HORARIOS_PERU:
            if hora_peru not in jugadas_por_hora:
                continue
                
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
                    texto_jugadas.append(f"{nombre_corto}{j['seleccion']}x{formatear_monto(j['monto'])}")
                else:
                    tipo_corto = j['seleccion'][0:3]
                    texto_jugadas.append(f"{tipo_corto}x{formatear_monto(j['monto'])}")
            
            lineas.append(" ".join(texto_jugadas))
            lineas.append("")
        
        tripletas_en_ticket = [j for j in jugadas if j['tipo'] == 'tripleta']
        if tripletas_en_ticket:
            lineas.append("*TRIPLETAS (Paga x60)*")
            for t in tripletas_en_ticket:
                nums = t['seleccion'].split(',')
                nombres = [ANIMALES.get(n, '')[0:3].upper() for n in nums]
                lineas.append(f"{'-'.join(nombres)} (x60) S/{formatear_monto(t['monto'])}")
            lineas.append("")
        
        lineas.append("------------------------")
        lineas.append(f"*TOTAL: S/{formatear_monto(total)}*")
        lineas.append("")
        lineas.append("Buena Suerte! 🍀")
        lineas.append("El ticket vence a los 3 dias")
        
        texto_whatsapp = "\n".join(lineas)
        url_whatsapp = f"https://wa.me/?text={urllib.parse.quote(texto_whatsapp)}"
        
        return jsonify({
            'status': 'ok',
            'serial': serial,
            'ticket_id': ticket_id,
            'total': total,
            'url_whatsapp': url_whatsapp
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/mis-tickets', methods=['POST'])
@agencia_required
def mis_tickets():
    try:
        data = request.get_json() or {}
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        estado = data.get('estado', 'todos')
        
        base_url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{session['user_id']}&order=fecha.desc&limit=5000"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        
        req = urllib.request.Request(base_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            all_tickets = json.loads(response.read().decode())
        
        tickets_filtrados = []
        dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d") if fecha_inicio else None
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59) if fecha_fin else None
        
        for t in all_tickets:
            if t.get('anulado'):
                continue
                
            dt_ticket = parse_fecha_ticket(t['fecha'])
            if not dt_ticket:
                continue
                
            if dt_inicio and dt_ticket < dt_inicio:
                continue
            if dt_fin and dt_ticket > dt_fin:
                continue
            
            if estado == 'pagados' and not t.get('pagado'):
                continue
            if estado == 'pendientes' and t.get('pagado'):
                continue
                
            tickets_filtrados.append(t)
        
        if estado == 'por_pagar':
            tickets_con_premio = []
            for t in tickets_filtrados:
                if t.get('pagado'):
                    continue
                premio_total = calcular_premio_ticket(t)
                if premio_total > 0:
                    t['premio_calculado'] = round(premio_total, 2)
                    tickets_con_premio.append(t)
            tickets_filtrados = tickets_con_premio
        
        total_ventas = sum(t['total'] for t in tickets_filtrados)
        total_tickets = len(tickets_filtrados)
        
        tickets_respuesta = tickets_filtrados[:50]
        
        return jsonify({
            'status': 'ok',
            'tickets': tickets_respuesta,
            'totales': {
                'cantidad': total_tickets,
                'ventas': round(total_ventas, 2)
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def calcular_premio_ticket(ticket):
    try:
        fecha_ticket = parse_fecha_ticket(ticket['fecha']).strftime("%d/%m/%Y")
        resultados_list = supabase_request("resultados", filters={"fecha": fecha_ticket})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        total_premio = 0
        
        jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
        for j in jugadas:
            wa = resultados.get(j['hora'])
            if wa:
                if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                    total_premio += calcular_premio_animal(j['monto'], wa)
                elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                    sel = j['seleccion']
                    num = int(wa)
                    if (sel == 'ROJO' and str(wa) in ROJOS) or \
                       (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                       (sel == 'PAR' and num % 2 == 0) or \
                       (sel == 'IMPAR' and num % 2 != 0):
                        total_premio += j['monto'] * PAGO_ESPECIAL
        
        tripletas = supabase_request("tripletas", filters={"ticket_id": ticket['id']})
        if tripletas:
            for trip in tripletas:
                nums = [trip['animal1'], trip['animal2'], trip['animal3']]
                nums_encontrados = []
                for hora, animal in resultados.items():
                    if animal in nums and animal not in nums_encontrados:
                        nums_encontrados.append(animal)
                if len(nums_encontrados) == 3:
                    total_premio += trip['monto'] * PAGO_TRIPLETA
        
        return total_premio
    except:
        return 0

@app.route('/api/consultar-ticket-detalle', methods=['POST'])
@agencia_required
def consultar_ticket_detalle():
    try:
        data = request.get_json()
        serial = data.get('serial')
        
        if not serial:
            return jsonify({'error': 'Serial requerido'}), 400
        
        tickets = supabase_request("tickets", filters={"serial": serial, "agencia_id": session['user_id']})
        if not tickets or len(tickets) == 0:
            return jsonify({'error': 'Ticket no encontrado o no pertenece a esta agencia'})
        
        ticket = tickets[0]
        jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
        
        fecha_ticket = parse_fecha_ticket(ticket['fecha']).strftime("%d/%m/%Y")
        resultados_list = supabase_request("resultados", filters={"fecha": fecha_ticket})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        jugadas_detalle = []
        total_premio = 0
        
        for j in jugadas:
            wa = resultados.get(j['hora'])
            premio = 0
            gano = False
            
            if wa:
                if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                    premio = calcular_premio_animal(j['monto'], wa)
                    gano = True
                elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                    sel = j['seleccion']
                    num = int(wa)
                    if (sel == 'ROJO' and str(wa) in ROJOS) or \
                       (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                       (sel == 'PAR' and num % 2 == 0) or \
                       (sel == 'IMPAR' and num % 2 != 0):
                        premio = j['monto'] * PAGO_ESPECIAL
                        gano = True
            
            if gano:
                total_premio += premio
            
            jugadas_detalle.append({
                'hora': j['hora'],
                'tipo': j['tipo'],
                'seleccion': j['seleccion'],
                'nombre_seleccion': ANIMALES.get(j['seleccion'], j['seleccion']) if j['tipo'] == 'animal' else j['seleccion'],
                'monto': j['monto'],
                'resultado': wa,
                'gano': gano,
                'premio': round(premio, 2) if gano else 0
            })
        
        tripletas = supabase_request("tripletas", filters={"ticket_id": ticket['id']})
        if tripletas:
            for trip in tripletas:
                nums = [trip['animal1'], trip['animal2'], trip['animal3']]
                nombres = [ANIMALES.get(n, n) for n in nums]
                nums_encontrados = []
                
                for hora, animal in resultados.items():
                    if animal in nums and animal not in nums_encontrados:
                        nums_encontrados.append(animal)
                
                gano = len(nums_encontrados) == 3
                premio = trip['monto'] * PAGO_TRIPLETA if gano else 0
                
                if gano:
                    total_premio += premio
                
                jugadas_detalle.append({
                    'hora': 'Todo el día',
                    'tipo': 'tripleta',
                    'seleccion': f"{trip['animal1']},{trip['animal2']},{trip['animal3']}",
                    'nombre_seleccion': f"{' - '.join(nombres)}",
                    'monto': trip['monto'],
                    'resultado': f"Salieron: {', '.join(nums_encontrados)}" if nums_encontrados else "Pendiente",
                    'gano': gano,
                    'premio': round(premio, 2)
                })
        
        return jsonify({
            'status': 'ok',
            'ticket': {
                'id': ticket['id'],
                'serial': ticket['serial'],
                'fecha': ticket['fecha'],
                'total_apostado': ticket['total'],
                'pagado': ticket['pagado'],
                'anulado': ticket['anulado'],
                'premio_total': round(total_premio, 2),
                'ganancia_neta': round(total_premio - ticket['total'], 2) if total_premio > 0 else -ticket['total']
            },
            'jugadas': jugadas_detalle
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/verificar-ticket', methods=['POST'])
@login_required
def verificar_ticket():
    try:
        serial = request.json.get('serial')
        
        tickets = supabase_request("tickets", filters={"serial": serial})
        if not tickets or len(tickets) == 0:
            return jsonify({'error': 'Ticket no existe'})
        
        ticket = tickets[0]
        
        if not session.get('es_admin') and ticket['agencia_id'] != session['user_id']:
            return jsonify({'error': 'No autorizado para ver este ticket'})
        
        if ticket['anulado']:
            return jsonify({'error': 'TICKET ANULADO'})
        if ticket['pagado']:
            return jsonify({'error': 'YA FUE PAGADO'})
        
        total_ganado = calcular_premio_ticket(ticket)
        
        return jsonify({
            'status': 'ok',
            'ticket_id': ticket['id'],
            'total_ganado': total_ganado,
            'detalles': []
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pagar-ticket', methods=['POST'])
@agencia_required
def pagar_ticket():
    try:
        ticket_id = request.json.get('ticket_id')
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?id=eq.{urllib.parse.quote(str(ticket_id))}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        data = json.dumps({"pagado": True}).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
        urllib.request.urlopen(req, timeout=15)
        
        url_trip = f"{SUPABASE_URL}/rest/v1/tripletas?ticket_id=eq.{urllib.parse.quote(str(ticket_id))}"
        data_trip = json.dumps({"pagado": True}).encode()
        req_trip = urllib.request.Request(url_trip, data=data_trip, headers=headers, method="PATCH")
        try:
            urllib.request.urlopen(req_trip, timeout=15)
        except:
            pass
        
        return jsonify({'status': 'ok', 'mensaje': 'Ticket pagado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/anular-ticket', methods=['POST'])
@login_required
def anular_ticket():
    try:
        serial = request.json.get('serial')
        tickets = supabase_request("tickets", filters={"serial": serial})
        if not tickets or len(tickets) == 0:
            return jsonify({'error': 'Ticket no existe'})
        
        ticket = tickets[0]
        
        if not session.get('es_admin') and ticket['agencia_id'] != session['user_id']:
            return jsonify({'error': 'No autorizado para anular este ticket'})
        
        if ticket['pagado']:
            return jsonify({'error': 'Ya esta pagado, no se puede anular'})
        
        if not session.get('es_admin'):
            fecha_ticket = parse_fecha_ticket(ticket['fecha'])
            if not fecha_ticket:
                return jsonify({'error': 'Error en fecha del ticket'})
            
            minutos_transcurridos = (ahora_peru() - fecha_ticket).total_seconds() / 60
            if minutos_transcurridos > 5:
                return jsonify({'error': f'No puede anular después de 5 minutos'})
            
            jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
            for j in jugadas:
                if not verificar_horario_bloqueo(j['hora']):
                    return jsonify({'error': f'No se puede anular, el sorteo {j["hora"]} ya cerró'})
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?id=eq.{urllib.parse.quote(str(ticket['id']))}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        data = json.dumps({"anulado": True}).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
        urllib.request.urlopen(req, timeout=15)
        return jsonify({'status': 'ok', 'mensaje': 'Ticket anulado correctamente'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/caja')
@agencia_required
def caja_agencia():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(hoy)}%25"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        
        ventas = sum(t['total'] for t in tickets if t['agencia_id'] == session['user_id'] and not t['anulado'])
        
        agencias = supabase_request("agencias", filters={"id": session['user_id']})
        comision_pct = agencias[0]['comision'] if agencias else COMISION_AGENCIA
        comision = ventas * comision_pct
        
        premios = 0
        tickets_pendientes = 0
        
        for t in tickets:
            if t['agencia_id'] == session['user_id'] and not t['anulado']:
                premio_ticket = calcular_premio_ticket(t)
                if t['pagado']:
                    premios += premio_ticket
                elif premio_ticket > 0:
                    tickets_pendientes += 1
        
        balance = ventas - premios - comision
        
        return jsonify({
            'ventas': round(ventas, 2),
            'premios': round(premios, 2),
            'comision': round(comision, 2),
            'balance': round(balance, 2),
            'tickets_pendientes': tickets_pendientes
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== API ADMIN ====================
@app.route('/admin/lista-agencias')
@admin_required
def lista_agencias():
    try:
        url = f"{SUPABASE_URL}/rest/v1/agencias?es_admin=eq.false"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            agencias = json.loads(response.read().decode())
        return jsonify([{"id": a['id'], "usuario": a['usuario'], "nombre_agencia": a['nombre_agencia'], "comision": a['comision']} for a in agencias])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/crear-agencia', methods=['POST'])
@admin_required
def crear_agencia():
    try:
        usuario = request.form.get('usuario', '').strip().lower()
        password = request.form.get('password', '').strip()
        nombre = request.form.get('nombre', '').strip()
        
        if not usuario or not password or not nombre:
            return jsonify({'error': 'Complete todos los campos'}), 400
        
        existentes = supabase_request("agencias", filters={"usuario": usuario})
        if existentes and len(existentes) > 0:
            return jsonify({'error': 'Usuario ya existe'}), 400
        
        data = {
            "usuario": usuario,
            "password": password,
            "nombre_agencia": nombre,
            "es_admin": False,
            "comision": COMISION_AGENCIA,
            "activa": True
        }
        
        supabase_request("agencias", method="POST", data=data)
        return jsonify({'status': 'ok', 'mensaje': f'Agencia {nombre} creada'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/guardar-resultado', methods=['POST'])
@admin_required
def guardar_resultado():
    try:
        hora = request.form.get('hora')
        animal = request.form.get('animal')
        fecha_input = request.form.get('fecha')
        
        if animal not in ANIMALES:
            return jsonify({'error': f'Animal inválido: {animal}'}), 400
        
        if fecha_input:
            try:
                fecha_obj = datetime.strptime(fecha_input, "%Y-%m-%d")
                fecha = fecha_obj.strftime("%d/%m/%Y")
            except:
                fecha = ahora_peru().strftime("%d/%m/%Y")
        else:
            fecha = ahora_peru().strftime("%d/%m/%Y")
        
        existentes = supabase_request("resultados", filters={"fecha": fecha, "hora": hora})
        
        if existentes and len(existentes) > 0:
            url = f"{SUPABASE_URL}/rest/v1/resultados?fecha=eq.{urllib.parse.quote(fecha)}&hora=eq.{urllib.parse.quote(hora)}"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            data = json.dumps({"animal": animal}).encode()
            req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
            
            try:
                with urllib.request.urlopen(req, timeout=15) as response:
                    if response.status in [200, 201, 204]:
                        return jsonify({
                            'status': 'ok', 
                            'mensaje': f'RESULTADO ACTUALIZADO: {hora} = {animal} ({ANIMALES[animal]})',
                            'accion': 'actualizado'
                        })
                    else:
                        return jsonify({'error': 'Error al actualizar'}), 500
            except urllib.error.HTTPError as e:
                return jsonify({'error': f'Error al actualizar: HTTP {e.code}'}), 500
        else:
            data = {"fecha": fecha, "hora": hora, "animal": animal}
            result = supabase_request("resultados", method="POST", data=data)
            
            if result:
                return jsonify({
                    'status': 'ok', 
                    'mensaje': f'RESULTADO GUARDADO: {hora} = {animal} ({ANIMALES[animal]})',
                    'accion': 'creado'
                })
            else:
                return jsonify({'error': 'Error al crear resultado'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/reporte-agencias-rango', methods=['POST'])
@admin_required
def reporte_agencias_rango():
    try:
        data = request.get_json()
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fechas requeridas'}), 400
        
        dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
        
        url = f"{SUPABASE_URL}/rest/v1/agencias?es_admin=eq.false"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            agencias = json.loads(response.read().decode())
        
        dict_agencias = {a['id']: a for a in agencias}
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=50000"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            all_tickets = json.loads(response.read().decode())
        
        tickets_validos = []
        for t in all_tickets:
            if t.get('anulado'):
                continue
            dt_ticket = parse_fecha_ticket(t['fecha'])
            if dt_ticket and dt_inicio <= dt_ticket <= dt_fin:
                tickets_validos.append(t)
        
        stats_por_agencia = {}
        for ag in agencias:
            stats_por_agencia[ag['id']] = {
                'id': ag['id'],
                'nombre': ag['nombre_agencia'],
                'usuario': ag['usuario'],
                'comision_pct': ag['comision'],
                'tickets': 0,
                'ventas': 0,
                'premios_pagados': 0,
                'premios_pendientes': 0,
                'premios_teoricos': 0,
                'comision': 0,
                'balance': 0,
            }
        
        for t in tickets_validos:
            ag_id = t['agencia_id']
            if ag_id not in stats_por_agencia:
                continue
            
            stats = stats_por_agencia[ag_id]
            stats['tickets'] += 1
            stats['ventas'] += t['total']
            
            premio_ticket = calcular_premio_ticket(t)
            stats['premios_teoricos'] += premio_ticket
            
            if t['pagado']:
                stats['premios_pagados'] += premio_ticket
            else:
                stats['premios_pendientes'] += premio_ticket
        
        reporte_agencias = []
        total_global = {'tickets': 0, 'ventas': 0, 'premios_teoricos': 0, 'comision': 0, 'balance': 0}
        
        for ag_id, stats in stats_por_agencia.items():
            if stats['tickets'] > 0:
                stats['comision'] = stats['ventas'] * stats['comision_pct']
                stats['balance'] = stats['ventas'] - stats['premios_teoricos'] - stats['comision']
                
                for k in ['ventas', 'premios_pagados', 'premios_pendientes', 'premios_teoricos', 'comision', 'balance']:
                    stats[k] = round(stats[k], 2)
                
                reporte_agencias.append(stats)
                for key in total_global:
                    if key in stats:
                        total_global[key] += stats[key]
        
        reporte_agencias.sort(key=lambda x: x['ventas'], reverse=True)
        
        return jsonify({
            'status': 'ok',
            'agencias': reporte_agencias,
            'totales': {k: round(v, 2) for k, v in total_global.items()},
            'rango': {'inicio': fecha_inicio, 'fin': fecha_fin}
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== TEMPLATES HTML COMPLETOS ====================
LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
    <title>Login - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body {
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: white;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-box {
            background: rgba(255,255,255,0.05);
            padding: 40px 30px;
            border-radius: 20px;
            border: 2px solid #ffd700;
            width: 100%;
            max-width: 400px;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        .login-box h2 { color: #ffd700; margin-bottom: 30px; font-size: 1.8rem; }
        .form-group { margin-bottom: 20px; text-align: left; }
        .form-group label { display: block; margin-bottom: 8px; color: #aaa; font-size: 0.9rem; }
        .form-group input {
            width: 100%; padding: 15px;
            border: 1px solid #444; border-radius: 10px;
            background: rgba(0,0,0,0.5); color: white; font-size: 1rem;
            -webkit-appearance: none;
        }
        .form-group input:focus {
            outline: none;
            border-color: #ffd700;
            box-shadow: 0 0 10px rgba(255,215,0,0.3);
        }
        .btn-login {
            width: 100%; padding: 16px;
            background: linear-gradient(45deg, #ffd700, #ffed4e);
            color: black; border: none; border-radius: 10px;
            font-size: 1.1rem; font-weight: bold; cursor: pointer;
            margin-top: 10px;
            transition: transform 0.2s;
        }
        .btn-login:active { transform: scale(0.98); }
        .error {
            background: rgba(255,0,0,0.2); color: #ff6b6b;
            padding: 12px; border-radius: 8px; margin-bottom: 20px;
            font-size: 0.9rem;
        }
        .info { margin-top: 25px; font-size: 0.8rem; color: #666; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🦁 ZOOLO CASINO</h2>
        {% if error %}
        <div class="error">{{error}}</div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label>Usuario</label>
                <input type="text" name="usuario" required autofocus autocomplete="off">
            </div>
            <div class="form-group">
                <label>Contraseña</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="btn-login">INICIAR SESIÓN</button>
        </form>
        <div class="info">
            Sistema ZOOLO CASINO v7.0<br>Tripleta x60 + Setup Inicial
        </div>
    </div>
</body>
</html>
'''

POS_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
    <title>POS - {{agencia}}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        html { height: 100%; }
        body { 
            background: #0a0a0a; color: white; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            min-height: 100vh; display: flex; flex-direction: column; overflow-x: hidden;
        }
        .mobile-header {
            display: flex;
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 12px 15px;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #ffd700;
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        .mobile-title { color: #ffd700; font-size: 1.1rem; font-weight: bold; }
        .hamburger-btn {
            background: transparent; border: none; color: #ffd700;
            font-size: 1.5rem; cursor: pointer; padding: 5px;
            width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;
        }
        .mobile-menu {
            display: none; position: fixed; top: 0; right: -300px;
            width: 280px; height: 100vh;
            background: linear-gradient(180deg, #1a1a2e 0%, #0a0a0a 100%);
            border-left: 2px solid #ffd700; z-index: 2000;
            transition: right 0.3s ease; overflow-y: auto;
        }
        .mobile-menu.active { right: 0; display: block; }
        .mobile-menu-header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 15px; background: rgba(0,0,0,0.3); border-bottom: 1px solid #333;
        }
        .mobile-menu-title { color: #ffd700; font-size: 1.1rem; }
        .close-menu-btn {
            background: #c0392b; border: none; color: white;
            width: 30px; height: 30px; border-radius: 50%; cursor: pointer; font-size: 1.1rem;
        }
        .mobile-menu-section { border-bottom: 1px solid #333; }
        .mobile-menu-section-title {
            background: rgba(255,215,0,0.1); color: #ffd700;
            padding: 12px 15px; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;
            border-bottom: 1px solid #333;
        }
        .mobile-menu-item {
            padding: 15px; color: #fff; cursor: pointer; border-bottom: 1px solid #222;
            display: flex; align-items: center; gap: 10px; font-size: 0.95rem;
        }
        .mobile-menu-item:active { background: rgba(255,215,0,0.1); }
        .mobile-menu-overlay {
            display: none; position: fixed; top: 0; left: 0;
            width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1999;
        }
        .mobile-menu-overlay.active { display: block; }
        
        .main-container { 
            display: flex; flex-direction: column; flex: 1;
            height: calc(100vh - 60px); overflow: hidden;
        }
        @media (min-width: 1024px) {
            .main-container { flex-direction: row; }
        }
        
        .left-panel { 
            flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden;
        }
        
        .special-btns { 
            display: grid; grid-template-columns: repeat(4, 1fr);
            gap: 6px; padding: 10px; background: #111; flex-shrink: 0;
        }
        .btn-esp { 
            padding: 12px 4px; border: none; border-radius: 8px;
            font-weight: bold; cursor: pointer; color: white; font-size: 0.8rem;
            touch-action: manipulation; min-height: 44px; transition: all 0.1s;
        }
        .btn-esp:active { transform: scale(0.95); }
        .btn-rojo { background: linear-gradient(135deg, #c0392b, #e74c3c); }
        .btn-negro { background: linear-gradient(135deg, #2c3e50, #34495e); border: 1px solid #555; }
        .btn-par { background: linear-gradient(135deg, #2980b9, #3498db); }
        .btn-impar { background: linear-gradient(135deg, #8e44ad, #9b59b6); }
        .btn-esp.active { 
            box-shadow: 0 0 15px rgba(255,255,255,0.5); transform: scale(0.95); border: 2px solid white;
        }
        
        .animals-grid {
            flex: 1; display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(70px, 1fr));
            gap: 5px; padding: 10px; overflow-y: auto; -webkit-overflow-scrolling: touch;
        }
        @media (min-width: 768px) {
            .animals-grid { grid-template-columns: repeat(7, 1fr); }
        }
        
        .animal-card {
            background: linear-gradient(135deg, #1a1a2e, #16213e); 
            border: 2px solid; border-radius: 10px; padding: 8px 2px;
            text-align: center; cursor: pointer; transition: all 0.15s; 
            min-height: 70px; display: flex; flex-direction: column; justify-content: center;
            user-select: none; position: relative; touch-action: manipulation;
        }
        .animal-card:active { transform: scale(0.92); }
        .animal-card.active { 
            box-shadow: 0 0 15px rgba(255,215,0,0.6); border-color: #ffd700 !important; 
            background: linear-gradient(135deg, #2a2a4e, #1a1a3e);
            transform: scale(1.05); z-index: 10;
        }
        .animal-card.tripleta-seleccionado {
            box-shadow: 0 0 15px rgba(255,215,0,0.9); border-color: #ffd700 !important;
            background: linear-gradient(135deg, #4a3c00, #2a2000);
            transform: scale(1.08); z-index: 15;
        }
        .animal-card .num { font-size: 1.2rem; font-weight: bold; line-height: 1; }
        .animal-card .name { font-size: 0.7rem; color: #aaa; line-height: 1; margin-top: 4px; font-weight: 500; }
        .animal-card.lechuza::after {
            content: "x70"; position: absolute; top: 3px; right: 3px;
            background: #ffd700; color: black; font-size: 0.6rem;
            padding: 2px 4px; border-radius: 4px; font-weight: bold;
        }
        
        .right-panel {
            background: #111; border-top: 2px solid #333;
            display: flex; flex-direction: column; height: 45vh; flex-shrink: 0;
        }
        @media (min-width: 1024px) { 
            .right-panel { width: 400px; height: auto; border-top: none; border-left: 2px solid #333; }
        }
        
        .monto-box { 
            display: flex; align-items: center; justify-content: center; gap: 8px;
            background: rgba(0,0,0,0.3); padding: 10px; border-bottom: 1px solid #333;
        }
        .monto-box span { font-size: 0.9rem; font-weight: bold; color: #ffd700; }
        .monto-box input {
            width: 80px; padding: 8px; border: 2px solid #ffd700; border-radius: 6px;
            background: #000; color: #ffd700; text-align: center; font-weight: bold; font-size: 1.1rem;
            -webkit-appearance: none;
        }
        
        .horarios {
            display: flex; gap: 6px; padding: 10px;
            overflow-x: auto; flex-shrink: 0; background: #0a0a0a;
            -webkit-overflow-scrolling: touch; scrollbar-width: thin; scrollbar-color: #ffd700 #222;
        }
        .horarios::-webkit-scrollbar { height: 8px; }
        .horarios::-webkit-scrollbar-track { background: #222; border-radius: 4px; }
        .horarios::-webkit-scrollbar-thumb { background: #ffd700; border-radius: 4px; }
        
        .btn-hora {
            flex: 0 0 auto; min-width: 85px; padding: 10px 6px;
            background: #222; border: 1px solid #444; border-radius: 8px;
            color: #ccc; cursor: pointer; font-size: 0.75rem;
            text-align: center; line-height: 1.3; touch-action: manipulation;
            transition: all 0.2s;
        }
        .btn-hora:hover { background: #333; border-color: #555; }
        .btn-hora.active { 
            background: linear-gradient(135deg, #27ae60, #229954); 
            color: white; font-weight: bold; border-color: #27ae60;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.4);
        }
        .btn-hora.expired { 
            background: #300; color: #666; text-decoration: line-through; 
            pointer-events: none; opacity: 0.5;
        }
        
        .ticket-display {
            flex: 1; background: #000; margin: 0 10px 10px;
            border-radius: 10px; padding: 12px; border: 1px solid #333;
            overflow-y: auto; font-size: 0.85rem; -webkit-overflow-scrolling: touch;
        }
        
        .ticket-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
        .ticket-table th {
            background: #1a1a2e; color: #ffd700; padding: 8px 6px;
            text-align: left; position: sticky; top: 0; font-size: 0.75rem;
        }
        .ticket-table td { padding: 8px 6px; border-bottom: 1px solid #222; vertical-align: middle; }
        .ticket-table tr:last-child td { border-bottom: none; }
        .ticket-total {
            margin-top: 12px; padding-top: 12px; border-top: 2px solid #ffd700;
            text-align: right; font-size: 1.2rem; font-weight: bold; color: #ffd700;
        }
        
        .action-btns { 
            display: grid; grid-template-columns: repeat(3, 1fr);
            gap: 6px; padding: 10px; background: #0a0a0a; flex-shrink: 0;
        }
        .action-btns button {
            padding: 14px 5px; border: none; border-radius: 8px;
            font-weight: bold; cursor: pointer; font-size: 0.8rem;
            touch-action: manipulation; min-height: 48px; transition: all 0.1s;
        }
        .action-btns button:active { transform: scale(0.95); }
        .btn-agregar { 
            background: linear-gradient(135deg, #27ae60, #229954);
            color: white; grid-column: span 3; font-size: 1.1rem;
        }
        .btn-vender { 
            background: linear-gradient(135deg, #2980b9, #2573a7);
            color: white; grid-column: span 3; font-size: 1rem;
        }
        .btn-resultados { background: #f39c12; color: black; }
        .btn-caja { background: #16a085; color: white; }
        .btn-pagar { background: #8e44ad; color: white; }
        .btn-tripleta { 
            background: linear-gradient(135deg, #FFD700, #FFA500);
            color: black; font-weight: bold; border: 2px solid #FFD700;
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
        }
        .btn-tripleta.active {
            background: linear-gradient(135deg, #FFA500, #FF8C00);
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.6); transform: scale(0.95);
        }
        .btn-anular { background: #c0392b; color: white; }
        .btn-borrar { background: #555; color: white; }
        .btn-salir { background: #333; color: white; grid-column: span 3; }
        
        .tripleta-info {
            background: linear-gradient(135deg, rgba(255,215,0,0.2), rgba(255,165,0,0.1));
            border: 2px solid #FFD700; border-radius: 8px; padding: 10px;
            margin: 0 10px 10px; text-align: center; color: #FFD700;
            font-weight: bold; display: none;
        }
        .tripleta-info.active { display: block; animation: pulse 2s infinite; }
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 5px rgba(255,215,0,0.5); }
            50% { box-shadow: 0 0 20px rgba(255,215,0,0.8); }
        }
        
        .modal {
            display: none; position: fixed; top: 0; left: 0;
            width: 100%; height: 100%; background: rgba(0,0,0,0.95);
            z-index: 1000; overflow-y: auto; -webkit-overflow-scrolling: touch;
        }
        .modal-content {
            background: #1a1a2e; margin: 10px; padding: 20px;
            border-radius: 15px; border: 2px solid #ffd700; max-width: 100%;
            min-height: calc(100vh - 20px);
        }
        @media (min-width: 768px) {
            .modal-content { margin: 40px auto; max-width: 700px; min-height: auto; }
        }
        .modal-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333;
        }
        .modal h3 { color: #ffd700; font-size: 1.3rem; }
        .btn-close {
            background: #c0392b; color: white; border: none;
            padding: 8px 16px; border-radius: 5px; cursor: pointer;
        }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #aaa; font-size: 0.9rem; }
        .form-group input, .form-group select {
            width: 100%; padding: 10px; border: 1px solid #444;
            border-radius: 5px; background: #222; color: white;
        }
        .results-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 10px; margin-top: 15px;
        }
        .result-item {
            background: rgba(255,255,255,0.05); padding: 10px;
            border-radius: 8px; text-align: center; border: 1px solid #333;
        }
        .result-time { font-size: 0.8rem; color: #888; margin-bottom: 5px; }
        .result-animal { font-size: 1.1rem; color: #ffd700; font-weight: bold; }
        .empty-result { color: #666; font-style: italic; }
        .tabs {
            display: flex; gap: 10px; margin-bottom: 20px;
            border-bottom: 1px solid #333; padding-bottom: 10px;
        }
        .tab {
            padding: 10px 20px; background: #222; border: none;
            color: #888; cursor: pointer; border-radius: 5px; font-weight: bold;
        }
        .tab.active { background: #ffd700; color: black; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .ticket-item {
            background: rgba(255,255,255,0.05); padding: 15px;
            margin-bottom: 10px; border-radius: 8px; border-left: 3px solid #ffd700;
        }
        .ticket-serial { font-weight: bold; color: #ffd700; }
        .ticket-fecha { font-size: 0.8rem; color: #888; }
        .ticket-monto { float: right; font-weight: bold; }
    </style>
</head>
<body>
    <div class="mobile-header">
        <div class="mobile-title">🦁 {{agencia}}</div>
        <button class="hamburger-btn" onclick="toggleMenu()">☰</button>
    </div>
    
    <div class="mobile-menu-overlay" onclick="toggleMenu()"></div>
    <div class="mobile-menu" id="mobileMenu">
        <div class="mobile-menu-header">
            <div class="mobile-menu-title">Menú</div>
            <button class="close-menu-btn" onclick="toggleMenu()">×</button>
        </div>
        <div class="mobile-menu-section">
            <div class="mobile-menu-section-title">Operaciones</div>
            <div class="mobile-menu-item" onclick="verResultados(); toggleMenu();">📊 Resultados</div>
            <div class="mobile-menu-item" onclick="verCaja(); toggleMenu();">💰 Caja del Día</div>
            <div class="mobile-menu-item" onclick="verMisTickets(); toggleMenu();">🎫 Mis Tickets</div>
            <div class="mobile-menu-item" onclick="pagarTicket(); toggleMenu();">💵 Pagar Ticket</div>
        </div>
        <div class="mobile-menu-section">
            <div class="mobile-menu-section-title">Sistema</div>
            <div class="mobile-menu-item" onclick="window.location='/logout'">🚪 Cerrar Sesión</div>
        </div>
    </div>

    <div class="main-container">
        <div class="left-panel">
            <div class="special-btns">
                <button class="btn-esp btn-rojo" onclick="seleccionarEspecial('ROJO', this)">ROJO</button>
                <button class="btn-esp btn-negro" onclick="seleccionarEspecial('NEGRO', this)">NEGRO</button>
                <button class="btn-esp btn-par" onclick="seleccionarEspecial('PAR', this)">PAR</button>
                <button class="btn-esp btn-impar" onclick="seleccionarEspecial('IMPAR', this)">IMPAR</button>
            </div>
            
            <div class="animals-grid" id="animalsGrid">
                {% for num, nombre in animales.items() %}
                <div class="animal-card {{ 'lechuza' if num == '40' else '' }}" 
                     style="border-color: {{ get_color(num) }}"
                     onclick="seleccionarAnimal('{{ num }}', '{{ nombre }}')"
                     data-num="{{ num }}">
                    <div class="num">{{ num }}</div>
                    <div class="name">{{ nombre[:3] }}</div>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div class="right-panel">
            <div class="monto-box">
                <span>MONTO: S/</span>
                <input type="number" id="montoInput" value="5" min="1" step="1">
            </div>
            
            <div class="tripleta-info" id="tripletaInfo">
                Modo Tripleta Activo: Selecciona 3 animales<br>
                <small>Paga x60 si salen los 3 en el día</small>
            </div>
            
            <div class="horarios" id="horariosContainer">
                {% for hora in horarios_peru %}
                <button class="btn-hora" onclick="seleccionarHora('{{ hora }}', this)" data-hora="{{ hora }}">
                    {{ hora }}
                </button>
                {% endfor %}
            </div>
            
            <div class="ticket-display" id="ticketDisplay">
                <table class="ticket-table" id="ticketTable">
                    <thead>
                        <tr>
                            <th>Hora</th>
                            <th>Jugada</th>
                            <th>Monto</th>
                            <th>Del</th>
                        </tr>
                    </thead>
                    <tbody id="ticketBody">
                        <tr>
                            <td colspan="4" style="text-align: center; color: #666; padding: 20px;">
                                Ticket vacío. Selecciona jugadas.
                            </td>
                        </tr>
                    </tbody>
                </table>
                <div class="ticket-total" id="ticketTotal">TOTAL: S/0.00</div>
            </div>
            
            <div class="action-btns">
                <button class="btn-agregar" onclick="agregarJugada()">➕ AGREGAR AL TICKET</button>
                <button class="btn-resultados" onclick="verResultados()">📊 RESULTADOS</button>
                <button class="btn-caja" onclick="verCaja()">💰 CAJA</button>
                <button class="btn-pagar" onclick="pagarTicket()">💵 PAGAR</button>
                <button class="btn-tripleta" id="btnTripleta" onclick="toggleTripleta()">🎲 TRIPLETA</button>
                <button class="btn-anular" onclick="anularTicket()">❌ ANULAR</button>
                <button class="btn-borrar" onclick="borrarUltima()">🗑️ BORRAR</button>
                <button class="btn-vender" onclick="venderTicket()">✅ VENDER TICKET</button>
                <button class="btn-salir" onclick="window.location='/logout'">🚪 SALIR</button>
            </div>
        </div>
    </div>

    <!-- Modal Resultados -->
    <div id="modalResultados" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>📊 Resultados del Día</h3>
                <button class="btn-close" onclick="cerrarModal('modalResultados')">Cerrar</button>
            </div>
            <div class="results-grid" id="resultsGrid"></div>
        </div>
    </div>

    <!-- Modal Caja -->
    <div id="modalCaja" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>💰 Caja del Día</h3>
                <button class="btn-close" onclick="cerrarModal('modalCaja')">Cerrar</button>
            </div>
            <div id="cajaContent"></div>
        </div>
    </div>

    <!-- Modal Pagar -->
    <div id="modalPagar" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>💵 Pagar Ticket</h3>
                <button class="btn-close" onclick="cerrarModal('modalPagar')">Cerrar</button>
            </div>
            <div class="form-group">
                <label>Número de Serial:</label>
                <input type="text" id="serialPagar" placeholder="Ej: 1234567890">
            </div>
            <button class="btn-vender" onclick="consultarTicketPagar()" style="width: 100%; margin-bottom: 10px;">
                Verificar Ticket
            </button>
            <div id="infoPago"></div>
        </div>
    </div>

    <!-- Modal Mis Tickets -->
    <div id="modalTickets" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>🎫 Mis Tickets</h3>
                <button class="btn-close" onclick="cerrarModal('modalTickets')">Cerrar</button>
            </div>
            <div class="form-group">
                <label>Fecha Inicio:</label>
                <input type="date" id="fechaInicioTickets">
            </div>
            <div class="form-group">
                <label>Fecha Fin:</label>
                <input type="date" id="fechaFinTickets">
            </div>
            <button class="btn-vender" onclick="cargarMisTickets()" style="width: 100%; margin-bottom: 10px;">
                Buscar Tickets
            </button>
            <div id="listaTickets"></div>
        </div>
    </div>

    <script>
        let jugadas = [];
        let seleccionActual = null;
        let horaSeleccionada = null;
        let modoTripleta = false;
        let seleccionTripleta = [];

        // Inicializar fechas en los inputs
        document.getElementById('fechaInicioTickets').valueAsDate = new Date();
        document.getElementById('fechaFinTickets').valueAsDate = new Date();

        function toggleMenu() {
            document.getElementById('mobileMenu').classList.toggle('active');
            document.querySelector('.mobile-menu-overlay').classList.toggle('active');
        }

        function seleccionarAnimal(num, nombre) {
            if (modoTripleta) {
                const idx = seleccionTripleta.indexOf(num);
                const card = document.querySelector(`[data-num="${num}"]`);
                
                if (idx > -1) {
                    seleccionTripleta.splice(idx, 1);
                    card.classList.remove('tripleta-seleccionado');
                } else {
                    if (seleccionTripleta.length < 3) {
                        seleccionTripleta.push(num);
                        card.classList.add('tripleta-seleccionado');
                    } else {
                        alert('Ya seleccionaste 3 animales. Deselecciona uno primero.');
                    }
                }
            } else {
                document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('active'));
                document.querySelector(`[data-num="${num}"]`).classList.add('active');
                seleccionActual = {tipo: 'animal', valor: num, nombre: nombre};
            }
        }

        function seleccionarEspecial(tipo, btn) {
            if (modoTripleta) return;
            document.querySelectorAll('.btn-esp').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            seleccionActual = {tipo: 'especial', valor: tipo};
        }

        function seleccionarHora(hora, btn) {
            if (modoTripleta) return;
            document.querySelectorAll('.btn-hora').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            horaSeleccionada = hora;
        }

        function toggleTripleta() {
            modoTripleta = !modoTripleta;
            const btn = document.getElementById('btnTripleta');
            const info = document.getElementById('tripletaInfo');
            
            if (modoTripleta) {
                btn.classList.add('active');
                info.classList.add('active');
                seleccionTripleta = [];
                document.querySelectorAll('.animal-card').forEach(c => {
                    c.classList.remove('active');
                    c.classList.remove('tripleta-seleccionado');
                });
                document.querySelectorAll('.btn-esp').forEach(b => b.classList.remove('active'));
                seleccionActual = null;
                horaSeleccionada = null;
            } else {
                btn.classList.remove('active');
                info.classList.remove('active');
                seleccionTripleta = [];
                document.querySelectorAll('.animal-card').forEach(c => {
                    c.classList.remove('tripleta-seleccionado');
                });
            }
        }

        function agregarJugada() {
            const monto = parseFloat(document.getElementById('montoInput').value);
            
            if (!monto || monto <= 0) {
                alert('Ingresa un monto válido');
                return;
            }

            if (modoTripleta) {
                if (seleccionTripleta.length !== 3) {
                    alert('Debes seleccionar exactamente 3 animales para la tripleta');
                    return;
                }
                jugadas.push({
                    tipo: 'tripleta',
                    seleccion: seleccionTripleta.join(','),
                    monto: monto,
                    hora: 'Todo el día'
                });
                
                seleccionTripleta = [];
                document.querySelectorAll('.animal-card').forEach(c => {
                    c.classList.remove('tripleta-seleccionado');
                });
            } else {
                if (!seleccionActual) {
                    alert('Selecciona un animal o especial');
                    return;
                }
                if (!horaSeleccionada) {
                    alert('Selecciona un horario');
                    return;
                }

                jugadas.push({
                    tipo: seleccionActual.tipo,
                    seleccion: seleccionActual.valor,
                    nombre: seleccionActual.nombre || seleccionActual.valor,
                    monto: monto,
                    hora: horaSeleccionada
                });

                document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('active'));
                document.querySelectorAll('.btn-esp').forEach(b => b.classList.remove('active'));
                seleccionActual = null;
            }

            actualizarTicket();
        }

        function actualizarTicket() {
            const tbody = document.getElementById('ticketBody');
            const totalEl = document.getElementById('ticketTotal');
            
            if (jugadas.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #666; padding: 20px;">Ticket vacío. Selecciona jugadas.</td></tr>';
                totalEl.textContent = 'TOTAL: S/0.00';
                return;
            }

            let html = '';
            let total = 0;

            jugadas.forEach((j, idx) => {
                total += j.monto;
                let display = '';
                if (j.tipo === 'animal') {
                    display = j.nombre;
                } else if (j.tipo === 'tripleta') {
                    display = 'Tripleta: ' + j.seleccion;
                } else {
                    display = j.seleccion;
                }
                
                html += `
                    <tr>
                        <td>${j.hora}</td>
                        <td>${display}</td>
                        <td>S/${j.monto}</td>
                        <td><button onclick="eliminarJugada(${idx})" style="background:#c0392b;color:white;border:none;padding:2px 8px;border-radius:3px;cursor:pointer;">X</button></td>
                    </tr>
                `;
            });

            tbody.innerHTML = html;
            totalEl.textContent = `TOTAL: S/${total.toFixed(2)}`;
        }

        function eliminarJugada(idx) {
            jugadas.splice(idx, 1);
            actualizarTicket();
        }

        function borrarUltima() {
            if (jugadas.length > 0) {
                jugadas.pop();
                actualizarTicket();
            }
        }

        async function venderTicket() {
            if (jugadas.length === 0) {
                alert('El ticket está vacío');
                return;
            }

            try {
                const response = await fetch('/api/procesar-venta', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({jugadas: jugadas})
                });

                const data = await response.json();
                
                if (data.status === 'ok') {
                    if (confirm(`Ticket #${data.ticket_id} creado. Total: S/${data.total}\\n\\n¿Compartir por WhatsApp?`)) {
                        window.open(data.url_whatsapp, '_blank');
                    }
                    jugadas = [];
                    actualizarTicket();
                } else {
                    alert('Error: ' + (data.error || 'Desconocido'));
                }
            } catch (e) {
                alert('Error de conexión: ' + e.message);
            }
        }

        async function verResultados() {
            try {
                const response = await fetch('/api/resultados-hoy');
                const data = await response.json();
                
                if (data.status === 'ok') {
                    let html = '';
                    const horarios = {{ horarios_peru | tojson }};
                    
                    horarios.forEach(hora => {
                        const res = data.resultados[hora];
                        if (res) {
                            html += `
                                <div class="result-item">
                                    <div class="result-time">${hora}</div>
                                    <div class="result-animal">${res.animal} - ${res.nombre}</div>
                                </div>
                            `;
                        } else {
                            html += `
                                <div class="result-item">
                                    <div class="result-time">${hora}</div>
                                    <div class="empty-result">Sin resultado</div>
                                </div>
                            `;
                        }
                    });
                    
                    document.getElementById('resultsGrid').innerHTML = html;
                    document.getElementById('modalResultados').style.display = 'block';
                }
            } catch (e) {
                alert('Error cargando resultados');
            }
        }

        async function verCaja() {
            try {
                const response = await fetch('/api/caja');
                const data = await response.json();
                
                let html = `
                    <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                        <h4 style="color: #ffd700; margin-bottom: 15px;">Resumen del Día</h4>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                            <span>Ventas:</span>
                            <span style="color: #27ae60; font-weight: bold;">S/${data.ventas}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                            <span>Premios Pagados:</span>
                            <span style="color: #e74c3c; font-weight: bold;">S/${data.premios}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                            <span>Comisión (15%):</span>
                            <span style="color: #f39c12; font-weight: bold;">S/${data.comision}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding-top: 10px; border-top: 2px solid #333; font-size: 1.2rem;">
                            <span>Balance:</span>
                            <span style="color: ${data.balance >= 0 ? '#27ae60' : '#e74c3c'}; font-weight: bold;">S/${data.balance}</span>
                        </div>
                    </div>
                    <div style="text-align: center; color: #888;">
                        Tickets pendientes de pago: <strong style="color: #ffd700;">${data.tickets_pendientes}</strong>
                    </div>
                `;
                
                document.getElementById('cajaContent').innerHTML = html;
                document.getElementById('modalCaja').style.display = 'block';
            } catch (e) {
                alert('Error cargando caja');
            }
        }

        async function pagarTicket() {
            document.getElementById('modalPagar').style.display = 'block';
        }

        async function consultarTicketPagar() {
            const serial = document.getElementById('serialPagar').value;
            if (!serial) return;

            try {
                const response = await fetch('/api/verificar-ticket', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({serial: serial})
                });
                
                const data = await response.json();
                const infoDiv = document.getElementById('infoPago');
                
                if (data.error) {
                    infoDiv.innerHTML = `<div style="color: #e74c3c; padding: 10px; background: rgba(231, 76, 60, 0.1); border-radius: 5px;">${data.error}</div>`;
                } else {
                    infoDiv.innerHTML = `
                        <div style="background: rgba(39, 174, 96, 0.1); padding: 15px; border-radius: 5px; margin-bottom: 10px;">
                            <h4 style="color: #27ae60; margin-bottom: 10px;">Ticket Ganador!</h4>
                            <p style="font-size: 1.3rem; color: #ffd700; font-weight: bold;">Monto a Pagar: S/${data.total_ganado}</p>
                        </div>
                        <button class="btn-vender" onclick="confirmarPago('${data.ticket_id}')" style="width: 100%;">
                            Confirmar Pago
                        </button>
                    `;
                }
            } catch (e) {
                alert('Error verificando ticket');
            }
        }

        async function confirmarPago(ticketId) {
            if (!confirm('¿Confirmas que vas a pagar este ticket?')) return;

            try {
                const response = await fetch('/api/pagar-ticket', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ticket_id: ticketId})
                });
                
                const data = await response.json();
                if (data.status === 'ok') {
                    alert('Ticket pagado exitosamente');
                    cerrarModal('modalPagar');
                    document.getElementById('serialPagar').value = '';
                    document.getElementById('infoPago').innerHTML = '';
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (e) {
                alert('Error procesando pago');
            }
        }

        async function anularTicket() {
            const serial = prompt('Ingresa el número de serial del ticket a anular:');
            if (!serial) return;

            if (!confirm('¿Estás seguro de anular este ticket?')) return;

            try {
                const response = await fetch('/api/anular-ticket', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({serial: serial})
                });
                
                const data = await response.json();
                if (data.status === 'ok') {
                    alert('Ticket anulado correctamente');
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (e) {
                alert('Error anulando ticket');
            }
        }

        async function verMisTickets() {
            document.getElementById('modalTickets').style.display = 'block';
        }

        async function cargarMisTickets() {
            const fechaInicio = document.getElementById('fechaInicioTickets').value;
            const fechaFin = document.getElementById('fechaFinTickets').value;

            try {
                const response = await fetch('/api/mis-tickets', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        fecha_inicio: fechaInicio,
                        fecha_fin: fechaFin,
                        estado: 'todos'
                    })
                });
                
                const data = await response.json();
                const listaDiv = document.getElementById('listaTickets');
                
                if (data.tickets && data.tickets.length > 0) {
                    let html = `<div style="margin-bottom: 15px; color: #888;">Mostrando ${data.tickets.length} de ${data.totales.cantidad} tickets</div>`;
                    
                    data.tickets.forEach(t => {
                        html += `
                            <div class="ticket-item">
                                <div class="ticket-serial">#${t.serial}</div>
                                <div class="ticket-fecha">${t.fecha}</div>
                                <div class="ticket-monto">S/${t.total}</div>
                                <div style="clear: both;"></div>
                            </div>
                        `;
                    });
                    
                    html += `
                        <div style="background: rgba(255,215,0,0.1); padding: 15px; border-radius: 8px; margin-top: 15px;">
                            <strong style="color: #ffd700;">Total Ventas: S/${data.totales.ventas}</strong>
                        </div>
                    `;
                    
                    listaDiv.innerHTML = html;
                } else {
                    listaDiv.innerHTML = '<div style="text-align: center; color: #666; padding: 20px;">No se encontraron tickets</div>';
                }
            } catch (e) {
                alert('Error cargando tickets');
            }
        }

        function cerrarModal(id) {
            document.getElementById(id).style.display = 'none';
        }

        // Verificar bloqueo de horarios cada minuto
        setInterval(async () => {
            try {
                const response = await fetch('/api/resultados-hoy');
                const data = await response.json();
                // Actualizar visualización de horarios bloqueados si es necesario
            } catch (e) {}
        }, 60000);
    </script>
</body>
</html>
'''

ADMIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Administración - ZOOLO CASINO</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            background: #0a0a0a; color: white; 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
        }
        .header {
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 20px; text-align: center;
            border-bottom: 3px solid #ffd700;
        }
        .header h1 { color: #ffd700; margin-bottom: 5px; }
        .header p { color: #888; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px; margin-top: 20px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border: 1px solid #333; border-radius: 10px;
            padding: 20px;
        }
        .card h3 {
            color: #ffd700; margin-bottom: 15px;
            border-bottom: 1px solid #333; padding-bottom: 10px;
        }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #aaa; }
        .form-group input, .form-group select {
            width: 100%; padding: 10px;
            background: #222; border: 1px solid #444;
            color: white; border-radius: 5px;
        }
        .btn {
            padding: 12px 24px; border: none; border-radius: 5px;
            cursor: pointer; font-weight: bold; transition: all 0.3s;
        }
        .btn-primary { background: #ffd700; color: black; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn:hover { opacity: 0.9; transform: translateY(-1px); }
        .results-table {
            width: 100%; border-collapse: collapse; margin-top: 15px;
        }
        .results-table th, .results-table td {
            padding: 10px; text-align: left; border-bottom: 1px solid #333;
        }
        .results-table th { color: #ffd700; background: rgba(255,215,0,0.1); }
        .stats-grid {
            display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;
            margin-bottom: 20px;
        }
        .stat-box {
            background: rgba(255,255,255,0.05); padding: 15px;
            border-radius: 8px; text-align: center;
        }
        .stat-value {
            font-size: 1.5rem; font-weight: bold; color: #ffd700;
        }
        .stat-label { color: #888; font-size: 0.9rem; }
        .nav-tabs {
            display: flex; gap: 10px; margin-bottom: 20px;
            border-bottom: 2px solid #333; padding-bottom: 10px;
        }
        .nav-tab {
            padding: 10px 20px; background: #222; border: none;
            color: #888; cursor: pointer; border-radius: 5px 5px 0 0;
        }
        .nav-tab.active { background: #ffd700; color: black; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .animal-select {
            display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px;
            max-height: 200px; overflow-y: auto;
        }
        .animal-option {
            padding: 8px; text-align: center;
            background: #222; border: 1px solid #444;
            cursor: pointer; border-radius: 5px; font-size: 0.8rem;
        }
        .animal-option:hover { background: #333; }
        .animal-option.selected {
            background: #ffd700; color: black; font-weight: bold;
        }
        #message {
            position: fixed; top: 20px; right: 20px;
            padding: 15px 20px; border-radius: 5px;
            display: none; z-index: 1000;
        }
        .message-success { background: #27ae60; }
        .message-error { background: #e74c3c; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🦁 ZOOLO CASINO - ADMIN</h1>
        <p>Panel de Control y Administración</p>
    </div>

    <div class="nav-tabs" style="max-width: 1200px; margin: 20px auto 0; padding: 0 20px;">
        <button class="nav-tab active" onclick="showTab('resultados')">Resultados</button>
        <button class="nav-tab" onclick="showTab('agencias')">Agencias</button>
        <button class="nav-tab" onclick="showTab('reportes')">Reportes</button>
        <button class="nav-tab" onclick="showTab('riesgo')">Riesgo</button>
        <button class="nav-tab" onclick="window.location='/logout'">Salir</button>
    </div>

    <div class="container">
        <div id="message"></div>

        <!-- Tab Resultados -->
        <div id="tab-resultados" class="tab-content active">
            <div class="grid">
                <div class="card">
                    <h3>🎯 Ingresar Resultado</h3>
                    <form id="formResultado" onsubmit="guardarResultado(event)">
                        <div class="form-group">
                            <label>Fecha (dejar vacío para hoy):</label>
                            <input type="date" id="fechaResultado">
                        </div>
                        <div class="form-group">
                            <label>Horario:</label>
                            <select id="horaResultado" required>
                                {% for hora in horarios %}
                                <option value="{{ hora }}">{{ hora }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Animal Ganador:</label>
                            <select id="animalResultado" required>
                                {% for num, nombre in animales.items() %}
                                <option value="{{ num }}">{{ num }} - {{ nombre }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <button type="submit" class="btn btn-primary" style="width: 100%;">
                            💾 Guardar Resultado
                        </button>
                    </form>
                </div>

                <div class="card">
                    <h3>📊 Resultados de Hoy</h3>
                    <div id="resultadosHoy">
                        <p style="color: #666; text-align: center;">Cargando...</p>
                    </div>
                    <button class="btn btn-success" onclick="cargarResultadosHoy()" style="width: 100%; margin-top: 10px;">
                        🔄 Actualizar
                    </button>
                </div>
            </div>
        </div>

        <!-- Tab Agencias -->
        <div id="tab-agencias" class="tab-content">
            <div class="grid">
                <div class="card">
                    <h3>➕ Crear Nueva Agencia</h3>
                    <form id="formAgencia" onsubmit="crearAgencia(event)">
                        <div class="form-group">
                            <label>Nombre de la Agencia:</label>
                            <input type="text" id="nombreAgencia" required placeholder="Ej: Agencia Principal">
                        </div>
                        <div class="form-group">
                            <label>Usuario (login):</label>
                            <input type="text" id="usuarioAgencia" required placeholder="Ej: agencia01">
                        </div>
                        <div class="form-group">
                            <label>Contraseña:</label>
                            <input type="password" id="passwordAgencia" required>
                        </div>
                        <button type="submit" class="btn btn-primary" style="width: 100%;">
                            Crear Agencia
                        </button>
                    </form>
                </div>

                <div class="card">
                    <h3>📋 Lista de Agencias</h3>
                    <div id="listaAgencias" style="max-height: 300px; overflow-y: auto;">
                        <p style="color: #666;">Cargando...</p>
                    </div>
                    <button class="btn btn-success" onclick="cargarAgencias()" style="width: 100%; margin-top: 10px;">
                        🔄 Actualizar Lista
                    </button>
                </div>
            </div>
        </div>

        <!-- Tab Reportes -->
        <div id="tab-reportes" class="tab-content">
            <div class="card" style="margin-bottom: 20px;">
                <h3>📈 Reporte por Rango de Fechas</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 10px; align-items: end;">
                    <div class="form-group" style="margin: 0;">
                        <label>Fecha Inicio:</label>
                        <input type="date" id="reporteFechaInicio">
                    </div>
                    <div class="form-group" style="margin: 0;">
                        <label>Fecha Fin:</label>
                        <input type="date" id="reporteFechaFin">
                    </div>
                    <button class="btn btn-primary" onclick="generarReporte()">Generar</button>
                </div>
            </div>
            
            <div id="resultadoReporte"></div>
        </div>

        <!-- Tab Riesgo -->
        <div id="tab-riesgo" class="tab-content">
            <div class="card">
                <h3>⚠️ Análisis de Riesgo por Sorteo</h3>
                <div class="form-group">
                    <label>Seleccionar Agencia (opcional):</label>
                    <select id="riesgoAgencia">
                        <option value="">Todas las agencias</option>
                    </select>
                </div>
                <button class="btn btn-primary" onclick="cargarRiesgo()" style="width: 100%; margin-bottom: 20px;">
                    Analizar Riesgo
                </button>
                <div id="riesgoContent"></div>
            </div>
        </div>
    </div>

    <script>
        // Inicializar fechas
        document.getElementById('fechaResultado').valueAsDate = new Date();
        document.getElementById('reporteFechaInicio').valueAsDate = new Date();
        document.getElementById('reporteFechaFin').valueAsDate = new Date();

        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.add('active');
            event.target.classList.add('active');
            
            if (tabName === 'resultados') cargarResultadosHoy();
            if (tabName === 'agencias') cargarAgencias();
        }

        function showMessage(text, type) {
            const msg = document.getElementById('message');
            msg.textContent = text;
            msg.className = type === 'error' ? 'message-error' : 'message-success';
            msg.style.display = 'block';
            setTimeout(() => msg.style.display = 'none', 3000);
        }

        async function guardarResultado(e) {
            e.preventDefault();
            const formData = new FormData();
            formData.append('fecha', document.getElementById('fechaResultado').value);
            formData.append('hora', document.getElementById('horaResultado').value);
            formData.append('animal', document.getElementById('animalResultado').value);

            try {
                const response = await fetch('/admin/guardar-resultado', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                
                if (data.status === 'ok') {
                    showMessage(data.mensaje, 'success');
                    cargarResultadosHoy();
                } else {
                    showMessage('Error: ' + data.error, 'error');
                }
            } catch (e) {
                showMessage('Error de conexión', 'error');
            }
        }

        async function cargarResultadosHoy() {
            try {
                const response = await fetch('/admin/resultados-hoy');
                const data = await response.json();
                
                if (data.status === 'ok') {
                    let html = '<table class="results-table">';
                    html += '<tr><th>Horario</th><th>Resultado</th></tr>';
                    
                    const horarios = {{ horarios | tojson }};
                    horarios.forEach(hora => {
                        const res = data.resultados[hora];
                        html += `<tr>
                            <td>${hora}</td>
                            <td style="color: ${res ? '#ffd700' : '#666'}">
                                ${res ? res.animal + ' - ' + res.nombre : 'Sin resultado'}
                            </td>
                        </tr>`;
                    });
                    html += '</table>';
                    document.getElementById('resultadosHoy').innerHTML = html;
                }
            } catch (e) {
                document.getElementById('resultadosHoy').innerHTML = '<p style="color: #e74c3c;">Error cargando resultados</p>';
            }
        }

        async function crearAgencia(e) {
            e.preventDefault();
            const formData = new FormData();
            formData.append('nombre', document.getElementById('nombreAgencia').value);
            formData.append('usuario', document.getElementById('usuarioAgencia').value);
            formData.append('password', document.getElementById('passwordAgencia').value);

            try {
                const response = await fetch('/admin/crear-agencia', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                
                if (data.status === 'ok') {
                    showMessage(data.mensaje, 'success');
                    document.getElementById('formAgencia').reset();
                    cargarAgencias();
                } else {
                    showMessage('Error: ' + data.error, 'error');
                }
            } catch (e) {
                showMessage('Error de conexión', 'error');
            }
        }

        async function cargarAgencias() {
            try {
                const response = await fetch('/admin/lista-agencias');
                const data = await response.json();
                
                let html = '<table class="results-table">';
                html += '<tr><th>Agencia</th><th>Usuario</th><th>Comisión</th></tr>';
                
                data.forEach(ag => {
                    html += `<tr>
                        <td>${ag.nombre_agencia}</td>
                        <td>${ag.usuario}</td>
                        <td>${(ag.comision * 100)}%</td>
                    </tr>`;
                });
                html += '</table>';
                
                document.getElementById('listaAgencias').innerHTML = html;
                
                // Actualizar select de riesgo
                const selectRiesgo = document.getElementById('riesgoAgencia');
                selectRiesgo.innerHTML = '<option value="">Todas las agencias</option>';
                data.forEach(ag => {
                    selectRiesgo.innerHTML += `<option value="${ag.id}">${ag.nombre_agencia}</option>`;
                });
            } catch (e) {
                document.getElementById('listaAgencias').innerHTML = '<p style="color: #e74c3c;">Error cargando agencias</p>';
            }
        }

        async function generarReporte() {
            const fechaInicio = document.getElementById('reporteFechaInicio').value;
            const fechaFin = document.getElementById('reporteFechaFin').value;
            
            try {
                const response = await fetch('/admin/reporte-agencias-rango', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({fecha_inicio: fechaInicio, fecha_fin: fechaFin})
                });
                
                const data = await response.json();
                const div = document.getElementById('resultadoReporte');
                
                if (data.status === 'ok') {
                    let html = '<div class="grid">';
                    
                    data.agencias.forEach(ag => {
                        html += `
                            <div class="card">
                                <h3>${ag.nombre}</h3>
                                <div class="stats-grid">
                                    <div class="stat-box">
                                        <div class="stat-value">${ag.tickets}</div>
                                        <div class="stat-label">Tickets</div>
                                    </div>
                                    <div class="stat-box">
                                        <div class="stat-value">S/${ag.ventas}</div>
                                        <div class="stat-label">Ventas</div>
                                    </div>
                                    <div class="stat-box">
                                        <div class="stat-value">S/${ag.premios_teoricos}</div>
                                        <div class="stat-label">Premios</div>
                                    </div>
                                    <div class="stat-box">
                                        <div class="stat-value" style="color: ${ag.balance >= 0 ? '#27ae60' : '#e74c3c'}">
                                            S/${ag.balance}
                                        </div>
                                        <div class="stat-label">Balance</div>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                    
                    // Totales
                    html += `
                        <div class="card" style="margin-top: 20px; background: rgba(255,215,0,0.1);">
                            <h3>Totales Generales</h3>
                            <div class="stats-grid">
                                <div class="stat-box">
                                    <div class="stat-value">${data.totales.tickets}</div>
                                    <div class="stat-label">Total Tickets</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-value">S/${data.totales.ventas}</div>
                                    <div class="stat-label">Total Ventas</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-value">S/${data.totales.premios_teoricos}</div>
                                    <div class="stat-label">Total Premios</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-value" style="color: ${data.totales.balance >= 0 ? '#27ae60' : '#e74c3c'}">
                                        S/${data.totales.balance}
                                    </div>
                                    <div class="stat-label">Balance Total</div>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    div.innerHTML = html;
                } else {
                    div.innerHTML = `<p style="color: #e74c3c;">Error: ${data.error}</p>`;
                }
            } catch (e) {
                document.getElementById('resultadoReporte').innerHTML = '<p style="color: #e74c3c;">Error generando reporte</p>';
            }
        }

        async function cargarRiesgo() {
            const agenciaId = document.getElementById('riesgoAgencia').value;
            try {
                const url = agenciaId ? `/admin/riesgo?agencia_id=${agenciaId}` : '/admin/riesgo';
                const response = await fetch(url);
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('riesgoContent').innerHTML = `<p style="color: #e74c3c;">${data.error}</p>`;
                    return;
                }
                
                let html = `
                    <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                        <strong>Sorteo:</strong> ${data.sorteo_objetivo || 'N/A'}<br>
                        <strong>Total Apostado:</strong> S/${data.total_apostado}<br>
                        <strong>Agencia:</strong> ${data.agencia_nombre}
                    </div>
                    <h4 style="color: #ffd700; margin-bottom: 10px;">Top Apuestas:</h4>
                `;
                
                if (Object.keys(data.riesgo).length === 0) {
                    html += '<p style="color: #666;">No hay apuestas para este sorteo</p>';
                } else {
                    html += '<table class="results-table">';
                    html += '<tr><th>Animal</th><th>Apostado</th><th>Pagaría</th><th>%</th></tr>';
                    
                    for (const [animal, info] of Object.entries(data.riesgo)) {
                        html += `<tr>
                            <td>${animal} ${info.es_lechuza ? '👑' : ''}</td>
                            <td>S/${info.apostado}</td>
                            <td style="color: ${info.pagaria > data.total_apostado ? '#e74c3c' : '#27ae60'}">
                                S/${info.pagaria}
                            </td>
                            <td>${info.porcentaje}%</td>
                        </tr>`;
                    }
                    html += '</table>';
                }
                
                document.getElementById('riesgoContent').innerHTML = html;
            } catch (e) {
                document.getElementById('riesgoContent').innerHTML = '<p style="color: #e74c3c;">Error cargando riesgo</p>';
            }
        }

        // Cargar datos iniciales
        cargarResultadosHoy();
        cargarAgencias();
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
