#!/usr/bin/env python3
"""
ZOOLO CASINO CLOUD v6.0 - COMPLETO REFACTORIZADO
Todo en un solo archivo listo para copiar y pegar.
Requisitos: pip install flask flask-bcrypt python-dotenv
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
import bcrypt

# ==================== CONFIGURACIÓN OBLIGATORIA ====================
# Validar que existan variables de entorno (sin defaults peligrosos)
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
SECRET_KEY = os.environ.get('SECRET_KEY')

if not all([SUPABASE_URL, SUPABASE_KEY, SECRET_KEY]):
    print("ERROR: Debes configurar las variables de entorno:")
    print("export SUPABASE_URL='https://tu-proyecto.supabase.co'")
    print("export SUPABASE_KEY='tu-api-key'")
    print("export SECRET_KEY='clave-secreta-larga-y-aleatoria'")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Configuración de negocio
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

# ==================== FUNCIONES AUXILIARES CENTRALIZADAS ====================
def ahora_peru():
    return datetime.utcnow() - timedelta(hours=5)

def hash_password(password):
    """Hash seguro con bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """Verificación segura"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def get_color(num):
    if num in ["0", "00"]: 
        return "#27ae60"
    if num in ROJOS: 
        return "#c0392b"
    return "#2c3e50"

def generar_serial():
    return str(int(ahora_peru().timestamp() * 1000))

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

def obtener_sorteo_en_curso():
    ahora = ahora_peru()
    actual_minutos = ahora.hour * 60 + ahora.minute
    
    for hora_str in HORARIOS_PERU:
        minutos_sorteo = hora_a_minutos(hora_str)
        if actual_minutos >= minutos_sorteo and actual_minutos < (minutos_sorteo + 60):
            return hora_str
    return None

def obtener_proximo_sorteo():
    ahora = ahora_peru()
    actual_minutos = ahora.hour * 60 + ahora.minute
    
    for hora_str in HORARIOS_PERU:
        minutos_sorteo = hora_a_minutos(hora_str)
        if (minutos_sorteo - actual_minutos) > MINUTOS_BLOQUEO:
            return hora_str
    return None

def puede_editar_resultado(hora_sorteo, fecha_str=None):
    """Verifica si aún está dentro de la ventana de 2 horas"""
    ahora = ahora_peru()
    hoy = ahora.strftime("%d/%m/%Y")
    
    # Solo permite edición el mismo día (o fechas pasadas con override)
    if fecha_str and fecha_str != hoy:
        return False  # No editar días pasados sin permiso especial
    
    minutos_sorteo = hora_a_minutos(hora_sorteo)
    minutos_actual = ahora.hour * 60 + ahora.minute
    minutos_limite = minutos_sorteo + (HORAS_EDICION_RESULTADO * 60)
    
    return minutos_actual <= minutos_limite

# ==================== CÁLCULO DE PREMIOS CENTRALIZADO ====================
def calcular_premio(jugada, numero_ganador):
    """
    Calcula el premio de una jugada individual.
    Retorna el monto del premio o 0 si no ganó.
    """
    if not numero_ganador:
        return 0
    
    tipo = jugada.get('tipo')
    seleccion = str(jugada.get('seleccion'))
    monto = float(jugada.get('monto', 0))
    
    if tipo == 'animal':
        if str(numero_ganador) == str(seleccion):
            if str(numero_ganador) == "40":
                return monto * PAGO_LECHUZA
            else:
                return monto * PAGO_ANIMAL_NORMAL
    elif tipo == 'especial':
        if str(numero_ganador) in ["0", "00"]:
            return 0  # Los especiales pierden con 0 o 00
        
        num = int(numero_ganador)
        if seleccion == 'ROJO' and str(numero_ganador) in ROJOS:
            return monto * PAGO_ESPECIAL
        elif seleccion == 'NEGRO' and str(numero_ganador) not in ROJOS:
            return monto * PAGO_ESPECIAL
        elif seleccion == 'PAR' and num % 2 == 0:
            return monto * PAGO_ESPECIAL
        elif seleccion == 'IMPAR' and num % 2 != 0:
            return monto * PAGO_ESPECIAL
    
    return 0

def verificar_ganador(jugada, numero_ganador):
    """Retorna True/False si la jugada ganó"""
    return calcular_premio(jugada, numero_ganador) > 0

# ==================== CLIENTE SUPABASE ====================
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
                    return True
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return False
                raise e
                
        elif method == "DELETE":
            req = urllib.request.Request(url, headers=headers, method="DELETE")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return True
                
    except Exception as e:
        print(f"[ERROR Supabase {method} {table}]: {e}")
        return None

def registrar_auditoria(accion, tabla, registro_id, valor_anterior, valor_nuevo):
    """Registra cambios importantes en auditoría"""
    try:
        data = {
            "fecha": ahora_peru().strftime("%d/%m/%Y %H:%M:%S"),
            "admin_id": session.get('user_id'),
            "admin_nombre": session.get('nombre_agencia', 'Unknown'),
            "accion": accion,
            "tabla": tabla,
            "registro_id": str(registro_id),
            "valor_anterior": json.dumps(valor_anterior) if valor_anterior else None,
            "valor_nuevo": json.dumps(valor_nuevo) if valor_nuevo else None
        }
        supabase_request("auditoria", method="POST", data=data)
    except Exception as e:
        print(f"[ERROR Auditoría]: {e}")

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
            users = supabase_request("agencias", filters={"usuario": u, "activa": "true"})
            
            if users and len(users) > 0:
                user = users[0]
                # Verificar con bcrypt (soporta legacy sin hash para migración)
                stored_pass = user['password']
                if stored_pass.startswith('$2b$') or stored_pass.startswith('$2a$'):
                    valid = check_password(p, stored_pass)
                else:
                    # Legacy: comparación directa (actualizar en primera ejecución)
                    valid = (p == stored_pass)
                
                if valid:
                    session['user_id'] = user['id']
                    session['nombre_agencia'] = user['nombre_agencia']
                    session['es_admin'] = user['es_admin']
                    
                    # Actualizar a bcrypt si era legacy
                    if not stored_pass.startswith('$2b$') and not stored_pass.startswith('$2a$'):
                        new_hash = hash_password(p)
                        supabase_request("agencias", method="PATCH", 
                                       filters={"id": user['id']}, 
                                       data={"password": new_hash})
                    
                    return redirect('/')
                else:
                    error = "Usuario o clave incorrecta"
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

# ==================== API AGENCIA - NUEVA: MIS TICKETS ====================
@app.route('/api/mis-tickets')
@agencia_required
def mis_tickets():
    """Obtiene tickets de la agencia con filtros de fecha"""
    try:
        fecha_desde = request.args.get('desde')
        fecha_hasta = request.args.get('hasta')
        estado = request.args.get('estado', 'todos')  # todos, pagados, pendientes, anulados
        
        # Construir filtros base
        filters = {"agencia_id": session['user_id']}
        
        # Consulta base
        url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{session['user_id']}&order=fecha.desc"
        
        if estado == 'pagados':
            url += "&pagado=eq.true&anulado=eq.false"
        elif estado == 'pendientes':
            url += "&pagado=eq.false&anulado=eq.false"
        elif estado == 'anulados':
            url += "&anulado=eq.true"
        else:
            url += "&anulado=eq.false"  # Por defecto no mostrar anulados
            
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            tickets = json.loads(response.read().decode())
        
        # Filtrar por fechas en Python (ya que Supabase no maneja bien el formato DD/MM/YYYY)
        resultado = []
        hoy = ahora_peru().strftime("%d/%m/%Y")
        
        for t in tickets:
            fecha_ticket = t['fecha'].split(' ')[0] if ' ' in t['fecha'] else t['fecha']
            
            # Parsear fecha del ticket
            try:
                dt_ticket = datetime.strptime(fecha_ticket, "%d/%m/%Y")
            except:
                continue
            
            # Filtros de fecha
            if fecha_desde:
                dt_desde = datetime.strptime(fecha_desde, "%Y-%m-%d")
                if dt_ticket < dt_desde:
                    continue
            
            if fecha_hasta:
                dt_hasta = datetime.strptime(fecha_hasta, "%Y-%m-%d")
                if dt_ticket > dt_hasta:
                    continue
            
            # Obtener jugadas para este ticket
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
            
            # Calcular si tiene premio pendiente
            premio_pendiente = 0
            if not t['pagado'] and not t['anulado']:
                resultados_list = supabase_request("resultados", filters={"fecha": fecha_ticket})
                resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
                
                for j in jugadas:
                    premio = calcular_premio(j, resultados.get(j['hora']))
                    premio_pendiente += premio
            
            ticket_data = {
                'id': t['id'],
                'serial': t['serial'],
                'fecha': t['fecha'],
                'total': t['total'],
                'pagado': t['pagado'],
                'anulado': t['anulado'],
                'cantidad_jugadas': len(jugadas) if jugadas else 0,
                'premio_pendiente': round(premio_pendiente, 2) if premio_pendiente > 0 else 0,
                'tiene_premio': premio_pendiente > 0
            }
            resultado.append(ticket_data)
        
        return jsonify({
            'status': 'ok',
            'tickets': resultado,
            'total_registros': len(resultado)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/ticket-detalle/<int:ticket_id>')
@agencia_required
def ticket_detalle(ticket_id):
    """Obtiene detalle completo de un ticket"""
    try:
        # Verificar que el ticket pertenezca a la agencia
        tickets = supabase_request("tickets", filters={"id": ticket_id, "agencia_id": session['user_id']})
        if not tickets:
            return jsonify({'error': 'Ticket no encontrado'}), 404
        
        ticket = tickets[0]
        jugadas = supabase_request("jugadas", filters={"ticket_id": ticket_id})
        
        fecha_ticket = ticket['fecha'].split(' ')[0]
        resultados_list = supabase_request("resultados", filters={"fecha": fecha_ticket})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        detalle_jugadas = []
        total_premio = 0
        
        for j in jugadas:
            num_ganador = resultados.get(j['hora'])
            premio = calcular_premio(j, num_ganador)
            total_premio += premio
            
            detalle_jugadas.append({
                'hora': j['hora'],
                'tipo': j['tipo'],
                'seleccion': j['seleccion'],
                'monto': j['monto'],
                'resultado': num_ganador,
                'premio': premio if premio > 0 else 0,
                'gano': premio > 0
            })
        
        return jsonify({
            'status': 'ok',
            'ticket': {
                'id': ticket['id'],
                'serial': ticket['serial'],
                'fecha': ticket['fecha'],
                'total': ticket['total'],
                'pagado': ticket['pagado'],
                'anulado': ticket['anulado']
            },
            'jugadas': detalle_jugadas,
            'total_premio': total_premio,
            'ganancia_neta': total_premio - ticket['total'] if total_premio > 0 else 0
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== API EXISTENTES ====================
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
        
        # Generar mensaje WhatsApp
        jugadas_por_hora = defaultdict(list)
        for j in jugadas:
            jugadas_por_hora[j['hora']].append(j)
        
        lineas = [f"*{session['nombre_agencia']}*", f"*TICKET:* #{ticket_id}", f"*SERIAL:* {serial}", fecha, "------------------------", ""]
        
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
        
        lineas.extend(["------------------------", f"*TOTAL: S/{int(total)}*", "", "Buena Suerte! 🍀", "El ticket vence a los 3 dias"])
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
        
        if not tickets:
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
            premio = calcular_premio(j, resultados.get(j['hora']))
            total_ganado += premio
            
            detalles.append({
                'hora': j['hora'],
                'sel': j['seleccion'],
                'gano': premio > 0,
                'premio': premio,
                'es_lechuza': str(resultados.get(j['hora'])) == "40" and j['tipo'] == 'animal'
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
        if not tickets:
            return jsonify({'error': 'Ticket no existe'})
        
        ticket = tickets[0]
        
        if ticket['pagado']:
            return jsonify({'error': 'Ya esta pagado, no se puede anular'})
        
        # Si no es admin, validar tiempo y sorteos cerrados
        if not session.get('es_admin'):
            fecha_ticket = datetime.strptime(ticket['fecha'], "%d/%m/%Y %I:%M %p")
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
        
        # Obtener tickets de hoy
        url = f"{SUPABASE_URL}/rest/v1/tickets?fecha=like.{urllib.parse.quote(hoy)}%25"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            tickets = json.loads(response.read().decode())
        
        mis_tickets = [t for t in tickets if t['agencia_id'] == session['user_id'] and not t['anulado']]
        ventas = sum(t['total'] for t in mis_tickets)
        
        # Obtener comisión
        agencias = supabase_request("agencias", filters={"id": session['user_id']})
        comision_pct = agencias[0]['comision'] if agencias else COMISION_AGENCIA
        comision = ventas * comision_pct
        
        # Calcular premios (pagados + pendientes)
        resultados_list = supabase_request("resultados", filters={"fecha": hoy})
        resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        premios_pagados = 0
        premios_pendientes = 0
        tickets_con_premio = 0
        
        for t in mis_tickets:
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
            premio_ticket = 0
            
            for j in jugadas:
                premio = calcular_premio(j, resultados.get(j['hora']))
                premio_ticket += premio
            
            if premio_ticket > 0:
                if t['pagado']:
                    premios_pagados += premio_ticket
                else:
                    premios_pendientes += premio_ticket
                    tickets_con_premio += 1
        
        total_premios = premios_pagados + premios_pendientes
        balance = ventas - total_premios - comision
        
        return jsonify({
            'ventas': round(ventas, 2),
            'premios_pagados': round(premios_pagados, 2),
            'premios_pendientes': round(premios_pendientes, 2),
            'total_premios': round(total_premios, 2),
            'comision': round(comision, 2),
            'balance': round(balance, 2),
            'tickets_pendientes': tickets_con_premio
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
        
        # Obtener todos los tickets de la agencia
        url = f"{SUPABASE_URL}/rest/v1/tickets?agencia_id=eq.{session['user_id']}&order=fecha.desc&limit=1000"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            all_tickets = json.loads(response.read().decode())
        
        dias_data = {}
        
        for t in all_tickets:
            if t.get('anulado'):
                continue
                
            dt_ticket = datetime.strptime(t['fecha'], "%d/%m/%Y %I:%M %p")
            if dt_ticket < dt_inicio or dt_ticket > dt_fin:
                continue
            
            dia_key = dt_ticket.strftime("%d/%m/%Y")
            
            if dia_key not in dias_data:
                dias_data[dia_key] = {'ventas': 0, 'tickets': 0, 'premios': 0}
            
            dias_data[dia_key]['ventas'] += t['total']
            dias_data[dia_key]['tickets'] += 1
            
            # Calcular premios para este día
            if t['pagado']:
                resultados_list = supabase_request("resultados", filters={"fecha": dia_key})
                resultados = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
                
                jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
                for j in jugadas:
                    premio = calcular_premio(j, resultados.get(j['hora']))
                    dias_data[dia_key]['premios'] += premio
        
        resumen_dias = []
        total_ventas = total_premios = 0
        
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
                'balance': round(balance_dia, 2)
            })
            
            total_ventas += datos['ventas']
            total_premios += datos['premios']
        
        total_comision = total_ventas * comision_pct
        balance_total = total_ventas - total_premios - total_comision
        
        return jsonify({
            'resumen_por_dia': resumen_dias,
            'totales': {
                'ventas': round(total_ventas, 2),
                'premios': round(total_premios, 2),
                'comision': round(total_comision, 2),
                'balance': round(balance_total, 2)
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== API ADMIN MEJORADAS ====================
@app.route('/admin/reporte-completo', methods=['POST'])
@admin_required
def reporte_completo():
    """
    Reporte completo con:
    - Ventas por agencia
    - Premios PAGADOS
    - Premios PENDIENTES (sin cobrar)
    - Balance real considerando ambos
    """
    try:
        data = request.get_json()
        fecha_inicio = data.get('fecha_inicio')
        fecha_fin = data.get('fecha_fin')
        
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fechas requeridas'}), 400
        
        dt_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(hour=23, minute=59)
        
        # Obtener todas las agencias
        agencias = supabase_request("agencias", filters={"es_admin": "false"})
        dict_agencias = {a['id']: a for a in agencias}
        
        # Obtener tickets del rango
        url = f"{SUPABASE_URL}/rest/v1/tickets?order=fecha.desc&limit=2000"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            all_tickets = json.loads(response.read().decode())
        
        # Pre-cargar resultados por día para eficiencia
        delta = dt_fin - dt_inicio
        resultados_cache = {}
        for i in range(delta.days + 1):
            dia_str = (dt_inicio + timedelta(days=i)).strftime("%d/%m/%Y")
            resultados_list = supabase_request("resultados", filters={"fecha": dia_str})
            resultados_cache[dia_str] = {r['hora']: r['animal'] for r in resultados_list} if resultados_list else {}
        
        stats_por_agencia = {}
        
        # Inicializar stats
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
                'tickets_pendientes': 0
            }
        
        for t in all_tickets:
            if t.get('anulado'):
                continue
                
            dt_ticket = datetime.strptime(t['fecha'], "%d/%m/%Y %I:%M %p")
            if dt_ticket < dt_inicio or dt_ticket > dt_fin:
                continue
            
            ag_id = t['agencia_id']
            if ag_id not in stats_por_agencia:
                continue
            
            stats = stats_por_agencia[ag_id]
            stats['tickets'] += 1
            stats['ventas'] += t['total']
            
            fecha_ticket = dt_ticket.strftime("%d/%m/%Y")
            resultados_dia = resultados_cache.get(fecha_ticket, {})
            
            # Obtener jugadas y calcular premios
            jugadas = supabase_request("jugadas", filters={"ticket_id": t['id']})
            premio_ticket = 0
            
            for j in jugadas:
                premio = calcular_premio(j, resultados_dia.get(j['hora']))
                premio_ticket += premio
            
            if premio_ticket > 0:
                if t['pagado']:
                    stats['premios_pagados'] += premio_ticket
                else:
                    stats['premios_pendientes'] += premio_ticket
                    stats['tickets_pendientes'] += 1
        
        # Calcular totales y formatear
        reporte_agencias = []
        total_ventas = total_pagados = total_pendientes = 0
        
        for ag_id, stats in stats_por_agencia.items():
            if stats['tickets'] > 0:
                comision = stats['ventas'] * stats['comision_pct']
                premios_totales = stats['premios_pagados'] + stats['premios_pendientes']
                balance = stats['ventas'] - premios_totales - comision
                
                reporte_agencias.append({
                    'nombre': stats['nombre'],
                    'usuario': stats['usuario'],
                    'tickets': stats['tickets'],
                    'ventas': round(stats['ventas'], 2),
                    'premios_pagados': round(stats['premios_pagados'], 2),
                    'premios_pendientes': round(stats['premios_pendientes'], 2),
                    'premios_totales': round(premios_totales, 2),
                    'comision': round(comision, 2),
                    'balance': round(balance, 2),
                    'tickets_pendientes': stats['tickets_pendientes']
                })
                
                total_ventas += stats['ventas']
                total_pagados += stats['premios_pagados']
                total_pendientes += stats['premios_pendientes']
        
        # Ordenar por ventas
        reporte_agencias.sort(key=lambda x: x['ventas'], reverse=True)
        
        total_premios = total_pagados + total_pendientes
        total_comision = total_ventas * COMISION_AGENCIA
        balance_global = total_ventas - total_premios - total_comision
        
        return jsonify({
            'status': 'ok',
            'agencias': reporte_agencias,
            'totales': {
                'ventas': round(total_ventas, 2),
                'premios_pagados': round(total_pagados, 2),
                'premios_pendientes': round(total_pendientes, 2),
                'premios_totales': round(total_premios, 2),
                'comision': round(total_comision, 2),
                'balance': round(balance_global, 2)
            },
            'rango': {'inicio': fecha_inicio, 'fin': fecha_fin}
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/guardar-resultado', methods=['POST'])
@admin_required
def guardar_resultado():
    """Guardar/Editar resultado con auditoría completa"""
    try:
        hora = request.form.get('hora')
        animal = request.form.get('animal')
        fecha_input = request.form.get('fecha')
        
        if animal not in ANIMALES:
            return jsonify({'error': f'Animal inválido: {animal}'}), 400
        
        # Parsear fecha
        if fecha_input:
            try:
                fecha_obj = datetime.strptime(fecha_input, "%Y-%m-%d")
                fecha = fecha_obj.strftime("%d/%m/%Y")
            except:
                fecha = ahora_peru().strftime("%d/%m/%Y")
        else:
            fecha = ahora_peru().strftime("%d/%m/%Y")
        
        # Verificar si ya existe (para auditoría)
        existentes = supabase_request("resultados", filters={"fecha": fecha, "hora": hora})
        
        if existentes and len(existentes) > 0:
            # Es edición
            resultado_anterior = existentes[0]
            
            # Validar ventana de edición (solo para hoy)
            hoy = ahora_peru().strftime("%d/%m/%Y")
            if fecha == hoy and not puede_editar_resultado(hora, fecha):
                return jsonify({
                    'error': f'No se puede editar. Solo disponible hasta 2 horas después del sorteo.'
                }), 403
            
            # Actualizar
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
                        # Registrar auditoría
                        registrar_auditoria(
                            "EDITAR_RESULTADO",
                            "resultados",
                            f"{fecha}_{hora}",
                            {"animal": resultado_anterior['animal']},
                            {"animal": animal}
                        )
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
            # Es creación nueva
            data = {"fecha": fecha, "hora": hora, "animal": animal}
            result = supabase_request("resultados", method="POST", data=data)
            
            if result:
                registrar_auditoria(
                    "CREAR_RESULTADO",
                    "resultados",
                    f"{fecha}_{hora}",
                    None,
                    {"animal": animal}
                )
                return jsonify({
                    'status': 'ok', 
                    'mensaje': f'RESULTADO GUARDADO: {hora} = {animal} ({ANIMALES[animal]})',
                    'accion': 'creado'
                })
            else:
                return jsonify({'error': 'Error al crear resultado'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/lista-agencias')
@admin_required
def lista_agencias():
    try:
        agencias = supabase_request("agencias", filters={"es_admin": "false"})
        return jsonify([{
            "id": a['id'], 
            "usuario": a['usuario'], 
            "nombre_agencia": a['nombre_agencia'], 
            "comision": a['comision']
        } for a in agencias])
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
        
        # Hash seguro del password
        hashed_pw = hash_password(password)
        
        data = {
            "usuario": usuario,
            "password": hashed_pw,
            "nombre_agencia": nombre,
            "es_admin": False,
            "comision": COMISION_AGENCIA,
            "activa": True
        }
        
        supabase_request("agencias", method="POST", data=data)
        
        # Registrar auditoría
        registrar_auditoria(
            "CREAR_AGENCIA",
            "agencias",
            usuario,
            None,
            {"nombre": nombre}
        )
        
        return jsonify({'status': 'ok', 'mensaje': f'Agencia {nombre} creada'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/auditoria')
@admin_required
def obtener_auditoria():
    """Obtiene logs de auditoría (últimos 100)"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/auditoria?order=fecha.desc&limit=100"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            logs = json.loads(response.read().decode())
        
        return jsonify({'status': 'ok', 'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== TEMPLATES HTML ====================
LOGIN_HTML = '''<!DOCTYPE html>
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
        }
        .login-box h2 { color: #ffd700; margin-bottom: 10px; font-size: 1.8rem; }
        .version { color: #666; font-size: 0.8rem; margin-bottom: 30px; }
        .form-group { margin-bottom: 20px; text-align: left; }
        .form-group label { display: block; margin-bottom: 8px; color: #aaa; font-size: 0.9rem; }
        .form-group input {
            width: 100%; padding: 15px;
            border: 1px solid #444; border-radius: 10px;
            background: rgba(0,0,0,0.5); color: white; font-size: 1rem;
        }
        .btn-login {
            width: 100%; padding: 16px;
            background: linear-gradient(45deg, #ffd700, #ffed4e);
            color: black; border: none; border-radius: 10px;
            font-size: 1.1rem; font-weight: bold; cursor: pointer;
            margin-top: 10px;
        }
        .error {
            background: rgba(255,0,0,0.2); color: #ff6b6b;
            padding: 12px; border-radius: 8px; margin-bottom: 20px;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🦁 ZOOLO CASINO</h2>
        <div class="version">v6.0 - Sistema Seguro</div>
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
    </div>
</body>
</html>'''

POS_HTML = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
    <title>POS - {{agencia}}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body { background: #0a0a0a; color: white; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-height: 100vh; display: flex; flex-direction: column; }
        
        /* Menu Windows */
        .win-menu-bar { background: linear-gradient(180deg, #2d2d2d 0%, #1a1a1a 100%); border-bottom: 2px solid #000; position: sticky; top: 0; z-index: 1000; }
        .win-menu-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 15px; background: linear-gradient(90deg, #1a1a2e, #16213e); border-bottom: 1px solid #000; }
        .win-title { color: #ffd700; font-size: 1rem; font-weight: bold; }
        .win-menu-items { display: flex; list-style: none; background: #2d2d2d; overflow-x: auto; }
        .win-menu-item { position: relative; }
        .win-menu-item > a { display: block; padding: 10px 15px; color: #fff; text-decoration: none; font-size: 0.8rem; border-right: 1px solid #444; cursor: pointer; white-space: nowrap; }
        .win-menu-item:hover > a { background: #404040; color: #ffd700; }
        .win-submenu { display: none; position: absolute; top: 100%; left: 0; background: #2d2d2d; border: 1px solid #555; min-width: 200px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); z-index: 1001; }
        .win-menu-item:hover .win-submenu { display: block; }
        .win-submenu-item a { display: block; padding: 12px 20px; color: #ddd; text-decoration: none; font-size: 0.85rem; cursor: pointer; }
        .win-submenu-item a:hover { background: #ffd700; color: #000; }
        
        /* Mobile Header */
        .mobile-header { display: none; background: linear-gradient(90deg, #1a1a2e, #16213e); padding: 12px 15px; justify-content: space-between; align-items: center; border-bottom: 2px solid #ffd700; position: sticky; top: 0; z-index: 1000; }
        .hamburger-btn { background: transparent; border: none; color: #ffd700; font-size: 1.5rem; cursor: pointer; }
        .mobile-menu { display: none; position: fixed; top: 0; right: -300px; width: 280px; height: 100vh; background: #1a1a2e; border-left: 2px solid #ffd700; z-index: 2000; transition: right 0.3s; overflow-y: auto; }
        .mobile-menu.active { right: 0; }
        .mobile-menu-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1999; }
        .mobile-menu-overlay.active { display: block; }
        
        @media (max-width: 768px) {
            .win-menu-bar { display: none; }
            .mobile-header { display: flex; }
            .mobile-menu { display: block; }
        }
        
        /* Layout */
        .header { background: linear-gradient(90deg, #1a1a2e, #16213e); padding: 10px 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #ffd700; }
        .header-info h3 { color: #ffd700; font-size: 1rem; margin: 0; }
        .header-info p { color: #888; font-size: 0.75rem; }
        .monto-box { display: flex; align-items: center; gap: 8px; background: rgba(0,0,0,0.3); padding: 6px 12px; border-radius: 20px; }
        .monto-box input { width: 60px; padding: 6px; border: 2px solid #ffd700; border-radius: 6px; background: #000; color: #ffd700; text-align: center; font-weight: bold; }
        
        .main-container { display: flex; flex-direction: column; flex: 1; height: calc(100vh - 110px); overflow: hidden; }
        @media (min-width: 1024px) { .main-container { flex-direction: row; } }
        
        .left-panel { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
        .special-btns { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; padding: 10px; background: #111; flex-shrink: 0; }
        .btn-esp { padding: 12px 4px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; color: white; font-size: 0.8rem; min-height: 44px; }
        .btn-esp:active { transform: scale(0.95); }
        .btn-rojo { background: linear-gradient(135deg, #c0392b, #e74c3c); }
        .btn-negro { background: linear-gradient(135deg, #2c3e50, #34495e); }
        .btn-par { background: linear-gradient(135deg, #2980b9, #3498db); }
        .btn-impar { background: linear-gradient(135deg, #8e44ad, #9b59b6); }
        .btn-esp.active { box-shadow: 0 0 15px rgba(255,255,255,0.5); border: 2px solid white; }
        
        .animals-grid { flex: 1; display: grid; grid-template-columns: repeat(auto-fill, minmax(60px, 1fr)); gap: 5px; padding: 10px; overflow-y: auto; }
        @media (min-width: 768px) { .animals-grid { grid-template-columns: repeat(7, 1fr); } }
        
        .animal-card { background: linear-gradient(135deg, #1a1a2e, #16213e); border: 2px solid; border-radius: 10px; padding: 8px 2px; text-align: center; cursor: pointer; min-height: 65px; display: flex; flex-direction: column; justify-content: center; user-select: none; position: relative; }
        .animal-card:active { transform: scale(0.92); }
        .animal-card.active { box-shadow: 0 0 15px rgba(255,215,0,0.6); border-color: #ffd700 !important; background: linear-gradient(135deg, #2a2a4e, #1a1a3e); transform: scale(1.05); z-index: 10; }
        .animal-card .num { font-size: 1.2rem; font-weight: bold; }
        .animal-card .name { font-size: 0.7rem; color: #aaa; margin-top: 4px; }
        .animal-card.lechuza::after { content: "x70"; position: absolute; top: 3px; right: 3px; background: #ffd700; color: black; font-size: 0.6rem; padding: 2px 4px; border-radius: 4px; font-weight: bold; }
        
        .right-panel { background: #111; border-top: 2px solid #333; display: flex; flex-direction: column; height: 40vh; flex-shrink: 0; }
        @media (min-width: 1024px) { .right-panel { width: 350px; height: auto; border-top: none; border-left: 2px solid #333; } }
        
        .horarios { display: flex; gap: 6px; padding: 10px; overflow-x: auto; flex-shrink: 0; background: #0a0a0a; -webkit-overflow-scrolling: touch; }
        .btn-hora { flex: 0 0 auto; min-width: 85px; padding: 10px 6px; background: #222; border: 1px solid #444; border-radius: 8px; color: #ccc; cursor: pointer; font-size: 0.75rem; text-align: center; }
        .btn-hora.active { background: linear-gradient(135deg, #27ae60, #229954); color: white; font-weight: bold; border-color: #27ae60; }
        .btn-hora.expired { background: #300; color: #666; text-decoration: line-through; pointer-events: none; opacity: 0.5; }
        
        .ticket-display { flex: 1; background: #000; margin: 0 10px 10px; border-radius: 10px; padding: 12px; border: 1px solid #333; overflow-y: auto; font-size: 0.85rem; }
        .ticket-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
        .ticket-table th { background: #1a1a2e; color: #ffd700; padding: 8px 6px; text-align: left; position: sticky; top: 0; }
        .ticket-table td { padding: 8px 6px; border-bottom: 1px solid #222; }
        .ticket-total { margin-top: 12px; padding-top: 12px; border-top: 2px solid #ffd700; text-align: right; font-size: 1.2rem; font-weight: bold; color: #ffd700; }
        
        .action-btns { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; padding: 10px; background: #0a0a0a; flex-shrink: 0; }
        .action-btns button { padding: 14px 5px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 0.8rem; min-height: 48px; }
        .btn-agregar { background: linear-gradient(135deg, #27ae60, #229954); color: white; grid-column: span 3; font-size: 1.1rem; }
        .btn-vender { background: linear-gradient(135deg, #2980b9, #2573a7); color: white; grid-column: span 3; }
        .btn-resultados { background: #f39c12; color: black; }
        .btn-caja { background: #16a085; color: white; }
        .btn-pagar { background: #8e44ad; color: white; }
        .btn-anular { background: #c0392b; color: white; }
        
        /* Modals */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 1000; overflow-y: auto; }
        .modal-content { background: #1a1a2e; margin: 10px; padding: 20px; border-radius: 15px; border: 2px solid #ffd700; max-width: 600px; margin: 40px auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333; }
        .modal h3 { color: #ffd700; }
        .btn-close { background: #c0392b; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
        
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; color: #888; font-size: 0.9rem; margin-bottom: 6px; }
        .form-group input, .form-group select { width: 100%; padding: 12px; background: #000; border: 1px solid #444; color: white; border-radius: 8px; }
        .btn-submit { background: linear-gradient(135deg, #27ae60, #229954); color: white; border: none; padding: 14px; width: 100%; border-radius: 8px; font-weight: bold; cursor: pointer; }
        
        .tabs { display: flex; gap: 2px; margin-bottom: 20px; border-bottom: 2px solid #333; }
        .tab-btn { flex: 1; background: transparent; border: none; color: #888; padding: 14px 10px; cursor: pointer; font-size: 0.85rem; border-bottom: 3px solid transparent; }
        .tab-btn.active { color: #ffd700; border-bottom-color: #ffd700; font-weight: bold; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        .stats-box { background: linear-gradient(135deg, #0a0a0a, #1a1a2e); padding: 20px; border-radius: 12px; margin: 15px 0; border: 1px solid #333; }
        .stat-row { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #222; }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #aaa; }
        .stat-value { color: #ffd700; font-weight: bold; font-size: 1.2rem; }
        .stat-value.negative { color: #e74c3c; }
        .stat-value.positive { color: #27ae60; }
        
        .table-container { overflow-x: auto; margin: 15px 0; border-radius: 8px; border: 1px solid #333; }
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        th, td { padding: 12px 10px; text-align: left; border-bottom: 1px solid #333; }
        th { background: linear-gradient(135deg, #ffd700, #ffed4e); color: black; font-weight: bold; }
        
        .ticket-item { background: #0a0a0a; padding: 15px; margin: 8px 0; border-radius: 10px; border-left: 4px solid #2980b9; cursor: pointer; }
        .ticket-item.ganador { border-left-color: #27ae60; background: rgba(39,174,96,0.1); }
        .ticket-serial { color: #ffd700; font-weight: bold; font-size: 1.1rem; }
        .ticket-info { color: #888; font-size: 0.85rem; margin-top: 5px; }
        .ticket-premio { color: #27ae60; font-weight: bold; margin-top: 5px; }
        .estado-pagado { color: #27ae60; }
        .estado-pendiente { color: #f39c12; }
        .estado-anulado { color: #e74c3c; text-decoration: line-through; }
    </style>
</head>
<body>
    <!-- Menu Desktop -->
    <div class="win-menu-bar">
        <div class="win-menu-header">
            <div class="win-title">🦁 {{agencia}}</div>
            <button onclick="location.href='/logout'" style="background: #c0392b; color: white; border: none; padding: 6px 15px; border-radius: 5px; cursor: pointer; font-size: 0.8rem;">SALIR</button>
        </div>
        <ul class="win-menu-items">
            <li class="win-menu-item">
                <a>📁 Archivo</a>
                <ul class="win-submenu">
                    <li class="win-submenu-item"><a onclick="abrirCaja()">💰 Caja del Día</a></li>
                    <li class="win-submenu-item"><a onclick="abrirCajaHistorico()">📊 Historial de Caja</a></li>
                    <li class="win-submenu-item"><a onclick="abrirMisTickets()">🎫 Mis Tickets</a></li>
                </ul>
            </li>
            <li class="win-menu-item">
                <a>🔍 Consultas</a>
                <ul class="win-submenu">
                    <li class="win-submenu-item"><a onclick="verResultados()">📋 Resultados de Hoy</a></li>
                    <li class="win-submenu-item"><a onclick="verificarTicket()">🔎 Verificar Ticket</a></li>
                </ul>
            </li>
        </ul>
    </div>

    <!-- Mobile Header -->
    <div class="mobile-header">
        <div style="color: #ffd700; font-weight: bold;">🦁 {{agencia}}</div>
        <button class="hamburger-btn" onclick="toggleMobileMenu()">☰</button>
    </div>
    
    <div class="mobile-menu-overlay" onclick="toggleMobileMenu()"></div>
    <div class="mobile-menu" id="mobileMenu">
        <div style="padding: 15px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center;">
            <div style="color: #ffd700;">MENÚ</div>
            <button onclick="toggleMobileMenu()" style="background: #c0392b; color: white; border: none; width: 30px; height: 30px; border-radius: 50%;">×</button>
        </div>
        <div style="padding: 15px; border-bottom: 1px solid #222; color: #ffd700; background: rgba(255,215,0,0.1);">📁 Archivo</div>
        <div style="padding: 15px; border-bottom: 1px solid #222; cursor: pointer;" onclick="abrirCaja(); toggleMobileMenu();">💰 Caja del Día</div>
        <div style="padding: 15px; border-bottom: 1px solid #222; cursor: pointer;" onclick="abrirCajaHistorico(); toggleMobileMenu();">📊 Historial</div>
        <div style="padding: 15px; border-bottom: 1px solid #222; cursor: pointer;" onclick="abrirMisTickets(); toggleMobileMenu();">🎫 Mis Tickets</div>
        <div style="padding: 15px; border-bottom: 1px solid #222; color: #ffd700; background: rgba(255,215,0,0.1); margin-top: 10px;">🔍 Consultas</div>
        <div style="padding: 15px; border-bottom: 1px solid #222; cursor: pointer;" onclick="verResultados(); toggleMobileMenu();">📋 Resultados</div>
        <div style="padding: 15px; border-bottom: 1px solid #222; cursor: pointer;" onclick="verificarTicket(); toggleMobileMenu();">🔎 Verificar Ticket</div>
        <div style="padding: 15px; color: #e74c3c; cursor: pointer; margin-top: 20px;" onclick="location.href='/logout'">🚪 Cerrar Sesión</div>
    </div>

    <!-- Header -->
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
                <div style="text-align:center; color:#666; padding:20px; font-style:italic;">Selecciona animales y horarios...</div>
            </div>
            <div class="action-btns">
                <button class="btn-agregar" onclick="agregar()">AGREGAR AL TICKET</button>
                <button class="btn-vender" onclick="vender()">ENVIAR POR WHATSAPP</button>
                <button class="btn-resultados" onclick="verResultados()">RESULTADOS</button>
                <button class="btn-caja" onclick="abrirCaja()">CAJA</button>
                <button class="btn-pagar" onclick="pagar()">PAGAR</button>
                <button class="btn-anular" onclick="anular()">ANULAR</button>
            </div>
        </div>
    </div>

    <!-- Modal Caja -->
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
                    <div class="stat-row"><span class="stat-label">Ventas:</span><span class="stat-value" id="caja-ventas">S/0</span></div>
                    <div class="stat-row"><span class="stat-label">Premios Pagados:</span><span class="stat-value negative" id="caja-premios-pagados">S/0</span></div>
                    <div class="stat-row"><span class="stat-label">Premios Pendientes:</span><span class="stat-value" style="color: #f39c12;" id="caja-premios-pendientes">S/0</span></div>
                    <div class="stat-row"><span class="stat-label">Comisión:</span><span class="stat-value" id="caja-comision">S/0</span></div>
                    <div class="stat-row"><span class="stat-label">Balance Real:</span><span class="stat-value" id="caja-balance">S/0</span></div>
                </div>
                <div id="alerta-pendientes" style="display:none; background: rgba(243,156,18,0.2); border: 1px solid #f39c12; padding: 15px; border-radius: 8px; color: #f39c12; text-align: center;">
                    Tienes <strong id="num-pendientes">0</strong> ticket(s) por cobrar
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
                <button class="btn-submit" onclick="consultarHistoricoCaja()">CONSULTAR</button>
                <div id="resultado-historico" style="display:none; margin-top: 20px;">
                    <div class="stats-box">
                        <div class="stat-row"><span class="stat-label">Ventas:</span><span class="stat-value" id="hist-ventas">S/0</span></div>
                        <div class="stat-row"><span class="stat-label">Premios:</span><span class="stat-value negative" id="hist-premios">S/0</span></div>
                        <div class="stat-row"><span class="stat-label">Balance:</span><span class="stat-value" id="hist-balance">S/0</span></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal Mis Tickets (NUEVO) -->
    <div class="modal" id="modal-mis-tickets">
        <div class="modal-content" style="max-width: 800px;">
            <div class="modal-header">
                <h3>🎫 MIS TICKETS VENDIDOS</h3>
                <button class="btn-close" onclick="cerrarModal('modal-mis-tickets')">X</button>
            </div>
            <div style="display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap;">
                <input type="date" id="ticket-desde" style="flex: 1; min-width: 120px; padding: 10px; background: #000; border: 1px solid #444; color: white; border-radius: 8px;">
                <input type="date" id="ticket-hasta" style="flex: 1; min-width: 120px; padding: 10px; background: #000; border: 1px solid #444; color: white; border-radius: 8px;">
                <select id="ticket-estado" style="flex: 1; min-width: 120px; padding: 10px; background: #000; border: 1px solid #444; color: white; border-radius: 8px;">
                    <option value="todos">Todos</option>
                    <option value="pagados">Pagados</option>
                    <option value="pendientes">Pendientes</option>
                    <option value="anulados">Anulados</option>
                </select>
                <button class="btn-submit" onclick="cargarMisTickets()" style="flex: 1; min-width: 120px;">BUSCAR</button>
            </div>
            <div id="lista-mis-tickets" style="max-height: 400px; overflow-y: auto;">
                <p style="color: #888; text-align: center; padding: 20px;">Selecciona fechas y presiona Buscar</p>
            </div>
        </div>
    </div>

    <!-- Modal Detalle Ticket -->
    <div class="modal" id="modal-detalle-ticket">
        <div class="modal-content">
            <div class="modal-header">
                <h3>DETALLE DE TICKET</h3>
                <button class="btn-close" onclick="cerrarModal('modal-detalle-ticket')">X</button>
            </div>
            <div id="contenido-detalle-ticket"></div>
        </div>
    </div>

    <!-- Modal Resultados -->
    <div class="modal" id="modal-resultados">
        <div class="modal-content">
            <div class="modal-header">
                <h3>RESULTADOS</h3>
                <button class="btn-close" onclick="cerrarModal('modal-resultados')">X</button>
            </div>
            <div class="form-group">
                <label>Fecha:</label>
                <input type="date" id="resultados-fecha" onchange="cargarResultadosFecha()">
            </div>
            <div id="lista-resultados" style="max-height: 400px; overflow-y: auto;"></div>
        </div>
    </div>

    <script>
        let seleccionados = [], especiales = [], horariosSel = [], carrito = [];
        let horasPeru = {{horarios_peru|tojson}};
        let horasVen = {{horarios_venezuela|tojson}};
        
        function toggleMobileMenu() {
            document.getElementById('mobileMenu').classList.toggle('active');
            document.querySelector('.mobile-menu-overlay').classList.toggle('active');
        }
        
        function updateReloj() {
            let now = new Date();
            let peruTime = new Date(now.toLocaleString("en-US", {timeZone: "America/Lima"}));
            document.getElementById('reloj').textContent = peruTime.toLocaleString('es-PE', {hour: '2-digit', minute:'2-digit'});
            
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
                if (btn && horaActual > sorteoMinutos - 5) btn.classList.add('expired');
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
            const display = document.getElementById('ticket-display');
            let total = 0;
            let html = '<table class="ticket-table"><thead><tr><th>Hora</th><th>Apuesta</th><th>S/</th></tr></thead><tbody>';
            
            for (let item of carrito) {
                let nom = item.tipo === 'animal' ? item.nombre.substring(0,10) : item.seleccion;
                let color = item.tipo === 'animal' ? '#ffd700' : '#3498db';
                html += `<tr><td style="color:#aaa; font-size:0.75rem">${item.hora}</td><td style="color:${color}; font-weight:bold; font-size:0.8rem">${item.seleccion} ${nom}</td><td style="text-align:right; font-weight:bold">${item.monto}</td></tr>`;
                total += item.monto;
            }
            
            if (horariosSel.length > 0 && (seleccionados.length > 0 || especiales.length > 0)) {
                let monto = parseFloat(document.getElementById('monto').value) || 5;
                for (let h of horariosSel) {
                    for (let a of seleccionados) {
                        let indicador = a.k === "40" ? " 🦉x70" : "";
                        html += `<tr style="opacity:0.7; background:rgba(255,215,0,0.1)"><td style="color:#ffd700; font-size:0.75rem">${h}</td><td style="color:#ffd700; font-size:0.8rem">${a.k} ${a.nombre}${indicador}</td><td style="text-align:right; color:#ffd700; font-weight:bold">${monto}</td></tr>`;
                    }
                    for (let e of especiales) {
                        html += `<tr style="opacity:0.7; background:rgba(52,152,219,0.1)"><td style="color:#3498db; font-size:0.75rem">${h}</td><td style="color:#3498db; font-size:0.8rem">${e}</td><td style="text-align:right; color:#3498db; font-weight:bold">${monto}</td></tr>`;
                    }
                }
            }
            
            html += '</tbody></table>';
            if (carrito.length === 0 && (seleccionados.length === 0 && especiales.length === 0)) {
                html = '<div style="text-align:center; color:#666; padding:20px; font-style:italic;">Selecciona animales y horarios...</div>';
            } else if (carrito.length === 0) {
                html += '<div style="text-align:center; color:#888; padding:15px; font-size:0.85rem; background:rgba(255,215,0,0.05); border-radius:8px; margin-top:10px;">👆 Presiona AGREGAR para confirmar</div>';
            }
            
            if (total > 0) html += `<div class="ticket-total">TOTAL: S/${total}</div>`;
            display.innerHTML = html;
        }
        
        function agregar() {
            if (horariosSel.length === 0 || (seleccionados.length === 0 && especiales.length === 0)) {
                alert('Selecciona horario y animal/especial'); 
                return;
            }
            let monto = parseFloat(document.getElementById('monto').value) || 5;
            for (let h of horariosSel) {
                for (let a of seleccionados) carrito.push({hora: h, seleccion: a.k, nombre: a.nombre, monto: monto, tipo: 'animal'});
                for (let e of especiales) carrito.push({hora: h, seleccion: e, nombre: e, monto: monto, tipo: 'especial'});
            }
            seleccionados = []; especiales = []; horariosSel = [];
            document.querySelectorAll('.animal-card.active, .btn-esp.active, .btn-hora.active').forEach(el => el.classList.remove('active'));
            updateTicket();
        }
        
        async function vender() {
            if (carrito.length === 0) { alert('Carrito vacío'); return; }
            if (!confirm(`Total: S/${carrito.reduce((a,b)=>a+b.monto,0)}\\n¿Confirmar venta?`)) return;
            
            try {
                let jugadas = carrito.map(c => ({hora: c.hora, seleccion: c.seleccion, monto: c.monto, tipo: c.tipo}));
                const response = await fetch('/api/procesar-venta', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({jugadas: jugadas})
                });
                const data = await response.json();
                if (data.error) { alert(data.error); }
                else {
                    window.open(data.url_whatsapp, '_blank');
                    carrito = []; updateTicket();
                    alert('Ticket generado');
                }
            } catch (e) { alert('Error de conexión'); }
        }

        function cerrarModal(id) { document.getElementById(id).style.display = 'none'; }
        
        function abrirCaja() {
            fetch('/api/caja').then(r => r.json()).then(d => {
                document.getElementById('caja-ventas').textContent = 'S/' + d.ventas.toFixed(2);
                document.getElementById('caja-premios-pagados').textContent = 'S/' + d.premios_pagados.toFixed(2);
                document.getElementById('caja-premios-pendientes').textContent = 'S/' + d.premios_pendientes.toFixed(2);
                document.getElementById('caja-comision').textContent = 'S/' + d.comision.toFixed(2);
                document.getElementById('caja-balance').textContent = 'S/' + d.balance.toFixed(2);
                document.getElementById('caja-balance').className = 'stat-value ' + (d.balance >= 0 ? 'positive' : 'negative');
                
                if (d.tickets_pendientes > 0) {
                    document.getElementById('alerta-pendientes').style.display = 'block';
                    document.getElementById('num-pendientes').textContent = d.tickets_pendientes;
                } else {
                    document.getElementById('alerta-pendientes').style.display = 'none';
                }
                document.getElementById('modal-caja').style.display = 'block';
            });
        }
        
        function abrirCajaHistorico() {
            abrirCaja();
            setTimeout(() => switchTab('historico'), 100);
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
            }).then(r => r.json()).then(d => {
                document.getElementById('resultado-historico').style.display = 'block';
                document.getElementById('hist-ventas').textContent = 'S/' + d.totales.ventas.toFixed(2);
                document.getElementById('hist-premios').textContent = 'S/' + d.totales.premios.toFixed(2);
                document.getElementById('hist-balance').textContent = 'S/' + d.totales.balance.toFixed(2);
            });
        }
        
        // NUEVO: Funciones para Mis Tickets
        function abrirMisTickets() {
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('ticket-desde').value = hoy;
            document.getElementById('ticket-hasta').value = hoy;
            document.getElementById('modal-mis-tickets').style.display = 'block';
            cargarMisTickets();
        }
        
        function cargarMisTickets() {
            let desde = document.getElementById('ticket-desde').value;
            let hasta = document.getElementById('ticket-hasta').value;
            let estado = document.getElementById('ticket-estado').value;
            
            let container = document.getElementById('lista-mis-tickets');
            container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Cargando...</p>';
            
            fetch(`/api/mis-tickets?desde=${desde}&hasta=${hasta}&estado=${estado}`)
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    container.innerHTML = `<p style="color: #c0392b; text-align: center;">${d.error}</p>`;
                    return;
                }
                
                if (d.tickets.length === 0) {
                    container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">No hay tickets en este rango</p>';
                    return;
                }
                
                let html = `<div style="margin-bottom: 15px; color: #ffd700; font-weight: bold;">Total: ${d.total_registros} tickets</div>`;
                
                d.tickets.forEach(t => {
                    let clase = t.tiene_premio ? 'ticket-item ganador' : 'ticket-item';
                    let estado = t.anulado ? '<span class="estado-anulado">ANULADO</span>' : 
                                t.pagado ? '<span class="estado-pagado">PAGADO</span>' : 
                                '<span class="estado-pendiente">PENDIENTE</span>';
                    
                    let premioHtml = t.tiene_premio ? `<div class="ticket-premio">💰 Premio: S/${t.premio_pendiente}</div>` : '';
                    
                    html += `
                        <div class="${clase}" onclick="verDetalleTicket(${t.id})">
                            <div class="ticket-serial">#${t.serial} ${estado}</div>
                            <div class="ticket-info">Fecha: ${t.fecha} • Monto: S/${t.total} • Jugadas: ${t.cantidad_jugadas}</div>
                            ${premioHtml}
                        </div>
                    `;
                });
                container.innerHTML = html;
            })
            .catch(e => {
                container.innerHTML = '<p style="color: #c0392b; text-align: center;">Error de conexión</p>';
            });
        }
        
        function verDetalleTicket(id) {
            fetch(`/api/ticket-detalle/${id}`)
            .then(r => r.json())
            .then(d => {
                if (d.error) { alert(d.error); return; }
                
                let ticket = d.ticket;
                let estado = ticket.anulado ? 'ANULADO' : ticket.pagado ? 'PAGADO' : 'PENDIENTE';
                let color = ticket.anulado ? '#e74c3c' : ticket.pagado ? '#27ae60' : '#f39c12';
                
                let html = `
                    <div style="background: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px; margin-bottom: 15px;">
                        <div style="font-size: 1.3rem; color: #ffd700; margin-bottom: 10px;">Ticket #${ticket.serial}</div>
                        <div style="color: #888; margin-bottom: 5px;">Fecha: ${ticket.fecha}</div>
                        <div style="color: #888; margin-bottom: 5px;">Estado: <span style="color: ${color}; font-weight: bold;">${estado}</span></div>
                        <div style="color: #888;">Total Apostado: S/${ticket.total}</div>
                    </div>
                    <h4 style="color: #ffd700; margin-bottom: 10px;">Jugadas:</h4>
                `;
                
                d.jugadas.forEach(j => {
                    let resultado = j.resultado ? `${j.resultado} - ${getNombreAnimal(j.resultado)}` : 'Pendiente';
                    let gano = j.gano ? '✅ GANÓ' : '❌ No ganó';
                    let colorGano = j.gano ? '#27ae60' : '#666';
                    
                    html += `
                        <div style="background: rgba(255,255,255,0.05); padding: 12px; margin-bottom: 8px; border-radius: 8px; border-left: 3px solid ${colorGano};">
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: #ffd700;">${j.hora}</span>
                                <span style="color: ${colorGano}; font-weight: bold;">${gano}</span>
                            </div>
                            <div style="color: #aaa; font-size: 0.9rem; margin-top: 5px;">
                                ${j.tipo === 'animal' ? j.seleccion + ' - ' + getNombreAnimal(j.seleccion) : j.seleccion} 
                                (S/${j.monto})
                            </div>
                            <div style="color: #666; font-size: 0.85rem; margin-top: 3px;">
                                Resultado: ${resultado}
                            </div>
                            ${j.gano ? `<div style="color: #27ae60; font-weight: bold; margin-top: 5px;">Premio: S/${j.premio}</div>` : ''}
                        </div>
                    `;
                });
                
                if (d.total_premio > 0) {
                    html += `
                        <div style="background: rgba(39,174,96,0.1); border: 1px solid #27ae60; padding: 15px; border-radius: 10px; margin-top: 15px; text-align: center;">
                            <div style="color: #27ae60; font-size: 1.2rem; font-weight: bold;">Total a Pagar: S/${d.total_premio}</div>
                            <div style="color: #888; font-size: 0.9rem; margin-top: 5px;">Ganancia neta: S/${d.ganancia_neta}</div>
                        </div>
                    `;
                }
                
                document.getElementById('contenido-detalle-ticket').innerHTML = html;
                document.getElementById('modal-detalle-ticket').style.display = 'block';
            });
        }
        
        function getNombreAnimal(numero) {
            const animales = {{animales|tojson}};
            return animales[numero] || 'Desconocido';
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
            container.innerHTML = '<p style="color: #888; text-align: center;">Cargando...</p>';
            
            fetch('/api/resultados-fecha', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha: fecha})
            })
            .then(r => r.json())
            .then(d => {
                let html = '';
                for (let hora of horasPeru) {
                    let resultado = d.resultados[hora];
                    let clase = resultado ? '' : 'pendiente';
                    let contenido = resultado ? 
                        `<span style="color: #ffd700; font-size: 1.3rem; font-weight: bold;">${resultado.animal}</span>
                         <span style="color: #aaa;">${resultado.nombre}</span>` :
                        `<span style="color: #666;">Pendiente</span>`;
                    
                    html += `
                        <div style="background: #0a0a0a; padding: 15px; margin: 8px 0; border-radius: 10px; border-left: 4px solid ${resultado ? '#27ae60' : '#666'}; display: flex; justify-content: space-between; align-items: center;">
                            <div><strong style="color: #ffd700;">${hora}</strong></div>
                            <div style="text-align: right; display: flex; flex-direction: column;">${contenido}</div>
                        </div>
                    `;
                }
                container.innerHTML = html;
            });
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
                
                if (d.error) { alert(d.error); return; }
                
                if (d.total_ganado > 0 && confirm(`Total Ganado: S/${d.total_ganado.toFixed(2)}\\n¿Confirmar pago?`)) {
                    await fetch('/api/pagar-ticket', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ticket_id: d.ticket_id})
                    });
                    alert('Ticket pagado correctamente');
                } else if (d.total_ganado === 0) {
                    alert('Ticket no ganador');
                }
            } catch (e) { alert('Error de conexión'); }
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
                alert(d.error || d.mensaje);
            } catch (e) { alert('Error de conexión'); }
        }
        
        function verificarTicket() {
            let serial = prompt('Ingrese SERIAL:'); 
            if (!serial) return;
            
            fetch('/api/verificar-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) alert(d.error);
                else alert('Total Ganado: S/' + d.total_ganado.toFixed(2));
            });
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
        });
    </script>
</body>
</html>'''

ADMIN_HTML = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0a0a0a; color: white; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        
        .admin-header { background: linear-gradient(90deg, #1a1a2e, #16213e); padding: 15px; border-bottom: 2px solid #ffd700; display: flex; justify-content: space-between; align-items: center; }
        .admin-title { color: #ffd700; font-size: 1.2rem; font-weight: bold; }
        .logout-btn { background: #c0392b; color: white; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        
        .admin-tabs { display: flex; background: #1a1a2e; border-bottom: 1px solid #333; overflow-x: auto; }
        .admin-tab { flex: 1; min-width: 120px; padding: 15px 10px; background: transparent; border: none; color: #888; cursor: pointer; font-size: 0.85rem; border-bottom: 3px solid transparent; }
        .admin-tab.active { color: #ffd700; border-bottom-color: #ffd700; font-weight: bold; }
        
        .content { padding: 20px; max-width: 1200px; margin: 0 auto; padding-bottom: 30px; }
        
        .form-box { background: #1a1a2e; padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #333; }
        .form-box h3 { color: #ffd700; margin-bottom: 15px; font-size: 1.1rem; border-bottom: 1px solid #333; padding-bottom: 10px; }
        .form-row { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }
        .form-row input, .form-row select { flex: 1; min-width: 120px; padding: 12px; background: #000; border: 1px solid #444; color: white; border-radius: 8px; }
        .btn-submit { background: linear-gradient(135deg, #27ae60, #229954); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; }
        .btn-secondary { background: #444; color: white; border: none; padding: 10px 16px; border-radius: 6px; cursor: pointer; }
        .btn-csv { background: linear-gradient(135deg, #f39c12, #e67e22); color: black; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; }
        
        .table-container { overflow-x: auto; margin: 15px 0; border-radius: 8px; border: 1px solid #333; }
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        th, td { padding: 12px 10px; text-align: left; border-bottom: 1px solid #333; }
        th { background: linear-gradient(135deg, #ffd700, #ffed4e); color: black; font-weight: bold; }
        tr:hover { background: rgba(255,215,0,0.05); }
        
        .stat-card { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 12px; border: 1px solid #ffd700; text-align: center; margin-bottom: 10px; }
        .stat-card h3 { color: #888; font-size: 0.75rem; margin-bottom: 8px; text-transform: uppercase; }
        .stat-card p { color: #ffd700; font-size: 1.4rem; font-weight: bold; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        
        .resultado-item { background: #0a0a0a; padding: 15px; margin: 8px 0; border-radius: 10px; border-left: 4px solid #27ae60; display: flex; justify-content: space-between; align-items: center; }
        .resultado-item.pendiente { border-left-color: #666; opacity: 0.7; }
        .resultado-numero { color: #ffd700; font-weight: bold; font-size: 1.4rem; }
        
        .btn-editar { background: linear-gradient(135deg, #2980b9, #3498db); color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; margin-left: 10px; }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 2000; justify-content: center; align-items: center; padding: 20px; }
        .modal.active { display: flex; }
        .modal-box { background: #1a1a2e; padding: 25px; border-radius: 15px; border: 2px solid #ffd700; max-width: 400px; width: 100%; }
        .warning-box { background: rgba(243, 156, 18, 0.2); border: 1px solid #f39c12; color: #f39c12; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 0.9rem; display: none; }
        
        .mensaje { padding: 15px; margin: 15px 0; border-radius: 8px; display: none; }
        .mensaje.success { background: rgba(39,174,96,0.2); border: 1px solid #27ae60; display: block; color: #27ae60; }
        .mensaje.error { background: rgba(192,57,43,0.2); border: 1px solid #c0392b; display: block; color: #c0392b; }
        
        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.3s; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        
        .premio-pendiente { color: #f39c12; font-weight: bold; }
        .premio-pagado { color: #27ae60; }
    </style>
</head>
<body>
    <!-- Modal Edición -->
    <div class="modal" id="modal-editar">
        <div class="modal-box">
            <h3 style="color: #ffd700; margin-bottom: 20px; text-align: center;">✏️ EDITAR RESULTADO</h3>
            <div class="warning-box" id="editar-advertencia"></div>
            <div style="margin-bottom: 15px;">
                <label style="color: #888;">Fecha:</label>
                <input type="text" id="editar-fecha-display" readonly style="width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #ffd700; border-radius: 6px; margin-top: 5px;">
            </div>
            <div style="margin-bottom: 15px;">
                <label style="color: #888;">Hora:</label>
                <input type="text" id="editar-hora-display" readonly style="width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #ffd700; border-radius: 6px; margin-top: 5px;">
            </div>
            <div style="margin-bottom: 20px;">
                <label style="color: #888;">Nuevo Animal:</label>
                <select id="editar-animal-select" style="width: 100%; padding: 12px; background: #000; border: 2px solid #ffd700; color: white; border-radius: 8px; margin-top: 5px;">
                    {% for k, v in animales.items() %}
                    <option value="{{k}}">{{k}} - {{v}}</option>
                    {% endfor %}
                </select>
            </div>
            <div style="display: flex; gap: 10px;">
                <button onclick="cerrarModalEditar()" style="flex: 1; background: #444; color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-weight: bold;">CANCELAR</button>
                <button onclick="confirmarEdicion()" style="flex: 2; background: linear-gradient(135deg, #27ae60, #229954); color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-weight: bold;">GUARDAR</button>
            </div>
        </div>
    </div>

    <div class="admin-header">
        <div class="admin-title">👑 PANEL ADMINISTRADOR</div>
        <button onclick="location.href='/logout'" class="logout-btn">SALIR</button>
    </div>

    <div class="admin-tabs">
        <button class="admin-tab active" onclick="showTab('dashboard')">📊 Dashboard</button>
        <button class="admin-tab" onclick="showTab('resultados')">📋 Resultados</button>
        <button class="admin-tab" onclick="showTab('reporte')">🏢 Reporte Agencias</button>
        <button class="admin-tab" onclick="showTab('agencias')">➕ Crear Agencias</button>
        <button class="admin-tab" onclick="showTab('auditoria')">📜 Auditoría</button>
    </div>

    <div class="content">
        <div id="mensaje" class="mensaje"></div>
        
        <!-- DASHBOARD -->
        <div id="dashboard" class="tab-content active">
            <h3 style="color: #ffd700; margin-bottom: 20px;">📊 RESUMEN GENERAL</h3>
            <div class="stats-grid">
                <div class="stat-card"><h3>Total Ventas</h3><p id="dash-ventas">S/0</p></div>
                <div class="stat-card"><h3>Premios Pagados</h3><p id="dash-premios-pagados">S/0</p></div>
                <div class="stat-card"><h3>Premios Pendientes</h3><p id="dash-premios-pendientes" style="color: #f39c12;">S/0</p></div>
                <div class="stat-card"><h3>Balance Real</h3><p id="dash-balance">S/0</p></div>
            </div>
        </div>

        <!-- RESULTADOS -->
        <div id="resultados" class="tab-content">
            <div class="form-box">
                <h3>📋 GESTIÓN DE RESULTADOS</h3>
                <div class="form-row">
                    <input type="date" id="res-fecha" onchange="cargarResultadosAdmin()">
                    <button class="btn-secondary" onclick="cargarResultadosAdmin()">HOY</button>
                </div>
                <div id="lista-resultados-admin"></div>
            </div>
            
            <div class="form-box">
                <h3>➕ CARGAR NUEVO RESULTADO</h3>
                <div class="form-row">
                    <select id="nueva-hora" style="flex: 1;">
                        {% for h in horarios %}<option value="{{h}}">{{h}}</option>{% endfor %}
                    </select>
                    <select id="nuevo-animal" style="flex: 2;">
                        {% for k, v in animales.items() %}<option value="{{k}}">{{k}} - {{v}}</option>{% endfor %}
                    </select>
                    <button class="btn-submit" onclick="guardarNuevoResultado()">GUARDAR</button>
                </div>
            </div>
        </div>

        <!-- REPORTE AGENCIAS MEJORADO -->
        <div id="reporte" class="tab-content">
            <div class="form-box">
                <h3>🏢 REPORTE COMPLETO POR AGENCIAS (CON PREMIOS PENDIENTES)</h3>
                <div class="form-row">
                    <input type="date" id="reporte-inicio">
                    <input type="date" id="reporte-fin">
                    <button class="btn-submit" onclick="generarReporteCompleto()">GENERAR REPORTE</button>
                </div>
                <div class="form-row">
                    <button class="btn-secondary" onclick="setRango('hoy')">Hoy</button>
                    <button class="btn-secondary" onclick="setRango('ayer')">Ayer</button>
                    <button class="btn-secondary" onclick="setRango('semana')">7 días</button>
                </div>
                
                <div id="reporte-contenido" style="display:none; margin-top: 30px;">
                    <div class="stats-grid">
                        <div class="stat-card"><h3>Ventas Totales</h3><p id="rep-ventas">S/0</p></div>
                        <div class="stat-card"><h3>Premios Pagados</h3><p id="rep-pagados">S/0</p></div>
                        <div class="stat-card"><h3>Premios Pendientes</h3><p id="rep-pendientes" style="color: #f39c12;">S/0</p></div>
                        <div class="stat-card"><h3>Balance Real</h3><p id="rep-balance">S/0</p></div>
                    </div>

                    <h4 style="color: #ffd700; margin: 25px 0 15px;">DETALLE POR AGENCIA</h4>
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Agencia</th>
                                    <th>Tickets</th>
                                    <th>Ventas</th>
                                    <th>Pagados</th>
                                    <th>Pendientes</th>
                                    <th>Total Premios</th>
                                    <th>Comisión</th>
                                    <th>Balance</th>
                                </tr>
                            </thead>
                            <tbody id="tabla-reporte"></tbody>
                        </table>
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
            <div class="form-box">
                <h3>🏢 AGENCIAS EXISTENTES</h3>
                <div class="table-container">
                    <table>
                        <thead><tr><th>ID</th><th>Usuario</th><th>Nombre</th><th>Comisión</th></tr></thead>
                        <tbody id="tabla-agencias"><tr><td colspan="4" style="text-align:center; padding: 20px;">Cargando...</td></tr></tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- AUDITORÍA -->
        <div id="auditoria" class="tab-content">
            <div class="form-box">
                <h3>📜 LOG DE AUDITORÍA (ÚLTIMOS 100 MOVIMIENTOS)</h3>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Fecha</th>
                                <th>Usuario</th>
                                <th>Acción</th>
                                <th>Detalle</th>
                            </tr>
                        </thead>
                        <tbody id="tabla-auditoria"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        let editandoFecha = null;
        let editandoHora = null;

        function showTab(tab) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.admin-tab').forEach(b => b.classList.remove('active'));
            document.getElementById(tab).classList.add('active');
            event.target.classList.add('active');
            
            if (tab === 'agencias') cargarAgencias();
            if (tab === 'auditoria') cargarAuditoria();
            if (tab === 'dashboard') cargarDashboard();
            if (tab === 'resultados') {
                let hoy = new Date().toISOString().split('T')[0];
                document.getElementById('res-fecha').value = hoy;
                cargarResultadosAdmin();
            }
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
                case 'hoy': inicio = fin = hoy; break;
                case 'ayer': let ayer = new Date(hoy); ayer.setDate(ayer.getDate() - 1); inicio = fin = ayer; break;
                case 'semana': inicio = new Date(hoy); inicio.setDate(inicio.getDate() - 6); fin = hoy; break;
            }
            document.getElementById('reporte-inicio').value = inicio.toISOString().split('T')[0];
            document.getElementById('reporte-fin').value = fin.toISOString().split('T')[0];
            generarReporteCompleto();
        }

        function cargarDashboard() {
            // Usar reporte de hoy para el dashboard
            let hoy = new Date().toISOString().split('T')[0];
            fetch('/admin/reporte-completo', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha_inicio: hoy, fecha_fin: hoy})
            })
            .then(r => r.json())
            .then(d => {
                if (d.totales) {
                    document.getElementById('dash-ventas').textContent = 'S/' + d.totales.ventas.toFixed(0);
                    document.getElementById('dash-premios-pagados').textContent = 'S/' + d.totales.premios_pagados.toFixed(0);
                    document.getElementById('dash-premios-pendientes').textContent = 'S/' + d.totales.premios_pendientes.toFixed(0);
                    document.getElementById('dash-balance').textContent = 'S/' + d.totales.balance.toFixed(0);
                    document.getElementById('dash-balance').style.color = d.totales.balance >= 0 ? '#27ae60' : '#e74c3c';
                }
            });
        }

        function generarReporteCompleto() {
            let inicio = document.getElementById('reporte-inicio').value;
            let fin = document.getElementById('reporte-fin').value;
            
            if (!inicio || !fin) { alert('Seleccione fechas'); return; }
            
            showMensaje('Generando reporte...', 'success');
            
            fetch('/admin/reporte-completo', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha_inicio: inicio, fecha_fin: fin})
            })
            .then(r => r.json())
            .then(d => {
                document.getElementById('reporte-contenido').style.display = 'block';
                document.getElementById('rep-ventas').textContent = 'S/' + d.totales.ventas.toFixed(0);
                document.getElementById('rep-pagados').textContent = 'S/' + d.totales.premios_pagados.toFixed(0);
                document.getElementById('rep-pendientes').textContent = 'S/' + d.totales.premios_pendientes.toFixed(0);
                document.getElementById('rep-balance').textContent = 'S/' + d.totales.balance.toFixed(0);
                
                let tbody = document.getElementById('tabla-reporte');
                let html = '';
                d.agencias.forEach(ag => {
                    let colorBalance = ag.balance >= 0 ? '#27ae60' : '#e74c3c';
                    html += `<tr>
                        <td><strong>${ag.nombre}</strong><br><small>${ag.usuario}</small></td>
                        <td>${ag.tickets}</td>
                        <td>S/${ag.ventas.toFixed(0)}</td>
                        <td class="premio-pagado">S/${ag.premios_pagados.toFixed(0)}</td>
                        <td class="premio-pendiente">S/${ag.premios_pendientes.toFixed(0)}</td>
                        <td>S/${ag.premios_totales.toFixed(0)}</td>
                        <td>S/${ag.comision.toFixed(0)}</td>
                        <td style="color: ${colorBalance}; font-weight: bold;">S/${ag.balance.toFixed(0)}</td>
                    </tr>`;
                });
                tbody.innerHTML = html;
            })
            .catch(e => showMensaje('Error: ' + e, 'error'));
        }

        function cargarResultadosAdmin() {
            let fecha = document.getElementById('res-fecha').value;
            if (!fecha) return;
            
            fetch('/api/resultados-fecha', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha: fecha})
            })
            .then(r => r.json())
            .then(d => {
                let container = document.getElementById('lista-resultados-admin');
                let html = '';
                let horarios = {{horarios|tojson}};
                
                horarios.forEach(hora => {
                    let resultado = d.resultados[hora];
                    let clase = resultado ? '' : 'pendiente';
                    let contenido = resultado ? 
                        `<span class="resultado-numero">${resultado.animal}</span><span style="color: #aaa;">${resultado.nombre}</span>` :
                        `<span style="color: #666;">Pendiente</span>`;
                    let boton = resultado ? 
                        `<button class="btn-editar" onclick="abrirModalEditar('${hora}', '${d.fecha_consulta}', '${resultado.animal}')">EDITAR</button>` :
                        `<button class="btn-editar" onclick="prepararNuevo('${hora}')" style="background: #27ae60;">CARGAR</button>`;
                    
                    html += `
                        <div class="resultado-item ${clase}">
                            <div><strong style="color: #ffd700;">${hora}</strong></div>
                            <div style="text-align: right;">${contenido}<br>${boton}</div>
                        </div>
                    `;
                });
                container.innerHTML = html;
            });
        }

        function prepararNuevo(hora) {
            document.getElementById('nueva-hora').value = hora;
            document.getElementById('nuevo-animal').focus();
        }

        function guardarNuevoResultado() {
            let form = new FormData();
            form.append('hora', document.getElementById('nueva-hora').value);
            form.append('animal', document.getElementById('nuevo-animal').value);
            form.append('fecha', document.getElementById('res-fecha').value);
            
            fetch('/admin/guardar-resultado', {method: 'POST', body: form})
            .then(r => r.json()).then(d => {
                if (d.status === 'ok') {
                    showMensaje(d.mensaje, 'success');
                    cargarResultadosAdmin();
                } else showMensaje(d.error, 'error');
            });
        }

        function abrirModalEditar(hora, fecha, animalActual) {
            editandoHora = hora;
            editandoFecha = fecha;
            document.getElementById('editar-fecha-display').value = fecha;
            document.getElementById('editar-hora-display').value = hora;
            document.getElementById('editar-animal-select').value = animalActual;
            
            // Verificar tickets afectados
            fetch('/admin/verificar-tickets-sorteo', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fecha: fecha, hora: hora})
            })
            .then(r => r.json())
            .then(d => {
                let adv = document.getElementById('editar-advertencia');
                if (d.tickets_count > 0) {
                    adv.style.display = 'block';
                    adv.textContent = `⚠️ Este sorteo tiene ${d.tickets_count} ticket(s) vendidos por S/${d.total_apostado}. Al cambiar el resultado, los premios se recalcularán.`;
                } else adv.style.display = 'none';
            });
            
            document.getElementById('modal-editar').classList.add('active');
        }

        function cerrarModalEditar() {
            document.getElementById('modal-editar').classList.remove('active');
        }

        function confirmarEdicion() {
            if (!confirm('¿Está seguro de modificar este resultado?')) return;
            
            let form = new FormData();
            form.append('hora', editandoHora);
            form.append('animal', document.getElementById('editar-animal-select').value);
            
            // Convertir fecha DD/MM/YYYY a YYYY-MM-DD para el backend
            let partes = editandoFecha.split('/');
            if (partes.length === 3) {
                form.append('fecha', `${partes[2]}-${partes[1]}-${partes[0]}`);
            }
            
            fetch('/admin/guardar-resultado', {method: 'POST', body: form})
            .then(r => r.json()).then(d => {
                if (d.status === 'ok') {
                    showMensaje('Resultado actualizado', 'success');
                    cerrarModalEditar();
                    cargarResultadosAdmin();
                } else showMensaje(d.error, 'error');
            });
        }

        function crearAgencia() {
            let form = new FormData();
            form.append('usuario', document.getElementById('new-usuario').value.trim());
            form.append('password', document.getElementById('new-password').value);
            form.append('nombre', document.getElementById('new-nombre').value.trim());
            
            fetch('/admin/crear-agencia', {method: 'POST', body: form})
            .then(r => r.json()).then(d => {
                if (d.status === 'ok') {
                    showMensaje(d.mensaje, 'success');
                    cargarAgencias();
                    document.getElementById('new-usuario').value = '';
                    document.getElementById('new-password').value = '';
                    document.getElementById('new-nombre').value = '';
                } else showMensaje(d.error, 'error');
            });
        }

        function cargarAgencias() {
            fetch('/admin/lista-agencias').then(r => r.json()).then(d => {
                let tbody = document.getElementById('tabla-agencias');
                if (!d || d.length === 0) { tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No hay agencias</td></tr>'; return; }
                let html = '';
                d.forEach(a => html += `<tr><td>${a.id}</td><td>${a.usuario}</td><td>${a.nombre_agencia}</td><td>${(a.comision * 100).toFixed(0)}%</td></tr>`);
                tbody.innerHTML = html;
            });
        }

        function cargarAuditoria() {
            fetch('/admin/auditoria')
            .then(r => r.json())
            .then(d => {
                let tbody = document.getElementById('tabla-auditoria');
                if (!d.logs || d.logs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 20px;">No hay registros</td></tr>';
                    return;
                }
                let html = '';
                d.logs.forEach(log => {
                    html += `<tr>
                        <td>${log.fecha}</td>
                        <td>${log.admin_nombre}</td>
                        <td>${log.accion}</td>
                        <td><small>${log.tabla} ${log.registro_id}</small></td>
                    </tr>`;
                });
                tbody.innerHTML = html;
            })
            .catch(e => {
                document.getElementById('tabla-auditoria').innerHTML = '<tr><td colspan="4" style="text-align:center; color: #c0392b;">Error cargando auditoría</td></tr>';
            });
        }

        document.addEventListener('DOMContentLoaded', function() {
            let hoy = new Date().toISOString().split('T')[0];
            document.getElementById('reporte-inicio').value = hoy;
            document.getElementById('reporte-fin').value = hoy;
            cargarDashboard();
        });
    </script>
</body>
</html>'''

# ==================== MAIN ====================
if __name__ == '__main__':
    print("=" * 60)
    print("  ZOOLO CASINO CLOUD v6.0")
    print("  SISTEMA REFACTORIZADO - TODO EN UNO")
    print("=" * 60)
    print("  Features incluidas:")
    print("  ✅ Consulta de tickets por fecha (Agencia)")
    print("  ✅ Reporte con premios pendientes (Admin)")
    print("  ✅ Edición de resultados con auditoría")
    print("  ✅ Seguridad Bcrypt")
    print("  ✅ Cálculo de premios centralizado")
    print("=" * 60)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
