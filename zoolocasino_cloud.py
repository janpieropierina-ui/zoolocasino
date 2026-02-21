#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v5.9.1 - REPARADO
- Fix: Pantalla blanca PC (CSS display)
- Fix: Reportes timeout optimizados
- Fix: Manejo de fechas robusto
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

# Horarios Perú (fijos)
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
    """Retorna datetime actual de Perú (UTC-5)"""
    return datetime.utcnow() - timedelta(hours=5)

def parse_fecha_ticket(fecha_str):
    """Parsea fechas en formato dd/mm/YYYY o dd/mm/YYYY HH:MM AM/PM"""
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

# ==================== APIS AGENCIA ====================
@app.route('/api/mis-tickets', methods=['POST'])
@agencia_required
def mis_tickets():
    try:
        data = request.get_json() or {}
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        estado = data.get('estado', 'todos')
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{session['user_id']}&order=fecha.desc&limit=200"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
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
            for t in tickets_filtrados[:50]:  # Limitar para velocidad
                if t.get('pagado'):
                    continue
                    
                fecha_ticket = parse_fecha_ticket(t['fecha']).strftime("%d/%m/%Y")
                resultados_list = supabase_request("resultados", filters={"fecha": fecha_ticket})
                resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
                
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
                    t['premio_calculado'] = round(tiene_premio, 2)
                    tickets_con_premio.append(t)
            
            tickets_filtrados = tickets_con_premio
        
        total_ventas = sum(t['total'] for t in tickets_filtrados)
        total_tickets = len(tickets_filtrados)
        
        return jsonify({
            'status': 'ok',
            'tickets': tickets_filtrados[:50],
            'totales': {
                'cantidad': total_tickets,
                'ventas': round(total_ventas, 2)
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            return jsonify({'error': 'Ticket no encontrado'})
        
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
        
        resultados_list = supabase_request("resultados", filters={"fecha": hoy})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        for t in tickets:
            if t['agencia_id'] == session['user_id'] and not t['anulado']:
                if not t['pagado']:
                    jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{session['user_id']}&order=fecha.desc&limit=300"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
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
                    'error': f'No se puede editar. Solo disponible hasta 2 horas después del sorteo.'
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
                            'mensaje': f'RESULTADO ACTUALIZADO: {hora} = {animal}',
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
                    'mensaje': f'RESULTADO GUARDADO: {hora} = {animal}',
                    'accion': 'creado'
                })
            else:
                return jsonify({'error': 'Error al crear resultado'}), 500
            
    except Exception as e:
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
        
        for t in tickets[:100]:  # Limitar para velocidad
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
        agencia_id = data.get('agencia_id')
        
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fechas requeridas'}), 400
        
        try:
            dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}), 400
        
        # Limitar rango a 31 días para evitar timeout
        if (dt_fin - dt_inicio).days > 31:
            dt_inicio = dt_fin - timedelta(days=30)
        
        # Obtener agencias
        if agencia_id:
            url = f"{SUPABASE_URL}/rest/v1/agencias?id=eq.{agencia_id}"
        else:
            url = f"{SUPABASE_URL}/rest/v1/agencias?es_admin=eq.false"
            
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                agencias = json.loads(response.read().decode())
        except Exception as e:
            return jsonify({'error': 'Error al obtener agencias de la base de datos'}), 500
        
        if not agencias:
            return jsonify({'agencias': [], 'totales': {}, 'status': 'ok'})
            
        dict_agencias = {a['id']: a for a in agencias}
        
        # Obtener tickets (limitados y filtrados)
        base_url = f"{SUPABASE_URL}/rest/v1/tickets?"
        params = ["anulado=eq.false", "order=fecha.desc", "limit=500"]  # Reducido a 500
        
        if agencia_id:
            params.insert(0, f"agencia_id=eq.{agencia_id}")
            
        url = base_url + "&".join(params)
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                all_tickets = json.loads(response.read().decode())
        except Exception as e:
            return jsonify({'error': 'Error al obtener tickets. Intente un rango menor.'}), 500
        
        # Filtrar por fecha
        tickets_validos = []
        for t in all_tickets:
            try:
                if t.get('anulado'):
                    continue
                fecha_ticket_str = t['fecha'].split(' ')[0]
                dt_ticket = datetime.strptime(fecha_ticket_str, "%d/%m/%Y")
                if dt_inicio <= dt_ticket <= dt_fin:
                    tickets_validos.append(t)
            except:
                continue
        
        # Si no hay tickets, retornar vacío
        if not tickets_validos:
            return jsonify({
                'status': 'ok',
                'agencias': [],
                'totales': {
                    'tickets': 0, 'ventas': 0, 'premios_pagados': 0, 
                    'premios_pendientes': 0, 'premios_teoricos': 0,
                    'comision': 0, 'balance': 0
                },
                'rango': {'inicio': fecha_inicio, 'fin': fecha_fin}
            })
        
        # Obtener resultados solo para fechas necesarias (máximo 31 días)
        fechas_unicas = list(set([
            datetime.strptime(t['fecha'].split(' ')[0], "%d/%m/%Y").strftime("%d/%m/%Y") 
            for t in tickets_validos
        ]))[:31]
        
        resultados_por_dia = {}
        for fecha_str in fechas_unicas:
            try:
                resultados_list = supabase_request("resultados", filters={"fecha": fecha_str})
                if resultados_list:
                    resultados_por_dia[fecha_str] = {r['hora']: r['animal'] for r in resultados_list}
            except:
                continue
        
        # Procesar estadísticas
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
        
        # Procesar tickets (limitar a 300 para evitar timeout)
        for t in tickets_validos[:300]:
            ag_id = t['agencia_id']
            if ag_id not in stats_por_agencia:
                continue
            
            stats = stats_por_agencia[ag_id]
            stats['tickets'] += 1
            stats['ventas'] += t['total']
            
            try:
                fecha_ticket = t['fecha'].split(' ')[0]
            except:
                continue
            
            resultados_dia = resultados_por_dia.get(fecha_ticket, {})
            
            # Obtener jugadas
            try:
                jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                if not jugadas:
                    continue
            except:
                continue
            
            premio_teorico_ticket = 0
            tiene_premio = False
            
            for j in jugadas:
                wa = resultados_dia.get(j['hora'])
                if wa:
                    premio_jugada = 0
                    if j['tipo'] == 'animal' and str(wa) == str(j['seleccion']):
                        premio_jugada = calcular_premio_animal(j['monto'], wa)
                        premio_teorico_ticket += premio_jugada
                        tiene_premio = True
                    elif j['tipo'] == 'especial' and str(wa) not in ["0", "00"]:
                        sel = j['seleccion']
                        num = int(wa)
                        if (sel == 'ROJO' and str(wa) in ROJOS) or \
                           (sel == 'NEGRO' and str(wa) not in ROJOS) or \
                           (sel == 'PAR' and num % 2 == 0) or \
                           (sel == 'IMPAR' and num % 2 != 0):
                            premio_jugada = j['monto'] * PAGO_ESPECIAL
                            premio_teorico_ticket += premio_jugada
                            tiene_premio = True
            
            stats['premios_teoricos'] += premio_teorico_ticket
            
            if t.get('pagado'):
                stats['tickets_pagados_count'] += 1
                stats['premios_pagados'] += premio_teorico_ticket
            else:
                if tiene_premio:
                    stats['tickets_pendientes_count'] += 1
                    stats['premios_pendientes'] += premio_teorico_ticket
        
        # Calcular totales y formatear
        total_global = {
            'tickets': 0, 'ventas': 0, 'premios_pagados': 0, 'premios_pendientes': 0,
            'premios_teoricos': 0, 'comision': 0, 'balance': 0
        }
        
        reporte_agencias = []
        for ag_id, stats in stats_por_agencia.items():
            if stats['tickets'] > 0:
                stats['comision'] = stats['ventas'] * stats['comision_pct']
                stats['balance'] = stats['ventas'] - stats['premios_teoricos'] - stats['comision']
                
                # Redondear
                for key in ['ventas', 'premios_pagados', 'premios_pendientes', 'premios_teoricos', 'comision', 'balance']:
                    stats[key] = round(stats[key], 2)
                
                reporte_agencias.append(stats)
                
                for key in total_global:
                    if key in stats:
                        total_global[key] += stats[key]
        
        # Calcular porcentajes
        if total_global['ventas'] > 0:
            for ag in reporte_agencias:
                ag['porcentaje_ventas'] = round((ag['ventas'] / total_global['ventas']) * 100, 1)
        
        reporte_agencias.sort(key=lambda x: x['ventas'], reverse=True)
        
        # Redondear totales
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
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=500"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            all_tickets = json.loads(response.read().decode())
        
        tickets_validos = []
        for t in all_tickets:
            if t.get('anulado'):
                continue
            try:
                dt_ticket = parse_fecha_ticket(t['fecha'])
                if dt_ticket and dt_inicio <= dt_ticket <= dt_fin:
                    tickets_validos.append(t)
            except:
                continue
        
        resultados_por_dia = {}
        delta = dt_fin - dt_inicio
        for i in range(min(delta.days + 1, 31)):  # Max 31 días
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
        
        for t in tickets_validos[:300]:  # Limitar
            ag_id = t['agencia_id']
            if ag_id not in stats_por_agencia:
                continue
            
            stats = stats_por_agencia[ag_id]
            stats['tickets'] += 1
            stats['ventas'] += t['total']
            
            try:
                fecha_ticket = t['fecha'].split(' ')[0]
            except:
                continue
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
        writer.writerow(['Agencia', 'Usuario', 'Tickets', 'Ventas (S/)', 'Premios (S/)', 'Comisión (S/)', 'Balance (S/)'])
        
        total_ventas = sum(s['ventas'] for s in stats_por_agencia.values())
        
        for ag_id, stats in sorted(stats_por_agencia.items(), key=lambda x: x[1]['ventas'], reverse=True):
            if stats['tickets'] > 0:
                comision = stats['ventas'] * dict_agencias[ag_id]['comision']
                balance = stats['ventas'] - stats['premios'] - comision
                
                writer.writerow([
                    stats['nombre'], stats['usuario'], stats['tickets'],
                    round(stats['ventas'], 2), round(stats['premios'], 2),
                    round(comision, 2), round(balance, 2)
                ])
        
        writer.writerow([])
        total_comision = sum(s['ventas'] * dict_agencias[ag_id]['comision'] for ag_id, s in stats_por_agencia.items())
        total_premios = sum(s['premios'] for s in stats_por_agencia.values())
        total_balance = sum(s['ventas'] for s in stats_por_agencia.values()) - total_premios - total_comision
        
        writer.writerow(['TOTALES', '', 
            sum(s['tickets'] for s in stats_por_agencia.values()),
            round(total_ventas, 2), round(total_premios, 2),
            round(total_comision, 2), round(total_balance, 2)
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
        total_ventas = total_premios = total_comisiones = premios_pendientes = 0
        
        for ag in agencias:
            ventas = sum(t['total'] for t in tickets if t['agencia_id'] == ag['id'] and not t['anulado'])
            comision = ventas * ag['comision']
            
            premios_pagados = 0
            premios_pend = 0
            
            for t in tickets:
                if t['agencia_id'] == ag['id'] and not t['anulado']:
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
                    
                    if t['pagado']:
                        premios_pagados += premio_ticket
                    else:
                        premios_pend += premio_ticket
            
            balance = ventas - premios_pagados - comision
            
            data_agencias.append({
                'nombre': ag['nombre_agencia'],
                'ventas': round(ventas, 2),
                'premios_pagados': round(premios_pagados, 2),
                'premios_pendientes': round(premios_pend, 2),
                'comision': round(comision, 2),
                'balance': round(balance, 2)
            })
            
            total_ventas += ventas
            total_premios += premios_pagados
            total_comisiones += comision
            premios_pendientes += premios_pend
        
        return jsonify({
            'agencias': data_agencias,
            'global': {
                'ventas': round(total_ventas, 2),
                'pagos': round(total_premios, 2),
                'premios_pendientes': round(premios_pendientes, 2),
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
        
        for t in tickets[:200]:  # Limitar para velocidad
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
        
        try:
            dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido'}), 400
        
        # Limitar a 31 días
        if (dt_fin - dt_inicio).days > 31:
            dt_inicio = dt_fin - timedelta(days=30)
        
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=500"
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            all_tickets = json.loads(response.read().decode())
        
        dias_data = {}
        tickets_rango = []
        
        for t in all_tickets:
            try:
                if t.get('anulado'):
                    continue
                fecha_str = t['fecha'].split(' ')[0]
                dt_ticket = datetime.strptime(fecha_str, "%d/%m/%Y")
                if dt_inicio <= dt_ticket <= dt_fin:
                    tickets_rango.append(t)
                    dia_key = dt_ticket.strftime("%d/%m/%Y")
                    
                    if dia_key not in dias_data:
                        dias_data[dia_key] = {
                            'ventas': 0, 'tickets': 0, 'premios': 0, 
                            'comisiones': 0
                        }
                    
                    dias_data[dia_key]['ventas'] += t['total']
                    dias_data[dia_key]['tickets'] += 1
            except:
                continue
        
        # Obtener resultados
        resultados_por_dia = {}
        fechas_list = list(dias_data.keys())[:31]
        
        for fecha_str in fechas_list:
            try:
                resultados_list = supabase_request("resultados", filters={"fecha": fecha_str})
                if resultados_list:
                    resultados_por_dia[fecha_str] = {r['hora']: r['animal'] for r in resultados_list}
            except:
                continue
        
        resumen_dias = []
        total_ventas = total_premios = total_tickets = 0
        
        for dia_key in sorted(dias_data.keys()):
            datos = dias_data[dia_key]
            resultados_dia = resultados_por_dia.get(dia_key, {})
            
            premios_dia = 0
            tickets_dia = [t for t in tickets_rango if t['fecha'].startswith(dia_key)][:50]
            
            for t in tickets_dia:
                if t.get('pagado'):
                    try:
                        jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
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
                    except:
                        continue
            
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
        
        try:
            dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
        except:
            return jsonify({'error': 'Fechas inválidas'}), 400
        
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=300"
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            all_tickets = json.loads(response.read().decode())
        
        ticket_ids = []
        for t in all_tickets:
            try:
                if t.get('anulado'):
                    continue
                fecha_str = t['fecha'].split(' ')[0]
                dt_ticket = datetime.strptime(fecha_str, "%d/%m/%Y")
                if dt_inicio <= dt_ticket <= dt_fin:
                    ticket_ids.append(t['id'])
            except:
                continue
        
        if not ticket_ids:
            return jsonify({'top_animales': []})
        
        apuestas = {}
        for ticket_id in ticket_ids[:50]:  # Limitar
            try:
                jugadas = supabase_request("jugadas", filters={"ticket_id": ticket_id, "tipo": "animal"})
                for j in jugadas:
                    sel = j['seleccion']
                    if sel not in apuestas:
                        apuestas[sel] = {'monto': 0, 'cantidad': 0}
                    apuestas[sel]['monto'] += j['monto']
                    apuestas[sel]['cantidad'] += 1
            except:
                continue
        
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
            Sistema ZOOLO CASINO v5.9<br>Zona Horaria Perú
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
        .left-panel { 
            flex: 1; 
            display: flex; 
            flex-direction: column; 
            min-height: 0;
            overflow: hidden;
        }
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
        .animals-grid {
            flex: 1; 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
            gap: 5px; 
            padding: 10px; 
            overflow-y: auto;
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
        }
        .animal-card:active { transform: scale(0.92); }
        .animal-card.active { 
            box-shadow: 0 0 15px rgba(255,215,0,0.6); 
            border-color: #ffd700 !important; 
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
        .horarios {
            display: flex;
            gap: 6px;
            padding: 10px;
            overflow-x: auto;
            flex-shrink: 0;
            background: #0a0a0a;
        }
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
        }
        .btn-hora.active { 
            background: linear-gradient(135deg, #27ae60, #229954); 
            color: white; 
            font-weight: bold; 
            border-color: #27ae60;
        }
        .btn-hora.expired { 
            background: #300; 
            color: #666; 
            text-decoration: line-through; 
            pointer-events: none;
            opacity: 0.5;
        }
        .ticket-display {
            flex: 1; 
            background: #000; 
            margin: 0 10px 10px; 
            border-radius: 10px;
            padding: 12px; 
            border: 1px solid #333;
            overflow-y: auto;
            font-size: 0.85rem;
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
        }
        .ticket-total {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 2px solid #ffd700;
            text-align: right;
            font-size: 1.2rem;
            font-weight: bold;
            color: #ffd700;
        }
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
        .modal {
            display: none; 
            position: fixed; 
            top: 0; left: 0;
            width: 100%; 
            height: 100%; 
            background: rgba(0,0,0,0.95);
            z-index: 1000; 
            overflow-y: auto;
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
                max-width: 700px;
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
        .tabs { 
            display: flex; 
            gap: 2px; 
            margin-bottom: 20px; 
            border-bottom: 2px solid #333;
            overflow-x: auto;
        }
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
        }
        .tab-btn.active { color: #ffd700; border-bottom-color: #ffd700; font-weight: bold; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
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
        }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #aaa; }
        .stat-value { color: #ffd700; font-weight: bold; font-size: 1.2rem; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; color: #888; font-size: 0.9rem; margin-bottom: 6px; }
        .form-group input, .form-group select {
            width: 100%; padding: 12px; background: #000; border: 1px solid #444;
            color: white; border-radius: 8px; font-size: 1rem;
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
        }
        .alert-box {
            background: rgba(243, 156, 18, 0.15); 
            border: 1px solid #f39c12;
            padding: 15px; 
            border-radius: 8px; 
            margin: 15px 0; 
        }
        .table-container {
            overflow-x: auto;
            margin: 15px 0;
            border-radius: 8px;
            border: 1px solid #333;
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            font-size: 0.85rem; 
        }
        th, td { 
            padding: 12px 8px; 
            text-align: left; 
            border-bottom: 1px solid #333; 
        }
        th { 
            background: linear-gradient(135deg, #ffd700, #ffed4e); 
            color: black; 
            font-weight: bold;
        }
        .ticket-item {
            background: #0a0a0a;
            padding: 15px;
            margin: 8px 0;
            border-radius: 10px;
            border-left: 4px solid #2980b9;
            cursor: pointer;
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
        .ticket-premio {
            color: #27ae60;
            font-weight: bold;
            font-size: 1.2rem;
            margin-top: 5px;
        }
        .jugada-detail {
            background: #111;
            padding: 8px;
            margin: 4px 0;
            border-radius: 6px;
            font-size: 0.85rem;
            display: flex;
            justify-content: space-between;
        }
        .jugada-ganadora {
            background: rgba(39,174,96,0.2);
            border: 1px solid #27ae60;
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
            <div class="ticket-display" id="ticket-display">
                <div style="text-align:center; color:#666; padding:20px;">
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
                        <span class="stat-value" id="caja-premios" style="color: #e74c3c;">S/0.00</span>
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
                            <span class="stat-value" id="hist-premios" style="color: #e74c3c;">S/0.00</span>
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
                </div>
            </div>
        </div>
    </div>

    <!-- MODAL RESULTADOS -->
    <div class="modal" id="modal-resultados">
        <div class="modal-content">
            <div class="modal-header">
                <h3>RESULTADOS</h3>
                <button class="btn-close" onclick="cerrarModal('modal-resultados')">X</button>
            </div>
            
            <div class="form-group" style="margin-bottom: 20px;">
                <label>Fecha:</label>
                <input type="date" id="resultados-fecha" onchange="cargarResultadosFecha()">
                <button class="btn-consultar" onclick="cargarResultadosFecha()" style="margin-top: 10px;">CONSULTAR</button>
            </div>

            <div id="lista-resultados" style="max-height: 400px; overflow-y: auto;">
                <p style="color: #888; text-align: center; padding: 20px;">Seleccione una fecha...</p>
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
            if (btn.classList.contains('expired')) {
                alert('Este sorteo ya cerró');
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
                html = '<div style="text-align:center; color:#666; padding:20px;">Selecciona animales y horarios...</div>';
            }
            
            if (total > 0) {
                html += `<div class="ticket-total">TOTAL: S/${total}</div>`;
            }
            
            display.innerHTML = html;
        }
        
        function agregar() {
            if (horariosSel.length === 0 || (seleccionados.length === 0 && especiales.length === 0)) {
                alert('Selecciona horario y animal/especial'); 
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
            alert(`${count} jugada(s) agregada(s)`);
        }
        
        async function vender() {
            if (carrito.length === 0) { 
                alert('Carrito vacío'); 
                return; 
            }
            
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
                    alert(data.error);
                } else {
                    window.open(data.url_whatsapp, '_blank');
                    carrito = []; 
                    updateTicket();
                }
            } catch (e) {
                alert('Error de conexión');
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
            
            fetch('/api/resultados-fecha', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha: fecha})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    container.innerHTML = '<p style="color: #c0392b; text-align: center;">Error: ' + d.error + '</p>';
                    return;
                }
                
                let html = '';
                if (d.resultados) {
                    for (let hora of horasPeru) {
                        let resultado = d.resultados[hora];
                        if (resultado) {
                            html += `<div style="background: #0a0a0a; padding: 15px; margin: 8px 0; border-radius: 10px; border-left: 4px solid #27ae60; display: flex; justify-content: space-between; align-items: center;">
                                <div><strong style="color: #ffd700;">${hora}</strong></div>
                                <div style="text-align: right;">
                                    <div style="color: #ffd700; font-weight: bold; font-size: 1.3rem;">${resultado.animal}</div>
                                    <div style="color: #888; font-size: 0.9rem;">${resultado.nombre}</div>
                                </div>
                            </div>`;
                        } else {
                            html += `<div style="background: #0a0a0a; padding: 15px; margin: 8px 0; border-radius: 10px; border-left: 4px solid #666; opacity: 0.7; display: flex; justify-content: space-between; align-items: center;">
                                <div><strong style="color: #ffd700;">${hora}</strong></div>
                                <div style="color: #666;">Pendiente</div>
                            </div>`;
                        }
                    }
                }
                container.innerHTML = html;
            })
            .catch(e => {
                container.innerHTML = '<p style="color: #c0392b; text-align: center;">Error de conexión</p>';
            });
        }

        function cerrarModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }
        
        function abrirCaja() {
            fetch('/api/caja')
            .then(r => r.json())
            .then(d => {
                if (d.error) { 
                    alert(d.error); 
                    return; 
                }
                document.getElementById('caja-ventas').textContent = 'S/' + d.ventas.toFixed(2);
                document.getElementById('caja-premios').textContent = 'S/' + d.premios.toFixed(2);
                document.getElementById('caja-comision').textContent = 'S/' + d.comision.toFixed(2);
                document.getElementById('caja-balance').textContent = 'S/' + d.balance.toFixed(2);
                
                let alertaDiv = document.getElementById('alerta-pendientes');
                if (d.tickets_pendientes > 0) {
                    alertaDiv.style.display = 'block';
                    document.getElementById('info-pendientes').innerHTML = `Tienes <strong>${d.tickets_pendientes}</strong> ticket(s) ganador(es) sin cobrar.`;
                } else {
                    alertaDiv.style.display = 'none';
                }
                
                document.getElementById('modal-caja').style.display = 'block';
            })
            .catch(e => alert('Error de conexión'));
            
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
                    alert(d.error);
                    return;
                }
                
                document.getElementById('resultado-historico').style.display = 'block';
                document.getElementById('hist-ventas').textContent = 'S/' + d.totales.ventas.toFixed(2);
                document.getElementById('hist-premios').textContent = 'S/' + d.totales.premios.toFixed(2);
                document.getElementById('hist-balance').textContent = 'S/' + d.totales.balance.toFixed(2);
                
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
            })
            .catch(e => alert('Error de conexión'));
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
                    alert(d.error); 
                    return; 
                }
                
                let msg = "TOTAL GANADO: S/" + d.total_ganado.toFixed(2) + "\\n\\n¿Confirma pago?";
                
                if (d.total_ganado > 0 && confirm(msg)) {
                    await fetch('/api/pagar-ticket', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ticket_id: d.ticket_id})
                    });
                    alert('✅ Ticket pagado');
                } else if (d.total_ganado === 0) {
                    alert('Ticket no ganador');
                }
            } catch (e) {
                alert('Error de conexión');
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
                    alert(d.error);
                } else {
                    alert('✅ ' + d.mensaje);
                }
            } catch (e) {
                alert('Error de conexión');
            }
        }
        
        function borrarTodo() {
            if (!confirm('¿Borrar todo?')) return;
            seleccionados = []; especiales = []; horariosSel = []; carrito = [];
            document.querySelectorAll('.active').forEach(el => el.classList.remove('active'));
            updateTicket();
        }
        
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', function(e) {
                if (e.target === this) this.style.display = 'none';
            });
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
        
        /* Header */
        .admin-header {
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 15px;
            border-bottom: 2px solid #ffd700;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        
        .admin-title {
            color: #ffd700;
            font-size: 1.2rem;
            font-weight: bold;
        }
        
        .logout-btn {
            background: #c0392b;
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            font-size: 0.9rem;
        }
        
        /* Tabs */
        .admin-tabs {
            display: flex;
            background: #1a1a2e;
            border-bottom: 1px solid #333;
            overflow-x: auto;
            scrollbar-width: none;
        }
        
        .admin-tabs::-webkit-scrollbar {
            display: none;
        }
        
        .admin-tab {
            flex: 1;
            min-width: 100px;
            padding: 15px 10px;
            background: transparent;
            border: none;
            color: #888;
            cursor: pointer;
            font-size: 0.85rem;
            border-bottom: 3px solid transparent;
            transition: all 0.2s;
            white-space: nowrap;
        }
        
        .admin-tab:hover {
            color: #ffd700;
            background: rgba(255,215,0,0.05);
        }
        
        .admin-tab.active {
            color: #ffd700;
            border-bottom-color: #ffd700;
            font-weight: bold;
        }
        
        /* Content - IMPORTANTE: Visible por defecto */
        .content { 
            padding: 20px; 
            max-width: 1200px; 
            margin: 0 auto; 
            padding-bottom: 30px;
        }
        
        /* Tab content - IMPORTANTE: Dashboard activo por defecto */
        .tab-content { 
            display: none; 
        }
        
        .tab-content.active { 
            display: block !important;
            animation: fadeIn 0.3s;
        }
        
        @keyframes fadeIn { 
            from { opacity: 0; } 
            to { opacity: 1; } 
        }
        
        /* Forzar que dashboard se vea al inicio */
        #dashboard {
            display: block !important;
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
        }
        .stat-card h3 { color: #888; font-size: 0.75rem; margin-bottom: 8px; text-transform: uppercase; }
        .stat-card p { color: #ffd700; font-size: 1.4rem; font-weight: bold; }
        
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
        }
        .btn-danger {
            background: linear-gradient(135deg, #c0392b, #e74c3c); 
            color: white; 
            border: none;
            padding: 12px 24px; 
            border-radius: 8px; 
            cursor: pointer; 
            font-weight: bold; 
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
        }
        
        .table-container {
            overflow-x: auto;
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
        }
        th { 
            background: linear-gradient(135deg, #ffd700, #ffed4e); 
            color: black; 
            font-weight: bold;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #888;
        }
        
        .error-box {
            background: rgba(192, 57, 43, 0.2);
            border: 1px solid #c0392b;
            color: #ff6b6b;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            text-align: center;
        }
        
        .success-box {
            background: rgba(39, 174, 96, 0.2);
            border: 1px solid #27ae60;
            color: #27ae60;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            text-align: center;
        }
        
        .mensaje {
            display: none;
            padding: 15px;
            margin: 15px 0;
            border-radius: 8px;
            text-align: center;
        }
        
        .riesgo-item {
            background: #1a1a2e; 
            padding: 15px; 
            margin-bottom: 10px;
            border-radius: 8px; 
            border-left: 4px solid #c0392b;
        }
        .riesgo-item.lechuza {
            border-left-color: #ffd700;
        }
        
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
        
        .btn-editar {
            background: #2980b9;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8rem;
        }
        
        .agencia-selector {
            background: rgba(255,215,0,0.05);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,215,0,0.2);
        }
        
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
        
        /* Responsive */
        @media (max-width: 768px) {
            .admin-title { font-size: 1rem; }
            .stat-card p { font-size: 1.2rem; }
        }
    </style>
</head>
<body>
    <!-- Header -->
    <div class="admin-header">
        <div class="admin-title">👑 PANEL ADMIN - ZOOLO CASINO</div>
        <button onclick="location.href='/logout'" class="logout-btn">SALIR</button>
    </div>

    <!-- Tabs -->
    <div class="admin-tabs">
        <button class="admin-tab active" onclick="showTab('dashboard')">📊 Dashboard</button>
        <button class="admin-tab" onclick="showTab('resultados')">📋 Resultados</button>
        <button class="admin-tab" onclick="showTab('riesgo')">⚠️ Riesgo</button>
        <button class="admin-tab" onclick="showTab('reporte')">🏢 Reporte</button>
        <button class="admin-tab" onclick="showTab('historico')">📈 Histórico</button>
        <button class="admin-tab" onclick="showTab('agencias')">🏪 Agencias</button>
        <button class="admin-tab" onclick="showTab('operaciones')">⚙️ Operaciones</button>
    </div>

    <div class="content">
        <div id="mensaje" class="mensaje"></div>
        
        <div class="info-pago">
            💰 REGLAS: Animales (00-39) = x35 | Lechuza (40) = x70 | Especiales = x2
        </div>
        
        <!-- DASHBOARD -->
        <div id="dashboard" class="tab-content active">
            <h3 style="color: #ffd700; margin-bottom: 15px;">📊 RESUMEN DE HOY</h3>
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>VENTAS</h3>
                    <p id="stat-ventas">S/0</p>
                </div>
                <div class="stat-card">
                    <h3>PREMIOS PAGADOS</h3>
                    <p id="stat-premios">S/0</p>
                </div>
                <div class="stat-card">
                    <h3>PREMIOS PENDIENTES</h3>
                    <p id="stat-premios-pendientes" style="color: #f39c12;">S/0</p>
                </div>
                <div class="stat-card">
                    <h3>BALANCE</h3>
                    <p id="stat-balance">S/0</p>
                </div>
            </div>
            
            <div class="form-box">
                <h3>⚡ ACCIONES RÁPIDAS</h3>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button class="btn-submit" onclick="showTab('riesgo')">Ver Riesgo</button>
                    <button class="btn-secondary" onclick="showTab('resultados')">Cargar Resultados</button>
                    <button class="btn-csv" onclick="showTab('reporte')">Reporte Agencias</button>
                </div>
            </div>
        </div>

        <!-- REPORTE -->
        <div id="reporte" class="tab-content">
            <div class="form-box">
                <h3>🏢 REPORTE POR AGENCIAS</h3>
                
                <div style="margin-bottom: 15px;">
                    <label style="color: #888; display: block; margin-bottom: 5px;">Filtrar por Agencia:</label>
                    <select id="reporte-agencia-select" style="width: 100%; padding: 12px; background: #000; border: 1px solid #444; color: white; border-radius: 8px;">
                        <option value="">TODAS LAS AGENCIAS</option>
                    </select>
                </div>
                
                <div class="form-row">
                    <input type="date" id="reporte-fecha-inicio">
                    <input type="date" id="reporte-fecha-fin">
                </div>
                
                <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px;">
                    <button class="btn-secondary" onclick="setRangoReporte('hoy')">Hoy</button>
                    <button class="btn-secondary" onclick="setRangoReporte('ayer')">Ayer</button>
                    <button class="btn-secondary" onclick="setRangoReporte('semana')">7 días</button>
                    <button class="btn-submit" onclick="consultarReporteAgencias()">GENERAR REPORTE</button>
                    <button class="btn-csv" onclick="exportarCSV()">📊 Exportar CSV</button>
                </div>
                
                <div id="loading-reporte" class="loading" style="display: none;">
                    Cargando reporte... por favor espere (puede tomar unos segundos)
                </div>
                
                <div id="error-reporte" class="error-box" style="display: none;"></div>
                
                <div id="reporte-agencias-resumen" style="display:none; margin-top: 25px;">
                    <h4 style="color: #ffd700; margin-bottom: 15px;">📈 TOTALES GLOBALES</h4>
                    <div class="stats-grid" id="stats-agencias-totales"></div>
                    
                    <div class="form-box" style="background: rgba(255,215,0,0.05);">
                        <h4 style="color: #ffd700; margin-bottom: 10px; font-size: 1rem;">💰 DESGLOSE DE PREMIOS</h4>
                        <div style="display: flex; justify-content: space-between; margin: 8px 0;">
                            <span style="color: #888;">Premios Pagados:</span>
                            <span id="reporte-premios-pagados" style="color: #27ae60; font-weight: bold;">S/0</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin: 8px 0;">
                            <span style="color: #888;">Premios Pendientes:</span>
                            <span id="reporte-premios-pendientes" style="color: #f39c12; font-weight: bold;">S/0</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin: 8px 0; border-top: 1px solid #333; padding-top: 8px;">
                            <span style="color: #ffd700;">Total en Premios:</span>
                            <span id="reporte-premios-total" style="color: #ffd700; font-weight: bold;">S/0</span>
                        </div>
                    </div>

                    <h4 style="color: #ffd700; margin: 25px 0 15px;">🏆 RANKING AGENCIAS</h4>
                    <div id="ranking-agencias"></div>

                    <h4 style="color: #ffd700; margin: 25px 0 15px;">📋 DETALLE COMPLETO</h4>
                    <div class="table-container">
                        <table id="tabla-detalle-agencias">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Agencia</th>
                                    <th>Tickets</th>
                                    <th>Ventas</th>
                                    <th>Premios Pag.</th>
                                    <th>Pendientes</th>
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

        <!-- RIESGO -->
        <div id="riesgo" class="tab-content">
            <div class="form-box">
                <h3>⚠️ RIESGO POR SORTEO</h3>
                
                <div class="agencia-selector">
                    <label style="color: #ffd700; font-weight: bold;">Filtrar por Agencia:</label>
                    <select id="riesgo-agencia-select" onchange="cargarRiesgo()" style="width: 100%; margin-top: 8px; padding: 10px; background: #000; border: 1px solid #ffd700; color: white; border-radius: 6px;">
                        <option value="">TODAS LAS AGENCIAS</option>
                    </select>
                </div>
                
                <div style="background: #0a0a0a; padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 2px solid #2980b9; text-align: center;">
                    <div style="color: #2980b9; font-size: 0.9rem; margin-bottom: 8px;">🎯 SORTEO EN ANÁLISIS</div>
                    <div id="sorteo-objetivo" style="color: #ffd700; font-size: 1.8rem; font-weight: bold;">Cargando...</div>
                </div>
                
                <div style="margin-bottom: 15px; text-align: center;">
                    <div style="color: #888; font-size: 0.9rem;">TOTAL APOSTADO EN ESTE SORTEO</div>
                    <div id="total-apostado-sorteo" style="color: #ffd700; font-size: 1.5rem; font-weight: bold;">S/0</div>
                </div>
                
                <div id="lista-riesgo" style="max-height: 400px; overflow-y: auto;">
                    <div class="loading">Cargando datos...</div>
                </div>
            </div>
        </div>

        <!-- RESULTADOS -->
        <div id="resultados" class="tab-content">
            <div class="form-box">
                <h3>📋 CARGAR Y CONSULTAR RESULTADOS</h3>
                
                <div class="form-row">
                    <select id="res-hora" style="flex: 1.5;">
                        {% for h in horarios %}<option value="{{h}}">{{h}}</option>{% endfor %}
                    </select>
                    <select id="res-animal" style="flex: 2;">
                        {% for k, v in animales.items() %}<option value="{{k}}">{{k}} - {{v}}</option>{% endfor %}
                    </select>
                    <button class="btn-submit" onclick="guardarResultado()">GUARDAR</button>
                </div>
                
                <div style="margin-top: 15px; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 6px; font-size: 0.85rem; color: #888;">
                    ℹ️ Los resultados son editables hasta 2 horas después del sorteo
                </div>
                
                <div style="margin-top: 20px; border-top: 1px solid #333; padding-top: 20px;">
                    <div class="form-row">
                        <input type="date" id="admin-resultados-fecha">
                        <button class="btn-submit" onclick="cargarResultadosAdminFecha()">CONSULTAR FECHA</button>
                        <button class="btn-secondary" onclick="cargarResultadosAdmin()">HOY</button>
                    </div>
                    
                    <div id="admin-resultados-titulo" style="margin: 15px 0; color: #ffd700; font-weight: bold; text-align: center;"></div>
                    
                    <div id="lista-resultados-admin" style="max-height: 400px; overflow-y: auto;">
                        <p style="color: #888; text-align: center; padding: 20px;">Seleccione una fecha para ver resultados</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- HISTORICO -->
        <div id="historico" class="tab-content">
            <div class="form-box">
                <h3>📈 CONSULTA HISTÓRICA GLOBAL</h3>
                <div class="form-row">
                    <input type="date" id="hist-fecha-inicio">
                    <input type="date" id="hist-fecha-fin">
                    <button class="btn-submit" onclick="consultarHistorico()">CONSULTAR</button>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 10px;">
                    <button class="btn-secondary" onclick="setRango('hoy')">Hoy</button>
                    <button class="btn-secondary" onclick="setRango('ayer')">Ayer</button>
                    <button class="btn-secondary" onclick="setRango('semana')">7 días</button>
                    <button class="btn-secondary" onclick="setRango('mes')">Mes</button>
                </div>
                
                <div id="historico-resumen" style="margin-top: 20px; display: none;">
                    <div class="stats-grid">
                        <div class="stat-card"><h3>VENTAS</h3><p id="hist-total-ventas">S/0</p></div>
                        <div class="stat-card"><h3>PREMIOS</h3><p id="hist-total-premios">S/0</p></div>
                        <div class="stat-card"><h3>TICKETS</h3><p id="hist-total-tickets">0</p></div>
                        <div class="stat-card"><h3>BALANCE</h3><p id="hist-total-balance">S/0</p></div>
                    </div>

                    <div class="table-container" style="margin-top: 20px;">
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

                    <h4 style="color: #ffd700; margin: 25px 0 15px;">🔥 TOP ANIMALES APUESTOS</h4>
                    <div id="top-animales-hist"></div>
                </div>
            </div>
        </div>

        <!-- AGENCIAS -->
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
            
            <h3 style="color: #ffd700; margin-bottom: 15px;">🏢 AGENCIAS REGISTRADAS</h3>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Usuario</th>
                            <th>Nombre</th>
                            <th>Comisión</th>
                        </tr>
                    </thead>
                    <tbody id="tabla-agencias">
                        <tr>
                            <td colspan="4" style="text-align:center; color:#888; padding: 20px;">Cargando...</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- OPERACIONES -->
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
                    <button class="btn-danger" onclick="anularTicketAdmin()">ANULAR TICKET</button>
                </div>
                <div style="margin-top: 15px; padding: 15px; background: rgba(192, 57, 43, 0.1); border-radius: 8px; font-size: 0.85rem; color: #ff6b6b;">
                    ⚠️ Solo se pueden anular tickets no pagados y antes de que inicie el sorteo
                </div>
                <div id="resultado-anular" style="margin-top: 15px;"></div>
            </div>
        </div>
    </div>

    <script>
        // CORREGIDO: Inicialización inmediata al cargar
        document.addEventListener('DOMContentLoaded', function() {
            console.log("Panel Admin cargado correctamente");
            
            // Establecer fechas por defecto
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('reporte-fecha-inicio').value = hoy;
            document.getElementById('reporte-fecha-fin').value = hoy;
            document.getElementById('admin-resultados-fecha').value = hoy;
            document.getElementById('hist-fecha-inicio').value = hoy;
            document.getElementById('hist-fecha-fin').value = hoy;
            
            // Cargar datos iniciales
            cargarDashboard();
            cargarAgenciasSelect();
            cargarAgenciasReporte();
            
            // IMPORTANTE: Asegurar que dashboard esté visible
            showTab('dashboard');
        });

        function showTab(tab) {
            console.log("Mostrando tab:", tab);
            
            // Ocultar todos los tabs
            document.querySelectorAll('.tab-content').forEach(t => {
                t.classList.remove('active');
            });
            
            document.querySelectorAll('.admin-tab').forEach(b => b.classList.remove('active'));
            
            // Mostrar el seleccionado
            const target = document.getElementById(tab);
            if (target) {
                target.classList.add('active');
                console.log("Tab activado correctamente");
            }
            
            // Activar botón
            const buttons = document.querySelectorAll('.admin-tab');
            buttons.forEach(btn => {
                if (btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(tab)) {
                    btn.classList.add('active');
                }
            });
            
            // Cargar datos específicos
            if (tab === 'riesgo') cargarRiesgo();
            if (tab === 'agencias') cargarAgencias();
            if (tab === 'resultados') cargarResultadosAdmin();
        }

        function showMensaje(msg, tipo) {
            let div = document.getElementById('mensaje');
            div.textContent = msg;
            div.style.display = 'block';
            
            if (tipo === 'success') {
                div.className = 'success-box';
            } else if (tipo === 'error') {
                div.className = 'error-box';
            }
            
            setTimeout(() => {
                div.style.display = 'none';
            }, 4000);
        }

        function setRangoReporte(tipo) {
            let hoy = new Date();
            let inicio, fin;
            
            switch(tipo) {
                case 'hoy':
                    inicio = fin = hoy;
                    break;
                case 'ayer':
                    let ayer = new Date(hoy);
                    ayer.setDate(ayer.getDate() - 1);
                    inicio = fin = ayer;
                    break;
                case 'semana':
                    inicio = new Date(hoy);
                    inicio.setDate(inicio.getDate() - 6);
                    fin = hoy;
                    break;
            }
            
            document.getElementById('reporte-fecha-inicio').value = inicio.toISOString().split('T')[0];
            document.getElementById('reporte-fecha-fin').value = fin.toISOString().split('T')[0];
            
            // Auto-generar
            consultarReporteAgencias();
        }

        function consultarReporteAgencias() {
            let inicio = document.getElementById('reporte-fecha-inicio').value;
            let fin = document.getElementById('reporte-fecha-fin').value;
            let agenciaId = document.getElementById('reporte-agencia-select').value;
            
            if (!inicio || !fin) {
                showMensaje('Seleccione ambas fechas', 'error');
                return;
            }
            
            // Mostrar loading, ocultar error previo
            document.getElementById('loading-reporte').style.display = 'block';
            document.getElementById('error-reporte').style.display = 'none';
            document.getElementById('reporte-agencias-resumen').style.display = 'none';
            
            console.log("Consultando reporte:", {inicio, fin, agenciaId});
            
            fetch('/admin/reporte-agencias-rango', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    fecha_inicio: inicio,
                    fecha_fin: fin,
                    agencia_id: agenciaId || null
                })
            })
            .then(r => {
                console.log("Status:", r.status);
                if (!r.ok) {
                    return r.json().then(err => { throw new Error(err.error || 'Error del servidor'); });
                }
                return r.json();
            })
            .then(d => {
                document.getElementById('loading-reporte').style.display = 'none';
                
                if (d.error) {
                    document.getElementById('error-reporte').textContent = d.error;
                    document.getElementById('error-reporte').style.display = 'block';
                    return;
                }
                
                mostrarReporte(d);
            })
            .catch(e => {
                console.error("Error:", e);
                document.getElementById('loading-reporte').style.display = 'none';
                document.getElementById('error-reporte').textContent = 'Error: ' + e.message + '. Intente con un rango menor (máx 7 días).';
                document.getElementById('error-reporte').style.display = 'block';
            });
        }

        function mostrarReporte(d) {
            document.getElementById('reporte-agencias-resumen').style.display = 'block';
            
            let totales = d.totales || {};
            
            // Stats grid
            let htmlTotales = `
                <div class="stat-card">
                    <h3>AGENCIAS</h3>
                    <p>${(d.agencias || []).length}</p>
                </div>
                <div class="stat-card">
                    <h3>TICKETS</h3>
                    <p>${totales.tickets || 0}</p>
                </div>
                <div class="stat-card">
                    <h3>VENTAS</h3>
                    <p>S/${(totales.ventas || 0).toFixed(0)}</p>
                </div>
                <div class="stat-card">
                    <h3>BALANCE</h3>
                    <p style="color: ${(totales.balance || 0) >= 0 ? '#27ae60' : '#c0392b'}">S/${(totales.balance || 0).toFixed(0)}</p>
                </div>
            `;
            document.getElementById('stats-agencias-totales').innerHTML = htmlTotales;
            
            // Desglose premios
            document.getElementById('reporte-premios-pagados').textContent = 'S/' + (totales.premios_pagados || 0).toFixed(2);
            document.getElementById('reporte-premios-pendientes').textContent = 'S/' + (totales.premios_pendientes || 0).toFixed(2);
            document.getElementById('reporte-premios-total').textContent = 'S/' + (totales.premios_teoricos || 0).toFixed(2);
            
            // Ranking
            let htmlRanking = '';
            (d.agencias || []).slice(0, 5).forEach((ag, idx) => {
                let medalla = ['🥇','🥈','🥉','4°','5°'][idx] || (idx + 1);
                let colorBalance = (ag.balance || 0) >= 0 ? '#27ae60' : '#c0392b';
                
                htmlRanking += `
                    <div class="ranking-item">
                        <div style="font-size: 1.5rem; font-weight: bold; color: #ffd700; min-width: 40px;">${medalla}</div>
                        <div style="flex: 1; padding: 0 10px;">
                            <div style="font-weight: bold; color: white;">${ag.nombre}</div>
                            <div style="font-size: 0.85rem; color: #888;">${ag.tickets} tickets • ${ag.porcentaje_ventas || 0}% del total</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 1.3rem; font-weight: bold; color: #27ae60;">S/${(ag.ventas || 0).toFixed(0)}</div>
                            <div style="font-size: 0.9rem; color: ${colorBalance};">S/${(ag.balance || 0).toFixed(0)}</div>
                        </div>
                    </div>
                `;
            });
            document.getElementById('ranking-agencias').innerHTML = htmlRanking || '<p style="color: #888; text-align: center;">No hay datos</p>';
            
            // Tabla detalle
            let tbody = document.querySelector('#tabla-detalle-agencias tbody');
            let htmlTabla = '';
            (d.agencias || []).forEach((ag, idx) => {
                let colorBalance = (ag.balance || 0) >= 0 ? '#27ae60' : '#c0392b';
                let pendienteBadge = (ag.premios_pendientes || 0) > 0 ? 
                    `<span style="background: #f39c12; color: black; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">S/${ag.premios_pendientes.toFixed(0)}</span>` : 
                    '<span style="color:#666">-</span>';
                
                htmlTabla += `<tr>
                    <td>${idx + 1}</td>
                    <td><strong>${ag.nombre}</strong><br><small style="color:#888">${ag.usuario}</small></td>
                    <td>${ag.tickets}</td>
                    <td>S/${(ag.ventas || 0).toFixed(0)}</td>
                    <td style="color:#27ae60">S/${(ag.premios_pagados || 0).toFixed(0)}</td>
                    <td>${pendienteBadge}</td>
                    <td style="color:${colorBalance}; font-weight:bold">S/${(ag.balance || 0).toFixed(0)}</td>
                    <td>${ag.porcentaje_ventas || 0}%</td>
                </tr>`;
            });
            tbody.innerHTML = htmlTabla || '<tr><td colspan="8" style="text-align:center; color:#888;">No hay datos</td></tr>';
        }

        function cargarDashboard() {
            fetch('/admin/reporte-agencias')
            .then(r => r.json())
            .then(d => {
                if (d.global) {
                    document.getElementById('stat-ventas').textContent = 'S/' + (d.global.ventas || 0).toFixed(0);
                    document.getElementById('stat-premios').textContent = 'S/' + (d.global.pagos || 0).toFixed(0);
                    document.getElementById('stat-premios-pendientes').textContent = 'S/' + (d.global.premios_pendientes || 0).toFixed(0);
                    document.getElementById('stat-balance').textContent = 'S/' + (d.global.balance || 0).toFixed(0);
                }
            })
            .catch(e => console.error("Error dashboard:", e));
        }

        function cargarAgenciasSelect() {
            fetch('/admin/lista-agencias')
            .then(r => r.json())
            .then(d => {
                if (d.error) return;
                let select = document.getElementById('riesgo-agencia-select');
                select.innerHTML = '<option value="">TODAS LAS AGENCIAS</option>';
                d.forEach(ag => {
                    select.innerHTML += `<option value="${ag.id}">${ag.nombre_agencia}</option>`;
                });
            })
            .catch(e => console.error("Error cargando agencias:", e));
        }

        function cargarAgenciasReporte() {
            fetch('/admin/lista-agencias')
            .then(r => r.json())
            .then(d => {
                if (d.error) return;
                let select = document.getElementById('reporte-agencia-select');
                select.innerHTML = '<option value="">TODAS LAS AGENCIAS</option>';
                d.forEach(ag => {
                    select.innerHTML += `<option value="${ag.id}">${ag.nombre_agencia}</option>`;
                });
            })
            .catch(e => console.error("Error:", e));
        }

        function exportarCSV() {
            showMensaje('Preparando exportación...', 'success');
            // Implementar exportación real aquí si es necesario
        }

        function setRango(tipo) {
            let hoy = new Date();
            let inicio, fin;
            
            switch(tipo) {
                case 'hoy':
                    inicio = fin = hoy;
                    break;
                case 'ayer':
                    let ayer = new Date(hoy);
                    ayer.setDate(ayer.getDate() - 1);
                    inicio = fin = ayer;
                    break;
                case 'semana':
                    inicio = new Date(hoy);
                    inicio.setDate(inicio.getDate() - 6);
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
                showMensaje('Seleccione fechas', 'error');
                return;
            }
            
            showMensaje('Consultando...', 'success');
            
            fetch('/admin/estadisticas-rango', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})
            })
            .then(r => r.json())
            .then(d => {
                document.getElementById('historico-resumen').style.display = 'block';
                
                if (d.totales) {
                    document.getElementById('hist-total-ventas').textContent = 'S/' + (d.totales.ventas || 0).toFixed(0);
                    document.getElementById('hist-total-premios').textContent = 'S/' + (d.totales.premios || 0).toFixed(0);
                    document.getElementById('hist-total-tickets').textContent = d.totales.tickets || 0;
                    document.getElementById('hist-total-balance').textContent = 'S/' + (d.totales.balance || 0).toFixed(0);
                }
                
                let tbody = document.getElementById('tabla-historico');
                let html = '';
                (d.resumen_por_dia || []).forEach(dia => {
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
                
                // Top animales
                if (d.top_animales && d.top_animales.length > 0) {
                    let htmlTop = '';
                    d.top_animales.slice(0, 5).forEach(a => {
                        htmlTop += `<div style="padding: 10px; background: rgba(255,215,0,0.1); margin: 5px 0; border-radius: 6px;">
                            <strong>${a.numero} - ${a.nombre}</strong>: S/${a.total_apostado} apostado
                        </div>`;
                    });
                    document.getElementById('top-animales-hist').innerHTML = htmlTop;
                }
            })
            .catch(e => showMensaje('Error: ' + e.message, 'error'));
        }

        function cargarRiesgo() {
            let agenciaId = document.getElementById('riesgo-agencia-select').value;
            let url = '/admin/riesgo';
            
            if (agenciaId) url += '?agencia_id=' + agenciaId;
            
            fetch(url)
            .then(r => r.json())
            .then(d => {
                if (d.sorteo_objetivo) {
                    document.getElementById('sorteo-objetivo').textContent = d.sorteo_objetivo;
                    document.getElementById('total-apostado-sorteo').textContent = 'S/' + (d.total_apostado || 0).toFixed(2);
                } else {
                    document.getElementById('sorteo-objetivo').textContent = 'No hay sorteo activo';
                    document.getElementById('total-apostado-sorteo').textContent = 'S/0';
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
                        <small>Apostado: S/${v.apostado.toFixed(2)} • Pagaría: S/${v.pagaria.toFixed(2)} • ${v.porcentaje}% del total</small>
                    </div>`;
                }
                container.innerHTML = html;
            })
            .catch(e => {
                document.getElementById('lista-riesgo').innerHTML = '<p style="color:#c0392b; text-align: center;">Error cargando riesgo</p>';
            });
        }

        function cargarResultadosAdmin() {
            fetch('/admin/resultados-hoy')
            .then(r => r.json())
            .then(d => {
                document.getElementById('admin-resultados-titulo').textContent = 'HOY - ' + new Date().toLocaleDateString('es-PE');
                renderizarResultadosAdmin(d.resultados || {}, d.fecha);
            })
            .catch(e => {
                document.getElementById('lista-resultados-admin').innerHTML = '<p style="color: #c0392b; text-align: center;">Error de conexión</p>';
            });
        }

        function cargarResultadosAdminFecha() {
            let fecha = document.getElementById('admin-resultados-fecha').value;
            if (!fecha) return;
            
            document.getElementById('lista-resultados-admin').innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Cargando...</p>';
            
            fetch('/api/resultados-fecha', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha: fecha})
            })
            .then(r => r.json())
            .then(d => {
                let fechaObj = new Date(fecha + 'T00:00:00');
                document.getElementById('admin-resultados-titulo').textContent = fechaObj.toLocaleDateString('es-PE', {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'});
                renderizarResultadosAdmin(d.resultados || {}, d.fecha_consulta);
            })
            .catch(e => {
                document.getElementById('lista-resultados-admin').innerHTML = '<p style="color: #c0392b; text-align: center;">Error de conexión</p>';
            });
        }

        function renderizarResultadosAdmin(resultados, fechaStr) {
            let container = document.getElementById('lista-resultados-admin');
            let html = '';
            
            for (let hora of {{horarios|tojson}}) {
                let resultado = resultados[hora];
                if (resultado) {
                    html += `<div class="resultado-item">
                        <div><strong style="color: #ffd700;">${hora}</strong></div>
                        <div style="text-align: right;">
                            <div style="color: #ffd700; font-weight: bold; font-size: 1.3rem;">${resultado.animal}</div>
                            <div style="color: #888;">${resultado.nombre}</div>
                        </div>
                    </div>`;
                } else {
                    html += `<div class="resultado-item pendiente">
                        <div><strong style="color: #ffd700;">${hora}</strong></div>
                        <div style="color: #666;">Pendiente</div>
                    </div>`;
                }
            }
            container.innerHTML = html;
        }

        function guardarResultado() {
            let hora = document.getElementById('res-hora').value;
            let animal = document.getElementById('res-animal').value;
            let fecha = document.getElementById('admin-resultados-fecha').value;
            
            let form = new FormData();
            form.append('hora', hora);
            form.append('animal', animal);
            if (fecha) form.append('fecha', fecha);
            
            fetch('/admin/guardar-resultado', {method: 'POST', body: form})
            .then(r => r.json()).then(d => {
                if (d.status === 'ok') {
                    showMensaje(d.mensaje, 'success');
                    if (!fecha || fecha === new Date().toISOString().split('T')[0]) {
                        cargarResultadosAdmin();
                    } else {
                        cargarResultadosAdminFecha();
                    }
                } else {
                    showMensaje(d.error || 'Error al guardar', 'error');
                }
            });
        }

        function cargarAgencias() {
            fetch('/admin/lista-agencias')
            .then(r => r.json())
            .then(d => {
                let tbody = document.getElementById('tabla-agencias');
                if (!d || d.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 20px;">No hay agencias</td></tr>';
                    return;
                }
                let html = '';
                for (let a of d) {
                    html += `<tr>
                        <td>${a.id}</td>
                        <td>${a.usuario}</td>
                        <td>${a.nombre_agencia}</td>
                        <td>${(a.comision * 100).toFixed(0)}%</td>
                    </tr>`;
                }
                tbody.innerHTML = html;
            })
            .catch(e => {
                document.getElementById('tabla-agencias').innerHTML = '<tr><td colspan="4" style="text-align:center; color:#c0392b; padding: 20px;">Error al cargar</td></tr>';
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
                    showMensaje(d.mensaje, 'success');
                    document.getElementById('new-usuario').value = '';
                    document.getElementById('new-password').value = '';
                    document.getElementById('new-nombre').value = '';
                    cargarAgencias();
                } else {
                    showMensaje(d.error || 'Error', 'error');
                }
            });
        }

        function pagarTicketAdmin() {
            let serial = document.getElementById('pagar-serial-admin').value.trim();
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
                    document.getElementById('resultado-pago-admin').innerHTML = `<div class="error-box">${d.error}</div>`;
                    return;
                }
                
                let html = `<div class="success-box">
                    <h4>Ticket #${d.ticket_id}</h4>
                    <p style="font-size: 1.3rem; margin: 10px 0;">Total Ganado: S/${d.total_ganado.toFixed(2)}</p>
                    ${d.total_ganado > 0 ? `<button onclick="confirmarPagoAdmin('${d.ticket_id}')" class="btn-submit" style="margin-top: 10px;">CONFIRMAR PAGO</button>` : '<p>No tiene premio</p>'}
                </div>`;
                
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
                    showMensaje('Pago realizado con éxito', 'success');
                    document.getElementById('resultado-pago-admin').innerHTML = '<div class="success-box">✅ Ticket pagado correctamente</div>';
                } else {
                    showMensaje(d.error || 'Error al pagar', 'error');
                }
            });
        }

        function anularTicketAdmin() {
            let serial = document.getElementById('anular-serial').value.trim();
            if (!serial) {
                showMensaje('Ingrese un serial', 'error');
                return;
            }
            
            if (!confirm('¿Está seguro de anular el ticket ' + serial + '?')) return;
            
            fetch('/api/anular-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => {
                let div = document.getElementById('resultado-anular');
                if (d.error) {
                    div.innerHTML = `<div class="error-box">${d.error}</div>`;
                    showMensaje(d.error, 'error');
                } else {
                    div.innerHTML = `<div class="success-box">${d.mensaje}</div>`;
                    showMensaje(d.mensaje, 'success');
                    document.getElementById('anular-serial').value = '';
                }
            });
        }
    </script>
</body>
</html>
'''

# ==================== MAIN ====================
if __name__ == '__main__':
    print("=" * 60)
    print("  ZOOLO CASINO CLOUD v5.9.1 - REPARADO")
    print("=" * 60)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
