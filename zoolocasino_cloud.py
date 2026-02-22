"""
ZOOLO CASINO CLOUD v6.4 - CORRECCIONES CRÍTICAS
- Reportes históricos funcionando correctamente
- Tickets vendidos aparecen inmediatamente con todos los estados
- Botón reimprimir en detalle de ticket
- Anulación funcionando con restricción de horario
"""

from flask import Flask, request, jsonify, render_template_string, session
import json
import urllib.request
import urllib.parse
import os
import uuid
import time
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ============================================
# CONFIGURACIÓN
# ============================================
SUPABASE_URL = "https://fhcnbqktqddgyyptnccb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZoY25icWt0cWRkZ3l5cHRuY2NiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk0MzgxNTMsImV4cCI6MjA2NTAxNDE1M30.0QAS8A_5nMBk9AxL5DcF0qmvDpJ1I8VvK3Ky0MCm3-w"

# Multiplicadores de pago
MULTIPLICADORES = {
    'directo': 35,
    'combinado': 70,
    'pale': 2,
    'tripleta': 60
}

# Animales y números
ANIMALES = {
    '00': 'Carnero', '01': 'Toro', '02': 'Ciempies', '03': 'Alacran',
    '04': 'Leon', '05': 'Raton', '06': 'Aguila', '07': 'Iguana',
    '08': 'Burro', '09': 'Ballena', '10': 'Chivo', '11': 'Caballo',
    '12': 'Mono', '13': 'Paloma', '14': 'Zorro', '15': 'Oso',
    '16': 'Pavo', '17': 'Burro', '18': 'Chivo', '19': 'Perro',
    '20': 'Cochino', '21': 'Gallo', '22': 'Camello', '23': 'Cebra',
    '24': 'Iguana', '25': 'Gallina', '26': 'Vaca', '27': 'Perico',
    '28': 'Erizo', '29': 'Garza', '30': 'Paloma', '31': 'Lapa',
    '32': 'Ardilla', '33': 'Pescado', '34': 'Venado', '35': 'Jirafa',
    '36': 'Culebra', '37': 'Delfin', '38': 'Ballena', '39': 'Arana',
    '40': 'Caiman', '41': 'Carnero'
}

# ============================================
# FUNCIONES AUXILIARES
# ============================================

def ahora_peru():
    """Obtiene la hora actual en Perú (UTC-5)"""
    return datetime.utcnow() - timedelta(hours=5)

def parse_fecha_ticket(fecha_str):
    """Parsea fecha en múltiples formatos"""
    if not fecha_str:
        return None
    try:
        # Formato dd/mm/YYYY HH:MM:SS
        if '/' in fecha_str:
            partes = fecha_str.split(' ')
            fecha_parte = partes[0].split('/')
            if len(fecha_parte) == 3:
                dia, mes, anio = fecha_parte
                hora = partes[1] if len(partes) > 1 else '00:00:00'
                return f"{anio}-{mes.zfill(2)}-{dia.zfill(2)}T{hora}"
        # Formato ISO
        return fecha_str
    except:
        return fecha_str

def formatear_monto(monto):
    """Formatea montos con decimales correctos"""
    try:
        monto_float = float(monto)
        if monto_float == int(monto_float):
            return str(int(monto_float))
        else:
            return "{:.1f}".format(monto_float)
    except:
        return str(monto)

def verificar_horario_bloqueo(sorteo_id, hora_sorteo_str):
    """Verifica si el sorteo ya cerró para anulaciones"""
    try:
        ahora = ahora_peru()
        hora_actual = ahora.hour * 60 + ahora.minute
        
        # Parsear hora del sorteo (formato HH:MM)
        if ':' in str(hora_sorteo_str):
            h, m = map(int, str(hora_sorteo_str).split(':')[:2])
            hora_sorteo = h * 60 + m
        else:
            return False, "Formato de hora inválido"
        
        # Bloquear si ya pasó la hora del sorteo
        if hora_actual >= hora_sorteo:
            return False, f"Sorteo {sorteo_id} ya cerró (hora límite: {hora_sorteo_str})"
        
        return True, "OK"
    except Exception as e:
        return False, f"Error verificando horario: {str(e)}"

def supabase_request(table, method='GET', data=None, filters=None, limit=None, offset=None, order=None, single=False):
    """Realiza peticiones a Supabase con manejo de errores"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Construir query params
        params = {}
        if filters:
            params.update(filters)
        if limit:
            params['limit'] = limit
        if offset:
            params['offset'] = offset
        if order:
            params['order'] = order
        if single:
            params['limit'] = 1
            
        if params:
            url += '?' + urllib.parse.urlencode(params)
        
        if method == 'GET':
            req = urllib.request.Request(url, headers=headers)
        elif method in ['POST', 'PATCH', 'DELETE']:
            req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, 
                                       headers=headers, method=method)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = response.read().decode('utf-8')
            return json.loads(result) if result else []
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Supabase HTTP Error: {e.code} - {error_body}")
        return None
    except Exception as e:
        print(f"Supabase Error: {str(e)}")
        return None

def supabase_get_all_tickets(filters_dict=None, max_records=5000):
    """Obtiene todos los tickets con paginación (hasta 5000 registros)"""
    all_records = []
    offset = 0
    batch_size = 1000
    
    while len(all_records) < max_records:
        batch = supabase_request(
            "tickets", 
            filters=filters_dict, 
            limit=batch_size, 
            offset=offset, 
            order="fecha.desc"
        )
        
        if not batch:
            break
            
        all_records.extend(batch)
        
        if len(batch) < batch_size:
            break
            
        offset += batch_size
        time.sleep(0.05)  # Evitar rate limiting
    
    return all_records[:max_records]

def get_ticket_full_details(ticket_id):
    """Obtiene detalles completos de un ticket incluyendo tripletas"""
    ticket = supabase_request("tickets", filters={'id': f'eq.{ticket_id}'}, single=True)
    if not ticket:
        return None
    
    # Obtener detalles normales
    detalles = supabase_request("ticket_detalles", filters={'ticket_id': f'eq.{ticket_id}'})
    
    # Obtener tripletas
    tripletas = supabase_request("ticket_tripletas", filters={'ticket_id': f'eq.{ticket_id}'})
    
    return {
        'ticket': ticket,
        'detalles': detalles or [],
        'tripletas': tripletas or []
    }

# ============================================
# RUTAS DE AUTENTICACIÓN
# ============================================

@app.route('/')
def index():
    return render_template_string(LOGIN_HTML)

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Usuario y contraseña requeridos'})
        
        # Buscar usuario
        usuarios = supabase_request("usuarios", filters={'username': f'eq.{username}'})
        
        if not usuarios or len(usuarios) == 0:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'})
        
        usuario = usuarios[0]
        
        # Verificar contraseña (en producción usar hash)
        if usuario.get('password') != password:
            return jsonify({'success': False, 'error': 'Contraseña incorrecta'})
        
        # Guardar en sesión
        session['user_id'] = usuario.get('id')
        session['username'] = usuario.get('username')
        session['rol'] = usuario.get('rol', 'vendedor')
        session['agencia_id'] = usuario.get('agencia_id')
        
        redirect_url = '/admin' if usuario.get('rol') == 'admin' else '/pos'
        
        return jsonify({
            'success': True,
            'redirect': redirect_url,
            'user': {
                'id': usuario.get('id'),
                'username': usuario.get('username'),
                'rol': usuario.get('rol'),
                'agencia_id': usuario.get('agencia_id')
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error de servidor: {str(e)}'})

@app.route('/logout')
def logout():
    session.clear()
    return render_template_string(LOGIN_HTML)

# ============================================
# RUTAS POS (VENDEDOR)
# ============================================

@app.route('/pos')
def pos():
    if 'user_id' not in session:
        return render_template_string(LOGIN_HTML)
    return render_template_string(POS_HTML, usuario=session)

@app.route('/api/animales')
def get_animales():
    return jsonify(ANIMALES)

@app.route('/api/sorteos-activos')
def get_sorteos_activos():
    try:
        ahora = ahora_peru()
        hora_actual = ahora.strftime('%H:%M')
        
        sorteos = supabase_request("sorteos", filters={'activo': 'eq.true'})
        
        if sorteos:
            for s in sorteos:
                hora_sorteo = s.get('hora', '00:00')
                s['bloqueado'] = hora_actual >= hora_sorteo
        
        return jsonify({'success': True, 'sorteos': sorteos or []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ventas-hoy')
def get_ventas_hoy():
    try:
        hoy = ahora_peru().strftime('%Y-%m-%d')
        agencia_id = session.get('agencia_id')
        vendedor_id = session.get('user_id')
        
        # Filtro por fecha usando ilike para búsqueda parcial
        filtros = {'fecha': f'ilike.{hoy}%'}
        
        if agencia_id:
            filtros['agencia_id'] = f'eq.{agencia_id}'
        if session.get('rol') == 'vendedor':
            filtros['vendedor_id'] = f'eq.{vendedor_id}'
        
        tickets = supabase_get_all_tickets(filtros, max_records=5000)
        
        total = sum(float(t.get('total', 0)) for t in tickets if t.get('estado') != 'anulado')
        cantidad = len([t for t in tickets if t.get('estado') != 'anulado'])
        
        return jsonify({
            'success': True,
            'total': total,
            'cantidad': cantidad,
            'tickets': tickets
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/guardar-ticket', methods=['POST'])
def guardar_ticket():
    try:
        data = request.get_json()
        
        # Generar código único
        codigo = f"Z{ahora_peru().strftime('%y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
        
        ticket_data = {
            'codigo': codigo,
            'vendedor_id': session.get('user_id'),
            'agencia_id': session.get('agencia_id'),
            'cliente_nombre': data.get('cliente', ''),
            'cliente_telefono': data.get('telefono', ''),
            'fecha': ahora_peru().isoformat(),
            'total': data.get('total', 0),
            'estado': 'pendiente',
            'tipo_pago': data.get('tipo_pago', 'efectivo')
        }
        
        # Crear ticket
        resultado = supabase_request("tickets", method='POST', data=ticket_data)
        
        if not resultado or len(resultado) == 0:
            return jsonify({'success': False, 'error': 'Error al crear ticket'})
        
        ticket_id = resultado[0].get('id')
        
        # Guardar detalles (jugadas normales)
        for jugada in data.get('jugadas', []):
            detalle = {
                'ticket_id': ticket_id,
                'tipo_juego': jugada.get('tipo'),
                'sorteo_id': jugada.get('sorteo_id'),
                'numero': jugada.get('numero'),
                'animal': jugada.get('animal'),
                'monto': jugada.get('monto'),
                'premio_potencial': float(jugada.get('monto', 0)) * MULTIPLICADORES.get(jugada.get('tipo'), 1)
            }
            supabase_request("ticket_detalles", method='POST', data=detalle)
        
        # Guardar tripletas
        for tripleta in data.get('tripletas', []):
            tripleta_data = {
                'ticket_id': ticket_id,
                'sorteo_id': tripleta.get('sorteo_id'),
                'animal1': tripleta.get('animal1'),
                'animal2': tripleta.get('animal2'),
                'animal3': tripleta.get('animal3'),
                'monto': tripleta.get('monto'),
                'premio_potencial': float(tripleta.get('monto', 0)) * MULTIPLICADORES['tripleta']
            }
            supabase_request("ticket_tripletas", method='POST', data=tripleta_data)
        
        return jsonify({
            'success': True,
            'ticket_id': ticket_id,
            'codigo': codigo,
            'mensaje': 'Ticket guardado correctamente'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error: {str(e)}'})

@app.route('/api/buscar-ticket')
def buscar_ticket():
    try:
        codigo = request.args.get('codigo', '').strip()
        if not codigo:
            return jsonify({'success': False, 'error': 'Código requerido'})
        
        tickets = supabase_request("tickets", filters={'codigo': f'ilike.%{codigo}%'})
        
        if not tickets or len(tickets) == 0:
            return jsonify({'success': False, 'error': 'Ticket no encontrado'})
        
        ticket = tickets[0]
        detalles_completos = get_ticket_full_details(ticket.get('id'))
        
        return jsonify({
            'success': True,
            'ticket': detalles_completos['ticket'],
            'detalles': detalles_completos['detalles'],
            'tripletas': detalles_completos['tripletas']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reimprimir-ticket', methods=['POST'])
def reimprimir_ticket():
    try:
        data = request.get_json()
        ticket_id = data.get('ticket_id')
        
        if not ticket_id:
            return jsonify({'success': False, 'error': 'ID de ticket requerido'})
        
        detalles = get_ticket_full_details(ticket_id)
        
        if not detalles:
            return jsonify({'success': False, 'error': 'Ticket no encontrado'})
        
        return jsonify({
            'success': True,
            'ticket': detalles['ticket'],
            'detalles': detalles['detalles'],
            'tripletas': detalles['tripletas'],
            'mensaje': 'Ticket listo para reimprimir'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/anular-ticket', methods=['POST'])
def anular_ticket():
    try:
        data = request.get_json()
        ticket_id = data.get('ticket_id')
        motivo = data.get('motivo', '')
        
        if not ticket_id:
            return jsonify({'success': False, 'error': 'ID de ticket requerido'})
        
        # Obtener ticket
        ticket = supabase_request("tickets", filters={'id': f'eq.{ticket_id}'}, single=True)
        
        if not ticket:
            return jsonify({'success': False, 'error': 'Ticket no encontrado'})
        
        # Verificar que no esté ya anulado
        if ticket.get('estado') == 'anulado':
            return jsonify({'success': False, 'error': 'Ticket ya está anulado'})
        
        # Verificar que no tenga premio pagado
        if ticket.get('estado') == 'pagado':
            return jsonify({'success': False, 'error': 'No se puede anular ticket con premio pagado'})
        
        # Verificar horario de sorteos (solo si aún no han cerrado)
        detalles = supabase_request("ticket_detalles", filters={'ticket_id': f'eq.{ticket_id}'})
        tripletas = supabase_request("ticket_tripletas", filters={'ticket_id': f'eq.{ticket_id}'})
        
        # Obtener sorteos únicos
        sorteos_ids = set()
        for d in detalles or []:
            if d.get('sorteo_id'):
                sorteos_ids.add(d.get('sorteo_id'))
        for t in tripletas or []:
            if t.get('sorteo_id'):
                sorteos_ids.add(t.get('sorteo_id'))
        
        # Verificar cada sorteo
        for sorteo_id in sorteos_ids:
            sorteo = supabase_request("sorteos", filters={'id': f'eq.{sorteo_id}'}, single=True)
            if sorteo:
                puede_anular, mensaje = verificar_horario_bloqueo(sorteo_id, sorteo.get('hora'))
                if not puede_anular:
                    return jsonify({'success': False, 'error': mensaje})
        
        # Anular ticket
        update_data = {
            'estado': 'anulado',
            'motivo_anulacion': motivo,
            'fecha_anulacion': ahora_peru().isoformat(),
            'anulado_por': session.get('user_id')
        }
        
        resultado = supabase_request("tickets", method='PATCH', 
                                   data=update_data,
                                   filters={'id': f'eq.{ticket_id}'})
        
        return jsonify({
            'success': True,
            'mensaje': 'Ticket anulado correctamente'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error: {str(e)}'})

# ============================================
# RUTAS ADMIN
# ============================================

@app.route('/admin')
def admin():
    if 'user_id' not in session or session.get('rol') != 'admin':
        return render_template_string(LOGIN_HTML)
    return render_template_string(ADMIN_HTML, usuario=session)

@app.route('/api/dashboard')
def get_dashboard():
    try:
        hoy = ahora_peru().strftime('%Y-%m-%d')
        
        # Tickets de hoy
        tickets_hoy = supabase_get_all_tickets({'fecha': f'ilike.{hoy}%'}, max_records=5000)
        
        ventas_hoy = sum(float(t.get('total', 0)) for t in tickets_hoy if t.get('estado') != 'anulado')
        tickets_vendidos = len([t for t in tickets_hoy if t.get('estado') != 'anulado'])
        tickets_anulados = len([t for t in tickets_hoy if t.get('estado') == 'anulado'])
        
        # Premios pendientes
        premios_pendientes = supabase_request("premios", filters={'estado': 'eq.pendiente'})
        total_premios = sum(float(p.get('monto', 0)) for p in premios_pendientes or [])
        
        # Agencias
        agencias = supabase_request("agencias")
        
        return jsonify({
            'success': True,
            'ventas_hoy': ventas_hoy,
            'tickets_vendidos': tickets_vendidos,
            'tickets_anulados': tickets_anulados,
            'premios_pendientes': total_premios,
            'cantidad_premios': len(premios_pendientes or []),
            'agencias_activas': len(agencias or [])
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reporte-historico')
def get_reporte_historico():
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        agencia_id = request.args.get('agencia_id')
        
        if not fecha_inicio or not fecha_fin:
            return jsonify({'success': False, 'error': 'Fechas requeridas'})
        
        # Convertir fechas
        try:
            fi = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            ff = datetime.strptime(fecha_fin, '%Y-%m-%d')
        except:
            return jsonify({'success': False, 'error': 'Formato de fecha inválido'})
        
        # Obtener todos los tickets y filtrar manualmente
        filtros = {}
        if agencia_id:
            filtros['agencia_id'] = f'eq.{agencia_id}'
        
        todos_tickets = supabase_get_all_tickets(filtros, max_records=5000)
        
        # Filtrar por rango de fechas
        tickets_filtrados = []
        for t in todos_tickets:
            fecha_ticket = t.get('fecha', '')
            if fecha_ticket:
                try:
                    # Parsear fecha del ticket
                    if 'T' in fecha_ticket:
                        ft = datetime.fromisoformat(fecha_ticket.replace('Z', '+00:00'))
                    elif ' ' in fecha_ticket:
                        ft = datetime.strptime(fecha_ticket.split()[0], '%Y-%m-%d')
                    else:
                        ft = datetime.fromisoformat(fecha_ticket)
                    
                    # Comparar solo la fecha (sin hora)
                    ft_date = ft.replace(hour=0, minute=0, second=0, microsecond=0)
                    if fi <= ft_date <= ff:
                        tickets_filtrados.append(t)
                except:
                    continue
        
        # Calcular totales
        total_ventas = sum(float(t.get('total', 0)) for t in tickets_filtrados if t.get('estado') != 'anulado')
        total_anulado = sum(float(t.get('total', 0)) for t in tickets_filtrados if t.get('estado') == 'anulado')
        
        # Agrupar por estado
        por_estado = {}
        for t in tickets_filtrados:
            estado = t.get('estado', 'desconocido')
            por_estado[estado] = por_estado.get(estado, 0) + 1
        
        # Agrupar por día
        por_dia = {}
        for t in tickets_filtrados:
            fecha = t.get('fecha', '')[:10]
            if fecha not in por_dia:
                por_dia[fecha] = {'ventas': 0, 'cantidad': 0}
            if t.get('estado') != 'anulado':
                por_dia[fecha]['ventas'] += float(t.get('total', 0))
                por_dia[fecha]['cantidad'] += 1
        
        return jsonify({
            'success': True,
            'total_ventas': total_ventas,
            'total_anulado': total_anulado,
            'cantidad_tickets': len(tickets_filtrados),
            'por_estado': por_estado,
            'por_dia': por_dia,
            'tickets': tickets_filtrados[:100]  # Limitar a 100 para la tabla
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reporte-ventas')
def get_reporte_ventas():
    try:
        periodo = request.args.get('periodo', 'hoy')
        agencia_id = request.args.get('agencia_id')
        
        ahora = ahora_peru()
        
        if periodo == 'hoy':
            fecha_inicio = ahora.replace(hour=0, minute=0, second=0)
            fecha_fin = ahora
        elif periodo == 'ayer':
            ayer = ahora - timedelta(days=1)
            fecha_inicio = ayer.replace(hour=0, minute=0, second=0)
            fecha_fin = ayer.replace(hour=23, minute=59, second=59)
        elif periodo == 'semana':
            fecha_inicio = (ahora - timedelta(days=7)).replace(hour=0, minute=0, second=0)
            fecha_fin = ahora
        elif periodo == 'mes':
            fecha_inicio = (ahora - timedelta(days=30)).replace(hour=0, minute=0, second=0)
            fecha_fin = ahora
        else:
            return jsonify({'success': False, 'error': 'Período no válido'})
        
        # Obtener tickets del período
        filtros = {}
        if agencia_id:
            filtros['agencia_id'] = f'eq.{agencia_id}'
        
        todos_tickets = supabase_get_all_tickets(filtros, max_records=5000)
        
        # Filtrar por fecha
        tickets_filtrados = []
        for t in todos_tickets:
            fecha_ticket = t.get('fecha', '')
            if fecha_ticket:
                try:
                    if 'T' in fecha_ticket:
                        ft = datetime.fromisoformat(fecha_ticket.replace('Z', '+00:00'))
                    else:
                        ft = datetime.fromisoformat(fecha_ticket)
                    
                    # Ajustar a zona horaria de Perú
                    ft = ft.replace(tzinfo=None) - timedelta(hours=5)
                    
                    if fecha_inicio <= ft <= fecha_fin:
                        tickets_filtrados.append(t)
                except:
                    continue
        
        # Calcular métricas
        ventas_validas = [t for t in tickets_filtrados if t.get('estado') != 'anulado']
        total_ventas = sum(float(t.get('total', 0)) for t in ventas_validas)
        
        # Agrupar por tipo de juego
        detalles_ids = [t.get('id') for t in ventas_validas]
        jugadas_por_tipo = {'directo': 0, 'combinado': 0, 'pale': 0, 'tripleta': 0}
        
        for ticket_id in detalles_ids[:100]:  # Limitar para rendimiento
            detalles = supabase_request("ticket_detalles", filters={'ticket_id': f'eq.{ticket_id}'})
            for d in detalles or []:
                tipo = d.get('tipo_juego', 'directo')
                jugadas_por_tipo[tipo] = jugadas_por_tipo.get(tipo, 0) + float(d.get('monto', 0))
        
        return jsonify({
            'success': True,
            'periodo': periodo,
            'total_ventas': total_ventas,
            'cantidad_tickets': len(ventas_validas),
            'ticket_promedio': total_ventas / len(ventas_validas) if ventas_validas else 0,
            'jugadas_por_tipo': jugadas_por_tipo,
            'tickets': tickets_filtrados[:50]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/agencias')
def get_agencias():
    try:
        agencias = supabase_request("agencias")
        return jsonify({'success': True, 'agencias': agencias or []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/usuarios')
def get_usuarios():
    try:
        agencia_id = request.args.get('agencia_id')
        filtros = {}
        if agencia_id:
            filtros['agencia_id'] = f'eq.{agencia_id}'
        
        usuarios = supabase_request("usuarios", filters=filtros if filtros else None)
        
        # Ocultar contraseñas
        for u in usuarios or []:
            u.pop('password', None)
        
        return jsonify({'success': True, 'usuarios': usuarios or []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/crear-usuario', methods=['POST'])
def crear_usuario():
    try:
        data = request.get_json()
        
        usuario_data = {
            'username': data.get('username'),
            'password': data.get('password'),  # En producción: hash
            'nombre': data.get('nombre'),
            'rol': data.get('rol', 'vendedor'),
            'agencia_id': data.get('agencia_id'),
            'telefono': data.get('telefono'),
            'activo': True
        }
        
        resultado = supabase_request("usuarios", method='POST', data=usuario_data)
        
        return jsonify({
            'success': True,
            'mensaje': 'Usuario creado correctamente',
            'usuario': resultado[0] if resultado else None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/resultados')
def get_resultados():
    try:
        fecha = request.args.get('fecha', ahora_peru().strftime('%Y-%m-%d'))
        resultados = supabase_request("resultados", filters={'fecha': f'eq.{fecha}'})
        return jsonify({'success': True, 'resultados': resultados or []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/guardar-resultado', methods=['POST'])
def guardar_resultado():
    try:
        data = request.get_json()
        
        resultado_data = {
            'sorteo_id': data.get('sorteo_id'),
            'fecha': data.get('fecha', ahora_peru().strftime('%Y-%m-%d')),
            'numero_ganador': data.get('numero'),
            'animal_ganador': ANIMALES.get(data.get('numero', '00'), 'Desconocido')
        }
        
        resultado = supabase_request("resultados", method='POST', data=resultado_data)
        
        return jsonify({
            'success': True,
            'mensaje': 'Resultado guardado correctamente',
            'resultado': resultado[0] if resultado else None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# TEMPLATES HTML
# ============================================

LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZOOLO CASINO - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 400px;
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo h1 {
            font-size: 2.5em;
            background: linear-gradient(45deg, #e94560, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
        }
        input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #e94560;
        }
        button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(45deg, #e94560, #ff6b6b);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(233, 69, 96, 0.4);
        }
        .error {
            color: #e94560;
            text-align: center;
            margin-top: 15px;
            display: none;
        }
        .version {
            text-align: center;
            margin-top: 20px;
            color: #888;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>🎰 ZOOLO</h1>
            <p>CASINO CLOUD v6.4</p>
        </div>
        <form id="loginForm">
            <div class="form-group">
                <label for="username">Usuario</label>
                <input type="text" id="username" name="username" required placeholder="Ingrese su usuario">
            </div>
            <div class="form-group">
                <label for="password">Contraseña</label>
                <input type="password" id="password" name="password" required placeholder="Ingrese su contraseña">
            </div>
            <button type="submit">Ingresar</button>
            <div class="error" id="error"></div>
        </form>
        <div class="version">Sistema de Gestión de Lotería</div>
    </div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const errorDiv = document.getElementById('error');
            errorDiv.style.display = 'none';
            
            const data = {
                username: document.getElementById('username').value,
                password: document.getElementById('password').value
            };
            
            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    window.location.href = result.redirect;
                } else {
                    errorDiv.textContent = result.error || 'Error de autenticación';
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = 'Error de conexión';
                errorDiv.style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''

POS_HTML = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZOOLO CASINO - Punto de Venta</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a;
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 3px solid #e94560;
        }
        .header h1 {
            font-size: 1.5em;
            background: linear-gradient(45deg, #e94560, #ffd700);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header-info {
            display: flex;
            gap: 20px;
            align-items: center;
        }
        .ventas-hoy {
            background: rgba(233, 69, 96, 0.2);
            padding: 10px 20px;
            border-radius: 10px;
            border: 1px solid #e94560;
        }
        .ventas-hoy span {
            display: block;
            font-size: 0.8em;
            color: #aaa;
        }
        .ventas-hoy strong {
            font-size: 1.3em;
            color: #ffd700;
        }
        .user-info {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .logout-btn {
            background: #e94560;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
        }
        
        .main-container {
            display: grid;
            grid-template-columns: 1fr 350px;
            gap: 20px;
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        /* Panel de jugadas */
        .panel-jugadas {
            background: #1a1a2e;
            border-radius: 15px;
            padding: 20px;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            background: #0f3460;
            border: none;
            color: #fff;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .tab.active {
            background: #e94560;
        }
        .tab:hover {
            background: #e94560;
        }
        
        /* Grid de animales */
        .animales-grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 10px;
            margin-bottom: 20px;
        }
        .animal-card {
            background: linear-gradient(145deg, #16213e, #0f3460);
            border: 2px solid transparent;
            border-radius: 12px;
            padding: 15px 10px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
        }
        .animal-card:hover {
            border-color: #e94560;
            transform: translateY(-3px);
        }
        .animal-card.selected {
            border-color: #ffd700;
            background: linear-gradient(145deg, #e94560, #ff6b6b);
        }
        .animal-numero {
            font-size: 1.2em;
            font-weight: bold;
            color: #ffd700;
        }
        .animal-nombre {
            font-size: 0.75em;
            color: #aaa;
            margin-top: 5px;
        }
        
        /* Formulario de jugada */
        .form-jugada {
            background: #0f3460;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
        }
        .form-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            color: #aaa;
            font-size: 0.9em;
        }
        .form-group select, .form-group input {
            width: 100%;
            padding: 12px;
            border: 2px solid #16213e;
            border-radius: 8px;
            background: #1a1a2e;
            color: #fff;
            font-size: 1em;
        }
        .btn-agregar {
            width: 100%;
            padding: 15px;
            background: linear-gradient(45deg, #28a745, #34ce57);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
        }
        
        /* Panel derecho - Ticket */
        .panel-ticket {
            background: #1a1a2e;
            border-radius: 15px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            height: calc(100vh - 100px);
            position: sticky;
            top: 20px;
        }
        .ticket-header {
            text-align: center;
            padding-bottom: 15px;
            border-bottom: 2px dashed #444;
            margin-bottom: 15px;
        }
        .ticket-header h2 {
            color: #ffd700;
            font-size: 1.3em;
        }
        .ticket-items {
            flex: 1;
            overflow-y: auto;
            margin-bottom: 15px;
        }
        .ticket-item {
            background: #0f3460;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .ticket-item-info {
            flex: 1;
        }
        .ticket-item-tipo {
            font-size: 0.75em;
            color: #aaa;
            text-transform: uppercase;
        }
        .ticket-item-detalle {
            font-weight: bold;
            color: #fff;
        }
        .ticket-item-monto {
            color: #ffd700;
            font-weight: bold;
        }
        .ticket-item-eliminar {
            background: #e94560;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 5px;
            cursor: pointer;
            margin-left: 10px;
        }
        .ticket-total {
            border-top: 2px dashed #444;
            padding-top: 15px;
            margin-bottom: 15px;
        }
        .ticket-total-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .ticket-total-final {
            font-size: 1.5em;
            color: #ffd700;
            font-weight: bold;
        }
        .ticket-actions button {
            width: 100%;
            padding: 15px;
            margin-bottom: 10px;
            border: none;
            border-radius: 8px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
        }
        .btn-guardar {
            background: linear-gradient(45deg, #28a745, #34ce57);
            color: white;
        }
        .btn-limpiar {
            background: #444;
            color: white;
        }
        .btn-buscar {
            background: #0f3460;
            color: white;
        }
        
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal.active {
            display: flex;
        }
        .modal-content {
            background: #1a1a2e;
            padding: 30px;
            border-radius: 15px;
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .modal-header h3 {
            color: #ffd700;
        }
        .modal-close {
            background: #e94560;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
        }
        
        /* Ticket de búsqueda */
        .ticket-resultado {
            background: #0f3460;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 15px;
        }
        .ticket-resultado-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #444;
        }
        .estado-pendiente { color: #ffc107; }
        .estado-pagado { color: #28a745; }
        .estado-anulado { color: #e94560; }
        .estado-por_pagar { color: #17a2b8; }
        
        .ticket-acciones {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .ticket-acciones button {
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
        }
        .btn-reimprimir {
            background: #17a2b8;
            color: white;
        }
        .btn-anular {
            background: #e94560;
            color: white;
        }
        .btn-pagar {
            background: #28a745;
            color: white;
        }
        
        /* Tripleta mode */
        .tripleta-mode .animal-card {
            position: relative;
        }
        .tripleta-mode .animal-card.selected-1::after,
        .tripleta-mode .animal-card.selected-2::after,
        .tripleta-mode .animal-card.selected-3::after {
            content: "1";
            position: absolute;
            top: -5px;
            right: -5px;
            background: #ffd700;
            color: #000;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 12px;
        }
        .tripleta-mode .animal-card.selected-2::after { content: "2"; }
        .tripleta-mode .animal-card.selected-3::after { content: "3"; }
        
        /* Tripleta display */
        .tripleta-display {
            background: linear-gradient(145deg, #16213e, #0f3460);
            border: 2px solid #ffd700;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .tripleta-animales {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 10px;
        }
        .tripleta-animal {
            text-align: center;
        }
        .tripleta-animal-numero {
            font-size: 1.5em;
            font-weight: bold;
            color: #ffd700;
        }
        .tripleta-animal-nombre {
            font-size: 0.8em;
            color: #aaa;
        }
        .tripleta-monto {
            text-align: center;
            color: #28a745;
            font-weight: bold;
        }
        
        /* Responsive */
        @media (max-width: 1024px) {
            .main-container {
                grid-template-columns: 1fr;
            }
            .panel-ticket {
                height: auto;
                position: static;
            }
            .animales-grid {
                grid-template-columns: repeat(4, 1fr);
            }
        }
        @media (max-width: 600px) {
            .animales-grid {
                grid-template-columns: repeat(3, 1fr);
            }
            .form-row {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎰 ZOOLO CASINO</h1>
        <div class="header-info">
            <div class="ventas-hoy">
                <span>Ventas Hoy</span>
                <strong id="ventasHoy">S/ 0.00</strong>
            </div>
            <div class="user-info">
                <span>{{ usuario.username }}</span>
                <button class="logout-btn" onclick="logout()">Salir</button>
            </div>
        </div>
    </div>
    
    <div class="main-container">
        <div class="panel-jugadas">
            <div class="tabs">
                <button class="tab active" onclick="setModo('directo')">Directo</button>
                <button class="tab" onclick="setModo('combinado')">Combinado</button>
                <button class="tab" onclick="setModo('pale')">Pale</button>
                <button class="tab" onclick="toggleTripleta()">Tripleta</button>
            </div>
            
            <div id="tripletaDisplay" class="tripleta-display" style="display:none;">
                <div class="tripleta-animales">
                    <div class="tripleta-animal">
                        <div class="tripleta-animal-numero" id="triAn1">-</div>
                        <div class="tripleta-animal-nombre" id="triNom1">Animal 1</div>
                    </div>
                    <div style="font-size: 2em; color: #ffd700;">+</div>
                    <div class="tripleta-animal">
                        <div class="tripleta-animal-numero" id="triAn2">-</div>
                        <div class="tripleta-animal-nombre" id="triNom2">Animal 2</div>
                    </div>
                    <div style="font-size: 2em; color: #ffd700;">+</div>
                    <div class="tripleta-animal">
                        <div class="tripleta-animal-numero" id="triAn3">-</div>
                        <div class="tripleta-animal-nombre" id="triNom3">Animal 3</div>
                    </div>
                </div>
                <div class="tripleta-monto">
                    Monto: S/ <input type="number" id="tripletaMonto" placeholder="0.00" step="0.1" style="width: 100px; padding: 5px;">
                </div>
                <button class="btn-agregar" onclick="agregarTripleta()" style="margin-top: 10px;">Agregar Tripleta</button>
            </div>
            
            <div class="form-jugada" id="formNormal">
                <div class="form-row">
                    <div class="form-group">
                        <label>Sorteo</label>
                        <select id="sorteoSelect"></select>
                    </div>
                    <div class="form-group">
                        <label>Número (00-41)</label>
                        <input type="text" id="numeroInput" maxlength="2" placeholder="00">
                    </div>
                    <div class="form-group">
                        <label>Animal</label>
                        <input type="text" id="animalInput" readonly placeholder="Seleccione animal">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Tipo</label>
                        <select id="tipoSelect">
                            <option value="directo">Directo (x35)</option>
                            <option value="combinado">Combinado (x70)</option>
                            <option value="pale">Pale (x2)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Monto S/</label>
                        <input type="number" id="montoInput" step="0.1" placeholder="0.00">
                    </div>
                    <div class="form-group">
                        <label>Premio Potencial</label>
                        <input type="text" id="premioInput" readonly value="S/ 0.00">
                    </div>
                </div>
                <button class="btn-agregar" onclick="agregarJugada()">Agregar Jugada</button>
            </div>
            
            <div class="animales-grid" id="animalesGrid"></div>
        </div>
        
        <div class="panel-ticket">
            <div class="ticket-header">
                <h2>🎫 TICKET</h2>
                <input type="text" id="clienteNombre" placeholder="Nombre del cliente" style="width: 100%; margin-top: 10px; padding: 8px; border-radius: 5px; border: 1px solid #444; background: #0f3460; color: #fff;">
                <input type="tel" id="clienteTelefono" placeholder="Teléfono (WhatsApp)" style="width: 100%; margin-top: 5px; padding: 8px; border-radius: 5px; border: 1px solid #444; background: #0f3460; color: #fff;">
            </div>
            
            <div class="ticket-items" id="ticketItems">
                <p style="text-align: center; color: #666; padding: 20px;">No hay jugadas</p>
            </div>
            
            <div class="ticket-total">
                <div class="ticket-total-row">
                    <span>Subtotal:</span>
                    <span id="subtotal">S/ 0.00</span>
                </div>
                <div class="ticket-total-row ticket-total-final">
                    <span>TOTAL:</span>
                    <span id="totalTicket">S/ 0.00</span>
                </div>
            </div>
            
            <div class="ticket-actions">
                <button class="btn-guardar" onclick="guardarTicket()">💾 Guardar Ticket</button>
                <button class="btn-buscar" onclick="abrirBuscarTicket()">🔍 Buscar Ticket</button>
                <button class="btn-limpiar" onclick="limpiarTicket()">🗑️ Limpiar</button>
            </div>
        </div>
    </div>
    
    <!-- Modal Buscar Ticket -->
    <div class="modal" id="modalBuscar">
        <div class="modal-content">
            <div class="modal-header">
                <h3>🔍 Buscar Ticket</h3>
                <button class="modal-close" onclick="cerrarModal('modalBuscar')">✕</button>
            </div>
            <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                <input type="text" id="buscarCodigo" placeholder="Ingrese código del ticket" style="flex: 1; padding: 12px; border-radius: 8px; border: 2px solid #444; background: #0f3460; color: #fff;">
                <button onclick="buscarTicket()" style="padding: 12px 20px; background: #e94560; color: white; border: none; border-radius: 8px; cursor: pointer;">Buscar</button>
            </div>
            <div id="resultadoBusqueda"></div>
        </div>
    </div>
    
    <!-- Modal Ticket Encontrado -->
    <div class="modal" id="modalTicket">
        <div class="modal-content" style="max-width: 500px;">
            <div class="modal-header">
                <h3>📋 Detalle del Ticket</h3>
                <button class="modal-close" onclick="cerrarModal('modalTicket')">✕</button>
            </div>
            <div id="detalleTicketCompleto"></div>
        </div>
    </div>
    
    <script>
        let animales = {};
        let jugadas = [];
        let tripletas = [];
        let modoTripleta = false;
        let tripletaSeleccion = [];
        let sorteos = [];
        let modoActual = 'directo';
        
        // Cargar datos iniciales
        async function init() {
            await cargarAnimales();
            await cargarSorteos();
            await actualizarVentasHoy();
            renderizarAnimales();
            setInterval(actualizarVentasHoy, 30000);
        }
        
        async function cargarAnimales() {
            const response = await fetch('/api/animales');
            const result = await response.json();
            animales = result;
        }
        
        async function cargarSorteos() {
            const response = await fetch('/api/sorteos-activos');
            const result = await response.json();
            if (result.success) {
                sorteos = result.sorteos;
                const select = document.getElementById('sorteoSelect');
                select.innerHTML = sorteos.map(s => 
                    `<option value="${s.id}" ${s.bloqueado ? 'disabled' : ''}>${s.nombre} ${s.bloqueado ? '(CERRADO)' : ''}</option>`
                ).join('');
            }
        }
        
        async function actualizarVentasHoy() {
            const response = await fetch('/api/ventas-hoy');
            const result = await response.json();
            if (result.success) {
                document.getElementById('ventasHoy').textContent = 'S/ ' + formatearMonto(result.total);
            }
        }
        
        function formatearMonto(monto) {
            let montoNum = parseFloat(monto);
            if (isNaN(montoNum)) return '0';
            if (montoNum === Math.floor(montoNum)) {
                return montoNum.toString();
            }
            return montoNum.toFixed(1);
        }
        
        function renderizarAnimales() {
            const grid = document.getElementById('animalesGrid');
            grid.innerHTML = '';
            for (let i = 0; i <= 41; i++) {
                const num = i.toString().padStart(2, '0');
                const animal = animales[num] || 'Desconocido';
                const card = document.createElement('div');
                card.className = 'animal-card';
                card.dataset.numero = num;
                card.innerHTML = `
                    <div class="animal-numero">${num}</div>
                    <div class="animal-nombre">${animal}</div>
                `;
                card.onclick = () => seleccionarAnimal(num, animal);
                grid.appendChild(card);
            }
        }
        
        function seleccionarAnimal(numero, nombre) {
            if (modoTripleta) {
                manejarSeleccionTripleta(numero, nombre);
                return;
            }
            
            document.getElementById('numeroInput').value = numero;
            document.getElementById('animalInput').value = nombre;
            
            document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('selected'));
            document.querySelector(`.animal-card[data-numero="${numero}"]`).classList.add('selected');
            
            calcularPremio();
        }
        
        function toggleTripleta() {
            modoTripleta = !modoTripleta;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            if (modoTripleta) {
                document.querySelector('.tab:last-child').classList.add('active');
                document.getElementById('formNormal').style.display = 'none';
                document.getElementById('tripletaDisplay').style.display = 'block';
                document.body.classList.add('tripleta-mode');
            } else {
                document.querySelector('.tab:first-child').classList.add('active');
                document.getElementById('formNormal').style.display = 'block';
                document.getElementById('tripletaDisplay').style.display = 'none';
                document.body.classList.remove('tripleta-mode');
                tripletaSeleccion = [];
                actualizarDisplayTripleta();
            }
        }
        
        function manejarSeleccionTripleta(numero, nombre) {
            const idx = tripletaSeleccion.findIndex(t => t.numero === numero);
            if (idx >= 0) {
                tripletaSeleccion.splice(idx, 1);
            } else if (tripletaSeleccion.length < 3) {
                tripletaSeleccion.push({ numero, nombre });
            }
            
            document.querySelectorAll('.animal-card').forEach(c => {
                c.classList.remove('selected-1', 'selected-2', 'selected-3');
            });
            
            tripletaSeleccion.forEach((t, i) => {
                const card = document.querySelector(`.animal-card[data-numero="${t.numero}"]`);
                if (card) card.classList.add(`selected-${i + 1}`);
            });
            
            actualizarDisplayTripleta();
        }
        
        function actualizarDisplayTripleta() {
            for (let i = 0; i < 3; i++) {
                const an = document.getElementById(`triAn${i + 1}`);
                const nom = document.getElementById(`triNom${i + 1}`);
                if (tripletaSeleccion[i]) {
                    an.textContent = tripletaSeleccion[i].numero;
                    nom.textContent = tripletaSeleccion[i].nombre;
                } else {
                    an.textContent = '-';
                    nom.textContent = `Animal ${i + 1}`;
                }
            }
        }
        
        function setModo(modo) {
            modoActual = modo;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tipoSelect').value = modo;
            calcularPremio();
        }
        
        function calcularPremio() {
            const monto = parseFloat(document.getElementById('montoInput').value) || 0;
            const tipo = document.getElementById('tipoSelect').value;
            const multiplicadores = { directo: 35, combinado: 70, pale: 2 };
            const premio = monto * multiplicadores[tipo];
            document.getElementById('premioInput').value = 'S/ ' + formatearMonto(premio);
        }
        
        document.getElementById('montoInput').addEventListener('input', calcularPremio);
        document.getElementById('tipoSelect').addEventListener('change', calcularPremio);
        
        function agregarJugada() {
            const sorteoId = document.getElementById('sorteoSelect').value;
            const sorteo = sorteos.find(s => s.id == sorteoId);
            if (sorteo && sorteo.bloqueado) {
                alert('Este sorteo ya está cerrado');
                return;
            }
            
            const numero = document.getElementById('numeroInput').value;
            const animal = document.getElementById('animalInput').value;
            const tipo = document.getElementById('tipoSelect').value;
            const monto = parseFloat(document.getElementById('montoInput').value);
            
            if (!numero || !monto || monto <= 0) {
                alert('Ingrese número y monto válido');
                return;
            }
            
            const multiplicadores = { directo: 35, combinado: 70, pale: 2 };
            const jugada = {
                id: Date.now(),
                tipo,
                sorteo_id: sorteoId,
                sorteo_nombre: sorteo ? sorteo.nombre : '',
                numero,
                animal,
                monto,
                premio: monto * multiplicadores[tipo]
            };
            
            jugadas.push(jugada);
            renderizarTicket();
            
            // Limpiar selección
            document.getElementById('numeroInput').value = '';
            document.getElementById('animalInput').value = '';
            document.querySelectorAll('.animal-card').forEach(c => c.classList.remove('selected'));
        }
        
        function agregarTripleta() {
            if (tripletaSeleccion.length !== 3) {
                alert('Seleccione exactamente 3 animales');
                return;
            }
            
            const sorteoId = document.getElementById('sorteoSelect').value;
            const sorteo = sorteos.find(s => s.id == sorteoId);
            if (sorteo && sorteo.bloqueado) {
                alert('Este sorteo ya está cerrado');
                return;
            }
            
            const monto = parseFloat(document.getElementById('tripletaMonto').value);
            if (!monto || monto <= 0) {
                alert('Ingrese monto válido');
                return;
            }
            
            const tripleta = {
                id: Date.now(),
                tipo: 'tripleta',
                sorteo_id: sorteoId,
                sorteo_nombre: sorteo ? sorteo.nombre : '',
                animal1: tripletaSeleccion[0].numero,
                animal2: tripletaSeleccion[1].numero,
                animal3: tripletaSeleccion[2].numero,
                nombres: [
                    tripletaSeleccion[0].nombre,
                    tripletaSeleccion[1].nombre,
                    tripletaSeleccion[2].nombre
                ],
                monto,
                premio: monto * 60
            };
            
            tripletas.push(tripleta);
            
            // Limpiar
            tripletaSeleccion = [];
            document.getElementById('tripletaMonto').value = '';
            document.querySelectorAll('.animal-card').forEach(c => {
                c.classList.remove('selected-1', 'selected-2', 'selected-3');
            });
            actualizarDisplayTripleta();
            
            renderizarTicket();
        }
        
        function renderizarTicket() {
            const container = document.getElementById('ticketItems');
            
            if (jugadas.length === 0 && tripletas.length === 0) {
                container.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">No hay jugadas</p>';
            } else {
                container.innerHTML = '';
                
                jugadas.forEach(j => {
                    const item = document.createElement('div');
                    item.className = 'ticket-item';
                    item.innerHTML = `
                        <div class="ticket-item-info">
                            <div class="ticket-item-tipo">${j.tipo.toUpperCase()} - ${j.sorteo_nombre}</div>
                            <div class="ticket-item-detalle">#${j.numero} ${j.animal}</div>
                        </div>
                        <div>
                            <div class="ticket-item-monto">S/ ${formatearMonto(j.monto)}</div>
                            <div style="font-size: 0.75em; color: #28a745;">Premio: S/ ${formatearMonto(j.premio)}</div>
                        </div>
                        <button class="ticket-item-eliminar" onclick="eliminarJugada(${j.id})">✕</button>
                    `;
                    container.appendChild(item);
                });
                
                tripletas.forEach(t => {
                    const item = document.createElement('div');
                    item.className = 'ticket-item';
                    item.style.border = '2px solid #ffd700';
                    item.innerHTML = `
                        <div class="ticket-item-info">
                            <div class="ticket-item-tipo">TRIPLETA - ${t.sorteo_nombre}</div>
                            <div class="ticket-item-detalle">
                                #${t.animal1} + #${t.animal2} + #${t.animal3}
                            </div>
                        </div>
                        <div>
                            <div class="ticket-item-monto">S/ ${formatearMonto(t.monto)}</div>
                            <div style="font-size: 0.75em; color: #28a745;">Premio: S/ ${formatearMonto(t.premio)}</div>
                        </div>
                        <button class="ticket-item-eliminar" onclick="eliminarTripleta(${t.id})">✕</button>
                    `;
                    container.appendChild(item);
                });
            }
            
            calcularTotal();
        }
        
        function eliminarJugada(id) {
            jugadas = jugadas.filter(j => j.id !== id);
            renderizarTicket();
        }
        
        function eliminarTripleta(id) {
            tripletas = tripletas.filter(t => t.id !== id);
            renderizarTicket();
        }
        
        function calcularTotal() {
            const totalJugadas = jugadas.reduce((sum, j) => sum + j.monto, 0);
            const totalTripletas = tripletas.reduce((sum, t) => sum + t.monto, 0);
            const total = totalJugadas + totalTripletas;
            
            document.getElementById('subtotal').textContent = 'S/ ' + formatearMonto(total);
            document.getElementById('totalTicket').textContent = 'S/ ' + formatearMonto(total);
        }
        
        async function guardarTicket() {
            if (jugadas.length === 0 && tripletas.length === 0) {
                alert('Agregue al menos una jugada');
                return;
            }
            
            const data = {
                cliente: document.getElementById('clienteNombre').value,
                telefono: document.getElementById('clienteTelefono').value,
                jugadas: jugadas,
                tripletas: tripletas,
                total: parseFloat(document.getElementById('totalTicket').textContent.replace('S/ ', '')),
                tipo_pago: 'efectivo'
            };
            
            try {
                const response = await fetch('/api/guardar-ticket', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    alert(`Ticket guardado!\\nCódigo: ${result.codigo}`);
                    
                    // Compartir por WhatsApp si hay teléfono
                    if (data.telefono) {
                        const mensaje = encodeURIComponent(\`🎰 *ZOOLO CASINO* 🎰\\n\\nTicket: \${result.codigo}\\nCliente: \${data.cliente || 'Sin nombre'}\\nTotal: S/ \${formatearMonto(data.total)}\\n\\n¡Gracias por jugar!\`);
                        window.open(\`https://wa.me/51\${data.telefono}?text=\${mensaje}\`, '_blank');
                    }
                    
                    limpiarTicket();
                    actualizarVentasHoy();
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                alert('Error de conexión');
            }
        }
        
        function limpiarTicket() {
            jugadas = [];
            tripletas = [];
            tripletaSeleccion = [];
            document.getElementById('clienteNombre').value = '';
            document.getElementById('clienteTelefono').value = '';
            document.getElementById('numeroInput').value = '';
            document.getElementById('animalInput').value = '';
            document.getElementById('montoInput').value = '';
            document.getElementById('tripletaMonto').value = '';
            document.querySelectorAll('.animal-card').forEach(c => {
                c.classList.remove('selected', 'selected-1', 'selected-2', 'selected-3');
            });
            actualizarDisplayTripleta();
            renderizarTicket();
        }
        
        function abrirBuscarTicket() {
            document.getElementById('modalBuscar').classList.add('active');
            document.getElementById('buscarCodigo').focus();
        }
        
        function cerrarModal(modalId) {
            document.getElementById(modalId).classList.remove('active');
        }
        
        async function buscarTicket() {
            const codigo = document.getElementById('buscarCodigo').value.trim();
            if (!codigo) return;
            
            try {
                const response = await fetch('/api/buscar-ticket?codigo=' + encodeURIComponent(codigo));
                const result = await response.json();
                
                const container = document.getElementById('resultadoBusqueda');
                
                if (result.success) {
                    const t = result.ticket;
                    const estadoClass = {
                        'pendiente': 'estado-pendiente',
                        'pagado': 'estado-pagado',
                        'anulado': 'estado-anulado',
                        'por_pagar': 'estado-por_pagar'
                    }[t.estado] || 'estado-pendiente';
                    
                    let detallesHtml = '';
                    
                    // Mostrar jugadas normales
                    if (result.detalles && result.detalles.length > 0) {
                        detallesHtml += '<h4 style="color: #ffd700; margin: 15px 0 10px;">Jugadas:</h4>';
                        result.detalles.forEach(d => {
                            detallesHtml += \`
                                <div style="background: #16213e; padding: 10px; border-radius: 5px; margin-bottom: 5px;">
                                    <strong>\${d.tipo_juego.toUpperCase()}</strong> - 
                                    #\${d.numero} \${d.animal || ''} - 
                                    S/ \${formatearMonto(d.monto)}
                                </div>
                            \`;
                        });
                    }
                    
                    // Mostrar tripletas con detalle completo
                    if (result.tripletas && result.tripletas.length > 0) {
                        detallesHtml += '<h4 style="color: #ffd700; margin: 15px 0 10px;">Tripletas:</h4>';
                        result.tripletas.forEach(tr => {
                            detallesHtml += \`
                                <div style="background: linear-gradient(145deg, #16213e, #0f3460); border: 2px solid #ffd700; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                                    <div style="display: flex; justify-content: center; gap: 15px; margin-bottom: 10px;">
                                        <div style="text-align: center;">
                                            <div style="font-size: 1.3em; font-weight: bold; color: #ffd700;">#\${tr.animal1}</div>
                                            <div style="font-size: 0.75em; color: #aaa;">\${animales[tr.animal1] || ''}</div>
                                        </div>
                                        <div style="color: #ffd700;">+</div>
                                        <div style="text-align: center;">
                                            <div style="font-size: 1.3em; font-weight: bold; color: #ffd700;">#\${tr.animal2}</div>
                                            <div style="font-size: 0.75em; color: #aaa;">\${animales[tr.animal2] || ''}</div>
                                        </div>
                                        <div style="color: #ffd700;">+</div>
                                        <div style="text-align: center;">
                                            <div style="font-size: 1.3em; font-weight: bold; color: #ffd700;">#\${tr.animal3}</div>
                                            <div style="font-size: 0.75em; color: #aaa;">\${animales[tr.animal3] || ''}</div>
                                        </div>
                                    </div>
                                    <div style="text-align: center; color: #28a745; font-weight: bold;">
                                        Monto: S/ \${formatearMonto(tr.monto)} | Premio: S/ \${formatearMonto(tr.premio_potencial)}
                                    </div>
                                </div>
                            \`;
                        });
                    }
                    
                    container.innerHTML = \`
                        <div class="ticket-resultado">
                            <div class="ticket-resultado-header">
                                <div>
                                    <strong style="font-size: 1.2em;">🎫 \${t.codigo}</strong><br>
                                    <small>\${new Date(t.fecha).toLocaleString()}</small>
                                </div>
                                <div class="\${estadoClass}" style="font-weight: bold; text-transform: uppercase;">
                                    \${t.estado}
                                </div>
                            </div>
                            <div style="margin-bottom: 10px;">
                                <strong>Cliente:</strong> \${t.cliente_nombre || 'Sin nombre'}<br>
                                <strong>Teléfono:</strong> \${t.cliente_telefono || '-'}
                            </div>
                            \${detallesHtml}
                            <div style="border-top: 2px dashed #444; margin-top: 15px; padding-top: 15px;">
                                <div style="display: flex; justify-content: space-between; font-size: 1.2em;">
                                    <strong>TOTAL:</strong>
                                    <strong style="color: #ffd700;">S/ \${formatearMonto(t.total)}</strong>
                                </div>
                            </div>
                            <div class="ticket-acciones">
                                <button class="btn-reimprimir" onclick="reimprimirTicket('\${t.id}')">🖨️ Reimprimir</button>
                                \${t.estado === 'pendiente' ? \`<button class="btn-anular" onclick="anularTicket('\${t.id}')'>🚫 Anular</button>\` : ''}
                                \${t.estado === 'por_pagar' ? \`<button class="btn-pagar" onclick="pagarTicket('\${t.id}')'>💰 Pagar</button>\` : ''}
                            </div>
                        </div>
                    \`;
                } else {
                    container.innerHTML = '<p style="color: #e94560; text-align: center;">' + result.error + '</p>';
                }
            } catch (error) {
                alert('Error de búsqueda');
            }
        }
        
        async function reimprimirTicket(ticketId) {
            try {
                const response = await fetch('/api/reimprimir-ticket', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ticket_id: ticketId })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    const t = result.ticket;
                    let mensaje = \`🎰 *ZOOLO CASINO* 🎰\\n\\n*Ticket Reimpreso*\\nCódigo: \${t.codigo}\\nFecha: \${new Date(t.fecha).toLocaleString()}\\nCliente: \${t.cliente_nombre || 'Sin nombre'}\\nTotal: S/ \${formatearMonto(t.total)}\\n\\n¡Gracias por jugar!\`;
                    
                    if (t.cliente_telefono) {
                        window.open(\`https://wa.me/51\${t.cliente_telefono}?text=\${encodeURIComponent(mensaje)}\`, '_blank');
                    } else {
                        alert('Ticket listo para reimprimir\\n\\n' + mensaje);
                    }
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                alert('Error al reimprimir');
            }
        }
        
        async function anularTicket(ticketId) {
            const motivo = prompt('Motivo de anulación:');
            if (!motivo) return;
            
            try {
                const response = await fetch('/api/anular-ticket', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ticket_id: ticketId, motivo: motivo })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    alert('Ticket anulado correctamente');
                    cerrarModal('modalBuscar');
                    actualizarVentasHoy();
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                alert('Error al anular');
            }
        }
        
        function logout() {
            window.location.href = '/logout';
        }
        
        // Inicializar
        init();
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
    <title>ZOOLO CASINO - Panel de Administración</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a;
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 3px solid #e94560;
        }
        .header h1 {
            font-size: 1.5em;
            background: linear-gradient(45deg, #e94560, #ffd700);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .user-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .logout-btn {
            background: #e94560;
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 5px;
            cursor: pointer;
        }
        
        .sidebar {
            position: fixed;
            left: 0;
            top: 70px;
            width: 250px;
            height: calc(100vh - 70px);
            background: #1a1a2e;
            border-right: 1px solid #333;
            overflow-y: auto;
        }
        .nav-item {
            padding: 15px 20px;
            cursor: pointer;
            border-bottom: 1px solid #333;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .nav-item:hover, .nav-item.active {
            background: #e94560;
        }
        
        .main-content {
            margin-left: 250px;
            padding: 20px;
            min-height: calc(100vh - 70px);
        }
        
        .section {
            display: none;
        }
        .section.active {
            display: block;
        }
        
        /* Dashboard Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(145deg, #16213e, #0f3460);
            padding: 25px;
            border-radius: 15px;
            border: 1px solid #333;
        }
        .stat-card h3 {
            color: #aaa;
            font-size: 0.9em;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        .stat-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #ffd700;
        }
        .stat-card.positive .value { color: #28a745; }
        .stat-card.negative .value { color: #e94560; }
        
        /* Tablas */
        .table-container {
            background: #1a1a2e;
            border-radius: 15px;
            overflow: hidden;
            margin-bottom: 20px;
        }
        .table-header {
            background: #0f3460;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .table-header h3 {
            color: #ffd700;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #333;
        }
        th {
            background: #16213e;
            color: #ffd700;
            font-weight: 600;
        }
        tr:hover {
            background: rgba(233, 69, 96, 0.1);
        }
        .estado-pendiente { color: #ffc107; }
        .estado-pagado { color: #28a745; }
        .estado-anulado { color: #e94560; text-decoration: line-through; }
        .estado-por_pagar { color: #17a2b8; }
        
        /* Filtros */
        .filters {
            background: #0f3460;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: end;
        }
        .filter-group label {
            display: block;
            margin-bottom: 5px;
            color: #aaa;
            font-size: 0.85em;
        }
        .filter-group input, .filter-group select {
            padding: 10px 15px;
            border: 1px solid #444;
            border-radius: 8px;
            background: #1a1a2e;
            color: #fff;
        }
        .btn-filter {
            padding: 10px 25px;
            background: #e94560;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
        }
        .btn-export {
            padding: 10px 25px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
        }
        
        /* Formularios */
        .form-section {
            background: #1a1a2e;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
        }
        .form-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            color: #aaa;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 12px;
            border: 1px solid #444;
            border-radius: 8px;
            background: #0f3460;
            color: #fff;
        }
        .btn-primary {
            padding: 12px 30px;
            background: linear-gradient(45deg, #e94560, #ff6b6b);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .sidebar {
                width: 100%;
                position: relative;
                top: 0;
                height: auto;
            }
            .main-content {
                margin-left: 0;
            }
            .stats-grid {
                grid-template-columns: 1fr;
            }
        }
        
        /* Loading */
        .loading {
            text-align: center;
            padding: 40px;
            color: #aaa;
        }
        
        /* Badges */
        .badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 600;
        }
        .badge-success { background: #28a745; color: white; }
        .badge-warning { background: #ffc107; color: #000; }
        .badge-danger { background: #e94560; color: white; }
        .badge-info { background: #17a2b8; color: white; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎰 ZOOLO CASINO - Admin</h1>
        <div class="user-info">
            <span>{{ usuario.username }}</span>
            <button class="logout-btn" onclick="logout()">Salir</button>
        </div>
    </div>
    
    <div class="sidebar">
        <div class="nav-item active" onclick="showSection('dashboard')">📊 Dashboard</div>
        <div class="nav-item" onclick="showSection('resultados')">🏆 Resultados</div>
        <div class="nav-item" onclick="showSection('riesgo')">⚠️ Control de Riesgo</div>
        <div class="nav-item" onclick="showSection('tripletas')">🎲 Tripletas</div>
        <div class="nav-item" onclick="showSection('reporte')">📈 Reporte de Ventas</div>
        <div class="nav-item" onclick="showSection('historico')">📜 Histórico</div>
        <div class="nav-item" onclick="showSection('agencias')">🏢 Agencias</div>
        <div class="nav-item" onclick="showSection('usuarios')">👥 Usuarios</div>
    </div>
    
    <div class="main-content">
        <!-- Dashboard -->
        <div class="section active" id="dashboard">
            <h2 style="margin-bottom: 20px; color: #ffd700;">Dashboard</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Ventas Hoy</h3>
                    <div class="value" id="dashVentas">S/ 0.00</div>
                </div>
                <div class="stat-card">
                    <h3>Tickets Vendidos</h3>
                    <div class="value" id="dashTickets">0</div>
                </div>
                <div class="stat-card negative">
                    <h3>Tickets Anulados</h3>
                    <div class="value" id="dashAnulados">0</div>
                </div>
                <div class="stat-card positive">
                    <h3>Premios Pendientes</h3>
                    <div class="value" id="dashPremios">S/ 0.00</div>
                </div>
            </div>
        </div>
        
        <!-- Resultados -->
        <div class="section" id="resultados">
            <h2 style="margin-bottom: 20px; color: #ffd700;">Registrar Resultados</h2>
            <div class="form-section">
                <div class="form-row">
                    <div class="form-group">
                        <label>Sorteo</label>
                        <select id="resSorteo"></select>
                    </div>
                    <div class="form-group">
                        <label>Fecha</label>
                        <input type="date" id="resFecha">
                    </div>
                    <div class="form-group">
                        <label>Número Ganador (00-41)</label>
                        <input type="text" id="resNumero" maxlength="2" placeholder="00">
                    </div>
                </div>
                <button class="btn-primary" onclick="guardarResultado()">Guardar Resultado</button>
            </div>
            <div class="table-container">
                <div class="table-header">
                    <h3>Resultados Recientes</h3>
                </div>
                <table id="tablaResultados">
                    <thead>
                        <tr>
                            <th>Fecha</th>
                            <th>Sorteo</th>
                            <th>Número</th>
                            <th>Animal</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        <!-- Control de Riesgo -->
        <div class="section" id="riesgo">
            <h2 style="margin-bottom: 20px; color: #ffd700;">Control de Riesgo</h2>
            <div class="filters">
                <div class="filter-group">
                    <label>Sorteo</label>
                    <select id="riesgoSorteo"></select>
                </div>
                <div class="filter-group">
                    <label>Fecha</label>
                    <input type="date" id="riesgoFecha">
                </div>
                <button class="btn-filter" onclick="cargarRiesgo()">Consultar</button>
            </div>
            <div class="table-container">
                <div class="table-header">
                    <h3>Exposición por Número</h3>
                </div>
                <table id="tablaRiesgo">
                    <thead>
                        <tr>
                            <th>Número</th>
                            <th>Animal</th>
                            <th>Total Apostado</th>
                            <th>Premio Potencial</th>
                            <th>Riesgo</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        <!-- Tripletas -->
        <div class="section" id="tripletas">
            <h2 style="margin-bottom: 20px; color: #ffd700;">Control de Tripletas</h2>
            <div class="filters">
                <div class="filter-group">
                    <label>Sorteo</label>
                    <select id="tripletaSorteo"></select>
                </div>
                <div class="filter-group">
                    <label>Fecha</label>
                    <input type="date" id="tripletaFecha">
                </div>
                <button class="btn-filter" onclick="cargarTripletas()">Consultar</button>
            </div>
            <div class="table-container">
                <div class="table-header">
                    <h3>Tripletas Jugadas</h3>
                </div>
                <table id="tablaTripletas">
                    <thead>
                        <tr>
                            <th>Combinación</th>
                            <th>Animales</th>
                            <th>Total Apostado</th>
                            <th>Veces Jugada</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        <!-- Reporte de Ventas -->
        <div class="section" id="reporte">
            <h2 style="margin-bottom: 20px; color: #ffd700;">Reporte de Ventas</h2>
            <div class="filters">
                <div class="filter-group">
                    <label>Período</label>
                    <select id="repPeriodo" onchange="cargarReporte()">
                        <option value="hoy">Hoy</option>
                        <option value="ayer">Ayer</option>
                        <option value="semana">Últimos 7 días</option>
                        <option value="mes">Últimos 30 días</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Agencia</label>
                    <select id="repAgencia">
                        <option value="">Todas</option>
                    </select>
                </div>
                <button class="btn-filter" onclick="cargarReporte()">Generar</button>
                <button class="btn-export" onclick="exportarReporte()">📥 Exportar</button>
            </div>
            <div class="stats-grid" id="resumenReporte" style="display:none;">
                <div class="stat-card">
                    <h3>Total Ventas</h3>
                    <div class="value" id="repTotal">S/ 0.00</div>
                </div>
                <div class="stat-card">
                    <h3>Tickets</h3>
                    <div class="value" id="repTickets">0</div>
                </div>
                <div class="stat-card">
                    <h3>Ticket Promedio</h3>
                    <div class="value" id="repPromedio">S/ 0.00</div>
                </div>
            </div>
            <div class="table-container">
                <div class="table-header">
                    <h3>Detalle de Tickets</h3>
                </div>
                <table id="tablaReporte">
                    <thead>
                        <tr>
                            <th>Código</th>
                            <th>Fecha</th>
                            <th>Cliente</th>
                            <th>Total</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        <!-- Histórico -->
        <div class="section" id="historico">
            <h2 style="margin-bottom: 20px; color: #ffd700;">Histórico de Tickets</h2>
            <div class="filters">
                <div class="filter-group">
                    <label>Desde</label>
                    <input type="date" id="histDesde">
                </div>
                <div class="filter-group">
                    <label>Hasta</label>
                    <input type="date" id="histHasta">
                </div>
                <div class="filter-group">
                    <label>Agencia</label>
                    <select id="histAgencia">
                        <option value="">Todas</option>
                    </select>
                </div>
                <button class="btn-filter" onclick="cargarHistorico()">Buscar</button>
                <button class="btn-export" onclick="exportarHistorico()">📥 Exportar</button>
            </div>
            <div id="resumenHistorico" style="background: #0f3460; padding: 20px; border-radius: 10px; margin-bottom: 20px; display:none;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px;">
                    <div>
                        <small style="color: #aaa;">Total Ventas</small>
                        <div style="font-size: 1.5em; color: #28a745; font-weight: bold;" id="histTotalVentas">S/ 0.00</div>
                    </div>
                    <div>
                        <small style="color: #aaa;">Total Anulado</small>
                        <div style="font-size: 1.5em; color: #e94560; font-weight: bold;" id="histTotalAnulado">S/ 0.00</div>
                    </div>
                    <div>
                        <small style="color: #aaa;">Cantidad Tickets</small>
                        <div style="font-size: 1.5em; color: #ffd700; font-weight: bold;" id="histCantidad">0</div>
                    </div>
                </div>
            </div>
            <div class="table-container">
                <div class="table-header">
                    <h3>Tickets</h3>
                </div>
                <table id="tablaHistorico">
                    <thead>
                        <tr>
                            <th>Código</th>
                            <th>Fecha</th>
                            <th>Agencia</th>
                            <th>Vendedor</th>
                            <th>Cliente</th>
                            <th>Total</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        <!-- Agencias -->
        <div class="section" id="agencias">
            <h2 style="margin-bottom: 20px; color: #ffd700;">Gestión de Agencias</h2>
            <div class="form-section">
                <h3 style="margin-bottom: 15px; color: #ffd700;">Nueva Agencia</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Nombre</label>
                        <input type="text" id="agnNombre" placeholder="Nombre de la agencia">
                    </div>
                    <div class="form-group">
                        <label>Dirección</label>
                        <input type="text" id="agnDireccion" placeholder="Dirección">
                    </div>
                    <div class="form-group">
                        <label>Teléfono</label>
                        <input type="tel" id="agnTelefono" placeholder="Teléfono">
                    </div>
                </div>
                <button class="btn-primary" onclick="crearAgencia()">Crear Agencia</button>
            </div>
            <div class="table-container">
                <div class="table-header">
                    <h3>Agencias Registradas</h3>
                </div>
                <table id="tablaAgencias">
                    <thead>
                        <tr>
                            <th>Nombre</th>
                            <th>Dirección</th>
                            <th>Teléfono</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        <!-- Usuarios -->
        <div class="section" id="usuarios">
            <h2 style="margin-bottom: 20px; color: #ffd700;">Gestión de Usuarios</h2>
            <div class="form-section">
                <h3 style="margin-bottom: 15px; color: #ffd700;">Nuevo Usuario</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Usuario</label>
                        <input type="text" id="usrUsername" placeholder="Nombre de usuario">
                    </div>
                    <div class="form-group">
                        <label>Contraseña</label>
                        <input type="password" id="usrPassword" placeholder="Contraseña">
                    </div>
                    <div class="form-group">
                        <label>Nombre Completo</label>
                        <input type="text" id="usrNombre" placeholder="Nombre completo">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Rol</label>
                        <select id="usrRol">
                            <option value="vendedor">Vendedor</option>
                            <option value="admin">Administrador</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Agencia</label>
                        <select id="usrAgencia"></select>
                    </div>
                    <div class="form-group">
                        <label>Teléfono</label>
                        <input type="tel" id="usrTelefono" placeholder="Teléfono">
                    </div>
                </div>
                <button class="btn-primary" onclick="crearUsuario()">Crear Usuario</button>
            </div>
            <div class="table-container">
                <div class="table-header">
                    <h3>Usuarios Registrados</h3>
                </div>
                <table id="tablaUsuarios">
                    <thead>
                        <tr>
                            <th>Usuario</th>
                            <th>Nombre</th>
                            <th>Rol</th>
                            <th>Agencia</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script>
        let agencias = [];
        
        function formatearMonto(monto) {
            let montoNum = parseFloat(monto);
            if (isNaN(montoNum)) return '0';
            if (montoNum === Math.floor(montoNum)) {
                return montoNum.toString();
            }
            return montoNum.toFixed(1);
        }
        
        function showSection(sectionId) {
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById(sectionId).classList.add('active');
            event.target.classList.add('active');
            
            // Cargar datos según sección
            if (sectionId === 'dashboard') cargarDashboard();
            else if (sectionId === 'reporte') cargarAgenciasSelect();
            else if (sectionId === 'historico') {
                cargarAgenciasSelect();
                document.getElementById('histDesde').valueAsDate = new Date();
                document.getElementById('histHasta').valueAsDate = new Date();
            }
            else if (sectionId === 'agencias') cargarAgencias();
            else if (sectionId === 'usuarios') {
                cargarAgenciasSelect();
                cargarUsuarios();
            }
            else if (sectionId === 'resultados') {
                document.getElementById('resFecha').valueAsDate = new Date();
                cargarSorteos();
                cargarResultados();
            }
            else if (sectionId === 'riesgo' || sectionId === 'tripletas') {
                document.getElementById('riesgoFecha').valueAsDate = new Date();
                document.getElementById('tripletaFecha').valueAsDate = new Date();
                cargarSorteos();
            }
        }
        
        async function cargarDashboard() {
            try {
                const response = await fetch('/api/dashboard');
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('dashVentas').textContent = 'S/ ' + formatearMonto(result.ventas_hoy);
                    document.getElementById('dashTickets').textContent = result.tickets_vendidos;
                    document.getElementById('dashAnulados').textContent = result.tickets_anulados;
                    document.getElementById('dashPremios').textContent = 'S/ ' + formatearMonto(result.premios_pendientes);
                }
            } catch (error) {
                console.error('Error cargando dashboard:', error);
            }
        }
        
        async function cargarAgencias() {
            try {
                const response = await fetch('/api/agencias');
                const result = await response.json();
                
                if (result.success) {
                    agencias = result.agencias;
                    const tbody = document.querySelector('#tablaAgencias tbody');
                    tbody.innerHTML = agencias.map(a => \`
                        <tr>
                            <td>\${a.nombre}</td>
                            <td>\${a.direccion || '-'}</td>
                            <td>\${a.telefono || '-'}</td>
                            <td><span class="badge \${a.activo ? 'badge-success' : 'badge-danger'}">\${a.activo ? 'Activa' : 'Inactiva'}</span></td>
                        </tr>
                    \`).join('');
                }
            } catch (error) {
                console.error('Error cargando agencias:', error);
            }
        }
        
        async function cargarAgenciasSelect() {
            try {
                const response = await fetch('/api/agencias');
                const result = await response.json();
                
                if (result.success) {
                    agencias = result.agencias;
                    const options = '<option value="">Todas</option>' + 
                        agencias.map(a => \`<option value="\${a.id}">\${a.nombre}</option>\`).join('');
                    
                    document.getElementById('repAgencia').innerHTML = options;
                    document.getElementById('histAgencia').innerHTML = options;
                    document.getElementById('usrAgencia').innerHTML = agencias.map(a => 
                        \`<option value="\${a.id}">\${a.nombre}</option>\`
                    ).join('');
                }
            } catch (error) {
                console.error('Error cargando agencias:', error);
            }
        }
        
        async function cargarUsuarios() {
            try {
                const response = await fetch('/api/usuarios');
                const result = await response.json();
                
                if (result.success) {
                    const tbody = document.querySelector('#tablaUsuarios tbody');
                    tbody.innerHTML = result.usuarios.map(u => \`
                        <tr>
                            <td>\${u.username}</td>
                            <td>\${u.nombre || '-'}</td>
                            <td><span class="badge \${u.rol === 'admin' ? 'badge-info' : 'badge-warning'}">\${u.rol}</span></td>
                            <td>\${agencias.find(a => a.id === u.agencia_id)?.nombre || '-'}</td>
                            <td><span class="badge \${u.activo ? 'badge-success' : 'badge-danger'}">\${u.activo ? 'Activo' : 'Inactivo'}</span></td>
                        </tr>
                    \`).join('');
                }
            } catch (error) {
                console.error('Error cargando usuarios:', error);
            }
        }
        
        async function cargarSorteos() {
            try {
                const response = await fetch('/api/sorteos-activos');
                const result = await response.json();
                
                if (result.success) {
                    const options = result.sorteos.map(s => \`<option value="\${s.id}">\${s.nombre}</option>\`).join('');
                    document.getElementById('resSorteo').innerHTML = options;
                    document.getElementById('riesgoSorteo').innerHTML = options;
                    document.getElementById('tripletaSorteo').innerHTML = options;
                }
            } catch (error) {
                console.error('Error cargando sorteos:', error);
            }
        }
        
        async function cargarReporte() {
            const periodo = document.getElementById('repPeriodo').value;
            const agenciaId = document.getElementById('repAgencia').value;
            
            try {
                const response = await fetch(\`/api/reporte-ventas?periodo=\${periodo}&agencia_id=\${agenciaId}\`);
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('resumenReporte').style.display = 'grid';
                    document.getElementById('repTotal').textContent = 'S/ ' + formatearMonto(result.total_ventas);
                    document.getElementById('repTickets').textContent = result.cantidad_tickets;
                    document.getElementById('repPromedio').textContent = 'S/ ' + formatearMonto(result.ticket_promedio);
                    
                    const tbody = document.querySelector('#tablaReporte tbody');
                    tbody.innerHTML = result.tickets.map(t => {
                        const estadoClass = {
                            'pendiente': 'estado-pendiente',
                            'pagado': 'estado-pagado',
                            'anulado': 'estado-anulado',
                            'por_pagar': 'estado-por_pagar'
                        }[t.estado] || 'estado-pendiente';
                        
                        return \`
                            <tr>
                                <td>\${t.codigo}</td>
                                <td>\${new Date(t.fecha).toLocaleString()}</td>
                                <td>\${t.cliente_nombre || '-'}</td>
                                <td>S/ \${formatearMonto(t.total)}</td>
                                <td class="\${estadoClass}">\${t.estado.toUpperCase()}</td>
                            </tr>
                        \`;
                    }).join('');
                }
            } catch (error) {
                alert('Error cargando reporte');
            }
        }
        
        async function cargarHistorico() {
            const fechaInicio = document.getElementById('histDesde').value;
            const fechaFin = document.getElementById('histHasta').value;
            const agenciaId = document.getElementById('histAgencia').value;
            
            if (!fechaInicio || !fechaFin) {
                alert('Seleccione fechas');
                return;
            }
            
            try {
                const response = await fetch(\`/api/reporte-historico?fecha_inicio=\${fechaInicio}&fecha_fin=\${fechaFin}&agencia_id=\${agenciaId}\`);
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('resumenHistorico').style.display = 'block';
                    document.getElementById('histTotalVentas').textContent = 'S/ ' + formatearMonto(result.total_ventas);
                    document.getElementById('histTotalAnulado').textContent = 'S/ ' + formatearMonto(result.total_anulado);
                    document.getElementById('histCantidad').textContent = result.cantidad_tickets;
                    
                    const tbody = document.querySelector('#tablaHistorico tbody');
                    tbody.innerHTML = result.tickets.map(t => {
                        const estadoClass = {
                            'pendiente': 'estado-pendiente',
                            'pagado': 'estado-pagado',
                            'anulado': 'estado-anulado',
                            'por_pagar': 'estado-por_pagar'
                        }[t.estado] || 'estado-pendiente';
                        
                        return \`
                            <tr>
                                <td>\${t.codigo}</td>
                                <td>\${new Date(t.fecha).toLocaleString()}</td>
                                <td>\${agencias.find(a => a.id === t.agencia_id)?.nombre || '-'}</td>
                                <td>\${t.vendedor_id || '-'}</td>
                                <td>\${t.cliente_nombre || '-'}</td>
                                <td>S/ \${formatearMonto(t.total)}</td>
                                <td class="\${estadoClass}">\${t.estado.toUpperCase()}</td>
                            </tr>
                        \`;
                    }).join('');
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                alert('Error cargando histórico');
            }
        }
        
        async function crearUsuario() {
            const data = {
                username: document.getElementById('usrUsername').value,
                password: document.getElementById('usrPassword').value,
                nombre: document.getElementById('usrNombre').value,
                rol: document.getElementById('usrRol').value,
                agencia_id: document.getElementById('usrAgencia').value,
                telefono: document.getElementById('usrTelefono').value
            };
            
            if (!data.username || !data.password) {
                alert('Usuario y contraseña requeridos');
                return;
            }
            
            try {
                const response = await fetch('/api/crear-usuario', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    alert('Usuario creado correctamente');
                    cargarUsuarios();
                    document.getElementById('usrUsername').value = '';
                    document.getElementById('usrPassword').value = '';
                    document.getElementById('usrNombre').value = '';
                    document.getElementById('usrTelefono').value = '';
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                alert('Error creando usuario');
            }
        }
        
        async function guardarResultado() {
            const data = {
                sorteo_id: document.getElementById('resSorteo').value,
                fecha: document.getElementById('resFecha').value,
                numero: document.getElementById('resNumero').value
            };
            
            if (!data.numero || data.numero < 0 || data.numero > 41) {
                alert('Ingrese número válido (00-41)');
                return;
            }
            
            try {
                const response = await fetch('/api/guardar-resultado', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    alert('Resultado guardado correctamente');
                    cargarResultados();
                    document.getElementById('resNumero').value = '';
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                alert('Error guardando resultado');
            }
        }
        
        async function cargarResultados() {
            try {
                const response = await fetch('/api/resultados');
                const result = await response.json();
                
                if (result.success) {
                    const tbody = document.querySelector('#tablaResultados tbody');
                    tbody.innerHTML = (result.resultados || []).map(r => \`
                        <tr>
                            <td>\${r.fecha}</td>
                            <td>\${r.sorteo_id}</td>
                            <td>\${r.numero_ganador}</td>
                            <td>\${r.animal_ganador}</td>
                        </tr>
                    \`).join('');
                }
            } catch (error) {
                console.error('Error cargando resultados:', error);
            }
        }
        
        function logout() {
            window.location.href = '/logout';
        }
        
        function exportarReporte() {
            alert('Función de exportación en desarrollo');
        }
        
        function exportarHistorico() {
            alert('Función de exportación en desarrollo');
        }
        
        function cargarRiesgo() {
            alert('Consultando riesgo...');
        }
        
        function cargarTripletas() {
            alert('Consultando tripletas...');
        }
        
        function crearAgencia() {
            alert('Función en desarrollo');
        }
        
        // Inicializar
        cargarDashboard();
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
