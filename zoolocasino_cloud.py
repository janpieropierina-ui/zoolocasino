#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v5.1 - Sistema en la Nube con Supabase + ESTADÍSTICAS HISTÓRICAS
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

# ==================== CONFIGURACION SUPABASE ====================
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://iuwgbtmhkqnqulwgcgkk.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml1d2didG1oa3FucXVsd2djZ2trIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEwMTM0OTQsImV4cCI6MjA4NjU4OTQ5NH0.HJGQk5JppC34OHWhQY9Goou617uxB1QVuIQLD72NLgE')

app = Flask(__name__)
app.secret_key = "zoolo_casino_cloud_2025"

# Configuracion de negocio
PAGO_ANIMAL = 35
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
    """Convierte 'DD/MM/YYYY HH:MM AM/PM' a datetime"""
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

def supabase_request(table, method="GET", data=None, filters=None):
    """Hace peticiones a Supabase REST API"""
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

# ==================== API POS (sin cambios) ====================
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
        
        lineas = [
            f"*{session['nombre_agencia']}*",
            f"*Serial:* {serial}",
            f"*Ticket N:* {ticket_id}",
            "",
            "*--- JUEGA Y GANA ---*",
            ""
        ]
        
        for j in jugadas:
            idx = HORARIOS_PERU.index(j['hora'])
            hora_ven = HORARIOS_VENEZUELA[idx]
            if j['tipo'] == 'animal':
                nombre = ANIMALES.get(j['seleccion'], j['seleccion'])
                lineas.append(f"{j['hora']} PERU / {hora_ven} VEN")
                lineas.append(f"{j['seleccion']} - {nombre}")
                lineas.append(f"Apuesta: S/{j['monto']}")
                lineas.append("")
            else:
                lineas.append(f"{j['hora']} PERU / {hora_ven} VEN")
                lineas.append(f"*{j['seleccion']}*")
                lineas.append(f"Apuesta: S/{j['monto']}")
                lineas.append("")
        
        lineas.append(f"*TOTAL: S/{total}*")
        lineas.append("")
        lineas.append("Buena Suerte!")
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
                    premio = j['monto'] * PAGO_ANIMAL
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
                'premio': premio
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
        for t in tickets:
            if t['agencia_id'] == session['user_id'] and t['pagado']:
                jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                resultados_list = supabase_request("resultados", filters={"fecha": hoy})
                resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
                
                for j in jugadas:
                    wa = resultados.get(j['hora'])
                    if wa:
                        if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                            premios += j['monto'] * PAGO_ANIMAL
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
            'balance': round(balance, 2)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== API ADMIN ACTUALIZADA CON ESTADÍSTICAS ====================
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
                                premios += j['monto'] * PAGO_ANIMAL
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
            riesgo[f"{sel} - {nombre}"] = {
                "apostado": round(monto, 2),
                "pagaria": round(monto * PAGO_ANIMAL, 2)
            }
        
        return jsonify({'riesgo': riesgo})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== NUEVAS RUTAS DE ESTADÍSTICAS HISTÓRICAS ====================
@app.route('/admin/estadisticas-rango', methods=['POST'])
@admin_required
def estadisticas_rango():
    """Obtiene estadísticas detalladas por día en un rango de fechas"""
    try:
        data = request.get_json()
        fecha_inicio = data.get('fecha_inicio')  # YYYY-MM-DD
        fecha_fin = data.get('fecha_fin')        # YYYY-MM-DD
        
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fechas requeridas'}), 400
        
        dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
        
        # Consultar todos los tickets (limitado a 1000 más recientes para rendimiento)
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=1000"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            all_tickets = json.loads(response.read().decode())
        
        # Filtrar por rango y agrupar por día
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
        
        # Calcular premios para cada día (esto es pesado pero necesario para precisión)
        # Optimización: Consultar todos los resultados del rango una sola vez
        resultados_por_dia = {}
        delta = dt_fin - dt_inicio
        for i in range(delta.days + 1):
            dia_str = (dt_inicio + timedelta(days=i)).strftime("%d/%m/%Y")
            resultados_list = supabase_request("resultados", filters={"fecha": dia_str})
            if resultados_list:
                resultados_por_dia[dia_str] = {r['hora']: r['animal'] for r in resultados_list}
        
        # Procesar premios por día
        resumen_dias = []
        total_ventas = total_premios = total_tickets = 0
        
        for dia_key in sorted(dias_data.keys()):
            datos = dias_data[dia_key]
            resultados_dia = resultados_por_dia.get(dia_key, {})
            
            # Calcular premios del día consultando jugadas de los tickets de ese día
            premios_dia = 0
            # Limitar a 50 tickets por día para no saturar
            for ticket_id in datos['ids_tickets'][:50]:
                jugadas = supabase_request("jugadas", filters={"ticket_id": ticket_id})
                ticket_info = next((t for t in tickets_rango if t['id'] == ticket_id), None)
                
                if ticket_info and ticket_info['pagado']:
                    for j in jugadas:
                        wa = resultados_dia.get(j['hora'])
                        if wa:
                            if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                                premios_dia += j['monto'] * PAGO_ANIMAL
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
    """Obtiene los animales más jugados en un rango de fechas"""
    try:
        data = request.get_json()
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fechas requeridas'}), 400
        
        dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
        
        # Consultar tickets del rango
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=500"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            all_tickets = json.loads(response.read().decode())
        
        # Filtrar tickets del rango y obtener sus IDs
        ticket_ids = []
        for t in all_tickets:
            if t.get('anulado'):
                continue
            dt_ticket = parse_fecha_ticket(t['fecha'])
            if dt_ticket and dt_inicio <= dt_ticket <= dt_fin:
                ticket_ids.append(t['id'])
        
        if not ticket_ids:
            return jsonify({'top_animales': []})
        
        # Consultar jugadas de tipo animal para estos tickets
        # Nota: En una implementación real ideal, usarías una función SQL o RPC
        apuestas = {}
        for ticket_id in ticket_ids[:100]:  # Limitar para rendimiento
            jugadas = supabase_request("jugadas", filters={"ticket_id": ticket_id, "tipo": "animal"})
            for j in jugadas:
                sel = j['seleccion']
                if sel not in apuestas:
                    apuestas[sel] = {'monto': 0, 'cantidad': 0}
                apuestas[sel]['monto'] += j['monto']
                apuestas[sel]['cantidad'] += 1
        
        # Ordenar por monto apostado
        top = sorted(apuestas.items(), key=lambda x: x[1]['monto'], reverse=True)
        resultado = []
        
        for sel, data in top[:20]:  # Top 20
            nombre = ANIMALES.get(sel, sel)
            resultado.append({
                'numero': sel,
                'nombre': nombre,
                'total_apostado': round(data['monto'], 2),
                'cantidad_jugadas': data['cantidad']
            })
        
        return jsonify({'top_animales': resultado})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/exportar-csv', methods=['POST'])
@admin_required
def exportar_csv():
    """Exporta datos históricos a CSV"""
    try:
        data = request.get_json()
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        tipo = data.get('tipo', 'ventas')  # ventas, jugadas, resultados
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        if tipo == 'ventas':
            writer.writerow(['Fecha', 'Ticket ID', 'Serial', 'Agencia ID', 'Total', 'Estado', 'Fecha_Hora'])
            
            dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
            
            url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=1000"
            headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                tickets = json.loads(response.read().decode())
            
            for t in tickets:
                dt_ticket = parse_fecha_ticket(t['fecha'])
                if dt_ticket and dt_inicio <= dt_ticket <= dt_fin:
                    estado = 'Anulado' if t['anulado'] else ('Pagado' if t['pagado'] else 'Pendiente')
                    writer.writerow([
                        dt_ticket.strftime("%d/%m/%Y"),
                        t['id'],
                        t['serial'],
                        t['agencia_id'],
                        t['total'],
                        estado,
                        t['fecha']
                    ])
        
        elif tipo == 'resultados':
            writer.writerow(['Fecha', 'Hora', 'Animal Ganador'])
            delta = dt_fin - dt_inicio
            for i in range(delta.days + 1):
                dia_str = (dt_inicio + timedelta(days=i)).strftime("%d/%m/%Y")
                resultados = supabase_request("resultados", filters={"fecha": dia_str})
                if resultados:
                    for r in resultados:
                        writer.writerow([r['fecha'], r['hora'], r['animal']])
        
        output.seek(0)
        return jsonify({
            'csv': output.getvalue(),
            'filename': f"{tipo}_{fecha_inicio}_{fecha_fin}.csv"
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== TEMPLATES HTML ACTUALIZADOS ====================
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
            Sistema ZOOLO CASINO v5.1
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
        }
        .animal-card:active { transform: scale(0.95); }
        .animal-card.active { box-shadow: 0 0 10px white; border-color: #ffd700 !important; background: #2a2a4e; }
        .animal-card .num { font-size: 1rem; font-weight: bold; line-height: 1; }
        .animal-card .name { font-size: 0.6rem; color: #aaa; line-height: 1; margin-top: 3px; }
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
        .btn-caja { background: #f39c12; color: black; }
        .btn-pagar { background: #8e44ad; color: white; }
        .btn-anular { background: #c0392b; color: white; }
        .btn-borrar { background: #555; color: white; }
        .btn-salir { background: #333; color: white; grid-column: span 3; }
        .modal {
            display: none; position: fixed; top: 0; left: 0;
            width: 100%; height: 100%; background: rgba(0,0,0,0.9);
            z-index: 1000; align-items: center; justify-content: center;
        }
        .modal-content {
            background: #1a1a2e; padding: 20px; border-radius: 10px;
            border: 2px solid #ffd700; max-width: 320px; width: 90%;
        }
        .modal h3 { color: #ffd700; margin-bottom: 15px; font-size: 1.1rem; }
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
    <div class="modal" id="modal-caja" onclick="if(event.target===this)cerrarModal()">
        <div class="modal-content">
            <h3>ESTADO DE CAJA</h3>
            <p>Ventas: S/<span id="caja-ventas">0</span></p>
            <p>Premios: S/<span id="caja-premios">0</span></p>
            <p>Comision: S/<span id="caja-comision">0</span></p>
            <hr style="border-color: #444; margin: 10px 0;">
            <p><strong>Balance: S/<span id="caja-balance">0</span></strong></p>
            <button onclick="cerrarModal()" style="width:100%;padding:12px;background:#555;color:white;border:none;border-radius:4px;margin-top:15px;font-weight:bold;">CERRAR</button>
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
                document.getElementById('caja-ventas').textContent = d.ventas.toFixed(2);
                document.getElementById('caja-premios').textContent = d.premios.toFixed(2);
                document.getElementById('caja-comision').textContent = d.comision.toFixed(2);
                document.getElementById('caja-balance').textContent = d.balance.toFixed(2);
                document.getElementById('modal-caja').style.display = 'flex';
            })
            .catch(e => alert('Error: ' + e));
        }
        
        function cerrarModal() { document.getElementById('modal-caja').style.display = 'none'; }
        
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
                let msg = "GANADO: S/" + d.total_ganado.toFixed(2) + "\\n\\n";
                for (let det of d.detalles) msg += det.hora + " | " + det.sel + " -> " + (det.gano ? 'SI' : 'NO') + "\\n";
                if (d.total_ganado > 0 && confirm(msg + "\\n¿PAGAR?")) {
                    fetch('/api/pagar-ticket', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ticket_id: d.ticket_id})
                    }).then(() => alert('Ticket pagado'));
                } else alert(msg);
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
            .then(d => { if (d.error) alert(d.error); else alert('Anulado'); });
        }
        
        function borrarTodo() {
            seleccionados = []; especiales = []; horariosSel = []; carrito = [];
            document.querySelectorAll('.active').forEach(el => el.classList.remove('active'));
            updateTicket();
        }
        
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
        .riesgo-item b { color: #ffd700; }
        .mensaje {
            padding: 10px; margin: 10px 0; border-radius: 4px; display: none;
            font-size: 0.85rem;
        }
        .mensaje.success { background: rgba(39,174,96,0.3); border: 1px solid #27ae60; display: block; }
        .mensaje.error { background: rgba(192,57,43,0.3); border: 1px solid #c0392b; display: block; }
        .chart-container {
            background: #1a1a2e; padding: 15px; border-radius: 8px; margin-top: 15px;
            height: 300px; position: relative;
        }
        .date-filters { margin-bottom: 15px; }
        .export-btns { margin-top: 15px; }
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
            <button onclick="showTab('agencias')">Agencias</button>
            <button onclick="location.href='/logout'" class="logout-btn">Salir</button>
        </div>
    </div>
    <div class="content">
        <div id="mensaje" class="mensaje"></div>
        
        <!-- DASHBOARD (HOY) -->
        <div id="dashboard" class="tab-content active">
            <h3 style="color: #ffd700; margin-bottom: 15px;">RESUMEN DE HOY</h3>
            <div class="stats-grid">
                <div class="stat-card"><h3>VENTAS</h3><p id="stat-ventas">S/0</p></div>
                <div class="stat-card"><h3>PREMIOS</h3><p id="stat-premios">S/0</p></div>
                <div class="stat-card"><h3>COMISIONES</h3><p id="stat-comisiones">S/0</p></div>
                <div class="stat-card"><h3>BALANCE</h3><p id="stat-balance">S/0</p></div>
            </div>
        </div>

        <!-- HISTÓRICO (NUEVO) -->
        <div id="historico" class="tab-content">
            <div class="form-box">
                <h3>CONSULTA HISTÓRICA POR RANGO</h3>
                <div class="date-filters">
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
                </div>
                
                <div id="historico-resumen" style="display:none;">
                    <div class="stats-grid" style="margin-top: 15px;">
                        <div class="stat-card"><h3>TOTAL VENTAS</h3><p id="hist-total-ventas">S/0</p></div>
                        <div class="stat-card"><h3>TOTAL PREMIOS</h3><p id="hist-total-premios">S/0</p></div>
                        <div class="stat-card"><h3>TOTAL TICKETS</h3><p id="hist-total-tickets">0</p></div>
                        <div class="stat-card"><h3>BALANCE</h3><p id="hist-total-balance">S/0</p></div>
                    </div>
                    
                    <div class="export-btns">
                        <button class="btn-submit" onclick="exportarCSV('ventas')">📥 Exportar Ventas (CSV)</button>
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

        <!-- RIESGO -->
        <div id="riesgo" class="tab-content">
            <h3 style="color: #ffd700; margin-bottom: 15px; font-size: 1rem;">ANIMALES MAS JUGADOS HOY</h3>
            <div id="lista-riesgo"><p style="color: #888; font-size: 0.85rem;">Cargando...</p></div>
        </div>

        <!-- REPORTE -->
        <div id="reporte" class="tab-content">
            <h3 style="color: #ffd700; margin-bottom: 15px; font-size: 1rem;">REPORTE POR AGENCIA (HOY)</h3>
            <div style="overflow-x: auto;">
                <table>
                    <thead><tr><th>Agencia</th><th>Ventas</th><th>Premios</th><th>Comision</th><th>Balance</th></tr></thead>
                    <tbody id="tabla-reporte"><tr><td colspan="5" style="text-align:center;color:#888;">Cargando...</td></tr></tbody>
                </table>
            </div>
        </div>

        <!-- RESULTADOS -->
        <div id="resultados" class="tab-content">
            <div class="form-box">
                <h3>CARGAR RESULTADO</h3>
                <div class="form-row">
                    <select id="res-hora">{% for h in horarios %}<option value="{{h}}">{{h}}</option>{% endfor %}</select>
                    <select id="res-animal">{% for k, v in animales.items() %}<option value="{{k}}">{{k}} - {{v}}</option>{% endfor %}</select>
                    <button class="btn-submit" onclick="guardarResultado()">GUARDAR</button>
                </div>
            </div>
        </div>

        <!-- AGENCIAS -->
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
        // Variables globales para histórico
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
            
            // Consultar estadísticas
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
                
                // Actualizar totales
                document.getElementById('hist-total-ventas').textContent = 'S/' + d.totales.ventas.toFixed(0);
                document.getElementById('hist-total-premios').textContent = 'S/' + d.totales.premios.toFixed(0);
                document.getElementById('hist-total-tickets').textContent = d.totales.tickets;
                document.getElementById('hist-total-balance').textContent = 'S/' + d.totales.balance.toFixed(0);
                
                // Tabla detalle
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
                
                // Cargar top animales
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
                    html += `<div class="riesgo-item" style="margin-bottom: 0;">
                        <b>${medalla} ${a.numero} - ${a.nombre}</b><br>
                        <small>Monto: S/${a.total_apostado} | Jugadas: ${a.cantidad_jugadas}</small>
                    </div>`;
                });
                container.innerHTML = html;
            });
        }

        function exportarCSV(tipo) {
            if (!fechasConsulta.inicio) {
                showMensaje('Primero consulte un rango de fechas', 'error');
                return;
            }
            
            fetch('/admin/exportar-csv', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    tipo: tipo,
                    fecha_inicio: fechasConsulta.inicio,
                    fecha_fin: fechasConsulta.fin
                })
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    showMensaje(d.error, 'error');
                    return;
                }
                
                // Descargar archivo
                let blob = new Blob([d.csv], {type: 'text/csv'});
                let url = window.URL.createObjectURL(blob);
                let a = document.createElement('a');
                a.href = url;
                a.download = d.filename;
                a.click();
                showMensaje('Archivo descargado', 'success');
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
                let container = document.getElementById('lista-riesgo');
                if (!d.riesgo || Object.keys(d.riesgo).length === 0) {
                    container.innerHTML = '<p style="color:#888; font-size: 0.85rem;">No hay apuestas</p>'; 
                    return;
                }
                let html = '';
                for (let [k, v] of Object.entries(d.riesgo)) {
                    html += '<div class="riesgo-item"><b>' + k + '</b><br>Apostado: S/' + v.apostado.toFixed(2) + ' | Pagaria: S/' + v.pagaria.toFixed(2) + '</div>';
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

        function guardarResultado() {
            let form = new FormData();
            form.append('hora', document.getElementById('res-hora').value);
            form.append('animal', document.getElementById('res-animal').value);
            fetch('/admin/guardar-resultado', {method: 'POST', body: form})
            .then(r => r.json()).then(d => {
                if (d.status === 'ok') showMensaje('Guardado', 'success');
                else showMensaje(d.error || 'Error', 'error');
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

        // Set fechas por defecto al cargar
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
    print("  ZOOLO CASINO CLOUD v5.1 - SISTEMA EN LA NUBE")
    print("  CON ESTADÍSTICAS HISTÓRICAS")
    print("=" * 60)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
