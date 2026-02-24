#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v6.1 - TRIPLETA x60 CORREGIDA
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

# ==================== CONFIGURACION SUPABASE ====================
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://iuwgbtmhkqnqulwgcgkk.supabase.co').strip()
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml1d2didG1oa3FucXVsd2djZ2trIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEwMTM0OTQsImV4cCI6MjA4NjU4OTQ5NH0.HJGQk5JppC34OHWhQY9Goou617uxB1QVuIQLD72NLgE').strip()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'zoolo_casino_cloud_2025_seguro')

PAGO_ANIMAL_NORMAL = 35      
PAGO_LECHUZA = 70           
PAGO_ESPECIAL = 2           
PAGO_TRIPLETA = 60          
COMISION_AGENCIA = 0.15
MINUTOS_BLOQUEO = 5
HORAS_EDICION_RESULTADO = 2

HORARIOS_PERU = [
    "08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
    "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM"
]

HORARIOS_VENEZUELA = [
    "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM",
    "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM"
]

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

def ahora_peru():
    try:
        return datetime.now(timezone.utc) - timedelta(hours=5)
    except:
        return datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(hours=5)

def parse_fecha_ticket(fecha_str):
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
    return True

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

# ==================== CAMBIO 1: supabase_request CORREGIDA ====================
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
    
    # IMPORTANTE: El límite SOLO se aplica al GET, de lo contrario rompe los POST/PATCH
    if method == "GET":
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
                    return False
                raise e
                
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.read().decode()} on {method} {url}")
        return None
    except Exception as e:
        print(f"[ERROR] Supabase: {e} on {method}")
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

# ==================== API POS ====================

# ==================== CAMBIO 2: resultados_hoy con isinstance ====================
@app.route('/api/resultados-hoy')
@login_required
def resultados_hoy():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        resultados_list = supabase_request("resultados", filters={"fecha": hoy})
        
        resultados_dict = {}
        # Validar que sí es una lista y no un error dict de Supabase
        if isinstance(resultados_list, list):
            for r in resultados_list:
                animal_str = str(r.get('animal', ''))
                resultados_dict[r['hora']] = {
                    'animal': animal_str,
                    'nombre': ANIMALES.get(animal_str, 'Desconocido')
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

# ==================== CAMBIO 3: resultados_fecha con isinstance ====================
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
        if isinstance(resultados_list, list):
            for r in resultados_list:
                animal_str = str(r.get('animal', ''))
                resultados_dict[r['hora']] = {
                    'animal': animal_str,
                    'nombre': ANIMALES.get(animal_str, 'Desconocido')
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
            },
            'filtros_aplicados': {
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'estado': estado
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def calcular_premio_ticket(ticket):
    try:
        fecha_ticket = parse_fecha_ticket(ticket['fecha']).strftime("%d/%m/%Y")
        resultados_list = supabase_request("resultados", filters={"fecha": fecha_ticket})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if isinstance(resultados_list, list) else {}
        
        total_premio = 0
        
        jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
        if isinstance(jugadas, list):
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
        if isinstance(tripletas, list):
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
        resultados = {r['hora']: r['animal'] for r in resultados_list} if isinstance(resultados_list, list) else {}
        
        jugadas_detalle = []
        total_premio = 0
        
        if isinstance(jugadas, list):
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
        if isinstance(tripletas, list):
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
            if isinstance(jugadas, list):
                for j in jugadas:
                    if not verificar_horario_bloqueo(j['hora']):
                        return jsonify({'error': f'No se puede anular, el sorteo {j["hora"]} ya cerró'})
        else:
            jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
            if isinstance(jugadas, list):
                for j in jugadas:
                    if not verificar_horario_bloqueo(j['hora']):
                        return jsonify({'error': f'No se puede anular, el sorteo {j["hora"]} ya está cerrado'})
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

@app.route('/api/caja-historico', methods=['POST'])
@agencia_required
def caja_historico():
    try:
        data = request.get_json()
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fechas requeridas'}), 400
        dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
        agencias = supabase_request("agencias", filters={"id": session['user_id']})
        comision_pct = agencias[0]['comision'] if agencias else COMISION_AGENCIA
        url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{session['user_id']}&order=fecha.desc&limit=5000"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            all_tickets = json.loads(response.read().decode())
        dias_data = {}
        tickets_pendientes_cobro = []
        total_ventas = total_premios = 0
        for t in all_tickets:
            if t.get('anulado'):
                continue
            dt_ticket = parse_fecha_ticket(t['fecha'])
            if not dt_ticket or dt_ticket < dt_inicio or dt_ticket > dt_fin:
                continue
            dia_key = dt_ticket.strftime("%d/%m/%Y")
            if dia_key not in dias_data:
                dias_data[dia_key] = {'ventas': 0, 'tickets': 0, 'premios': 0, 'pendientes': 0}
            dias_data[dia_key]['ventas'] += t['total']
            dias_data[dia_key]['tickets'] += 1
            total_ventas += t['total']
            premio_ticket = calcular_premio_ticket(t)
            if t['pagado']:
                dias_data[dia_key]['premios'] += premio_ticket
                total_premios += premio_ticket
            elif premio_ticket > 0:
                dias_data[dia_key]['pendientes'] += 1
                tickets_pendientes_cobro.append({
                    'serial': t['serial'],
                    'fecha': t['fecha'],
                    'monto': t['total'],
                    'premio': round(premio_ticket, 2)
                })
        resumen_dias = []
        for dia_key in sorted(dias_data.keys()):
            datos = dias_data[dia_key]
            comision_dia = datos['ventas'] * comision_pct
            balance_dia = datos['ventas'] - datos['premios'] - comision_dia
            resumen_dias.append({
                'fecha': dia_key,
                'tickets': datos['tickets'],
                'ventas': round(datos['ventas'], 2),
                'premios': round(datos['premios'], 2),
                'comision': round(comision_dia, 2),
                'balance': round(balance_dia, 2),
                'pendientes': datos['pendientes']
            })
        total_comision = total_ventas * comision_pct
        balance_total = total_ventas - total_premios - total_comision
        return jsonify({
            'resumen_por_dia': resumen_dias,
            'totales': {
                'ventas': round(total_ventas, 2),
                'premios': round(total_premios, 2),
                'comision': round(total_comision, 2),
                'balance': round(balance_total, 2),
                'tickets_pendientes_cobro': len(tickets_pendientes_cobro),
                'total_pendiente_cobro': round(sum(t['premio'] for t in tickets_pendientes_cobro), 2)
            },
            'tickets_pendientes': tickets_pendientes_cobro[:10]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/mis-tickets-pendientes')
@agencia_required
def mis_tickets_pendientes():
    try:
        url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{session['user_id']}&anulado=eq.false&pagado=eq.false"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        tickets_con_premio = []
        for t in tickets:
            premio_total = calcular_premio_ticket(t)
            if premio_total > 0:
                jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                tripletas = supabase_request("tripletas", filters={"ticket_id": t['id']})
                jugadas_count = len(jugadas) if isinstance(jugadas, list) else 0
                trip_count = len(tripletas) if isinstance(tripletas, list) else 0
                tickets_con_premio.append({
                    'serial': t['serial'],
                    'fecha': t['fecha'],
                    'total': t['total'],
                    'premio': round(premio_total, 2),
                    'jugadas': jugadas_count + trip_count
                })
        return jsonify({
            'status': 'ok',
            'tickets': tickets_con_premio,
            'total_pendiente': sum(t['premio'] for t in tickets_con_premio)
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
        hoy = ahora_peru().strftime("%d/%m/%Y")
        if fecha == hoy:
            if not puede_editar_resultado(hora, fecha):
                return jsonify({'error': 'No se puede editar.'}), 403
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
                            'accion': 'actualizado',
                            'fecha': fecha,
                            'hora': hora,
                            'animal': animal
                        })
                    else:
                        return jsonify({'error': 'Error al actualizar'}), 500
            except urllib.error.HTTPError as e:
                print(f"[ERROR PATCH] HTTP {e.code}: {e.read().decode()}")
                return jsonify({'error': f'Error al actualizar: HTTP {e.code}'}), 500
        else:
            data = {"fecha": fecha, "hora": hora, "animal": animal}
            result = supabase_request("resultados", method="POST", data=data)
            if result:
                return jsonify({
                    'status': 'ok',
                    'mensaje': f'RESULTADO GUARDADO: {hora} = {animal} ({ANIMALES[animal]})',
                    'accion': 'creado',
                    'fecha': fecha,
                    'hora': hora,
                    'animal': animal
                })
            else:
                return jsonify({'error': 'Error al crear resultado'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/verificar-tickets-sorteo', methods=['POST'])
@admin_required
def verificar_tickets_sorteo():
    try:
        data = request.get_json()
        fecha = data.get('fecha')
        hora = data.get('hora')
        if not fecha or not hora:
            return jsonify({'error': 'Fecha y hora requeridas'}), 400
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(fecha)}%25&anulado=eq.false"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        tickets_con_jugadas = []
        total_apostado = 0
        for t in tickets:
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id'], "hora": hora})
            if isinstance(jugadas, list) and len(jugadas) > 0:
                monto_jugadas = sum(j['monto'] for j in jugadas)
                tickets_con_jugadas.append({
                    'serial': t['serial'],
                    'agencia_id': t['agencia_id'],
                    'monto': monto_jugadas
                })
                total_apostado += monto_jugadas
        return jsonify({
            'status': 'ok',
            'tickets_count': len(tickets_con_jugadas),
            'total_apostado': round(total_apostado, 2),
            'tickets': tickets_con_jugadas[:5]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== CAMBIO 4: admin_resultados_hoy con isinstance ====================
@app.route('/admin/resultados-hoy')
@admin_required
def admin_resultados_hoy():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        resultados_list = supabase_request("resultados", filters={"fecha": hoy})
        
        resultados_dict = {}
        if isinstance(resultados_list, list):
            for r in resultados_list:
                animal_str = str(r.get('animal', ''))
                resultados_dict[r['hora']] = {
                    'animal': animal_str,
                    'nombre': ANIMALES.get(animal_str, 'Desconocido')
                }
        
        for hora in HORARIOS_PERU:
            if hora not in resultados_dict:
                resultados_dict[hora] = None
                
        return jsonify({'status': 'ok', 'fecha': hoy, 'resultados': resultados_dict})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/tripletas-hoy')
@admin_required
def tripletas_hoy():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        url = f"{SUPABASE_URL}/rest/v1/tripletas?fecha=eq.{urllib.parse.quote(hoy)}"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tripletas = json.loads(response.read().decode())
        if not tripletas:
            return jsonify({'tripletas': [], 'total': 0, 'ganadoras': 0, 'total_premios': 0})
        resultados_list = supabase_request("resultados", filters={"fecha": hoy})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if isinstance(resultados_list, list) else {}
        tripletas_procesadas = []
        ganadoras = 0
        for trip in tripletas:
            tickets = supabase_request("tickets", filters={"id": trip['ticket_id']})
            if not tickets:
                continue
            ticket = tickets[0]
            agencias = supabase_request("agencias", filters={"id": ticket['agencia_id']})
            nombre_agencia = agencias[0]['nombre_agencia'] if isinstance(agencias, list) and agencias else 'Desconocida'
            nums = [trip['animal1'], trip['animal2'], trip['animal3']]
            nums_encontrados = []
            for hora, animal in resultados.items():
                if animal in nums and animal not in nums_encontrados:
                    nums_encontrados.append(animal)
            gano = len(nums_encontrados) == 3
            if gano:
                ganadoras += 1
            nombres_animales = [ANIMALES.get(n, n) for n in nums]
            tripletas_procesadas.append({
                'id': trip['id'],
                'serial': ticket['serial'],
                'agencia': nombre_agencia,
                'animal1': trip['animal1'],
                'animal2': trip['animal2'],
                'animal3': trip['animal3'],
                'nombres': nombres_animales,
                'monto': trip['monto'],
                'premio': trip['monto'] * PAGO_TRIPLETA if gano else 0,
                'gano': gano,
                'salieron': nums_encontrados,
                'pagado': trip.get('pagado', False)
            })
        return jsonify({
            'tripletas': tripletas_procesadas,
            'total': len(tripletas_procesadas),
            'ganadoras': ganadoras,
            'total_premios': sum(t['premio'] for t in tripletas_procesadas)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/reporte-agencias-rango', methods=['POST'])
@admin_required
def reporte_agencias_rango():
    try:
        data = request.get_json()
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        agencia_id = data.get('agencia_id')
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fechas requeridas'}), 400
        dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
        if agencia_id:
            url = f"{SUPABASE_URL}/rest/v1/agencias?id=eq.{agencia_id}"
        else:
            url = f"{SUPABASE_URL}/rest/v1/agencias?es_admin=eq.false"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            agencias = json.loads(response.read().decode())
        dict_agencias = {a['id']: a for a in agencias}
        if agencia_id:
            url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{agencia_id}&order=fecha.desc&limit=50000"
        else:
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
        resultados_por_dia = {}
        delta = dt_fin - dt_inicio
        for i in range(delta.days + 1):
            dia_str = (dt_inicio + timedelta(days=i)).strftime("%d/%m/%Y")
            resultados_list = supabase_request("resultados", filters={"fecha": dia_str})
            if isinstance(resultados_list, list):
                resultados_por_dia[dia_str] = {r['hora']: r['animal'] for r in resultados_list}
        stats_por_agencia = {}
        for ag in agencias:
            stats_por_agencia[ag['id']] = {
                'id': ag['id'],
                'nombre': ag['nombre_agencia'],
                'usuario': ag['usuario'],
                'comision_pct': ag['comision'],
                'tickets': 0, 'ventas': 0, 'premios_pagados': 0,
                'premios_pendientes': 0, 'premios_teoricos': 0,
                'comision': 0, 'balance': 0,
                'tickets_pagados_count': 0, 'tickets_pendientes_count': 0
            }
        for t in tickets_validos:
            ag_id = t['agencia_id']
            if ag_id not in stats_por_agencia:
                continue
            stats = stats_por_agencia[ag_id]
            stats['tickets'] += 1
            stats['ventas'] += t['total']
            fecha_ticket = parse_fecha_ticket(t['fecha']).strftime("%d/%m/%Y")
            resultados_dia = resultados_por_dia.get(fecha_ticket, {})
            premio_teorico_ticket = 0
            tiene_premio = False
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
            if isinstance(jugadas, list):
                for j in jugadas:
                    wa = resultados_dia.get(j['hora'])
                    if wa:
                        if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                            premio_teorico_ticket += calcular_premio_animal(j['monto'], wa)
                            tiene_premio = True
                        elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                            sel = j['seleccion']
                            num = int(wa)
                            if (sel == 'ROJO' and str(wa) in ROJOS) or \
                               (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                               (sel == 'PAR' and num % 2 == 0) or \
                               (sel == 'IMPAR' and num % 2 != 0):
                                premio_teorico_ticket += j['monto'] * PAGO_ESPECIAL
                                tiene_premio = True
            tripletas = supabase_request("tripletas", filters={"ticket_id": t['id']})
            if isinstance(tripletas, list):
                for trip in tripletas:
                    nums = [trip['animal1'], trip['animal2'], trip['animal3']]
                    nums_encontrados = []
                    for hora, animal in resultados_dia.items():
                        if animal in nums and animal not in nums_encontrados:
                            nums_encontrados.append(animal)
                    if len(nums_encontrados) == 3:
                        premio_teorico_ticket += trip['monto'] * PAGO_TRIPLETA
                        tiene_premio = True
            stats['premios_teoricos'] += premio_teorico_ticket
            if t['pagado']:
                stats['tickets_pagados_count'] += 1
                stats['premios_pagados'] += premio_teorico_ticket
            else:
                if tiene_premio:
                    stats['tickets_pendientes_count'] += 1
                    stats['premios_pendientes'] += premio_teorico_ticket
        total_global = {
            'tickets': 0, 'ventas': 0, 'premios_pagados': 0, 'premios_pendientes': 0,
            'premios_teoricos': 0, 'comision': 0, 'balance': 0,
            'tickets_pagados_count': 0, 'tickets_pendientes_count': 0
        }
        reporte_agencias = []
        for ag_id, stats in stats_por_agencia.items():
            if stats['tickets'] > 0:
                stats['comision'] = stats['ventas'] * stats['comision_pct']
                stats['balance'] = stats['ventas'] - stats['premios_teoricos'] - stats['comision']
                for key in ['ventas', 'premios_pagados', 'premios_pendientes', 'premios_teoricos', 'comision', 'balance']:
                    stats[key] = round(stats[key], 2)
                reporte_agencias.append(stats)
                for key in total_global:
                    if key in stats:
                        total_global[key] += stats[key]
        if total_global['ventas'] > 0:
            for ag in reporte_agencias:
                ag['porcentaje_ventas'] = round((ag['ventas'] / total_global['ventas']) * 100, 1)
        reporte_agencias.sort(key=lambda x: x['ventas'], reverse=True)
        for key in total_global:
            total_global[key] = round(total_global[key], 2)
        return jsonify({
            'status': 'ok',
            'agencias': reporte_agencias,
            'totales': total_global,
            'rango': {'inicio': fecha_inicio, 'fin': fecha_fin, 'dias': (dt_fin - dt_inicio).days + 1},
            'filtro_agencia': agencia_id
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/exportar-csv', methods=['POST'])
@admin_required
def exportar_csv():
    try:
        data = request.get_json()
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
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
        resultados_por_dia = {}
        delta = dt_fin - dt_inicio
        for i in range(delta.days + 1):
            dia_str = (dt_inicio + timedelta(days=i)).strftime("%d/%m/%Y")
            resultados_list = supabase_request("resultados", filters={"fecha": dia_str})
            if isinstance(resultados_list, list):
                resultados_por_dia[dia_str] = {r['hora']: r['animal'] for r in resultados_list}
        stats_por_agencia = {}
        for ag in agencias:
            stats_por_agencia[ag['id']] = {'nombre': ag['nombre_agencia'], 'usuario': ag['usuario'], 'tickets': 0, 'ventas': 0, 'premios': 0}
        for t in tickets_validos:
            ag_id = t['agencia_id']
            if ag_id not in stats_por_agencia:
                continue
            stats = stats_por_agencia[ag_id]
            stats['tickets'] += 1
            stats['ventas'] += t['total']
            fecha_ticket = parse_fecha_ticket(t['fecha']).strftime("%d/%m/%Y")
            resultados_dia = resultados_por_dia.get(fecha_ticket, {})
            if t['pagado']:
                jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                if isinstance(jugadas, list):
                    for j in jugadas:
                        wa = resultados_dia.get(j['hora'])
                        if wa:
                            if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                                stats['premios'] += calcular_premio_animal(j['monto'], wa)
                            elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                                num = int(wa)
                                sel = j['seleccion']
                                if (sel == 'ROJO' and str(wa) in ROJOS) or \
                                   (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                                   (sel == 'PAR' and num % 2 == 0) or \
                                   (sel == 'IMPAR' and num % 2 != 0):
                                    stats['premios'] += j['monto'] * PAGO_ESPECIAL
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['REPORTE ZOOLO CASINO - AGENCIAS'])
        writer.writerow([f'Periodo: {fecha_inicio} al {fecha_fin}'])
        writer.writerow([])
        writer.writerow(['Agencia', 'Usuario', 'Tickets', 'Ventas (S/)', 'Premios (S/)', 'Comisión (S/)', 'Balance (S/)', '% Participación'])
        total_ventas = sum(s['ventas'] for s in stats_por_agencia.values())
        for ag_id, stats in sorted(stats_por_agencia.items(), key=lambda x: x[1]['ventas'], reverse=True):
            if stats['tickets'] > 0:
                comision = stats['ventas'] * dict_agencias[ag_id]['comision']
                balance = stats['ventas'] - stats['premios'] - comision
                porcentaje = (stats['ventas'] / total_ventas * 100) if total_ventas > 0 else 0
                writer.writerow([stats['nombre'], stats['usuario'], stats['tickets'],
                    round(stats['ventas'], 2), round(stats['premios'], 2),
                    round(comision, 2), round(balance, 2), f"{porcentaje:.1f}%"])
        writer.writerow([])
        total_comision = sum(s['ventas'] * dict_agencias[ag_id]['comision'] for ag_id, s in stats_por_agencia.items())
        total_balance = sum(s['ventas'] for s in stats_por_agencia.values()) - sum(s['premios'] for s in stats_por_agencia.values()) - total_comision
        writer.writerow(['TOTALES', '',
            sum(s['tickets'] for s in stats_por_agencia.values()),
            round(total_ventas, 2), round(sum(s['premios'] for s in stats_por_agencia.values()), 2),
            round(total_comision, 2), round(total_balance, 2), '100%'])
        output.seek(0)
        return Response(output.getvalue(), mimetype='text/csv',
            headers={'Content-Type': 'text/csv; charset=utf-8',
                'Content-Disposition': f'attachment; filename=reporte_agencias_{fecha_inicio}_{fecha_fin}.csv'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/reporte-agencias')
@admin_required
def reporte_agencias():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        url = f"{SUPABASE_URL}/rest/v1/agencias?es_admin=eq.false"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            agencias = json.loads(response.read().decode())
        resultados_list = supabase_request("resultados", filters={"fecha": hoy})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if isinstance(resultados_list, list) else {}
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(hoy)}%25"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        data_agencias = []
        total_ventas = total_premios = total_comisiones = 0
        for ag in agencias:
            ventas = sum(t['total'] for t in tickets if t['agencia_id'] == ag['id'] and not t['anulado'])
            comision = ventas * ag['comision']
            premios_pagados = 0
            premios_pendientes = 0
            for t in tickets:
                if t['agencia_id'] == ag['id'] and not t['anulado']:
                    premio_ticket = calcular_premio_ticket(t)
                    if t['pagado']:
                        premios_pagados += premio_ticket
                    else:
                        premios_pendientes += premio_ticket
            balance = ventas - premios_pagados - comision
            data_agencias.append({
                'nombre': ag['nombre_agencia'],
                'ventas': round(ventas, 2),
                'premios_pagados': round(premios_pagados, 2),
                'premios_pendientes': round(premios_pendientes, 2),
                'premios_total': round(premios_pagados + premios_pendientes, 2),
                'comision': round(comision, 2),
                'balance': round(balance, 2)
            })
            total_ventas += ventas
            total_premios += premios_pagados
            total_comisiones += comision
        return jsonify({
            'agencias': data_agencias,
            'global': {
                'ventas': round(total_ventas, 2),
                'pagos': round(total_premios, 2),
                'premios_pendientes': round(sum(a['premios_pendientes'] for a in data_agencias), 2),
                'comisiones': round(total_comisiones, 2),
                'balance': round(total_ventas - total_premios - total_comisiones, 2)
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/riesgo')
@admin_required
def riesgo():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        sorteo_objetivo = obtener_sorteo_en_curso() or obtener_proximo_sorteo()
        agencia_id = request.args.get('agencia_id')
        nombre_agencia = "TODAS LAS AGENCIAS"
        if not sorteo_objetivo:
            return jsonify({'riesgo': {}, 'sorteo_objetivo': None, 'mensaje': 'No hay más sorteos disponibles para hoy', 'agencia_nombre': nombre_agencia})
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(hoy)}%25&anulado=eq.false"
        if agencia_id:
            url += f"&agencia_id=eq.{urllib.parse.quote(str(agencia_id))}"
            agencias = supabase_request("agencias", filters={"id": agencia_id})
            if isinstance(agencias, list) and len(agencias) > 0:
                nombre_agencia = agencias[0]['nombre_agencia']
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        if not tickets:
            return jsonify({'riesgo': {}, 'sorteo_objetivo': sorteo_objetivo, 'mensaje': 'No hay tickets vendidos hoy', 'total_apostado': 0, 'agencia_nombre': nombre_agencia, 'agencia_id': agencia_id})
        apuestas = {}
        total_apostado_sorteo = 0
        total_jugadas_contadas = 0
        for t in tickets:
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id'], "tipo": "animal"})
            if isinstance(jugadas, list):
                for j in jugadas:
                    if j.get('hora') == sorteo_objetivo:
                        sel = j.get('seleccion')
                        monto = j.get('monto', 0)
                        if sel:
                            if sel not in apuestas:
                                apuestas[sel] = 0
                            apuestas[sel] += monto
                            total_apostado_sorteo += monto
                            total_jugadas_contadas += 1
        apuestas_ordenadas = sorted(apuestas.items(), key=lambda x: x[1], reverse=True)
        riesgo_data = {}
        for sel, monto in apuestas_ordenadas:
            nombre = ANIMALES.get(sel, sel)
            multiplicador = PAGO_LECHUZA if sel == "40" else PAGO_ANIMAL_NORMAL
            riesgo_data[f"{sel} - {nombre}"] = {
                "apostado": round(monto, 2),
                "pagaria": round(monto * multiplicador, 2),
                "es_lechuza": sel == "40",
                "porcentaje": round((monto / total_apostado_sorteo) * 100, 1) if total_apostado_sorteo > 0 else 0
            }
        return jsonify({
            'riesgo': riesgo_data,
            'sorteo_objetivo': sorteo_objetivo,
            'total_apostado': round(total_apostado_sorteo, 2),
            'hora_actual': ahora_peru().strftime("%I:%M %p"),
            'cantidad_jugadas': total_jugadas_contadas,
            'agencia_nombre': nombre_agencia,
            'agencia_id': agencia_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/estadisticas-rango', methods=['POST'])
@admin_required
def estadisticas_rango():
    try:
        data = request.get_json()
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fechas requeridas'}), 400
        dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=1000"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            all_tickets = json.loads(response.read().decode())
        dias_data = {}
        tickets_rango = []
        for t in all_tickets:
            if t.get('anulado'):
                continue
            dt_ticket = parse_fecha_ticket(t['fecha'])
            if not dt_ticket or dt_ticket < dt_inicio or dt_ticket > dt_fin:
                continue
            tickets_rango.append(t)
            dia_key = dt_ticket.strftime("%d/%m/%Y")
            if dia_key not in dias_data:
                dias_data[dia_key] = {'ventas': 0, 'tickets': 0, 'premios': 0, 'comisiones': 0, 'ids_tickets': []}
            dias_data[dia_key]['ventas'] += t['total']
            dias_data[dia_key]['tickets'] += 1
            dias_data[dia_key]['ids_tickets'].append(t['id'])
        resumen_dias = []
        total_ventas = total_premios = total_tickets = 0
        for dia_key in sorted(dias_data.keys()):
            datos = dias_data[dia_key]
            premios_dia = 0
            for ticket_id in datos['ids_tickets'][:50]:
                t = next((tk for tk in tickets_rango if tk['id'] == ticket_id), None)
                if t:
                    premios_dia += calcular_premio_ticket(t)
            comision_dia = datos['ventas'] * COMISION_AGENCIA
            balance_dia = datos['ventas'] - premios_dia - comision_dia
            resumen_dias.append({
                'fecha': dia_key,
                'ventas': round(datos['ventas'], 2),
                'premios': round(premios_dia, 2),
                'comisiones': round(comision_dia, 2),
                'balance': round(balance_dia, 2),
                'tickets': datos['tickets']
            })
            total_ventas += datos['ventas']
            total_premios += premios_dia
            total_tickets += datos['tickets']
        return jsonify({
            'resumen_por_dia': resumen_dias,
            'totales': {
                'ventas': round(total_ventas, 2),
                'premios': round(total_premios, 2),
                'comisiones': round(total_ventas * COMISION_AGENCIA, 2),
                'balance': round(total_ventas - total_premios - (total_ventas * COMISION_AGENCIA), 2),
                'tickets': total_tickets
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/top-animales-rango', methods=['POST'])
@admin_required
def top_animales_rango():
    try:
        data = request.get_json()
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fechas requeridas'}), 400
        dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=5000"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            all_tickets = json.loads(response.read().decode())
        ticket_ids = []
        for t in all_tickets:
            if t.get('anulado'):
                continue
            dt_ticket = parse_fecha_ticket(t['fecha'])
            if dt_ticket and dt_inicio <= dt_ticket <= dt_fin:
                ticket_ids.append(t['id'])
        if not ticket_ids:
            return jsonify({'top_animales': []})
        apuestas = {}
        for ticket_id in ticket_ids[:100]:
            jugadas = supabase_request("jugadas", filters={"ticket_id": ticket_id, "tipo": "animal"})
            if isinstance(jugadas, list):
                for j in jugadas:
                    sel = j['seleccion']
                    if sel not in apuestas:
                        apuestas[sel] = {'monto': 0, 'cantidad': 0}
                    apuestas[sel]['monto'] += j['monto']
                    apuestas[sel]['cantidad'] += 1
        top = sorted(apuestas.items(), key=lambda x: x[1]['monto'], reverse=True)
        resultado = []
        for sel, data in top[:20]:
            nombre = ANIMALES.get(sel, sel)
            resultado.append({
                'numero': sel,
                'nombre': nombre,
                'total_apostado': round(data['monto'], 2),
                'cantidad_jugadas': data['cantidad'],
                'pago_potencial': round(data['monto'] * (PAGO_LECHUZA if sel == "40" else PAGO_ANIMAL_NORMAL), 2)
            })
        return jsonify({'top_animales': resultado})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== TEMPLATES HTML ====================
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
        .form-group input:focus { outline: none; border-color: #ffd700; box-shadow: 0 0 10px rgba(255,215,0,0.3); }
        .btn-login {
            width: 100%; padding: 16px;
            background: linear-gradient(45deg, #ffd700, #ffed4e);
            color: black; border: none; border-radius: 10px;
            font-size: 1.1rem; font-weight: bold; cursor: pointer;
            margin-top: 10px; transition: transform 0.2s;
        }
        .btn-login:active { transform: scale(0.98); }
        .error { background: rgba(255,0,0,0.2); color: #ff6b6b; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 0.9rem; }
        .info { margin-top: 25px; font-size: 0.8rem; color: #666; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🦁 ZOOLO CASINO</h2>
        {% if error %}<div class="error">{{error}}</div>{% endif %}
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
        <div class="info">Sistema ZOOLO CASINO v6.1<br>Tripleta x60 + Nuevos Horarios Perú</div>
    </div>
</body>
</html>
'''

POS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
    <title>POS - {{agencia}}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        html { height: 100%; }
        body { background: #0a0a0a; color: white; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-height: 100vh; display: flex; flex-direction: column; overflow-x: hidden; }
        .header { background: linear-gradient(90deg, #1a1a2e, #16213e); padding: 10px 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #ffd700; flex-shrink: 0; }
        .header-info h3 { color: #ffd700; font-size: 1rem; margin: 0; }
        .header-info p { color: #888; font-size: 0.75rem; margin: 0; }
        .monto-box { display: flex; align-items: center; gap: 8px; background: rgba(0,0,0,0.3); padding: 6px 12px; border-radius: 20px; }
        .monto-box span { font-size: 0.8rem; font-weight: bold; color: #ffd700; }
        .monto-box input { width: 60px; padding: 6px; border: 2px solid #ffd700; border-radius: 6px; background: #000; color: #ffd700; text-align: center; font-weight: bold; font-size: 1rem; }
        .main-container { display: flex; flex-direction: column; flex: 1; height: calc(100vh - 110px); overflow: hidden; }
        @media (min-width: 1024px) { .main-container { flex-direction: row; } }
        .left-panel { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
        .special-btns { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; padding: 10px; background: #111; flex-shrink: 0; }
        .btn-esp { padding: 12px 4px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; color: white; font-size: 0.8rem; touch-action: manipulation; min-height: 44px; transition: all 0.1s; }
        .btn-esp:active { transform: scale(0.95); }
        .btn-rojo { background: linear-gradient(135deg, #c0392b, #e74c3c); }
        .btn-negro { background: linear-gradient(135deg, #2c3e50, #34495e); border: 1px solid #555; }
        .btn-par { background: linear-gradient(135deg, #2980b9, #3498db); }
        .btn-impar { background: linear-gradient(135deg, #8e44ad, #9b59b6); }
        .btn-esp.active { box-shadow: 0 0 15px rgba(255,255,255,0.5); transform: scale(0.95); border: 2px solid white; }
        .animals-grid { flex: 1; display: grid; grid-template-columns: repeat(auto-fill, minmax(60px, 1fr)); gap: 5px; padding: 10px; overflow-y: auto; }
        @media (min-width: 768px) { .animals-grid { grid-template-columns: repeat(7, 1fr); } }
        .animal-card { background: linear-gradient(135deg, #1a1a2e, #16213e); border: 2px solid; border-radius: 10px; padding: 8px 2px; text-align: center; cursor: pointer; transition: all 0.15s; min-height: 65px; display: flex; flex-direction: column; justify-content: center; user-select: none; position: relative; touch-action: manipulation; }
        .animal-card:active { transform: scale(0.92); }
        .animal-card.active { box-shadow: 0 0 15px rgba(255,215,0,0.6); border-color: #ffd700 !important; background: linear-gradient(135deg, #2a2a4e, #1a1a3e); transform: scale(1.05); z-index: 10; }
        .animal-card.tripleta-seleccionado { box-shadow: 0 0 15px rgba(255,215,0,0.9); border-color: #ffd700 !important; background: linear-gradient(135deg, #4a3c00, #2a2000); transform: scale(1.08); z-index: 15; }
        .animal-card .num { font-size: 1.2rem; font-weight: bold; line-height: 1; }
        .animal-card .name { font-size: 0.7rem; color: #aaa; line-height: 1; margin-top: 4px; font-weight: 500; }
        .animal-card.lechuza::after { content: "x70"; position: absolute; top: 3px; right: 3px; background: #ffd700; color: black; font-size: 0.6rem; padding: 2px 4px; border-radius: 4px; font-weight: bold; }
        .right-panel { background: #111; border-top: 2px solid #333; display: flex; flex-direction: column; height: 40vh; flex-shrink: 0; }
        @media (min-width: 1024px) { .right-panel { width: 350px; height: auto; border-top: none; border-left: 2px solid #333; } }
        .horarios { display: flex; gap: 6px; padding: 10px; overflow-x: auto; flex-shrink: 0; background: #0a0a0a; }
        .btn-hora { flex: 0 0 auto; min-width: 85px; padding: 10px 6px; background: #222; border: 1px solid #444; border-radius: 8px; color: #ccc; cursor: pointer; font-size: 0.75rem; text-align: center; line-height: 1.3; touch-action: manipulation; transition: all 0.2s; }
        .btn-hora.active { background: linear-gradient(135deg, #27ae60, #229954); color: white; font-weight: bold; border-color: #27ae60; }
        .btn-hora.expired { background: #300; color: #666; text-decoration: line-through; pointer-events: none; opacity: 0.5; }
        .ticket-display { flex: 1; background: #000; margin: 0 10px 10px; border-radius: 10px; padding: 12px; border: 1px solid #333; overflow-y: auto; font-size: 0.85rem; }
        .ticket-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
        .ticket-table th { background: #1a1a2e; color: #ffd700; padding: 8px 6px; text-align: left; position: sticky; top: 0; font-size: 0.75rem; }
        .ticket-table td { padding: 8px 6px; border-bottom: 1px solid #222; vertical-align: middle; }
        .ticket-total { margin-top: 12px; padding-top: 12px; border-top: 2px solid #ffd700; text-align: right; font-size: 1.2rem; font-weight: bold; color: #ffd700; }
        .action-btns { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; padding: 10px; background: #0a0a0a; flex-shrink: 0; }
        .action-btns button { padding: 14px 5px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 0.8rem; touch-action: manipulation; min-height: 48px; transition: all 0.1s; }
        .action-btns button:active { transform: scale(0.95); }
        .btn-agregar { background: linear-gradient(135deg, #27ae60, #229954); color: white; grid-column: span 3; font-size: 1.1rem; }
        .btn-vender { background: linear-gradient(135deg, #2980b9, #2573a7); color: white; grid-column: span 3; font-size: 1rem; }
        .btn-resultados { background: #f39c12; color: black; }
        .btn-caja { background: #16a085; color: white; }
        .btn-pagar { background: #8e44ad; color: white; }
        .btn-tripleta { background: linear-gradient(135deg, #FFD700, #FFA500); color: black; font-weight: bold; border: 2px solid #FFD700; }
        .btn-tripleta.active { background: linear-gradient(135deg, #FFA500, #FF8C00); }
        .btn-anular { background: #c0392b; color: white; }
        .btn-borrar { background: #555; color: white; }
        .btn-salir { background: #333; color: white; grid-column: span 3; }
        .tripleta-info { background: linear-gradient(135deg, rgba(255,215,0,0.2), rgba(255,165,0,0.1)); border: 2px solid #FFD700; border-radius: 8px; padding: 10px; margin: 0 10px 10px; text-align: center; color: #FFD700; font-weight: bold; display: none; }
        .tripleta-info.active { display: block; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 1000; overflow-y: auto; }
        .modal-content { background: #1a1a2e; margin: 10px; padding: 20px; border-radius: 15px; border: 2px solid #ffd700; max-width: 100%; min-height: calc(100vh - 20px); }
        @media (min-width: 768px) { .modal-content { margin: 40px auto; max-width: 700px; min-height: auto; } }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333; }
        .modal h3 { color: #ffd700; font-size: 1.3rem; }
        .btn-close { background: #c0392b; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .tabs { display: flex; gap: 2px; margin-bottom: 20px; border-bottom: 2px solid #333; overflow-x: auto; scrollbar-width: none; }
        .tab-btn { flex: 1; background: transparent; border: none; color: #888; padding: 14px 10px; cursor: pointer; font-size: 0.85rem; border-bottom: 3px solid transparent; white-space: nowrap; min-width: 80px; }
        .tab-btn.active { color: #ffd700; border-bottom-color: #ffd700; font-weight: bold; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .stats-box { background: linear-gradient(135deg, #0a0a0a, #1a1a2e); padding: 20px; border-radius: 12px; margin: 15px 0; border: 1px solid #333; }
        .stat-row { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #222; font-size: 1rem; align-items: center; }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #aaa; }
        .stat-value { color: #ffd700; font-weight: bold; font-size: 1.2rem; }
        .stat-value.negative { color: #e74c3c; }
        .stat-value.positive { color: #27ae60; }
        .table-container { overflow-x: auto; margin: 15px 0; border-radius: 8px; border: 1px solid #333; }
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; min-width: 300px; }
        th, td { padding: 12px 8px; text-align: left; border-bottom: 1px solid #333; white-space: nowrap; }
        th { background: linear-gradient(135deg, #ffd700, #ffed4e); color: black; font-weight: bold; }
        tr:hover { background: rgba(255,215,0,0.05); }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; color: #888; font-size: 0.9rem; margin-bottom: 6px; }
        .form-group input, .form-group select { width: 100%; padding: 12px; background: #000; border: 1px solid #444; color: white; border-radius: 8px; font-size: 1rem; }
        .btn-consultar { background: linear-gradient(135deg, #27ae60, #229954); color: white; border: none; padding: 14px; width: 100%; border-radius: 8px; font-weight: bold; cursor: pointer; margin-top: 10px; font-size: 1rem; }
        .alert-box { background: rgba(243, 156, 18, 0.15); border: 1px solid #f39c12; padding: 15px; border-radius: 8px; margin: 15px 0; font-size: 0.9rem; }
        .alert-box strong { color: #f39c12; }
        .resultado-item { background: #0a0a0a; padding: 15px; margin: 8px 0; border-radius: 10px; border-left: 4px solid #27ae60; display: flex; justify-content: space-between; align-items: center; }
        .resultado-item.pendiente { border-left-color: #666; opacity: 0.7; }
        .resultado-numero { color: #ffd700; font-weight: bold; font-size: 1.4rem; }
        .resultado-nombre { color: #aaa; font-size: 1rem; }
        .toast-notification { position: fixed; top: 80px; left: 50%; transform: translateX(-50%); padding: 14px 24px; border-radius: 30px; font-size: 0.95rem; z-index: 10000; box-shadow: 0 6px 20px rgba(0,0,0,0.5); max-width: 90%; text-align: center; font-weight: bold; }
        .ticket-item { background: #0a0a0a; padding: 15px; margin: 8px 0; border-radius: 10px; border-left: 4px solid #2980b9; cursor: pointer; }
        .ticket-item.ganador { border-left-color: #27ae60; background: rgba(39,174,96,0.1); }
        .ticket-serial { color: #ffd700; font-weight: bold; font-size: 1.1rem; }
        .ticket-info { color: #888; font-size: 0.85rem; margin-top: 5px; }
        .ticket-premio { color: #27ae60; font-weight: bold; font-size: 1.2rem; margin-top: 5px; }
        .ticket-estado { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-top: 5px; }
        .estado-pagado { background: #27ae60; color: white; }
        .estado-pendiente { background: #f39c12; color: black; }
        .filter-row { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        .filter-row select, .filter-row input { flex: 1; min-width: 120px; padding: 10px; background: #000; border: 1px solid #444; color: white; border-radius: 6px; }
        .jugada-detail { background: #111; padding: 8px; margin: 4px 0; border-radius: 6px; font-size: 0.85rem; display: flex; justify-content: space-between; align-items: center; }
        .jugada-ganadora { background: rgba(39,174,96,0.2); border: 1px solid #27ae60; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-info">
            <h3>🦁 {{agencia}}</h3>
            <p id="reloj">--</p>
        </div>
        <div class="monto-box">
            <span>S/:</span>
            <input type="number" id="monto" value="5" min="1">
        </div>
    </div>
    
    <div class="tripleta-info" id="tripleta-banner">
        🎯 MODO TRIPLETA: Selecciona 3 animalitos (Paga x60 si salen hoy)
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
                <div class="animal-card {{ 'lechuza' if k == '40' else '' }}" id="ani-{{k}}" style="border-color: {{get_color(k)}}" onclick="toggleAni('{{k}}', '{{v}}')">
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
                <div style="text-align:center; color:#666; padding:20px; font-style:italic;">Selecciona animales y horarios...</div>
            </div>
            <div class="action-btns">
                <button class="btn-agregar" onclick="agregar()">AGREGAR AL TICKET</button>
                <button class="btn-vender" onclick="vender()">ENVIAR POR WHATSAPP</button>
                <button class="btn-resultados" onclick="verResultados()">RESULTADOS</button>
                <button class="btn-caja" onclick="abrirCaja()">CAJA</button>
                <button class="btn-pagar" onclick="pagar()">PAGAR</button>
                <button class="btn-tripleta" id="btn-tripleta" onclick="toggleModoTripleta()">🎯 TRIPLETA</button>
                <button class="btn-anular" onclick="anular()">ANULAR</button>
                <button class="btn-borrar" onclick="borrarTodo()">BORRAR TODO</button>
                <button class="btn-salir" onclick="location.href='/logout'">CERRAR SESIÓN</button>
            </div>
        </div>
    </div>

    <div class="modal" id="modal-caja">
        <div class="modal-content">
            <div class="modal-header">
                <h3>ESTADO DE CAJA</h3>
                <button class="btn-close" onclick="cerrarModal('modal-caja')">X</button>
            </div>
            <div class="tabs">
                <button class="tab-btn active" onclick="switchTab(event,'hoy')">Hoy</button>
                <button class="tab-btn" onclick="switchTab(event,'historico')">Histórico</button>
            </div>
            <div id="tab-hoy" class="tab-content active">
                <div class="stats-box">
                    <div class="stat-row"><span class="stat-label">Ventas:</span><span class="stat-value" id="caja-ventas">S/0.00</span></div>
                    <div class="stat-row"><span class="stat-label">Premios Pagados:</span><span class="stat-value negative" id="caja-premios">S/0.00</span></div>
                    <div class="stat-row"><span class="stat-label">Tu Comisión:</span><span class="stat-value" id="caja-comision">S/0.00</span></div>
                    <div class="stat-row"><span class="stat-label">Balance:</span><span class="stat-value" id="caja-balance">S/0.00</span></div>
                </div>
                <div id="alerta-pendientes" class="alert-box" style="display:none;"><strong>⚠️ Tickets por Cobrar:</strong><div id="info-pendientes"></div></div>
            </div>
            <div id="tab-historico" class="tab-content">
                <div class="form-group"><label>Desde:</label><input type="date" id="hist-fecha-inicio"></div>
                <div class="form-group"><label>Hasta:</label><input type="date" id="hist-fecha-fin"></div>
                <button class="btn-consultar" onclick="consultarHistoricoCaja()">CONSULTAR HISTORIAL</button>
                <div id="resultado-historico" style="display:none; margin-top: 20px;">
                    <div class="stats-box">
                        <div class="stat-row"><span class="stat-label">Total Ventas:</span><span class="stat-value" id="hist-ventas">S/0.00</span></div>
                        <div class="stat-row"><span class="stat-label">Total Premios:</span><span class="stat-value negative" id="hist-premios">S/0.00</span></div>
                        <div class="stat-row"><span class="stat-label">Balance:</span><span class="stat-value" id="hist-balance">S/0.00</span></div>
                    </div>
                    <div class="table-container" style="max-height: 250px; overflow-y: auto; margin-top: 15px;">
                        <table><thead><tr><th>Fecha</th><th>Tickets</th><th>Ventas</th><th>Balance</th></tr></thead><tbody id="tabla-historico-caja"></tbody></table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="modal" id="modal-resultados">
        <div class="modal-content">
            <div class="modal-header">
                <h3>RESULTADOS DE SORTEOS</h3>
                <button class="btn-close" onclick="cerrarModal('modal-resultados')">X</button>
            </div>
            <div class="form-group" style="margin-bottom: 20px;">
                <label>Seleccionar Fecha:</label>
                <input type="date" id="resultados-fecha" onchange="cargarResultadosFecha()">
                <button class="btn-consultar" onclick="cargarResultadosFecha()" style="margin-top: 10px;">CONSULTAR FECHA</button>
            </div>
            <div style="margin-bottom: 15px; text-align: center; color: #ffd700; font-size: 1.1rem; font-weight: bold;" id="resultados-fecha-titulo">Hoy</div>
            <div id="lista-resultados" style="max-height: 400px; overflow-y: auto;"><p style="color: #888; text-align: center; padding: 20px;">Seleccione una fecha...</p></div>
        </div>
    </div>

    <div class="modal" id="modal-mis-tickets">
        <div class="modal-content">
            <div class="modal-header"><h3>🎫 MIS TICKETS VENDIDOS</h3><button class="btn-close" onclick="cerrarModal('modal-mis-tickets')">X</button></div>
            <div class="filter-row">
                <input type="date" id="mis-tickets-fecha-inicio">
                <input type="date" id="mis-tickets-fecha-fin">
                <select id="mis-tickets-estado"><option value="todos">Todos</option><option value="pagados">Pagados</option><option value="pendientes">Pendientes</option><option value="por_pagar">Con Premio</option></select>
            </div>
            <button class="btn-consultar" onclick="consultarMisTickets()">BUSCAR</button>
            <div id="mis-tickets-resumen" style="margin: 15px 0; padding: 10px; background: rgba(255,215,0,0.1); border-radius: 8px; display: none;"><strong style="color: #ffd700;">Resumen:</strong> <span id="mis-tickets-info"></span></div>
            <div id="lista-mis-tickets" style="max-height: 400px; overflow-y: auto; margin-top: 15px;"><p style="color: #888; text-align: center; padding: 20px;">Use los filtros y presione BUSCAR</p></div>
        </div>
    </div>

    <div class="modal" id="modal-buscar-ticket">
        <div class="modal-content">
            <div class="modal-header"><h3>🔎 BUSCAR TICKET POR SERIAL</h3><button class="btn-close" onclick="cerrarModal('modal-buscar-ticket')">X</button></div>
            <div class="form-group"><label>Ingrese el número de serial:</label><input type="text" id="buscar-serial-input" placeholder="Ej: 1234567890" style="font-size: 1.2rem; text-align: center;"></div>
            <button class="btn-consultar" onclick="buscarTicketEspecifico()">BUSCAR TICKET</button>
            <div id="resultado-busqueda-ticket" style="margin-top: 20px;"></div>
        </div>
    </div>

    <div class="modal" id="modal-calculadora">
        <div class="modal-content">
            <div class="modal-header"><h3>🧮 CALCULADORA DE PREMIOS</h3><button class="btn-close" onclick="cerrarModal('modal-calculadora')">X</button></div>
            <div class="form-group"><label>Monto Apostado (S/):</label><input type="number" id="calc-monto" value="10" min="1"></div>
            <div class="form-group"><label>Tipo de Apuesta:</label>
                <select id="calc-tipo" onchange="calcularPremio()">
                    <option value="35">Animal Normal (00-39) x35</option>
                    <option value="70">Lechuza (40) x70</option>
                    <option value="2">Especial x2</option>
                    <option value="60">TRIPLETA x60</option>
                </select>
            </div>
            <button class="btn-consultar" onclick="calcularPremio()">CALCULAR</button>
            <div class="stats-box" id="calc-resultado" style="display: none; margin-top: 20px; text-align: center;">
                <div style="color: #888; margin-bottom: 5px;">Premio a Pagar:</div>
                <div style="color: #ffd700; font-size: 2rem; font-weight: bold;" id="calc-total">S/0.00</div>
            </div>
        </div>
    </div>

    <div class="modal" id="modal-pendientes">
        <div class="modal-content">
            <div class="modal-header"><h3>💰 MIS TICKETS POR COBRAR</h3><button class="btn-close" onclick="cerrarModal('modal-pendientes')">X</button></div>
            <div id="pendientes-info" style="margin-bottom: 15px; color: #ffd700; font-weight: bold; text-align: center;">Cargando...</div>
            <div id="lista-pendientes" style="max-height: 400px; overflow-y: auto;"></div>
        </div>
    </div>

    <script>
        let seleccionados = [], especiales = [], horariosSel = [], carrito = [];
        let modoTripleta = false;
        let seleccionTripleta = [];
        let horasPeru = JSON.parse('{{ horarios_peru | tojson | safe }}');
        let horasVen = JSON.parse('{{ horarios_venezuela | tojson | safe }}');
        
        function showToast(message, type = 'info') {
            const existing = document.querySelector('.toast-notification');
            if (existing) existing.remove();
            const toast = document.createElement('div');
            toast.className = 'toast-notification';
            toast.style.background = type === 'error' ? '#c0392b' : type === 'success' ? '#27ae60' : '#2980b9';
            toast.style.color = 'white';
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
        
        function toggleModoTripleta() {
            modoTripleta = !modoTripleta;
            const btn = document.getElementById('btn-tripleta');
            const banner = document.getElementById('tripleta-banner');
            if (modoTripleta) {
                btn.classList.add('active'); banner.classList.add('active');
                seleccionTripleta = [];
                showToast('Modo Tripleta activado: Selecciona 3 animalitos (Paga x60)', 'info');
            } else {
                btn.classList.remove('active'); banner.classList.remove('active');
                seleccionTripleta = [];
                document.querySelectorAll('.animal-card.tripleta-seleccionado').forEach(el => el.classList.remove('tripleta-seleccionado'));
            }
            updateTicket();
        }
        
        function updateReloj() {
            try {
                let now = new Date();
                let peruTime = new Date(now.toLocaleString("en-US", {timeZone: "America/Lima"}));
                document.getElementById('reloj').textContent = peruTime.toLocaleString('es-PE', {hour: '2-digit', minute:'2-digit', hour12: true, timeZone: 'America/Lima'});
                let horaActual = peruTime.getHours() * 60 + peruTime.getMinutes();
                horasPeru.forEach((h, idx) => {
                    try {
                        let partes = h.split(/[: ]/);
                        let hora = parseInt(partes[0]); let minuto = parseInt(partes[1]); let ampm = partes[2];
                        if (ampm === 'PM' && hora !== 12) hora += 12;
                        if (ampm === 'AM' && hora === 12) hora = 0;
                        let sorteoMinutos = hora * 60 + minuto;
                        let btn = document.getElementById('hora-' + (idx + 1));
                        if (btn && horaActual > sorteoMinutos - 5) btn.classList.add('expired');
                    } catch(e) {}
                });
            } catch(e) {}
        }
        setInterval(updateReloj, 30000); setTimeout(updateReloj, 1000);
        
        function toggleAni(k, nombre) {
            if (modoTripleta) {
                let idx = seleccionTripleta.findIndex(a => a.k === k);
                let el = document.getElementById('ani-' + k);
                if (idx >= 0) { seleccionTripleta.splice(idx, 1); el.classList.remove('tripleta-seleccionado'); }
                else {
                    if (seleccionTripleta.length >= 3) { showToast('Solo puedes seleccionar 3 animalitos para la tripleta', 'error'); return; }
                    seleccionTripleta.push({k, nombre}); el.classList.add('tripleta-seleccionado');
                    if (navigator.vibrate) navigator.vibrate(50);
                }
            } else {
                let idx = seleccionados.findIndex(a => a.k === k);
                let el = document.getElementById('ani-' + k);
                if (idx >= 0) { seleccionados.splice(idx, 1); el.classList.remove('active'); }
                else { seleccionados.push({k, nombre}); el.classList.add('active'); if (navigator.vibrate) navigator.vibrate(50); }
            }
            updateTicket();
        }
        
        function toggleEsp(tipo) {
            if (modoTripleta) { showToast('No puedes jugar especiales en modo Tripleta', 'error'); return; }
            let idx = especiales.indexOf(tipo);
            let el = document.querySelector('.btn-' + tipo.toLowerCase());
            if (idx >= 0) { especiales.splice(idx, 1); el.classList.remove('active'); }
            else { especiales.push(tipo); el.classList.add('active'); }
            updateTicket();
        }
        
        function toggleHora(hora, id) {
            if (modoTripleta) { showToast('Las tripletas no necesitan horario', 'info'); return; }
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
                let nom = item.tipo === 'animal' ? item.nombre.substring(0,10) : item.tipo === 'tripleta' ? 'TRIP' : item.seleccion;
                let color = item.tipo === 'animal' ? '#ffd700' : item.tipo === 'tripleta' ? '#FFA500' : '#3498db';
                let horaTxt = item.tipo === 'tripleta' ? 'Todo el día' : item.hora;
                html += `<tr><td style="color:#aaa; font-size:0.75rem">${horaTxt}</td><td style="color:${color}; font-weight:bold; font-size:0.8rem">${item.seleccion} ${nom}</td><td style="text-align:right; font-weight:bold">${item.monto}</td></tr>`;
                total += item.monto;
            }
            html += '</tbody></table>';
            if (carrito.length === 0 && seleccionados.length === 0 && especiales.length === 0 && seleccionTripleta.length === 0) {
                html = '<div style="text-align:center; color:#666; padding:20px; font-style:italic;">Selecciona animales y horarios...</div>';
            }
            if (total > 0) html += `<div class="ticket-total">TOTAL: S/${total}</div>`;
            display.innerHTML = html;
        }
        
        function agregar() {
            if (modoTripleta) {
                if (seleccionTripleta.length !== 3) { showToast('Debes seleccionar exactamente 3 animalitos', 'error'); return; }
                let monto = parseFloat(document.getElementById('monto').value) || 5;
                let nums = seleccionTripleta.map(a => a.k).join(',');
                let nombres = seleccionTripleta.map(a => a.nombre).join('-');
                carrito.push({hora: 'Todo el día', seleccion: nums, nombre: nombres, monto: monto, tipo: 'tripleta'});
                seleccionTripleta = [];
                document.querySelectorAll('.animal-card.tripleta-seleccionado').forEach(el => el.classList.remove('tripleta-seleccionado'));
                showToast('Tripleta agregada al ticket (Paga x60)', 'success');
                updateTicket(); return;
            }
            if (horariosSel.length === 0 || (seleccionados.length === 0 && especiales.length === 0)) { showToast('Selecciona horario y animal/especial', 'error'); return; }
            let monto = parseFloat(document.getElementById('monto').value) || 5;
            let count = 0;
            for (let h of horariosSel) {
                for (let a of seleccionados) { carrito.push({hora: h, seleccion: a.k, nombre: a.nombre, monto: monto, tipo: 'animal'}); count++; }
                for (let e of especiales) { carrito.push({hora: h, seleccion: e, nombre: e, monto: monto, tipo: 'especial'}); count++; }
            }
            seleccionados = []; especiales = []; horariosSel = [];
            document.querySelectorAll('.animal-card.active, .btn-esp.active, .btn-hora.active').forEach(el => el.classList.remove('active'));
            updateTicket(); showToast(`${count} jugada(s) agregada(s)`, 'success');
        }
        
        async function vender() {
            if (carrito.length === 0) { showToast('Carrito vacío', 'error'); return; }
            const btn = document.querySelector('.btn-vender');
            const originalText = btn.innerHTML;
            btn.innerHTML = '⏳ Procesando...'; btn.disabled = true;
            try {
                let jugadas = carrito.map(c => ({hora: c.hora, seleccion: c.seleccion, monto: c.monto, tipo: c.tipo}));
                const response = await fetch('/api/procesar-venta', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({jugadas: jugadas})});
                const data = await response.json();
                if (data.error) { showToast(data.error, 'error'); }
                else {
                    if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) window.location.href = data.url_whatsapp;
                    else window.open(data.url_whatsapp, '_blank');
                    carrito = []; updateTicket(); showToast('¡Ticket generado! Redirigiendo a WhatsApp...', 'success');
                }
            } catch (e) { showToast('Error de conexión. Intenta de nuevo.', 'error'); }
            finally { btn.innerHTML = originalText; btn.disabled = false; }
        }

        function verResultados() {
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('resultados-fecha').value = hoy;
            cargarResultadosFecha();
            document.getElementById('modal-resultados').style.display = 'block';
        }

        function cargarResultadosFecha() {
            let fecha = document.getElementById('resultados-fecha').value;
            if (!fecha) return;
            let container = document.getElementById('lista-resultados');
            container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Cargando...</p>';
            fetch('/api/resultados-fecha', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fecha: fecha})})
            .then(r => r.json()).then(d => {
                if (d.error) { container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error: ' + d.error + '</p>'; return; }
                let html = '';
                if (d.resultados && Object.keys(d.resultados).length > 0) {
                    for (let hora of horasPeru) {
                        let resultado = d.resultados[hora];
                        let clase = resultado ? '' : 'pendiente';
                        let contenido = resultado ? `<span class="resultado-numero">${resultado.animal}</span><span class="resultado-nombre">${resultado.nombre}</span>` : `<span style="color: #666;">Pendiente</span>`;
                        html += `<div class="resultado-item ${clase}"><strong style="color: #ffd700;">${hora}</strong><div style="text-align: right;">${contenido}</div></div>`;
                    }
                } else { html = '<p style="color: #888; text-align: center; padding: 20px;">No hay resultados disponibles</p>'; }
                container.innerHTML = html;
            }).catch(e => { container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexión</p>'; });
        }

        function cerrarModal(modalId) { document.getElementById(modalId).style.display = 'none'; }
        
        function abrirCaja() {
            fetch('/api/caja').then(r => r.json()).then(d => {
                if (d.error) { showToast(d.error, 'error'); return; }
                document.getElementById('caja-ventas').textContent = 'S/' + d.ventas.toFixed(2);
                document.getElementById('caja-premios').textContent = 'S/' + d.premios.toFixed(2);
                document.getElementById('caja-comision').textContent = 'S/' + d.comision.toFixed(2);
                let balanceEl = document.getElementById('caja-balance');
                balanceEl.textContent = 'S/' + d.balance.toFixed(2);
                balanceEl.className = 'stat-value ' + (d.balance >= 0 ? 'positive' : 'negative');
                let alertaDiv = document.getElementById('alerta-pendientes');
                if (d.tickets_pendientes > 0) { alertaDiv.style.display = 'block'; document.getElementById('info-pendientes').innerHTML = `Tienes <strong>${d.tickets_pendientes}</strong> ticket(s) ganador(es) sin cobrar.`; }
                else { alertaDiv.style.display = 'none'; }
                document.getElementById('modal-caja').style.display = 'block';
            }).catch(e => showToast('Error de conexión', 'error'));
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('hist-fecha-inicio').value = hoy;
            document.getElementById('hist-fecha-fin').value = hoy;
        }
        
        function calcularPremio() {
            const monto = parseFloat(document.getElementById('calc-monto').value) || 0;
            const multiplicador = parseInt(document.getElementById('calc-tipo').value);
            document.getElementById('calc-total').textContent = 'S/' + (monto * multiplicador).toFixed(2);
            document.getElementById('calc-resultado').style.display = 'block';
        }
        
        function abrirCaja() {
            fetch('/api/caja').then(r => r.json()).then(d => {
                if (d.error) { showToast(d.error, 'error'); return; }
                document.getElementById('caja-ventas').textContent = 'S/' + d.ventas.toFixed(2);
                document.getElementById('caja-premios').textContent = 'S/' + d.premios.toFixed(2);
                document.getElementById('caja-comision').textContent = 'S/' + d.comision.toFixed(2);
                let balanceEl = document.getElementById('caja-balance');
                balanceEl.textContent = 'S/' + d.balance.toFixed(2);
                balanceEl.className = 'stat-value ' + (d.balance >= 0 ? 'positive' : 'negative');
                document.getElementById('modal-caja').style.display = 'block';
            }).catch(e => showToast('Error de conexión', 'error'));
        }
        
        function consultarHistoricoCaja() {
            let inicio = document.getElementById('hist-fecha-inicio').value;
            let fin = document.getElementById('hist-fecha-fin').value;
            if (!inicio || !fin) { showToast('Seleccione ambas fechas', 'error'); return; }
            fetch('/api/caja-historico', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})})
            .then(r => r.json()).then(d => {
                if (d.error) { showToast(d.error, 'error'); return; }
                document.getElementById('resultado-historico').style.display = 'block';
                document.getElementById('hist-ventas').textContent = 'S/' + d.totales.ventas.toFixed(2);
                document.getElementById('hist-premios').textContent = 'S/' + d.totales.premios.toFixed(2);
                let balanceEl = document.getElementById('hist-balance');
                balanceEl.textContent = 'S/' + d.totales.balance.toFixed(2);
                balanceEl.className = 'stat-value ' + (d.totales.balance >= 0 ? 'positive' : 'negative');
                let tbody = document.getElementById('tabla-historico-caja');
                let html = '';
                d.resumen_por_dia.forEach(dia => {
                    let color = dia.balance >= 0 ? '#27ae60' : '#c0392b';
                    html += `<tr><td>${dia.fecha}</td><td>${dia.tickets}</td><td>S/${dia.ventas.toFixed(0)}</td><td style="color:${color}; font-weight:bold">S/${dia.balance.toFixed(0)}</td></tr>`;
                });
                tbody.innerHTML = html;
            }).catch(e => showToast('Error de conexión', 'error'));
        }
        
        function switchTab(event, tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active');
        }
        
        function consultarMisTickets() {
            let inicio = document.getElementById('mis-tickets-fecha-inicio').value;
            let fin = document.getElementById('mis-tickets-fecha-fin').value;
            let estado = document.getElementById('mis-tickets-estado').value;
            if (!inicio || !fin) { showToast('Seleccione fechas', 'error'); return; }
            let container = document.getElementById('lista-mis-tickets');
            container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Cargando...</p>';
            fetch('/api/mis-tickets', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin, estado: estado})})
            .then(r => r.json()).then(d => {
                if (d.error) { container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error: ' + d.error + '</p>'; return; }
                document.getElementById('mis-tickets-resumen').style.display = 'block';
                document.getElementById('mis-tickets-info').textContent = `${d.totales.cantidad} tickets - Total ventas: S/${d.totales.ventas.toFixed(2)}`;
                if (d.tickets.length === 0) { container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">No se encontraron tickets</p>'; return; }
                let html = '';
                d.tickets.forEach(t => {
                    html += `<div class="ticket-item ${t.pagado ? 'ganador' : ''}" onclick="verDetalleTicket('${t.serial}')">
                        <div class="ticket-serial">#${t.serial}</div>
                        <div class="ticket-info">${t.fecha} - Total: S/${t.total}</div>
                        ${t.premio_calculado ? `<div class="ticket-premio">Premio: S/${t.premio_calculado}</div>` : ''}
                        <span class="ticket-estado ${t.pagado ? 'estado-pagado' : 'estado-pendiente'}">${t.pagado ? 'PAGADO' : 'PENDIENTE'}</span>
                    </div>`;
                });
                container.innerHTML = html;
            }).catch(e => { container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexión</p>'; });
        }
        
        function buscarTicketEspecifico() {
            let serial = document.getElementById('buscar-serial-input').value.trim();
            if (!serial) { showToast('Ingrese un serial', 'error'); return; }
            let container = document.getElementById('resultado-busqueda-ticket');
            container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Buscando...</p>';
            fetch('/api/consultar-ticket-detalle', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({serial: serial})})
            .then(r => r.json()).then(d => {
                if (d.error) { container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">' + d.error + '</p>'; return; }
                let t = d.ticket;
                let estadoColor = t.pagado ? '#27ae60' : (t.premio_total > 0 ? '#f39c12' : '#888');
                let html = `<div style="background: #0a0a0a; padding: 20px; border-radius: 10px; border: 2px solid ${estadoColor};">
                    <h3 style="color: #ffd700; margin-bottom: 15px; text-align: center;">TICKET #${t.serial}</h3>
                    <div class="stats-box">
                        <div class="stat-row"><span class="stat-label">Fecha:</span><span class="stat-value" style="font-size: 1rem;">${t.fecha}</span></div>
                        <div class="stat-row"><span class="stat-label">Apostado:</span><span class="stat-value" style="font-size: 1rem;">S/${t.total_apostado}</span></div>
                        <div class="stat-row"><span class="stat-label">Premio Total:</span><span class="stat-value" style="color: ${t.premio_total > 0 ? '#27ae60' : '#888'}; font-size: 1.2rem;">S/${t.premio_total.toFixed(2)}</span></div>
                    </div></div>`;
                container.innerHTML = html;
            }).catch(e => { container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexión</p>'; });
        }
        
        function verDetalleTicket(serial) {
            document.getElementById('modal-mis-tickets').style.display = 'none';
            document.getElementById('modal-buscar-ticket').style.display = 'block';
            document.getElementById('buscar-serial-input').value = serial;
            buscarTicketEspecifico();
        }
        
        function abrirMisTicketsPendientes() {
            document.getElementById('modal-pendientes').style.display = 'block';
            document.getElementById('lista-pendientes').innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Cargando...</p>';
            fetch('/api/mis-tickets-pendientes').then(r => r.json()).then(d => {
                if (d.error) { document.getElementById('lista-pendientes').innerHTML = '<p style="color: #c0392b; text-align: center;">Error: ' + d.error + '</p>'; return; }
                document.getElementById('pendientes-info').innerHTML = `Total Pendiente: <span style="color: #27ae60; font-size: 1.3rem;">S/${d.total_pendiente.toFixed(2)}</span> (${d.tickets.length} tickets)`;
                if (d.tickets.length === 0) { document.getElementById('lista-pendientes').innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">No tienes tickets pendientes por cobrar</p>'; return; }
                let html = '';
                d.tickets.forEach(t => { html += `<div class="ticket-item ganador"><div class="ticket-serial">#${t.serial}</div><div class="ticket-info">${t.fecha} • Apostado: S/${t.total}</div><div class="ticket-premio">💰 Ganancia: S/${t.premio.toFixed(2)}</div></div>`; });
                document.getElementById('lista-pendientes').innerHTML = html;
            }).catch(e => { document.getElementById('lista-pendientes').innerHTML = '<p style="color: #c0392b; text-align: center;">Error de conexión</p>'; });
        }
        
        async function pagar() {
            let serial = prompt('Ingrese SERIAL del ticket:');
            if (!serial) return;
            try {
                const response = await fetch('/api/verificar-ticket', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({serial: serial})});
                const d = await response.json();
                if (d.error) { showToast(d.error, 'error'); return; }
                let total = d.total_ganado;
                if (total > 0 && confirm(`TOTAL GANADO: S/${total.toFixed(2)}\\n\\n¿CONFIRMA PAGO?`)) {
                    await fetch('/api/pagar-ticket', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ticket_id: d.ticket_id})});
                    showToast('✅ Ticket pagado correctamente', 'success');
                } else if (total === 0) { showToast('Ticket no ganador', 'info'); }
            } catch (e) { showToast('Error de conexión', 'error'); }
        }
        
        async function anular() {
            let serial = prompt('SERIAL a anular:');
            if (!serial) return;
            if (!confirm('¿ANULAR ' + serial + '?')) return;
            try {
                const response = await fetch('/api/anular-ticket', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({serial: serial})});
                const d = await response.json();
                if (d.error) { showToast(d.error, 'error'); } else { showToast('✅ ' + d.mensaje, 'success'); }
            } catch (e) { showToast('Error de conexión', 'error'); }
        }
        
        function borrarTodo() {
            if (carrito.length > 0 || seleccionados.length > 0) { if (!confirm('¿Borrar todo?')) return; }
            seleccionados = []; especiales = []; horariosSel = []; carrito = []; seleccionTripleta = [];
            document.querySelectorAll('.active, .tripleta-seleccionado').forEach(el => { el.classList.remove('active'); el.classList.remove('tripleta-seleccionado'); });
            if (modoTripleta) toggleModoTripleta();
            updateTicket(); showToast('Ticket limpiado', 'info');
        }
        
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', function(e) { if (e.target === this) this.style.display = 'none'; });
        });
        
        document.addEventListener('DOMContentLoaded', function() {
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('hist-fecha-inicio').value = hoy;
            document.getElementById('hist-fecha-fin').value = hoy;
            document.getElementById('resultados-fecha').value = hoy;
            document.getElementById('mis-tickets-fecha-inicio').value = hoy;
            document.getElementById('mis-tickets-fecha-fin').value = hoy;
        });
    </script>
</body>
</html>
"""


ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
    <title>Panel Admin - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { background: #0a0a0a; color: white; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.5; }
        .admin-header { background: linear-gradient(90deg, #1a1a2e, #16213e); padding: 15px; border-bottom: 2px solid #ffd700; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; }
        .admin-title { color: #ffd700; font-size: 1.2rem; font-weight: bold; }
        .logout-btn { background: #c0392b; color: white; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 0.9rem; }
        .admin-tabs { display: flex; background: #1a1a2e; border-bottom: 1px solid #333; overflow-x: auto; scrollbar-width: none; }
        .admin-tabs::-webkit-scrollbar { display: none; }
        .admin-tab { flex: 1; min-width: 100px; padding: 15px 10px; background: transparent; border: none; color: #888; cursor: pointer; font-size: 0.85rem; border-bottom: 3px solid transparent; transition: all 0.2s; white-space: nowrap; }
        .admin-tab:hover { color: #ffd700; }
        .admin-tab.active { color: #ffd700; border-bottom-color: #ffd700; font-weight: bold; }
        .content { padding: 20px; max-width: 1200px; margin: 0 auto; padding-bottom: 30px; }
        .info-pago { background: linear-gradient(135deg, rgba(255,215,0,0.1), rgba(255,215,0,0.05)); padding: 15px; border-radius: 10px; margin: 15px 0; font-size: 0.85rem; text-align: center; border: 1px solid rgba(255,215,0,0.3); color: #ffd700; }
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px; }
        @media (min-width: 768px) { .stats-grid { grid-template-columns: repeat(4, 1fr); } }
        .stat-card { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px 15px; border-radius: 12px; border: 1px solid #ffd700; text-align: center; }
        .stat-card h3 { color: #888; font-size: 0.75rem; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; }
        .stat-card p { color: #ffd700; font-size: 1.4rem; font-weight: bold; }
        .form-box { background: #1a1a2e; padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #333; }
        .form-box h3 { color: #ffd700; margin-bottom: 15px; font-size: 1.1rem; border-bottom: 1px solid #333; padding-bottom: 10px; }
        .form-row { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }
        .form-row input, .form-row select { flex: 1; min-width: 120px; padding: 12px; background: #000; border: 1px solid #444; color: white; border-radius: 8px; font-size: 1rem; }
        .btn-submit { background: linear-gradient(135deg, #27ae60, #229954); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.95rem; flex: 1; min-width: 120px; }
        .btn-danger { background: linear-gradient(135deg, #c0392b, #e74c3c); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.95rem; }
        .btn-secondary { background: #444; color: white; border: none; padding: 10px 16px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; flex: 1; }
        .btn-csv { background: linear-gradient(135deg, #f39c12, #e67e22); color: black; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.95rem; }
        .btn-tripleta { background: linear-gradient(135deg, #FFD700, #FFA500); color: black; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.95rem; border: 2px solid #FFD700; }
        .table-container { overflow-x: auto; margin: 15px 0; border-radius: 8px; border: 1px solid #333; background: #1a1a2e; }
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        th, td { padding: 12px 10px; text-align: left; border-bottom: 1px solid #333; white-space: nowrap; }
        th { background: linear-gradient(135deg, #ffd700, #ffed4e); color: black; font-weight: bold; position: sticky; top: 0; }
        tr:hover { background: rgba(255,215,0,0.05); }
        .riesgo-item { background: #1a1a2e; padding: 15px; margin-bottom: 10px; border-radius: 8px; border-left: 4px solid #c0392b; font-size: 0.9rem; }
        .riesgo-item.lechuza { border-left-color: #ffd700; background: linear-gradient(135deg, rgba(255,215,0,0.1), #1a1a2e); }
        .riesgo-item b { color: #ffd700; font-size: 1.1rem; }
        .sorteo-actual-box { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 2px solid #2980b9; text-align: center; }
        .sorteo-actual-box h4 { color: #2980b9; margin-bottom: 8px; }
        .sorteo-actual-box p { color: #ffd700; font-size: 1.8rem; font-weight: bold; }
        .resultado-item { background: #0a0a0a; padding: 15px; margin: 8px 0; border-radius: 10px; border-left: 4px solid #27ae60; display: flex; justify-content: space-between; align-items: center; }
        .resultado-item.pendiente { border-left-color: #666; opacity: 0.7; }
        .resultado-numero { color: #ffd700; font-weight: bold; font-size: 1.3rem; }
        .resultado-nombre { color: #888; font-size: 0.9rem; }
        .btn-editar { background: linear-gradient(135deg, #2980b9, #3498db); color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: bold; margin-left: 10px; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 2000; justify-content: center; align-items: center; padding: 20px; }
        .modal.active { display: flex; }
        .modal-box { background: #1a1a2e; padding: 25px; border-radius: 15px; border: 2px solid #ffd700; max-width: 400px; width: 100%; }
        .modal-box h3 { color: #ffd700; margin-bottom: 20px; text-align: center; }
        .warning-box { background: rgba(243, 156, 18, 0.2); border: 1px solid #f39c12; color: #f39c12; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 0.9rem; display: none; }
        .ranking-item { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 15px; margin-bottom: 10px; border-radius: 10px; border-left: 4px solid #ffd700; display: flex; justify-content: space-between; align-items: center; }
        .ranking-pos { font-size: 1.5rem; font-weight: bold; color: #ffd700; min-width: 40px; }
        .ranking-info { flex: 1; padding: 0 10px; }
        .ranking-nombre { font-weight: bold; color: white; font-size: 1.1rem; }
        .ranking-detalle { font-size: 0.85rem; color: #888; margin-top: 3px; }
        .ranking-ventas { font-size: 1.3rem; font-weight: bold; color: #27ae60; }
        .stat-row { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #222; font-size: 1rem; align-items: center; }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #aaa; }
        .stat-value { color: #ffd700; font-weight: bold; font-size: 1.2rem; }
        .mensaje { padding: 15px; margin: 15px 0; border-radius: 8px; display: none; font-size: 0.95rem; text-align: center; }
        .mensaje.success { background: rgba(39,174,96,0.2); border: 1px solid #27ae60; display: block; color: #27ae60; }
        .mensaje.error { background: rgba(192,57,43,0.2); border: 1px solid #c0392b; display: block; color: #c0392b; }
        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.3s; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .btn-group { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
        .btn-group button { flex: 1; min-width: 80px; }
        .tripleta-card { background: linear-gradient(135deg, #1a1a2e, #16213e); border: 2px solid #FFD700; border-radius: 12px; padding: 15px; margin-bottom: 15px; position: relative; }
        .tripleta-card.ganadora { background: linear-gradient(135deg, rgba(39,174,96,0.2), #1a1a2e); border-color: #27ae60; }
        .tripleta-serial { color: #ffd700; font-weight: bold; font-size: 1.1rem; }
        .tripleta-agencia { color: #888; font-size: 0.85rem; }
        .tripleta-animales { display: flex; gap: 10px; margin: 15px 0; justify-content: center; }
        .tripleta-animal { background: #000; border: 2px solid #FFD700; border-radius: 10px; padding: 10px 15px; text-align: center; min-width: 80px; }
        .tripleta-animal .num { color: #FFD700; font-size: 1.5rem; font-weight: bold; }
        .tripleta-animal .name { color: #aaa; font-size: 0.75rem; margin-top: 4px; }
        .tripleta-premio { text-align: center; color: #27ae60; font-size: 1.3rem; font-weight: bold; margin-top: 5px; }
        .tripleta-estado { position: absolute; top: 10px; right: 10px; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: bold; }
        .estado-ganadora { background: #27ae60; color: white; }
        .estado-pendiente { background: #666; color: white; }
        .premio-box { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
        .premio-pendiente { background: #f39c12; color: black; }
        .agencia-selector { background: linear-gradient(135deg, #0a0a0a, #1a1a2e); padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #444; }
        .agencia-selector label { color: #ffd700; font-weight: bold; display: block; margin-bottom: 8px; font-size: 0.9rem; }
        .agencia-selector select { width: 100%; padding: 12px; background: #000; border: 2px solid #ffd700; color: white; border-radius: 8px; font-size: 1rem; }
    </style>
</head>
<body>
    <div class="modal" id="modal-editar">
        <div class="modal-box">
            <h3>✏️ EDITAR RESULTADO</h3>
            <div class="warning-box" id="editar-advertencia">⚠️ Este sorteo tiene tickets vendidos. Cambiar el resultado afectará quién gana o pierde.</div>
            <div style="margin-bottom: 15px;">
                <label style="display: block; color: #888; margin-bottom: 5px;">Fecha:</label>
                <input type="text" id="editar-fecha-display" readonly style="width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #ffd700; border-radius: 6px; font-weight: bold;">
            </div>
            <div style="margin-bottom: 15px;">
                <label style="display: block; color: #888; margin-bottom: 5px;">Hora:</label>
                <input type="text" id="editar-hora-display" readonly style="width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #ffd700; border-radius: 6px; font-weight: bold;">
            </div>
            <div style="margin-bottom: 20px;">
                <label style="display: block; color: #888; margin-bottom: 5px;">Nuevo Animal:</label>
                <select id="editar-animal-select" style="width: 100%; padding: 12px; background: #000; border: 2px solid #ffd700; color: white; border-radius: 8px; font-size: 1rem;">
                    {% for k, v in animales.items() %}<option value="{{k}}">{{k}} - {{v}}</option>{% endfor %}
                </select>
            </div>
            <div style="display: flex; gap: 10px;">
                <button onclick="cerrarModalEditar()" style="flex: 1; background: #444; color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-weight: bold;">CANCELAR</button>
                <button onclick="confirmarEdicion()" style="flex: 2; background: linear-gradient(135deg, #27ae60, #229954); color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-weight: bold;">GUARDAR CAMBIO</button>
            </div>
        </div>
    </div>

    <div class="admin-header">
        <div class="admin-title">👑 PANEL ADMIN - ZOOLO CASINO</div>
        <button onclick="location.href='/logout'" class="logout-btn">SALIR</button>
    </div>

    <div class="admin-tabs">
        <button class="admin-tab active" onclick="showTab('dashboard')">📊 Dashboard</button>
        <button class="admin-tab" onclick="showTab('resultados')">📋 Resultados</button>
        <button class="admin-tab" onclick="showTab('riesgo')">⚠️ Riesgo</button>
        <button class="admin-tab" onclick="showTab('tripletas')">🎯 Tripletas</button>
        <button class="admin-tab" onclick="showTab('reporte')">🏢 Reporte</button>
        <button class="admin-tab" onclick="showTab('historico')">📈 Histórico</button>
        <button class="admin-tab" onclick="showTab('agencias')">🏪 Agencias</button>
        <button class="admin-tab" onclick="showTab('operaciones')">⚙️ Operaciones</button>
    </div>

    <div class="content">
        <div id="mensaje" class="mensaje"></div>
        <div class="info-pago">💰 REGLAS: Animales (00-39) = x35 | Lechuza (40) = x70 | Especiales = x2 | Tripleta = x60</div>

        <div id="dashboard" class="tab-content active">
            <h3 style="color: #ffd700; margin-bottom: 15px;">📊 RESUMEN DE HOY</h3>
            <div class="stats-grid">
                <div class="stat-card"><h3>VENTAS</h3><p id="stat-ventas">S/0</p></div>
                <div class="stat-card"><h3>PREMIOS PAGADOS</h3><p id="stat-premios">S/0</p></div>
                <div class="stat-card"><h3>PENDIENTES</h3><p id="stat-premios-pendientes" style="color: #f39c12;">S/0</p></div>
                <div class="stat-card"><h3>BALANCE</h3><p id="stat-balance">S/0</p></div>
            </div>
            <div class="form-box">
                <h3>⚡ ACCIONES RÁPIDAS</h3>
                <div class="btn-group">
                    <button class="btn-submit" onclick="showTab('riesgo')">Ver Riesgo</button>
                    <button class="btn-tripleta" onclick="showTab('tripletas')">🎯 Ver Tripletas</button>
                    <button class="btn-secondary" onclick="showTab('resultados')">Cargar Resultados</button>
                    <button class="btn-csv" onclick="showTab('reporte')">Reporte Agencias</button>
                </div>
            </div>
        </div>

        <div id="riesgo" class="tab-content">
            <div class="agencia-selector">
                <label for="riesgo-agencia-select">🏢 SELECCIONAR AGENCIA:</label>
                <select id="riesgo-agencia-select" onchange="cambiarAgenciaRiesgo()"><option value="">TODAS LAS AGENCIAS</option></select>
            </div>
            <div class="sorteo-actual-box"><h4>🎯 SORTEO EN CURSO / PRÓXIMO</h4><p id="sorteo-objetivo">Cargando...</p></div>
            <h3 style="color: #ffd700; margin-bottom: 15px;">💸 APUESTAS: <span id="total-apostado-sorteo" style="color: white;">S/0</span></h3>
            <div id="lista-riesgo"><p style="color: #888;">Cargando...</p></div>
        </div>

        <div id="tripletas" class="tab-content">
            <h3 style="color: #ffd700; margin-bottom: 15px;">🎯 TRIPLETAS DE HOY (Paga x60)</h3>
            <div class="form-box">
                <button class="btn-tripleta" onclick="cargarTripletas()">🔄 Actualizar</button>
                <div class="stats-grid" style="margin: 15px 0;">
                    <div class="stat-card" style="border-color: #FFD700;"><h3>TOTAL</h3><p id="trip-total" style="color: #FFD700;">0</p></div>
                    <div class="stat-card" style="border-color: #27ae60;"><h3>GANADORAS</h3><p id="trip-ganadoras" style="color: #27ae60;">0</p></div>
                    <div class="stat-card" style="border-color: #c0392b;"><h3>PREMIOS</h3><p id="trip-premios" style="color: #c0392b;">S/0</p></div>
                </div>
                <div id="lista-tripletas" style="max-height: 600px; overflow-y: auto;"><p style="color: #888; text-align: center; padding: 20px;">Cargando...</p></div>
            </div>
        </div>

        <div id="reporte" class="tab-content">
            <div class="form-box">
                <h3>🏢 REPORTE POR AGENCIAS</h3>
                <div style="margin-bottom: 15px;">
                    <label style="display: block; color: #888; margin-bottom: 6px;">Filtrar por Agencia:</label>
                    <select id="reporte-agencia-select" onchange="cambiarFiltroAgencia()" style="width: 100%; padding: 12px; background: #000; border: 1px solid #444; color: white; border-radius: 8px;"><option value="">TODAS LAS AGENCIAS</option></select>
                </div>
                <div class="form-row">
                    <input type="date" id="reporte-fecha-inicio">
                    <input type="date" id="reporte-fecha-fin">
                    <button class="btn-submit" onclick="consultarReporteAgencias()">GENERAR</button>
                </div>
                <div class="btn-group">
                    <button class="btn-secondary" onclick="setRangoReporte('hoy')">Hoy</button>
                    <button class="btn-secondary" onclick="setRangoReporte('ayer')">Ayer</button>
                    <button class="btn-secondary" onclick="setRangoReporte('semana')">7 días</button>
                    <button class="btn-csv" onclick="exportarCSV()">📊 CSV</button>
                </div>
                <div id="reporte-agencias-resumen" style="display:none; margin-top: 25px;">
                    <h4 style="color: #ffd700; margin-bottom: 15px;">📈 TOTALES <span id="titulo-filtro-agencia"></span></h4>
                    <div class="stats-grid" id="stats-agencias-totales"></div>
                    <div class="form-box" style="background: rgba(255,215,0,0.05);">
                        <h4 style="color: #ffd700; margin-bottom: 10px;">💰 DESGLOSE DE PREMIOS</h4>
                        <div class="stat-row"><span class="stat-label">Premios Pagados:</span><span class="stat-value" id="reporte-premios-pagados" style="color: #27ae60;">S/0</span></div>
                        <div class="stat-row"><span class="stat-label">Premios Pendientes:</span><span class="stat-value" id="reporte-premios-pendientes" style="color: #f39c12;">S/0</span></div>
                        <div class="stat-row"><span class="stat-label">Total en Premios:</span><span class="stat-value" id="reporte-premios-total" style="color: #ffd700;">S/0</span></div>
                        <div class="stat-row"><span class="stat-label">Tickets sin Cobrar:</span><span class="stat-value" id="reporte-tickets-pendientes" style="color: #f39c12;">0</span></div>
                    </div>
                    <h4 style="color: #ffd700; margin: 25px 0 15px;">🏆 TOP 5 AGENCIAS</h4>
                    <div id="ranking-agencias"></div>
                    <h4 style="color: #ffd700; margin: 25px 0 15px;">📋 DETALLE COMPLETO</h4>
                    <div class="table-container">
                        <table id="tabla-detalle-agencias">
                            <thead><tr><th>#</th><th>Agencia</th><th>Tickets</th><th>Ventas</th><th>Premios Pagados</th><th>Pendientes</th><th>Balance</th><th>%</th></tr></thead>
                            <tbody></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div id="resultados" class="tab-content">
            <div class="form-box">
                <h3>🔍 CONSULTAR RESULTADOS</h3>
                <div class="form-row">
                    <input type="date" id="admin-resultados-fecha" onchange="cargarResultadosAdminFecha()">
                    <button class="btn-submit" onclick="cargarResultadosAdminFecha()">CONSULTAR</button>
                    <button class="btn-secondary" onclick="cargarResultadosAdmin()">HOY</button>
                </div>
                <div id="admin-resultados-titulo" style="margin-top: 15px; color: #ffd700; font-weight: bold; text-align: center;"></div>
            </div>
            <div class="form-box">
                <h3>📋 RESULTADOS CARGADOS</h3>
                <div id="lista-resultados-admin" style="max-height: 400px; overflow-y: auto;"><p style="color: #888; text-align: center; padding: 20px;">Seleccione una fecha...</p></div>
            </div>
            <div class="form-box">
                <h3>✏️ CARGAR/EDITAR RESULTADO</h3>
                <div class="form-row">
                    <select id="res-hora" style="flex: 1.5;">{% for h in horarios %}<option value="{{h}}">{{h}}</option>{% endfor %}</select>
                    <select id="res-animal" style="flex: 2;">{% for k, v in animales.items() %}<option value="{{k}}">{{k}} - {{v}}</option>{% endfor %}</select>
                    <button class="btn-submit" onclick="guardarResultado()">GUARDAR</button>
                </div>
                <div style="margin-top: 10px; font-size: 0.85rem; color: #888;">ℹ️ Atajos: Presiona <strong>N</strong> para seleccionar Delfín (0) | <strong>M</strong> para Ballena (00)</div>
            </div>
        </div>

        <div id="historico" class="tab-content">
            <div class="form-box">
                <h3>📅 CONSULTA HISTÓRICA</h3>
                <div class="form-row">
                    <input type="date" id="hist-fecha-inicio">
                    <input type="date" id="hist-fecha-fin">
                    <button class="btn-submit" onclick="consultarHistorico()">CONSULTAR</button>
                </div>
                <div class="btn-group">
                    <button class="btn-secondary" onclick="setRango('hoy')">Hoy</button>
                    <button class="btn-secondary" onclick="setRango('ayer')">Ayer</button>
                    <button class="btn-secondary" onclick="setRango('semana')">7 días</button>
                    <button class="btn-secondary" onclick="setRango('mes')">Mes</button>
                </div>
                <div id="historico-resumen" style="display:none;">
                    <div class="stats-grid" style="margin-top: 20px;">
                        <div class="stat-card"><h3>VENTAS</h3><p id="hist-total-ventas">S/0</p></div>
                        <div class="stat-card"><h3>PREMIOS</h3><p id="hist-total-premios">S/0</p></div>
                        <div class="stat-card"><h3>TICKETS</h3><p id="hist-total-tickets">0</p></div>
                        <div class="stat-card"><h3>BALANCE</h3><p id="hist-total-balance">S/0</p></div>
                    </div>
                    <h3 style="color: #ffd700; margin: 25px 0 15px;">📋 DETALLE POR DÍA</h3>
                    <div class="table-container">
                        <table><thead><tr><th>Fecha</th><th>Tickets</th><th>Ventas</th><th>Premios</th><th>Balance</th></tr></thead><tbody id="tabla-historico"></tbody></table>
                    </div>
                    <h3 style="color: #ffd700; margin: 25px 0 15px;">🔥 TOP ANIMALES</h3>
                    <div id="top-animales-hist"></div>
                </div>
            </div>
        </div>

        <div id="operaciones" class="tab-content">
            <div class="form-box">
                <h3>💰 PAGAR TICKET</h3>
                <div class="form-row">
                    <input type="text" id="pagar-serial-admin" placeholder="Ingrese SERIAL del ticket" style="flex: 2;">
                    <button class="btn-submit" onclick="pagarTicketAdmin()">VERIFICAR Y PAGAR</button>
                </div>
                <div id="resultado-pago-admin" style="margin-top: 15px;"></div>
            </div>
            <div class="form-box">
                <h3>❌ ANULAR TICKET</h3>
                <div class="form-row">
                    <input type="text" id="anular-serial" placeholder="Ingrese SERIAL del ticket" style="flex: 2;">
                    <button class="btn-danger" onclick="anularTicketAdmin()">ANULAR</button>
                </div>
                <div id="resultado-anular" style="margin-top: 15px; font-size: 1rem; text-align: center;"></div>
            </div>
        </div>

        <div id="agencias" class="tab-content">
            <div class="form-box">
                <h3>➕ CREAR NUEVA AGENCIA</h3>
                <div class="form-row">
                    <input type="text" id="new-usuario" placeholder="Usuario">
                    <input type="password" id="new-password" placeholder="Contraseña">
                </div>
                <div class="form-row">
                    <input type="text" id="new-nombre" placeholder="Nombre de la Agencia" style="flex: 2;">
                    <button class="btn-submit" onclick="crearAgencia()">CREAR AGENCIA</button>
                </div>
            </div>
            <h3 style="color: #ffd700; margin-bottom: 15px;">🏢 AGENCIAS EXISTENTES</h3>
            <div class="table-container">
                <table><thead><tr><th>ID</th><th>Usuario</th><th>Nombre</th><th>Comisión</th></tr></thead><tbody id="tabla-agencias"><tr><td colspan="4" style="text-align:center;color:#888; padding: 20px;">Cargando...</td></tr></tbody></table>
            </div>
        </div>
    </div>

    <script>
        const HORARIOS_ORDEN = JSON.parse('{{ horarios | tojson | safe }}');
        let reporteAgenciasData = null;
        let fechasConsulta = { inicio: null, fin: null };
        let listaAgencias = [];
        let editandoFecha = null;
        let editandoHora = null;
        let filtroAgenciaActual = null;

        function showTab(tab) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.admin-tab').forEach(b => b.classList.remove('active'));
            const target = document.getElementById(tab);
            if (target) target.classList.add('active');
            const buttons = document.querySelectorAll('.admin-tab');
            buttons.forEach(btn => { if (btn.getAttribute('onclick').includes("'" + tab + "'")) btn.classList.add('active'); });
            if (tab === 'riesgo') { cargarAgenciasSelect(); cargarRiesgo(); }
            if (tab === 'tripletas') cargarTripletas();
            if (tab === 'reporte') { let hoy = new Date().toISOString().split('T')[0]; document.getElementById('reporte-fecha-inicio').value = hoy; document.getElementById('reporte-fecha-fin').value = hoy; cargarAgenciasReporte(); consultarReporteAgencias(); }
            if (tab === 'agencias') cargarAgencias();
            if (tab === 'dashboard') cargarDashboard();
            if (tab === 'resultados') { let hoy = new Date().toISOString().split('T')[0]; document.getElementById('admin-resultados-fecha').value = hoy; cargarResultadosAdmin(); }
        }

        function showMensaje(msg, tipo) {
            let div = document.getElementById('mensaje');
            div.textContent = msg; div.className = 'mensaje ' + tipo;
            setTimeout(() => div.className = 'mensaje', 4000);
        }

        function setRango(tipo) {
            let hoy = new Date(); let inicio, fin;
            switch(tipo) {
                case 'hoy': inicio = fin = hoy; break;
                case 'ayer': let ayer = new Date(hoy); ayer.setDate(ayer.getDate() - 1); inicio = fin = ayer; break;
                case 'semana': inicio = new Date(hoy); inicio.setDate(inicio.getDate() - 6); fin = hoy; break;
                case 'mes': inicio = new Date(hoy.getFullYear(), hoy.getMonth(), 1); fin = hoy; break;
            }
            document.getElementById('hist-fecha-inicio').value = inicio.toISOString().split('T')[0];
            document.getElementById('hist-fecha-fin').value = fin.toISOString().split('T')[0];
            consultarHistorico();
        }

        function setRangoReporte(tipo) {
            let hoy = new Date(); let inicio, fin;
            switch(tipo) {
                case 'hoy': inicio = fin = hoy; break;
                case 'ayer': let ayer = new Date(hoy); ayer.setDate(ayer.getDate() - 1); inicio = fin = ayer; break;
                case 'semana': inicio = new Date(hoy); inicio.setDate(inicio.getDate() - 6); fin = hoy; break;
            }
            document.getElementById('reporte-fecha-inicio').value = inicio.toISOString().split('T')[0];
            document.getElementById('reporte-fecha-fin').value = fin.toISOString().split('T')[0];
            consultarReporteAgencias();
        }

        function cargarAgenciasSelect() {
            fetch('/admin/lista-agencias').then(r => r.json()).then(d => {
                if (d.error) return;
                listaAgencias = d;
                let select = document.getElementById('riesgo-agencia-select');
                select.innerHTML = '<option value="">TODAS LAS AGENCIAS</option>';
                d.forEach(ag => { select.innerHTML += `<option value="${ag.id}">${ag.nombre_agencia} (${ag.usuario})</option>`; });
            });
        }

        function cargarAgenciasReporte() {
            fetch('/admin/lista-agencias').then(r => r.json()).then(d => {
                if (d.error) return;
                let select = document.getElementById('reporte-agencia-select');
                select.innerHTML = '<option value="">TODAS LAS AGENCIAS</option>';
                d.forEach(ag => { select.innerHTML += `<option value="${ag.id}">${ag.nombre_agencia}</option>`; });
            });
        }

        function cambiarFiltroAgencia() { filtroAgenciaActual = document.getElementById('reporte-agencia-select').value; consultarReporteAgencias(); }
        function cambiarAgenciaRiesgo() { cargarRiesgo(); }

        function cargarTripletas() {
            fetch('/admin/tripletas-hoy').then(r => r.json()).then(d => {
                if (d.error) { showMensaje(d.error, 'error'); return; }
                document.getElementById('trip-total').textContent = d.total;
                document.getElementById('trip-ganadoras').textContent = d.ganadoras;
                document.getElementById('trip-premios').textContent = 'S/' + d.total_premios.toFixed(2);
                let container = document.getElementById('lista-tripletas');
                if (!d.tripletas || d.tripletas.length === 0) { container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">No hay tripletas jugadas hoy</p>'; return; }
                let html = '';
                d.tripletas.forEach(trip => {
                    let claseGanadora = trip.gano ? 'ganadora' : '';
                    let estadoClass = trip.pagado ? '' : (trip.gano ? 'estado-ganadora' : 'estado-pendiente');
                    let estadoText = trip.pagado ? 'PAGADA' : (trip.gano ? 'GANADORA' : 'EN JUEGO');
                    html += `<div class="tripleta-card ${claseGanadora}"><div class="tripleta-estado ${estadoClass}">${estadoText}</div>
                        <div><div class="tripleta-serial">#${trip.serial}</div><div class="tripleta-agencia">${trip.agencia}</div></div>
                        <div class="tripleta-animales">
                            <div class="tripleta-animal"><div class="num">${trip.animal1}</div><div class="name">${trip.nombres[0]}</div></div>
                            <div class="tripleta-animal"><div class="num">${trip.animal2}</div><div class="name">${trip.nombres[1]}</div></div>
                            <div class="tripleta-animal"><div class="num">${trip.animal3}</div><div class="name">${trip.nombres[2]}</div></div>
                        </div>
                        <div style="text-align: center; color: #aaa;">Apostado: S/${trip.monto} | Paga x60</div>
                        ${trip.gano ? `<div class="tripleta-premio">💰 Premio: S/${trip.premio}</div>` : ''}
                    </div>`;
                });
                container.innerHTML = html;
            }).catch(e => showMensaje('Error cargando tripletas', 'error'));
        }

        function pagarTicketAdmin() {
            const serial = document.getElementById('pagar-serial-admin').value.trim();
            if (!serial) { showMensaje('Ingrese un serial', 'error'); return; }
            fetch('/api/verificar-ticket', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({serial: serial})})
            .then(r => r.json()).then(d => {
                if (d.error) { document.getElementById('resultado-pago-admin').innerHTML = `<div style="color: #c0392b; padding: 15px; background: rgba(192,57,43,0.1); border-radius: 8px;">${d.error}</div>`; return; }
                let html = `<div style="background: rgba(39,174,96,0.1); padding: 20px; border-radius: 10px; border: 1px solid #27ae60;">
                    <p style="font-size: 1.3rem; color: #ffd700; margin-bottom: 15px;">Total Ganado: S/${d.total_ganado.toFixed(2)}</p>
                    ${d.total_ganado > 0 ? `<button onclick="confirmarPagoAdmin('${d.ticket_id}')" class="btn-submit" style="width: 100%;">CONFIRMAR PAGO</button>` : '<p style="color: #888;">Ticket no ganador</p>'}
                </div>`;
                document.getElementById('resultado-pago-admin').innerHTML = html;
            });
        }

        function confirmarPagoAdmin(ticketId) {
            fetch('/api/pagar-ticket', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ticket_id: ticketId})})
            .then(r => r.json()).then(d => {
                if (d.status === 'ok') { showMensaje('✅ Ticket pagado correctamente', 'success'); document.getElementById('resultado-pago-admin').innerHTML = '<div style="color: #27ae60; text-align: center; padding: 20px;">✅ Pago realizado con éxito</div>'; }
                else { showMensaje(d.error || 'Error al pagar', 'error'); }
            });
        }

        function anularTicketAdmin() {
            let serial = document.getElementById('anular-serial').value.trim();
            if (!serial) { showMensaje('Ingrese un serial', 'error'); return; }
            if (!confirm('¿Está seguro de anular el ticket ' + serial + '?')) return;
            fetch('/api/anular-ticket', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({serial: serial})})
            .then(r => r.json()).then(d => {
                let resultadoDiv = document.getElementById('resultado-anular');
                if (d.error) { resultadoDiv.innerHTML = '<span style="color: #c0392b; font-weight:bold">❌ ' + d.error + '</span>'; showMensaje(d.error, 'error'); }
                else { resultadoDiv.innerHTML = '<span style="color: #27ae60; font-weight:bold">✅ ' + d.mensaje + '</span>'; showMensaje(d.mensaje, 'success'); document.getElementById('anular-serial').value = ''; }
            }).catch(e => showMensaje('Error de conexión', 'error'));
        }

        function abrirModalEditar(hora, fecha, animalActual) {
            editandoHora = hora; editandoFecha = fecha;
            document.getElementById('editar-fecha-display').value = fecha;
            document.getElementById('editar-hora-display').value = hora;
            document.getElementById('editar-animal-select').value = animalActual;
            verificarTicketsSorteo(fecha, hora);
            document.getElementById('modal-editar').classList.add('active');
        }

        function cerrarModalEditar() { document.getElementById('modal-editar').classList.remove('active'); editandoFecha = null; editandoHora = null; }

        function verificarTicketsSorteo(fecha, hora) {
            fetch('/admin/verificar-tickets-sorteo', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fecha: fecha, hora: hora})})
            .then(r => r.json()).then(d => {
                let advertencia = document.getElementById('editar-advertencia');
                if (d.tickets_count > 0) { advertencia.style.display = 'block'; advertencia.innerHTML = `⚠️ <strong>ADVERTENCIA:</strong> Este sorteo tiene <strong>${d.tickets_count} ticket(s)</strong> vendidos por un total de <strong>S/${d.total_apostado}</strong>.`; }
                else { advertencia.style.display = 'none'; }
            }).catch(e => console.error(e));
        }

        function confirmarEdicion() {
            let nuevoAnimal = document.getElementById('editar-animal-select').value;
            if (!confirm(`¿Está seguro de cambiar el resultado de ${editandoHora} a ${nuevoAnimal}?`)) return;
            let partes = editandoFecha.split('/');
            let fechaISO = `${partes[2]}-${partes[1]}-${partes[0]}`;
            let form = new FormData();
            form.append('hora', editandoHora); form.append('animal', nuevoAnimal); form.append('fecha', fechaISO);
            fetch('/admin/guardar-resultado', {method: 'POST', body: form}).then(r => r.json()).then(d => {
                if (d.status === 'ok') { showMensaje('✅ ' + d.mensaje, 'success'); cerrarModalEditar(); cargarResultadosAdmin(); }
                else { showMensaje(d.error || 'Error al guardar', 'error'); }
            }).catch(e => showMensaje('Error de conexión', 'error'));
        }

        function getNombreAnimal(numero) {
            const animales = JSON.parse('{{ animales | tojson | safe }}');
            return animales[numero] || 'Desconocido';
        }

        function consultarHistorico() {
            let inicio = document.getElementById('hist-fecha-inicio').value;
            let fin = document.getElementById('hist-fecha-fin').value;
            if (!inicio || !fin) { showMensaje('Seleccione ambas fechas', 'error'); return; }
            fetch('/admin/estadisticas-rango', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})})
            .then(r => r.json()).then(d => {
                if (d.error) { showMensaje(d.error, 'error'); return; }
                document.getElementById('historico-resumen').style.display = 'block';
                document.getElementById('hist-total-ventas').textContent = 'S/' + d.totales.ventas.toFixed(0);
                document.getElementById('hist-total-premios').textContent = 'S/' + d.totales.premios.toFixed(0);
                document.getElementById('hist-total-tickets').textContent = d.totales.tickets;
                document.getElementById('hist-total-balance').textContent = 'S/' + d.totales.balance.toFixed(0);
                let tbody = document.getElementById('tabla-historico');
                let html = '';
                d.resumen_por_dia.forEach(dia => {
                    let color = dia.balance >= 0 ? '#27ae60' : '#c0392b';
                    html += `<tr><td>${dia.fecha}</td><td>${dia.tickets}</td><td>S/${dia.ventas.toFixed(0)}</td><td>S/${dia.premios.toFixed(0)}</td><td style="color:${color}; font-weight:bold">S/${dia.balance.toFixed(0)}</td></tr>`;
                });
                tbody.innerHTML = html;
                cargarTopAnimalesHistorico(inicio, fin);
            }).catch(e => showMensaje('Error de conexión', 'error'));
        }

        function consultarReporteAgencias() {
            let inicio = document.getElementById('reporte-fecha-inicio').value;
            let fin = document.getElementById('reporte-fecha-fin').value;
            let agenciaId = document.getElementById('reporte-agencia-select').value;
            if (!inicio || !fin) { showMensaje('Seleccione ambas fechas', 'error'); return; }
            fetch('/admin/reporte-agencias-rango', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin, agencia_id: agenciaId || null})})
            .then(r => r.json()).then(d => {
                if (d.error) { showMensaje(d.error, 'error'); return; }
                reporteAgenciasData = d;
                document.getElementById('reporte-agencias-resumen').style.display = 'block';
                let tituloAgencia = agenciaId ? document.querySelector('#reporte-agencia-select option:checked').text : 'TODAS LAS AGENCIAS';
                document.getElementById('titulo-filtro-agencia').textContent = `- ${tituloAgencia}`;
                let totales = d.totales;
                document.getElementById('stats-agencias-totales').innerHTML = `
                    <div class="stat-card"><h3>AGENCIAS</h3><p>${d.agencias.length}</p></div>
                    <div class="stat-card"><h3>TICKETS</h3><p>${totales.tickets}</p></div>
                    <div class="stat-card"><h3>VENTAS</h3><p>S/${totales.ventas.toFixed(0)}</p></div>
                    <div class="stat-card"><h3>BALANCE</h3><p style="color: ${totales.balance >= 0 ? '#27ae60' : '#c0392b'}">S/${totales.balance.toFixed(0)}</p></div>`;
                document.getElementById('reporte-premios-pagados').textContent = 'S/' + totales.premios_pagados.toFixed(2);
                document.getElementById('reporte-premios-pendientes').textContent = 'S/' + totales.premios_pendientes.toFixed(2);
                document.getElementById('reporte-premios-total').textContent = 'S/' + totales.premios_teoricos.toFixed(2);
                document.getElementById('reporte-tickets-pendientes').textContent = totales.tickets_pendientes_count;
                let htmlRanking = '';
                d.agencias.slice(0, 5).forEach((ag, idx) => {
                    let medalla = ['🥇','🥈','🥉','4°','5°'][idx];
                    let colorBalance = ag.balance >= 0 ? '#27ae60' : '#c0392b';
                    htmlRanking += `<div class="ranking-item"><div class="ranking-pos">${medalla}</div><div class="ranking-info"><div class="ranking-nombre">${ag.nombre}</div><div class="ranking-detalle">${ag.tickets} tickets • ${ag.porcentaje_ventas}%</div></div><div><div class="ranking-ventas">S/${ag.ventas.toFixed(0)}</div><div style="color: ${colorBalance}">S/${ag.balance.toFixed(0)}</div></div></div>`;
                });
                document.getElementById('ranking-agencias').innerHTML = htmlRanking;
                let tbody = document.querySelector('#tabla-detalle-agencias tbody');
                let htmlTabla = '';
                d.agencias.forEach((ag, idx) => {
                    let colorBalance = ag.balance >= 0 ? '#27ae60' : '#c0392b';
                    let pendienteBadge = ag.premios_pendientes > 0 ? `<span class="premio-box premio-pendiente">S/${ag.premios_pendientes}</span>` : '<span style="color:#666">-</span>';
                    htmlTabla += `<tr><td>${idx + 1}</td><td><strong>${ag.nombre}</strong><br><small style="color:#888">${ag.usuario}</small></td><td>${ag.tickets}</td><td>S/${ag.ventas.toFixed(0)}</td><td style="color:#27ae60">S/${ag.premios_pagados.toFixed(0)}</td><td>${pendienteBadge}</td><td style="color:${colorBalance}; font-weight:bold">S/${ag.balance.toFixed(0)}</td><td>${ag.porcentaje_ventas}%</td></tr>`;
                });
                tbody.innerHTML = htmlTabla;
            }).catch(e => { console.error(e); showMensaje('Error de conexión', 'error'); });
        }

        function exportarCSV() {
            if (!reporteAgenciasData) { showMensaje('Primero genere un reporte', 'error'); return; }
            let inicio = document.getElementById('reporte-fecha-inicio').value;
            let fin = document.getElementById('reporte-fecha-fin').value;
            fetch('/admin/exportar-csv', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})})
            .then(r => r.blob()).then(blob => {
                let url = window.URL.createObjectURL(blob);
                let a = document.createElement('a'); a.href = url; a.download = `reporte_agencias_${inicio}_${fin}.csv`;
                document.body.appendChild(a); a.click(); window.URL.revokeObjectURL(url); document.body.removeChild(a);
                showMensaje('CSV descargado correctamente', 'success');
            }).catch(e => showMensaje('Error al exportar', 'error'));
        }

        function cargarTopAnimalesHistorico(inicio, fin) {
            fetch('/admin/top-animales-rango', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})})
            .then(r => r.json()).then(d => {
                let container = document.getElementById('top-animales-hist');
                if (!d.top_animales || d.top_animales.length === 0) { container.innerHTML = '<p style="color: #888;">No hay datos</p>'; return; }
                let html = '';
                d.top_animales.slice(0, 10).forEach((a, idx) => {
                    let medalla = idx < 3 ? ['🥇','🥈','🥉'][idx] : (idx + 1);
                    html += `<div class="riesgo-item"><b>${medalla} ${a.numero} - ${a.nombre}</b><br><small>Apostado: S/${a.total_apostado} • Si sale pagaría: S/${a.pago_potencial}</small></div>`;
                });
                container.innerHTML = html;
            });
        }

        function cargarDashboard() {
            fetch('/admin/reporte-agencias').then(r => r.json()).then(d => {
                if (d.global) {
                    document.getElementById('stat-ventas').textContent = 'S/' + d.global.ventas.toFixed(0);
                    document.getElementById('stat-premios').textContent = 'S/' + d.global.pagos.toFixed(0);
                    document.getElementById('stat-premios-pendientes').textContent = 'S/' + (d.global.premios_pendientes || 0).toFixed(0);
                    document.getElementById('stat-balance').textContent = 'S/' + d.global.balance.toFixed(0);
                }
            }).catch(() => {});
        }

        function cargarRiesgo() {
            let agenciaId = document.getElementById('riesgo-agencia-select').value;
            let url = '/admin/riesgo' + (agenciaId ? '?agencia_id=' + agenciaId : '');
            fetch(url).then(r => r.json()).then(d => {
                document.getElementById('sorteo-objetivo').textContent = d.sorteo_objetivo || 'No hay más sorteos hoy';
                document.getElementById('total-apostado-sorteo').textContent = 'S/' + (d.total_apostado || 0).toFixed(2);
                let container = document.getElementById('lista-riesgo');
                if (!d.riesgo || Object.keys(d.riesgo).length === 0) { container.innerHTML = '<p style="color:#888; text-align: center; padding: 20px;">No hay apuestas para este sorteo</p>'; return; }
                let html = '';
                for (let [k, v] of Object.entries(d.riesgo)) {
                    let clase = v.es_lechuza ? 'riesgo-item lechuza' : 'riesgo-item';
                    html += `<div class="${clase}"><b>${k}${v.es_lechuza ? ' ⚠️ ALTO RIESGO (x70)' : ''}</b><br>Apostado: S/${v.apostado.toFixed(2)} • Pagaría: S/${v.pagaria.toFixed(2)} • ${v.porcentaje}% del total</div>`;
                }
                container.innerHTML = html;
            }).catch(e => showMensaje('Error cargando riesgo', 'error'));
        }

        function cargarResultadosAdminFecha() {
            let fecha = document.getElementById('admin-resultados-fecha').value;
            if (!fecha) return;
            let container = document.getElementById('lista-resultados-admin');
            container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Cargando...</p>';
            fetch('/api/resultados-fecha', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fecha: fecha})})
            .then(r => r.json()).then(d => {
                if (d.error) { container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error: ' + d.error + '</p>'; return; }
                renderizarResultadosAdmin(d.resultados, d.fecha_consulta);
            }).catch(() => { container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexión</p>'; });
        }

        function cargarResultadosAdmin() {
            fetch('/admin/resultados-hoy').then(r => r.json()).then(d => {
                if (d.error) { document.getElementById('lista-resultados-admin').innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error al cargar</p>'; return; }
                document.getElementById('admin-resultados-titulo').textContent = 'HOY - ' + new Date().toLocaleDateString('es-PE');
                renderizarResultadosAdmin(d.resultados, d.fecha);
            }).catch(() => { document.getElementById('lista-resultados-admin').innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexión</p>'; });
        }

        function renderizarResultadosAdmin(resultados, fechaStr) {
            let container = document.getElementById('lista-resultados-admin');
            let html = '';
            for (let hora of HORARIOS_ORDEN) {
                let resultado = resultados[hora];
                let clase = resultado ? '' : 'pendiente';
                let contenido, botonEditar;
                if (resultado) {
                    contenido = `<span class="resultado-numero">${resultado.animal}</span><span class="resultado-nombre">${resultado.nombre}</span>`;
                    botonEditar = `<button class="btn-editar" onclick="abrirModalEditar('${hora}', '${fechaStr}', '${resultado.animal}')">✏️ EDITAR</button>`;
                } else {
                    contenido = `<span style="color: #666;">Pendiente</span>`;
                    botonEditar = `<button class="btn-editar" onclick="prepararNuevoResultado('${hora}')" style="background: #27ae60;">➕ CARGAR</button>`;
                }
                html += `<div class="resultado-item ${clase}"><strong style="color: #ffd700;">${hora}</strong><div style="text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 5px;">${contenido}${botonEditar}</div></div>`;
            }
            container.innerHTML = html;
        }

        function prepararNuevoResultado(hora) {
            document.getElementById('res-hora').value = hora;
            document.getElementById('res-animal').focus();
            document.querySelector('[onclick="showTab('resultados')"]').click();
            setTimeout(() => document.getElementById('res-hora').scrollIntoView({behavior: 'smooth'}), 300);
        }

        function guardarResultado() {
            let form = new FormData();
            form.append('hora', document.getElementById('res-hora').value);
            form.append('animal', document.getElementById('res-animal').value);
            let fechaActual = document.getElementById('admin-resultados-fecha').value;
            if (fechaActual) form.append('fecha', fechaActual);
            fetch('/admin/guardar-resultado', {method: 'POST', body: form}).then(r => r.json()).then(d => {
                if (d.status === 'ok') { showMensaje('✅ ' + d.mensaje, 'success'); cargarResultadosAdmin(); }
                else showMensaje(d.error || 'Error', 'error');
            });
        }

        function cargarAgencias() {
            fetch('/admin/lista-agencias').then(r => r.json()).then(d => {
                let tbody = document.getElementById('tabla-agencias');
                if (!d || d.length === 0) { tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 20px;">No hay agencias</td></tr>'; return; }
                let html = '';
                for (let a of d) html += `<tr><td>${a.id}</td><td>${a.usuario}</td><td>${a.nombre_agencia}</td><td>${(a.comision * 100).toFixed(0)}%</td></tr>`;
                tbody.innerHTML = html;
            });
        }

        function crearAgencia() {
            let form = new FormData();
            form.append('usuario', document.getElementById('new-usuario').value.trim());
            form.append('password', document.getElementById('new-password').value.trim());
            form.append('nombre', document.getElementById('new-nombre').value.trim());
            fetch('/admin/crear-agencia', {method: 'POST', body: form}).then(r => r.json()).then(d => {
                if (d.status === 'ok') { showMensaje('✅ ' + d.mensaje, 'success'); document.getElementById('new-usuario').value = ''; document.getElementById('new-password').value = ''; document.getElementById('new-nombre').value = ''; cargarAgencias(); }
                else showMensaje(d.error || 'Error', 'error');
            });
        }

        document.addEventListener('DOMContentLoaded', function() {
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('hist-fecha-inicio').value = hoy;
            document.getElementById('hist-fecha-fin').value = hoy;
            document.getElementById('admin-resultados-fecha').value = hoy;
        });

        // ==================== CAMBIO 4: SHORTCUTS N y M ====================
        document.addEventListener('keydown', function(e) {
            let selectAnimal = document.getElementById('res-animal');
            if (!selectAnimal) return;
            // No activar si el usuario está escribiendo en otro lado
            if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
            
            if (e.key.toLowerCase() === 'n') {
                selectAnimal.value = "0"; // Selecciona el Delfín
                showMensaje('Seleccionado: 0 - Delfin', 'success');
            } else if (e.key.toLowerCase() === 'm') {
                selectAnimal.value = "00"; // Selecciona la Ballena
                showMensaje('Seleccionado: 00 - Ballena', 'success');
            }
        });

        cargarDashboard();
    </script>
</body>
</html>
"""

# ==================== MAIN ====================
if __name__ == '__main__':
    print("=" * 60)
    print("  ZOOLO CASINO CLOUD v6.1 - CORREGIDO")
    print("=" * 60)
    print("  ✓ supabase_request: limit SOLO en GET (fix POST/PATCH)")
    print("  ✓ resultados_hoy: isinstance check")
    print("  ✓ resultados_fecha: isinstance check")
    print("  ✓ admin_resultados_hoy: isinstance check")
    print("  ✓ Shortcuts N=Delfin, M=Ballena en admin")
    print("=" * 60)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
