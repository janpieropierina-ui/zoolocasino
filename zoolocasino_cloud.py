#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v5.6 - Admin Completo + Riesgo por Sorteo
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
from flask import Flask, render_template_string, request, session, redirect, jsonify
from collections import defaultdict

# ==================== CONFIGURACION SUPABASE ====================
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://iuwgbtmhkqnqulwgcgkk.supabase.co ')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml1d2didG1oa3FucXVsd2djZ2trIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEwMTM0OTQsImV4cCI6MjA4NjU4OTQ5NH0.HJGQk5JppC34OHWhQY9Goou617uxB1QVuIQLD72NLgE')

app = Flask(__name__)
app.secret_key = "zoolo_casino_cloud_2025"

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

def supabase_request(table, method="GET", data=None, filters=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    if filters:
        filter_str = "&".join([f"{k}=eq.{v}" for k, v in filters.items()])
        url += "?" + filter_str
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        if method == "GET":
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode())
        
        elif method == "POST":
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode())
        
        elif method == "PATCH":
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="PATCH")
            with urllib.request.urlopen(req, timeout=15) as response:
                return True
                
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode()}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def obtener_proximo_sorteo():
    """Devuelve el próximo horario de sorteo disponible"""
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
        
        # Si faltan más de 5 minutos para el sorteo, es el próximo válido
        if (sorteo_minutos - actual_minutos) > MINUTOS_BLOQUEO:
            return hora_str
    
    return None

def obtener_sorteo_en_curso():
    """Devuelve el sorteo que está actualmente en curso (dentro de la hora actual)"""
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
        
        # Si estamos dentro de la hora del sorteo (entre la hora exacta y 59 min)
        if actual_minutos >= sorteo_minutos and actual_minutos < (sorteo_minutos + 60):
            return hora_str
    
    # Si no hay sorteo en curso, devolver el próximo
    return obtener_proximo_sorteo()

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
        
        users = supabase_request("agencias", filters={"usuario": u, "password": p, "activa": "true"})
        
        if users and len(users) > 0:
            user = users[0]
            session['user_id'] = user['id']
            session['nombre_agencia'] = user['nombre_agencia']
            session['es_admin'] = user['es_admin']
            return redirect('/')
        else:
            error = "Usuario o clave incorrecta"
    
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
    """Endpoint para que las agencias vean los resultados del día (solo lectura)"""
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
        
        # Completar con horarios pendientes
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
        
        # ==================== FORMATO COMPACTO DEL TICKET ====================
        # Agrupar jugadas por hora
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
        
        # Procesar cada horario
        for hora_peru in HORARIOS_PERU:
            if hora_peru not in jugadas_por_hora:
                continue
                
            idx = HORARIOS_PERU.index(hora_peru)
            hora_ven = HORARIOS_VENEZUELA[idx]
            
            # Formato: ZOOLO PERU/09:AM...VZLA/10:AM
            hora_peru_corta = hora_peru.replace(' ', '').replace('00', '').lower()
            hora_ven_corta = hora_ven.replace(' ', '').replace('00', '').lower()
            lineas.append(f"*ZOOLO.PERU/{hora_peru_corta}...VZLA/{hora_ven_corta}*")
            
            # Agrupar jugadas de esta hora en una sola línea
            jugadas_hora = jugadas_por_hora[hora_peru]
            texto_jugadas = []
            
            for j in jugadas_hora:
                if j['tipo'] == 'animal':
                    # Formato: ZOR 15x10 (abreviatura del animal + numero x monto)
                    nombre_corto = ANIMALES.get(j['seleccion'], '')[0:3].upper()  # Primeras 3 letras
                    if j['seleccion'] == "40":
                        texto_jugadas.append(f"{nombre_corto}{j['seleccion']}x{int(j['monto'])}")
                    else:
                        texto_jugadas.append(f"{nombre_corto}{j['seleccion']}x{int(j['monto'])}")
                else:
                    # Formato especial: ROJx10 o NEGx10
                    tipo_corto = j['seleccion'][0:3]
                    texto_jugadas.append(f"{tipo_corto}x{int(j['monto'])}")
            
            # Unir todas las jugadas de esta hora con espacios
            lineas.append(" ".join(texto_jugadas))
            lineas.append("")  # Línea en blanco entre horarios
        
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
        url = f"{SUPABASE_URL}/rest/v1/tickets?id=eq.{ticket_id}"
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
        
        # Verificar si ya está pagado
        if ticket['pagado']:
            return jsonify({'error': 'Ya esta pagado, no se puede anular'})
        
        # Si es agencia (no admin), verificar restricción de 5 minutos
        if not session.get('es_admin'):
            fecha_ticket = parse_fecha_ticket(ticket['fecha'])
            if not fecha_ticket:
                return jsonify({'error': 'Error en fecha del ticket'})
            
            minutos_transcurridos = (ahora_peru() - fecha_ticket).total_seconds() / 60
            if minutos_transcurridos > 5:
                return jsonify({'error': f'No puede anular después de 5 minutos. Han pasado {int(minutos_transcurridos)} minutos'})
            
            # Verificar que el sorteo no haya pasado para ninguna jugada
            jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
            for j in jugadas:
                if not verificar_horario_bloqueo(j['hora']):
                    return jsonify({'error': f'No se puede anular, el sorteo {j["hora"]} ya cerró o está por cerrar'})
        
        # Si es admin, solo verificar que el sorteo no haya ocurrido aún (más permisivo)
        else:
            jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
            for j in jugadas:
                # Admin puede anular hasta el último momento antes del sorteo
                if not verificar_horario_bloqueo(j['hora']):
                    return jsonify({'error': f'No se puede anular, el sorteo {j["hora"]} ya está cerrado o en curso'})
        
        # Proceder a anular
        url = f"{SUPABASE_URL}/rest/v1/tickets?id=eq.{ticket['id']}"
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{hoy}%25"
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
                            sel = j['seleccion']
                            num = int(wa)
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
        fecha = ahora_peru().strftime("%d/%m/%Y")
        
        existentes = supabase_request("resultados", filters={"fecha": fecha, "hora": hora})
        
        if existentes and len(existentes) > 0:
            url = f"{SUPABASE_URL}/rest/v1/resultados?fecha=eq.{fecha}&hora=eq.{hora}"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            data = json.dumps({"animal": animal}).encode()
            req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
            urllib.request.urlopen(req, timeout=15)
        else:
            data = {"fecha": fecha, "hora": hora, "animal": animal}
            supabase_request("resultados", method="POST", data=data)
        
        return jsonify({'status': 'ok', 'mensaje': f'Resultado guardado: {hora} = {animal}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/resultados-hoy')
@admin_required
def admin_resultados_hoy():
    """Obtener resultados del día para el admin"""
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
        
        # Completar con horarios pendientes
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{hoy}%25"
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
        
        print(f"[DEBUG] Sorteo objetivo (en curso o próximo): {sorteo_objetivo}")
        print(f"[DEBUG] Hora actual Perú: {ahora_peru().strftime('%I:%M %p')}")
        
        if not sorteo_objetivo:
            return jsonify({
                'riesgo': {},
                'sorteo_objetivo': None,
                'mensaje': 'No hay más sorteos disponibles para hoy'
            })
        
        # Obtener todos los tickets de hoy no anulados
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{hoy}%25&anulado=eq.false"
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
                'total_apostado': 0
            })
        
        print(f"[DEBUG] Tickets encontrados hoy: {len(tickets)}")
        
        # Obtener jugadas de tipo animal SOLO para el sorteo objetivo
        apuestas = {}
        total_apostado_sorteo = 0
        total_jugadas_contadas = 0
        
        for t in tickets:
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id'], "tipo": "animal"})
            
            for j in jugadas:
                # FILTRO ESTRICTO: Solo el sorteo en curso/próximo
                if j.get('hora') == sorteo_objetivo:
                    sel = j.get('seleccion')
                    monto = j.get('monto', 0)
                    if sel:
                        if sel not in apuestas:
                            apuestas[sel] = 0
                        apuestas[sel] += monto
                        total_apostado_sorteo += monto
                        total_jugadas_contadas += 1
        
        print(f"[DEBUG] Jugadas para {sorteo_objetivo}: {total_jugadas_contadas}")
        print(f"[DEBUG] Total apostado: {total_apostado_sorteo}")
        
        # Ordenar por monto mayor
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
            'cantidad_jugadas': total_jugadas_contadas
        })
        
    except Exception as e:
        print(f"[ERROR] En riesgo: {str(e)}")
        import traceback
        traceback.print_exc()
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: white;
            font-family: 'Segoe UI', sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-box {
            background: rgba(255,255,255,0.05);
            padding: 40px;
            border-radius: 20px;
            border: 2px solid #ffd700;
            width: 90%;
            max-width: 400px;
            text-align: center;
        }
        .login-box h2 { color: #ffd700; margin-bottom: 30px; font-size: 2rem; }
        .form-group { margin-bottom: 20px; text-align: left; }
        .form-group label { display: block; margin-bottom: 8px; color: #aaa; }
        .form-group input {
            width: 100%; padding: 12px;
            border: 1px solid #444; border-radius: 8px;
            background: rgba(0,0,0,0.5); color: white; font-size: 1rem;
        }
        .btn-login {
            width: 100%; padding: 15px;
            background: linear-gradient(45deg, #ffd700, #ffed4e);
            color: black; border: none; border-radius: 8px;
            font-size: 1.1rem; font-weight: bold; cursor: pointer;
        }
        .error {
            background: rgba(255,0,0,0.2); color: #ff6b6b;
            padding: 10px; border-radius: 5px; margin-bottom: 20px;
        }
        .info { margin-top: 20px; font-size: 0.85rem; color: #666; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>ZOOLO CASINO</h2>
        {% if error %}
        <div class="error">{{error}}</div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label>Usuario</label>
                <input type="text" name="usuario" required autofocus>
            </div>
            <div class="form-group">
                <label>Contrasena</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="btn-login">INICIAR SESION</button>
        </form>
        <div class="info">
            Sistema ZOOLO CASINO v5.6 - Admin Completo
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
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { 
            background: #0a0a0a; color: white; font-family: 'Segoe UI', sans-serif; 
            height: 100%; overflow: hidden; touch-action: manipulation;
        }
        .header {
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 8px 10px; display: flex; justify-content: space-between; align-items: center;
            border-bottom: 2px solid #ffd700; height: 50px; flex-shrink: 0;
        }
        .header-info h3 { color: #ffd700; font-size: 0.9rem; margin: 0; }
        .header-info p { color: #888; font-size: 0.7rem; margin: 0; }
        .monto-box { display: flex; align-items: center; gap: 5px; }
        .monto-box span { font-size: 0.75rem; }
        .monto-box input {
            width: 60px; padding: 5px; border: 1px solid #ffd700; border-radius: 4px;
            background: #000; color: #ffd700; text-align: center; font-weight: bold; font-size: 0.9rem;
        }
        .main-container { 
            display: flex; height: calc(100% - 50px); 
        }
        .left-panel { 
            flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden;
        }
        .special-btns { 
            display: flex; gap: 4px; padding: 6px; background: #111; flex-shrink: 0;
        }
        .btn-esp { 
            flex: 1; padding: 10px 4px; border: none; border-radius: 4px; 
            font-weight: bold; cursor: pointer; color: white; font-size: 0.75rem;
            -webkit-tap-highlight-color: transparent;
        }
        .btn-rojo { background: #c0392b; }
        .btn-negro { background: #2c3e50; border: 1px solid #555; }
        .btn-par { background: #2980b9; }
        .btn-impar { background: #8e44ad; }
        .btn-esp.active { box-shadow: 0 0 8px white; transform: scale(0.95); }
        .animals-grid {
            flex: 1; display: grid; 
            grid-template-columns: repeat(7, 1fr);
            gap: 3px; padding: 5px; overflow-y: auto;
            -webkit-overflow-scrolling: touch;
        }
        .animal-card {
            background: #1a1a2e; border: 2px solid; border-radius: 6px;
            padding: 6px 2px; text-align: center; cursor: pointer; 
            transition: all 0.1s; min-height: 55px; display: flex; flex-direction: column; justify-content: center;
            -webkit-tap-highlight-color: transparent; user-select: none;
            position: relative;
        }
        .animal-card:active { transform: scale(0.95); }
        .animal-card.active { box-shadow: 0 0 10px white; border-color: #ffd700 !important; background: #2a2a4e; }
        .animal-card .num { font-size: 1rem; font-weight: bold; line-height: 1; }
        .animal-card .name { font-size: 0.6rem; color: #aaa; line-height: 1; margin-top: 3px; }
        .animal-card.lechuza::after {
            content: "x70";
            position: absolute;
            top: 2px;
            right: 2px;
            background: #ffd700;
            color: black;
            font-size: 0.5rem;
            padding: 1px 3px;
            border-radius: 2px;
            font-weight: bold;
        }
        .right-panel {
            width: 260px; background: #111; border-left: 1px solid #333;
            display: flex; flex-direction: column; flex-shrink: 0;
        }
        .horarios {
            display: grid; grid-template-columns: repeat(2, 1fr); gap: 3px;
            padding: 5px; max-height: 160px; overflow-y: auto; flex-shrink: 0;
            -webkit-overflow-scrolling: touch;
        }
        .btn-hora {
            padding: 6px 3px; background: #222; border: 1px solid #444;
            border-radius: 4px; color: #ccc; cursor: pointer; 
            font-size: 0.65rem; text-align: center; line-height: 1.3;
            -webkit-tap-highlight-color: transparent; user-select: none;
        }
        .btn-hora.active { background: #27ae60; color: white; font-weight: bold; border-color: #27ae60; }
        .btn-hora.expired { background: #400000; color: #666; text-decoration: line-through; pointer-events: none; }
        .ticket-display {
            flex: 1; background: #000; margin: 0 5px 5px; border-radius: 4px;
            padding: 8px; font-family: monospace; font-size: 0.72rem;
            overflow-y: auto; white-space: pre-wrap; border: 1px solid #333;
            line-height: 1.4; -webkit-overflow-scrolling: touch;
        }
        .action-btns { 
            display: grid; grid-template-columns: repeat(3, 1fr); 
            gap: 3px; padding: 5px; flex-shrink: 0;
        }
        .action-btns button {
            padding: 10px 3px; border: none; border-radius: 4px;
            font-weight: bold; cursor: pointer; font-size: 0.68rem;
            -webkit-tap-highlight-color: transparent;
        }
        .btn-agregar { background: #27ae60; color: white; grid-column: span 3; }
        .btn-vender { background: #2980b9; color: white; grid-column: span 3; }
        .btn-resultados { background: #f39c12; color: black; }
        .btn-caja { background: #16a085; color: white; }
        .btn-pagar { background: #8e44ad; color: white; }
        .btn-anular { background: #c0392b; color: white; }
        .btn-borrar { background: #555; color: white; }
        .btn-salir { background: #333; color: white; grid-column: span 3; }
        
        .modal {
            display: none; position: fixed; top: 0; left: 0;
            width: 100%; height: 100%; background: rgba(0,0,0,0.95);
            z-index: 1000; overflow-y: auto;
        }
        .modal-content {
            background: #1a1a2e; margin: 20px auto; padding: 20px; 
            border-radius: 10px; border: 2px solid #ffd700; 
            max-width: 500px; width: 95%;
        }
        .modal-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #333;
        }
        .modal h3 { color: #ffd700; font-size: 1.1rem; }
        .btn-close {
            background: #c0392b; color: white; border: none; 
            padding: 5px 12px; border-radius: 4px; cursor: pointer;
        }
        
        .tabs { display: flex; gap: 5px; margin-bottom: 15px; border-bottom: 1px solid #444; }
        .tab-btn { 
            background: transparent; border: none; color: #888; 
            padding: 10px 15px; cursor: pointer; font-size: 0.85rem; 
            border-bottom: 2px solid transparent;
        }
        .tab-btn.active { color: #ffd700; border-bottom-color: #ffd700; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        .form-group { margin-bottom: 10px; }
        .form-group label { display: block; color: #888; font-size: 0.8rem; margin-bottom: 4px; }
        .form-group input, .form-group select {
            width: 100%; padding: 8px; background: #000; border: 1px solid #444;
            color: white; border-radius: 4px; font-size: 0.85rem;
        }
        .btn-consultar {
            background: #27ae60; color: white; border: none; padding: 10px;
            width: 100%; border-radius: 4px; font-weight: bold; cursor: pointer;
            margin-top: 10px;
        }
        .stats-box {
            background: #0a0a0a; padding: 15px; border-radius: 8px; margin: 10px 0;
            border: 1px solid #333;
        }
        .stat-row {
            display: flex; justify-content: space-between; padding: 8px 0;
            border-bottom: 1px solid #222; font-size: 0.9rem;
        }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #888; }
        .stat-value { color: #ffd700; font-weight: bold; }
        .stat-value.negative { color: #c0392b; }
        .stat-value.positive { color: #27ae60; }
        
        table { width: 100%; border-collapse: collapse; font-size: 0.75rem; margin-top: 10px; }
        th, td { padding: 6px; text-align: left; border-bottom: 1px solid #333; }
        th { background: #222; color: #ffd700; }
        tr:hover { background: rgba(255,215,0,0.05); }
        
        .alert-box {
            background: rgba(243, 156, 18, 0.2); border: 1px solid #f39c12;
            padding: 10px; border-radius: 4px; margin: 10px 0; font-size: 0.85rem;
        }
        .alert-box strong { color: #f39c12; }

        .resultado-item {
            background: #0a0a0a;
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            border-left: 3px solid #27ae60;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .resultado-item.pendiente {
            border-left-color: #666;
            opacity: 0.6;
        }
        .resultado-numero {
            color: #ffd700;
            font-weight: bold;
            font-size: 1.2rem;
        }
        .resultado-nombre {
            color: #888;
            font-size: 0.9rem;
        }
        
        @media (max-width: 768px) {
            .main-container { flex-direction: column; }
            .right-panel { width: 100%; height: 42vh; border-left: none; border-top: 1px solid #333; }
            .animals-grid { grid-template-columns: repeat(7, 1fr); }
        }
        @media (max-width: 480px) {
            .animals-grid { grid-template-columns: repeat(6, 1fr); }
            .animal-card { min-height: 50px; padding: 4px 1px; }
            .animal-card .num { font-size: 0.9rem; }
            .animal-card .name { font-size: 0.55rem; }
        }
    </style>
</head>
<body>
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
            <div class="ticket-display" id="ticket-display">Selecciona animales y horarios...</div>
            <div class="action-btns">
                <button class="btn-agregar" onclick="agregar()">AGREGAR</button>
                <button class="btn-vender" onclick="vender()">WHATSAPP</button>
                <button class="btn-resultados" onclick="verResultados()">RESULTADOS</button>
                <button class="btn-caja" onclick="verCaja()">CAJA</button>
                <button class="btn-pagar" onclick="pagar()">PAGAR</button>
                <button class="btn-anular" onclick="anular()">ANULAR</button>
                <button class="btn-borrar" onclick="borrarTodo()">BORRAR</button>
                <button class="btn-salir" onclick="location.href='/logout'">SALIR</button>
            </div>
        </div>
    </div>

    <div class="modal" id="modal-caja">
        <div class="modal-content">
            <div class="modal-header">
                <h3>ESTADO DE CAJA</h3>
                <button class="btn-close" onclick="cerrarModal()">X</button>
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
                
                <div style="margin-top: 15px; font-size: 0.75rem; color: #666; text-align: center;">
                    Reglas: Animales x35 | Lechuza(40) x70 | Especiales x2
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
                <button class="btn-consultar" onclick="consultarHistoricoCaja()">CONSULTAR</button>
                
                <div id="resultado-historico" style="display:none; margin-top: 15px;">
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

                    <div style="max-height: 200px; overflow-y: auto; margin-top: 10px;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Fecha</th>
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

    <!-- Modal de Resultados (Solo lectura para agencias) -->
    <div class="modal" id="modal-resultados">
        <div class="modal-content">
            <div class="modal-header">
                <h3>RESULTADOS DEL DÍA</h3>
                <button class="btn-close" onclick="cerrarModalResultados()">X</button>
            </div>
            
            <div style="margin-bottom: 15px; text-align: center; color: #888; font-size: 0.85rem;">
                Solo visualización. Para modificar contactar al administrador.
            </div>

            <div id="lista-resultados" style="max-height: 400px; overflow-y: auto;">
                <p style="color: #888; text-align: center;">Cargando...</p>
            </div>
        </div>
    </div>

    <script>
        let seleccionados = [], especiales = [], horariosSel = [], carrito = [];
        let horasPeru = {{horarios_peru|tojson}};
        let horasVen = {{horarios_venezuela|tojson}};
        
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
            if (btn.classList.contains('expired')) return;
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
            let txt = "=== TICKET ===\\n", total = 0;
            for (let item of carrito) {
                let nom = item.tipo === 'animal' ? item.nombre : item.seleccion;
                txt += item.hora + " | " + item.seleccion + " " + nom + " | S/" + item.monto + "\\n";
                total += item.monto;
            }
            if (horariosSel.length > 0 && (seleccionados.length > 0 || especiales.length > 0)) {
                txt += "\\n--- SELECCION ---\\n";
                let monto = parseFloat(document.getElementById('monto').value) || 5;
                for (let h of horariosSel) {
                    for (let a of seleccionados) {
                        let indicador = a.k === "40" ? " [x70!]" : "";
                        txt += "> " + h + " | " + a.k + " " + a.nombre + indicador + "\\n";
                    }
                    for (let e of especiales) txt += "> " + h + " | " + e + " [x2]\\n";
                }
            }
            txt += "\\nTOTAL: S/" + total;
            document.getElementById('ticket-display').textContent = txt;
        }
        
        function agregar() {
            if (horariosSel.length === 0 || (seleccionados.length === 0 && especiales.length === 0)) {
                alert('Selecciona horario y animal'); return;
            }
            let monto = parseFloat(document.getElementById('monto').value) || 5;
            for (let h of horariosSel) {
                for (let a of seleccionados) carrito.push({hora: h, seleccion: a.k, nombre: a.nombre, monto: monto, tipo: 'animal'});
                for (let e of especiales) carrito.push({hora: h, seleccion: e, nombre: e, monto: monto, tipo: 'especial'});
            }
            seleccionados = []; especiales = []; horariosSel = [];
            document.querySelectorAll('.active').forEach(el => el.classList.remove('active'));
            updateTicket();
        }
        
        function vender() {
            if (carrito.length === 0) { alert('Carrito vacio'); return; }
            let jugadas = carrito.map(c => ({hora: c.hora, seleccion: c.seleccion, monto: c.monto, tipo: c.tipo}));
            fetch('/api/procesar-venta', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({jugadas: jugadas})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) alert('Error: ' + d.error);
                else { window.open(d.url_whatsapp, '_blank'); carrito = []; updateTicket(); }
            })
            .catch(e => alert('Error de conexion: ' + e));
        }

        // Nueva función para ver resultados (solo lectura)
        function verResultados() {
            fetch('/api/resultados-hoy')
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    alert('Error: ' + d.error);
                    return;
                }
                
                let container = document.getElementById('lista-resultados');
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
                                <span style="color: #666;">Pendiente</span>
                                <span style="color: #444; font-size: 0.8rem;">Sin resultado</span>
                            `;
                        }
                        
                        html += `
                            <div class="resultado-item ${clase}">
                                <div style="display: flex; flex-direction: column;">
                                    <strong style="color: #ffd700; font-size: 0.9rem;">${hora}</strong>
                                    <small style="color: #666; font-size: 0.7rem;">Venezuela: ${horasVen[horasPeru.indexOf(hora)]}</small>
                                </div>
                                <div style="text-align: right;">
                                    ${contenido}
                                </div>
                            </div>
                        `;
                    }
                } else {
                    html = '<p style="color: #888; text-align: center;">No hay resultados disponibles</p>';
                }
                
                container.innerHTML = html;
                document.getElementById('modal-resultados').style.display = 'block';
            })
            .catch(e => alert('Error de conexión: ' + e));
        }

        function cerrarModalResultados() {
            document.getElementById('modal-resultados').style.display = 'none';
        }
        
        function verCaja() {
            fetch('/api/caja')
            .then(r => r.json())
            .then(d => {
                if (d.error) { alert(d.error); return; }
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
                    infoDiv.innerHTML = `Tienes <strong>${d.tickets_pendientes}</strong> ticket(s) ganador(es) sin cobrar. Pasa a pagar!`;
                } else {
                    alertaDiv.style.display = 'none';
                }
                
                document.getElementById('modal-caja').style.display = 'block';
            })
            .catch(e => alert('Error: ' + e));
            
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('hist-fecha-inicio').value = hoy;
            document.getElementById('hist-fecha-fin').value = hoy;
        }
        
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
                alert('Seleccione ambas fechas');
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
                    alert('Error: ' + d.error);
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
                        <td>S/${dia.ventas.toFixed(0)}</td>
                        <td style="color:${color}">S/${dia.balance.toFixed(0)}</td>
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
            .catch(e => alert('Error de conexion: ' + e));
        }
        
        function cerrarModal() { 
            document.getElementById('modal-caja').style.display = 'none';
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector('.tab-btn').classList.add('active');
            document.getElementById('tab-hoy').classList.add('active');
        }
        
        function pagar() {
            let serial = prompt('Ingrese SERIAL:'); if (!serial) return;
            fetch('/api/verificar-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) { alert(d.error); return; }
                
                let msg = "=== RESULTADO ===\\n\\n";
                let total = d.total_ganado;
                
                for (let det of d.detalles) {
                    let premioTxt = det.gano ? ('S/' + det.premio.toFixed(2)) : 'No';
                    let especial = det.es_lechuza ? ' 🦉x70!' : '';
                    msg += det.hora + " | " + det.sel + " -> " + premioTxt + especial + "\\n";
                }
                
                msg += "\\nTOTAL GANADO: S/" + total.toFixed(2);
                
                if (total > 0 && confirm(msg + "\\n\\n¿CONFIRMA PAGO?")) {
                    fetch('/api/pagar-ticket', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ticket_id: d.ticket_id})
                    }).then(() => alert('✅ Ticket pagado correctamente'));
                } else {
                    alert(msg);
                }
            });
        }
        
        function anular() {
            let serial = prompt('SERIAL a anular:'); if (!serial) return;
            if (!confirm('¿ANULAR ' + serial + '?')) return;
            fetch('/api/anular-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => { 
                if (d.error) alert('Error: ' + d.error); 
                else alert('✅ ' + d.mensaje); 
            });
        }
        
        function borrarTodo() {
            seleccionados = []; especiales = []; horariosSel = []; carrito = [];
            document.querySelectorAll('.active').forEach(el => el.classList.remove('active'));
            updateTicket();
        }
        
        document.getElementById('modal-caja').addEventListener('click', function(e) {
            if (e.target === this) cerrarModal();
        });

        document.getElementById('modal-resultados').addEventListener('click', function(e) {
            if (e.target === this) cerrarModalResultados();
        });
        
        document.addEventListener('dblclick', function(e) { e.preventDefault(); }, { passive: false });
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
    <title>Panel Admin - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0a0a0a; color: white; font-family: 'Segoe UI', sans-serif; }
        .navbar {
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 10px 15px; display: flex; justify-content: space-between; align-items: center;
            border-bottom: 2px solid #ffd700; flex-wrap: wrap; gap: 10px;
        }
        .navbar h2 { color: #ffd700; font-size: 1.2rem; }
        .nav-tabs { display: flex; gap: 5px; flex-wrap: wrap; }
        .nav-tabs button {
            padding: 8px 12px; background: #333; border: none; color: white;
            cursor: pointer; border-radius: 4px; font-size: 0.8rem;
        }
        .nav-tabs button.active { background: #ffd700; color: black; font-weight: bold; }
        .logout-btn { background: #c0392b !important; }
        .content { padding: 15px; max-width: 1200px; margin: 0 auto; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .stats-grid {
            display: grid; grid-template-columns: repeat(2, 1fr);
            gap: 10px; margin-bottom: 20px;
        }
        .stat-card {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 15px; border-radius: 8px; border: 1px solid #ffd700; text-align: center;
        }
        .stat-card h3 { color: #888; font-size: 0.75rem; margin-bottom: 5px; }
        .stat-card p { color: #ffd700; font-size: 1.3rem; font-weight: bold; }
        .form-box { background: #1a1a2e; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
        .form-box h3 { color: #ffd700; margin-bottom: 10px; font-size: 1rem; }
        .form-row { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; align-items: center; }
        .form-row input, .form-row select {
            flex: 1; min-width: 120px; padding: 8px; background: #000;
            border: 1px solid #444; color: white; border-radius: 4px; font-size: 0.85rem;
        }
        .btn-submit {
            background: #27ae60; color: white; border: none;
            padding: 8px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.85rem;
        }
        .btn-danger {
            background: #c0392b; color: white; border: none;
            padding: 8px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.85rem;
        }
        .btn-secondary {
            background: #2980b9; color: white; border: none;
            padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8rem; margin-right: 5px;
        }
        table { width: 100%; border-collapse: collapse; background: #1a1a2e; border-radius: 8px; overflow: hidden; font-size: 0.8rem; margin-top: 10px; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #333; }
        th { background: #ffd700; color: black; }
        tr:hover { background: rgba(255,215,0,0.1); }
        .riesgo-item {
            background: #1a1a2e; padding: 10px; margin-bottom: 8px;
            border-radius: 4px; border-left: 3px solid #c0392b; font-size: 0.85rem;
        }
        .riesgo-item.lechuza {
            border-left-color: #ffd700;
            background: rgba(255, 215, 0, 0.1);
        }
        .riesgo-item b { color: #ffd700; }
        .mensaje {
            padding: 10px; margin: 10px 0; border-radius: 4px; display: none;
            font-size: 0.85rem;
        }
        .mensaje.success { background: rgba(39,174,96,0.3); border: 1px solid #27ae60; display: block; }
        .mensaje.error { background: rgba(192,57,43,0.3); border: 1px solid #c0392b; display: block; }
        .info-pago {
            background: #0a0a0a; padding: 10px; border-radius: 4px; margin: 10px 0;
            font-size: 0.8rem; color: #888; text-align: center;
            border: 1px solid #333;
        }
        .sorteo-actual-box {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 15px; border-radius: 8px; margin-bottom: 15px;
            border: 2px solid #2980b9; text-align: center;
        }
        .sorteo-actual-box h4 { color: #2980b9; margin-bottom: 5px; }
        .sorteo-actual-box p { color: #ffd700; font-size: 1.5rem; font-weight: bold; }
        .resultado-item {
            background: #0a0a0a; padding: 10px; margin: 5px 0;
            border-radius: 5px; border-left: 3px solid #27ae60;
            display: flex; justify-content: space-between; align-items: center;
        }
        .resultado-item.pendiente {
            border-left-color: #666; opacity: 0.6;
        }
        .resultado-numero { color: #ffd700; font-weight: bold; font-size: 1.2rem; }
        .resultado-nombre { color: #888; font-size: 0.9rem; }
        @media (min-width: 768px) {
            .stats-grid { grid-template-columns: repeat(4, 1fr); }
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h2>PANEL ADMIN</h2>
        <div class="nav-tabs">
            <button onclick="showTab('dashboard')" class="active">Dashboard</button>
            <button onclick="showTab('historico')">Histórico</button>
            <button onclick="showTab('riesgo')">Riesgo</button>
            <button onclick="showTab('reporte')">Reporte</button>
            <button onclick="showTab('resultados')">Resultados</button>
            <button onclick="showTab('anular')">Anular Ticket</button>
            <button onclick="showTab('agencias')">Agencias</button>
            <button onclick="location.href='/logout'" class="logout-btn">Salir</button>
        </div>
    </div>
    <div class="content">
        <div id="mensaje" class="mensaje"></div>
        
        <div class="info-pago">
            💰 REGLAS: Animales (00-39) = x35 | Lechuza (40) = x70 | Especiales = x2
        </div>
        
        <div id="dashboard" class="tab-content active">
            <h3 style="color: #ffd700; margin-bottom: 15px;">RESUMEN DE HOY</h3>
            <div class="stats-grid">
                <div class="stat-card"><h3>VENTAS</h3><p id="stat-ventas">S/0</p></div>
                <div class="stat-card"><h3>PREMIOS</h3><p id="stat-premios">S/0</p></div>
                <div class="stat-card"><h3>COMISIONES</h3><p id="stat-comisiones">S/0</p></div>
                <div class="stat-card"><h3>BALANCE</h3><p id="stat-balance">S/0</p></div>
            </div>
        </div>

        <div id="historico" class="tab-content">
            <div class="form-box">
                <h3>CONSULTA HISTÓRICA POR RANGO</h3>
                <div class="form-row">
                    <input type="date" id="hist-fecha-inicio" value="">
                    <input type="date" id="hist-fecha-fin" value="">
                    <button class="btn-submit" onclick="consultarHistorico()">CONSULTAR</button>
                </div>
                <div class="form-row" style="margin-top: 10px;">
                    <button class="btn-secondary" onclick="setRango('hoy')">Hoy</button>
                    <button class="btn-secondary" onclick="setRango('ayer')">Ayer</button>
                    <button class="btn-secondary" onclick="setRango('semana')">Últimos 7 días</button>
                    <button class="btn-secondary" onclick="setRango('mes')">Este mes</button>
                </div>
                
                <div id="historico-resumen" style="display:none;">
                    <div class="stats-grid" style="margin-top: 15px;">
                        <div class="stat-card"><h3>TOTAL VENTAS</h3><p id="hist-total-ventas">S/0</p></div>
                        <div class="stat-card"><h3>TOTAL PREMIOS</h3><p id="hist-total-premios">S/0</p></div>
                        <div class="stat-card"><h3>TOTAL TICKETS</h3><p id="hist-total-tickets">0</p></div>
                        <div class="stat-card"><h3>BALANCE</h3><p id="hist-total-balance">S/0</p></div>
                    </div>

                    <h3 style="color: #ffd700; margin: 20px 0 10px;">DETALLE POR DÍA</h3>
                    <div style="overflow-x: auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Fecha</th>
                                    <th>Tickets</th>
                                    <th>Ventas</th>
                                    <th>Premios</th>
                                    <th>Comisiones</th>
                                    <th>Balance</th>
                                </tr>
                            </thead>
                            <tbody id="tabla-historico"></tbody>
                        </table>
                    </div>

                    <h3 style="color: #ffd700; margin: 20px 0 10px;">TOP ANIMALES DEL PERÍODO</h3>
                    <div id="top-animales-hist" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px;">
                        <p style="color: #888;">Cargando...</p>
                    </div>
                </div>
            </div>
        </div>

        <div id="riesgo" class="tab-content">
            <div class="sorteo-actual-box">
                <h4>🎯 SORTEO EN CURSO / PRÓXIMO</h4>
                <p id="sorteo-objetivo">Cargando...</p>
                <small style="color: #888; font-size: 0.8rem;">Riesgo calculado solo para este horario específico</small>
            </div>
            
            <h3 style="color: #ffd700; margin-bottom: 15px; font-size: 1rem;">
                APUESTAS PARA ESTE SORTEO: <span id="total-apostado-sorteo" style="color: white;">S/0</span>
            </h3>
            <div id="lista-riesgo"><p style="color: #888; font-size: 0.85rem;">Cargando...</p></div>
            
            <div style="margin-top: 20px; padding: 10px; background: rgba(192, 57, 43, 0.1); border-radius: 4px; border: 1px solid #c0392b;">
                <small style="color: #ff6b6b;">
                    ⚠️ Este riesgo se resetea automáticamente cuando pasa el sorteo y comienza el siguiente horario. No acumula jugadas de otros sorteos.
                </small>
            </div>
        </div>

        <div id="reporte" class="tab-content">
            <h3 style="color: #ffd700; margin-bottom: 15px; font-size: 1rem;">REPORTE POR AGENCIA (HOY)</h3>
            <div style="overflow-x: auto;">
                <table>
                    <thead><tr><th>Agencia</th><th>Ventas</th><th>Premios</th><th>Comision</th><th>Balance</th></tr></thead>
                    <tbody id="tabla-reporte"><tr><td colspan="5" style="text-align:center;color:#888;">Cargando...</td></tr></tbody>
                </table>
            </div>
        </div>

        <div id="resultados" class="tab-content">
            <!-- NUEVO: Lista de resultados del día -->
            <div class="form-box">
                <h3>RESULTADOS DEL DÍA</h3>
                <div id="lista-resultados-admin" style="max-height: 300px; overflow-y: auto; margin-bottom: 15px;">
                    <p style="color: #888;">Cargando...</p>
                </div>
            </div>

            <div class="form-box">
                <h3>CARGAR/EDITAR RESULTADO</h3>
                <div class="form-row">
                    <select id="res-hora">{% for h in horarios %}<option value="{{h}}">{{h}}</option>{% endfor %}</select>
                    <select id="res-animal">{% for k, v in animales.items() %}<option value="{{k}}">{{k}} - {{v}}</option>{% endfor %}</select>
                    <button class="btn-submit" onclick="guardarResultado()">GUARDAR</button>
                </div>
                <div style="margin-top: 10px; font-size: 0.8rem; color: #888;">
                    ℹ️ Si el resultado ya existe, se actualizará automáticamente.
                </div>
            </div>
        </div>

        <!-- NUEVA PESTAÑA: Anular Ticket -->
        <div id="anular" class="tab-content">
            <div class="form-box">
                <h3>ANULAR TICKET</h3>
                <div class="form-row">
                    <input type="text" id="anular-serial" placeholder="Ingrese SERIAL del ticket" style="flex: 2;">
                    <button class="btn-danger" onclick="anularTicketAdmin()">ANULAR TICKET</button>
                </div>
                <div style="margin-top: 15px; padding: 10px; background: rgba(192, 57, 43, 0.1); border-radius: 4px; border: 1px solid #c0392b;">
                    <small style="color: #ff6b6b;">
                        ⚠️ Solo se pueden anular tickets que no estén pagados y cuyo sorteo no haya iniciado aún.
                    </small>
                </div>
                <div id="resultado-anular" style="margin-top: 10px; font-size: 0.9rem;"></div>
            </div>
        </div>

        <div id="agencias" class="tab-content">
            <div class="form-box">
                <h3>CREAR AGENCIA</h3>
                <div class="form-row">
                    <input type="text" id="new-usuario" placeholder="Usuario">
                    <input type="password" id="new-password" placeholder="Contrasena">
                    <input type="text" id="new-nombre" placeholder="Nombre">
                    <button class="btn-submit" onclick="crearAgencia()">CREAR</button>
                </div>
            </div>
            <h3 style="color: #ffd700; margin-bottom: 10px; font-size: 1rem;">AGENCIAS</h3>
            <div style="overflow-x: auto;">
                <table>
                    <thead><tr><th>ID</th><th>Usuario</th><th>Nombre</th><th>Comision</th></tr></thead>
                    <tbody id="tabla-agencias"><tr><td colspan="4" style="text-align:center;color:#888;">Cargando...</td></tr></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let historicoData = null;
        let fechasConsulta = { inicio: null, fin: null };

        function showTab(tab) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-tabs button').forEach(b => b.classList.remove('active'));
            document.getElementById(tab).classList.add('active');
            event.target.classList.add('active');
            
            if (tab === 'riesgo') cargarRiesgo();
            if (tab === 'reporte') cargarReporte();
            if (tab === 'agencias') cargarAgencias();
            if (tab === 'dashboard') cargarDashboard();
            if (tab === 'resultados') cargarResultadosAdmin();
        }

        function showMensaje(msg, tipo) {
            let div = document.getElementById('mensaje');
            div.textContent = msg; 
            div.className = 'mensaje ' + tipo;
            setTimeout(() => div.className = 'mensaje', 3000);
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
                        <td>S/${dia.ventas.toFixed(2)}</td>
                        <td>S/${dia.premios.toFixed(2)}</td>
                        <td>S/${dia.comisiones.toFixed(2)}</td>
                        <td style="color:${color}; font-weight:bold">S/${dia.balance.toFixed(2)}</td>
                    </tr>`;
                });
                tbody.innerHTML = html;
                
                cargarTopAnimalesHistorico(inicio, fin);
            })
            .catch(e => showMensaje('Error de conexión', 'error'));
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
                    
                    html += `<div class="${clase}" style="margin-bottom: 0;">
                        <b>${medalla} ${a.numero} - ${a.nombre}${extra}</b><br>
                        <small>Apostado: S/${a.total_apostado} | Si sale pagaría: S/${a.pago_potencial}</small>
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
            fetch('/admin/riesgo').then(r => r.json()).then(d => {
                // Actualizar sorteo objetivo
                if (d.sorteo_objetivo) {
                    document.getElementById('sorteo-objetivo').textContent = d.sorteo_objetivo;
                    document.getElementById('total-apostado-sorteo').textContent = 'S/' + (d.total_apostado || 0).toFixed(2);
                } else {
                    document.getElementById('sorteo-objetivo').textContent = 'No hay más sorteos hoy';
                    document.getElementById('total-apostado-sorteo').textContent = 'S/0';
                }
                
                let container = document.getElementById('lista-riesgo');
                if (!d.riesgo || Object.keys(d.riesgo).length === 0) {
                    container.innerHTML = '<p style="color:#888; font-size: 0.85rem;">No hay apuestas para este sorteo</p>'; 
                    return;
                }
                let html = '';
                for (let [k, v] of Object.entries(d.riesgo)) {
                    let clase = v.es_lechuza ? 'riesgo-item lechuza' : 'riesgo-item';
                    let extra = v.es_lechuza ? ' ⚠️ ALTO RIESGO (x70)' : '';
                    html += `<div class="${clase}"><b>${k}${extra}</b><br>Apostado: S/${v.apostado.toFixed(2)} | Pagaria: S/${v.pagaria.toFixed(2)} | ${v.porcentaje}% del total</div>`;
                }
                container.innerHTML = html;
            });
        }

        function cargarReporte() {
            fetch('/admin/reporte-agencias').then(r => r.json()).then(d => {
                let tbody = document.getElementById('tabla-reporte');
                if (!d.agencias || d.agencias.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No hay agencias</td></tr>'; 
                    return;
                }
                let html = '';
                for (let a of d.agencias) {
                    html += '<tr><td>' + a.nombre + '</td><td>S/' + a.ventas.toFixed(2) + '</td><td>S/' + a.premios.toFixed(2) + '</td><td>S/' + a.comision.toFixed(2) + '</td><td style="color:' + (a.balance >= 0 ? '#27ae60' : '#c0392b') + '">S/' + a.balance.toFixed(2) + '</td></tr>';
                }
                html += '<tr style="background:rgba(255,215,0,0.2);font-weight:bold;"><td>TOTAL</td><td>S/' + d.global.ventas.toFixed(2) + '</td><td>S/' + d.global.pagos.toFixed(2) + '</td><td>S/' + d.global.comisiones.toFixed(2) + '</td><td>S/' + d.global.balance.toFixed(2) + '</td></tr>';
                tbody.innerHTML = html;
            });
        }

        // NUEVA FUNCIÓN: Cargar resultados del día en admin
        function cargarResultadosAdmin() {
            fetch('/admin/resultados-hoy')
            .then(r => r.json())
            .then(d => {
                let container = document.getElementById('lista-resultados-admin');
                if (d.error) {
                    container.innerHTML = '<p style="color: #c0392b;">Error al cargar</p>';
                    return;
                }
                
                let html = '';
                if (d.resultados && Object.keys(d.resultados).length > 0) {
                    for (let hora of Object.keys(d.resultados).sort()) {
                        let resultado = d.resultados[hora];
                        let clase = resultado ? '' : 'pendiente';
                        let contenido;
                        
                        if (resultado) {
                            contenido = `
                                <span class="resultado-numero">${resultado.animal}</span>
                                <span class="resultado-nombre">${resultado.nombre}</span>
                                <span style="color: #27ae60; font-size: 0.8rem;">✓ Cargado</span>
                            `;
                        } else {
                            contenido = `
                                <span style="color: #666;">Pendiente</span>
                                <span style="color: #444; font-size: 0.8rem;">Sin resultado</span>
                            `;
                        }
                        
                        html += `
                            <div class="resultado-item ${clase}">
                                <div style="display: flex; flex-direction: column;">
                                    <strong style="color: #ffd700; font-size: 0.9rem;">${hora}</strong>
                                </div>
                                <div style="text-align: right; display: flex; flex-direction: column; align-items: flex-end;">
                                    ${contenido}
                                </div>
                            </div>
                        `;
                    }
                } else {
                    html = '<p style="color: #888; text-align: center;">No hay resultados disponibles</p>';
                }
                container.innerHTML = html;
            })
            .catch(() => {
                document.getElementById('lista-resultados-admin').innerHTML = '<p style="color: #c0392b;">Error de conexión</p>';
            });
        }

        function guardarResultado() {
            let form = new FormData();
            form.append('hora', document.getElementById('res-hora').value);
            form.append('animal', document.getElementById('res-animal').value);
            fetch('/admin/guardar-resultado', {method: 'POST', body: form})
            .then(r => r.json()).then(d => {
                if (d.status === 'ok') {
                    showMensaje('Guardado', 'success');
                    cargarResultadosAdmin(); // Recargar la lista
                }
                else showMensaje(d.error || 'Error', 'error');
            });
        }

        // NUEVA FUNCIÓN: Anular ticket desde admin
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
                    resultadoDiv.innerHTML = '<span style="color: #c0392b;">❌ ' + d.error + '</span>';
                    showMensaje(d.error, 'error');
                } else {
                    resultadoDiv.innerHTML = '<span style="color: #27ae60;">✅ ' + d.mensaje + '</span>';
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
                if (!d || d.length === 0) { tbody.innerHTML = '<tr><td colspan="4">No hay agencias</td></tr>'; return; }
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
                    showMensaje('Creada', 'success');
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
        });

        cargarDashboard();
    </script>
</body>
</html>
'''

# ==================== MAIN ====================
if __name__ == '__main__':
    print("=" * 60)
    print("  ZOOLO CASINO CLOUD v5.6 - Admin Completo")
    print("  RIESGO POR SORTEO ACTIVO (No acumulativo)")
    print("=" * 60)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
