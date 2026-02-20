#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v5.8 - MENU WINDOWS AGENCIA + ADMIN
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

# ==================== FUNCIONES AUXILIARES ====================
def ahora_peru():
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

# ==================== FUNCIONES ZONA HORARIA ====================
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
    ahora = ahora_peru()
    hoy = ahora.strftime("%d/%m/%Y")
    
    if fecha_str and fecha_str != hoy:
        pass
    
    minutos_sorteo = hora_a_minutos(hora_sorteo)
    minutos_actual = ahora.hour * 60 + ahora.minute
    
    minutos_limite = minutos_sorteo + (HORAS_EDICION_RESULTADO * 60)
    
    return minutos_actual <= minutos_limite

def obtener_sorteo_en_curso():
    ahora = ahora_peru()
    actual_minutos = ahora.hour * 60 + ahora.minute
    
    for hora_str in HORARIOS_PERU:
        minutos_sorteo = hora_a_minutos(hora_str)
        
        if actual_minutos >= minutos_sorteo and actual_minutos < (minutos_sorteo + 60):
            return hora_str
    
    return obtener_proximo_sorteo()

def obtener_proximo_sorteo():
    ahora = ahora_peru()
    actual_minutos = ahora.hour * 60 + ahora.minute
    
    for hora_str in HORARIOS_PERU:
        minutos_sorteo = hora_a_minutos(hora_str)
        
        if (minutos_sorteo - actual_minutos) > MINUTOS_BLOQUEO:
            return hora_str
    
    return None

def supabase_request(table, method="GET", data=None, filters=None, timeout=30):
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
        data = request.get_json()
        fecha_str = data.get('fecha')
        
        if not fecha_str:
            return jsonify({'error': 'Fecha requerida'}), 400
        
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
            if not verificar_horario_bloqueo(j['hora']):
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
                    texto_jugadas.append(f"{nombre_corto}{j['seleccion']}x{int(j['monto'])}")
                else:
                    tipo_corto = j['seleccion'][0:3]
                    texto_jugadas.append(f"{tipo_corto}x{int(j['monto'])}")
            
            lineas.append(" ".join(texto_jugadas))
            lineas.append("")
        
        lineas.append("------------------------")
        lineas.append(f"*TOTAL: S/{int(total)}*")
        lineas.append("")
        lineas.append("Buena Suerte! 🍀")
        lineas.append("El ticket vence a los 3 dias")
        
        texto_whatsapp = "\n".join(lineas)
        url_whatsapp = f"https://wa.me/?text= {urllib.parse.quote(texto_whatsapp)}"
        
        return jsonify({
            'status': 'ok',
            'serial': serial,
            'ticket_id': ticket_id,
            'total': total,
            'url_whatsapp': url_whatsapp
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
        
        if ticket['anulado']:
            return jsonify({'error': 'TICKET ANULADO'})
        if ticket['pagado']:
            return jsonify({'error': 'YA FUE PAGADO'})
        
        jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
        
        fecha_ticket = ticket['fecha'].split(' ')[0]
        resultados_list = supabase_request("resultados", filters={"fecha": fecha_ticket})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        total_ganado = 0
        detalles = []
        
        for j in jugadas:
            wa = resultados.get(j['hora'])
            premio = 0
            if wa:
                if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                    premio = calcular_premio_animal(j['monto'], wa)
                elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                    sel = j['seleccion']
                    num = int(wa)
                    if (sel == 'ROJO' and str(wa) in ROJOS) or \
                       (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                       (sel == 'PAR' and num % 2 == 0) or \
                       (sel == 'IMPAR' and num % 2 != 0):
                        premio = j['monto'] * PAGO_ESPECIAL
            
            total_ganado += premio
            detalles.append({
                'hora': j['hora'],
                'sel': j['seleccion'],
                'gano': premio > 0,
                'premio': premio,
                'es_lechuza': str(wa) == "40" and j['tipo'] == 'animal' and str(wa) == str(j['seleccion'])
            })
        
        return jsonify({
            'status': 'ok',
            'ticket_id': ticket['id'],
            'total_ganado': total_ganado,
            'detalles': detalles
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
        else:
            jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
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
                if not t['pagado']:
                    jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                    resultados_list = supabase_request("resultados", filters={"fecha": hoy})
                    resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
                    
                    tiene_premio = False
                    for j in jugadas:
                        wa = resultados.get(j['hora'])
                        if wa:
                            if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                                tiene_premio = True
                            elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                                sel = j['seleccion']
                                num = int(wa)
                                if (sel == 'ROJO' and str(wa) in ROJOS) or \
                                   (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                                   (sel == 'PAR' and num % 2 == 0) or \
                                   (sel == 'IMPAR' and num % 2 != 0):
                                    tiene_premio = True
                    if tiene_premio:
                        tickets_pendientes += 1
                
                if t['pagado']:
                    jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                    resultados_list = supabase_request("resultados", filters={"fecha": hoy})
                    resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
                    
                    for j in jugadas:
                        wa = resultados.get(j['hora'])
                        if wa:
                            if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                                premios += calcular_premio_animal(j['monto'], wa)
                            elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                                sel = j['seleccion']
                                num = int(wa)
                                if (sel == 'ROJO' and str(wa) in ROJOS) or \
                                   (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                                   (sel == 'PAR' and num % 2 == 0) or \
                                   (sel == 'IMPAR' and num % 2 != 0):
                                    premios += j['monto'] * PAGO_ESPECIAL
        
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{session['user_id']}&order=fecha.desc&limit=500"
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
                dias_data[dia_key] = {
                    'ventas': 0, 
                    'tickets': 0, 
                    'premios': 0,
                    'pendientes': 0
                }
            
            dias_data[dia_key]['ventas'] += t['total']
            dias_data[dia_key]['tickets'] += 1
            total_ventas += t['total']
            
            resultados_list = supabase_request("resultados", filters={"fecha": dia_key})
            resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
            
            if t['pagado']:
                jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                premio_ticket = 0
                for j in jugadas:
                    wa = resultados.get(j['hora'])
                    if wa:
                        if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                            premio_ticket += calcular_premio_animal(j['monto'], wa)
                        elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                            num = int(wa)
                            sel = j['seleccion']
                            if (sel == 'ROJO' and str(wa) in ROJOS) or \
                               (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                               (sel == 'PAR' and num % 2 == 0) or \
                               (sel == 'IMPAR' and num % 2 != 0):
                                premio_ticket += j['monto'] * PAGO_ESPECIAL
                
                dias_data[dia_key]['premios'] += premio_ticket
                total_premios += premio_ticket
            else:
                jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                tiene_premio = 0
                for j in jugadas:
                    wa = resultados.get(j['hora'])
                    if wa:
                        if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                            tiene_premio += calcular_premio_animal(j['monto'], wa)
                        elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                            sel = j['seleccion']
                            num = int(wa)
                            if (sel == 'ROJO' and str(wa) in ROJOS) or \
                               (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                               (sel == 'PAR' and num % 2 == 0) or \
                               (sel == 'IMPAR' and num % 2 != 0):
                                tiene_premio += j['monto'] * PAGO_ESPECIAL
                
                if tiene_premio > 0:
                    dias_data[dia_key]['pendientes'] += 1
                    tickets_pendientes_cobro.append({
                        'serial': t['serial'],
                        'fecha': t['fecha'],
                        'monto': t['total'],
                        'premio': round(tiene_premio, 2)
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
        hoy = ahora_peru().strftime("%d/%m/%Y")
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{session['user_id']}&anulado=eq.false&pagado=eq.false"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        
        resultados_list = supabase_request("resultados", filters={"fecha": hoy})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        tickets_con_premio = []
        
        for t in tickets:
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
            total_premio = 0
            tiene_premio = False
            
            for j in jugadas:
                wa = resultados.get(j['hora'])
                if wa:
                    if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                        total_premio += calcular_premio_animal(j['monto'], wa)
                        tiene_premio = True
                    elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                        sel = j['seleccion']
                        num = int(wa)
                        if (sel == 'ROJO' and str(wa) in ROJOS) or \
                           (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                           (sel == 'PAR' and num % 2 == 0) or \
                           (sel == 'IMPAR' and num % 2 != 0):
                            total_premio += j['monto'] * PAGO_ESPECIAL
                            tiene_premio = True
            
            if tiene_premio:
                tickets_con_premio.append({
                    'serial': t['serial'],
                    'fecha': t['fecha'],
                    'total': t['total'],
                    'premio': round(total_premio, 2),
                    'jugadas': len(jugadas)
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
                return jsonify({
                    'error': f'No se puede editar. Solo disponible hasta 2 horas después del sorteo (ej: 7PM editable hasta 9PM).'
                }), 403
        
        existentes = supabase_request("resultados", filters={"fecha": fecha, "hora": hora})
        
        if existentes and len(existentes) > 0:
            url = f"{SUPABASE_URL}/rest/v1/resultados?fecha=eq.{urllib.parse.quote(fecha)}&hora=eq.{urllib.parse.quote(hora)}"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
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
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        
        tickets_con_jugadas = []
        total_apostado = 0
        
        for t in tickets:
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id'], "hora": hora})
            if jugadas and len(jugadas) > 0:
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

@app.route('/admin/resultados-hoy')
@admin_required
def admin_resultados_hoy():
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=2000"
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
            if resultados_list:
                resultados_por_dia[dia_str] = {r['hora']: r['animal'] for r in resultados_list}
        
        stats_por_agencia = {}
        for ag in agencias:
            stats_por_agencia[ag['id']] = {
                'id': ag['id'],
                'nombre': ag['nombre_agencia'],
                'usuario': ag['usuario'],
                'comision_pct': ag['comision'],
                'tickets': 0,
                'ventas': 0,
                'premios': 0,
                'comision': 0,
                'balance': 0,
                'tickets_pagados': 0,
                'tickets_pendientes': 0
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
            
            if t['pagado']:
                stats['tickets_pagados'] += 1
                jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
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
            else:
                jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                tiene_premio = False
                for j in jugadas:
                    wa = resultados_dia.get(j['hora'])
                    if wa:
                        if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                            tiene_premio = True
                            break
                        elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                            num = int(wa)
                            sel = j['seleccion']
                            if (sel == 'ROJO' and str(wa) in ROJOS) or \
                               (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                               (sel == 'PAR' and num % 2 == 0) or \
                               (sel == 'IMPAR' and num % 2 != 0):
                                tiene_premio = True
                                break
                if tiene_premio:
                    stats['tickets_pendientes'] += 1
        
        total_global = {
            'tickets': 0, 'ventas': 0, 'premios': 0, 'comision': 0,
            'balance': 0, 'tickets_pagados': 0, 'tickets_pendientes': 0
        }
        
        reporte_agencias = []
        for ag_id, stats in stats_por_agencia.items():
            if stats['tickets'] > 0:
                stats['comision'] = stats['ventas'] * stats['comision_pct']
                stats['balance'] = stats['ventas'] - stats['premios'] - stats['comision']
                stats['ventas'] = round(stats['ventas'], 2)
                stats['premios'] = round(stats['premios'], 2)
                stats['comision'] = round(stats['comision'], 2)
                stats['balance'] = round(stats['balance'], 2)
                
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
            'rango': {'inicio': fecha_inicio, 'fin': fecha_fin, 'dias': (dt_fin - dt_inicio).days + 1}
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=2000"
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
            if resultados_list:
                resultados_por_dia[dia_str] = {r['hora']: r['animal'] for r in resultados_list}
        
        stats_por_agencia = {}
        for ag in agencias:
            stats_por_agencia[ag['id']] = {
                'nombre': ag['nombre_agencia'],
                'usuario': ag['usuario'],
                'tickets': 0, 'ventas': 0, 'premios': 0
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
            
            if t['pagado']:
                jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
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
                
                writer.writerow([
                    stats['nombre'], stats['usuario'], stats['tickets'],
                    round(stats['ventas'], 2), round(stats['premios'], 2),
                    round(comision, 2), round(balance, 2), f"{porcentaje:.1f}%"
                ])
        
        writer.writerow([])
        total_comision = sum(s['ventas'] * dict_agencias[ag_id]['comision'] for ag_id, s in stats_por_agencia.items())
        total_balance = sum(s['ventas'] for s in stats_por_agencia.values()) - sum(s['premios'] for s in stats_por_agencia.values()) - total_comision
        
        writer.writerow(['TOTALES', '', 
            sum(s['tickets'] for s in stats_por_agencia.values()),
            round(total_ventas, 2), round(sum(s['premios'] for s in stats_por_agencia.values()), 2),
            round(total_comision, 2), round(total_balance, 2), '100%'
        ])
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Type': 'text/csv; charset=utf-8',
                'Content-Disposition': f'attachment; filename=reporte_agencias_{fecha_inicio}_{fecha_fin}.csv'
            }
        )
        
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
        resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(hoy)}%25"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        
        data_agencias = []
        total_ventas = total_premios = total_comisiones = 0
        
        for ag in agencias:
            ventas = sum(t['total'] for t in tickets if t['agencia_id'] == ag['id'] and not t['anulado'])
            comision = ventas * ag['comision']
            
            premios = 0
            for t in tickets:
                if t['agencia_id'] == ag['id'] and t['pagado']:
                    jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                    for j in jugadas:
                        wa = resultados.get(j['hora'])
                        if wa:
                            if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                                premios += calcular_premio_animal(j['monto'], wa)
                            elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                                sel = j['seleccion']
                                num = int(wa)
                                if (sel == 'ROJO' and str(wa) in ROJOS) or \
                                   (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                                   (sel == 'PAR' and num % 2 == 0) or \
                                   (sel == 'IMPAR' and num % 2 != 0):
                                    premios += j['monto'] * PAGO_ESPECIAL
            
            balance = ventas - premios - comision
            
            data_agencias.append({
                'nombre': ag['nombre_agencia'],
                'ventas': round(ventas, 2),
                'premios': round(premios, 2),
                'comision': round(comision, 2),
                'balance': round(balance, 2)
            })
            
            total_ventas += ventas
            total_premios += premios
            total_comisiones += comision
        
        return jsonify({
            'agencias': data_agencias,
            'global': {
                'ventas': round(total_ventas, 2),
                'pagos': round(total_premios, 2),
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
            return jsonify({
                'riesgo': {},
                'sorteo_objetivo': None,
                'mensaje': 'No hay más sorteos disponibles para hoy',
                'agencia_nombre': nombre_agencia
            })
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(hoy)}%25&anulado=eq.false"
        
        if agencia_id:
            url += f"&agencia_id=eq.{urllib.parse.quote(str(agencia_id))}"
            agencias = supabase_request("agencias", filters={"id": agencia_id})
            if agencias and len(agencias) > 0:
                nombre_agencia = agencias[0]['nombre_agencia']
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        
        if not tickets:
            return jsonify({
                'riesgo': {},
                'sorteo_objetivo': sorteo_objetivo,
                'mensaje': 'No hay tickets vendidos hoy',
                'total_apostado': 0,
                'agencia_nombre': nombre_agencia,
                'agencia_id': agencia_id
            })
        
        apuestas = {}
        total_apostado_sorteo = 0
        total_jugadas_contadas = 0
        
        for t in tickets:
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id'], "tipo": "animal"})
            
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
        
        riesgo = {}
        for sel, monto in apuestas_ordenadas:
            nombre = ANIMALES.get(sel, sel)
            multiplicador = PAGO_LECHUZA if sel == "40" else PAGO_ANIMAL_NORMAL
            riesgo[f"{sel} - {nombre}"] = {
                "apostado": round(monto, 2),
                "pagaria": round(monto * multiplicador, 2),
                "es_lechuza": sel == "40",
                "porcentaje": round((monto / total_apostado_sorteo) * 100, 1) if total_apostado_sorteo > 0 else 0
            }
        
        return jsonify({
            'riesgo': riesgo,
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
                dias_data[dia_key] = {
                    'ventas': 0, 'tickets': 0, 'premios': 0, 
                    'comisiones': 0, 'ids_tickets': []
                }
            
            dias_data[dia_key]['ventas'] += t['total']
            dias_data[dia_key]['tickets'] += 1
            dias_data[dia_key]['ids_tickets'].append(t['id'])
        
        resultados_por_dia = {}
        delta = dt_fin - dt_inicio
        for i in range(delta.days + 1):
            dia_str = (dt_inicio + timedelta(days=i)).strftime("%d/%m/%Y")
            resultados_list = supabase_request("resultados", filters={"fecha": dia_str})
            if resultados_list:
                resultados_por_dia[dia_str] = {r['hora']: r['animal'] for r in resultados_list}
        
        resumen_dias = []
        total_ventas = total_premios = total_tickets = 0
        
        for dia_key in sorted(dias_data.keys()):
            datos = dias_data[dia_key]
            resultados_dia = resultados_por_dia.get(dia_key, {})
            
            premios_dia = 0
            for ticket_id in datos['ids_tickets'][:50]:
                jugadas = supabase_request("jugadas", filters={"ticket_id": ticket_id})
                ticket_info = next((t for t in tickets_rango if t['id'] == ticket_id), None)
                
                if ticket_info and ticket_info['pagado']:
                    for j in jugadas:
                        wa = resultados_dia.get(j['hora'])
                        if wa:
                            if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                                premios_dia += calcular_premio_animal(j['monto'], wa)
                            elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                                num = int(wa)
                                sel = j['seleccion']
                                if (sel == 'ROJO' and str(wa) in ROJOS) or \
                                   (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                                   (sel == 'PAR' and num % 2 == 0) or \
                                   (sel == 'IMPAR' and num % 2 != 0):
                                    premios_dia += j['monto'] * PAGO_ESPECIAL
            
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=500"
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
            Sistema ZOOLO CASINO v5.8<br>Menu Windows Agencia + Admin
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
            min-height: 100vh; 
            display: flex; 
            flex-direction: column;
            overflow-x: hidden;
        }
        
        /* ==========================================
           MENU WINDOWS FORMS - AGENCIA
           ========================================== */
        .win-menu-bar {
            background: linear-gradient(180deg, #2d2d2d 0%, #1a1a1a 100%);
            border-bottom: 2px solid #000;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        
        .win-menu-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 15px;
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            border-bottom: 1px solid #000;
        }
        
        .win-title {
            color: #ffd700;
            font-size: 1rem;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .win-menu-items {
            display: flex;
            list-style: none;
            padding: 0;
            margin: 0;
            background: #2d2d2d;
        }
        
        .win-menu-item {
            position: relative;
        }
        
        .win-menu-item > a {
            display: block;
            padding: 10px 20px;
            color: #fff;
            text-decoration: none;
            font-size: 0.85rem;
            border-right: 1px solid #444;
            transition: all 0.2s;
            cursor: pointer;
        }
        
        .win-menu-item:hover > a {
            background: linear-gradient(180deg, #404040 0%, #333 100%);
            color: #ffd700;
        }
        
        .win-submenu {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            background: #2d2d2d;
            border: 1px solid #555;
            border-top: none;
            min-width: 200px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            z-index: 1001;
        }
        
        .win-menu-item:hover .win-submenu {
            display: block;
        }
        
        .win-submenu-item {
            border-bottom: 1px solid #444;
        }
        
        .win-submenu-item:last-child {
            border-bottom: none;
        }
        
        .win-submenu-item a {
            display: block;
            padding: 12px 20px;
            color: #ddd;
            text-decoration: none;
            font-size: 0.85rem;
            transition: all 0.2s;
            cursor: pointer;
        }
        
        .win-submenu-item a:hover {
            background: #ffd700;
            color: #000;
            padding-left: 25px;
        }
        
        /* ==========================================
           MENU HAMBURGER - MOBIL AGENCIA
           ========================================== */
        .mobile-header {
            display: none;
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 12px 15px;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #ffd700;
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        
        .mobile-title {
            color: #ffd700;
            font-size: 1.1rem;
            font-weight: bold;
        }
        
        .hamburger-btn {
            background: transparent;
            border: none;
            color: #ffd700;
            font-size: 1.5rem;
            cursor: pointer;
            padding: 5px;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .mobile-menu {
            display: none;
            position: fixed;
            top: 0;
            right: -300px;
            width: 280px;
            height: 100vh;
            background: linear-gradient(180deg, #1a1a2e 0%, #0a0a0a 100%);
            border-left: 2px solid #ffd700;
            z-index: 2000;
            transition: right 0.3s ease;
            overflow-y: auto;
        }
        
        .mobile-menu.active {
            right: 0;
        }
        
        .mobile-menu-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: rgba(0,0,0,0.3);
            border-bottom: 1px solid #333;
        }
        
        .mobile-menu-title {
            color: #ffd700;
            font-size: 1.1rem;
        }
        
        .close-menu-btn {
            background: #c0392b;
            border: none;
            color: white;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.1rem;
        }
        
        .mobile-menu-section {
            border-bottom: 1px solid #333;
        }
        
        .mobile-menu-section-title {
            background: rgba(255,215,0,0.1);
            color: #ffd700;
            padding: 12px 15px;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 1px solid #333;
        }
        
        .mobile-menu-item {
            padding: 15px;
            color: #fff;
            cursor: pointer;
            border-bottom: 1px solid #222;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.95rem;
        }
        
        .mobile-menu-item:active {
            background: rgba(255,215,0,0.1);
        }
        
        .mobile-menu-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 1999;
        }
        
        .mobile-menu-overlay.active {
            display: block;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .win-menu-bar {
                display: none;
            }
            .mobile-header {
                display: flex;
            }
            .mobile-menu {
                display: block;
            }
        }
        
        @media (min-width: 769px) {
            .mobile-menu, .mobile-menu-overlay {
                display: none !important;
            }
        }
        
        /* Header optimizado */
        .header {
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 10px 15px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            border-bottom: 2px solid #ffd700; 
            flex-shrink: 0;
        }
        .header-info h3 { color: #ffd700; font-size: 1rem; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
        .header-info p { color: #888; font-size: 0.75rem; margin: 0; }
        .monto-box { display: flex; align-items: center; gap: 8px; background: rgba(0,0,0,0.3); padding: 6px 12px; border-radius: 20px; }
        .monto-box span { font-size: 0.8rem; font-weight: bold; color: #ffd700; }
        .monto-box input {
            width: 60px; padding: 6px; border: 2px solid #ffd700; border-radius: 6px;
            background: #000; color: #ffd700; text-align: center; font-weight: bold; font-size: 1rem;
            -webkit-appearance: none;
        }
        
        /* Layout principal */
        .main-container { 
            display: flex; 
            flex-direction: column;
            flex: 1;
            height: calc(100vh - 110px);
            overflow: hidden;
        }
        
        @media (min-width: 1024px) {
            .main-container { flex-direction: row; }
        }
        
        /* Panel izquierdo */
        .left-panel { 
            flex: 1; 
            display: flex; 
            flex-direction: column; 
            min-height: 0;
            overflow: hidden;
        }
        
        /* Botones especiales */
        .special-btns { 
            display: grid; 
            grid-template-columns: repeat(4, 1fr);
            gap: 6px; 
            padding: 10px; 
            background: #111; 
            flex-shrink: 0;
        }
        .btn-esp { 
            padding: 12px 4px; 
            border: none; 
            border-radius: 8px; 
            font-weight: bold; 
            cursor: pointer; 
            color: white; 
            font-size: 0.8rem;
            touch-action: manipulation;
            min-height: 44px;
            transition: all 0.1s;
        }
        .btn-esp:active { transform: scale(0.95); }
        .btn-rojo { background: linear-gradient(135deg, #c0392b, #e74c3c); }
        .btn-negro { background: linear-gradient(135deg, #2c3e50, #34495e); border: 1px solid #555; }
        .btn-par { background: linear-gradient(135deg, #2980b9, #3498db); }
        .btn-impar { background: linear-gradient(135deg, #8e44ad, #9b59b6); }
        .btn-esp.active { 
            box-shadow: 0 0 15px rgba(255,255,255,0.5); 
            transform: scale(0.95);
            border: 2px solid white;
        }
        
        /* Grid de animales */
        .animals-grid {
            flex: 1; 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
            gap: 5px; 
            padding: 10px; 
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
        }
        @media (min-width: 768px) {
            .animals-grid { grid-template-columns: repeat(7, 1fr); }
        }
        
        .animal-card {
            background: linear-gradient(135deg, #1a1a2e, #16213e); 
            border: 2px solid; 
            border-radius: 10px;
            padding: 8px 2px; 
            text-align: center; 
            cursor: pointer; 
            transition: all 0.15s; 
            min-height: 65px; 
            display: flex; 
            flex-direction: column; 
            justify-content: center;
            user-select: none;
            position: relative;
            touch-action: manipulation;
        }
        .animal-card:active { transform: scale(0.92); }
        .animal-card.active { 
            box-shadow: 0 0 15px rgba(255,215,0,0.6); 
            border-color: #ffd700 !important; 
            background: linear-gradient(135deg, #2a2a4e, #1a1a3e);
            transform: scale(1.05);
            z-index: 10;
        }
        .animal-card .num { font-size: 1.2rem; font-weight: bold; line-height: 1; }
        .animal-card .name { font-size: 0.7rem; color: #aaa; line-height: 1; margin-top: 4px; font-weight: 500; }
        .animal-card.lechuza::after {
            content: "x70";
            position: absolute;
            top: 3px;
            right: 3px;
            background: #ffd700;
            color: black;
            font-size: 0.6rem;
            padding: 2px 4px;
            border-radius: 4px;
            font-weight: bold;
        }
        
        /* Panel derecho */
        .right-panel {
            background: #111; 
            border-top: 2px solid #333;
            display: flex; 
            flex-direction: column;
            height: 40vh;
            flex-shrink: 0;
        }
        @media (min-width: 1024px) { 
            .right-panel { 
                width: 350px; 
                height: auto;
                border-top: none;
                border-left: 2px solid #333;
            }
        }
        
        /* Horarios */
        .horarios {
            display: flex;
            gap: 6px;
            padding: 10px;
            overflow-x: auto;
            flex-shrink: 0;
            background: #0a0a0a;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: thin;
            scrollbar-color: #ffd700 #222;
        }
        .horarios::-webkit-scrollbar { height: 8px; }
        .horarios::-webkit-scrollbar-track { background: #222; border-radius: 4px; }
        .horarios::-webkit-scrollbar-thumb { background: #ffd700; border-radius: 4px; }
        
        .btn-hora {
            flex: 0 0 auto;
            min-width: 85px;
            padding: 10px 6px; 
            background: #222; 
            border: 1px solid #444;
            border-radius: 8px; 
            color: #ccc; 
            cursor: pointer; 
            font-size: 0.75rem; 
            text-align: center; 
            line-height: 1.3;
            touch-action: manipulation;
            transition: all 0.2s;
        }
        .btn-hora:hover { background: #333; border-color: #555; }
        .btn-hora.active { 
            background: linear-gradient(135deg, #27ae60, #229954); 
            color: white; 
            font-weight: bold; 
            border-color: #27ae60;
            box-shadow: 0 0 10px rgba(39, 174, 96, 0.4);
        }
        .btn-hora.expired { 
            background: #300; 
            color: #666; 
            text-decoration: line-through; 
            pointer-events: none;
            opacity: 0.5;
        }
        
        /* Ticket display */
        .ticket-display {
            flex: 1; 
            background: #000; 
            margin: 0 10px 10px; 
            border-radius: 10px;
            padding: 12px; 
            border: 1px solid #333;
            overflow-y: auto;
            font-size: 0.85rem;
            -webkit-overflow-scrolling: touch;
        }
        
        .ticket-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem;
        }
        .ticket-table th {
            background: #1a1a2e;
            color: #ffd700;
            padding: 8px 6px;
            text-align: left;
            position: sticky;
            top: 0;
            font-size: 0.75rem;
        }
        .ticket-table td {
            padding: 8px 6px;
            border-bottom: 1px solid #222;
            vertical-align: middle;
        }
        .ticket-table tr:last-child td { border-bottom: none; }
        .ticket-total {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 2px solid #ffd700;
            text-align: right;
            font-size: 1.2rem;
            font-weight: bold;
            color: #ffd700;
        }
        
        /* Botones de acción */
        .action-btns { 
            display: grid; 
            grid-template-columns: repeat(3, 1fr); 
            gap: 6px; 
            padding: 10px;
            background: #0a0a0a;
            flex-shrink: 0;
        }
        .action-btns button {
            padding: 14px 5px; 
            border: none; 
            border-radius: 8px;
            font-weight: bold; 
            cursor: pointer; 
            font-size: 0.8rem;
            touch-action: manipulation;
            min-height: 48px;
            transition: all 0.1s;
        }
        .action-btns button:active { transform: scale(0.95); }
        .btn-agregar { 
            background: linear-gradient(135deg, #27ae60, #229954); 
            color: white; 
            grid-column: span 3; 
            font-size: 1.1rem;
        }
        .btn-vender { 
            background: linear-gradient(135deg, #2980b9, #2573a7); 
            color: white; 
            grid-column: span 3;
            font-size: 1rem;
        }
        .btn-resultados { background: #f39c12; color: black; }
        .btn-caja { background: #16a085; color: white; }
        .btn-pagar { background: #8e44ad; color: white; }
        .btn-anular { background: #c0392b; color: white; }
        .btn-borrar { background: #555; color: white; }
        .btn-salir { background: #333; color: white; grid-column: span 3; }
        
        /* Modales */
        .modal {
            display: none; 
            position: fixed; 
            top: 0; left: 0;
            width: 100%; 
            height: 100%; 
            background: rgba(0,0,0,0.95);
            z-index: 1000; 
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
        }
        .modal-content {
            background: #1a1a2e; 
            margin: 10px; 
            padding: 20px; 
            border-radius: 15px; 
            border: 2px solid #ffd700; 
            max-width: 100%;
            min-height: calc(100vh - 20px);
        }
        @media (min-width: 768px) {
            .modal-content {
                margin: 40px auto; 
                max-width: 600px;
                min-height: auto;
            }
        }
        .modal-header {
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            margin-bottom: 20px; 
            padding-bottom: 15px; 
            border-bottom: 1px solid #333;
        }
        .modal h3 { color: #ffd700; font-size: 1.3rem; }
        .btn-close {
            background: #c0392b; 
            color: white; 
            border: none; 
            padding: 8px 16px; 
            border-radius: 6px; 
            cursor: pointer;
            font-weight: bold;
        }
        
        /* Tabs */
        .tabs { 
            display: flex; 
            gap: 2px; 
            margin-bottom: 20px; 
            border-bottom: 2px solid #333;
            overflow-x: auto;
            scrollbar-width: none;
        }
        .tabs::-webkit-scrollbar { display: none; }
        .tab-btn { 
            flex: 1;
            background: transparent; 
            border: none; 
            color: #888; 
            padding: 14px 10px; 
            cursor: pointer; 
            font-size: 0.85rem; 
            border-bottom: 3px solid transparent;
            white-space: nowrap;
            min-width: 80px;
        }
        .tab-btn.active { color: #ffd700; border-bottom-color: #ffd700; font-weight: bold; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Stats */
        .stats-box {
            background: linear-gradient(135deg, #0a0a0a, #1a1a2e); 
            padding: 20px; 
            border-radius: 12px; 
            margin: 15px 0;
            border: 1px solid #333;
        }
        .stat-row {
            display: flex; 
            justify-content: space-between; 
            padding: 12px 0;
            border-bottom: 1px solid #222; 
            font-size: 1rem;
            align-items: center;
        }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #aaa; }
        .stat-value { color: #ffd700; font-weight: bold; font-size: 1.2rem; }
        .stat-value.negative { color: #e74c3c; }
        .stat-value.positive { color: #27ae60; }
        
        /* Tablas */
        .table-container {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin: 15px 0;
            border-radius: 8px;
            border: 1px solid #333;
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            font-size: 0.85rem; 
            min-width: 300px;
        }
        th, td { 
            padding: 12px 8px; 
            text-align: left; 
            border-bottom: 1px solid #333; 
            white-space: nowrap;
        }
        th { 
            background: linear-gradient(135deg, #ffd700, #ffed4e); 
            color: black; 
            font-weight: bold;
            position: sticky;
            top: 0;
        }
        tr:hover { background: rgba(255,215,0,0.05); }
        
        /* Formularios */
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; color: #888; font-size: 0.9rem; margin-bottom: 6px; }
        .form-group input, .form-group select {
            width: 100%; padding: 12px; background: #000; border: 1px solid #444;
            color: white; border-radius: 8px; font-size: 1rem;
            -webkit-appearance: none;
        }
        .btn-consultar {
            background: linear-gradient(135deg, #27ae60, #229954); 
            color: white; 
            border: none; 
            padding: 14px;
            width: 100%; 
            border-radius: 8px; 
            font-weight: bold; 
            cursor: pointer;
            margin-top: 10px;
            font-size: 1rem;
        }
        
        /* Alertas */
        .alert-box {
            background: rgba(243, 156, 18, 0.15); 
            border: 1px solid #f39c12;
            padding: 15px; 
            border-radius: 8px; 
            margin: 15px 0; 
            font-size: 0.9rem;
        }
        .alert-box strong { color: #f39c12; }

        /* Resultados */
        .resultado-item {
            background: #0a0a0a;
            padding: 15px;
            margin: 8px 0;
            border-radius: 10px;
            border-left: 4px solid #27ae60;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .resultado-item.pendiente {
            border-left-color: #666;
            opacity: 0.7;
        }
        .resultado-numero {
            color: #ffd700;
            font-weight: bold;
            font-size: 1.4rem;
        }
        .resultado-nombre {
            color: #aaa;
            font-size: 1rem;
        }
        
        /* Toast Notification */
        .toast-notification {
            position: fixed;
            top: 80px;
            left: 50%;
            transform: translateX(-50%);
            padding: 14px 24px;
            border-radius: 30px;
            font-size: 0.95rem;
            z-index: 10000;
            box-shadow: 0 6px 20px rgba(0,0,0,0.5);
            max-width: 90%;
            text-align: center;
            font-weight: bold;
            animation: slideDown 0.3s ease;
        }
        @keyframes slideDown {
            from { transform: translateX(-50%) translateY(-20px); opacity: 0; }
            to { transform: translateX(-50%) translateY(0); opacity: 1; }
        }
        @keyframes slideUp {
            from { transform: translateX(-50%) translateY(0); opacity: 1; }
            to { transform: translateX(-50%) translateY(-20px); opacity: 0; }
        }
        
        /* Calculadora en modal */
        .calc-result {
            background: rgba(255,215,0,0.1);
            border: 2px solid #ffd700;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            margin-top: 20px;
        }
        .calc-result h4 {
            color: #ffd700;
            font-size: 1.5rem;
            margin: 0;
        }
        
        /* Ticket item en listado */
        .ticket-item {
            background: #0a0a0a;
            padding: 15px;
            margin: 8px 0;
            border-radius: 10px;
            border-left: 4px solid #2980b9;
        }
        .ticket-item.ganador {
            border-left-color: #27ae60;
            background: rgba(39,174,96,0.1);
        }
        .ticket-serial {
            color: #ffd700;
            font-weight: bold;
            font-size: 1.1rem;
        }
        .ticket-info {
            color: #888;
            font-size: 0.85rem;
            margin-top: 5px;
        }
        .ticket-premio {
            color: #27ae60;
            font-weight: bold;
            font-size: 1.2rem;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <!-- MENU DESKTOP - WINDOWS FORMS STYLE -->
    <div class="win-menu-bar">
        <div class="win-menu-header">
            <div class="win-title">🦁 {{agencia}}</div>
            <button onclick="location.href='/logout'" style="background: #c0392b; color: white; border: none; padding: 6px 15px; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 0.8rem;">SALIR</button>
        </div>
        <ul class="win-menu-items">
            <li class="win-menu-item">
                <a>📁 Archivo</a>
                <ul class="win-submenu">
                    <li class="win-submenu-item"><a onclick="abrirCaja()">💰 Caja del Día</a></li>
                    <li class="win-submenu-item"><a onclick="abrirCajaHistorico()">📊 Historial de Caja</a></li>
                    <li class="win-submenu-item"><a onclick="abrirCalculadora()">🧮 Calculadora de Premios</a></li>
                </ul>
            </li>
            <li class="win-menu-item">
                <a>🔍 Consultas</a>
                <ul class="win-submenu">
                    <li class="win-submenu-item"><a onclick="verResultados()">📋 Resultados de Hoy</a></li>
                    <li class="win-submenu-item"><a onclick="abrirMisTicketsPendientes()">🎫 Mis Tickets Pendientes</a></li>
                    <li class="win-submenu-item"><a onclick="verificarTicket()">🔎 Verificar Ticket</a></li>
                </ul>
            </li>
            <li class="win-menu-item">
                <a>❓ Ayuda</a>
                <ul class="win-submenu">
                    <li class="win-submenu-item"><a onclick="mostrarReglas()">📖 Reglas de Pago</a></li>
                    <li class="win-submenu-item"><a onclick="mostrarComoUsar()">❓ Cómo Usar</a></li>
                    <li class="win-submenu-item"><a onclick="mostrarAcerca()">ℹ️ Acerca del Sistema</a></li>
                </ul>
            </li>
        </ul>
    </div>

    <!-- MENU MOBIL - HAMBURGER -->
    <div class="mobile-header">
        <div class="mobile-title">🦁 {{agencia}}</div>
        <button class="hamburger-btn" onclick="toggleMobileMenu()">☰</button>
    </div>
    
    <div class="mobile-menu-overlay" onclick="toggleMobileMenu()"></div>
    <div class="mobile-menu" id="mobileMenu">
        <div class="mobile-menu-header">
            <div class="mobile-menu-title">MENÚ</div>
            <button class="close-menu-btn" onclick="toggleMobileMenu()">×</button>
        </div>
        
        <div class="mobile-menu-section">
            <div class="mobile-menu-section-title">📁 Archivo</div>
            <div class="mobile-menu-item" onclick="abrirCajaMobile()">💰 Caja del Día</div>
            <div class="mobile-menu-item" onclick="abrirCajaHistoricoMobile()">📊 Historial de Caja</div>
            <div class="mobile-menu-item" onclick="abrirCalculadoraMobile()">🧮 Calculadora</div>
        </div>
        
        <div class="mobile-menu-section">
            <div class="mobile-menu-section-title">🔍 Consultas</div>
            <div class="mobile-menu-item" onclick="verResultadosMobile()">📋 Resultados</div>
            <div class="mobile-menu-item" onclick="abrirMisTicketsPendientesMobile()">🎫 Tickets Pendientes</div>
            <div class="mobile-menu-item" onclick="verificarTicketMobile()">🔎 Verificar Ticket</div>
        </div>
        
        <div class="mobile-menu-section">
            <div class="mobile-menu-section-title">❓ Ayuda</div>
            <div class="mobile-menu-item" onclick="mostrarReglasMobile()">📖 Reglas</div>
            <div class="mobile-menu-item" onclick="mostrarComoUsarMobile()">❓ Cómo Usar</div>
            <div class="mobile-menu-item" onclick="mostrarAcercaMobile()">ℹ️ Acerca de</div>
        </div>
        
        <div class="mobile-menu-section">
            <div class="mobile-menu-item" onclick="location.href='/logout'" style="color: #e74c3c; font-weight: bold;">🚪 Cerrar Sesión</div>
        </div>
    </div>

    <!-- Header original -->
    <div class="header">
        <div class="header-info">
            <h3>{{agencia}}</h3>
            <p id="reloj">--</p>
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
                <div style="text-align:center; color:#666; padding:20px; font-style:italic;">
                    Selecciona animales y horarios...
                </div>
            </div>
            <div class="action-btns">
                <button class="btn-agregar" onclick="agregar()">AGREGAR AL TICKET</button>
                <button class="btn-vender" onclick="vender()">ENVIAR POR WHATSAPP</button>
                <button class="btn-resultados" onclick="verResultados()">RESULTADOS</button>
                <button class="btn-caja" onclick="abrirCaja()">CAJA</button>
                <button class="btn-pagar" onclick="pagar()">PAGAR</button>
                <button class="btn-anular" onclick="anular()">ANULAR</button>
                <button class="btn-borrar" onclick="borrarTodo()">BORRAR TODO</button>
                <button class="btn-salir" onclick="location.href='/logout'">CERRAR SESIÓN</button>
            </div>
        </div>
    </div>

    <!-- MODAL CAJA -->
    <div class="modal" id="modal-caja">
        <div class="modal-content">
            <div class="modal-header">
                <h3>ESTADO DE CAJA</h3>
                <button class="btn-close" onclick="cerrarModal('modal-caja')">X</button>
            </div>
            
            <div class="tabs">
                <button class="tab-btn active" onclick="switchTab('hoy')">Hoy</button>
                <button class="tab-btn" onclick="switchTab('historico')">Histórico</button>
            </div>

            <div id="tab-hoy" class="tab-content active">
                <div class="stats-box">
                    <div class="stat-row">
                        <span class="stat-label">Ventas:</span>
                        <span class="stat-value" id="caja-ventas">S/0.00</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Premios Pagados:</span>
                        <span class="stat-value negative" id="caja-premios">S/0.00</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Tu Comisión:</span>
                        <span class="stat-value" id="caja-comision">S/0.00</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Balance:</span>
                        <span class="stat-value" id="caja-balance">S/0.00</span>
                    </div>
                </div>
                
                <div id="alerta-pendientes" class="alert-box" style="display:none;">
                    <strong>⚠️ Tickets por Cobrar:</strong>
                    <div id="info-pendientes"></div>
                </div>
            </div>

            <div id="tab-historico" class="tab-content">
                <div class="form-group">
                    <label>Desde:</label>
                    <input type="date" id="hist-fecha-inicio">
                </div>
                <div class="form-group">
                    <label>Hasta:</label>
                    <input type="date" id="hist-fecha-fin">
                </div>
                <button class="btn-consultar" onclick="consultarHistoricoCaja()">CONSULTAR HISTORIAL</button>
                
                <div id="resultado-historico" style="display:none; margin-top: 20px;">
                    <div class="stats-box">
                        <div class="stat-row">
                            <span class="stat-label">Total Ventas:</span>
                            <span class="stat-value" id="hist-ventas">S/0.00</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Total Premios:</span>
                            <span class="stat-value negative" id="hist-premios">S/0.00</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Balance:</span>
                            <span class="stat-value" id="hist-balance">S/0.00</span>
                        </div>
                    </div>

                    <div class="table-container" style="max-height: 250px; overflow-y: auto; margin-top: 15px;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Fecha</th>
                                    <th>Tickets</th>
                                    <th>Ventas</th>
                                    <th>Balance</th>
                                </tr>
                            </thead>
                            <tbody id="tabla-historico-caja"></tbody>
                        </table>
                    </div>

                    <div id="hist-alerta-pendientes" class="alert-box" style="display:none;">
                        <strong>💰 Pendiente por Cobrar:</strong>
                        <div id="hist-info-pendientes"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- MODAL RESULTADOS -->
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

            <div style="margin-bottom: 15px; text-align: center; color: #ffd700; font-size: 1.1rem; font-weight: bold;" id="resultados-fecha-titulo">
                Hoy
            </div>

            <div id="lista-resultados" style="max-height: 400px; overflow-y: auto;">
                <p style="color: #888; text-align: center; padding: 20px;">Seleccione una fecha...</p>
            </div>
        </div>
    </div>

    <!-- MODAL CALCULADORA -->
    <div class="modal" id="modal-calculadora">
        <div class="modal-content">
            <div class="modal-header">
                <h3>🧮 CALCULADORA DE PREMIOS</h3>
                <button class="btn-close" onclick="cerrarModal('modal-calculadora')">X</button>
            </div>
            
            <div class="form-group">
                <label>Monto Apostado (S/):</label>
                <input type="number" id="calc-monto" value="10" min="1">
            </div>
            
            <div class="form-group">
                <label>Tipo de Apuesta:</label>
                <select id="calc-tipo" onchange="calcularPremio()">
                    <option value="35">Animal Normal (00-39) x35</option>
                    <option value="70">Lechuza (40) x70</option>
                    <option value="2">Especial (Rojo/Negro/Par/Impar) x2</option>
                </select>
            </div>
            
            <button class="btn-consultar" onclick="calcularPremio()">CALCULAR</button>
            
            <div class="calc-result" id="calc-resultado" style="display: none;">
                <div style="color: #888; font-size: 0.9rem; margin-bottom: 5px;">Premio a Pagar:</div>
                <h4 id="calc-total">S/0.00</h4>
            </div>
        </div>
    </div>

    <!-- MODAL MIS TICKETS PENDIENTES -->
    <div class="modal" id="modal-pendientes">
        <div class="modal-content">
            <div class="modal-header">
                <h3>🎫 MIS TICKETS PENDIENTES</h3>
                <button class="btn-close" onclick="cerrarModal('modal-pendientes')">X</button>
            </div>
            
            <div id="pendientes-info" style="margin-bottom: 15px; color: #ffd700; font-weight: bold; text-align: center;">
                Cargando...
            </div>
            
            <div id="lista-pendientes" style="max-height: 400px; overflow-y: auto;">
                <!-- Aquí se cargarán los tickets -->
            </div>
        </div>
    </div>

    <!-- MODAL REGLAS -->
    <div class="modal" id="modal-reglas">
        <div class="modal-content">
            <div class="modal-header">
                <h3>📖 REGLAS DE PAGO</h3>
                <button class="btn-close" onclick="cerrarModal('modal-reglas')">X</button>
            </div>
            
            <div style="line-height: 2; color: #ddd;">
                <h4 style="color: #ffd700; margin: 15px 0;">🎯 Animales (00-39)</h4>
                <ul style="margin-left: 20px; margin-bottom: 20px;">
                    <li>Pago: <strong style="color: #27ae60;">x35</strong> veces el monto apostado</li>
                    <li>Ejemplo: S/10 → S/350</li>
                </ul>
                
                <h4 style="color: #ffd700; margin: 15px 0;">🦉 Lechuza (40)</h4>
                <ul style="margin-left: 20px; margin-bottom: 20px;">
                    <li>Pago: <strong style="color: #e74c3c;">x70</strong> veces el monto apostado</li>
                    <li>Ejemplo: S/10 → S/700</li>
                </ul>
                
                <h4 style="color: #ffd700; margin: 15px 0;">🎲 Especiales</h4>
                <ul style="margin-left: 20px; margin-bottom: 20px;">
                    <li>Rojo, Negro, Par, Impar</li>
                    <li>Pago: <strong style="color: #2980b9;">x2</strong> veces el monto</li>
                </ul>
                
                <h4 style="color: #ffd700; margin: 15px 0;">⚠️ Importante</h4>
                <ul style="margin-left: 20px;">
                    <li>Anular: Solo dentro de 5 minutos</li>
                    <li>Bloqueo: 5 minutos antes del sorteo</li>
                    <li>Vencimiento: Tickets vencen a los 3 días</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- MODAL CÓMO USAR -->
    <div class="modal" id="modal-como-usar">
        <div class="modal-content">
            <div class="modal-header">
                <h3>❓ CÓMO USAR EL SISTEMA</h3>
                <button class="btn-close" onclick="cerrarModal('modal-como-usar')">X</button>
            </div>
            
            <div style="line-height: 1.8; color: #ddd;">
                <div style="background: rgba(255,215,0,0.1); padding: 15px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #ffd700;">
                    <h4 style="color: #ffd700; margin-bottom: 10px;">1. Hacer una Venta</h4>
                    <ol style="margin-left: 20px; color: #aaa;">
                        <li>Selecciona el monto (arriba a la derecha)</li>
                        <li>Toca los animales que quieres jugar</li>
                        <li>Selecciona los horarios (puedes varios)</li>
                        <li>Presiona "AGREGAR AL TICKET"</li>
                        <li>Repite si quieres más jugadas</li>
                        <li>Presiona "ENVIAR POR WHATSAPP"</li>
                    </ol>
                </div>
                
                <div style="background: rgba(39,174,96,0.1); padding: 15px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #27ae60;">
                    <h4 style="color: #27ae60; margin-bottom: 10px;">2. Pagar un Ticket Ganador</h4>
                    <ol style="margin-left: 20px; color: #aaa;">
                        <li>Presiona el botón PAGAR</li>
                        <li>Ingresa el SERIAL del ticket</li>
                        <li>Verifica el monto ganado</li>
                        <li>Confirma el pago</li>
                    </ol>
                </div>
                
                <div style="background: rgba(192,57,43,0.1); padding: 15px; border-radius: 10px; border-left: 4px solid #c0392b;">
                    <h4 style="color: #c0392b; margin-bottom: 10px;">3. Anular un Ticket</h4>
                    <ol style="margin-left: 20px; color: #aaa;">
                        <li>Solo puedes anular dentro de 5 minutos</li>
                        <li>Presiona ANULAR e ingresa el serial</li>
                        <li>No se pueden anular tickets pagados</li>
                    </ol>
                </div>
            </div>
        </div>
    </div>

    <!-- MODAL ACERCA DE -->
    <div class="modal" id="modal-acerca">
        <div class="modal-content" style="text-align: center;">
            <div class="modal-header">
                <h3>ℹ️ ACERCA DEL SISTEMA</h3>
                <button class="btn-close" onclick="cerrarModal('modal-acerca')">X</button>
            </div>
            
            <div style="padding: 20px;">
                <div style="font-size: 4rem; margin-bottom: 20px;">🦁</div>
                <h2 style="color: #ffd700; margin-bottom: 10px;">ZOOLO CASINO</h2>
                <p style="color: #888; font-size: 1.2rem; margin-bottom: 20px;">Versión 5.8</p>
                
                <div style="background: rgba(255,215,0,0.1); padding: 20px; border-radius: 10px; border: 1px solid rgba(255,215,0,0.3); margin-top: 20px;">
                    <p style="color: #ffd700; margin: 0; line-height: 1.8;">
                        Sistema de Lotería Animal<br>
                        Desarrollado para Agencias<br><br>
                        <strong>Características:</strong><br>
                        ✓ Menú Windows Forms<br>
                        ✓ Gestión de Tickets<br>
                        ✓ Cálculo Automático<br>
                        ✓ Resultados en Vivo
                    </p>
                </div>
                
                <p style="color: #666; margin-top: 20px; font-size: 0.9rem;">
                    © 2025 ZOOLO CASINO<br>
                    Todos los derechos reservados
                </p>
            </div>
        </div>
    </div>

    <script>
        let seleccionados = [], especiales = [], horariosSel = [], carrito = [];
        let horasPeru = {{horarios_peru|tojson}};
        let horasVen = {{horarios_venezuela|tojson}};
        
        // Toggle mobile menu
        function toggleMobileMenu() {
            const menu = document.getElementById('mobileMenu');
            const overlay = document.querySelector('.mobile-menu-overlay');
            menu.classList.toggle('active');
            overlay.classList.toggle('active');
        }
        
        // Funciones para menú móvil
        function abrirCajaMobile() { toggleMobileMenu(); abrirCaja(); }
        function abrirCajaHistoricoMobile() { toggleMobileMenu(); abrirCajaHistorico(); }
        function abrirCalculadoraMobile() { toggleMobileMenu(); abrirCalculadora(); }
        function verResultadosMobile() { toggleMobileMenu(); verResultados(); }
        function abrirMisTicketsPendientesMobile() { toggleMobileMenu(); abrirMisTicketsPendientes(); }
        function verificarTicketMobile() { toggleMobileMenu(); verificarTicket(); }
        function mostrarReglasMobile() { toggleMobileMenu(); mostrarReglas(); }
        function mostrarComoUsarMobile() { toggleMobileMenu(); mostrarComoUsar(); }
        function mostrarAcercaMobile() { toggleMobileMenu(); mostrarAcerca(); }
        
        function showToast(message, type = 'info') {
            const existing = document.querySelector('.toast-notification');
            if (existing) existing.remove();
            
            const toast = document.createElement('div');
            toast.className = 'toast-notification';
            toast.style.background = type === 'error' ? '#c0392b' : type === 'success' ? '#27ae60' : '#2980b9';
            toast.style.color = 'white';
            toast.textContent = message;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.animation = 'slideUp 0.3s ease';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        function updateReloj() {
            let now = new Date();
            let peruTime = new Date(now.toLocaleString("en-US", {timeZone: "America/Lima"}));
            document.getElementById('reloj').textContent = peruTime.toLocaleString('es-PE', {hour: '2-digit', minute:'2-digit', hour12: true});
            
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
                if (btn && horaActual > sorteoMinutos - 5) {
                    btn.classList.add('expired');
                }
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
                if (navigator.vibrate) navigator.vibrate(50);
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
            if (btn.classList.contains('expired')) {
                showToast('Este sorteo ya cerró', 'error');
                return;
            }
            let idx = horariosSel.indexOf(hora);
            if (idx >= 0) {
                horariosSel.splice(idx, 1);
                btn.classList.remove('active');
            } else {
                horariosSel.push(hora);
                btn.classList.add('active');
            }
            updateTicket();
        }
        
        function updateTicket() {
            const display = document.getElementById('ticket-display');
            let total = 0;
            let html = '<table class="ticket-table"><thead><tr><th>Hora</th><th>Apuesta</th><th>S/</th></tr></thead><tbody>';
            
            for (let item of carrito) {
                let nom = item.tipo === 'animal' ? item.nombre.substring(0,10) : item.seleccion;
                let color = item.tipo === 'animal' ? '#ffd700' : '#3498db';
                html += `<tr>
                    <td style="color:#aaa; font-size:0.75rem">${item.hora}</td>
                    <td style="color:${color}; font-weight:bold; font-size:0.8rem">${item.seleccion} ${nom}</td>
                    <td style="text-align:right; font-weight:bold">${item.monto}</td>
                </tr>`;
                total += item.monto;
            }
            
            if (horariosSel.length > 0 && (seleccionados.length > 0 || especiales.length > 0)) {
                let monto = parseFloat(document.getElementById('monto').value) || 5;
                for (let h of horariosSel) {
                    for (let a of seleccionados) {
                        let indicador = a.k === "40" ? " 🦉x70" : "";
                        html += `<tr style="opacity:0.7; background:rgba(255,215,0,0.1)">
                            <td style="color:#ffd700; font-size:0.75rem">${h}</td>
                            <td style="color:#ffd700; font-size:0.8rem">${a.k} ${a.nombre}${indicador}</td>
                            <td style="text-align:right; color:#ffd700; font-weight:bold">${monto}</td>
                        </tr>`;
                    }
                    for (let e of especiales) {
                        html += `<tr style="opacity:0.7; background:rgba(52,152,219,0.1)">
                            <td style="color:#3498db; font-size:0.75rem">${h}</td>
                            <td style="color:#3498db; font-size:0.8rem">${e}</td>
                            <td style="text-align:right; color:#3498db; font-weight:bold">${monto}</td>
                        </tr>`;
                    }
                }
            }
            
            html += '</tbody></table>';
            
            if (carrito.length === 0 && (seleccionados.length === 0 && especiales.length === 0)) {
                html = '<div style="text-align:center; color:#666; padding:20px; font-style:italic;">Selecciona animales y horarios...</div>';
            } else if (carrito.length === 0) {
                html += '<div style="text-align:center; color:#888; padding:15px; font-size:0.85rem; background:rgba(255,215,0,0.05); border-radius:8px; margin-top:10px;">👆 Presiona AGREGAR para confirmar las selecciones</div>';
            }
            
            if (total > 0) {
                html += `<div class="ticket-total">TOTAL: S/${total}</div>`;
            }
            
            display.innerHTML = html;
        }
        
        function agregar() {
            if (horariosSel.length === 0 || (seleccionados.length === 0 && especiales.length === 0)) {
                showToast('Selecciona horario y animal/especial', 'error'); 
                return;
            }
            let monto = parseFloat(document.getElementById('monto').value) || 5;
            let count = 0;
            for (let h of horariosSel) {
                for (let a of seleccionados) {
                    carrito.push({hora: h, seleccion: a.k, nombre: a.nombre, monto: monto, tipo: 'animal'});
                    count++;
                }
                for (let e of especiales) {
                    carrito.push({hora: h, seleccion: e, nombre: e, monto: monto, tipo: 'especial'});
                    count++;
                }
            }
            seleccionados = []; especiales = []; horariosSel = [];
            document.querySelectorAll('.animal-card.active, .btn-esp.active, .btn-hora.active').forEach(el => el.classList.remove('active'));
            updateTicket();
            showToast(`${count} jugada(s) agregada(s)`, 'success');
        }
        
        async function vender() {
            if (carrito.length === 0) { 
                showToast('Carrito vacío', 'error'); 
                return; 
            }
            
            const btn = document.querySelector('.btn-vender');
            const originalText = btn.innerHTML;
            btn.innerHTML = '⏳ Procesando...';
            btn.disabled = true;
            
            try {
                let jugadas = carrito.map(c => ({
                    hora: c.hora, 
                    seleccion: c.seleccion, 
                    monto: c.monto, 
                    tipo: c.tipo
                }));
                
                const response = await fetch('/api/procesar-venta', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({jugadas: jugadas})
                });
                
                const data = await response.json();
                
                if (data.error) {
                    showToast(data.error, 'error');
                } else {
                    if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
                        window.location.href = data.url_whatsapp;
                    } else {
                        window.open(data.url_whatsapp, '_blank');
                    }
                    carrito = []; 
                    updateTicket();
                    showToast('¡Ticket generado! Redirigiendo a WhatsApp...', 'success');
                }
            } catch (e) {
                showToast('Error de conexión. Intenta de nuevo.', 'error');
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
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
            
            let fechaObj = new Date(fecha + 'T00:00:00');
            let opciones = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
            document.getElementById('resultados-fecha-titulo').textContent = fechaObj.toLocaleDateString('es-PE', opciones);
            
            fetch('/api/resultados-fecha', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha: fecha})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error: ' + d.error + '</p>';
                    return;
                }
                
                let html = '';
                if (d.resultados && Object.keys(d.resultados).length > 0) {
                    for (let hora of horasPeru) {
                        let resultado = d.resultados[hora];
                        let clase = resultado ? '' : 'pendiente';
                        let contenido;
                        
                        if (resultado) {
                            contenido = `
                                <span class="resultado-numero">${resultado.animal}</span>
                                <span class="resultado-nombre">${resultado.nombre}</span>
                            `;
                        } else {
                            contenido = `
                                <span style="color: #666; font-size:1.1rem">Pendiente</span>
                                <span style="color: #444; font-size: 0.85rem;">Sin resultado</span>
                            `;
                        }
                        
                        html += `
                            <div class="resultado-item ${clase}">
                                <div style="display: flex; flex-direction: column;">
                                    <strong style="color: #ffd700; font-size: 1rem;">${hora}</strong>
                                    <small style="color: #666; font-size: 0.75rem;">Venezuela: ${horasVen[horasPeru.indexOf(hora)]}</small>
                                </div>
                                <div style="text-align: right; display: flex; flex-direction: column; align-items: flex-end;">
                                    ${contenido}
                                </div>
                            </div>
                        `;
                    }
                } else {
                    html = '<p style="color: #888; text-align: center; padding: 20px;">No hay resultados disponibles para esta fecha</p>';
                }
                container.innerHTML = html;
            })
            .catch(e => {
                container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexión</p>';
            });
        }

        function cerrarModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }
        
        // Funciones del menú Archivo
        function abrirCaja() {
            fetch('/api/caja')
            .then(r => r.json())
            .then(d => {
                if (d.error) { 
                    showToast(d.error, 'error'); 
                    return; 
                }
                document.getElementById('caja-ventas').textContent = 'S/' + d.ventas.toFixed(2);
                document.getElementById('caja-premios').textContent = 'S/' + d.premios.toFixed(2);
                document.getElementById('caja-comision').textContent = 'S/' + d.comision.toFixed(2);
                
                let balanceEl = document.getElementById('caja-balance');
                balanceEl.textContent = 'S/' + d.balance.toFixed(2);
                balanceEl.className = 'stat-value ' + (d.balance >= 0 ? 'positive' : 'negative');
                
                let alertaDiv = document.getElementById('alerta-pendientes');
                let infoDiv = document.getElementById('info-pendientes');
                if (d.tickets_pendientes > 0) {
                    alertaDiv.style.display = 'block';
                    infoDiv.innerHTML = `Tienes <strong>${d.tickets_pendientes}</strong> ticket(s) ganador(es) sin cobrar.<br>¡Pasa a pagar!`;
                } else {
                    alertaDiv.style.display = 'none';
                }
                
                document.getElementById('modal-caja').style.display = 'block';
            })
            .catch(e => showToast('Error de conexión', 'error'));
            
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('hist-fecha-inicio').value = hoy;
            document.getElementById('hist-fecha-fin').value = hoy;
        }
        
        function abrirCajaHistorico() {
            abrirCaja();
            setTimeout(() => switchTab('historico'), 100);
        }
        
        function abrirCalculadora() {
            document.getElementById('modal-calculadora').style.display = 'block';
            calcularPremio();
        }
        
        function calcularPremio() {
            const monto = parseFloat(document.getElementById('calc-monto').value) || 0;
            const multiplicador = parseInt(document.getElementById('calc-tipo').value);
            const total = monto * multiplicador;
            
            document.getElementById('calc-total').textContent = 'S/' + total.toFixed(2);
            document.getElementById('calc-resultado').style.display = 'block';
        }
        
        // Funciones del menú Consultas
        function abrirMisTicketsPendientes() {
            document.getElementById('modal-pendientes').style.display = 'block';
            document.getElementById('lista-pendientes').innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Cargando...</p>';
            
            fetch('/api/mis-tickets-pendientes')
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    document.getElementById('lista-pendientes').innerHTML = '<p style="color: #c0392b; text-align: center;">Error: ' + d.error + '</p>';
                    return;
                }
                
                document.getElementById('pendientes-info').innerHTML = 
                    `Total Pendiente: <span style="color: #27ae60; font-size: 1.3rem;">S/${d.total_pendiente.toFixed(2)}</span> (${d.tickets.length} tickets)`;
                
                if (d.tickets.length === 0) {
                    document.getElementById('lista-pendientes').innerHTML = 
                        '<p style="color: #888; text-align: center; padding: 20px;">No tienes tickets pendientes por cobrar</p>';
                    return;
                }
                
                let html = '';
                d.tickets.forEach(t => {
                    html += `
                        <div class="ticket-item ganador">
                            <div class="ticket-serial">#${t.serial}</div>
                            <div class="ticket-info">Fecha: ${t.fecha} • Jugadas: ${t.jugadas} • Apostado: S/${t.total}</div>
                            <div class="ticket-premio">💰 Ganancia: S/${t.premio.toFixed(2)}</div>
                        </div>
                    `;
                });
                document.getElementById('lista-pendientes').innerHTML = html;
            })
            .catch(e => {
                document.getElementById('lista-pendientes').innerHTML = '<p style="color: #c0392b; text-align: center;">Error de conexión</p>';
            });
        }
        
        function verificarTicket() {
            let serial = prompt('Ingrese el SERIAL del ticket a verificar:');
            if (!serial) return;
            
            fetch('/api/verificar-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    showToast(d.error, 'error');
                } else {
                    let msg = `Ticket #${d.ticket_id}\\n`;
                    msg += `Total Ganado: S/${d.total_ganado.toFixed(2)}\\n\\n`;
                    msg += 'Detalles:\\n';
                    d.detalles.forEach(det => {
                        let status = det.gano ? '✅ GANÓ' : '❌ No ganó';
                        msg += `${det.hora}: ${det.sel} - ${status}`;
                        if (det.gano) msg += ` S/${det.premio.toFixed(2)}`;
                        msg += '\\n';
                    });
                    alert(msg);
                }
            })
            .catch(e => showToast('Error de conexión', 'error'));
        }
        
        // Funciones del menú Ayuda
        function mostrarReglas() {
            document.getElementById('modal-reglas').style.display = 'block';
        }
        
        function mostrarComoUsar() {
            document.getElementById('modal-como-usar').style.display = 'block';
        }
        
        function mostrarAcerca() {
            document.getElementById('modal-acerca').style.display = 'block';
        }
        
        // Funciones existentes...
        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active');
        }
        
        function consultarHistoricoCaja() {
            let inicio = document.getElementById('hist-fecha-inicio').value;
            let fin = document.getElementById('hist-fecha-fin').value;
            
            if (!inicio || !fin) {
                showToast('Seleccione ambas fechas', 'error');
                return;
            }
            
            fetch('/api/caja-historico', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    showToast(d.error, 'error');
                    return;
                }
                
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
                    html += `<tr>
                        <td>${dia.fecha}</td>
                        <td>${dia.tickets}</td>
                        <td>S/${dia.ventas.toFixed(0)}</td>
                        <td style="color:${color}; font-weight:bold">S/${dia.balance.toFixed(0)}</td>
                    </tr>`;
                });
                tbody.innerHTML = html;
                
                let alertaDiv = document.getElementById('hist-alerta-pendientes');
                let infoDiv = document.getElementById('hist-info-pendientes');
                if (d.totales.tickets_pendientes_cobro > 0) {
                    alertaDiv.style.display = 'block';
                    infoDiv.innerHTML = `${d.totales.tickets_pendientes_cobro} ticket(s) sin cobrar por <strong>S/${d.totales.total_pendiente_cobro.toFixed(2)}</strong>`;
                } else {
                    alertaDiv.style.display = 'none';
                }
            })
            .catch(e => showToast('Error de conexión', 'error'));
        }
        
        async function pagar() {
            let serial = prompt('Ingrese SERIAL del ticket:'); 
            if (!serial) return;
            
            try {
                const response = await fetch('/api/verificar-ticket', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({serial: serial})
                });
                const d = await response.json();
                
                if (d.error) { 
                    showToast(d.error, 'error'); 
                    return; 
                }
                
                let msg = "=== RESULTADO ===\\n\\n";
                let total = d.total_ganado;
                
                for (let det of d.detalles) {
                    let premioTxt = det.gano ? ('S/' + det.premio.toFixed(2)) : 'No';
                    let especial = det.es_lechuza ? ' 🦉x70!' : '';
                    msg += det.hora + " | " + det.sel + " -> " + premioTxt + especial + "\\n";
                }
                
                msg += "\\nTOTAL GANADO: S/" + total.toFixed(2);
                
                if (total > 0 && confirm(msg + "\\n\\n¿CONFIRMA PAGO?")) {
                    await fetch('/api/pagar-ticket', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ticket_id: d.ticket_id})
                    });
                    showToast('✅ Ticket pagado correctamente', 'success');
                } else if (total === 0) {
                    showToast('Ticket no ganador', 'info');
                }
            } catch (e) {
                showToast('Error de conexión', 'error');
            }
        }
        
        async function anular() {
            let serial = prompt('SERIAL a anular:'); 
            if (!serial) return;
            if (!confirm('¿ANULAR ' + serial + '?')) return;
            
            try {
                const response = await fetch('/api/anular-ticket', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({serial: serial})
                });
                const d = await response.json();
                
                if (d.error) {
                    showToast(d.error, 'error');
                } else {
                    showToast('✅ ' + d.mensaje, 'success');
                }
            } catch (e) {
                showToast('Error de conexión', 'error');
            }
        }
        
        function borrarTodo() {
            if (carrito.length > 0 || seleccionados.length > 0 || especiales.length > 0 || horariosSel.length > 0) {
                if (!confirm('¿Borrar todo?')) return;
            }
            seleccionados = []; especiales = []; horariosSel = []; carrito = [];
            document.querySelectorAll('.active').forEach(el => el.classList.remove('active'));
            updateTicket();
            showToast('Ticket limpiado', 'info');
        }
        
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', function(e) {
                if (e.target === this) this.style.display = 'none';
            });
        });
        
        document.addEventListener('DOMContentLoaded', function() {
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('hist-fecha-inicio').value = hoy;
            document.getElementById('hist-fecha-fin').value = hoy;
            document.getElementById('resultados-fecha').value = hoy;
        });
    </script>
</body>
</html>
'''

ADMIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
    <title>Panel Admin - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { 
            background: #0a0a0a; 
            color: white; 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.5;
        }
        
        /* ==========================================
           MENU WINDOWS FORMS - DESKTOP (Horizontal)
           ========================================== */
        .win-menu-bar {
            background: linear-gradient(180deg, #2d2d2d 0%, #1a1a1a 100%);
            border-bottom: 2px solid #000;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        
        .win-menu-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 15px;
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            border-bottom: 1px solid #000;
        }
        
        .win-title {
            color: #ffd700;
            font-size: 1.1rem;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .win-menu-items {
            display: flex;
            list-style: none;
            padding: 0;
            margin: 0;
            background: #2d2d2d;
        }
        
        .win-menu-item {
            position: relative;
        }
        
        .win-menu-item > a {
            display: block;
            padding: 10px 20px;
            color: #fff;
            text-decoration: none;
            font-size: 0.9rem;
            border-right: 1px solid #444;
            transition: all 0.2s;
            cursor: pointer;
        }
        
        .win-menu-item:hover > a {
            background: linear-gradient(180deg, #404040 0%, #333 100%);
            color: #ffd700;
        }
        
        .win-submenu {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            background: #2d2d2d;
            border: 1px solid #555;
            border-top: none;
            min-width: 220px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            z-index: 1001;
        }
        
        .win-menu-item:hover .win-submenu {
            display: block;
        }
        
        .win-submenu-item {
            border-bottom: 1px solid #444;
        }
        
        .win-submenu-item:last-child {
            border-bottom: none;
        }
        
        .win-submenu-item a {
            display: block;
            padding: 12px 20px;
            color: #ddd;
            text-decoration: none;
            font-size: 0.85rem;
            transition: all 0.2s;
            cursor: pointer;
        }
        
        .win-submenu-item a:hover {
            background: #ffd700;
            color: #000;
            padding-left: 25px;
        }
        
        .win-submenu-item a::before {
            content: "▸";
            margin-right: 8px;
            color: #888;
        }
        
        .win-submenu-item a:hover::before {
            color: #000;
        }
        
        /* ==========================================
           MENU HAMBURGER - MOBIL
           ========================================== */
        .mobile-header {
            display: none;
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 12px 15px;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #ffd700;
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        
        .mobile-title {
            color: #ffd700;
            font-size: 1.1rem;
            font-weight: bold;
        }
        
        .hamburger-btn {
            background: transparent;
            border: none;
            color: #ffd700;
            font-size: 1.5rem;
            cursor: pointer;
            padding: 5px;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .mobile-menu {
            display: none;
            position: fixed;
            top: 0;
            right: -300px;
            width: 280px;
            height: 100vh;
            background: linear-gradient(180deg, #1a1a2e 0%, #0a0a0a 100%);
            border-left: 2px solid #ffd700;
            z-index: 2000;
            transition: right 0.3s ease;
            overflow-y: auto;
        }
        
        .mobile-menu.active {
            right: 0;
        }
        
        .mobile-menu-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: rgba(0,0,0,0.3);
            border-bottom: 1px solid #333;
        }
        
        .mobile-menu-title {
            color: #ffd700;
            font-size: 1.1rem;
        }
        
        .close-menu-btn {
            background: #c0392b;
            border: none;
            color: white;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.1rem;
        }
        
        .mobile-menu-section {
            border-bottom: 1px solid #333;
        }
        
        .mobile-menu-section-title {
            background: rgba(255,215,0,0.1);
            color: #ffd700;
            padding: 12px 15px;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 1px solid #333;
        }
        
        .mobile-menu-item {
            padding: 15px;
            color: #fff;
            cursor: pointer;
            border-bottom: 1px solid #222;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.95rem;
        }
        
        .mobile-menu-item:active {
            background: rgba(255,215,0,0.1);
        }
        
        .mobile-menu-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 1999;
        }
        
        .mobile-menu-overlay.active {
            display: block;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .win-menu-bar {
                display: none;
            }
            .mobile-header {
                display: flex;
            }
            .mobile-menu {
                display: block;
            }
        }
        
        @media (min-width: 769px) {
            .mobile-menu, .mobile-menu-overlay {
                display: none !important;
            }
        }
        
        /* Contenido */
        .content { 
            padding: 20px; 
            max-width: 1200px; 
            margin: 0 auto; 
            padding-bottom: 30px;
        }
        
        .info-pago {
            background: linear-gradient(135deg, rgba(255,215,0,0.1), rgba(255,215,0,0.05)); 
            padding: 15px; 
            border-radius: 10px; 
            margin: 15px 0; 
            font-size: 0.85rem; 
            text-align: center;
            border: 1px solid rgba(255,215,0,0.3);
            color: #ffd700;
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid; 
            grid-template-columns: repeat(2, 1fr);
            gap: 10px; 
            margin-bottom: 20px;
        }
        @media (min-width: 768px) {
            .stats-grid { grid-template-columns: repeat(4, 1fr); }
        }
        .stat-card {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 20px 15px; 
            border-radius: 12px; 
            border: 1px solid #ffd700; 
            text-align: center;
            transition: transform 0.2s;
        }
        .stat-card:active { transform: scale(0.98); }
        .stat-card h3 { color: #888; font-size: 0.75rem; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; }
        .stat-card p { color: #ffd700; font-size: 1.4rem; font-weight: bold; }
        
        /* Formularios */
        .form-box { 
            background: #1a1a2e; 
            padding: 20px; 
            border-radius: 12px; 
            margin-bottom: 20px;
            border: 1px solid #333;
        }
        .form-box h3 { 
            color: #ffd700; 
            margin-bottom: 15px; 
            font-size: 1.1rem; 
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
        }
        .form-row { 
            display: flex; 
            gap: 10px; 
            margin-bottom: 12px; 
            flex-wrap: wrap; 
            align-items: center; 
        }
        .form-row input, .form-row select {
            flex: 1; 
            min-width: 120px; 
            padding: 12px; 
            background: #000;
            border: 1px solid #444; 
            color: white; 
            border-radius: 8px; 
            font-size: 1rem;
            -webkit-appearance: none;
        }
        .btn-submit {
            background: linear-gradient(135deg, #27ae60, #229954); 
            color: white; 
            border: none;
            padding: 12px 24px; 
            border-radius: 8px; 
            cursor: pointer; 
            font-weight: bold; 
            font-size: 0.95rem;
            flex: 1;
            min-width: 120px;
        }
        .btn-danger {
            background: linear-gradient(135deg, #c0392b, #e74c3c); 
            color: white; 
            border: none;
            padding: 12px 24px; 
            border-radius: 8px; 
            cursor: pointer; 
            font-weight: bold; 
            font-size: 0.95rem;
        }
        .btn-secondary {
            background: #444; 
            color: white; 
            border: none;
            padding: 10px 16px; 
            border-radius: 6px; 
            cursor: pointer; 
            font-size: 0.85rem;
            flex: 1;
        }
        .btn-csv {
            background: linear-gradient(135deg, #f39c12, #e67e22); 
            color: black; 
            border: none;
            padding: 12px 24px; 
            border-radius: 8px; 
            cursor: pointer; 
            font-weight: bold; 
            font-size: 0.95rem;
        }
        
        /* Tablas */
        .table-container {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin: 15px 0;
            border-radius: 8px;
            border: 1px solid #333;
            background: #1a1a2e;
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            font-size: 0.85rem; 
        }
        th, td { 
            padding: 12px 10px; 
            text-align: left; 
            border-bottom: 1px solid #333; 
            white-space: nowrap;
        }
        th { 
            background: linear-gradient(135deg, #ffd700, #ffed4e); 
            color: black; 
            font-weight: bold;
            position: sticky;
            top: 0;
        }
        tr:hover { background: rgba(255,215,0,0.05); }
        
        /* Riesgo */
        .riesgo-item {
            background: #1a1a2e; 
            padding: 15px; 
            margin-bottom: 10px;
            border-radius: 8px; 
            border-left: 4px solid #c0392b;
            font-size: 0.9rem;
        }
        .riesgo-item.lechuza {
            border-left-color: #ffd700;
            background: linear-gradient(135deg, rgba(255,215,0,0.1), #1a1a2e);
        }
        .riesgo-item b { color: #ffd700; font-size: 1.1rem; }
        
        .sorteo-actual-box {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 20px; 
            border-radius: 12px; 
            margin-bottom: 20px;
            border: 2px solid #2980b9; 
            text-align: center;
        }
        .sorteo-actual-box h4 { color: #2980b9; margin-bottom: 8px; font-size: 0.9rem; }
        .sorteo-actual-box p { color: #ffd700; font-size: 1.8rem; font-weight: bold; }
        
        /* Selector de agencia */
        .agencia-selector {
            background: linear-gradient(135deg, #0a0a0a, #1a1a2e);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            border: 1px solid #444;
        }
        .agencia-selector label {
            color: #ffd700;
            font-weight: bold;
            display: block;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }
        .agencia-selector select {
            width: 100%;
            padding: 12px;
            background: #000;
            border: 2px solid #ffd700;
            color: white;
            border-radius: 8px;
            font-size: 1rem;
        }
        .agencia-info {
            margin-top: 10px;
            padding: 10px;
            background: rgba(255,215,0,0.1);
            border-radius: 6px;
            text-align: center;
            color: #ffd700;
            font-weight: bold;
        }
        
        /* Resultados */
        .resultado-item {
            background: #0a0a0a;
            padding: 15px;
            margin: 8px 0;
            border-radius: 10px;
            border-left: 4px solid #27ae60;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .resultado-item.pendiente {
            border-left-color: #666;
            opacity: 0.7;
        }
        .resultado-numero { color: #ffd700; font-weight: bold; font-size: 1.3rem; }
        .resultado-nombre { color: #888; font-size: 0.9rem; }
        
        .btn-editar {
            background: linear-gradient(135deg, #2980b9, #3498db);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: bold;
            margin-left: 10px;
            transition: all 0.2s;
        }
        .btn-editar:hover {
            background: linear-gradient(135deg, #3498db, #2980b9);
            transform: scale(1.05);
        }
        
        /* Modal de edición */
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 2000;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .modal.active { display: flex; }
        .modal-box {
            background: #1a1a2e;
            padding: 25px;
            border-radius: 15px;
            border: 2px solid #ffd700;
            max-width: 400px;
            width: 100%;
        }
        .modal-box h3 {
            color: #ffd700;
            margin-bottom: 20px;
            text-align: center;
        }
        .warning-box {
            background: rgba(243, 156, 18, 0.2);
            border: 1px solid #f39c12;
            color: #f39c12;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 0.9rem;
            display: none;
        }
        
        /* Ranking */
        .ranking-item {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 10px;
            border-left: 4px solid #ffd700;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .ranking-pos {
            font-size: 1.5rem;
            font-weight: bold;
            color: #ffd700;
            min-width: 40px;
        }
        .ranking-info { flex: 1; padding: 0 10px; }
        .ranking-nombre { font-weight: bold; color: white; font-size: 1.1rem; }
        .ranking-detalle { font-size: 0.85rem; color: #888; margin-top: 3px; }
        .ranking-monto { text-align: right; }
        .ranking-ventas { font-size: 1.3rem; font-weight: bold; color: #27ae60; }
        .ranking-balance { font-size: 0.9rem; color: #888; }
        
        /* Mensajes */
        .mensaje {
            padding: 15px; 
            margin: 15px 0; 
            border-radius: 8px; 
            display: none;
            font-size: 0.95rem;
            text-align: center;
        }
        .mensaje.success { 
            background: rgba(39,174,96,0.2); 
            border: 1px solid #27ae60; 
            display: block; 
            color: #27ae60;
        }
        .mensaje.error { 
            background: rgba(192,57,43,0.2); 
            border: 1px solid #c0392b; 
            display: block; 
            color: #c0392b;
        }
        
        /* Tabs content */
        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.3s; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        
        .btn-group {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 10px;
        }
        .btn-group button {
            flex: 1;
            min-width: 80px;
        }
        
        .logout-btn {
            background: #c0392b;
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            font-size: 0.85rem;
        }
        
        /* Info de zona horaria */
        .timezone-info {
            background: rgba(41, 128, 185, 0.1);
            border: 1px solid #2980b9;
            color: #3498db;
            padding: 12px;
            border-radius: 8px;
            margin: 15px 0;
            font-size: 0.85rem;
            text-align: center;
        }
    </style>
</head>
<body>
    <!-- Modal de Edición de Resultado -->
    <div class="modal" id="modal-editar">
        <div class="modal-box">
            <h3>✏️ EDITAR RESULTADO</h3>
            <div class="warning-box" id="editar-advertencia">
                ⚠️ Este sorteo tiene tickets vendidos. Al cambiar el resultado, los tickets ganadores cambiarán.
            </div>
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
                    {% for k, v in animales.items() %}
                    <option value="{{k}}">{{k}} - {{v}}</option>
                    {% endfor %}
                </select>
            </div>
            <div style="display: flex; gap: 10px;">
                <button onclick="cerrarModalEditar()" style="flex: 1; background: #444; color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-weight: bold;">CANCELAR</button>
                <button onclick="confirmarEdicion()" style="flex: 2; background: linear-gradient(135deg, #27ae60, #229954); color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-weight: bold;">GUARDAR CAMBIO</button>
            </div>
        </div>
    </div>

    <!-- MENU DESKTOP - WINDOWS FORMS STYLE -->
    <div class="win-menu-bar">
        <div class="win-menu-header">
            <div class="win-title">👑 PANEL ADMIN - ZOOLO CASINO</div>
            <button onclick="location.href='/logout'" class="logout-btn">SALIR</button>
        </div>
        <ul class="win-menu-items">
            <li class="win-menu-item">
                <a>📁 Archivo</a>
                <ul class="win-submenu">
                    <li class="win-submenu-item"><a onclick="showTab('dashboard')">📊 Dashboard / Auditor</a></li>
                    <li class="win-submenu-item"><a onclick="showTab('calculadora')">🧮 Calcular Premio</a></li>
                    <li class="win-submenu-item"><a onclick="showTab('parametros')">⚙️ Parámetros del Sistema</a></li>
                </ul>
            </li>
            <li class="win-menu-item">
                <a>🔄 Movimientos</a>
                <ul class="win-submenu">
                    <li class="win-submenu-item"><a onclick="eliminarListas()">🗑️ Eliminar Listas (Limpiar)</a></li>
                    <li class="win-submenu-item"><a onclick="showTab('anular')">❌ Borrar Tickets</a></li>
                    <li class="win-submenu-item"><a onclick="showTab('pagar')">💰 Pagar Ticket</a></li>
                </ul>
            </li>
            <li class="win-menu-item">
                <a>🔍 Consultas</a>
                <ul class="win-submenu">
                    <li class="win-submenu-item"><a onclick="showTab('resultados')">📋 Resultados</a></li>
                    <li class="win-submenu-item"><a onclick="showTab('status')">📊 Status Tickets</a></li>
                    <li class="win-submenu-item"><a onclick="showTab('reporte')">🏢 Tickets Por Pagar/Pagados</a></li>
                    <li class="win-submenu-item"><a onclick="cargarAnulados()">🗑️ Tickets Anulados</a></li>
                </ul>
            </li>
            <li class="win-menu-item">
                <a>❓ Ayuda</a>
                <ul class="win-submenu">
                    <li class="win-submenu-item"><a onclick="showTab('reglas')">📖 Reglas de Pago</a></li>
                    <li class="win-submenu-item"><a onclick="showTab('acerca')">ℹ️ Acerca del Sistema</a></li>
                </ul>
            </li>
        </ul>
    </div>

    <!-- MENU MOBIL - HAMBURGER -->
    <div class="mobile-header">
        <div class="mobile-title">👑 PANEL ADMIN</div>
        <button class="hamburger-btn" onclick="toggleMobileMenu()">☰</button>
    </div>
    
    <div class="mobile-menu-overlay" onclick="toggleMobileMenu()"></div>
    <div class="mobile-menu" id="mobileMenu">
        <div class="mobile-menu-header">
            <div class="mobile-menu-title">MENÚ</div>
            <button class="close-menu-btn" onclick="toggleMobileMenu()">×</button>
        </div>
        
        <div class="mobile-menu-section">
            <div class="mobile-menu-section-title">📁 Archivo</div>
            <div class="mobile-menu-item" onclick="showTabMobile('dashboard')">📊 Dashboard / Auditor</div>
            <div class="mobile-menu-item" onclick="showTabMobile('calculadora')">🧮 Calcular Premio</div>
            <div class="mobile-menu-item" onclick="showTabMobile('parametros')">⚙️ Parámetros</div>
        </div>
        
        <div class="mobile-menu-section">
            <div class="mobile-menu-section-title">🔄 Movimientos</div>
            <div class="mobile-menu-item" onclick="eliminarListasMobile()">🗑️ Eliminar Listas</div>
            <div class="mobile-menu-item" onclick="showTabMobile('anular')">❌ Borrar Tickets</div>
            <div class="mobile-menu-item" onclick="showTabMobile('pagar')">💰 Pagar Ticket</div>
        </div>
        
        <div class="mobile-menu-section">
            <div class="mobile-menu-section-title">🔍 Consultas</div>
            <div class="mobile-menu-item" onclick="showTabMobile('resultados')">📋 Resultados</div>
            <div class="mobile-menu-item" onclick="showTabMobile('status')">📊 Status Tickets</div>
            <div class="mobile-menu-item" onclick="showTabMobile('reporte')">🏢 Por Pagar/Pagados</div>
            <div class="mobile-menu-item" onclick="cargarAnuladosMobile()">🗑️ Anulados</div>
        </div>
        
        <div class="mobile-menu-section">
            <div class="mobile-menu-section-title">❓ Ayuda</div>
            <div class="mobile-menu-item" onclick="showTabMobile('reglas')">📖 Reglas de Pago</div>
            <div class="mobile-menu-item" onclick="showTabMobile('acerca')">ℹ️ Acerca de</div>
        </div>
        
        <div class="mobile-menu-section">
            <div class="mobile-menu-item" onclick="location.href='/logout'" style="color: #e74c3c; font-weight: bold;">🚪 Cerrar Sesión</div>
        </div>
    </div>

    <div class="content">
        <div id="mensaje" class="mensaje"></div>
        
        <div class="info-pago">
            💰 REGLAS: Animales (00-39) = x35 | Lechuza (40) = x70 | Especiales = x2
        </div>
        
        <div class="timezone-info" id="timezone-info" style="display: none;">
            ⏰ <strong>Zona Horaria Perú:</strong> Los resultados son editables hasta 2 horas después del sorteo (ej: 7PM editable hasta 9PM).
        </div>
        
        <!-- DASHBOARD -->
        <div id="dashboard" class="tab-content active">
            <h3 style="color: #ffd700; margin-bottom: 15px; font-size: 1.2rem;">📊 RESUMEN DE HOY</h3>
            <div class="stats-grid">
                <div class="stat-card"><h3>VENTAS</h3><p id="stat-ventas">S/0</p></div>
                <div class="stat-card"><h3>PREMIOS</h3><p id="stat-premios">S/0</p></div>
                <div class="stat-card"><h3>COMISIONES</h3><p id="stat-comisiones">S/0</p></div>
                <div class="stat-card"><h3>BALANCE</h3><p id="stat-balance">S/0</p></div>
            </div>
            
            <div class="form-box">
                <h3>⚡ ACCIONES RÁPIDAS</h3>
                <div class="btn-group">
                    <button class="btn-submit" onclick="showTab('riesgo')">Ver Riesgo</button>
                    <button class="btn-secondary" onclick="showTab('resultados')">Cargar Resultados</button>
                    <button class="btn-csv" onclick="showTab('reporte')">Reporte Agencias</button>
                </div>
            </div>
        </div>

        <!-- CALCULADORA -->
        <div id="calculadora" class="tab-content">
            <div class="form-box">
                <h3>🧮 CALCULAR PREMIO</h3>
                <div class="form-row">
                    <input type="number" id="calc-monto" placeholder="Monto apostado" min="1">
                    <select id="calc-tipo">
                        <option value="35">Animal Normal (x35)</option>
                        <option value="70">Lechuza (x70)</option>
                        <option value="2">Especial (x2)</option>
                    </select>
                </div>
                <button class="btn-submit" onclick="calcularPremio()" style="width: 100%; margin-top: 10px;">CALCULAR</button>
                <div id="calc-resultado" style="margin-top: 20px; text-align: center; font-size: 1.5rem; color: #ffd700; display: none;">
                    Premio: <span id="calc-premio">S/0</span>
                </div>
            </div>
        </div>

        <!-- PARAMETROS -->
        <div id="parametros" class="tab-content">
            <div class="form-box">
                <h3>⚙️ PARÁMETROS DEL SISTEMA</h3>
                <div class="stat-row">
                    <span class="stat-label">Pago Animal Normal:</span>
                    <span class="stat-value">x35</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Pago Lechuza (40):</span>
                    <span class="stat-value">x70</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Pago Especiales:</span>
                    <span class="stat-value">x2</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Comisión Agencia:</span>
                    <span class="stat-value">15%</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Minutos Bloqueo:</span>
                    <span class="stat-value">5 min antes</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Ventana Edición Resultados:</span>
                    <span class="stat-value" style="color: #3498db;">2 horas después del sorteo</span>
                </div>
                <div class="timezone-info">
                    <strong>Nota:</strong> El sorteo de 7:00 PM puede editarse hasta las 9:00 PM (2 horas después).
                </div>
            </div>
        </div>

        <!-- HISTORICO -->
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
                        <div class="stat-card"><h3>TOTAL VENTAS</h3><p id="hist-total-ventas">S/0</p></div>
                        <div class="stat-card"><h3>TOTAL PREMIOS</h3><p id="hist-total-premios">S/0</p></div>
                        <div class="stat-card"><h3>TICKETS</h3><p id="hist-total-tickets">0</p></div>
                        <div class="stat-card"><h3>BALANCE</h3><p id="hist-total-balance">S/0</p></div>
                    </div>

                    <h3 style="color: #ffd700; margin: 25px 0 15px; font-size: 1.1rem;">📋 DETALLE POR DÍA</h3>
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Fecha</th>
                                    <th>Tickets</th>
                                    <th>Ventas</th>
                                    <th>Premios</th>
                                    <th>Balance</th>
                                </tr>
                            </thead>
                            <tbody id="tabla-historico"></tbody>
                        </table>
                    </div>

                    <h3 style="color: #ffd700; margin: 25px 0 15px; font-size: 1.1rem;">🔥 TOP ANIMALES</h3>
                    <div id="top-animales-hist"></div>
                </div>
            </div>
        </div>

        <!-- RIESGO -->
        <div id="riesgo" class="tab-content">
            <div class="agencia-selector">
                <label for="riesgo-agencia-select">🏢 SELECCIONAR AGENCIA:</label>
                <select id="riesgo-agencia-select" onchange="cambiarAgenciaRiesgo()">
                    <option value="">TODAS LAS AGENCIAS</option>
                </select>
                <div class="agencia-info" id="riesgo-agencia-nombre" style="display:none;">
                    Mostrando riesgo para: <span id="nombre-agencia-actual">TODAS</span>
                </div>
            </div>
            
            <div class="sorteo-actual-box">
                <h4>🎯 SORTEO EN CURSO / PRÓXIMO</h4>
                <p id="sorteo-objetivo">Cargando...</p>
                <small style="color: #888; font-size: 0.8rem;">Riesgo calculado para este horario específico</small>
            </div>
            
            <h3 style="color: #ffd700; margin-bottom: 15px; font-size: 1.1rem;">
                💸 APUESTAS: <span id="total-apostado-sorteo" style="color: white;">S/0</span>
                <span id="cantidad-jugadas-info" style="color: #888; font-size: 0.8rem; display: block; margin-top: 5px;"></span>
            </h3>
            <div id="lista-riesgo"><p style="color: #888;">Cargando...</p></div>
            
            <div style="margin-top: 20px; padding: 15px; background: rgba(192, 57, 43, 0.1); border-radius: 8px; border: 1px solid #c0392b;">
                <small style="color: #ff6b6b;">
                    ⚠️ El riesgo se resetea automáticamente cuando cambia el sorteo.
                </small>
            </div>
        </div>

        <!-- REPORTE AGENCIAS -->
        <div id="reporte" class="tab-content">
            <div class="form-box">
                <h3>🏢 REPORTE POR AGENCIAS</h3>
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
                    <h4 style="color: #ffd700; margin-bottom: 15px; font-size: 1.1rem;">📈 TOTALES</h4>
                    <div class="stats-grid" id="stats-agencias-totales"></div>

                    <h4 style="color: #ffd700; margin: 25px 0 15px; font-size: 1.1rem;">🏆 TOP 5 AGENCIAS</h4>
                    <div id="ranking-agencias"></div>

                    <h4 style="color: #ffd700; margin: 25px 0 15px; font-size: 1.1rem;">📋 DETALLE COMPLETO</h4>
                    <div class="table-container">
                        <table id="tabla-detalle-agencias">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Agencia</th>
                                    <th>Tickets</th>
                                    <th>Ventas</th>
                                    <th>Premios</th>
                                    <th>Balance</th>
                                    <th>%</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- RESULTADOS -->
        <div id="resultados" class="tab-content">
            <div class="form-box">
                <h3>🔍 CONSULTAR RESULTADOS</h3>
                <div class="form-row">
                    <input type="date" id="admin-resultados-fecha" onchange="cargarResultadosAdminFecha()">
                    <button class="btn-submit" onclick="cargarResultadosAdminFecha()">CONSULTAR</button>
                    <button class="btn-secondary" onclick="cargarResultadosAdmin()">HOY</button>
                </div>
                <div id="admin-resultados-titulo" style="margin-top: 15px; color: #ffd700; font-weight: bold; text-align: center; font-size: 1.1rem;"></div>
            </div>

            <div class="form-box">
                <h3>📋 RESULTADOS CARGADOS</h3>
                <div class="timezone-info">
                    ℹ️ Los resultados solo son editables hasta 2 horas después de su horario (ej: 7PM hasta 9PM).
                </div>
                <div id="lista-resultados-admin" style="max-height: 400px; overflow-y: auto;">
                    <p style="color: #888; text-align: center; padding: 20px;">Seleccione una fecha...</p>
                </div>
            </div>

            <div class="form-box">
                <h3>✏️ CARGAR/EDITAR RESULTADO</h3>
                <div class="form-row">
                    <select id="res-hora" style="flex: 1.5;">{% for h in horarios %}<option value="{{h}}">{{h}}</option>{% endfor %}</select>
                    <select id="res-animal" style="flex: 2;">{% for k, v in animales.items() %}<option value="{{k}}">{{k}} - {{v}}</option>{% endfor %}</select>
                    <button class="btn-submit" onclick="guardarResultado()">GUARDAR</button>
                </div>
                <div style="margin-top: 10px; font-size: 0.85rem; color: #888;">
                    ℹ️ Si el resultado ya existe, se actualizará automáticamente (dentro de la ventana de 2 horas).
                </div>
            </div>
        </div>

        <!-- ANULAR -->
        <div id="anular" class="tab-content">
            <div class="form-box">
                <h3>❌ ANULAR TICKET</h3>
                <div class="form-row">
                    <input type="text" id="anular-serial" placeholder="Ingrese SERIAL del ticket" style="flex: 2;">
                    <button class="btn-danger" onclick="anularTicketAdmin()">ANULAR</button>
                </div>
                <div style="margin-top: 15px; padding: 15px; background: rgba(192, 57, 43, 0.1); border-radius: 8px; border: 1px solid #c0392b;">
                    <small style="color: #ff6b6b;">
                        ⚠️ Solo se pueden anular tickets que no estén pagados y cuyo sorteo no haya iniciado.
                    </small>
                </div>
                <div id="resultado-anular" style="margin-top: 15px; font-size: 1rem; text-align: center;"></div>
            </div>
        </div>

        <!-- PAGAR (ADMIN) -->
        <div id="pagar" class="tab-content">
            <div class="form-box">
                <h3>💰 PAGAR TICKET (ADMIN)</h3>
                <div class="form-row">
                    <input type="text" id="pagar-serial-admin" placeholder="Ingrese SERIAL del ticket" style="flex: 2;">
                    <button class="btn-submit" onclick="pagarTicketAdmin()">VERIFICAR Y PAGAR</button>
                </div>
                <div id="resultado-pago-admin" style="margin-top: 15px;"></div>
            </div>
        </div>

        <!-- STATUS TICKETS -->
        <div id="status" class="tab-content">
            <div class="form-box">
                <h3>📊 STATUS DE TICKETS</h3>
                <div class="form-row">
                    <input type="date" id="status-fecha" value="">
                    <button class="btn-submit" onclick="consultarStatusTickets()">CONSULTAR</button>
                </div>
                <div id="status-resultados" style="margin-top: 20px;"></div>
            </div>
        </div>

        <!-- REGLAS -->
        <div id="reglas" class="tab-content">
            <div class="form-box">
                <h3>📖 REGLAS DE PAGO</h3>
                <div style="line-height: 2; color: #ddd;">
                    <h4 style="color: #ffd700; margin: 15px 0;">🎯 Animales (00-39)</h4>
                    <ul style="margin-left: 20px; margin-bottom: 20px;">
                        <li>Pago: <strong style="color: #27ae60;">x35</strong> veces el monto apostado</li>
                        <li>Ejemplo: S/10 → S/350</li>
                    </ul>
                    
                    <h4 style="color: #ffd700; margin: 15px 0;">🦉 Lechuza (40)</h4>
                    <ul style="margin-left: 20px; margin-bottom: 20px;">
                        <li>Pago: <strong style="color: #e74c3c;">x70</strong> veces el monto apostado</li>
                        <li>Ejemplo: S/10 → S/700</li>
                        <li>¡Doble premio por el animal especial!</li>
                    </ul>
                    
                    <h4 style="color: #ffd700; margin: 15px 0;">🎲 Apuestas Especiales</h4>
                    <ul style="margin-left: 20px; margin-bottom: 20px;">
                        <li>Rojo, Negro, Par, Impar</li>
                        <li>Pago: <strong style="color: #2980b9;">x2</strong> veces el monto apostado</li>
                        <li>Ejemplo: S/10 → S/20</li>
                    </ul>
                    
                    <h4 style="color: #ffd700; margin: 15px 0;">⚠️ Restricciones</h4>
                    <ul style="margin-left: 20px;">
                        <li>Tickets se pueden anular hasta 5 minutos después de creados</li>
                        <li>Venta se bloquea 5 minutos antes de cada sorteo</li>
                        <li>Resultados editables hasta 2 horas después del sorteo</li>
                        <li>Tickets vencen a los 3 días</li>
                    </ul>
                </div>
            </div>
        </div>

        <!-- ACERCA -->
        <div id="acerca" class="tab-content">
            <div class="form-box" style="text-align: center;">
                <h3>ℹ️ ACERCA DEL SISTEMA</h3>
                <div style="padding: 30px;">
                    <div style="font-size: 3rem; margin-bottom: 20px;">🦁</div>
                    <h2 style="color: #ffd700; margin-bottom: 10px;">ZOOLO CASINO CLOUD</h2>
                    <p style="color: #888; font-size: 1.2rem; margin-bottom: 20px;">Versión 5.8</p>
                    <p style="color: #aaa; line-height: 1.8; margin-bottom: 30px;">
                        Sistema de gestión de lotería animal<br>
                        Desarrollado para Perú y Venezuela<br>
                        Zona horaria: Perú (UTC-5)
                    </p>
                    <div style="background: rgba(255,215,0,0.1); padding: 20px; border-radius: 10px; border: 1px solid rgba(255,215,0,0.3);">
                        <p style="color: #ffd700; margin: 0;">
                            <strong>Características:</strong><br>
                            ✓ Edición de resultados con ventana de 2 horas<br>
                            ✓ Menú estilo Windows Forms<br>
                            ✓ Gestión multi-agencia<br>
                            ✓ Cálculo automático de premios<br>
                            ✓ Exportación CSV
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <!-- CREAR AGENCIAS -->
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
            <h3 style="color: #ffd700; margin-bottom: 15px; font-size: 1.1rem;">🏢 AGENCIAS EXISTENTES</h3>
            <div class="table-container">
                <table>
                    <thead><tr><th>ID</th><th>Usuario</th><th>Nombre</th><th>Comisión</th></tr></thead>
                    <tbody id="tabla-agencias"><tr><td colspan="4" style="text-align:center;color:#888; padding: 20px;">Cargando...</td></tr></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const HORARIOS_ORDEN = {{horarios|tojson}};
        let historicoData = null;
        let reporteAgenciasData = null;
        let fechasConsulta = { inicio: null, fin: null };
        let listaAgencias = [];
        let editandoFecha = null;
        let editandoHora = null;

        // Toggle mobile menu
        function toggleMobileMenu() {
            const menu = document.getElementById('mobileMenu');
            const overlay = document.querySelector('.mobile-menu-overlay');
            menu.classList.toggle('active');
            overlay.classList.toggle('active');
        }

        function showTab(tab) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.win-menu-items .active').forEach(b => b.classList.remove('active'));
            
            const target = document.getElementById(tab);
            if (target) {
                target.classList.add('active');
            }
            
            if (tab === 'riesgo') {
                cargarAgenciasSelect();
                cargarRiesgo();
            }
            if (tab === 'reporte') {
                let hoy = new Date().toISOString().split('T')[0];
                document.getElementById('reporte-fecha-inicio').value = hoy;
                document.getElementById('reporte-fecha-fin').value = hoy;
                consultarReporteAgencias();
            }
            if (tab === 'agencias') cargarAgencias();
            if (tab === 'dashboard') cargarDashboard();
            if (tab === 'resultados') {
                let hoy = new Date().toISOString().split('T')[0];
                document.getElementById('admin-resultados-fecha').value = hoy;
                cargarResultadosAdmin();
            }
            if (tab === 'status') {
                document.getElementById('status-fecha').value = new Date().toISOString().split('T')[0];
            }
        }

        function showTabMobile(tab) {
            toggleMobileMenu();
            showTab(tab);
        }

        function showMensaje(msg, tipo) {
            let div = document.getElementById('mensaje');
            div.textContent = msg; 
            div.className = 'mensaje ' + tipo;
            setTimeout(() => div.className = 'mensaje', 4000);
        }

        function setRango(tipo) {
            let hoy = new Date();
            let inicio, fin;
            
            switch(tipo) {
                case 'hoy':
                    inicio = fin = hoy;
                    break;
                case 'ayer':
                    let ayer = new Date(hoy); ayer.setDate(ayer.getDate() - 1);
                    inicio = fin = ayer;
                    break;
                case 'semana':
                    inicio = new Date(hoy); inicio.setDate(inicio.getDate() - 6);
                    fin = hoy;
                    break;
                case 'mes':
                    inicio = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
                    fin = hoy;
                    break;
            }
            
            document.getElementById('hist-fecha-inicio').value = inicio.toISOString().split('T')[0];
            document.getElementById('hist-fecha-fin').value = fin.toISOString().split('T')[0];
            consultarHistorico();
        }

        function setRangoReporte(tipo) {
            let hoy = new Date();
            let inicio, fin;
            
            switch(tipo) {
                case 'hoy':
                    inicio = fin = hoy;
                    break;
                case 'ayer':
                    let ayer = new Date(hoy); ayer.setDate(ayer.getDate() - 1);
                    inicio = fin = ayer;
                    break;
                case 'semana':
                    inicio = new Date(hoy); inicio.setDate(inicio.getDate() - 6);
                    fin = hoy;
                    break;
                case 'mes':
                    inicio = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
                    fin = hoy;
                    break;
            }
            
            document.getElementById('reporte-fecha-inicio').value = inicio.toISOString().split('T')[0];
            document.getElementById('reporte-fecha-fin').value = fin.toISOString().split('T')[0];
            consultarReporteAgencias();
        }

        function cargarAgenciasSelect() {
            fetch('/admin/lista-agencias')
            .then(r => r.json())
            .then(d => {
                if (d.error) return;
                listaAgencias = d;
                let select = document.getElementById('riesgo-agencia-select');
                select.innerHTML = '<option value="">TODAS LAS AGENCIAS</option>';
                d.forEach(ag => {
                    select.innerHTML += `<option value="${ag.id}">${ag.nombre_agencia} (${ag.usuario})</option>`;
                });
            });
        }

        function cambiarAgenciaRiesgo() {
            cargarRiesgo();
        }

        function eliminarListas() {
            if (confirm('¿Eliminar todas las listas y limpiar el sistema?')) {
                showMensaje('Listas eliminadas correctamente', 'success');
            }
        }

        function eliminarListasMobile() {
            toggleMobileMenu();
            eliminarListas();
        }

        function calcularPremio() {
            const monto = parseFloat(document.getElementById('calc-monto').value) || 0;
            const multiplicador = parseInt(document.getElementById('calc-tipo').value);
            const premio = monto * multiplicador;
            
            document.getElementById('calc-premio').textContent = 'S/' + premio.toFixed(2);
            document.getElementById('calc-resultado').style.display = 'block';
        }

        function consultarStatusTickets() {
            const fecha = document.getElementById('status-fecha').value;
            if (!fecha) {
                showMensaje('Seleccione una fecha', 'error');
                return;
            }
            
            document.getElementById('status-resultados').innerHTML = `
                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>TOTAL TICKETS</h3>
                        <p>0</p>
                    </div>
                    <div class="stat-card">
                        <h3>PAGADOS</h3>
                        <p>0</p>
                    </div>
                    <div class="stat-card">
                        <h3>PENDIENTES</h3>
                        <p>0</p>
                    </div>
                    <div class="stat-card">
                        <h3>ANULADOS</h3>
                        <p>0</p>
                    </div>
                </div>
                <p style="color: #888; text-align: center; margin-top: 20px;">Consulta realizada para: ${fecha}</p>
            `;
        }

        function cargarAnulados() {
            showTab('reporte');
            showMensaje('Mostrando tickets anulados del período', 'success');
        }

        function cargarAnuladosMobile() {
            toggleMobileMenu();
            cargarAnulados();
        }

        function pagarTicketAdmin() {
            const serial = document.getElementById('pagar-serial-admin').value.trim();
            if (!serial) {
                showMensaje('Ingrese un serial', 'error');
                return;
            }
            
            fetch('/api/verificar-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    document.getElementById('resultado-pago-admin').innerHTML = `<div style="color: #c0392b; padding: 15px; background: rgba(192,57,43,0.1); border-radius: 8px;">${d.error}</div>`;
                    return;
                }
                
                let html = `<div style="background: rgba(39,174,96,0.1); padding: 20px; border-radius: 10px; border: 1px solid #27ae60;">`;
                html += `<h4 style="color: #27ae60; margin-bottom: 15px;">Ticket #${d.ticket_id}</h4>`;
                html += `<p style="font-size: 1.3rem; color: #ffd700; margin-bottom: 15px;">Total Ganado: S/${d.total_ganado.toFixed(2)}</p>`;
                
                if (d.total_ganado > 0) {
                    html += `<button onclick="confirmarPagoAdmin('${d.ticket_id}')" class="btn-submit" style="width: 100%;">CONFIRMAR PAGO</button>`;
                } else {
                    html += `<p style="color: #888;">Ticket no ganador</p>`;
                }
                html += `</div>`;
                
                document.getElementById('resultado-pago-admin').innerHTML = html;
            });
        }

        function confirmarPagoAdmin(ticketId) {
            fetch('/api/pagar-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ticket_id: ticketId})
            })
            .then(r => r.json())
            .then(d => {
                if (d.status === 'ok') {
                    showMensaje('✅ Ticket pagado correctamente', 'success');
                    document.getElementById('resultado-pago-admin').innerHTML = '<div style="color: #27ae60; text-align: center; padding: 20px;">✅ Pago realizado con éxito</div>';
                } else {
                    showMensaje(d.error || 'Error al pagar', 'error');
                }
            });
        }

        function abrirModalEditar(hora, fecha, animalActual) {
            editandoHora = hora;
            editandoFecha = fecha;
            
            document.getElementById('editar-fecha-display').value = fecha;
            document.getElementById('editar-hora-display').value = hora;
            document.getElementById('editar-animal-select').value = animalActual;
            
            verificarTicketsSorteo(fecha, hora);
            document.getElementById('modal-editar').classList.add('active');
        }
        
        function cerrarModalEditar() {
            document.getElementById('modal-editar').classList.remove('active');
            editandoFecha = null;
            editandoHora = null;
        }
        
        function verificarTicketsSorteo(fecha, hora) {
            fetch('/admin/verificar-tickets-sorteo', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha: fecha, hora: hora})
            })
            .then(r => r.json())
            .then(d => {
                let advertencia = document.getElementById('editar-advertencia');
                if (d.tickets_count > 0) {
                    advertencia.style.display = 'block';
                    advertencia.innerHTML = `⚠️ <strong>ADVERTENCIA:</strong> Este sorteo tiene <strong>${d.tickets_count} ticket(s)</strong> vendidos por un total de <strong>S/${d.total_apostado}</strong>.<br>Cambiar el resultado afectará quién gana o pierde.`;
                } else {
                    advertencia.style.display = 'none';
                }
            })
            .catch(e => console.error('Error verificando tickets:', e));
        }
        
        function confirmarEdicion() {
            let nuevoAnimal = document.getElementById('editar-animal-select').value;
            
            if (!confirm(`¿Está seguro de cambiar el resultado de ${editandoHora} a ${nuevoAnimal} - ${getNombreAnimal(nuevoAnimal)}?`)) {
                return;
            }
            
            let partes = editandoFecha.split('/');
            let fechaISO = `${partes[2]}-${partes[1]}-${partes[0]}`;
            
            let form = new FormData();
            form.append('hora', editandoHora);
            form.append('animal', nuevoAnimal);
            form.append('fecha', fechaISO);
            
            fetch('/admin/guardar-resultado', {method: 'POST', body: form})
            .then(r => r.json()).then(d => {
                if (d.status === 'ok') {
                    showMensaje('✅ ' + d.mensaje, 'success');
                    cerrarModalEditar();
                    let fechaActual = document.getElementById('admin-resultados-fecha').value;
                    if (fechaActual && fechaActual !== new Date().toISOString().split('T')[0]) {
                        cargarResultadosAdminFecha();
                    } else {
                        cargarResultadosAdmin();
                    }
                } else {
                    showMensaje(d.error || 'Error al guardar', 'error');
                }
            })
            .catch(e => {
                showMensaje('Error de conexión', 'error');
            });
        }
        
        function getNombreAnimal(numero) {
            const animales = {{animales|tojson}};
            return animales[numero] || 'Desconocido';
        }

        function consultarHistorico() {
            let inicio = document.getElementById('hist-fecha-inicio').value;
            let fin = document.getElementById('hist-fecha-fin').value;
            
            if (!inicio || !fin) {
                showMensaje('Seleccione ambas fechas', 'error');
                return;
            }
            
            fechasConsulta = { inicio, fin };
            showMensaje('Consultando datos...', 'success');
            
            fetch('/admin/estadisticas-rango', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    showMensaje(d.error, 'error');
                    return;
                }
                
                historicoData = d;
                document.getElementById('historico-resumen').style.display = 'block';
                
                document.getElementById('hist-total-ventas').textContent = 'S/' + d.totales.ventas.toFixed(0);
                document.getElementById('hist-total-premios').textContent = 'S/' + d.totales.premios.toFixed(0);
                document.getElementById('hist-total-tickets').textContent = d.totales.tickets;
                document.getElementById('hist-total-balance').textContent = 'S/' + d.totales.balance.toFixed(0);
                
                let tbody = document.getElementById('tabla-historico');
                let html = '';
                d.resumen_por_dia.forEach(dia => {
                    let color = dia.balance >= 0 ? '#27ae60' : '#c0392b';
                    html += `<tr>
                        <td>${dia.fecha}</td>
                        <td>${dia.tickets}</td>
                        <td>S/${dia.ventas.toFixed(0)}</td>
                        <td>S/${dia.premios.toFixed(0)}</td>
                        <td style="color:${color}; font-weight:bold">S/${dia.balance.toFixed(0)}</td>
                    </tr>`;
                });
                tbody.innerHTML = html;
                
                cargarTopAnimalesHistorico(inicio, fin);
            })
            .catch(e => showMensaje('Error de conexión', 'error'));
        }

        function consultarReporteAgencias() {
            let inicio = document.getElementById('reporte-fecha-inicio').value;
            let fin = document.getElementById('reporte-fecha-fin').value;
            
            if (!inicio || !fin) {
                showMensaje('Seleccione ambas fechas', 'error');
                return;
            }
            
            showMensaje('Consultando reporte...', 'success');
            
            fetch('/admin/reporte-agencias-rango', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    showMensaje(d.error, 'error');
                    return;
                }
                
                reporteAgenciasData = d;
                document.getElementById('reporte-agencias-resumen').style.display = 'block';
                
                let totales = d.totales;
                let htmlTotales = `
                    <div class="stat-card">
                        <h3>AGENCIAS</h3>
                        <p>${d.agencias.length}</p>
                    </div>
                    <div class="stat-card">
                        <h3>TICKETS</h3>
                        <p>${totales.tickets}</p>
                    </div>
                    <div class="stat-card">
                        <h3>VENTAS</h3>
                        <p>S/${totales.ventas.toFixed(0)}</p>
                    </div>
                    <div class="stat-card">
                        <h3>BALANCE</h3>
                        <p style="color: ${totales.balance >= 0 ? '#27ae60' : '#c0392b'}">S/${totales.balance.toFixed(0)}</p>
                    </div>
                `;
                document.getElementById('stats-agencias-totales').innerHTML = htmlTotales;
                
                let htmlRanking = '';
                d.agencias.slice(0, 5).forEach((ag, idx) => {
                    let medalla = ['🥇','🥈','🥉','4°','5°'][idx];
                    let colorBalance = ag.balance >= 0 ? '#27ae60' : '#c0392b';
                    htmlRanking += `
                        <div class="ranking-item">
                            <div class="ranking-pos">${medalla}</div>
                            <div class="ranking-info">
                                <div class="ranking-nombre">${ag.nombre}</div>
                                <div class="ranking-detalle">${ag.tickets} tickets • ${ag.porcentaje_ventas}% del total</div>
                            </div>
                            <div class="ranking-monto">
                                <div class="ranking-ventas">S/${ag.ventas.toFixed(0)}</div>
                                <div class="ranking-balance" style="color: ${colorBalance}">S/${ag.balance.toFixed(0)}</div>
                            </div>
                        </div>
                    `;
                });
                document.getElementById('ranking-agencias').innerHTML = htmlRanking;
                
                let tbody = document.querySelector('#tabla-detalle-agencias tbody');
                let htmlTabla = '';
                d.agencias.forEach((ag, idx) => {
                    let colorBalance = ag.balance >= 0 ? '#27ae60' : '#c0392b';
                    htmlTabla += `<tr>
                        <td>${idx + 1}</td>
                        <td><strong>${ag.nombre}</strong><br><small style="color:#888">${ag.usuario}</small></td>
                        <td>${ag.tickets}</td>
                        <td>S/${ag.ventas.toFixed(0)}</td>
                        <td>S/${ag.premios.toFixed(0)}</td>
                        <td style="color:${colorBalance}; font-weight:bold">S/${ag.balance.toFixed(0)}</td>
                        <td>${ag.porcentaje_ventas}%</td>
                    </tr>`;
                });
                
                htmlTabla += `<tr style="background:rgba(255,215,0,0.2); font-weight:bold;">
                    <td colspan="2">TOTALES</td>
                    <td>${totales.tickets}</td>
                    <td>S/${totales.ventas.toFixed(0)}</td>
                    <td>S/${totales.premios.toFixed(0)}</td>
                    <td style="color:${totales.balance >= 0 ? '#27ae60' : '#c0392b'}">S/${totales.balance.toFixed(0)}</td>
                    <td>100%</td>
                </tr>`;
                
                tbody.innerHTML = htmlTabla;
            })
            .catch(e => {
                console.error(e);
                showMensaje('Error de conexión', 'error');
            });
        }

        function exportarCSV() {
            if (!reporteAgenciasData) {
                showMensaje('Primero genere un reporte', 'error');
                return;
            }
            
            let inicio = document.getElementById('reporte-fecha-inicio').value;
            let fin = document.getElementById('reporte-fecha-fin').value;
            
            fetch('/admin/exportar-csv', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})
            })
            .then(r => r.blob())
            .then(blob => {
                let url = window.URL.createObjectURL(blob);
                let a = document.createElement('a');
                a.href = url;
                a.download = `reporte_agencias_${inicio}_${fin}.csv`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                showMensaje('CSV descargado correctamente', 'success');
            })
            .catch(e => showMensaje('Error al exportar', 'error'));
        }

        function cargarTopAnimalesHistorico(inicio, fin) {
            fetch('/admin/top-animales-rango', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})
            })
            .then(r => r.json())
            .then(d => {
                let container = document.getElementById('top-animales-hist');
                if (!d.top_animales || d.top_animales.length === 0) {
                    container.innerHTML = '<p style="color: #888;">No hay datos suficientes</p>';
                    return;
                }
                
                let html = '';
                d.top_animales.slice(0, 10).forEach((a, idx) => {
                    let medalla = idx < 3 ? ['🥇','🥈','🥉'][idx] : (idx + 1);
                    let esLechuza = a.numero === "40";
                    let clase = esLechuza ? 'riesgo-item lechuza' : 'riesgo-item';
                    let extra = esLechuza ? ' 🦉 ¡Paga x70!' : '';
                    
                    html += `<div class="${clase}" style="margin-bottom: 10px;">
                        <b>${medalla} ${a.numero} - ${a.nombre}${extra}</b><br>
                        <small>Apostado: S/${a.total_apostado} • Si sale pagaría: S/${a.pago_potencial}</small>
                    </div>`;
                });
                container.innerHTML = html;
            });
        }

        function cargarDashboard() {
            fetch('/admin/reporte-agencias').then(r => r.json()).then(d => {
                if (d.global) {
                    document.getElementById('stat-ventas').textContent = 'S/' + d.global.ventas.toFixed(0);
                    document.getElementById('stat-premios').textContent = 'S/' + d.global.pagos.toFixed(0);
                    document.getElementById('stat-comisiones').textContent = 'S/' + d.global.comisiones.toFixed(0);
                    document.getElementById('stat-balance').textContent = 'S/' + d.global.balance.toFixed(0);
                }
            }).catch(() => showMensaje('Error de conexion', 'error'));
        }

        function cargarRiesgo() {
            let agenciaId = document.getElementById('riesgo-agencia-select').value;
            let url = '/admin/riesgo';
            
            if (agenciaId) {
                url += '?agencia_id=' + agenciaId;
            }
            
            fetch(url)
            .then(r => r.json())
            .then(d => {
                if (d.sorteo_objetivo) {
                    document.getElementById('sorteo-objetivo').textContent = d.sorteo_objetivo;
                    document.getElementById('total-apostado-sorteo').textContent = 'S/' + (d.total_apostado || 0).toFixed(2);
                    
                    let nombreAgencia = d.agencia_nombre || "TODAS LAS AGENCIAS";
                    document.getElementById('nombre-agencia-actual').textContent = nombreAgencia;
                    document.getElementById('riesgo-agencia-nombre').style.display = 'block';
                    
                    let infoExtra = d.cantidad_jugadas ? `${d.cantidad_jugadas} jugadas registradas` : '';
                    if (d.hora_actual) infoExtra += ` • Hora actual: ${d.hora_actual}`;
                    document.getElementById('cantidad-jugadas-info').textContent = infoExtra;
                } else {
                    document.getElementById('sorteo-objetivo').textContent = 'No hay más sorteos hoy';
                    document.getElementById('total-apostado-sorteo').textContent = 'S/0';
                    document.getElementById('cantidad-jugadas-info').textContent = '';
                }
                
                let container = document.getElementById('lista-riesgo');
                if (!d.riesgo || Object.keys(d.riesgo).length === 0) {
                    container.innerHTML = '<p style="color:#888; text-align: center; padding: 20px;">No hay apuestas para este sorteo</p>'; 
                    return;
                }
                let html = '';
                for (let [k, v] of Object.entries(d.riesgo)) {
                    let clase = v.es_lechuza ? 'riesgo-item lechuza' : 'riesgo-item';
                    let extra = v.es_lechuza ? ' ⚠️ ALTO RIESGO (x70)' : '';
                    html += `<div class="${clase}">
                        <b>${k}${extra}</b><br>
                        Apostado: S/${v.apostado.toFixed(2)} • Pagaría: S/${v.pagaria.toFixed(2)} • ${v.porcentaje}% del total
                    </div>`;
                }
                container.innerHTML = html;
            })
            .catch(e => {
                console.error(e);
                showMensaje('Error cargando riesgo', 'error');
            });
        }

        function cargarResultadosAdminFecha() {
            let fecha = document.getElementById('admin-resultados-fecha').value;
            if (!fecha) return;
            
            let container = document.getElementById('lista-resultados-admin');
            container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Cargando...</p>';
            
            let fechaObj = new Date(fecha + 'T00:00:00');
            let opciones = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
            document.getElementById('admin-resultados-titulo').textContent = fechaObj.toLocaleDateString('es-PE', opciones);
            
            fetch('/api/resultados-fecha', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha: fecha})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error: ' + d.error + '</p>';
                    return;
                }
                renderizarResultadosAdmin(d.resultados, d.fecha_consulta);
            })
            .catch(() => {
                container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexión</p>';
            });
        }

        function cargarResultadosAdmin() {
            fetch('/admin/resultados-hoy')
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    document.getElementById('lista-resultados-admin').innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error al cargar</p>';
                    return;
                }
                document.getElementById('admin-resultados-titulo').textContent = 'HOY - ' + new Date().toLocaleDateString('es-PE');
                renderizarResultadosAdmin(d.resultados, d.fecha);
            })
            .catch(() => {
                document.getElementById('lista-resultados-admin').innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexión</p>';
            });
        }

        function renderizarResultadosAdmin(resultados, fechaStr) {
            let container = document.getElementById('lista-resultados-admin');
            let html = '';
            
            for (let hora of HORARIOS_ORDEN) {
                let resultado = resultados[hora];
                let clase = resultado ? '' : 'pendiente';
                let contenido;
                let botonEditar = '';
                
                if (resultado) {
                    contenido = `
                        <span class="resultado-numero">${resultado.animal}</span>
                        <span class="resultado-nombre">${resultado.nombre}</span>
                    `;
                    botonEditar = `<button class="btn-editar" onclick="abrirModalEditar('${hora}', '${fechaStr}', '${resultado.animal}')">✏️ EDITAR</button>`;
                } else {
                    contenido = `
                        <span style="color: #666; font-size:1.1rem">Pendiente</span>
                        <span style="color: #444; font-size: 0.85rem;">Sin resultado</span>
                    `;
                    botonEditar = `<button class="btn-editar" onclick="prepararNuevoResultado('${hora}')" style="background: #27ae60;">➕ CARGAR</button>`;
                }
                
                html += `
                    <div class="resultado-item ${clase}">
                        <div style="display: flex; flex-direction: column;">
                            <strong style="color: #ffd700; font-size: 1rem;">${hora}</strong>
                        </div>
                        <div style="text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 5px;">
                            ${contenido}
                            ${botonEditar}
                        </div>
                    </div>
                `;
            }
            container.innerHTML = html;
        }
        
        function prepararNuevoResultado(hora) {
            document.getElementById('res-hora').value = hora;
            document.getElementById('res-animal').focus();
            document.getElementById('res-hora').scrollIntoView({behavior: 'smooth'});
        }

        function guardarResultado() {
            let form = new FormData();
            form.append('hora', document.getElementById('res-hora').value);
            form.append('animal', document.getElementById('res-animal').value);
            
            let fechaActual = document.getElementById('admin-resultados-fecha').value;
            if (fechaActual) {
                form.append('fecha', fechaActual);
            }
            
            fetch('/admin/guardar-resultado', {method: 'POST', body: form})
            .then(r => r.json()).then(d => {
                if (d.status === 'ok') {
                    showMensaje('✅ ' + d.mensaje, 'success');
                    let fechaActual = document.getElementById('admin-resultados-fecha').value;
                    if (fechaActual && fechaActual !== new Date().toISOString().split('T')[0]) {
                        cargarResultadosAdminFecha();
                    } else {
                        cargarResultadosAdmin();
                    }
                }
                else showMensaje(d.error || 'Error', 'error');
            });
        }

        function anularTicketAdmin() {
            let serial = document.getElementById('anular-serial').value.trim();
            if (!serial) {
                showMensaje('Ingrese un serial', 'error');
                return;
            }
            
            if (!confirm('¿Está seguro de anular el ticket ' + serial + '?')) {
                return;
            }
            
            fetch('/api/anular-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => {
                let resultadoDiv = document.getElementById('resultado-anular');
                if (d.error) {
                    resultadoDiv.innerHTML = '<span style="color: #c0392b; font-weight:bold">❌ ' + d.error + '</span>';
                    showMensaje(d.error, 'error');
                } else {
                    resultadoDiv.innerHTML = '<span style="color: #27ae60; font-weight:bold">✅ ' + d.mensaje + '</span>';
                    showMensaje(d.mensaje, 'success');
                    document.getElementById('anular-serial').value = '';
                }
            })
            .catch(e => {
                showMensaje('Error de conexión', 'error');
            });
        }

        function cargarAgencias() {
            fetch('/admin/lista-agencias').then(r => r.json()).then(d => {
                let tbody = document.getElementById('tabla-agencias');
                if (!d || d.length === 0) { 
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 20px;">No hay agencias</td></tr>'; 
                    return; 
                }
                let html = '';
                for (let a of d) html += '<tr><td>' + a.id + '</td><td>' + a.usuario + '</td><td>' + a.nombre_agencia + '</td><td>' + (a.comision * 100).toFixed(0) + '%</td></tr>';
                tbody.innerHTML = html;
            });
        }

        function crearAgencia() {
            let form = new FormData();
            form.append('usuario', document.getElementById('new-usuario').value.trim());
            form.append('password', document.getElementById('new-password').value.trim());
            form.append('nombre', document.getElementById('new-nombre').value.trim());
            fetch('/admin/crear-agencia', {method: 'POST', body: form})
            .then(r => r.json()).then(d => {
                if (d.status === 'ok') {
                    showMensaje('✅ ' + d.mensaje, 'success');
                    document.getElementById('new-usuario').value = '';
                    document.getElementById('new-password').value = '';
                    document.getElementById('new-nombre').value = '';
                    cargarAgencias();
                } else showMensaje(d.error || 'Error', 'error');
            });
        }

        document.addEventListener('DOMContentLoaded', function() {
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('hist-fecha-inicio').value = hoy;
            document.getElementById('hist-fecha-fin').value = hoy;
            document.getElementById('admin-resultados-fecha').value = hoy;
            
            setTimeout(() => {
                document.getElementById('timezone-info').style.display = 'block';
            }, 1000);
        });

        cargarDashboard();
    </script>
</body>
</html>
'''

# ==================== MAIN ====================
if __name__ == '__main__':
    print("=" * 60)
    print("  ZOOLO CASINO CLOUD v5.8")
    print("  MENU WINDOWS AGENCIA + ADMIN")
    print("=" * 60)
    print("  - Agencia: Menu Archivo/Consultas/Ayuda")
    print("  - Admin: Menu Archivo/Movimientos/Consultas/Ayuda")
    print("  - Estilo Windows Forms (Desktop) / Hamburger (Mobile)")
    print("=" * 60)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
