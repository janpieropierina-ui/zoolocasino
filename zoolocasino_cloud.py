#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v5.4 - Ticket Compacto (CORREGIDO)
"""

import os
import sys
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from flask import Flask, render_template_string, request, session, redirect, jsonify

# ==================== CONFIGURACION ====================
# IMPORTANTE: Configura estas variables en tu servidor (Render)
# O cámbialas aquí directamente si es para pruebas locales

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://iuwgbtmhkqnqulwgcgkk.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml1d2didG1oa3FucXVsd2djZ2trIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEwMTM0OTQsImV4cCI6MjA4NjU4OTQ5NH0.HJGQk5JppC34OHWhQY9Goou617uxB1QVuIQLD72NLgE')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'zoolo_casino_cloud_2025_seguro')

# Configuración de negocio
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

# Animales
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

def calcular_premio_animal(monto, numero):
    """Calcula premio: Lechuza(40) paga x70, otros x35"""
    if str(numero) == "40":
        return monto * PAGO_LECHUZA
    return monto * PAGO_ANIMAL_NORMAL

def supabase_request(table, method="GET", data=None, filters=None):
    """Hace peticiones a Supabase"""
    try:
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
                
    except Exception as e:
        print(f"Error Supabase: {e}")
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
        
        # Guardar ticket
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
        
        # Guardar jugadas
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
        # Agrupar por hora
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
            
            # Formato compacto de hora: 09:00 AM -> 09:am
            hora_peru_corta = hora_peru.replace(' ', '').replace('00', '').lower()
            hora_ven_corta = hora_ven.replace(' ', '').replace('00', '').lower()
            
            lineas.append(f"*ZOOLO.PERU/{hora_peru_corta}...VZLA/{hora_ven_corta}*")
            
            # Juntar todas las jugadas de esta hora
            jugadas_hora = jugadas_por_hora[hora_peru]
            texto_jugadas = []
            
            for j in jugadas_hora:
                if j['tipo'] == 'animal':
                    # Abreviatura: 3 primeras letras + numero x monto
                    nombre = ANIMALES.get(j['seleccion'], '')
                    abrev = nombre[0:3].upper() if nombre else 'ANI'
                    texto_jugadas.append(f"{abrev}{j['seleccion']}x{int(j['monto'])}")
                else:
                    # Especial: ROJ, NEG, PAR, IMP
                    abrev = j['seleccion'][0:3]
                    texto_jugadas.append(f"{abrev}x{int(j['monto'])}")
            
            lineas.append(" ".join(texto_jugadas))
            lineas.append("")  # Línea en blanco entre horarios
        
        lineas.append("------------------------")
        lineas.append(f"*TOTAL: S/{int(total)}*")
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
        print(f"Error en procesar_venta: {e}")
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
@agencia_required
def anular_ticket():
    try:
        serial = request.json.get('serial')
        tickets = supabase_request("tickets", filters={"serial": serial})
        if not tickets or len(tickets) == 0:
            return jsonify({'error': 'Ticket no existe'})
        
        ticket = tickets[0]
        if ticket['pagado']:
            return jsonify({'error': 'Ya esta pagado'})
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?id=eq.{ticket['id']}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        data = json.dumps({"anulado": True}).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
        urllib.request.urlopen(req, timeout=15)
        return jsonify({'status': 'ok', 'mensaje': 'Ticket anulado'})
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{hoy}%25&anulado=eq.false"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        
        apuestas = {}
        for t in tickets:
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id'], "tipo": "animal"})
            for j in jugadas:
                sel = j['seleccion']
                if sel not in apuestas:
                    apuestas[sel] = 0
                apuestas[sel] += j['monto']
        
        apuestas_ordenadas = sorted(apuestas.items(), key=lambda x: x[1], reverse=True)
        
        riesgo = {}
        for sel, monto in apuestas_ordenadas:
            nombre = ANIMALES.get(sel, sel)
            multiplicador = PAGO_LECHUZA if sel == "40" else PAGO_ANIMAL_NORMAL
            riesgo[f"{sel} - {nombre}"] = {
                "apostado": round(monto, 2),
                "pagaria": round(monto * multiplicador, 2),
                "es_lechuza": sel == "40"
            }
        
        return jsonify({'riesgo': riesgo})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== TEMPLATES ====================
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
        }
        .animal-card {
            background: #1a1a2e; border: 2px solid; border-radius: 6px;
            padding: 6px 2px; text-align: center; cursor: pointer; 
            min-height: 55px; display: flex; flex-direction: column; justify-content: center;
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
        }
        .btn-hora {
            padding: 6px 3px; background: #222; border: 1px solid #444;
            border-radius: 4px; color: #ccc; cursor: pointer; 
            font-size: 0.65rem; text-align: center; line-height: 1.3;
        }
        .btn-hora.active { background: #27ae60; color: white; font-weight: bold; border-color: #27ae60; }
        .btn-hora.expired { background: #400000; color: #666; text-decoration: line-through; pointer-events: none; }
        .ticket-display {
            flex: 1; background: #000; margin: 0 5px 5px; border-radius: 4px;
            padding: 8px; font-family: monospace; font-size: 0.72rem;
            overflow-y: auto; white-space: pre-wrap; border: 1px solid #333;
            line-height: 1.4;
        }
        .action-btns { 
            display: grid; grid-template-columns: repeat(3, 1fr); 
            gap: 3px; padding: 5px; flex-shrink: 0;
        }
        .action-btns button {
            padding: 10px 3px; border: none; border-radius: 4px;
            font-weight: bold; cursor: pointer; font-size: 0.68rem;
        }
        .btn-agregar { background: #27ae60; color: white; grid-column: span 3; }
        .btn-vender { background: #2980b9; color: white; grid-column: span 3; }
        .btn-caja { background: #f39c12; color: black; }
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
        .alert-box {
            background: rgba(243, 156, 18, 0.2); border: 1px solid #f39c12;
            padding: 10px; border-radius: 4px; margin: 10px 0; font-size: 0.85rem;
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
                        <span class="stat-label">Premios:</span>
                        <span class="stat-value negative" id="caja-premios">S/0.00</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Comisión:</span>
                        <span class="stat-value" id="caja-comision">S/0.00</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Balance:</span>
                        <span class="stat-value" id="caja-balance">S/0.00</span>
                    </div>
                </div>
                <div id="alerta-pendientes" class="alert-box" style="display:none;">
                    <strong>⚠️ Pendientes:</strong>
                    <div id="info-pendientes"></div>
                </div>
            </div>
            <div id="tab-historico" class="tab-content">
                <div style="margin-bottom:10px;">
                    <label style="color:#888;font-size:0.8rem;">Desde:</label>
                    <input type="date" id="hist-fecha-inicio" style="width:100%;padding:8px;background:#000;border:1px solid #444;color:white;border-radius:4px;">
                </div>
                <div style="margin-bottom:10px;">
                    <label style="color:#888;font-size:0.8rem;">Hasta:</label>
                    <input type="date" id="hist-fecha-fin" style="width:100%;padding:8px;background:#000;border:1px solid #444;color:white;border-radius:4px;">
                </div>
                <button onclick="consultarHistoricoCaja()" style="width:100%;padding:10px;background:#27ae60;color:white;border:none;border-radius:4px;font-weight:bold;cursor:pointer;">CONSULTAR</button>
                <div id="resultado-historico" style="display:none;margin-top:15px;">
                    <div class="stats-box">
                        <div class="stat-row">
                            <span class="stat-label">Ventas:</span>
                            <span class="stat-value" id="hist-ventas">S/0.00</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Balance:</span>
                            <span class="stat-value" id="hist-balance">S/0.00</span>
                        </div>
                    </div>
                </div>
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
                    for (let a of seleccionados) txt += "> " + h + " | " + a.k + " " + a.nombre + "\\n";
                    for (let e of especiales) txt += "> " + h + " | " + e + "\\n";
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
                if (d.tickets_pendientes > 0) {
                    alertaDiv.style.display = 'block';
                    document.getElementById('info-pendientes').innerHTML = `Tienes <strong>${d.tickets_pendientes}</strong> ticket(s) ganador(es) sin cobrar.`;
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
            if (!inicio || !fin) { alert('Seleccione fechas'); return; }
            fetch('/api/caja-historico', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})
            })
            .then(r => r.json())
            .then(d =>
