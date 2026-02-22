#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v7.1 - CORRECCIONES COMPLETAS
✓ Reportes históricos funcionando correctamente
✓ Límite aumentado a 5000 tickets
✓ Reimpresión de tickets funcional
✓ Tripletas con detalles completos
✓ Decimales funcionando en tickets (0.5, 1.5, etc.)
✓ Tickets vendidos aparecen inmediatamente
✓ Anulación funcional con validaciones correctas
✓ Estados: todos, activos, pagados, pendientes, anulados, por_pagar
✓ Resultados cargan y editan correctamente
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

# Configuracion de negocio
PAGO_ANIMAL_NORMAL = 35      
PAGO_LECHUZA = 70           
PAGO_ESPECIAL = 2           
PAGO_TRIPLETA = 60          
COMISION_AGENCIA = 0.15
MINUTOS_BLOQUEO = 5
HORAS_EDICION_RESULTADO = 2

# ==================== NUEVOS HORARIOS ACTUALIZADOS ====================
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

# ==================== FUNCIONES ZONA HORARIA CORREGIDAS ====================
def hora_a_minutos(hora_str):
    """Convierte '07:00 PM' a minutos desde medianoche"""
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
    
    # Si es fecha diferente a hoy, permitir edición siempre
    if fecha_str and fecha_str != hoy:
        return True
    
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

# ==================== FUNCION SUPABASE MEJORADA CON LIMITE 5000 ====================
def supabase_request(table, method="GET", data=None, filters=None, timeout=30, limit=None):
    """Función mejorada para consultas a Supabase con soporte para límites"""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    params = []
    if filters:
        for k, v in filters.items():
            if k.endswith('__like'):
                params.append(f"{k.replace('__like', '')}=like.{urllib.parse.quote(str(v))}")
            elif k.endswith('__gte'):
                params.append(f"{k.replace('__gte', '')}=gte.{urllib.parse.quote(str(v))}")
            elif k.endswith('__lte'):
                params.append(f"{k.replace('__lte', '')}=lte.{urllib.parse.quote(str(v))}")
            elif k.endswith('__in'):
                params.append(f"{k.replace('__in', '')}=in.({urllib.parse.quote(str(v))})")
            else:
                params.append(f"{k}=eq.{urllib.parse.quote(str(v))}")
    
    # Aumentar límite a 5000 tickets
    if limit:
        params.append(f"limit={limit}")
    else:
        params.append("limit=5000")
    
    if params:
        url += "?" + "&".join(params)
    
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

# ==================== FUNCION PARA FORMATEAR MONTOS CON DECIMALES ====================
def formatear_monto(monto):
    """Formatea el monto mostrando decimales correctamente (0.5, 1.5, etc.)"""
    try:
        monto_float = float(monto)
        # Si es entero, mostrar sin decimales
        if monto_float == int(monto_float):
            return str(int(monto_float))
        else:
            # Mostrar con 1 decimal si tiene decimales
            return f"{monto_float:.1f}"
    except:
        return str(monto)

@app.route('/api/procesar-venta', methods=['POST'])
@agencia_required
def procesar_venta():
    try:
        data = request.get_json()
        jugadas = data.get('jugadas', [])
        
        if not jugadas:
            return jsonify({'error': 'Ticket vacio'}), 400
        
        # Verificar bloqueo solo para jugadas normales (no tripletas que son todo el día)
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
                # Guardar tripleta en tabla separada
                nums = j['seleccion'].split(',')
                tripleta_data = {
                    "ticket_id": ticket_id,
                    "animal1": nums[0],
                    "animal2": nums[1],
                    "animal3": nums[2],
                    "monto": j['monto'],
                    "fecha": fecha.split(' ')[0],  # Solo la fecha sin hora
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
        
        # Agrupar jugadas normales por hora
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
                    # CORREGIDO: Usar formatear_monto para decimales
                    monto_str = formatear_monto(j['monto'])
                    texto_jugadas.append(f"{nombre_corto}{j['seleccion']}x{monto_str}")
                else:
                    tipo_corto = j['seleccion'][0:3]
                    monto_str = formatear_monto(j['monto'])
                    texto_jugadas.append(f"{tipo_corto}x{monto_str}")
            
            lineas.append(" ".join(texto_jugadas))
            lineas.append("")
        
        # Agregar tripletas al ticket de texto
        tripletas_en_ticket = [j for j in jugadas if j['tipo'] == 'tripleta']
        if tripletas_en_ticket:
            lineas.append("*TRIPLETAS (Paga x60)*")
            for t in tripletas_en_ticket:
                nums = t['seleccion'].split(',')
                nombres = [ANIMALES.get(n, '')[0:3].upper() for n in nums]
                monto_str = formatear_monto(t['monto'])
                lineas.append(f"{'-'.join(nombres)} (x60) S/{monto_str}")
            lineas.append("")
        
        lineas.append("------------------------")
        # CORREGIDO: Mostrar total con decimales si aplica
        total_str = formatear_monto(total)
        lineas.append(f"*TOTAL: S/{total_str}*")
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

# ==================== NUEVAS APIS DE CONSULTA PARA AGENCIAS - CORREGIDAS ====================

@app.route('/api/mis-tickets', methods=['POST'])
@agencia_required
def mis_tickets():
    try:
        data = request.get_json() or {}
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        estado = data.get('estado', 'todos')
        
        # CORREGIDO: Usar límite 5000 en lugar de 500
        filters = {"agencia_id": session['user_id']}
        all_tickets = supabase_request("tickets", filters=filters, limit=5000)
        
        if all_tickets is None:
            all_tickets = []
        
        tickets_filtrados = []
        dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d") if fecha_inicio else None
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59) if fecha_fin else None
        
        for t in all_tickets:
            dt_ticket = parse_fecha_ticket(t['fecha'])
            if not dt_ticket:
                continue
                
            if dt_inicio and dt_ticket < dt_inicio:
                continue
            if dt_fin and dt_ticket > dt_fin:
                continue
            
            # CORREGIDO: Filtros de estado mejorados
            if estado == 'pagados' and not t.get('pagado'):
                continue
            if estado == 'pendientes' and t.get('pagado'):
                continue
            if estado == 'anulados' and not t.get('anulado'):
                continue
            if estado == 'activos' and t.get('anulado'):
                continue
            # Para 'todos', mostrar todo incluyendo anulados
            if estado == 'todos':
                pass  # No filtrar nada
            elif estado not in ['todos', 'pagados', 'pendientes', 'anulados', 'activos', 'por_pagar']:
                # Si no es anulado y estado no reconocido, mostrar solo activos
                if t.get('anulado'):
                    continue
                
            tickets_filtrados.append(t)
        
        if estado == 'por_pagar':
            tickets_con_premio = []
            for t in tickets_filtrados:
                if t.get('pagado') or t.get('anulado'):
                    continue
                
                # Calcular premio incluyendo tripletas
                premio_total = calcular_premio_ticket(t)
                
                if premio_total > 0:
                    t['premio_calculado'] = round(premio_total, 2)
                    tickets_con_premio.append(t)
            
            tickets_filtrados = tickets_con_premio
        
        total_ventas = sum(t['total'] for t in tickets_filtrados)
        total_tickets = len(tickets_filtrados)
        
        # CORREGIDO: Aumentar a 200 tickets en respuesta
        tickets_respuesta = tickets_filtrados[:200]
        
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
    """Calcula el premio total de un ticket incluyendo tripletas"""
    try:
        fecha_ticket = parse_fecha_ticket(ticket['fecha']).strftime("%d/%m/%Y")
        resultados_list = supabase_request("resultados", filters={"fecha": fecha_ticket})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        total_premio = 0
        
        # Jugadas normales
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
        
        # Tripletas
        tripletas = supabase_request("tripletas", filters={"ticket_id": ticket['id']})
        if tripletas:
            for trip in tripletas:
                # Verificar si los 3 números salieron durante el día
                nums = [trip['animal1'], trip['animal2'], trip['animal3']]
                nums_encontrados = []
                
                for hora, animal in resultados.items():
                    if animal in nums and animal not in nums_encontrados:
                        nums_encontrados.append(animal)
                
                if len(nums_encontrados) == 3:  # Salieron los 3
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
        
        # Procesar jugadas normales
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
        
        # Procesar tripletas - CORREGIDO: Mostrar detalles completos
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

# ==================== NUEVO ENDPOINT: REIMPRIMIR TICKET ====================
@app.route('/api/reimprimir-ticket', methods=['POST'])
@login_required
def reimprimir_ticket():
    """Reimprime un ticket existente generando el texto para WhatsApp nuevamente"""
    try:
        data = request.get_json()
        serial = data.get('serial')
        
        if not serial:
            return jsonify({'error': 'Serial requerido'}), 400
        
        # Buscar ticket
        tickets = supabase_request("tickets", filters={"serial": serial})
        if not tickets or len(tickets) == 0:
            return jsonify({'error': 'Ticket no encontrado'})
        
        ticket = tickets[0]
        
        # Verificar permisos
        if not session.get('es_admin') and ticket['agencia_id'] != session['user_id']:
            return jsonify({'error': 'No autorizado para reimprimir este ticket'})
        
        if ticket.get('anulado'):
            return jsonify({'error': 'No se puede reimprimir: Ticket anulado'})
        
        # Obtener jugadas
        jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
        tripletas = supabase_request("tripletas", filters={"ticket_id": ticket['id']})
        
        # Obtener info de agencia
        agencias = supabase_request("agencias", filters={"id": ticket['agencia_id']})
        nombre_agencia = agencias[0]['nombre_agencia'] if agencias else 'Agencia'
        
        # Generar texto del ticket nuevamente
        jugadas_por_hora = defaultdict(list)
        if jugadas:
            for j in jugadas:
                jugadas_por_hora[j['hora']].append(j)
        
        lineas = [
            f"*{nombre_agencia}*",
            f"*TICKET:* #{ticket['id']}",
            f"*SERIAL:* {serial}",
            f"*REIMPRESION*",
            ticket['fecha'],
            "------------------------",
            ""
        ]
        
        # Procesar jugadas normales
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
                    monto_str = formatear_monto(j['monto'])
                    texto_jugadas.append(f"{nombre_corto}{j['seleccion']}x{monto_str}")
                else:
                    tipo_corto = j['seleccion'][0:3]
                    monto_str = formatear_monto(j['monto'])
                    texto_jugadas.append(f"{tipo_corto}x{monto_str}")
            
            lineas.append(" ".join(texto_jugadas))
            lineas.append("")
        
        # Procesar tripletas
        if tripletas:
            lineas.append("*TRIPLETAS (Paga x60)*")
            for trip in tripletas:
                nums = [trip['animal1'], trip['animal2'], trip['animal3']]
                nombres = [ANIMALES.get(n, '')[0:3].upper() for n in nums]
                monto_str = formatear_monto(trip['monto'])
                lineas.append(f"{'-'.join(nombres)} (x60) S/{monto_str}")
            lineas.append("")
        
        lineas.append("------------------------")
        total_str = formatear_monto(ticket['total'])
        lineas.append(f"*TOTAL: S/{total_str}*")
        lineas.append("")
        lineas.append("Buena Suerte! 🍀")
        lineas.append("El ticket vence a los 3 dias")
        
        texto_whatsapp = "\n".join(lineas)
        url_whatsapp = f"https://wa.me/?text={urllib.parse.quote(texto_whatsapp)}"
        
        return jsonify({
            'status': 'ok',
            'mensaje': 'Ticket listo para reimprimir',
            'ticket': {
                'id': ticket['id'],
                'serial': ticket['serial'],
                'fecha': ticket['fecha'],
                'total': ticket['total'],
                'pagado': ticket.get('pagado', False),
                'anulado': ticket.get('anulado', False)
            },
            'texto_ticket': texto_whatsapp,
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
        
        if not session.get('es_admin') and ticket['agencia_id'] != session['user_id']:
            return jsonify({'error': 'No autorizado para ver este ticket'})
        
        if ticket.get('anulado'):
            return jsonify({'error': 'TICKET ANULADO'})
        if ticket.get('pagado'):
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
        
        # Marcar ticket como pagado
        url = f"{SUPABASE_URL}/rest/v1/tickets?id=eq.{urllib.parse.quote(str(ticket_id))}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        data = json.dumps({"pagado": True}).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
        urllib.request.urlopen(req, timeout=15)
        
        # Marcar tripletas como pagadas también
        url_trip = f"{SUPABASE_URL}/rest/v1/tripletas?ticket_id=eq.{urllib.parse.quote(str(ticket_id))}"
        data_trip = json.dumps({"pagado": True}).encode()
        req_trip = urllib.request.Request(url_trip, data=data_trip, headers=headers, method="PATCH")
        try:
            urllib.request.urlopen(req_trip, timeout=15)
        except:
            pass  # Si no hay tripletas, no importa el error
        
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
        
        # CORREGIDO: Verificar si ya está anulado
        if ticket.get('anulado'):
            return jsonify({'error': 'Este ticket ya fue anulado anteriormente'})
        
        if not session.get('es_admin') and ticket['agencia_id'] != session['user_id']:
            return jsonify({'error': 'No autorizado para anular este ticket'})
        
        if ticket.get('pagado'):
            return jsonify({'error': 'Ya esta pagado, no se puede anular'})
        
        # Validaciones de tiempo para agencias (admin puede anular sin límite de tiempo)
        if not session.get('es_admin'):
            fecha_ticket = parse_fecha_ticket(ticket['fecha'])
            if not fecha_ticket:
                return jsonify({'error': 'Error en fecha del ticket'})
            
            # Verificar que no hayan pasado más de 5 minutos desde la creación
            minutos_transcurridos = (ahora_peru() - fecha_ticket).total_seconds() / 60
            if minutos_transcurridos > 5:
                return jsonify({'error': f'No puede anular después de 5 minutos. Han pasado {int(minutos_transcurridos)} minutos'})
            
            # Verificar que el sorteo no haya iniciado (para jugadas normales)
            jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
            if jugadas:
                for j in jugadas:
                    if j['tipo'] != 'tripleta' and not verificar_horario_bloqueo(j['hora']):
                        return jsonify({'error': f'No se puede anular, el sorteo {j["hora"]} ya cerro o esta por iniciar'})
        else:
            # Admin también verifica que el sorteo no haya cerrado
            jugadas = supabase_request("jugadas", filters={"ticket_id": ticket['id']})
            if jugadas:
                for j in jugadas:
                    if j['tipo'] != 'tripleta' and not verificar_horario_bloqueo(j['hora']):
                        return jsonify({'error': f'No se puede anular, el sorteo {j["hora"]} ya esta cerrado'})
        
        # Proceder a anular
        url = f"{SUPABASE_URL}/rest/v1/tickets?id=eq.{urllib.parse.quote(str(ticket['id']))}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        data = json.dumps({"anulado": True}).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
        urllib.request.urlopen(req, timeout=15)
        
        return jsonify({'status': 'ok', 'mensaje': f'Ticket #{serial} anulado correctamente'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/caja')
@agencia_required
def caja_agencia():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        
        # CORREGIDO: Usar supabase_request con límite 5000
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(hoy)}%25&limit=5000"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        
        ventas = sum(t['total'] for t in tickets if t['agencia_id'] == session['user_id'] and not t.get('anulado'))
        
        agencias = supabase_request("agencias", filters={"id": session['user_id']})
        comision_pct = agencias[0]['comision'] if agencias else COMISION_AGENCIA
        comision = ventas * comision_pct
        
        premios = 0
        tickets_pendientes = 0
        
        for t in tickets:
            if t['agencia_id'] == session['user_id'] and not t.get('anulado'):
                premio_ticket = calcular_premio_ticket(t)
                
                if t.get('pagado'):
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
        
        # CORREGIDO: Usar límite 5000
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
                dias_data[dia_key] = {
                    'ventas': 0, 'tickets': 0, 'premios': 0,
                    'pendientes': 0
                }
            
            dias_data[dia_key]['ventas'] += t['total']
            dias_data[dia_key]['tickets'] += 1
            total_ventas += t['total']
            
            premio_ticket = calcular_premio_ticket(t)
            
            if t.get('pagado'):
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
        hoy = ahora_peru().strftime("%d/%m/%Y")
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{session['user_id']}&anulado=eq.false&pagado=eq.false&limit=5000"
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
                
                tickets_con_premio.append({
                    'serial': t['serial'],
                    'fecha': t['fecha'],
                    'total': t['total'],
                    'premio': round(premio_total, 2),
                    'jugadas': len(jugadas) + len(tripletas)
                })
        
        return jsonify({
            'status': 'ok',
            'tickets': tickets_con_premio,
            'total_pendiente': sum(t['premio'] for t in tickets_con_premio)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== API ADMIN - CORREGIDO RESULTADOS ====================
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

# ==================== CORREGIDO: GUARDAR RESULTADO ====================
@app.route('/admin/guardar-resultado', methods=['POST'])
@admin_required
def guardar_resultado():
    try:
        hora = request.form.get('hora')
        animal = request.form.get('animal')
        fecha_input = request.form.get('fecha')
        
        if not hora or not animal:
            return jsonify({'error': 'Hora y animal requeridos'}), 400
        
        if animal not in ANIMALES:
            return jsonify({'error': f'Animal inválido: {animal}'}), 400
        
        # Determinar la fecha
        if fecha_input:
            try:
                fecha_obj = datetime.strptime(fecha_input, "%Y-%m-%d")
                fecha = fecha_obj.strftime("%d/%m/%Y")
            except:
                fecha = ahora_peru().strftime("%d/%m/%Y")
        else:
            fecha = ahora_peru().strftime("%d/%m/%Y")
        
        hoy = ahora_peru().strftime("%d/%m/%Y")
        
        # Verificar si existe el resultado
        existentes = supabase_request("resultados", filters={"fecha": fecha, "hora": hora})
        
        if existentes and len(existentes) > 0:
            # ACTUALIZAR resultado existente
            # CORREGIDO: Verificar restricción de tiempo solo para hoy
            if fecha == hoy:
                if not puede_editar_resultado(hora, fecha):
                    return jsonify({
                        'error': f'No se puede editar. Solo disponible hasta 2 horas después del sorteo.'
                    }), 403
            
            # CORREGIDO: Usar PATCH correctamente
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
                error_msg = e.read().decode()
                print(f"[ERROR PATCH] HTTP {e.code}: {error_msg}")
                return jsonify({'error': f'Error al actualizar: HTTP {e.code}'}), 500
                
        else:
            # CREAR nuevo resultado
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(fecha)}%25&anulado=eq.false&limit=5000"
        
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

@app.route('/admin/tripletas-hoy')
@admin_required
def tripletas_hoy():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        
        # Obtener todas las tripletas de hoy
        url = f"{SUPABASE_URL}/rest/v1/tripletas?fecha=eq.{urllib.parse.quote(hoy)}&limit=5000"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            tripletas = json.loads(response.read().decode())
        
        if not tripletas:
            return jsonify({'tripletas': [], 'total': 0, 'ganadoras': 0})
        
        # Obtener resultados del día
        resultados_list = supabase_request("resultados", filters={"fecha": hoy})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        # Procesar cada tripleta
        tripletas_procesadas = []
        ganadoras = 0
        
        for trip in tripletas:
            # Obtener info del ticket
            tickets = supabase_request("tickets", filters={"id": trip['ticket_id']})
            if not tickets:
                continue
            
            ticket = tickets[0]
            agencias = supabase_request("agencias", filters={"id": ticket['agencia_id']})
            nombre_agencia = agencias[0]['nombre_agencia'] if agencias else 'Desconocida'
            
            # Verificar si ganó
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
        
        # CORREGIDO: Usar límite 5000
        if agencia_id:
            url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{agencia_id}&order=fecha.desc&limit=5000"
        else:
            url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=5000"
            
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
                'premios_pagados': 0,
                'premios_pendientes': 0,
                'premios_teoricos': 0,
                'comision': 0,
                'balance': 0,
                'tickets_pagados_count': 0,
                'tickets_pendientes_count': 0
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
            
            # Jugadas normales
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
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
            
            # Tripletas
            tripletas = supabase_request("tripletas", filters={"ticket_id": t['id']})
            if tripletas:
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
            
            if t.get('pagado'):
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
                
                stats['ventas'] = round(stats['ventas'], 2)
                stats['premios_pagados'] = round(stats['premios_pagados'], 2)
                stats['premios_pendientes'] = round(stats['premios_pendientes'], 2)
                stats['premios_teoricos'] = round(stats['premios_teoricos'], 2)
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
        
        # CORREGIDO: Usar límite 5000
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=5000"
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
            
            if t.get('pagado'):
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(hoy)}%25&limit=5000"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        
        data_agencias = []
        total_ventas = total_premios = total_comisiones = 0
        
        for ag in agencias:
            ventas = sum(t['total'] for t in tickets if t['agencia_id'] == ag['id'] and not t.get('anulado'))
            comision = ventas * ag['comision']
            
            premios_pagados = 0
            premios_pendientes = 0
            
            for t in tickets:
                if t['agencia_id'] == ag['id'] and not t.get('anulado'):
                    premio_ticket = calcular_premio_ticket(t)
                    
                    if t.get('pagado'):
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
        
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(hoy)}%25&anulado=eq.false&limit=5000"
        
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
        
        # CORREGIDO: Usar límite 5000
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=5000"
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
                t = next((tk for tk in tickets_rango if tk['id'] == ticket_id), None)
                if t:
                    premio_ticket = calcular_premio_ticket(t)
                    premios_dia += premio_ticket
            
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
        
        # CORREGIDO: Usar límite 5000
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
    <title>Login - ZOOLO CASINO v7.1</title>
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
        .version-badge {
            background: linear-gradient(45deg, #27ae60, #229954);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: bold;
            display: inline-block;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="login-box">
        <div class="version-badge">v7.1 CORREGIDO</div>
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
            Sistema ZOOLO CASINO v7.1<br>
            ✓ Reportes históricos<br>
            ✓ Reimpresión de tickets<br>
            ✓ Decimales funcionando
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
        .animal-card.tripleta-seleccionado {
            box-shadow: 0 0 15px rgba(255,215,0,0.9); 
            border-color: #ffd700 !important;
            background: linear-gradient(135deg, #4a3c00, #2a2000);
            transform: scale(1.08);
            z-index: 15;
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
        .btn-tripleta { 
            background: linear-gradient(135deg, #FFD700, #FFA500); 
            color: black; 
            font-weight: bold;
            border: 2px solid #FFD700;
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
        }
        .btn-tripleta.active {
            background: linear-gradient(135deg, #FFA500, #FF8C00);
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.6);
            transform: scale(0.95);
        }
        .btn-anular { background: #c0392b; color: white; }
        .btn-borrar { background: #555; color: white; }
        .btn-salir { background: #333; color: white; grid-column: span 3; }
        
        .tripleta-info {
            background: linear-gradient(135deg, rgba(255,215,0,0.2), rgba(255,165,0,0.1));
            border: 2px solid #FFD700;
            border-radius: 8px;
            padding: 10px;
            margin: 0 10px 10px;
            text-align: center;
            color: #FFD700;
            font-weight: bold;
            display: none;
        }
        .tripleta-info.active {
            display: block;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 5px rgba(255,215,0,0.5); }
            50% { box-shadow: 0 0 20px rgba(255,215,0,0.8); }
        }
        
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
        
        .alert-box {
            background: rgba(243, 156, 18, 0.15); 
            border: 1px solid #f39c12;
            padding: 15px; 
            border-radius: 8px; 
            margin: 15px 0; 
            font-size: 0.9rem;
        }
        .alert-box strong { color: #f39c12; }

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
        
        .ticket-item {
            background: #0a0a0a;
            padding: 15px;
            margin: 8px 0;
            border-radius: 10px;
            border-left: 4px solid #2980b9;
            cursor: pointer;
            transition: all 0.2s;
        }
        .ticket-item:active {
            background: #1a1a2e;
        }
        .ticket-item.ganador {
            border-left-color: #27ae60;
            background: rgba(39,174,96,0.1);
        }
        .ticket-item.pendiente-pago {
            border-left-color: #f39c12;
            background: rgba(243,156,18,0.1);
        }
        .ticket-item.anulado {
            border-left-color: #c0392b;
            background: rgba(192,57,43,0.1);
            opacity: 0.7;
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
        .ticket-estado {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: bold;
            margin-top: 5px;
        }
        .estado-pagado { background: #27ae60; color: white; }
        .estado-pendiente { background: #f39c12; color: black; }
        .estado-anulado { background: #c0392b; color: white; }
        
        .filter-row {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        .filter-row select, .filter-row input {
            flex: 1;
            min-width: 120px;
            padding: 10px;
            background: #000;
            border: 1px solid #444;
            color: white;
            border-radius: 6px;
        }
        
        .jugada-detail {
            background: #111;
            padding: 8px;
            margin: 4px 0;
            border-radius: 6px;
            font-size: 0.85rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .jugada-ganadora {
            background: rgba(39,174,96,0.2);
            border: 1px solid #27ae60;
        }
        
        .btn-reimprimir {
            background: linear-gradient(135deg, #2980b9, #3498db);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: bold;
            margin-top: 10px;
        }
        
        .btn-anular-ticket {
            background: #c0392b;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: bold;
            margin-top: 10px;
            margin-left: 10px;
        }
    </style>
</head>
<body>
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
                    <li class="win-submenu-item"><a onclick="abrirMisTickets()">🎫 Mis Tickets Vendidos</a></li>
                    <li class="win-submenu-item"><a onclick="abrirBuscarTicket()">🔎 Buscar Ticket por Serial</a></li>
                    <li class="win-submenu-item"><a onclick="abrirMisTicketsPendientes()">💰 Tickets por Cobrar</a></li>
                    <li class="win-submenu-item"><a onclick="verResultados()">📋 Resultados de Hoy</a></li>
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
            <div class="mobile-menu-item" onclick="abrirMisTicketsMobile()">🎫 Mis Tickets Vendidos</div>
            <div class="mobile-menu-item" onclick="abrirBuscarTicketMobile()">🔎 Buscar Ticket</div>
            <div class="mobile-menu-item" onclick="abrirMisTicketsPendientesMobile()">💰 Tickets por Cobrar</div>
            <div class="mobile-menu-item" onclick="verResultadosMobile()">📋 Resultados</div>
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

    <div class="header">
        <div class="header-info">
            <h3>{{agencia}}</h3>
            <p id="reloj">--</p>
        </div>
        <div class="monto-box">
            <span>S/:</span>
            <input type="number" id="monto" value="5" min="0.5" step="0.5">
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

    <div class="modal" id="modal-mis-tickets">
        <div class="modal-content">
            <div class="modal-header">
                <h3>🎫 MIS TICKETS VENDIDOS</h3>
                <button class="btn-close" onclick="cerrarModal('modal-mis-tickets')">X</button>
            </div>
            
            <div class="filter-row">
                <input type="date" id="mis-tickets-fecha-inicio" placeholder="Desde">
                <input type="date" id="mis-tickets-fecha-fin" placeholder="Hasta">
                <select id="mis-tickets-estado">
                    <option value="todos">Todos</option>
                    <option value="activos">Activos (no anulados)</option>
                    <option value="pagados">Pagados</option>
                    <option value="pendientes">Pendientes</option>
                    <option value="anulados">Anulados</option>
                    <option value="por_pagar">Con Premio (por cobrar)</option>
                </select>
            </div>
            <button class="btn-consultar" onclick="consultarMisTickets()">BUSCAR</button>
            
            <div id="mis-tickets-resumen" style="margin: 15px 0; padding: 10px; background: rgba(255,215,0,0.1); border-radius: 8px; display: none;">
                <strong style="color: #ffd700;">Resumen:</strong> <span id="mis-tickets-info"></span>
            </div>
            
            <div id="lista-mis-tickets" style="max-height: 400px; overflow-y: auto; margin-top: 15px;">
                <p style="color: #888; text-align: center; padding: 20px;">Use los filtros y presione BUSCAR</p>
            </div>
        </div>
    </div>

    <div class="modal" id="modal-buscar-ticket">
        <div class="modal-content">
            <div class="modal-header">
                <h3>🔎 BUSCAR TICKET POR SERIAL</h3>
                <button class="btn-close" onclick="cerrarModal('modal-buscar-ticket')">X</button>
            </div>
            
            <div class="form-group">
                <label>Ingrese el número de serial:</label>
                <input type="text" id="buscar-serial-input" placeholder="Ej: 1234567890" style="font-size: 1.2rem; text-align: center; letter-spacing: 2px;">
            </div>
            <button class="btn-consultar" onclick="buscarTicketEspecifico()">BUSCAR TICKET</button>
            
            <div id="resultado-busqueda-ticket" style="margin-top: 20px;">
            </div>
        </div>
    </div>

    <div class="modal" id="modal-calculadora">
        <div class="modal-content">
            <div class="modal-header">
                <h3>🧮 CALCULADORA DE PREMIOS</h3>
                <button class="btn-close" onclick="cerrarModal('modal-calculadora')">X</button>
            </div>
            
            <div class="form-group">
                <label>Monto Apostado (S/):</label>
                <input type="number" id="calc-monto" value="10" min="0.5" step="0.5">
            </div>
            
            <div class="form-group">
                <label>Tipo de Apuesta:</label>
                <select id="calc-tipo" onchange="calcularPremio()">
                    <option value="35">Animal Normal (00-39) x35</option>
                    <option value="70">Lechuza (40) x70</option>
                    <option value="2">Especial (Rojo/Negro/Par/Impar) x2</option>
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
            <div class="modal-header">
                <h3>💰 MIS TICKETS POR COBRAR</h3>
                <button class="btn-close" onclick="cerrarModal('modal-pendientes')">X</button>
            </div>
            
            <div id="pendientes-info" style="margin-bottom: 15px; color: #ffd700; font-weight: bold; text-align: center;">
                Cargando...
            </div>
            
            <div id="lista-pendientes" style="max-height: 400px; overflow-y: auto;">
            </div>
        </div>
    </div>

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
                
                <h4 style="color: #ffd700; margin: 15px 0;">🎯 TRIPLETA</h4>
                <ul style="margin-left: 20px; margin-bottom: 20px;">
                    <li>Selecciona <strong>3 animalitos</strong></li>
                    <li>Si salen los 3 durante el día: <strong style="color: #ffd700;">x60</strong></li>
                    <li>Ejemplo: S/10 → S/600</li>
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
                    <li>Horarios: 8AM a 6PM hora Perú</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="modal" id="modal-como-usar">
        <div class="modal-content">
            <div class="modal-header">
                <h3>❓ CÓMO USAR EL SISTEMA</h3>
                <button class="btn-close" onclick="cerrarModal('modal-como-usar')">X</button>
            </div>
            
            <div style="line-height: 1.8; color: #ddd;">
                <div style="background: rgba(255,215,0,0.1); padding: 15px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #ffd700;">
                    <h4 style="color: #ffd700; margin-bottom: 10px;">1. Hacer una Venta Normal</h4>
                    <ol style="margin-left: 20px; color: #aaa;">
                        <li>Selecciona el monto (puede ser 0.5, 1, 1.5, etc.)</li>
                        <li>Toca los animales que quieres jugar</li>
                        <li>Selecciona los horarios</li>
                        <li>Presiona "AGREGAR AL TICKET"</li>
                        <li>Presiona "ENVIAR POR WHATSAPP"</li>
                    </ol>
                </div>
                
                <div style="background: rgba(255,165,0,0.1); padding: 15px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #FFA500;">
                    <h4 style="color: #FFA500; margin-bottom: 10px;">2. Hacer una Tripleta</h4>
                    <ol style="margin-left: 20px; color: #aaa;">
                        <li>Presiona el botón 🎯 TRIPLETA</li>
                        <li>Selecciona exactamente 3 animalitos</li>
                        <li>Presiona "AGREGAR AL TICKET"</li>
                        <li>Paga <strong>x60</strong> veces el monto apostado</li>
                    </ol>
                </div>
                
                <div style="background: rgba(39,174,96,0.1); padding: 15px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #27ae60;">
                    <h4 style="color: #27ae60; margin-bottom: 10px;">3. Reimprimir un Ticket</h4>
                    <ol style="margin-left: 20px; color: #aaa;">
                        <li>Ve a "Mis Tickets Vendidos"</li>
                        <li>Busca el ticket</li>
                        <li>Presiona "🖨️ Reimprimir"</li>
                    </ol>
                </div>
            </div>
        </div>
    </div>

    <div class="modal" id="modal-acerca">
        <div class="modal-content" style="text-align: center;">
            <div class="modal-header">
                <h3>ℹ️ ACERCA DEL SISTEMA</h3>
                <button class="btn-close" onclick="cerrarModal('modal-acerca')">X</button>
            </div>
            
            <div style="padding: 20px;">
                <div style="font-size: 4rem; margin-bottom: 20px;">🦁</div>
                <h2 style="color: #ffd700; margin-bottom: 10px;">ZOOLO CASINO</h2>
                <p style="color: #888; font-size: 1.2rem; margin-bottom: 20px;">Versión 7.1 - Corregida</p>
                
                <div style="background: rgba(255,215,0,0.1); padding: 20px; border-radius: 10px; border: 1px solid rgba(255,215,0,0.3); margin-top: 20px;">
                    <p style="color: #ffd700; margin: 0; line-height: 1.8;">
                        <strong>Novedades v7.1:</strong><br>
                        ✓ Reportes históricos funcionando<br>
                        ✓ Reimpresión de tickets<br>
                        ✓ Decimales (0.5, 1.5, etc.)<br>
                        ✓ Hasta 5000 tickets por consulta<br>
                        ✓ Tickets anulados visibles<br>
                        ✓ Resultados cargan y editan correctamente
                    </p>
                </div>
            </div>
        </div>
    </div>

    <script>
        let seleccionados = [], especiales = [], horariosSel = [], carrito = [];
        let modoTripleta = false;
        let seleccionTripleta = [];
        let horasPeru = JSON.parse('{{ horarios_peru | tojson | safe }}');
        let horasVen = JSON.parse('{{ horarios_venezuela | tojson | safe }}');
        
        function toggleMobileMenu() {
            const menu = document.getElementById('mobileMenu');
            const overlay = document.querySelector('.mobile-menu-overlay');
            menu.classList.toggle('active');
            overlay.classList.toggle('active');
        }
        
        function abrirCajaMobile() { toggleMobileMenu(); abrirCaja(); }
        function abrirCajaHistoricoMobile() { toggleMobileMenu(); abrirCajaHistorico(); }
        function abrirCalculadoraMobile() { toggleMobileMenu(); abrirCalculadora(); }
        function abrirMisTicketsMobile() { toggleMobileMenu(); abrirMisTickets(); }
        function abrirBuscarTicketMobile() { toggleMobileMenu(); abrirBuscarTicket(); }
        function abrirMisTicketsPendientesMobile() { toggleMobileMenu(); abrirMisTicketsPendientes(); }
        function verResultadosMobile() { toggleMobileMenu(); verResultados(); }
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
        
        function toggleModoTripleta() {
            modoTripleta = !modoTripleta;
            const btn = document.getElementById('btn-tripleta');
            const banner = document.getElementById('tripleta-banner');
            
            if (modoTripleta) {
                btn.classList.add('active');
                banner.classList.add('active');
                seleccionTripleta = [];
                showToast('Modo Tripleta activado: Selecciona 3 animalitos (Paga x60)', 'info');
            } else {
                btn.classList.remove('active');
                banner.classList.remove('active');
                seleccionTripleta = [];
                document.querySelectorAll('.animal-card.tripleta-seleccionado').forEach(el => {
                    el.classList.remove('tripleta-seleccionado');
                });
            }
            updateTicket();
        }
        
        function updateReloj() {
            try {
                let now = new Date();
                let peruTime = new Date(now.toLocaleString("en-US", {timeZone: "America/Lima"}));
                document.getElementById('reloj').textContent = peruTime.toLocaleString('es-PE', {
                    hour: '2-digit', 
                    minute:'2-digit', 
                    hour12: true,
                    timeZone: 'America/Lima'
                });
                
                let horaActual = peruTime.getHours() * 60 + peruTime.getMinutes();
                
                if (typeof horasPeru === 'undefined' || !Array.isArray(horasPeru)) {
                    console.error('horasPeru no está definido correctamente');
                    return;
                }
                
                horasPeru.forEach((h, idx) => {
                    try {
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
                    } catch(e) {
                        console.error('Error procesando hora:', h, e);
                    }
                });
            } catch(e) {
                console.error('Error en updateReloj:', e);
            }
        }
        
        setInterval(updateReloj, 30000);
        setTimeout(updateReloj, 1000);
        
        function toggleAni(k, nombre) {
            if (modoTripleta) {
                let idx = seleccionTripleta.findIndex(a => a.k === k);
                let el = document.getElementById('ani-' + k);
                
                if (idx >= 0) {
                    seleccionTripleta.splice(idx, 1);
                    el.classList.remove('tripleta-seleccionado');
                } else {
                    if (seleccionTripleta.length >= 3) {
                        showToast('Solo puedes seleccionar 3 animalitos para la tripleta', 'error');
                        return;
                    }
                    seleccionTripleta.push({k, nombre});
                    el.classList.add('tripleta-seleccionado');
                    if (navigator.vibrate) navigator.vibrate(50);
                }
            } else {
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
            }
            updateTicket();
        }
        
        function toggleEsp(tipo) {
            if (modoTripleta) {
                showToast('No puedes jugar especiales en modo Tripleta', 'error');
                return;
            }
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
            if (modoTripleta) {
                showToast('Las tripletas no necesitan horario (validas todo el dia)', 'info');
                return;
            }
            let btn = document.getElementById('hora-' + id);
            if (btn.classList.contains('expired')) {
                showToast('Este sorteo ya cerro', 'error');
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
                let nom = item.tipo === 'animal' ? item.nombre.substring(0,10) : 
                         item.tipo === 'tripleta' ? 'TRIP' : item.seleccion;
                let color = item.tipo === 'animal' ? '#ffd700' : 
                           item.tipo === 'tripleta' ? '#FFA500' : '#3498db';
                let horaTxt = item.tipo === 'tripleta' ? 'Todo el dia' : item.hora;
                // CORREGIDO: Mostrar decimales correctamente
                let montoStr = item.monto % 1 === 0 ? item.monto : item.monto.toFixed(1);
                html += `<tr>
                    <td style="color:#aaa; font-size:0.75rem">${horaTxt}</td>
                    <td style="color:${color}; font-weight:bold; font-size:0.8rem">${item.seleccion} ${nom}</td>
                    <td style="text-align:right; font-weight:bold">${montoStr}</td>
                </tr>`;
                total += item.monto;
            }
            
            if (modoTripleta && seleccionTripleta.length > 0) {
                let monto = parseFloat(document.getElementById('monto').value) || 5;
                let nums = seleccionTripleta.map(a => a.k).join(',');
                let nombres = seleccionTripleta.map(a => a.nombre).join('-');
                let montoStr = monto % 1 === 0 ? monto : monto.toFixed(1);
                html += `<tr style="opacity:0.8; background:rgba(255,165,0,0.2)">
                    <td style="color:#FFA500; font-size:0.75rem">Todo el dia</td>
                    <td style="color:#FFA500; font-size:0.8rem">🎯 ${nums} (${nombres})</td>
                    <td style="text-align:right; color:#FFA500; font-weight:bold">${montoStr}</td>
                </tr>`;
            } else if (!modoTripleta && horariosSel.length > 0 && (seleccionados.length > 0 || especiales.length > 0)) {
                let monto = parseFloat(document.getElementById('monto').value) || 5;
                let montoStr = monto % 1 === 0 ? monto : monto.toFixed(1);
                for (let h of horariosSel) {
                    for (let a of seleccionados) {
                        let indicador = a.k === "40" ? " 🦉x70" : "";
                        html += `<tr style="opacity:0.7; background:rgba(255,215,0,0.1)">
                            <td style="color:#ffd700; font-size:0.75rem">${h}</td>
                            <td style="color:#ffd700; font-size:0.8rem">${a.k} ${a.nombre}${indicador}</td>
                            <td style="text-align:right; color:#ffd700; font-weight:bold">${montoStr}</td>
                        </tr>`;
                    }
                    for (let e of especiales) {
                        html += `<tr style="opacity:0.7; background:rgba(52,152,219,0.1)">
                            <td style="color:#3498db; font-size:0.75rem">${h}</td>
                            <td style="color:#3498db; font-size:0.8rem">${e}</td>
                            <td style="text-align:right; color:#3498db; font-weight:bold">${montoStr}</td>
                        </tr>`;
                    }
                }
            }
            
            html += '</tbody></table>';
            
            if (carrito.length === 0 && 
                (seleccionados.length === 0 && especiales.length === 0 && seleccionTripleta.length === 0)) {
                html = '<div style="text-align:center; color:#666; padding:20px; font-style:italic;">Selecciona animales y horarios...</div>';
            } else if (carrito.length === 0) {
                html += '<div style="text-align:center; color:#888; padding:15px; font-size:0.85rem; background:rgba(255,215,0,0.05); border-radius:8px; margin-top:10px;">👆 Presiona AGREGAR para confirmar las selecciones</div>';
            }
            
            if (total > 0) {
                let totalStr = total % 1 === 0 ? total : total.toFixed(1);
                html += `<div class="ticket-total">TOTAL: S/${totalStr}</div>`;
            }
            
            display.innerHTML = html;
        }
        
        function agregar() {
            if (modoTripleta) {
                if (seleccionTripleta.length !== 3) {
                    showToast('Debes seleccionar exactamente 3 animalitos para la tripleta', 'error');
                    return;
                }
                let monto = parseFloat(document.getElementById('monto').value) || 5;
                let nums = seleccionTripleta.map(a => a.k).join(',');
                let nombres = seleccionTripleta.map(a => a.nombre).join('-');
                
                carrito.push({
                    hora: 'Todo el dia', 
                    seleccion: nums, 
                    nombre: nombres, 
                    monto: monto, 
                    tipo: 'tripleta'
                });
                
                seleccionTripleta = [];
                document.querySelectorAll('.animal-card.tripleta-seleccionado').forEach(el => {
                    el.classList.remove('tripleta-seleccionado');
                });
                
                showToast('Tripleta agregada al ticket (Paga x60)', 'success');
                updateTicket();
                return;
            }
            
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
                showToast('Carrito vacio', 'error'); 
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
                showToast('Error de conexion. Intenta de nuevo.', 'error');
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
                        
                        let horaVenIdx = horasPeru.indexOf(hora);
                        let horaVen = horaVenIdx >= 0 ? horasVen[horaVenIdx] : '';
                        
                        html += `
                            <div class="resultado-item ${clase}">
                                <div style="display: flex; flex-direction: column;">
                                    <strong style="color: #ffd700; font-size: 1rem;">${hora}</strong>
                                    <small style="color: #666; font-size: 0.75rem;">Venezuela: ${horaVen}</small>
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
                container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexion</p>';
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
            .catch(e => showToast('Error de conexion', 'error'));
            
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
        
        function abrirMisTickets() {
            document.getElementById('modal-mis-tickets').style.display = 'block';
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('mis-tickets-fecha-inicio').value = hoy;
            document.getElementById('mis-tickets-fecha-fin').value = hoy;
        }
        
        function abrirBuscarTicket() {
            document.getElementById('modal-buscar-ticket').style.display = 'block';
            document.getElementById('buscar-serial-input').value = '';
            document.getElementById('resultado-busqueda-ticket').innerHTML = '';
            document.getElementById('buscar-serial-input').focus();
        }
        
        function consultarMisTickets() {
            let inicio = document.getElementById('mis-tickets-fecha-inicio').value;
            let fin = document.getElementById('mis-tickets-fecha-fin').value;
            let estado = document.getElementById('mis-tickets-estado').value;
            
            if (!inicio || !fin) {
                showToast('Seleccione fechas', 'error');
                return;
            }
            
            let container = document.getElementById('lista-mis-tickets');
            container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Cargando...</p>';
            
            fetch('/api/mis-tickets', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    fecha_inicio: inicio,
                    fecha_fin: fin,
                    estado: estado
                })
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error: ' + d.error + '</p>';
                    return;
                }
                
                document.getElementById('mis-tickets-resumen').style.display = 'block';
                document.getElementById('mis-tickets-info').textContent = 
                    `${d.totales.cantidad} tickets - Total ventas: S/${d.totales.ventas.toFixed(2)}`;
                
                if (d.tickets.length === 0) {
                    container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">No se encontraron tickets con esos filtros</p>';
                    return;
                }
                
                let html = '';
                d.tickets.forEach(t => {
                    let estadoClass = t.pagado ? 'ganador' : (t.premio_calculado ? 'pendiente-pago' : (t.anulado ? 'anulado' : ''));
                    let estadoText = t.pagado ? 'PAGADO' : (t.anulado ? 'ANULADO' : (t.premio_calculado ? 'GANADOR (sin cobrar)' : 'PENDIENTE'));
                    let estadoBadgeClass = t.pagado ? 'estado-pagado' : (t.anulado ? 'estado-anulado' : 'estado-pendiente');
                    
                    html += `
                        <div class="ticket-item ${estadoClass}" onclick="verDetalleTicket('${t.serial}')">
                            <div class="ticket-serial">#${t.serial}</div>
                            <div class="ticket-info">${t.fecha} - Total: S/${t.total}</div>
                            ${t.premio_calculado ? `<div class="ticket-premio">Premio: S/${t.premio_calculado}</div>` : ''}
                            <span class="ticket-estado ${estadoBadgeClass}">${estadoText}</span>
                            ${!t.pagado && !t.anulado ? `<button class="btn-reimprimir" onclick="event.stopPropagation(); reimprimirTicket('${t.serial}')">🖨️ Reimprimir</button>` : ''}
                        </div>
                    `;
                });
                container.innerHTML = html;
            })
            .catch(e => {
                container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexion</p>';
            });
        }
        
        // NUEVA FUNCION: Reimprimir ticket
        function reimprimirTicket(serial) {
            fetch('/api/reimprimir-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    showToast(d.error, 'error');
                    return;
                }
                
                if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
                    window.location.href = d.url_whatsapp;
                } else {
                    window.open(d.url_whatsapp, '_blank');
                }
                showToast('Ticket listo para reimprimir', 'success');
            })
            .catch(e => showToast('Error de conexion', 'error'));
        }
        
        function buscarTicketEspecifico() {
            let serial = document.getElementById('buscar-serial-input').value.trim();
            if (!serial) {
                showToast('Ingrese un serial', 'error');
                return;
            }
            
            let container = document.getElementById('resultado-busqueda-ticket');
            container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Buscando...</p>';
            
            fetch('/api/consultar-ticket-detalle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">' + d.error + '</p>';
                    return;
                }
                
                let t = d.ticket;
                let estadoColor = t.pagado ? '#27ae60' : (t.anulado ? '#c0392b' : (t.premio_total > 0 ? '#f39c12' : '#888'));
                let estadoText = t.pagado ? 'PAGADO' : (t.anulado ? 'ANULADO' : (t.premio_total > 0 ? 'GANADOR - PENDIENTE DE COBRO' : 'NO GANADOR'));
                
                let html = `
                    <div style="background: #0a0a0a; padding: 20px; border-radius: 10px; border: 2px solid ${estadoColor};">
                        <h3 style="color: #ffd700; margin-bottom: 15px; text-align: center;">TICKET #${t.serial}</h3>
                        <div class="stats-box" style="margin-bottom: 15px;">
                            <div class="stat-row">
                                <span class="stat-label">Fecha:</span>
                                <span class="stat-value" style="font-size: 1rem;">${t.fecha}</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">Apostado:</span>
                                <span class="stat-value" style="font-size: 1rem;">S/${t.total_apostado}</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">Estado:</span>
                                <span class="stat-value" style="color: ${estadoColor}; font-size: 1rem;">${estadoText}</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">Premio Total:</span>
                                <span class="stat-value" style="color: ${t.premio_total > 0 ? '#27ae60' : '#888'}; font-size: 1.2rem;">
                                    S/${t.premio_total.toFixed(2)}
                                </span>
                            </div>
                        </div>
                        <h4 style="color: #ffd700; margin-bottom: 10px;">Detalle de Jugadas:</h4>
                `;
                
                d.jugadas.forEach(j => {
                    let ganoClass = j.gano ? 'jugada-ganadora' : '';
                    let resultadoText = j.resultado ? `${j.resultado}` : 'Pendiente';
                    
                    html += `
                        <div class="jugada-detail ${ganoClass}">
                            <div>
                                <strong>${j.hora}</strong> - ${j.seleccion} ${j.nombre_seleccion}<br>
                                <small style="color: #888;">Resultado: ${resultadoText}</small>
                            </div>
                            <div style="text-align: right;">
                                <div>S/${j.monto}</div>
                                ${j.gano ? '<div style="color: #27ae60; font-weight: bold;">S/' + j.premio + '</div>' : ''}
                            </div>
                        </div>
                    `;
                });
                
                // Botones de acción
                if (!t.pagado && !t.anulado) {
                    html += `
                        <div style="margin-top: 15px; text-align: center;">
                            <button class="btn-reimprimir" onclick="reimprimirTicket('${t.serial}')">🖨️ Reimprimir Ticket</button>
                        </div>
                    `;
                }
                
                html += '</div>';
                container.innerHTML = html;
            })
            .catch(e => {
                container.innerHTML = '<p style="color: #c0392b; text-align: center; padding: 20px;">Error de conexion</p>';
            });
        }
        
        function verDetalleTicket(serial) {
            document.getElementById('modal-mis-tickets').style.display = 'none';
            abrirBuscarTicket();
            document.getElementById('buscar-serial-input').value = serial;
            buscarTicketEspecifico();
        }
        
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
                document.getElementById('lista-pendientes').innerHTML = '<p style="color: #c0392b; text-align: center;">Error de conexion</p>';
            });
        }
        
        function mostrarReglas() {
            document.getElementById('modal-reglas').style.display = 'block';
        }
        
        function mostrarComoUsar() {
            document.getElementById('modal-como-usar').style.display = 'block';
        }
        
        function mostrarAcerca() {
            document.getElementById('modal-acerca').style.display = 'block';
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
            .catch(e => showToast('Error de conexion', 'error'));
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
                showToast('Error de conexion', 'error');
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
                showToast('Error de conexion', 'error');
            }
        }
        
        function borrarTodo() {
            if (carrito.length > 0 || seleccionados.length > 0 || especiales.length > 0 || horariosSel.length > 0 || seleccionTripleta.length > 0) {
                if (!confirm('¿Borrar todo?')) return;
            }
            seleccionados = []; especiales = []; horariosSel = []; carrito = []; seleccionTripleta = [];
            document.querySelectorAll('.active, .tripleta-seleccionado').forEach(el => {
                el.classList.remove('active');
                el.classList.remove('tripleta-seleccionado');
            });
            if (modoTripleta) toggleModoTripleta();
            updateTicket();
            showToast('Ticket limpiado', 'info');
        }
        
        function calcularPremio() {
            const monto = parseFloat(document.getElementById('calc-monto').value) || 0;
            const multiplicador = parseInt(document.getElementById('calc-tipo').value);
            const total = monto * multiplicador;
            
            document.getElementById('calc-total').textContent = 'S/' + total.toFixed(2);
            document.getElementById('calc-resultado').style.display = 'block';
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
            document.getElementById('mis-tickets-fecha-inicio').value = hoy;
            document.getElementById('mis-tickets-fecha-fin').value = hoy;
        });
    </script>
</body>
</html>
'''

ADMIN_HTML = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - Zoolo Casino</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #fff; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 15px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.3rem; }
        .nav { display: flex; gap: 10px; }
        .nav button { background: rgba(255,255,255,0.2); border: none; color: #fff; padding: 8px 15px; border-radius: 8px; cursor: pointer; font-size: 0.85rem; }
        .nav button:hover { background: rgba(255,255,255,0.3); }
        .container { padding: 20px; max-width: 1400px; margin: 0 auto; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .card { background: #252542; border-radius: 12px; padding: 20px; }
        .card h3 { color: #a0a0c0; font-size: 0.9rem; margin-bottom: 10px; text-transform: uppercase; }
        .card .valor { font-size: 2rem; font-weight: bold; color: #fff; }
        .card .valor.success { color: #2ecc71; }
        .card .valor.danger { color: #e74c3c; }
        .card .valor.warning { color: #f39c12; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #a0a0c0; font-size: 0.9rem; }
        .form-group input, .form-group select { width: 100%; padding: 12px; border: 1px solid #3a3a5c; border-radius: 8px; background: #1a1a2e; color: #fff; font-size: 1rem; }
        .btn { padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; transition: all 0.3s; }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; }
        .btn-success { background: #27ae60; color: #fff; }
        .btn-danger { background: #e74c3c; color: #fff; }
        .btn-warning { background: #f39c12; color: #fff; }
        .btn:hover { transform: translateY(-2px); opacity: 0.9; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.85rem; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #3a3a5c; }
        th { background: #1a1a2e; color: #a0a0c0; font-weight: 600; }
        tr:hover { background: rgba(102, 126, 234, 0.1); }
        .tabs { display: flex; gap: 5px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab { padding: 10px 20px; background: #252542; border: none; color: #a0a0c0; cursor: pointer; border-radius: 8px 8px 0 0; }
        .tab.active { background: #667eea; color: #fff; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .filtros { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        .filtros input, .filtros select { padding: 10px; border: 1px solid #3a3a5c; border-radius: 8px; background: #1a1a2e; color: #fff; }
        .estado-badge { padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
        .estado-activo { background: #27ae60; }
        .estado-pagado { background: #3498db; }
        .estado-pendiente { background: #f39c12; }
        .estado-anulado { background: #e74c3c; }
        .toast { position: fixed; bottom: 20px; right: 20px; padding: 15px 25px; border-radius: 8px; color: #fff; font-weight: 500; z-index: 10000; animation: slideIn 0.3s ease; }
        .toast.success { background: #27ae60; }
        .toast.error { background: #e74c3c; }
        @keyframes slideIn { from { transform: translateX(400px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 1000; justify-content: center; align-items: center; }
        .modal-content { background: #252542; padding: 30px; border-radius: 12px; max-width: 500px; width: 90%; }
        .detalle-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 15px 0; }
        .detalle-item { background: #1a1a2e; padding: 10px; border-radius: 8px; text-align: center; }
        .detalle-item .num { font-size: 1.2rem; font-weight: bold; color: #667eea; }
        .detalle-item .tipo { font-size: 0.75rem; color: #a0a0c0; }
        @media (max-width: 768px) {
            .header { flex-direction: column; gap: 10px; }
            .nav { flex-wrap: wrap; justify-content: center; }
            .grid { grid-template-columns: 1fr; }
            .filtros { flex-direction: column; }
            table { font-size: 0.75rem; }
            th, td { padding: 6px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Panel de Administracion</h1>
        <div class="nav">
            <button onclick="mostrarSeccion('dashboard')">Dashboard</button>
            <button onclick="mostrarSeccion('resultados')">Resultados</button>
            <button onclick="mostrarSeccion('tickets')">Tickets</button>
            <button onclick="mostrarSeccion('usuarios')">Usuarios</button>
            <button onclick="mostrarSeccion('reportes')">Reportes</button>
            <button onclick="window.location.href='/pos'">Ir a POS</button>
            <button onclick="cerrarSesion()">Cerrar Sesion</button>
        </div>
    </div>

    <div class="container">
        <!-- DASHBOARD -->
        <div id="dashboard" class="seccion">
            <div class="grid">
                <div class="card">
                    <h3>Ventas Hoy</h3>
                    <div class="valor" id="dash-ventas">S/ 0.00</div>
                </div>
                <div class="card">
                    <h3>Tickets Hoy</h3>
                    <div class="valor success" id="dash-tickets">0</div>
                </div>
                <div class="card">
                    <h3>Tickets Pendientes</h3>
                    <div class="valor warning" id="dash-pendientes">0</div>
                </div>
                <div class="card">
                    <h3>Comisiones</h3>
                    <div class="valor danger" id="dash-comisiones">S/ 0.00</div>
                </div>
            </div>
            <div class="card">
                <h3>Ultimos Tickets</h3>
                <div id="dash-ultimos"></div>
            </div>
        </div>

        <!-- RESULTADOS -->
        <div id="resultados" class="seccion" style="display:none;">
            <div class="card">
                <h3>Gestionar Resultados</h3>
                <div class="filtros">
                    <input type="date" id="resultados-fecha">
                    <select id="resultados-sorteo">
                        <option value="">Todos los sorteos</option>
                        <option value="peru">Peru</option>
                        <option value="venezuela">Venezuela</option>
                    </select>
                    <button class="btn btn-primary" onclick="cargarResultados()">Cargar</button>
                </div>
                <div id="tabla-resultados"></div>
            </div>
            <div class="card" style="margin-top: 20px;">
                <h3>Agregar/Editar Resultado</h3>
                <form id="form-resultado">
                    <input type="hidden" id="res-id">
                    <div class="form-group">
                        <label>Fecha</label>
                        <input type="date" id="res-fecha" required>
                    </div>
                    <div class="form-group">
                        <label>Sorteo</label>
                        <select id="res-sorteo" required>
                            <option value="peru">Peru</option>
                            <option value="venezuela">Venezuela</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Horario</label>
                        <select id="res-horario" required></select>
                    </div>
                    <div class="form-group">
                        <label>Animal Ganador (0-40)</label>
                        <input type="number" id="res-animal" min="0" max="40" required>
                    </div>
                    <button type="submit" class="btn btn-success">Guardar Resultado</button>
                </form>
            </div>
        </div>

        <!-- TICKETS -->
        <div id="tickets" class="seccion" style="display:none;">
            <div class="card">
                <h3>Todos los Tickets</h3>
                <div class="filtros">
                    <input type="date" id="tickets-fecha-inicio">
                    <input type="date" id="tickets-fecha-fin">
                    <select id="tickets-estado">
                        <option value="todos">Todos</option>
                        <option value="activos">Activos</option>
                        <option value="pagados">Pagados</option>
                        <option value="pendientes">Pendientes</option>
                        <option value="anulados">Anulados</option>
                        <option value="por_pagar">Por Pagar</option>
                    </select>
                    <input type="text" id="tickets-buscar" placeholder="Buscar ticket...">
                    <button class="btn btn-primary" onclick="cargarTicketsAdmin()">Buscar</button>
                </div>
                <div id="tabla-tickets-admin"></div>
            </div>
        </div>

        <!-- USUARIOS -->
        <div id="usuarios" class="seccion" style="display:none;">
            <div class="card">
                <h3>Crear Nuevo Usuario</h3>
                <form id="form-usuario">
                    <div class="form-group">
                        <label>Usuario</label>
                        <input type="text" id="user-usuario" required>
                    </div>
                    <div class="form-group">
                        <label>Contraseña</label>
                        <input type="password" id="user-password" required>
                    </div>
                    <div class="form-group">
                        <label>Rol</label>
                        <select id="user-rol" required>
                            <option value="vendedor">Vendedor</option>
                            <option value="admin">Administrador</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Comision % (0-100)</label>
                        <input type="number" id="user-comision" min="0" max="100" value="15">
                    </div>
                    <button type="submit" class="btn btn-success">Crear Usuario</button>
                </form>
            </div>
            <div class="card" style="margin-top: 20px;">
                <h3>Usuarios Existentes</h3>
                <div id="tabla-usuarios"></div>
            </div>
        </div>

        <!-- REPORTES -->
        <div id="reportes" class="seccion" style="display:none;">
            <div class="card">
                <h3>Reporte de Ventas</h3>
                <div class="filtros">
                    <input type="date" id="reporte-fecha-inicio">
                    <input type="date" id="reporte-fecha-fin">
                    <select id="reporte-vendedor">
                        <option value="">Todos los vendedores</option>
                    </select>
                    <button class="btn btn-primary" onclick="generarReporte()">Generar</button>
                    <button class="btn btn-success" onclick="exportarCSV()">Exportar CSV</button>
                </div>
                <div id="reporte-resultado"></div>
            </div>
        </div>
    </div>

    <!-- Modal Detalle Ticket -->
    <div id="modal-detalle" class="modal">
        <div class="modal-content">
            <h3>Detalle del Ticket</h3>
            <div id="detalle-contenido"></div>
            <button class="btn btn-primary" onclick="cerrarModal()" style="margin-top: 15px; width: 100%;">Cerrar</button>
        </div>
    </div>

    <script>
        let datosReporte = [];
        
        function mostrarSeccion(seccion) {
            document.querySelectorAll('.seccion').forEach(s => s.style.display = 'none');
            document.getElementById(seccion).style.display = 'block';
            if (seccion === 'dashboard') cargarDashboard();
            if (seccion === 'usuarios') cargarUsuarios();
        }
        
        function showToast(mensaje, tipo) {
            const t = document.createElement('div');
            t.className = 'toast ' + tipo;
            t.textContent = mensaje;
            document.body.appendChild(t);
            setTimeout(() => t.remove(), 3000);
        }
        
        function cerrarModal() {
            document.getElementById('modal-detalle').style.display = 'none';
        }
        
        function cerrarSesion() {
            fetch('/logout', {method: 'POST'}).then(() => window.location.href = '/');
        }
        
        // DASHBOARD
        async function cargarDashboard() {
            try {
                const r = await fetch('/admin/dashboard-data');
                const d = await r.json();
                document.getElementById('dash-ventas').textContent = 'S/ ' + parseFloat(d.ventas_hoy || 0).toFixed(2);
                document.getElementById('dash-tickets').textContent = d.total_tickets_hoy || 0;
                document.getElementById('dash-pendientes').textContent = d.pendientes_hoy || 0;
                document.getElementById('dash-comisiones').textContent = 'S/ ' + parseFloat(d.comisiones_hoy || 0).toFixed(2);
                
                let html = '<table><tr><th>Ticket</th><th>Vendedor</th><th>Monto</th><th>Estado</th></tr>';
                (d.ultimos_tickets || []).forEach(t => {
                    html += `<tr><td>${t.codigo}</td><td>${t.vendedor}</td><td>S/ ${parseFloat(t.total).toFixed(2)}</td><td><span class="estado-badge estado-${t.estado}">${t.estado}</span></td></tr>`;
                });
                html += '</table>';
                document.getElementById('dash-ultimos').innerHTML = html;
            } catch (e) {
                showToast('Error cargando dashboard', 'error');
            }
        }
        
        // RESULTADOS
        document.getElementById('res-sorteo').addEventListener('change', actualizarHorariosAdmin);
        
        function actualizarHorariosAdmin() {
            const sorteo = document.getElementById('res-sorteo').value;
            const horarios = sorteo === 'peru' ? 
                ["08:00 AM", "09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM"] :
                ["09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM"];
            const sel = document.getElementById('res-horario');
            sel.innerHTML = horarios.map(h => `<option value="${h}">${h}</option>`).join('');
        }
        
        async function cargarResultados() {
            const fecha = document.getElementById('resultados-fecha').value;
            const sorteo = document.getElementById('resultados-sorteo').value;
            if (!fecha) return showToast('Seleccione fecha', 'error');
            
            try {
                let url = '/admin/resultados?fecha=' + fecha;
                if (sorteo) url += '&sorteo=' + sorteo;
                const r = await fetch(url);
                const d = await r.json();
                
                let html = '<table><tr><th>Fecha</th><th>Sorteo</th><th>Horario</th><th>Animal</th><th>Acciones</th></tr>';
                d.forEach(res => {
                    html += `<tr>
                        <td>${res.fecha}</td>
                        <td>${res.sorteo}</td>
                        <td>${res.horario}</td>
                        <td><strong>${res.animal}</strong> - ${res.nombre_animal || ''}</td>
                        <td><button class="btn btn-primary" onclick="editarResultado('${res.id}', '${res.fecha}', '${res.sorteo}', '${res.horario}', '${res.animal}')">Editar</button></td>
                    </tr>`;
                });
                html += '</table>';
                document.getElementById('tabla-resultados').innerHTML = html;
            } catch (e) {
                showToast('Error cargando resultados', 'error');
            }
        }
        
        function editarResultado(id, fecha, sorteo, horario, animal) {
            document.getElementById('res-id').value = id;
            document.getElementById('res-fecha').value = fecha;
            document.getElementById('res-sorteo').value = sorteo;
            actualizarHorariosAdmin();
            document.getElementById('res-horario').value = horario;
            document.getElementById('res-animal').value = animal;
        }
        
        document.getElementById('form-resultado').addEventListener('submit', async function(e) {
            e.preventDefault();
            const datos = {
                id: document.getElementById('res-id').value,
                fecha: document.getElementById('res-fecha').value,
                sorteo: document.getElementById('res-sorteo').value,
                horario: document.getElementById('res-horario').value,
                animal: document.getElementById('res-animal').value
            };
            
            try {
                const r = await fetch('/admin/guardar-resultado', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(datos)
                });
                const d = await r.json();
                if (d.success) {
                    showToast('Resultado guardado correctamente', 'success');
                    document.getElementById('res-id').value = '';
                    document.getElementById('form-resultado').reset();
                    cargarResultados();
                } else {
                    showToast(d.error || 'Error al guardar', 'error');
                }
            } catch (e) {
                showToast('Error de conexion', 'error');
            }
        });
        
        // TICKETS ADMIN
        async function cargarTicketsAdmin() {
            const inicio = document.getElementById('tickets-fecha-inicio').value;
            const fin = document.getElementById('tickets-fecha-fin').value;
            const estado = document.getElementById('tickets-estado').value;
            const buscar = document.getElementById('tickets-buscar').value;
            
            try {
                let url = '/admin/tickets?estado=' + estado;
                if (inicio) url += '&fecha_inicio=' + inicio;
                if (fin) url += '&fecha_fin=' + fin;
                if (buscar) url += '&buscar=' + encodeURIComponent(buscar);
                
                const r = await fetch(url);
                const d = await r.json();
                
                let html = '<table><tr><th>Codigo</th><th>Fecha</th><th>Vendedor</th><th>Total</th><th>Estado</th><th>Acciones</th></tr>';
                (d.tickets || []).forEach(t => {
                    html += `<tr>
                        <td>${t.codigo}</td>
                        <td>${t.fecha_venta}</td>
                        <td>${t.vendedor}</td>
                        <td>S/ ${parseFloat(t.total).toFixed(2)}</td>
                        <td><span class="estado-badge estado-${t.estado}">${t.estado}</span></td>
                        <td>
                            <button class="btn btn-primary" onclick="verDetalle('${t.codigo}')">Ver</button>
                            ${t.estado === 'activo' ? `<button class="btn btn-danger" onclick="anularTicket('${t.codigo}')">Anular</button>` : ''}
                            ${t.estado === 'por_pagar' ? `<button class="btn btn-success" onclick="marcarPagado('${t.codigo}')">Pagar</button>` : ''}
                        </td>
                    </tr>`;
                });
                html += '</table>';
                document.getElementById('tabla-tickets-admin').innerHTML = html;
            } catch (e) {
                showToast('Error cargando tickets', 'error');
            }
        }
        
        async function verDetalle(codigo) {
            try {
                const r = await fetch('/admin/ticket-detalle?codigo=' + codigo);
                const t = await r.json();
                
                let detallesHtml = '<div class="detalle-grid">';
                (t.detalles || []).forEach(d => {
                    detallesHtml += `<div class="detalle-item">
                        <div class="num">${d.animal}</div>
                        <div class="tipo">${d.tipo} - S/ ${parseFloat(d.monto).toFixed(2)}</div>
                    </div>`;
                });
                detallesHtml += '</div>';
                
                document.getElementById('detalle-contenido').innerHTML = `
                    <p><strong>Codigo:</strong> ${t.codigo}</p>
                    <p><strong>Vendedor:</strong> ${t.vendedor}</p>
                    <p><strong>Fecha:</strong> ${t.fecha_venta}</p>
                    <p><strong>Total:</strong> S/ ${parseFloat(t.total).toFixed(2)}</p>
                    <p><strong>Estado:</strong> ${t.estado}</p>
                    <h4 style="margin: 15px 0 10px;">Detalles:</h4>
                    ${detallesHtml}
                `;
                document.getElementById('modal-detalle').style.display = 'flex';
            } catch (e) {
                showToast('Error cargando detalle', 'error');
            }
        }
        
        async function anularTicket(codigo) {
            if (!confirm('¿Anular ticket ' + codigo + '?')) return;
            try {
                const r = await fetch('/admin/anular-ticket', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({codigo: codigo})
                });
                const d = await r.json();
                if (d.success) {
                    showToast('Ticket anulado', 'success');
                    cargarTicketsAdmin();
                } else {
                    showToast(d.error || 'Error al anular', 'error');
                }
            } catch (e) {
                showToast('Error de conexion', 'error');
            }
        }
        
        async function marcarPagado(codigo) {
            try {
                const r = await fetch('/admin/marcar-pagado', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({codigo: codigo})
                });
                const d = await r.json();
                if (d.success) {
                    showToast('Ticket marcado como pagado', 'success');
                    cargarTicketsAdmin();
                } else {
                    showToast(d.error || 'Error', 'error');
                }
            } catch (e) {
                showToast('Error de conexion', 'error');
            }
        }
        
        // USUARIOS
        document.getElementById('form-usuario').addEventListener('submit', async function(e) {
            e.preventDefault();
            const datos = {
                usuario: document.getElementById('user-usuario').value,
                password: document.getElementById('user-password').value,
                rol: document.getElementById('user-rol').value,
                comision: parseInt(document.getElementById('user-comision').value)
            };
            
            try {
                const r = await fetch('/admin/crear-usuario', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(datos)
                });
                const d = await r.json();
                if (d.success) {
                    showToast('Usuario creado correctamente', 'success');
                    document.getElementById('form-usuario').reset();
                    cargarUsuarios();
                } else {
                    showToast(d.error || 'Error al crear usuario', 'error');
                }
            } catch (e) {
                showToast('Error de conexion', 'error');
            }
        });
        
        async function cargarUsuarios() {
            try {
                const r = await fetch('/admin/usuarios');
                const d = await r.json();
                
                let html = '<table><tr><th>Usuario</th><th>Rol</th><th>Comision</th><th>Acciones</th></tr>';
                (d.usuarios || []).forEach(u => {
                    html += `<tr>
                        <td>${u.usuario}</td>
                        <td>${u.rol}</td>
                        <td>${u.comision}%</td>
                        <td><button class="btn btn-danger" onclick="eliminarUsuario('${u.usuario}')">Eliminar</button></td>
                    </tr>`;
                });
                html += '</table>';
                document.getElementById('tabla-usuarios').innerHTML = html;
                
                // Actualizar select de reportes
                const select = document.getElementById('reporte-vendedor');
                select.innerHTML = '<option value="">Todos los vendedores</option>';
                (d.usuarios || []).forEach(u => {
                    select.innerHTML += `<option value="${u.usuario}">${u.usuario}</option>`;
                });
            } catch (e) {
                showToast('Error cargando usuarios', 'error');
            }
        }
        
        async function eliminarUsuario(usuario) {
            if (!confirm('¿Eliminar usuario ' + usuario + '?')) return;
            try {
                const r = await fetch('/admin/eliminar-usuario', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({usuario: usuario})
                });
                const d = await r.json();
                if (d.success) {
                    showToast('Usuario eliminado', 'success');
                    cargarUsuarios();
                } else {
                    showToast(d.error || 'Error al eliminar', 'error');
                }
            } catch (e) {
                showToast('Error de conexion', 'error');
            }
        }
        
        // REPORTES
        async function generarReporte() {
            const inicio = document.getElementById('reporte-fecha-inicio').value;
            const fin = document.getElementById('reporte-fecha-fin').value;
            const vendedor = document.getElementById('reporte-vendedor').value;
            
            if (!inicio || !fin) return showToast('Seleccione fechas', 'error');
            
            try {
                let url = '/admin/reporte?fecha_inicio=' + inicio + '&fecha_fin=' + fin;
                if (vendedor) url += '&vendedor=' + vendedor;
                
                const r = await fetch(url);
                const d = await r.json();
                datosReporte = d.tickets || [];
                
                let total = 0, comisiones = 0;
                datosReporte.forEach(t => {
                    total += parseFloat(t.total || 0);
                    comisiones += parseFloat(t.comision || 0);
                });
                
                let html = `<div class="grid">
                    <div class="card"><h3>Total Ventas</h3><div class="valor">S/ ${total.toFixed(2)}</div></div>
                    <div class="card"><h3>Total Tickets</h3><div class="valor success">${datosReporte.length}</div></div>
                    <div class="card"><h3>Comisiones</h3><div class="valor danger">S/ ${comisiones.toFixed(2)}</div></div>
                    <div class="card"><h3>Neto</h3><div class="valor warning">S/ ${(total - comisiones).toFixed(2)}</div></div>
                </div>`;
                
                html += '<table><tr><th>Fecha</th><th>Ticket</th><th>Vendedor</th><th>Total</th><th>Comision</th><th>Estado</th></tr>';
                datosReporte.forEach(t => {
                    html += `<tr>
                        <td>${t.fecha_venta}</td>
                        <td>${t.codigo}</td>
                        <td>${t.vendedor}</td>
                        <td>S/ ${parseFloat(t.total).toFixed(2)}</td>
                        <td>S/ ${parseFloat(t.comision).toFixed(2)}</td>
                        <td><span class="estado-badge estado-${t.estado}">${t.estado}</span></td>
                    </tr>`;
                });
                html += '</table>';
                
                document.getElementById('reporte-resultado').innerHTML = html;
            } catch (e) {
                showToast('Error generando reporte', 'error');
            }
        }
        
        function exportarCSV() {
            if (datosReporte.length === 0) return showToast('Genere un reporte primero', 'error');
            
            let csv = 'Fecha,Ticket,Vendedor,Total,Comision,Estado\\n';
            datosReporte.forEach(t => {
                csv += `${t.fecha_venta},${t.codigo},${t.vendedor},${t.total},${t.comision},${t.estado}\\n`;
            });
            
            const blob = new Blob([csv], {type: 'text/csv'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'reporte_' + new Date().toISOString().split('T')[0] + '.csv';
            a.click();
            URL.revokeObjectURL(url);
            showToast('CSV descargado', 'success');
        }
        
        // Inicializar
        document.addEventListener('DOMContentLoaded', function() {
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('resultados-fecha').value = hoy;
            document.getElementById('tickets-fecha-inicio').value = hoy;
            document.getElementById('tickets-fecha-fin').value = hoy;
            document.getElementById('reporte-fecha-inicio').value = hoy;
            document.getElementById('reporte-fecha-fin').value = hoy;
            actualizarHorariosAdmin();
            cargarDashboard();
        });
    </script>
</body>
</html>
'''

# ==================== MAIN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
