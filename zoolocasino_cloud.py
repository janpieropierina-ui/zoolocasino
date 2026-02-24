#!/usr/bin/env python3
"""
ZOOLO CASINO LOCAL v1.1 
Base de datos: SQLite local (sin Supabase)
Acceso: localhost o ngrok
Correcciones: Manejo de errores, conexiones DB, estabilidad
"""

import os, json, csv, io, sqlite3, logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, render_template_string, request, session, redirect, jsonify, Response

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'zoolo_local_2025_ultra_seguro')

# Configurar logging para ver errores en consola
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zoolo_casino.db')

# ==================== CONFIGURACION ====================
PAGO_ANIMAL_NORMAL = 35
PAGO_LECHUZA       = 70
PAGO_ESPECIAL      = 2
PAGO_TRIPLETA      = 60
COMISION_AGENCIA   = 0.15
MINUTOS_BLOQUEO    = 5

HORARIOS_PERU = [
    "08:00 AM","09:00 AM","10:00 AM","11:00 AM","12:00 PM",
    "01:00 PM","02:00 PM","03:00 PM","04:00 PM","05:00 PM","06:00 PM"
]
HORARIOS_VENEZUELA = [
    "09:00 AM","10:00 AM","11:00 AM","12:00 PM","01:00 PM",
    "02:00 PM","03:00 PM","04:00 PM","05:00 PM","06:00 PM","07:00 PM"
]

ANIMALES = {
    "00":"Ballena","0":"Delfin","1":"Carnero","2":"Toro","3":"Ciempies",
    "4":"Alacran","5":"Leon","6":"Rana","7":"Perico","8":"Raton","9":"Aguila",
    "10":"Tigre","11":"Gato","12":"Caballo","13":"Mono","14":"Paloma",
    "15":"Zorro","16":"Oso","17":"Pavo","18":"Burro","19":"Chivo","20":"Cochino",
    "21":"Gallo","22":"Camello","23":"Cebra","24":"Iguana","25":"Gallina",
    "26":"Vaca","27":"Perro","28":"Zamuro","29":"Elefante","30":"Caiman",
    "31":"Lapa","32":"Ardilla","33":"Pescado","34":"Venado","35":"Jirafa",
    "36":"Culebra","37":"Aviapa","38":"Conejo","39":"Tortuga","40":"Lechuza"
}
ROJOS = ["1","3","5","7","9","12","14","16","18","19",
         "21","23","25","27","30","32","34","36","37","39"]

# ==================== BASE DE DATOS SQLITE ====================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    try:
        with get_db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS agencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                nombre_agencia TEXT NOT NULL,
                es_admin INTEGER DEFAULT 0,
                comision REAL DEFAULT 0.15,
                activa INTEGER DEFAULT 1,
                creado TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial TEXT UNIQUE NOT NULL,
                agencia_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                total REAL NOT NULL,
                pagado INTEGER DEFAULT 0,
                anulado INTEGER DEFAULT 0,
                creado TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (agencia_id) REFERENCES agencias(id)
            );
            CREATE TABLE IF NOT EXISTS jugadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                hora TEXT NOT NULL,
                seleccion TEXT NOT NULL,
                monto REAL NOT NULL,
                tipo TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            );
            CREATE TABLE IF NOT EXISTS tripletas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                animal1 TEXT NOT NULL,
                animal2 TEXT NOT NULL,
                animal3 TEXT NOT NULL,
                monto REAL NOT NULL,
                fecha TEXT NOT NULL,
                pagado INTEGER DEFAULT 0,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            );
            CREATE TABLE IF NOT EXISTS resultados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                animal TEXT NOT NULL,
                UNIQUE(fecha, hora)
            );
            CREATE INDEX IF NOT EXISTS idx_tickets_agencia ON tickets(agencia_id);
            CREATE INDEX IF NOT EXISTS idx_tickets_fecha ON tickets(fecha);
            CREATE INDEX IF NOT EXISTS idx_jugadas_ticket ON jugadas(ticket_id);
            CREATE INDEX IF NOT EXISTS idx_tripletas_ticket ON tripletas(ticket_id);
            CREATE INDEX IF NOT EXISTS idx_resultados_fecha ON resultados(fecha);
            """)
            admin = db.execute("SELECT id FROM agencias WHERE es_admin=1").fetchone()
            if not admin:
                db.execute("""INSERT INTO agencias (usuario,password,nombre_agencia,es_admin,comision,activa)
                              VALUES (?,?,?,1,0,1)""", ('admin','admin123','ADMINISTRADOR'))
                db.commit()
                print("[DB] Admin creado: usuario=admin  password=admin123")
        logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"Error inicializando DB: {e}")
        raise

# ==================== HELPERS ====================
def ahora_peru():
    return datetime.now(timezone.utc) - timedelta(hours=5)

def parse_fecha(f):
    if not f: 
        return None
    formatos = ("%d/%m/%Y %I:%M %p", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S")
    for fmt in formatos:
        try: 
            return datetime.strptime(f, fmt)
        except ValueError: 
            continue
    return None

def generar_serial():
    return str(int(ahora_peru().timestamp() * 1000))

def fmt(m):
    try:
        v = float(m)
        return str(int(v)) if v == int(v) else str(v)
    except: 
        return str(m)

def hora_a_min(h):
    try:
        p = h.replace(':',' ').split()
        hr, mn, ap = int(p[0]), int(p[1]), p[2]
        if ap=='PM' and hr!=12: 
            hr+=12
        elif ap=='AM' and hr==12: 
            hr=0
        return hr*60+mn
    except: 
        return 0

def puede_vender(hora_sorteo):
    ahora = ahora_peru()
    diff = hora_a_min(hora_sorteo) - (ahora.hour*60+ahora.minute)
    return diff > MINUTOS_BLOQUEO

def calcular_premio_animal(monto, num):
    try:
        return monto * (PAGO_LECHUZA if str(num)=="40" else PAGO_ANIMAL_NORMAL)
    except:
        return 0

def calcular_premio_ticket(ticket_id, db=None):
    close_db = False
    if db is None:
        db = get_db()
        close_db = True
    try:
        t = db.execute("SELECT fecha FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not t: 
            return 0
        fecha_ticket = parse_fecha(t['fecha'])
        if not fecha_ticket: 
            return 0
        fecha_str = fecha_ticket.strftime("%d/%m/%Y")
        
        res_rows = db.execute("SELECT hora, animal FROM resultados WHERE fecha=?", (fecha_str,)).fetchall()
        resultados = {r['hora']: r['animal'] for r in res_rows}
        
        total = 0
        
        # Procesar jugadas normales
        jugadas = db.execute("SELECT * FROM jugadas WHERE ticket_id=?", (ticket_id,)).fetchall()
        for j in jugadas:
            wa = resultados.get(j['hora'])
            if not wa: 
                continue
            try:
                if j['tipo']=='animal' and str(wa)==str(j['seleccion']):
                    total += calcular_premio_animal(j['monto'], wa)
                elif j['tipo']=='especial' and str(wa) not in ["0","00"]:
                    sel, num = j['seleccion'], int(wa)
                    if ((sel=='ROJO' and str(wa) in ROJOS) or 
                        (sel=='NEGRO' and str(wa) not in ROJOS) or 
                        (sel=='PAR' and num%2==0) or 
                        (sel=='IMPAR' and num%2!=0)):
                        total += j['monto'] * PAGO_ESPECIAL
            except (ValueError, TypeError):
                continue
        
        # Procesar tripletas
        trips = db.execute("SELECT * FROM tripletas WHERE ticket_id=?", (ticket_id,)).fetchall()
        for tr in trips:
            try:
                nums = {tr['animal1'], tr['animal2'], tr['animal3']}
                salidos = {a for a in resultados.values() if a in nums}
                if len(salidos)==3:
                    total += tr['monto'] * PAGO_TRIPLETA
            except:
                continue
                
        return total
    except Exception as e:
        logger.error(f"Error calculando premio ticket {ticket_id}: {e}")
        return 0
    finally:
        if close_db: 
            db.close()

# ==================== DECORADORES ====================
def login_required(f):
    @wraps(f)
    def d(*a,**k):
        if 'user_id' not in session: 
            return redirect('/login')
        return f(*a,**k)
    return d

def admin_required(f):
    @wraps(f)
    def d(*a,**k):
        if 'user_id' not in session or not session.get('es_admin'):
            return "No autorizado", 403
        return f(*a,**k)
    return d

def agencia_required(f):
    @wraps(f)
    def d(*a,**k):
        if 'user_id' not in session: 
            return jsonify({'error':'Login requerido'}),403
        if session.get('es_admin'): 
            return jsonify({'error':'Admin no puede vender'}),403
        return f(*a,**k)
    return d

# ==================== MANEJADORES DE ERROR ====================
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Error 500: {error}")
    return jsonify({'error': 'Error interno del servidor', 'detalle': str(error)}), 500

@app.errorhandler(Exception)
def unhandled_exception(e):
    logger.error(f"Excepción no manejada: {e}")
    return jsonify({'error': 'Error inesperado', 'detalle': str(e)}), 500

# ==================== RUTAS ====================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/admin' if session.get('es_admin') else '/pos')
    return redirect('/login')

@app.route('/login', methods=['GET','POST'])
def login():
    error=""
    if request.method=='POST':
        u = request.form.get('usuario','').strip().lower()
        p = request.form.get('password','').strip()
        try:
            with get_db() as db:
                row = db.execute(
                    "SELECT * FROM agencias WHERE usuario=? AND password=? AND activa=1",(u,p)
                ).fetchone()
            if row:
                session['user_id']        = row['id']
                session['nombre_agencia'] = row['nombre_agencia']
                session['es_admin']       = bool(row['es_admin'])
                return redirect('/')
            error="Usuario o clave incorrecta"
        except Exception as e:
            logger.error(f"Error en login: {e}")
            error="Error de sistema"
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
        horarios_venezuela=HORARIOS_VENEZUELA)

@app.route('/admin')
@admin_required
def admin():
    return render_template_string(ADMIN_HTML,
        animales=ANIMALES, horarios=HORARIOS_PERU)

# ==================== API POS ====================
@app.route('/api/resultados-hoy')
@login_required
def resultados_hoy():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        with get_db() as db:
            rows = db.execute("SELECT hora,animal FROM resultados WHERE fecha=?",(hoy,)).fetchall()
        rd = {r['hora']:{'animal':r['animal'],'nombre':ANIMALES.get(r['animal'],'?')} for r in rows}
        for h in HORARIOS_PERU:
            if h not in rd: 
                rd[h]=None
        return jsonify({'status':'ok','fecha':hoy,'resultados':rd})
    except Exception as e:
        logger.error(f"Error en resultados-hoy: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/resultados-fecha', methods=['POST'])
@login_required
def resultados_fecha():
    try:
        data = request.get_json() or {}
        fs = data.get('fecha')
        try: 
            fecha_obj = datetime.strptime(fs, "%Y-%m-%d") if fs else ahora_peru()
        except: 
            fecha_obj = ahora_peru()
        fecha_str = fecha_obj.strftime("%d/%m/%Y")
        with get_db() as db:
            rows = db.execute("SELECT hora,animal FROM resultados WHERE fecha=?",(fecha_str,)).fetchall()
        rd = {r['hora']:{'animal':r['animal'],'nombre':ANIMALES.get(r['animal'],'?')} for r in rows}
        for h in HORARIOS_PERU:
            if h not in rd: 
                rd[h]=None
        return jsonify({'status':'ok','fecha_consulta':fecha_str,'resultados':rd})
    except Exception as e:
        logger.error(f"Error en resultados-fecha: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/procesar-venta', methods=['POST'])
@agencia_required
def procesar_venta():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error':'Datos JSON requeridos'}),400
            
        jugadas = data.get('jugadas', [])
        if not jugadas: 
            return jsonify({'error':'Ticket vacío'}),400
            
        # Validar cierre de sorteos
        for j in jugadas:
            if j.get('tipo')!='tripleta' and not puede_vender(j['hora']):
                return jsonify({'error':f"Sorteo {j['hora']} ya cerró"}),400
        
        serial = generar_serial()
        fecha = ahora_peru().strftime("%d/%m/%Y %I:%M %p")
        total = sum(j['monto'] for j in jugadas)
        
        with get_db() as db:
            cur = db.execute(
                "INSERT INTO tickets (serial,agencia_id,fecha,total) VALUES (?,?,?,?)",
                (serial, session['user_id'], fecha, total))
            ticket_id = cur.lastrowid
            
            for j in jugadas:
                if j['tipo']=='tripleta':
                    nums = j['seleccion'].split(',')
                    if len(nums) != 3:
                        raise ValueError("Tripleta debe tener 3 animales")
                    db.execute(
                        "INSERT INTO tripletas (ticket_id,animal1,animal2,animal3,monto,fecha) VALUES (?,?,?,?,?,?)",
                        (ticket_id, nums[0], nums[1], nums[2], j['monto'], fecha.split(' ')[0]))
                else:
                    db.execute(
                        "INSERT INTO jugadas (ticket_id,hora,seleccion,monto,tipo) VALUES (?,?,?,?,?)",
                        (ticket_id, j['hora'], j['seleccion'], j['monto'], j['tipo']))
            db.commit()
            
        # Generar mensaje WhatsApp
        jpoh = {}
        for j in jugadas:
            if j['tipo']!='tripleta': 
                if j['hora'] not in jpoh:
                    jpoh[j['hora']] = []
                jpoh[j['hora']].append(j)
                
        lineas = [f"*{session['nombre_agencia']}*",
                  f"*TICKET:* #{ticket_id}",
                  f"*SERIAL:* {serial}", 
                  fecha,
                  "------------------------",""]
                  
        for hp in HORARIOS_PERU:
            if hp not in jpoh: 
                continue
            idx = HORARIOS_PERU.index(hp)
            hv = HORARIOS_VENEZUELA[idx]
            hpc = hp.replace(' ','').replace('00','').lower()
            hvc = hv.replace(' ','').replace('00','').lower()
            lineas.append(f"*ZOOLO.PERU/{hpc}...VZLA/{hvc}*")
            items=[]
            for j in jpoh[hp]:
                if j['tipo']=='animal':
                    n = ANIMALES.get(j['seleccion'],'')[0:3].upper()
                    items.append(f"{n}{j['seleccion']}x{fmt(j['monto'])}")
                else:
                    items.append(f"{j['seleccion'][0:3]}x{fmt(j['monto'])}")
            lineas.append(" ".join(items))
            lineas.append("")
            
        trips_t = [j for j in jugadas if j['tipo']=='tripleta']
        if trips_t:
            lineas.append("*TRIPLETAS (Paga x60)*")
            for t in trips_t:
                nums = t['seleccion'].split(',')
                ns = [ANIMALES.get(n,'')[0:3].upper() for n in nums]
                lineas.append(f"{'-'.join(ns)} x60 S/{fmt(t['monto'])}")
            lineas.append("")
            
        lineas += ["------------------------",
                   f"*TOTAL: S/{fmt(total)}*","",
                   "Buena Suerte!","El ticket vence a los 3 dias"]
                   
        import urllib.parse
        texto = "\n".join(lineas)
        url_wa = f"https://wa.me/?text={urllib.parse.quote(texto)}"
        
        return jsonify({'status':'ok','serial':serial,'ticket_id':ticket_id,
                        'total':total,'url_whatsapp':url_wa})
    except Exception as e:
        logger.error(f"Error en procesar-venta: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/api/mis-tickets', methods=['POST'])
@agencia_required
def mis_tickets():
    try:
        data = request.get_json() or {}
        fi = data.get('fecha_inicio')
        ff = data.get('fecha_fin')
        est = data.get('estado','todos')
        
        dti = datetime.strptime(fi,"%Y-%m-%d") if fi else None
        dtf = datetime.strptime(ff,"%Y-%m-%d").replace(hour=23,minute=59) if ff else None
        
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM tickets WHERE agencia_id=? AND anulado=0 ORDER BY id DESC LIMIT 500",
                (session['user_id'],)).fetchall()
            tickets_fil = []
            for t in rows:
                dt = parse_fecha(t['fecha'])
                if not dt: 
                    continue
                if dti and dt<dti: 
                    continue
                if dtf and dt>dtf: 
                    continue
                if est=='pagados' and not t['pagado']: 
                    continue
                if est=='pendientes' and t['pagado']: 
                    continue
                tickets_fil.append(dict(t))
                
            resultado_cache = {}
            tickets_out = []
            
            for t in tickets_fil[:60]:
                try:
                    fecha_dt = parse_fecha(t['fecha'])
                    if not fecha_dt:
                        continue
                    fecha_str = fecha_dt.strftime("%d/%m/%Y")
                    
                    if fecha_str not in resultado_cache:
                        rr = db.execute("SELECT hora,animal FROM resultados WHERE fecha=?",(fecha_str,)).fetchall()
                        resultado_cache[fecha_str] = {r['hora']:r['animal'] for r in rr}
                    res_dia = resultado_cache[fecha_str]
                    
                    jugadas_raw = db.execute("SELECT * FROM jugadas WHERE ticket_id=?",(t['id'],)).fetchall()
                    tripletas_raw = db.execute("SELECT * FROM tripletas WHERE ticket_id=?",(t['id'],)).fetchall()
                    
                    premio_total = 0
                    jugadas_det = []
                    
                    for j in jugadas_raw:
                        wa = res_dia.get(j['hora'])
                        gano = False
                        pj = 0
                        if wa:
                            if j['tipo']=='animal' and str(wa)==str(j['seleccion']):
                                pj = calcular_premio_animal(j['monto'],wa)
                                gano = True
                            elif j['tipo']=='especial' and str(wa) not in ["0","00"]:
                                sel, num = j['seleccion'], int(wa)
                                if ((sel=='ROJO' and str(wa) in ROJOS) or 
                                    (sel=='NEGRO' and str(wa) not in ROJOS) or 
                                    (sel=='PAR' and num%2==0) or 
                                    (sel=='IMPAR' and num%2!=0)):
                                    pj = j['monto']*PAGO_ESPECIAL
                                    gano = True
                        if gano: 
                            premio_total += pj
                        jugadas_det.append({
                            'tipo':j['tipo'],'hora':j['hora'],
                            'seleccion':j['seleccion'],
                            'nombre':ANIMALES.get(j['seleccion'],j['seleccion']) if j['tipo']=='animal' else j['seleccion'],
                            'monto':j['monto'],
                            'resultado':wa,
                            'resultado_nombre':ANIMALES.get(str(wa),str(wa)) if wa else None,
                            'gano':gano,'premio':round(pj,2)
                        })
                        
                    trips_det = []
                    for tr in tripletas_raw:
                        nums = {tr['animal1'], tr['animal2'], tr['animal3']}
                        salidos = list(dict.fromkeys([a for a in res_dia.values() if a in nums]))
                        gano_t = len(salidos)==3
                        pt = tr['monto']*PAGO_TRIPLETA if gano_t else 0
                        if gano_t: 
                            premio_total += pt
                        trips_det.append({
                            'animal1':tr['animal1'],'nombre1':ANIMALES.get(tr['animal1'],tr['animal1']),
                            'animal2':tr['animal2'],'nombre2':ANIMALES.get(tr['animal2'],tr['animal2']),
                            'animal3':tr['animal3'],'nombre3':ANIMALES.get(tr['animal3'],tr['animal3']),
                            'monto':tr['monto'],'salieron':salidos,
                            'gano':gano_t,'premio':round(pt,2),'pagado':bool(tr['pagado'])
                        })
                        
                    if est=='por_pagar' and (t['pagado'] or premio_total==0): 
                        continue
                        
                    tickets_out.append({
                        'id':t['id'],'serial':t['serial'],'fecha':t['fecha'],
                        'total':t['total'],'pagado':bool(t['pagado']),
                        'premio_calculado':round(premio_total,2),
                        'jugadas':jugadas_det,'tripletas':trips_det
                    })
                except Exception as e:
                    logger.error(f"Error procesando ticket {t['id']}: {e}")
                    continue
                    
        tv = sum(t['total'] for t in tickets_out)
        return jsonify({'status':'ok','tickets':tickets_out,
                        'totales':{'cantidad':len(tickets_out),'ventas':round(tv,2)}})
    except Exception as e:
        logger.error(f"Error en mis-tickets: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/api/consultar-ticket-detalle', methods=['POST'])
@agencia_required
def consultar_ticket_detalle():
    try:
        serial = (request.get_json() or {}).get('serial')
        if not serial: 
            return jsonify({'error':'Serial requerido'}),400
            
        with get_db() as db:
            t = db.execute(
                "SELECT * FROM tickets WHERE serial=? AND agencia_id=?",(serial,session['user_id'])
            ).fetchone()
            if not t: 
                return jsonify({'error':'Ticket no encontrado'})
            t = dict(t)
            fecha_dt = parse_fecha(t['fecha'])
            if not fecha_dt:
                return jsonify({'error':'Fecha inválida en ticket'})
            fecha_str = fecha_dt.strftime("%d/%m/%Y")
            res_rows = db.execute("SELECT hora,animal FROM resultados WHERE fecha=?",(fecha_str,)).fetchall()
            res_dia = {r['hora']:r['animal'] for r in res_rows}
            jugadas_raw = db.execute("SELECT * FROM jugadas WHERE ticket_id=?",(t['id'],)).fetchall()
            tripletas_raw = db.execute("SELECT * FROM tripletas WHERE ticket_id=?",(t['id'],)).fetchall()
            
        premio_total=0
        jdet=[]
        for j in jugadas_raw:
            wa=res_dia.get(j['hora'])
            gano=False
            pj=0
            if wa:
                if j['tipo']=='animal' and str(wa)==str(j['seleccion']):
                    pj=calcular_premio_animal(j['monto'],wa)
                    gano=True
                elif j['tipo']=='especial' and str(wa) not in ["0","00"]:
                    sel,num=j['seleccion'],int(wa)
                    if ((sel=='ROJO' and str(wa) in ROJOS) or 
                        (sel=='NEGRO' and str(wa) not in ROJOS) or 
                        (sel=='PAR' and num%2==0) or 
                        (sel=='IMPAR' and num%2!=0)):
                        pj=j['monto']*PAGO_ESPECIAL
                        gano=True
            if gano: 
                premio_total+=pj
            jdet.append({
                'tipo':j['tipo'],'hora':j['hora'],'seleccion':j['seleccion'],
                'nombre_seleccion':ANIMALES.get(j['seleccion'],j['seleccion']) if j['tipo']=='animal' else j['seleccion'],
                'monto':j['monto'],'resultado':wa,
                'resultado_nombre':ANIMALES.get(str(wa),str(wa)) if wa else None,
                'gano':gano,'premio':round(pj,2)
            })
            
        tdet=[]
        for tr in tripletas_raw:
            nums={tr['animal1'],tr['animal2'],tr['animal3']}
            salidos=list(dict.fromkeys([a for a in res_dia.values() if a in nums]))
            gano_t=len(salidos)==3
            pt=tr['monto']*PAGO_TRIPLETA if gano_t else 0
            if gano_t: 
                premio_total+=pt
            tdet.append({
                'tipo':'tripleta',
                'animal1':tr['animal1'],'nombre1':ANIMALES.get(tr['animal1'],''),
                'animal2':tr['animal2'],'nombre2':ANIMALES.get(tr['animal2'],''),
                'animal3':tr['animal3'],'nombre3':ANIMALES.get(tr['animal3'],''),
                'monto':tr['monto'],'salieron':salidos,
                'gano':gano_t,'premio':round(pt,2),'pagado':bool(tr['pagado'])
            })
            
        return jsonify({
            'status':'ok',
            'ticket':{
                'id':t['id'],
                'serial':t['serial'],
                'fecha':t['fecha'],
                'total_apostado':t['total'],
                'pagado':bool(t['pagado']),
                'anulado':bool(t['anulado']),
                'premio_total':round(premio_total,2)
            },
            'jugadas':jdet,
            'tripletas':tdet
        })
    except Exception as e:
        logger.error(f"Error en consultar-ticket-detalle: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/api/verificar-ticket', methods=['POST'])
@login_required
def verificar_ticket():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error':'Datos requeridos'}),400
        serial = data.get('serial')
        if not serial:
            return jsonify({'error':'Serial requerido'}),400
            
        with get_db() as db:
            t = db.execute("SELECT * FROM tickets WHERE serial=?",(serial,)).fetchone()
            if not t: 
                return jsonify({'error':'Ticket no existe'})
            if not session.get('es_admin') and t['agencia_id']!=session['user_id']:
                return jsonify({'error':'No autorizado'})
            if t['anulado']: 
                return jsonify({'error':'TICKET ANULADO'})
            if t['pagado']:  
                return jsonify({'error':'YA FUE PAGADO'})
            premio = calcular_premio_ticket(t['id'], db)
        return jsonify({'status':'ok','ticket_id':t['id'],'total_ganado':round(premio,2)})
    except Exception as e:
        logger.error(f"Error en verificar-ticket: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/api/pagar-ticket', methods=['POST'])
@login_required
def pagar_ticket():
    try:
        data = request.get_json()
        if not data or not data.get('ticket_id'):
            return jsonify({'error':'ticket_id requerido'}),400
            
        tid = data['ticket_id']
        with get_db() as db:
            t = db.execute("SELECT * FROM tickets WHERE id=?",(tid,)).fetchone()
            if not t: 
                return jsonify({'error':'Ticket no existe'})
            if not session.get('es_admin') and t['agencia_id']!=session['user_id']:
                return jsonify({'error':'No autorizado'})
            db.execute("UPDATE tickets SET pagado=1 WHERE id=?",(tid,))
            db.execute("UPDATE tripletas SET pagado=1 WHERE ticket_id=?",(tid,))
            db.commit()
        return jsonify({'status':'ok','mensaje':'Ticket pagado'})
    except Exception as e:
        logger.error(f"Error en pagar-ticket: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/api/anular-ticket', methods=['POST'])
@login_required
def anular_ticket():
    try:
        data = request.get_json()
        if not data or not data.get('serial'):
            return jsonify({'error':'serial requerido'}),400
            
        serial = data['serial']
        with get_db() as db:
            t = db.execute("SELECT * FROM tickets WHERE serial=?",(serial,)).fetchone()
            if not t: 
                return jsonify({'error':'Ticket no existe'})
            if not session.get('es_admin') and t['agencia_id']!=session['user_id']:
                return jsonify({'error':'No autorizado'})
            if t['pagado']: 
                return jsonify({'error':'Ya pagado, no se puede anular'})
            if not session.get('es_admin'):
                dt = parse_fecha(t['fecha'])
                if dt and (ahora_peru()-dt).total_seconds()/60 > 5:
                    return jsonify({'error':'Solo puede anular dentro de 5 minutos'})
                jugs = db.execute("SELECT hora FROM jugadas WHERE ticket_id=?",(t['id'],)).fetchall()
                for j in jugs:
                    if not puede_vender(j['hora']):
                        return jsonify({'error':f"Sorteo {j['hora']} ya cerró"})
            db.execute("UPDATE tickets SET anulado=1 WHERE id=?",(t['id'],))
            db.commit()
        return jsonify({'status':'ok','mensaje':'Ticket anulado'})
    except Exception as e:
        logger.error(f"Error en anular-ticket: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/api/caja')
@agencia_required
def caja_agencia():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        with get_db() as db:
            tickets = db.execute(
                "SELECT * FROM tickets WHERE agencia_id=? AND anulado=0 AND fecha LIKE ?",
                (session['user_id'], hoy+'%')).fetchall()
            ag = db.execute("SELECT comision FROM agencias WHERE id=?",(session['user_id'],)).fetchone()
            com_pct = ag['comision'] if ag else COMISION_AGENCIA
            ventas=0
            premios_pagados=0
            pendientes=0
            for t in tickets:
                ventas += t['total']
                p = calcular_premio_ticket(t['id'],db)
                if t['pagado']: 
                    premios_pagados+=p
                elif p>0: 
                    pendientes+=1
        return jsonify({
            'ventas':round(ventas,2),
            'premios':round(premios_pagados,2),
            'comision':round(ventas*com_pct,2),
            'balance':round(ventas-premios_pagados-ventas*com_pct,2),
            'tickets_pendientes':pendientes
        })
    except Exception as e:
        logger.error(f"Error en caja: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/api/caja-historico', methods=['POST'])
@agencia_required
def caja_historico():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error':'Datos requeridos'}),400
            
        fi,ff = data.get('fecha_inicio'), data.get('fecha_fin')
        if not fi or not ff: 
            return jsonify({'error':'Fechas requeridas'}),400
            
        dti = datetime.strptime(fi,"%Y-%m-%d")
        dtf = datetime.strptime(ff,"%Y-%m-%d").replace(hour=23,minute=59)
        
        with get_db() as db:
            ag = db.execute("SELECT comision FROM agencias WHERE id=?",(session['user_id'],)).fetchone()
            com_pct = ag['comision'] if ag else COMISION_AGENCIA
            tickets = db.execute(
                "SELECT * FROM tickets WHERE agencia_id=? AND anulado=0 ORDER BY id DESC LIMIT 2000",
                (session['user_id'],)).fetchall()
                
        dias={}
        tv=0
        tp=0
        
        for t in tickets:
            try:
                dt=parse_fecha(t['fecha'])
                if not dt or dt<dti or dt>dtf: 
                    continue
                dk=dt.strftime("%d/%m/%Y")
                if dk not in dias: 
                    dias[dk]={'ventas':0,'tickets':0,'premios':0,'pendientes':0}
                dias[dk]['ventas']+=t['total']
                dias[dk]['tickets']+=1
                tv+=t['total']
                with get_db() as db2:
                    p=calcular_premio_ticket(t['id'],db2)
                if t['pagado']: 
                    dias[dk]['premios']+=p
                    tp+=p
                elif p>0: 
                    dias[dk]['pendientes']+=1
            except Exception as e:
                logger.error(f"Error procesando ticket histórico {t['id']}: {e}")
                continue
                
        resumen=[]
        for dk in sorted(dias.keys()):
            d=dias[dk]
            cd=d['ventas']*com_pct
            resumen.append({
                'fecha':dk,
                'tickets':d['tickets'],
                'ventas':round(d['ventas'],2),
                'premios':round(d['premios'],2),
                'comision':round(cd,2),
                'balance':round(d['ventas']-d['premios']-cd,2),
                'pendientes':d['pendientes']
            })
            
        tc=tv*com_pct
        return jsonify({
            'resumen_por_dia':resumen,
            'totales':{
                'ventas':round(tv,2),
                'premios':round(tp,2),
                'comision':round(tc,2),
                'balance':round(tv-tp-tc,2)
            }
        })
    except Exception as e:
        logger.error(f"Error en caja-historico: {e}")
        return jsonify({'error':str(e)}),500

# ==================== API ADMIN ====================
@app.route('/admin/guardar-resultado', methods=['POST'])
@admin_required
def guardar_resultado():
    try:
        hora   = request.form.get('hora','').strip()
        animal = request.form.get('animal','').strip()
        fi     = request.form.get('fecha','').strip()
        
        if animal not in ANIMALES:
            return jsonify({'error':f'Animal inválido: {animal}'}),400
            
        if fi:
            try: 
                fecha = datetime.strptime(fi,"%Y-%m-%d").strftime("%d/%m/%Y")
            except: 
                fecha = ahora_peru().strftime("%d/%m/%Y")
        else:
            fecha = ahora_peru().strftime("%d/%m/%Y")
            
        with get_db() as db:
            db.execute("""INSERT INTO resultados (fecha,hora,animal) VALUES (?,?,?)
                          ON CONFLICT(fecha,hora) DO UPDATE SET animal=excluded.animal""",
                       (fecha, hora, animal))
            db.commit()
        return jsonify({
            'status':'ok',
            'mensaje':f'Resultado guardado: {hora} = {animal} ({ANIMALES[animal]})',
            'fecha':fecha,
            'hora':hora,
            'animal':animal
        })
    except Exception as e:
        logger.error(f"Error en guardar-resultado: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/admin/resultados-hoy')
@admin_required
def admin_resultados_hoy():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        with get_db() as db:
            rows = db.execute("SELECT hora,animal FROM resultados WHERE fecha=?",(hoy,)).fetchall()
        rd={r['hora']:{'animal':r['animal'],'nombre':ANIMALES.get(r['animal'],'?')} for r in rows}
        for h in HORARIOS_PERU:
            if h not in rd: 
                rd[h]=None
        return jsonify({'status':'ok','fecha':hoy,'resultados':rd})
    except Exception as e:
        logger.error(f"Error en resultados-hoy: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/api/resultados-fecha-admin', methods=['POST'])
@admin_required
def resultados_fecha_admin():
    try:
        data = request.get_json() or {}
        fs   = data.get('fecha')
        try: 
            fecha_str = datetime.strptime(fs,"%Y-%m-%d").strftime("%d/%m/%Y")
        except: 
            fecha_str = ahora_peru().strftime("%d/%m/%Y")
        with get_db() as db:
            rows = db.execute("SELECT hora,animal FROM resultados WHERE fecha=?",(fecha_str,)).fetchall()
        rd={r['hora']:{'animal':r['animal'],'nombre':ANIMALES.get(r['animal'],'?')} for r in rows}
        for h in HORARIOS_PERU:
            if h not in rd: 
                rd[h]=None
        return jsonify({'status':'ok','fecha_consulta':fecha_str,'resultados':rd})
    except Exception as e:
        logger.error(f"Error en resultados-fecha-admin: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/admin/lista-agencias')
@admin_required
def lista_agencias():
    try:
        with get_db() as db:
            rows = db.execute("SELECT id,usuario,nombre_agencia,comision,activa FROM agencias WHERE es_admin=0").fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.error(f"Error en lista-agencias: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/admin/crear-agencia', methods=['POST'])
@admin_required
def crear_agencia():
    try:
        u = request.form.get('usuario','').strip().lower()
        p = request.form.get('password','').strip()
        n = request.form.get('nombre','').strip()
        if not u or not p or not n: 
            return jsonify({'error':'Complete todos los campos'}),400
            
        with get_db() as db:
            ex = db.execute("SELECT id FROM agencias WHERE usuario=?",(u,)).fetchone()
            if ex: 
                return jsonify({'error':'Usuario ya existe'}),400
            db.execute("INSERT INTO agencias (usuario,password,nombre_agencia,es_admin,comision,activa) VALUES (?,?,?,0,?,1)",
                       (u,p,n,COMISION_AGENCIA))
            db.commit()
        return jsonify({'status':'ok','mensaje':f'Agencia {n} creada'})
    except Exception as e:
        logger.error(f"Error en crear-agencia: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/admin/editar-agencia', methods=['POST'])
@admin_required
def editar_agencia():
    try:
        data = request.get_json() or {}
        aid  = data.get('id')
        if not aid:
            return jsonify({'error':'ID requerido'}),400
            
        with get_db() as db:
            if 'password' in data and data['password']:
                db.execute("UPDATE agencias SET password=? WHERE id=? AND es_admin=0",(data['password'],aid))
            if 'comision' in data:
                db.execute("UPDATE agencias SET comision=? WHERE id=? AND es_admin=0",(float(data['comision'])/100,aid))
            if 'activa' in data:
                db.execute("UPDATE agencias SET activa=? WHERE id=? AND es_admin=0",(1 if data['activa'] else 0,aid))
            db.commit()
        return jsonify({'status':'ok','mensaje':'Agencia actualizada'})
    except Exception as e:
        logger.error(f"Error en editar-agencia: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/admin/reporte-agencias')
@admin_required
def reporte_agencias():
    try:
        hoy = ahora_peru().strftime("%d/%m/%Y")
        with get_db() as db:
            ags = db.execute("SELECT * FROM agencias WHERE es_admin=0").fetchall()
            tickets = db.execute("SELECT * FROM tickets WHERE anulado=0 AND fecha LIKE ?",(hoy+'%',)).fetchall()
        data=[]
        tv=tp=tc=0
        
        for ag in ags:
            try:
                mts=[t for t in tickets if t['agencia_id']==ag['id']]
                ventas=sum(t['total'] for t in mts)
                pp=0
                pend=0
                for t in mts:
                    try:
                        with get_db() as db2:
                            p=calcular_premio_ticket(t['id'],db2)
                        if t['pagado']: 
                            pp+=p
                        else: 
                            pend+=p
                    except:
                        continue
                com=ventas*ag['comision']
                data.append({
                    'nombre':ag['nombre_agencia'],
                    'usuario':ag['usuario'],
                    'ventas':round(ventas,2),
                    'premios_pagados':round(pp,2),
                    'premios_pendientes':round(pend,2),
                    'comision':round(com,2),
                    'balance':round(ventas-pp-com,2),
                    'tickets':len(mts)
                })
                tv+=ventas
                tp+=pp
                tc+=com
            except Exception as e:
                logger.error(f"Error procesando agencia {ag['id']}: {e}")
                continue
                
        return jsonify({
            'agencias':data,
            'global':{
                'ventas':round(tv,2),
                'pagos':round(tp,2),
                'comisiones':round(tc,2),
                'balance':round(tv-tp-tc,2)
            }
        })
    except Exception as e:
        logger.error(f"Error en reporte-agencias: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/admin/reporte-agencias-rango', methods=['POST'])
@admin_required
def reporte_agencias_rango():
    try:
        data=request.get_json()
        if not data:
            return jsonify({'error':'Datos requeridos'}),400
            
        fi=data.get('fecha_inicio')
        ff=data.get('fecha_fin')
        if not fi or not ff: 
            return jsonify({'error':'Fechas requeridas'}),400
            
        dti=datetime.strptime(fi,"%Y-%m-%d")
        dtf=datetime.strptime(ff,"%Y-%m-%d").replace(hour=23,minute=59)
        
        with get_db() as db:
            ags=db.execute("SELECT * FROM agencias WHERE es_admin=0").fetchall()
            all_t=db.execute("SELECT * FROM tickets WHERE anulado=0 ORDER BY id DESC LIMIT 50000").fetchall()
            
        stats={ag['id']:{'nombre':ag['nombre_agencia'],'usuario':ag['usuario'],
                          'tickets':0,'ventas':0,'premios_teoricos':0,'premios_pagados':0,
                          'premios_pendientes':0,'comision_pct':ag['comision']} for ag in ags}
                          
        for t in all_t:
            try:
                dt=parse_fecha(t['fecha'])
                if not dt or dt<dti or dt>dtf: 
                    continue
                aid=t['agencia_id']
                if aid not in stats: 
                    continue
                stats[aid]['tickets']+=1
                stats[aid]['ventas']+=t['total']
                with get_db() as db2:
                    p=calcular_premio_ticket(t['id'],db2)
                stats[aid]['premios_teoricos']+=p
                if t['pagado']: 
                    stats[aid]['premios_pagados']+=p
                elif p>0: 
                    stats[aid]['premios_pendientes']+=p
            except Exception as e:
                logger.error(f"Error procesando ticket {t['id']}: {e}")
                continue
                
        out=[]
        for s in stats.values():
            if s['tickets']==0: 
                continue
            com=s['ventas']*s['comision_pct']
            s['comision']=round(com,2)
            s['balance']=round(s['ventas']-s['premios_teoricos']-com,2)
            for k in ['ventas','premios_teoricos','premios_pagados','premios_pendientes']:
                s[k]=round(s[k],2)
            out.append(s)
            
        out.sort(key=lambda x:x['ventas'],reverse=True)
        tv=sum(x['ventas'] for x in out)
        if tv>0:
            for x in out: 
                x['porcentaje_ventas']=round(x['ventas']/tv*100,1)
                
        total={
            'tickets':sum(x['tickets'] for x in out),
            'ventas':round(tv,2),
            'premios':round(sum(x['premios_teoricos'] for x in out),2),
            'comision':round(sum(x['comision'] for x in out),2),
            'balance':round(sum(x['balance'] for x in out),2)
        }
        
        return jsonify({
            'agencias':out,
            'total':total,
            'periodo':{'inicio':fi,'fin':ff}
        })
    except Exception as e:
        logger.error(f"Error en reporte-agencias-rango: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/admin/estadisticas-rango', methods=['POST'])
@admin_required
def estadisticas_rango():
    try:
        data=request.get_json()
        if not data:
            return jsonify({'error':'Datos requeridos'}),400
            
        fi=data.get('fecha_inicio')
        ff=data.get('fecha_fin')
        if not fi or not ff: 
            return jsonify({'error':'Fechas requeridas'}),400
            
        dti=datetime.strptime(fi,"%Y-%m-%d")
        dtf=datetime.strptime(ff,"%Y-%m-%d").replace(hour=23,minute=59)
        
        with get_db() as db:
            all_t=db.execute("SELECT * FROM tickets WHERE anulado=0 ORDER BY id DESC LIMIT 10000").fetchall()
            
        dias={}
        total_v=total_p=total_t=0
        
        for t in all_t:
            try:
                dt=parse_fecha(t['fecha'])
                if not dt or dt<dti or dt>dtf: 
                    continue
                dk=dt.strftime("%d/%m/%Y")
                if dk not in dias: 
                    dias[dk]={'ventas':0,'tickets':0,'ids':[]}
                dias[dk]['ventas']+=t['total']
                dias[dk]['tickets']+=1
                dias[dk]['ids'].append(t['id'])
                total_v+=t['total']
                total_t+=1
            except:
                continue
                
        resumen=[]
        total_p=0
        
        for dk in sorted(dias.keys()):
            try:
                d=dias[dk]
                prem=0
                for tid in d['ids']:
                    try:
                        with get_db() as db2:
                            prem+=calcular_premio_ticket(tid,db2)
                    except:
                        continue
                total_p+=prem
                cd=d['ventas']*COMISION_AGENCIA
                resumen.append({
                    'fecha':dk,
                    'ventas':round(d['ventas'],2),
                    'premios':round(prem,2),
                    'comisiones':round(cd,2),
                    'balance':round(d['ventas']-prem-cd,2),
                    'tickets':d['tickets']
                })
            except Exception as e:
                logger.error(f"Error procesando día {dk}: {e}")
                continue
                
        tc=total_v*COMISION_AGENCIA
        return jsonify({
            'resumen_por_dia':resumen,
            'totales':{
                'ventas':round(total_v,2),
                'premios':round(total_p,2),
                'comisiones':round(tc,2),
                'balance':round(total_v-total_p-tc,2),
                'tickets':total_t
            }
        })
    except Exception as e:
        logger.error(f"Error en estadisticas-rango: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/admin/riesgo')
@admin_required
def riesgo():
    try:
        hoy=ahora_peru().strftime("%d/%m/%Y")
        now=ahora_peru()
        am=now.hour*60+now.minute
        sorteo=None
        
        for h in HORARIOS_PERU:
            m=hora_a_min(h)
            if am>=m and am<m+60: 
                sorteo=h
                break
        if not sorteo:
            for h in HORARIOS_PERU:
                if (hora_a_min(h)-am)>MINUTOS_BLOQUEO: 
                    sorteo=h
                    break
        if not sorteo: 
            sorteo=HORARIOS_PERU[-1]
            
        with get_db() as db:
            tickets=db.execute("SELECT id FROM tickets WHERE anulado=0 AND fecha LIKE ?",(hoy+'%',)).fetchall()
            
        apuestas={}
        total=0
        
        for t in tickets:
            try:
                with get_db() as db:
                    jugs=db.execute("SELECT * FROM jugadas WHERE ticket_id=? AND tipo='animal' AND hora=?",(t['id'],sorteo)).fetchall()
                for j in jugs:
                    apuestas[j['seleccion']]=apuestas.get(j['seleccion'],0)+j['monto']
                    total+=j['monto']
            except:
                continue
                
        riesgo_d={}
        for sel,monto in sorted(apuestas.items(),key=lambda x:x[1],reverse=True):
            mult=PAGO_LECHUZA if sel=="40" else PAGO_ANIMAL_NORMAL
            riesgo_d[f"{sel} - {ANIMALES.get(sel,sel)}"]={
                'apostado':round(monto,2),
                'pagaria':round(monto*mult,2),
                'es_lechuza':sel=="40",
                'porcentaje':round(monto/total*100,1) if total>0 else 0
            }
            
        return jsonify({
            'riesgo':riesgo_d,
            'sorteo_objetivo':sorteo,
            'total_apostado':round(total,2)
        })
    except Exception as e:
        logger.error(f"Error en riesgo: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/admin/tripletas-hoy')
@admin_required
def tripletas_hoy():
    try:
        hoy=ahora_peru().strftime("%d/%m/%Y")
        with get_db() as db:
            trips=db.execute("SELECT tr.*,tk.serial,tk.agencia_id FROM tripletas tr JOIN tickets tk ON tr.ticket_id=tk.id WHERE tr.fecha=?",(hoy,)).fetchall()
            res_rows=db.execute("SELECT hora,animal FROM resultados WHERE fecha=?",(hoy,)).fetchall()
            res_dia={r['hora']:r['animal'] for r in res_rows}
            ags={ag['id']:ag['nombre_agencia'] for ag in db.execute("SELECT id,nombre_agencia FROM agencias").fetchall()}
            
        out=[]
        ganadoras=0
        
        for tr in trips:
            try:
                nums={tr['animal1'],tr['animal2'],tr['animal3']}
                salidos=list(dict.fromkeys([a for a in res_dia.values() if a in nums]))
                gano=len(salidos)==3
                if gano: 
                    ganadoras+=1
                out.append({
                    'id':tr['id'],
                    'serial':tr['serial'],
                    'agencia':ags.get(tr['agencia_id'],'?'),
                    'animal1':tr['animal1'],
                    'animal2':tr['animal2'],
                    'animal3':tr['animal3'],
                    'nombres':[ANIMALES.get(tr['animal1'],''),ANIMALES.get(tr['animal2'],''),ANIMALES.get(tr['animal3'],'')],
                    'monto':tr['monto'],
                    'premio':tr['monto']*PAGO_TRIPLETA if gano else 0,
                    'gano':gano,
                    'salieron':salidos,
                    'pagado':bool(tr['pagado'])
                })
            except:
                continue
                
        return jsonify({
            'tripletas':out,
            'total':len(out),
            'ganadoras':ganadoras,
            'total_premios':sum(x['premio'] for x in out)
        })
    except Exception as e:
        logger.error(f"Error en tripletas-hoy: {e}")
        return jsonify({'error':str(e)}),500

@app.route('/admin/exportar-csv', methods=['POST'])
@admin_required
def exportar_csv():
    try:
        data=request.get_json()
        if not data:
            return jsonify({'error':'Datos requeridos'}),400
            
        fi=data.get('fecha_inicio')
        ff=data.get('fecha_fin')
        if not fi or not ff: 
            return jsonify({'error':'Fechas requeridas'}),400
            
        dti=datetime.strptime(fi,"%Y-%m-%d")
        dtf=datetime.strptime(ff,"%Y-%m-%d").replace(hour=23,minute=59)
        
        with get_db() as db:
            ags=db.execute("SELECT * FROM agencias WHERE es_admin=0").fetchall()
            all_t=db.execute("SELECT * FROM tickets WHERE anulado=0 ORDER BY id DESC LIMIT 50000").fetchall()
            
        stats={ag['id']:{'nombre':ag['nombre_agencia'],'usuario':ag['usuario'],
                          'tickets':0,'ventas':0,'premios':0,'comision_pct':ag['comision']} for ag in ags}
                          
        for t in all_t:
            try:
                dt=parse_fecha(t['fecha'])
                if not dt or dt<dti or dt>dtf: 
                    continue
                aid=t['agencia_id']
                if aid not in stats: 
                    continue
                stats[aid]['tickets']+=1
                stats[aid]['ventas']+=t['total']
                if t['pagado']:
                    with get_db() as db2:
                        stats[aid]['premios']+=calcular_premio_ticket(t['id'],db2)
            except:
                continue
                
        out=io.StringIO()
        w=csv.writer(out)
        w.writerow(['REPORTE ZOOLO CASINO'])
        w.writerow([f'Periodo: {fi} al {ff}'])
        w.writerow([])
        w.writerow(['Agencia','Usuario','Tickets','Ventas','Premios','Comision','Balance'])
        tv=0
        
        for s in sorted(stats.values(),key=lambda x:x['ventas'],reverse=True):
            if s['tickets']==0: 
                continue
            com=s['ventas']*s['comision_pct']
            w.writerow([s['nombre'],s['usuario'],s['tickets'],
                        round(s['ventas'],2),round(s['premios'],2),round(com,2),
                        round(s['ventas']-s['premios']-com,2)])
            tv+=s['ventas']
            
        w.writerow([])
        w.writerow(['TOTAL','',sum(s['tickets'] for s in stats.values()),round(tv,2),'','',''])
        out.seek(0)
        
        return Response(
            out.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition':f'attachment; filename=reporte_{fi}_{ff}.csv'}
        )
    except Exception as e:
        logger.error(f"Error en exportar-csv: {e}")
        return jsonify({'error':str(e)}),500

# ==================== HTML ====================
LOGIN_HTML = '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ZOOLO CASINO</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:linear-gradient(135deg,#0a0a0a,#1a1a2e);min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:-apple-system,sans-serif;padding:20px}
.box{background:rgba(255,255,255,0.05);padding:40px 30px;border-radius:20px;border:2px solid #ffd700;width:100%;max-width:400px;text-align:center}
h2{color:#ffd700;margin-bottom:30px;font-size:1.8rem}
.fg{margin-bottom:20px;text-align:left}
.fg label{display:block;margin-bottom:8px;color:#aaa;font-size:.9rem}
.fg input{width:100%;padding:15px;border:1px solid #444;border-radius:10px;background:rgba(0,0,0,.5);color:white;font-size:1rem}
.fg input:focus{outline:none;border-color:#ffd700}
.btn{width:100%;padding:16px;background:linear-gradient(45deg,#ffd700,#ffed4e);color:black;border:none;border-radius:10px;font-size:1.1rem;font-weight:bold;cursor:pointer;margin-top:10px}
.err{background:rgba(255,0,0,.2);color:#ff6b6b;padding:12px;border-radius:8px;margin-bottom:20px}
.info{margin-top:25px;font-size:.8rem;color:#666}
</style></head><body>
<div class="box">
<h2> ZOOLO CASINO</h2>
{% if error %}<div class="err">{{error}}</div>{% endif %}
<form method="POST">
<div class="fg"><label>Usuario</label><input type="text" name="usuario" required autofocus autocomplete="off"></div>
<div class="fg"><label>Contraseña</label><input type="password" name="password" required></div>
<button type="submit" class="btn">INICIAR SESIÓN</button>
</form>
<div class="info">ZOOLO CASINO Local v1.1</div>
</div></body></html>'''

POS_HTML = '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1,user-scalable=no">
<title>POS - {{agencia}}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:#0a0a0a;color:white;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;min-height:100vh;display:flex;flex-direction:column}
.topbar{background:linear-gradient(90deg,#1a1a2e,#16213e);padding:10px 15px;display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #ffd700;position:sticky;top:0;z-index:1000;flex-wrap:wrap;gap:6px}
.topbar-title{color:#ffd700;font-weight:bold;font-size:1rem}
.topbar-btns{display:flex;gap:6px;flex-wrap:wrap}
.tbtn{padding:6px 12px;border:1px solid #555;background:#2d2d2d;color:#ccc;border-radius:6px;cursor:pointer;font-size:.78rem}
.tbtn:active{background:#ffd700;color:black}
.main{display:flex;flex-direction:column;flex:1;padding:10px;gap:10px}
.section-title{color:#ffd700;font-size:.85rem;font-weight:bold;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px}
.horas-grid{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.btn-hora{padding:8px 12px;background:#1a1a2e;border:2px solid #333;color:#aaa;border-radius:8px;cursor:pointer;font-size:.82rem;font-weight:bold;transition:all .2s}
.btn-hora.active{background:#ffd700;color:black;border-color:#ffd700}
.btn-hora.bloqueado{opacity:.4;cursor:not-allowed}
.tipos-grid{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.btn-tipo{padding:8px 14px;background:#111;border:2px solid #333;color:#aaa;border-radius:8px;cursor:pointer;font-size:.82rem;transition:all .2s}
.btn-tipo.active{background:#9b59b6;color:white;border-color:#9b59b6}
.animales-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(72px,1fr));gap:6px;margin-bottom:10px}
.animal-card{background:#111;border:2px solid #222;border-radius:8px;padding:8px 4px;text-align:center;cursor:pointer;transition:all .15s}
.animal-card:active{transform:scale(.95)}
.animal-card.active{border-color:#ffd700;background:#1a1500}
.animal-num{font-size:1.1rem;font-weight:bold}
.animal-nom{font-size:.65rem;color:#aaa;margin-top:2px}
.rojo .animal-num{color:#e74c3c}
.verde .animal-num{color:#27ae60}
.negro .animal-num{color:#aaa}
.esp-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-bottom:10px}
.btn-esp{padding:12px;background:#111;border:2px solid #333;color:#ddd;border-radius:8px;cursor:pointer;text-align:center;font-weight:bold;font-size:.9rem;transition:all .2s}
.btn-esp.active{border-color:#e74c3c;background:rgba(231,76,60,.15)}
.trip-section{background:#0d0d1a;border:2px solid #9b59b6;border-radius:10px;padding:12px;margin-bottom:10px}
.trip-animales{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
.trip-slot{flex:1;min-width:80px;background:#111;border:2px solid #333;border-radius:8px;padding:8px;text-align:center;cursor:pointer;font-size:.8rem}
.trip-slot.sel{border-color:#9b59b6;background:rgba(155,89,182,.2);color:#c39bd3}
.monto-row{display:flex;gap:8px;align-items:center;margin-bottom:10px}
.monto-row input{flex:1;padding:12px;background:#111;border:2px solid #444;border-radius:8px;color:white;font-size:1.1rem;text-align:center}
.monto-row input:focus{outline:none;border-color:#ffd700}
.monto-presets{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:8px}
.mpre{padding:7px 12px;background:#1a1a2e;border:1px solid #333;color:#aaa;border-radius:6px;cursor:pointer;font-size:.82rem}
.mpre:active{background:#ffd700;color:black}
.carrito-section{background:#0a0a14;border:2px solid #333;border-radius:10px;padding:12px}
.carrito-empty{color:#555;text-align:center;padding:15px;font-size:.9rem}
.carrito-item{display:flex;justify-content:space-between;align-items:center;padding:8px;border-bottom:1px solid #222;font-size:.85rem}
.carrito-item:last-child{border-bottom:none}
.ci-desc{color:#ddd;flex:1}
.ci-hora{color:#ffd700;font-size:.75rem}
.ci-monto{color:#27ae60;font-weight:bold;margin-right:8px}
.ci-del{background:#c0392b;color:white;border:none;border-radius:4px;padding:3px 8px;cursor:pointer;font-size:.75rem}
.carrito-total{text-align:right;color:#ffd700;font-weight:bold;font-size:1.1rem;margin-top:8px;padding-top:8px;border-top:1px solid #333}
.btn-add{width:100%;padding:13px;background:linear-gradient(135deg,#2980b9,#1a5276);color:white;border:none;border-radius:10px;font-size:1rem;font-weight:bold;cursor:pointer;margin-bottom:8px}
.btn-vender{width:100%;padding:16px;background:linear-gradient(135deg,#27ae60,#1e8449);color:white;border:none;border-radius:10px;font-size:1.1rem;font-weight:bold;cursor:pointer}
.btn-vender:disabled{opacity:.6}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.85);z-index:2000;overflow-y:auto;padding:10px}
.modal-content{background:#111;border-radius:14px;max-width:600px;margin:auto;padding:20px;border:1px solid #333}
.modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;padding-bottom:15px;border-bottom:1px solid #333}
.modal-header h3{color:#ffd700;font-size:1.1rem}
.btn-close{background:#333;color:white;border:none;border-radius:6px;padding:6px 12px;cursor:pointer}
.filter-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.filter-row input,.filter-row select{flex:1;min-width:110px;padding:10px;background:#000;border:1px solid #444;border-radius:8px;color:white;font-size:.85rem}
.btn-consultar{width:100%;padding:12px;background:linear-gradient(135deg,#2980b9,#1a5276);color:white;border:none;border-radius:8px;font-weight:bold;cursor:pointer;margin-bottom:10px}
.ticket-item{background:#0a0a0a;padding:13px;margin:7px 0;border-radius:10px;border-left:4px solid #2980b9}
.ticket-item.ganador{border-left-color:#27ae60;background:rgba(39,174,96,.08)}
.ticket-item.pendiente-pago{border-left-color:#f39c12;background:rgba(243,156,18,.08)}
.ticket-serial{color:#ffd700;font-weight:bold;font-size:1rem}
.ticket-info{color:#888;font-size:.82rem;margin-top:3px}
.ticket-premio{color:#27ae60;font-weight:bold;margin-top:4px}
.t-badge{display:inline-block;padding:3px 8px;border-radius:4px;font-size:.72rem;font-weight:bold;margin-top:4px}
.badge-pagado{background:#27ae60;color:white}
.badge-ganador{background:#f39c12;color:black}
.badge-pendiente{background:#333;color:#aaa}
.ticket-expand{display:none;margin-top:10px;border-top:1px solid #222;padding-top:10px}
.ticket-expand.open{display:block}
.jugada-row{display:flex;justify-content:space-between;align-items:center;padding:6px 10px;margin:3px 0;border-radius:6px;background:#111;font-size:.83rem}
.jugada-row.gano{background:rgba(39,174,96,.15);border-left:3px solid #27ae60}
.jugada-row.perdio{border-left:3px solid #333}
.jugada-row.sin-res{border-left:3px solid #2980b9}
.tripleta-row{padding:8px 10px;margin:3px 0;border-radius:6px;background:#0d0d1a;border-left:3px solid #9b59b6;font-size:.83rem}
.tripleta-row.gano{background:rgba(39,174,96,.15);border-left-color:#27ae60}
.jh{color:#ffd700;font-weight:bold;min-width:70px;font-size:.8rem}
.ja{color:#ddd;flex:1;margin:0 6px}
.jm{color:#aaa;min-width:40px;text-align:right}
.jr{color:#888;font-size:.76rem}
.jp{color:#27ae60;font-weight:bold;font-size:.88rem}
.sec-label{color:#ffd700;font-size:.75rem;font-weight:bold;text-transform:uppercase;margin:8px 0 4px;letter-spacing:1px}
.sec-label.tripleta{color:#9b59b6}
.toggle-btn{background:none;border:1px solid #444;color:#888;padding:2px 8px;border-radius:4px;font-size:.72rem;cursor:pointer;float:right}
.res-item{display:flex;justify-content:space-between;align-items:center;padding:10px;margin:6px 0;background:#0a0a0a;border-radius:8px;border-left:3px solid #333}
.res-item.tiene{border-left-color:#27ae60}
.res-hora{color:#ffd700;font-weight:bold;font-size:.88rem}
.res-animal{color:#27ae60;font-weight:bold}
.res-pend{color:#555;font-size:.85rem}
.toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#333;color:white;padding:12px 20px;border-radius:10px;z-index:9999;font-size:.9rem;display:none;max-width:90%}
.toast.success{background:#27ae60}.toast.error{background:#c0392b}
.caja-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:15px 0}
.caja-card{background:#0a0a0a;border-radius:10px;padding:15px;text-align:center;border:1px solid #333}
.caja-label{color:#888;font-size:.78rem;margin-bottom:5px}
.caja-val{color:#ffd700;font-size:1.3rem;font-weight:bold}
.caja-val.verde{color:#27ae60}.caja-val.rojo{color:#e74c3c}
.stats-box{background:#0a0a0a;border-radius:8px;padding:12px;margin:8px 0;border:1px solid #222}
.stat-row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1a1a1a;font-size:.85rem}
.stat-row:last-child{border-bottom:none}
.stat-label{color:#888}.stat-value{color:#ffd700;font-weight:bold}
</style></head><body>
<div class="topbar">
  <div class="topbar-title"> {{agencia}}</div>
  <div class="topbar-btns">
    <button class="tbtn" onclick="openModal('modal-resultados')"> Resultados</button>
    <button class="tbtn" onclick="openMisTickets()"> Tickets</button>
    <button class="tbtn" onclick="openCaja()"> Caja</button>
    <button class="tbtn" onclick="openAnular()"> Anular</button>
    <button class="tbtn" onclick="openBuscar()"> Buscar</button>
    <button class="tbtn" onclick="location.href='/logout'" style="color:#e74c3c">Salir</button>
  </div>
</div>
<div class="main">
  <div>
    <div class="section-title"> Seleccionar Sorteo</div>
    <div class="horas-grid" id="horas-grid"></div>
  </div>
  <div>
    <div class="section-title"> Tipo de Apuesta</div>
    <div class="tipos-grid">
      <button class="btn-tipo active" onclick="setTipo('animal',this)"> Animal</button>
      <button class="btn-tipo" onclick="setTipo('especial',this)"> Especial</button>
      <button class="btn-tipo" onclick="setTipo('tripleta',this)"> Tripleta</button>
    </div>
  </div>
  <div id="panel-animal">
    <div class="section-title"> Animales</div>
    <div class="animales-grid" id="animales-grid"></div>
  </div>
  <div id="panel-especial" style="display:none">
    <div class="section-title"> Especiales <small style="color:#666">(x2)</small></div>
    <div class="esp-grid">
      <button class="btn-esp" onclick="selEsp('ROJO',this)" style="color:#e74c3c"> ROJO</button>
      <button class="btn-esp" onclick="selEsp('NEGRO',this)"> NEGRO</button>
      <button class="btn-esp" onclick="selEsp('PAR',this)"> PAR</button>
      <button class="btn-esp" onclick="selEsp('IMPAR',this)"> IMPAR</button>
    </div>
  </div>
  <div id="panel-tripleta" style="display:none">
    <div class="section-title"> Tripleta <small style="color:#666">(x60 - Todo el dia)</small></div>
    <div class="trip-section">
      <div class="trip-animales">
        <div class="trip-slot" id="ts0" onclick="focusTripSlot(0)">Animal 1</div>
        <div class="trip-slot" id="ts1" onclick="focusTripSlot(1)">Animal 2</div>
        <div class="trip-slot" id="ts2" onclick="focusTripSlot(2)">Animal 3</div>
      </div>
      <div class="section-title" style="font-size:.75rem;margin-top:8px">Seleccionar animal:</div>
      <div class="animales-grid" id="trip-grid" style="max-height:200px;overflow-y:auto"></div>
    </div>
  </div>
  <div>
    <div class="section-title"> Monto (S/)</div>
    <div class="monto-presets">
      <button class="mpre" onclick="setMonto(1)">1</button>
      <button class="mpre" onclick="setMonto(2)">2</button>
      <button class="mpre" onclick="setMonto(5)">5</button>
      <button class="mpre" onclick="setMonto(10)">10</button>
      <button class="mpre" onclick="setMonto(20)">20</button>
      <button class="mpre" onclick="setMonto(50)">50</button>
    </div>
    <div class="monto-row">
      <input type="number" id="monto-input" value="1" min="0.5" step="0.5">
    </div>
  </div>
  <button class="btn-add" onclick="agregarAlCarrito()"> AGREGAR AL TICKET</button>
  <div class="carrito-section">
    <div class="section-title"> Ticket Actual</div>
    <div id="carrito-contenido"><div class="carrito-empty">Ticket vacio</div></div>
    <div id="carrito-total" style="display:none" class="carrito-total"></div>
  </div>
  <button class="btn-vender" onclick="vender()" id="btn-vender"> GENERAR TICKET</button>
</div>
<div class="toast" id="toast"></div>

<div class="modal" id="modal-resultados">
<div class="modal-content">
  <div class="modal-header"><h3> Resultados</h3><button class="btn-close" onclick="closeModal('modal-resultados')">x</button></div>
  <div class="filter-row"><input type="date" id="res-fecha"></div>
  <button class="btn-consultar" onclick="cargarResultadosFecha()">VER RESULTADOS</button>
  <div id="res-titulo" style="color:#ffd700;font-weight:bold;text-align:center;margin-bottom:10px"></div>
  <div id="res-lista"></div>
</div></div>

<div class="modal" id="modal-mis-tickets">
<div class="modal-content">
  <div class="modal-header"><h3> Mis Tickets</h3><button class="btn-close" onclick="closeModal('modal-mis-tickets')">x</button></div>
  <div class="filter-row">
    <input type="date" id="mt-inicio">
    <input type="date" id="mt-fin">
    <select id="mt-estado">
      <option value="todos">Todos</option>
      <option value="pagados">Pagados</option>
      <option value="pendientes">Pendientes</option>
      <option value="por_pagar">Con Premio</option>
    </select>
  </div>
  <button class="btn-consultar" onclick="consultarMisTickets()">BUSCAR</button>
  <div id="mt-resumen" style="display:none;background:rgba(255,215,0,.08);border-radius:8px;padding:10px;margin-bottom:10px;color:#ffd700;font-size:.88rem"></div>
  <div id="mt-lista" style="max-height:500px;overflow-y:auto"><p style="color:#555;text-align:center;padding:20px">Use los filtros y presione BUSCAR</p></div>
</div></div>

<div class="modal" id="modal-caja">
<div class="modal-content">
  <div class="modal-header"><h3> Caja</h3><button class="btn-close" onclick="closeModal('modal-caja')">x</button></div>
  <div id="caja-hoy"></div>
  <hr style="border-color:#333;margin:15px 0">
  <h4 style="color:#ffd700;margin-bottom:10px"> Historico</h4>
  <div class="filter-row">
    <input type="date" id="caja-ini">
    <input type="date" id="caja-fin">
  </div>
  <button class="btn-consultar" onclick="consultarCajaHist()">VER HISTORICO</button>
  <div id="caja-hist"></div>
</div></div>

<div class="modal" id="modal-anular">
<div class="modal-content">
  <div class="modal-header"><h3> Anular Ticket</h3><button class="btn-close" onclick="closeModal('modal-anular')">x</button></div>
  <label style="color:#aaa">Serial:</label>
  <input type="text" id="anular-serial" style="width:100%;padding:12px;background:#000;border:1px solid #444;border-radius:8px;color:white;margin:6px 0 12px;font-size:1rem">
  <button class="btn-consultar" style="background:linear-gradient(135deg,#c0392b,#922b21)" onclick="anularTicket()">ANULAR</button>
  <div id="anular-res" style="margin-top:12px"></div>
</div></div>

<div class="modal" id="modal-buscar">
<div class="modal-content">
  <div class="modal-header"><h3> Buscar Ticket</h3><button class="btn-close" onclick="closeModal('modal-buscar')">x</button></div>
  <label style="color:#aaa">Serial:</label>
  <input type="text" id="buscar-serial" style="width:100%;padding:12px;background:#000;border:1px solid #444;border-radius:8px;color:white;margin:6px 0 12px;font-size:1rem">
  <button class="btn-consultar" onclick="buscarTicket()">BUSCAR</button>
  <div id="buscar-res" style="margin-top:12px"></div>
</div></div>

<script>
const ANIMALES = {{ animales | tojson }};
const HORARIOS_PERU = {{ horarios_peru | tojson }};
const HORARIOS_VEN  = {{ horarios_venezuela | tojson }};
let carrito=[], tipoActual='animal', horaActual=null, selAnimal=null, selEspActual=null;
let tripSlotActivo=0, tripSeleccionados=[null,null,null];

function init(){
  renderHoras(); renderAnimales(); renderTripGrid();
  let hoy=new Date().toISOString().split('T')[0];
  document.getElementById('res-fecha').value=hoy;
  document.getElementById('mt-inicio').value=hoy;
  document.getElementById('mt-fin').value=hoy;
  document.getElementById('caja-ini').value=hoy;
  document.getElementById('caja-fin').value=hoy;
}

function renderHoras(){
  let g=document.getElementById('horas-grid'); g.innerHTML='';
  HORARIOS_PERU.forEach(h=>{
    let b=document.createElement('button');
    b.className='btn-hora'; b.textContent=h.replace(':00','');
    b.onclick=()=>selHora(h,b); g.appendChild(b);
  });
}

function renderAnimales(){
  let g=document.getElementById('animales-grid'); g.innerHTML='';
  let orden=['00','0','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','32','33','34','35','36','37','38','39','40'];
  let rojos=['1','3','5','7','9','12','14','16','18','19','21','23','25','27','30','32','34','36','37','39'];
  orden.forEach(k=>{
    if(!ANIMALES[k])return;
    let cls='animal-card '+(k==='0'||k==='00'?'verde':(rojos.includes(k)?'rojo':'negro'));
    let d=document.createElement('div'); d.className=cls;
    d.innerHTML='<div class="animal-num">'+k+'</div><div class="animal-nom">'+ANIMALES[k]+'</div>';
    d.onclick=()=>selAnimalCard(k,d); g.appendChild(d);
  });
}

function renderTripGrid(){
  let g=document.getElementById('trip-grid'); g.innerHTML='';
  let orden=['00','0','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','32','33','34','35','36','37','38','39','40'];
  orden.forEach(k=>{
    if(!ANIMALES[k])return;
    let d=document.createElement('div'); d.className='animal-card negro';
    d.innerHTML='<div class="animal-num" style="font-size:.95rem">'+k+'</div><div class="animal-nom">'+ANIMALES[k]+'</div>';
    d.onclick=()=>selTripAnimal(k,d); g.appendChild(d);
  });
}

function selHora(h,btn){
  document.querySelectorAll('.btn-hora').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); horaActual=h;
}

function setTipo(t,btn){
  tipoActual=t;
  document.querySelectorAll('.btn-tipo').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('panel-animal').style.display=t==='animal'?'block':'none';
  document.getElementById('panel-especial').style.display=t==='especial'?'block':'none';
  document.getElementById('panel-tripleta').style.display=t==='tripleta'?'block':'none';
  selAnimal=null; selEspActual=null;
  document.querySelectorAll('.animal-card').forEach(c=>c.classList.remove('active'));
  document.querySelectorAll('.btn-esp').forEach(b=>b.classList.remove('active'));
}

function selAnimalCard(k,el){
  document.querySelectorAll('#animales-grid .animal-card').forEach(c=>c.classList.remove('active'));
  el.classList.add('active'); selAnimal=k;
}

function selEsp(v,btn){
  document.querySelectorAll('.btn-esp').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); selEspActual=v;
}

function focusTripSlot(i){ tripSlotActivo=i; }

function selTripAnimal(k){
  tripSeleccionados[tripSlotActivo]=k;
  for(let i=0;i<3;i++){
    let sl=document.getElementById('ts'+i);
    if(tripSeleccionados[i]) sl.textContent=tripSeleccionados[i]+' '+ANIMALES[tripSeleccionados[i]].substring(0,5);
    else sl.textContent='Animal '+(i+1);
    sl.classList.toggle('sel',!!tripSeleccionados[i]);
  }
  if(tripSlotActivo<2) tripSlotActivo++;
}

function setMonto(v){ document.getElementById('monto-input').value=v; }

function agregarAlCarrito(){
  let monto=parseFloat(document.getElementById('monto-input').value)||0;
  if(monto<=0){toast('Ingrese un monto valido','error');return;}
  if(tipoActual==='tripleta'){
    if(tripSeleccionados.some(x=>x===null)){toast('Seleccione los 3 animales','error');return;}
    if(new Set(tripSeleccionados).size<3){toast('Los 3 animales deben ser diferentes','error');return;}
    carrito.push({tipo:'tripleta',hora:'TODO EL DIA',seleccion:tripSeleccionados.join(','),monto:monto,
                  desc:tripSeleccionados.map(n=>ANIMALES[n].substring(0,4)).join('-')+' x60'});
    tripSeleccionados=[null,null,null]; tripSlotActivo=0;
    ['ts0','ts1','ts2'].forEach((id,i)=>{let el=document.getElementById(id);el.textContent='Animal '+(i+1);el.classList.remove('sel');});
  } else if(tipoActual==='especial'){
    if(!selEspActual){toast('Seleccione tipo especial','error');return;}
    if(!horaActual){toast('Seleccione un horario','error');return;}
    carrito.push({tipo:'especial',hora:horaActual,seleccion:selEspActual,monto:monto,desc:selEspActual+' x2'});
  } else {
    if(!selAnimal){toast('Seleccione un animal','error');return;}
    if(!horaActual){toast('Seleccione un horario','error');return;}
    carrito.push({tipo:'animal',hora:horaActual,seleccion:selAnimal,monto:monto,desc:selAnimal+' - '+ANIMALES[selAnimal]});
  }
  renderCarrito(); toast('Agregado al ticket','success');
}

function renderCarrito(){
  let c=document.getElementById('carrito-contenido');
  let tot=document.getElementById('carrito-total');
  if(carrito.length===0){c.innerHTML='<div class="carrito-empty">Ticket vacio</div>';tot.style.display='none';return;}
  let html='',total=0;
  carrito.forEach((item,i)=>{
    total+=item.monto;
    html+='<div class="carrito-item">'+
      '<div class="ci-desc">'+item.desc+'<br><span class="ci-hora">'+item.hora+'</span></div>'+
      '<span class="ci-monto">S/'+item.monto+'</span>'+
      '<button class="ci-del" onclick="quitarItem('+i+')">x</button>'+
    '</div>';
  });
  c.innerHTML=html; tot.style.display='block'; tot.innerHTML='TOTAL: S/'+total.toFixed(2);
}

function quitarItem(i){ carrito.splice(i,1); renderCarrito(); }

async function vender(){
  if(carrito.length===0){toast('Ticket vacio','error');return;}
  let btn=document.getElementById('btn-vender');
  btn.disabled=true; btn.textContent=' Procesando...';
  try{
    let r=await fetch('/api/procesar-venta',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({jugadas:carrito.map(c=>({hora:c.hora,seleccion:c.seleccion,monto:c.monto,tipo:c.tipo}))})});
    let d=await r.json();
    if(d.error){toast(d.error,'error');}
    else{
      if(/Android|iPhone|iPad/i.test(navigator.userAgent)) window.location.href=d.url_whatsapp;
      else window.open(d.url_whatsapp,'_blank');
      carrito=[]; renderCarrito(); toast('Ticket generado!','success');
    }
  }catch(e){toast('Error de conexion','error');}
  finally{btn.disabled=false;btn.textContent=' GENERAR TICKET';}
}

function cargarResultadosFecha(){
  let f=document.getElementById('res-fecha').value;
  if(!f)return;
  let cont=document.getElementById('res-lista');
  cont.innerHTML='<p style="color:#555;text-align:center;padding:15px">Cargando...</p>';
  fetch('/api/resultados-fecha',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fecha:f})})
  .then(r=>r.json()).then(d=>{
    let fobj=new Date(f+'T00:00:00');
    document.getElementById('res-titulo').textContent=fobj.toLocaleDateString('es-PE',{weekday:'long',year:'numeric',month:'long',day:'numeric'});
    let html='';
    HORARIOS_PERU.forEach(h=>{
      let res=d.resultados[h];
      html+='<div class="res-item '+(res?'tiene':'')+'">'+
        '<span class="res-hora">'+h+'</span>'+
        (res?'<span class="res-animal">'+res.animal+' - '+res.nombre+'</span>':'<span class="res-pend">Pendiente</span>')+
      '</div>';
    });
    cont.innerHTML=html;
  }).catch(()=>{cont.innerHTML='<p style="color:#c0392b;text-align:center">Error</p>';});
}

function openMisTickets(){
  openModal('modal-mis-tickets');
  let hoy=new Date().toISOString().split('T')[0];
  document.getElementById('mt-inicio').value=hoy;
  document.getElementById('mt-fin').value=hoy;
}

function consultarMisTickets(){
  let ini=document.getElementById('mt-inicio').value;
  let fin=document.getElementById('mt-fin').value;
  let est=document.getElementById('mt-estado').value;
  if(!ini||!fin){toast('Seleccione fechas','error');return;}
  let lista=document.getElementById('mt-lista');
  lista.innerHTML='<p style="color:#555;text-align:center;padding:20px">Cargando...</p>';
  fetch('/api/mis-tickets',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({fecha_inicio:ini,fecha_fin:fin,estado:est})})
  .then(r=>r.json()).then(d=>{
    if(d.error){lista.innerHTML='<p style="color:#c0392b;text-align:center">'+d.error+'</p>';return;}
    document.getElementById('mt-resumen').style.display='block';
    document.getElementById('mt-resumen').textContent=d.totales.cantidad+' ticket(s) — Total: S/'+d.totales.ventas.toFixed(2);
    if(!d.tickets.length){lista.innerHTML='<p style="color:#555;text-align:center;padding:20px">Sin resultados</p>';return;}
    let html='';
    d.tickets.forEach((t,idx)=>{
      let bclass=t.pagado?'badge-pagado':(t.premio_calculado>0?'badge-ganador':'badge-pendiente');
      let btxt=t.pagado?' PAGADO':(t.premio_calculado>0?' GANADOR':' PENDIENTE');
      let tcls=t.pagado?'ganador':(t.premio_calculado>0?'pendiente-pago':'');
      let resumen='';
      if(t.jugadas&&t.jugadas.length){
        let gh={};
        t.jugadas.forEach(j=>{if(!gh[j.hora])gh[j.hora]=[];gh[j.hora].push(j);});
        Object.keys(gh).forEach(h=>{
          let its=gh[h].map(j=>{
            let n=j.tipo==='animal'?(ANIMALES[j.seleccion]||j.seleccion).substring(0,4).toUpperCase():j.seleccion;
            return n+'x'+j.monto;
          }).join(' ');
          resumen+='<span style="color:#aaa;font-size:.77rem">'+h+': '+its+'</span><br>';
        });
      }
      if(t.tripletas&&t.tripletas.length){
        t.tripletas.forEach(tr=>{
          resumen+='<span style="color:#9b59b6;font-size:.77rem"> '+tr.nombre1+'-'+tr.nombre2+'-'+tr.nombre3+' x'+tr.monto+'</span><br>';
        });
      }
      let det='<div class="ticket-expand" id="exp-'+idx+'">';
      if(t.jugadas&&t.jugadas.length){
        det+='<div class="sec-label"> Jugadas</div>';
        let gh={};
        t.jugadas.forEach(j=>{if(!gh[j.hora])gh[j.hora]=[];gh[j.hora].push(j);});
        Object.keys(gh).forEach(h=>{
          gh[h].forEach(j=>{
            let rc=j.gano?'gano':(j.resultado?'perdio':'sin-res');
            let rn=j.resultado_nombre?(j.resultado+' - '+j.resultado_nombre):(j.resultado||'Sin resultado');
            det+='<div class="jugada-row '+rc+'">'+
              '<span class="jh">'+j.hora+'</span>'+
              '<span class="ja">'+j.seleccion+' '+(j.nombre||'')+'</span>'+
              '<span class="jm">S/'+j.monto+'</span>'+
              '<span style="text-align:right;margin-left:6px">'+
                '<span class="jr">'+rn+'</span>'+
                (j.gano?'<br><span class="jp">+S/'+j.premio+'</span>':'')+
              '</span>'+
            '</div>';
          });
        });
      }
      if(t.tripletas&&t.tripletas.length){
        det+='<div class="sec-label tripleta"> Tripletas x60</div>';
        t.tripletas.forEach(tr=>{
          let sal=tr.salieron&&tr.salieron.length?'Salieron: '+tr.salieron.join(', ')+' ('+tr.salieron.length+'/3)':'Pendiente';
          det+='<div class="tripleta-row '+(tr.gano?'gano':'')+'">'+
            '<div style="display:flex;justify-content:space-between">'+
              '<b style="color:#c39bd3">'+tr.nombre1+' • '+tr.nombre2+' • '+tr.nombre3+'</b>'+
              '<span style="color:#aaa">S/'+tr.monto+' x60</span>'+
            '</div>'+
            '<div style="margin-top:4px;font-size:.8rem;display:flex;justify-content:space-between">'+
              '<span style="color:'+(tr.gano?'#27ae60':'#888')+'">'+sal+'</span>'+
              (tr.gano?'<span class="jp">+S/'+tr.premio+'</span>':'')+
            '</div>'+
          '</div>';
        });
      }
      if(t.premio_calculado>0){
        det+='<div style="text-align:right;margin-top:8px;padding-top:8px;border-top:1px solid #222">'+
          '<span style="color:#27ae60;font-weight:bold">PREMIO: S/'+t.premio_calculado.toFixed(2)+'</span></div>';
      }
      det+='</div>';
      html+='<div class="ticket-item '+tcls+'">'+
        '<div style="display:flex;justify-content:space-between;align-items:flex-start">'+
          '<div>'+
            '<div class="ticket-serial"> #'+t.serial+'</div>'+
            '<div class="ticket-info">'+t.fecha+'</div>'+
            '<div style="margin-top:4px;line-height:1.7">'+resumen+'</div>'+
          '</div>'+
          '<div style="text-align:right;min-width:90px">'+
            '<span class="t-badge '+bclass+'">'+btxt+'</span>'+
            '<div style="color:#ffd700;font-weight:bold;margin-top:4px">S/'+t.total+'</div>'+
            (t.premio_calculado>0?'<div class="ticket-premio" style="font-size:.9rem">+S/'+t.premio_calculado.toFixed(2)+'</div>':'')+
            '<button class="toggle-btn" onclick="toggleExp('+idx+')">▼ Detalle</button>'+
          '</div>'+
        '</div>'+det+'</div>';
    });
    lista.innerHTML=html;
  }).catch(()=>{lista.innerHTML='<p style="color:#c0392b;text-align:center">Error</p>';});
}

function toggleExp(i){
  let el=document.getElementById('exp-'+i);
  let open=el.classList.toggle('open');
  let btn=el.parentElement.querySelector('.toggle-btn');
  if(btn) btn.textContent=open?'▲ Ocultar':'▼ Detalle';
}

function openCaja(){
  openModal('modal-caja');
  fetch('/api/caja').then(r=>r.json()).then(d=>{
    if(d.error)return;
    let col=d.balance>=0?'verde':'rojo';
    document.getElementById('caja-hoy').innerHTML=
      '<h4 style="color:#ffd700;margin-bottom:10px"> HOY</h4>'+
      '<div class="caja-grid">'+
        '<div class="caja-card"><div class="caja-label">VENTAS</div><div class="caja-val">S/'+d.ventas.toFixed(2)+'</div></div>'+
        '<div class="caja-card"><div class="caja-label">PREMIOS PAGADOS</div><div class="caja-val rojo">S/'+d.premios.toFixed(2)+'</div></div>'+
        '<div class="caja-card"><div class="caja-label">COMISION</div><div class="caja-val">S/'+d.comision.toFixed(2)+'</div></div>'+
        '<div class="caja-card"><div class="caja-label">BALANCE</div><div class="caja-val '+col+'">S/'+d.balance.toFixed(2)+'</div></div>'+
      '</div>'+
      (d.tickets_pendientes>0?'<div style="background:rgba(243,156,18,.1);border:1px solid #f39c12;border-radius:8px;padding:10px;text-align:center;color:#f39c12"> '+d.tickets_pendientes+' ticket(s) ganador(es) sin cobrar</div>':'');
  });
}

function consultarCajaHist(){
  let ini=document.getElementById('caja-ini').value;
  let fin=document.getElementById('caja-fin').value;
  if(!ini||!fin){toast('Seleccione fechas','error');return;}
  let c=document.getElementById('caja-hist');
  c.innerHTML='<p style="color:#555;text-align:center;padding:10px">Cargando...</p>';
  fetch('/api/caja-historico',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({fecha_inicio:ini,fecha_fin:fin})})
  .then(r=>r.json()).then(d=>{
    if(d.error){c.innerHTML='<p style="color:#c0392b">'+d.error+'</p>';return;}
    let html='<div class="stats-box">';
    d.resumen_por_dia.forEach(dia=>{
      let col=dia.balance>=0?'#27ae60':'#e74c3c';
      html+='<div class="stat-row">'+
        '<span class="stat-label">'+dia.fecha+'</span>'+
        '<span style="font-size:.8rem;color:#aaa">V:'+dia.ventas+' P:'+dia.premios+'</span>'+
        '<span class="stat-value" style="color:'+col+'">S/'+dia.balance.toFixed(2)+'</span>'+
      '</div>';
    });
    html+='</div><div class="stats-box" style="margin-top:10px">'+
      '<div class="stat-row"><span class="stat-label">Total Ventas</span><span class="stat-value">S/'+d.totales.ventas.toFixed(2)+'</span></div>'+
      '<div class="stat-row"><span class="stat-label">Premios</span><span class="stat-value" style="color:#e74c3c">S/'+d.totales.premios.toFixed(2)+'</span></div>'+
      '<div class="stat-row"><span class="stat-label">Comision</span><span class="stat-value">S/'+d.totales.comision.toFixed(2)+'</span></div>'+
      '<div class="stat-row"><span class="stat-label">Balance</span><span class="stat-value" style="color:'+(d.totales.balance>=0?'#27ae60':'#e74c3c')+'">S/'+d.totales.balance.toFixed(2)+'</span></div>'+
    '</div>';
    c.innerHTML=html;
  });
}

function openAnular(){ openModal('modal-anular'); document.getElementById('anular-serial').value=''; document.getElementById('anular-res').innerHTML=''; }
function anularTicket(){
  let s=document.getElementById('anular-serial').value.trim();
  if(!s){toast('Ingrese serial','error');return;}
  fetch('/api/anular-ticket',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({serial:s})})
  .then(r=>r.json()).then(d=>{
    let c=document.getElementById('anular-res');
    if(d.status==='ok') c.innerHTML='<p style="color:#27ae60;text-align:center;padding:10px"> '+d.mensaje+'</p>';
    else c.innerHTML='<p style="color:#e74c3c;text-align:center;padding:10px"> '+d.error+'</p>';
  });
}

function openBuscar(){ openModal('modal-buscar'); document.getElementById('buscar-serial').value=''; document.getElementById('buscar-res').innerHTML=''; }
function buscarTicket(){
  let s=document.getElementById('buscar-serial').value.trim();
  if(!s){toast('Ingrese serial','error');return;}
  let c=document.getElementById('buscar-res');
  c.innerHTML='<p style="color:#555;text-align:center">Buscando...</p>';
  fetch('/api/consultar-ticket-detalle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({serial:s})})
  .then(r=>r.json()).then(d=>{
    if(d.error){c.innerHTML='<p style="color:#e74c3c;text-align:center">'+d.error+'</p>';return;}
    let t=d.ticket;
    let col=t.pagado?'#27ae60':(t.premio_total>0?'#f39c12':'#555');
    let est=t.pagado?' PAGADO':(t.premio_total>0?' GANADOR SIN COBRAR':' PENDIENTE');
    let html='<div style="border:2px solid '+col+';border-radius:10px;padding:15px">'+
      '<h3 style="color:#ffd700;text-align:center;margin-bottom:12px">Ticket #'+t.serial+'</h3>'+
      '<div class="stats-box">'+
        '<div class="stat-row"><span class="stat-label">Fecha</span><span class="stat-value" style="font-size:.9rem">'+t.fecha+'</span></div>'+
        '<div class="stat-row"><span class="stat-label">Apostado</span><span class="stat-value">S/'+t.total_apostado+'</span></div>'+
        '<div class="stat-row"><span class="stat-label">Estado</span><span class="stat-value" style="color:'+col+'">'+est+'</span></div>'+
        (t.premio_total>0?'<div class="stat-row"><span class="stat-label">Premio</span><span class="stat-value" style="color:#27ae60;font-size:1.1rem">S/'+t.premio_total.toFixed(2)+'</span></div>':'')+
      '</div>';
    if(d.jugadas&&d.jugadas.length){
      html+='<div class="sec-label" style="margin-top:12px"> Jugadas</div>';
      d.jugadas.forEach(j=>{
        let rc=j.gano?'gano':(j.resultado?'perdio':'sin-res');
        let rn=j.resultado_nombre?(j.resultado+' - '+j.resultado_nombre):(j.resultado||'Sin resultado');
        html+='<div class="jugada-row '+rc+'">'+
          '<span class="jh">'+j.hora+'</span>'+
          '<span class="ja">'+j.seleccion+' '+(j.nombre_seleccion||'')+'</span>'+
          '<span class="jm">S/'+j.monto+'</span>'+
          '<span style="text-align:right;margin-left:6px">'+
            '<span class="jr">'+rn+'</span>'+
            (j.gano?'<br><span class="jp">+S/'+j.premio+'</span>':'')+
          '</span>'+
        '</div>';
      });
    }
    if(d.tripletas&&d.tripletas.length){
      html+='<div class="sec-label tripleta" style="margin-top:12px"> Tripletas x60</div>';
      d.tripletas.forEach(tr=>{
        let sal=tr.salieron&&tr.salieron.length?'Salieron: '+tr.salieron.join(', ')+' ('+tr.salieron.length+'/3)':'Pendiente';
        html+='<div class="tripleta-row '+(tr.gano?'gano':'')+'">'+
          '<div style="display:flex;justify-content:space-between">'+
            '<b style="color:#c39bd3">'+tr.nombre1+' • '+tr.nombre2+' • '+tr.nombre3+'</b>'+
            '<span style="color:#aaa">S/'+tr.monto+' x60</span>'+
          '</div>'+
          '<div style="margin-top:4px;font-size:.8rem;display:flex;justify-content:space-between">'+
            '<span style="color:'+(tr.gano?'#27ae60':'#888')+'">'+sal+'</span>'+
            (tr.gano?'<span class="jp">+S/'+tr.premio+'</span>':'')+
          '</div>'+
        '</div>';
      });
    }
    if(!t.pagado&&t.premio_total>0){
      html+='<button onclick="cobrarDesdeDetalle('+t.id+')" style="width:100%;margin-top:12px;padding:12px;background:linear-gradient(135deg,#27ae60,#1e8449);color:white;border:none;border-radius:8px;font-weight:bold;cursor:pointer;font-size:1rem"> COBRAR S/'+t.premio_total.toFixed(2)+'</button>';
    }
    html+='</div>';
    c.innerHTML=html;
  });
}

function cobrarDesdeDetalle(tid){
  if(!confirm('Confirmar pago?'))return;
  fetch('/api/pagar-ticket',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticket_id:tid})})
  .then(r=>r.json()).then(d=>{
    if(d.status==='ok'){toast(' Ticket pagado','success');buscarTicket();}
    else toast(d.error||'Error','error');
  });
}

function openModal(id){ document.getElementById(id).style.display='block'; }
function closeModal(id){ document.getElementById(id).style.display='none'; }
function toast(msg,tipo){
  let t=document.getElementById('toast');
  t.textContent=msg; t.className='toast '+tipo; t.style.display='block';
  setTimeout(()=>t.style.display='none',3000);
}
document.addEventListener('DOMContentLoaded',init);
</script></body></html>'''

ADMIN_HTML = '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ADMIN - ZOOLO CASINO</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0a0a;color:white;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;min-height:100vh}
.topbar{background:linear-gradient(90deg,#1a0a00,#2d1600);padding:12px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #ffd700;position:sticky;top:0;z-index:100}
.topbar h1{color:#ffd700;font-size:1.1rem}
.tabs{display:flex;background:#111;border-bottom:2px solid #222;overflow-x:auto}
.tab{padding:12px 18px;cursor:pointer;color:#888;font-size:.85rem;white-space:nowrap;border-bottom:3px solid transparent;transition:all .2s}
.tab.active{color:#ffd700;border-bottom-color:#ffd700;background:#1a1a00}
.tab-content{display:none;padding:15px;max-width:900px;margin:auto}
.tab-content.active{display:block}
.form-box{background:#111;border-radius:12px;padding:18px;margin-bottom:15px;border:1px solid #222}
.form-box h3{color:#ffd700;margin-bottom:15px;font-size:1rem}
.form-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.form-row input,.form-row select{flex:1;min-width:120px;padding:10px;background:#000;border:1px solid #444;border-radius:8px;color:white;font-size:.88rem}
.form-row input:focus,.form-row select:focus{outline:none;border-color:#ffd700}
.btn-submit{padding:10px 18px;background:linear-gradient(135deg,#27ae60,#1e8449);color:white;border:none;border-radius:8px;font-weight:bold;cursor:pointer;font-size:.88rem;white-space:nowrap}
.btn-secondary{padding:8px 14px;background:#2d2d2d;color:#ccc;border:1px solid #444;border-radius:6px;cursor:pointer;font-size:.82rem}
.btn-danger{background:linear-gradient(135deg,#c0392b,#922b21);color:white;border:none;border-radius:8px;padding:10px 18px;font-weight:bold;cursor:pointer}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:20px}
.stat-card{background:#0a0a0a;border-radius:10px;padding:15px;text-align:center;border:1px solid #222}
.stat-card h3{color:#888;font-size:.75rem;text-transform:uppercase;margin-bottom:8px}
.stat-card p{color:#ffd700;font-size:1.4rem;font-weight:bold}
.stat-card p.verde{color:#27ae60}.stat-card p.rojo{color:#e74c3c}
.resultado-item{display:flex;justify-content:space-between;align-items:center;padding:10px;margin:5px 0;background:#0a0a0a;border-radius:8px;border-left:3px solid #333}
.resultado-item.tiene{border-left-color:#27ae60}
.btn-editar{padding:5px 12px;background:#2980b9;color:white;border:none;border-radius:5px;cursor:pointer;font-size:.78rem}
.msg{padding:10px;border-radius:8px;margin:8px 0;text-align:center;font-size:.88rem}
.msg.ok{background:rgba(39,174,96,.2);color:#27ae60;border:1px solid #27ae60}
.msg.err{background:rgba(192,57,43,.2);color:#e74c3c;border:1px solid #e74c3c}
table{width:100%;border-collapse:collapse;font-size:.82rem}
th{background:#1a1a1a;color:#ffd700;padding:10px;text-align:left;border-bottom:1px solid #333}
td{padding:8px 10px;border-bottom:1px solid #1a1a1a;color:#ccc}
tr:hover td{background:#111}
.riesgo-item{padding:10px;margin:5px 0;background:#0a0a0a;border-radius:8px;border-left:3px solid #2980b9;font-size:.85rem}
.riesgo-item.lechuza{border-left-color:#f39c12;background:rgba(243,156,18,.05)}
.ranking-item{display:flex;justify-content:space-between;align-items:center;padding:12px;margin:6px 0;background:#0a0a0a;border-radius:8px;border-left:3px solid #ffd700}
.trip-card{padding:10px;margin:5px 0;background:#0d0d1a;border-radius:8px;border-left:3px solid #9b59b6;font-size:.83rem}
.trip-card.ganadora{background:rgba(39,174,96,.1);border-left-color:#27ae60}
#global-msg{position:fixed;top:70px;left:50%;transform:translateX(-50%);z-index:9999;min-width:280px;display:none}
</style></head><body>
<div class="topbar">
  <h1> ZOOLO CASINO - Admin</h1>
  <button onclick="location.href='/logout'" style="background:#c0392b;color:white;border:none;padding:8px 14px;border-radius:6px;cursor:pointer">Salir</button>
</div>
<div id="global-msg"></div>
<div class="tabs">
  <div class="tab active" onclick="showTab('dashboard')"> Dashboard</div>
  <div class="tab" onclick="showTab('resultados')"> Resultados</div>
  <div class="tab" onclick="showTab('tripletas')"> Tripletas</div>
  <div class="tab" onclick="showTab('riesgo')"> Riesgo</div>
  <div class="tab" onclick="showTab('reportes')"> Reportes</div>
  <div class="tab" onclick="showTab('agencias')"> Agencias</div>
  <div class="tab" onclick="showTab('operaciones')"> Operaciones</div>
</div>

<div id="tab-dashboard" class="tab-content active">
  <div class="stats-grid">
    <div class="stat-card"><h3>VENTAS HOY</h3><p id="d-ventas">--</p></div>
    <div class="stat-card"><h3>PREMIOS PAGADOS</h3><p id="d-premios" class="rojo">--</p></div>
    <div class="stat-card"><h3>COMISIONES</h3><p id="d-comisiones">--</p></div>
    <div class="stat-card"><h3>BALANCE</h3><p id="d-balance">--</p></div>
  </div>
  <div class="form-box">
    <h3> Por Agencia (Hoy)</h3>
    <div id="dash-agencias"></div>
  </div>
</div>

<div id="tab-resultados" class="tab-content">
  <div class="form-box">
    <h3> Seleccionar Fecha</h3>
    <div class="form-row">
      <input type="date" id="res-admin-fecha">
      <button class="btn-submit" onclick="cargarResultadosAdmin()">VER</button>
    </div>
  </div>
  <div class="form-box">
    <h3> Resultados</h3>
    <div id="lista-resultados-admin" style="max-height:400px;overflow-y:auto">
      <p style="color:#555;text-align:center;padding:20px">Seleccione una fecha</p>
    </div>
  </div>
  <div class="form-box">
    <h3> Cargar / Editar Resultado</h3>
    <div class="form-row">
      <select id="res-hora">{% for h in horarios %}<option value="{{h}}">{{h}}</option>{% endfor %}</select>
      <select id="res-animal">{% for k,v in animales.items() %}<option value="{{k}}">{{k}} - {{v}}</option>{% endfor %}</select>
      <input type="date" id="res-fecha-input" style="max-width:160px">
      <button class="btn-submit" onclick="guardarResultado()"> GUARDAR</button>
    </div>
    <div id="res-msg"></div>
  </div>
</div>

<div id="tab-tripletas" class="tab-content">
  <div class="form-box">
    <h3> Tripletas de Hoy</h3>
    <button class="btn-submit" onclick="cargarTripletas()" style="margin-bottom:12px"> Actualizar</button>
    <div id="trip-stats" style="margin:12px 0"></div>
    <div id="trip-lista" style="max-height:500px;overflow-y:auto"></div>
  </div>
</div>

<div id="tab-riesgo" class="tab-content">
  <div class="form-box">
    <h3> Analisis de Riesgo</h3>
    <button class="btn-submit" onclick="cargarRiesgo()" style="margin-bottom:12px"> Actualizar</button>
    <div id="riesgo-info" style="margin:10px 0;color:#ffd700;font-weight:bold"></div>
    <div id="riesgo-lista" style="max-height:500px;overflow-y:auto"></div>
  </div>
</div>

<div id="tab-reportes" class="tab-content">
  <div class="form-box">
    <h3> Reporte por Rango</h3>
    <div class="form-row">
      <input type="date" id="rep-ini">
      <input type="date" id="rep-fin">
      <button class="btn-submit" onclick="generarReporte()">GENERAR</button>
      <button class="btn-secondary" onclick="exportarCSV()"> CSV</button>
    </div>
    <div id="rep-resumen" style="display:none">
      <div class="stats-grid" style="margin-top:15px">
        <div class="stat-card"><h3>VENTAS</h3><p id="rep-v">--</p></div>
        <div class="stat-card"><h3>PREMIOS</h3><p id="rep-p" class="rojo">--</p></div>
        <div class="stat-card"><h3>COMISION</h3><p id="rep-c">--</p></div>
        <div class="stat-card"><h3>BALANCE</h3><p id="rep-b">--</p></div>
      </div>
      <h4 style="color:#ffd700;margin:15px 0 10px">Detalle por dia</h4>
      <div style="overflow-x:auto"><table>
        <thead><tr><th>Fecha</th><th>Tickets</th><th>Ventas</th><th>Premios</th><th>Comision</th><th>Balance</th></tr></thead>
        <tbody id="rep-tabla"></tbody>
      </table></div>
      <h4 style="color:#ffd700;margin:15px 0 10px">Por Agencia</h4>
      <div id="rep-agencias"></div>
    </div>
  </div>
</div>

<div id="tab-agencias" class="tab-content">
  <div class="form-box">
    <h3> Nueva Agencia</h3>
    <div class="form-row">
      <input type="text" id="ag-usuario" placeholder="Usuario">
      <input type="password" id="ag-password" placeholder="Contrasena">
      <input type="text" id="ag-nombre" placeholder="Nombre agencia">
      <button class="btn-submit" onclick="crearAgencia()">CREAR</button>
    </div>
    <div id="ag-msg"></div>
  </div>
  <div class="form-box">
    <h3> Lista de Agencias</h3>
    <button class="btn-secondary" onclick="cargarAgencias()" style="margin-bottom:10px"> Actualizar</button>
    <div style="overflow-x:auto"><table>
      <thead><tr><th>ID</th><th>Usuario</th><th>Nombre</th><th>Comision</th><th>Estado</th><th>Acciones</th></tr></thead>
      <tbody id="tabla-agencias"></tbody>
    </table></div>
  </div>
</div>

<div id="tab-operaciones" class="tab-content">
  <div class="form-box">
    <h3> Verificar y Pagar Ticket</h3>
    <div class="form-row">
      <input type="text" id="op-serial" placeholder="Serial del ticket">
      <button class="btn-submit" onclick="verificarTicketAdmin()">VERIFICAR</button>
    </div>
    <div id="op-resultado"></div>
  </div>
  <div class="form-box">
    <h3> Anular Ticket</h3>
    <div class="form-row">
      <input type="text" id="an-serial" placeholder="Serial del ticket">
      <button class="btn-danger" onclick="anularTicketAdmin()">ANULAR</button>
    </div>
    <div id="an-resultado"></div>
  </div>
</div>

<script>
const ANIMALES = {{ animales | tojson }};
const HORARIOS = {{ horarios | tojson }};

function showTab(id){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  let tabs=['dashboard','resultados','tripletas','riesgo','reportes','agencias','operaciones'];
  let idx=tabs.indexOf(id);
  if(idx>=0) document.querySelectorAll('.tab')[idx].classList.add('active');
  if(id==='dashboard') cargarDashboard();
  if(id==='resultados'){ 
    let h=new Date().toISOString().split('T')[0]; 
    document.getElementById('res-admin-fecha').value=h; 
    document.getElementById('res-fecha-input').value=h; 
    cargarResultadosAdmin(); 
  }
  if(id==='tripletas') cargarTripletas();
  if(id==='riesgo') cargarRiesgo();
  if(id==='agencias') cargarAgencias();
}

function showMsg(id,msg,tipo){ 
  let el=document.getElementById(id); 
  el.innerHTML='<div class="msg '+tipo+'">'+msg+'</div>'; 
  setTimeout(()=>el.innerHTML='',4000); 
}

function showGlobal(msg,tipo){ 
  let el=document.getElementById('global-msg'); 
  el.innerHTML='<div class="msg '+tipo+'" style="background:#111;padding:12px 20px;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,.5)">'+msg+'</div>'; 
  el.style.display='block'; 
  setTimeout(()=>el.style.display='none',4000); 
}

function cargarDashboard(){
  fetch('/admin/reporte-agencias').then(r=>r.json()).then(d=>{
    if(d.error)return;
    document.getElementById('d-ventas').textContent='S/'+d.global.ventas.toFixed(2);
    document.getElementById('d-premios').textContent='S/'+d.global.pagos.toFixed(2);
    document.getElementById('d-comisiones').textContent='S/'+d.global.comisiones.toFixed(2);
    let b=d.global.balance, bp=document.getElementById('d-balance');
    bp.textContent='S/'+b.toFixed(2); bp.className=b>=0?'verde':'rojo';
    let html='';
    d.agencias.forEach(ag=>{
      html+='<div class="ranking-item">'+
        '<div><b style="color:#ffd700">'+ag.nombre+'</b><br><small style="color:#888">'+ag.tickets+' tickets</small></div>'+
        '<div style="text-align:right">'+
          '<div style="color:#27ae60;font-weight:bold">V: S/'+ag.ventas.toFixed(2)+'</div>'+
          '<div style="color:'+(ag.balance>=0?'#27ae60':'#e74c3c')+';font-size:.85rem">Bal: S/'+ag.balance.toFixed(2)+'</div>'+
        '</div>'+
      '</div>';
    });
    document.getElementById('dash-agencias').innerHTML=html||'<p style="color:#555;text-align:center;padding:20px">Sin actividad hoy</p>';
  });
}

function cargarResultadosAdmin(){
  let f=document.getElementById('res-admin-fecha').value;
  if(!f)return;
  let c=document.getElementById('lista-resultados-admin');
  c.innerHTML='<p style="color:#555;text-align:center;padding:15px">Cargando...</p>';
  fetch('/api/resultados-fecha-admin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fecha:f})})
  .then(r=>r.json()).then(d=>{
    let html='';
    HORARIOS.forEach(h=>{
      let res=d.resultados[h];
      html+='<div class="resultado-item '+(res?'tiene':'')+'">'+
        '<strong style="color:#ffd700">'+h+'</strong>'+
        '<div style="text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:4px">'+
          (res?'<span style="color:#27ae60;font-weight:bold">'+res.animal+' - '+res.nombre+'</span>':'<span style="color:#555">Pendiente</span>')+
          '<button class="btn-editar" onclick="preSelRes(\''+h+'\',\''+f+'\','+(res?'\''+res.animal+'\'':'null')+')">'+(res?' Editar':' Cargar')+'</button>'+
        '</div>'+
      '</div>';
    });
    c.innerHTML=html;
  });
}

function preSelRes(hora,fecha,animal){
  document.getElementById('res-hora').value=hora;
  document.getElementById('res-fecha-input').value=fecha;
  if(animal&&animal!=='null') document.getElementById('res-animal').value=animal;
  document.getElementById('res-hora').scrollIntoView({behavior:'smooth'});
}

function guardarResultado(){
  let hora=document.getElementById('res-hora').value;
  let animal=document.getElementById('res-animal').value;
  let fecha=document.getElementById('res-fecha-input').value;
  let form=new FormData();
  form.append('hora',hora); form.append('animal',animal);
  if(fecha) form.append('fecha',fecha);
  fetch('/admin/guardar-resultado',{method:'POST',body:form})
  .then(r=>r.json()).then(d=>{
    if(d.status==='ok'){ showMsg('res-msg',d.mensaje,'ok'); cargarResultadosAdmin(); }
    else showMsg('res-msg',d.error||'Error','err');
  }).catch(()=>showMsg('res-msg','Error de conexion','err'));
}

function cargarTripletas(){
  let l=document.getElementById('trip-lista');
  l.innerHTML='<p style="color:#555;text-align:center;padding:15px">Cargando...</p>';
  fetch('/admin/tripletas-hoy').then(r=>r.json()).then(d=>{
    document.getElementById('trip-stats').innerHTML=
      '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px">'+
        '<div class="stat-card" style="flex:1"><h3>TOTAL</h3><p>'+d.total+'</p></div>'+
        '<div class="stat-card" style="flex:1"><h3>GANADORAS</h3><p class="verde">'+d.ganadoras+'</p></div>'+
        '<div class="stat-card" style="flex:1"><h3>PREMIOS</h3><p class="rojo">S/'+d.total_premios.toFixed(2)+'</p></div>'+
      '</div>';
    if(!d.tripletas.length){l.innerHTML='<p style="color:#555;text-align:center;padding:20px">No hay tripletas hoy</p>';return;}
    let html='';
    d.tripletas.forEach(tr=>{
      html+='<div class="trip-card '+(tr.gano?'ganadora':'')+'">'+
        '<div style="display:flex;justify-content:space-between;align-items:center">'+
          '<div><b style="color:#c39bd3">'+tr.nombres[0]+' • '+tr.nombres[1]+' • '+tr.nombres[2]+'</b>'+
            '<span style="color:#555;font-size:.78rem;margin-left:8px">'+tr.agencia+'</span></div>'+
          '<div style="text-align:right"><div style="color:#aaa">S/'+tr.monto+' x60</div>'+
            (tr.gano?'<div style="color:#27ae60;font-weight:bold">+S/'+tr.premio+'</div>':'')+'</div>'+
        '</div>'+
        '<div style="margin-top:5px;font-size:.8rem;color:'+(tr.gano?'#27ae60':'#888')+'">'+
          (tr.salieron.length>0?'Salieron: '+tr.salieron.join(', ')+' ('+tr.salieron.length+'/3)':'Pendiente')+
        '</div>'+
        '<div style="font-size:.75rem;color:#555;margin-top:2px">Serial: '+tr.serial+'</div>'+
      '</div>';
    });
    l.innerHTML=html;
  });
}

function cargarRiesgo(){
  let l=document.getElementById('riesgo-lista');
  l.innerHTML='<p style="color:#555;text-align:center;padding:15px">Cargando...</p>';
  fetch('/admin/riesgo').then(r=>r.json()).then(d=>{
    document.getElementById('riesgo-info').textContent='Sorteo: '+(d.sorteo_objetivo||'N/A')+' | Total: S/'+((d.total_apostado||0).toFixed(2));
    if(!Object.keys(d.riesgo).length){l.innerHTML='<p style="color:#555;text-align:center;padding:20px">Sin apuestas</p>';return;}
    let html='';
    for(let k in d.riesgo){
      let v=d.riesgo[k];
      html+='<div class="riesgo-item '+(v.es_lechuza?'lechuza':'')+'">'+
        '<b>'+k+(v.es_lechuza?' ALTO RIESGO':'')+'</b><br>'+
        '<span style="color:#aaa;font-size:.82rem">Apostado: S/'+v.apostado.toFixed(2)+' | Pagaria: S/'+v.pagaria.toFixed(2)+' | '+v.porcentaje+'%</span>'+
      '</div>';
    }
    l.innerHTML=html;
  });
}

function generarReporte(){
  let ini=document.getElementById('rep-ini').value;
  let fin=document.getElementById('rep-fin').value;
  if(!ini||!fin){showGlobal('Seleccione fechas','err');return;}
  showGlobal('Generando...','ok');
  Promise.all([
    fetch('/admin/estadisticas-rango',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fecha_inicio:ini,fecha_fin:fin})}).then(r=>r.json()),
    fetch('/admin/reporte-agencias-rango',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fecha_inicio:ini,fecha_fin:fin})}).then(r=>r.json())
  ]).then(([est,ag])=>{
    document.getElementById('rep-resumen').style.display='block';
    document.getElementById('rep-v').textContent='S/'+est.totales.ventas.toFixed(2);
    document.getElementById('rep-p').textContent='S/'+est.totales.premios.toFixed(2);
    document.getElementById('rep-c').textContent='S/'+est.totales.comisiones.toFixed(2);
    let b=est.totales.balance, bp=document.getElementById('rep-b');
    bp.textContent='S/'+b.toFixed(2); bp.className=b>=0?'verde':'rojo';
    let tbody=document.getElementById('rep-tabla'); tbody.innerHTML='';
    est.resumen_por_dia.forEach(d=>{
      let col=d.balance>=0?'#27ae60':'#e74c3c';
      tbody.innerHTML+='<tr><td>'+d.fecha+'</td><td>'+d.tickets+'</td><td>S/'+d.ventas.toFixed(2)+'</td><td>S/'+d.premios.toFixed(2)+'</td><td>S/'+d.comisiones.toFixed(2)+'</td><td style="color:'+col+';font-weight:bold">S/'+d.balance.toFixed(2)+'</td></tr>';
    });
    let agHtml='';
    if(ag.agencias) ag.agencias.forEach(a=>{
      agHtml+='<div class="ranking-item">'+
        '<div><b style="color:#ffd700">'+a.nombre+'</b> <small style="color:#555">'+a.usuario+'</small><br>'+
          '<small style="color:#888">'+a.tickets+' tickets | '+(a.porcentaje_ventas||0)+'%</small></div>'+
        '<div style="text-align:right">'+
          '<div style="color:#aaa;font-size:.85rem">S/'+a.ventas.toFixed(2)+'</div>'+
          '<div style="color:'+(a.balance>=0?'#27ae60':'#e74c3c')+';font-weight:bold">Bal: S/'+a.balance.toFixed(2)+'</div>'+
        '</div>'+
      '</div>';
    });
    document.getElementById('rep-agencias').innerHTML=agHtml;
    showGlobal('Reporte generado','ok');
  }).catch(()=>showGlobal('Error','err'));
}

function exportarCSV(){
  let ini=document.getElementById('rep-ini').value;
  let fin=document.getElementById('rep-fin').value;
  if(!ini||!fin){showGlobal('Seleccione fechas','err');return;}
  fetch('/admin/exportar-csv',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fecha_inicio:ini,fecha_fin:fin})})
  .then(r=>r.blob()).then(b=>{
    let a=document.createElement('a'); a.href=URL.createObjectURL(b);
    a.download='reporte_'+ini+'_'+fin+'.csv'; a.click();
  });
}

function cargarAgencias(){
  fetch('/admin/lista-agencias').then(r=>r.json()).then(d=>{
    let t=document.getElementById('tabla-agencias'); t.innerHTML='';
    if(!d.length){t.innerHTML='<tr><td colspan="6" style="text-align:center;color:#555;padding:20px">Sin agencias</td></tr>';return;}
    d.forEach(a=>{
      t.innerHTML+='<tr>'+
        '<td>'+a.id+'</td><td>'+a.usuario+'</td><td>'+a.nombre_agencia+'</td>'+
        '<td>'+(a.comision*100).toFixed(0)+'%</td>'+
        '<td><span style="color:'+(a.activa?'#27ae60':'#e74c3c')+'">'+(a.activa?'Activa':'Inactiva')+'</span></td>'+
        '<td><button class="btn-secondary" onclick="toggleAgencia('+a.id+','+(a.activa?1:0)+')">'+(a.activa?'Desactivar':'Activar')+'</button></td>'+
      '</tr>';
    });
  });
}

function crearAgencia(){
  let u=document.getElementById('ag-usuario').value.trim();
  let p=document.getElementById('ag-password').value.trim();
  let n=document.getElementById('ag-nombre').value.trim();
  if(!u||!p||!n){showMsg('ag-msg','Complete todos los campos','err');return;}
  let form=new FormData();
  form.append('usuario',u); form.append('password',p); form.append('nombre',n);
  fetch('/admin/crear-agencia',{method:'POST',body:form}).then(r=>r.json()).then(d=>{
    if(d.status==='ok'){
      showMsg('ag-msg',' '+d.mensaje,'ok');
      document.getElementById('ag-usuario').value='';
      document.getElementById('ag-password').value='';
      document.getElementById('ag-nombre').value='';
      cargarAgencias();
    } else showMsg('ag-msg',' '+d.error,'err');
  });
}

function toggleAgencia(id,activa){
  fetch('/admin/editar-agencia',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id,activa:!activa})}).then(r=>r.json()).then(d=>{
    if(d.status==='ok') cargarAgencias();
    else showGlobal(d.error,'err');
  });
}

function verificarTicketAdmin(){
  let s=document.getElementById('op-serial').value.trim();
  if(!s)return;
  let c=document.getElementById('op-resultado');
  c.innerHTML='<p style="color:#555;text-align:center">Verificando...</p>';
  fetch('/api/verificar-ticket',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({serial:s})})
  .then(r=>r.json()).then(d=>{
    if(d.error){c.innerHTML='<div class="msg err">'+d.error+'</div>';return;}
    let col=d.total_ganado>0?'#27ae60':'#555';
    c.innerHTML='<div style="border:2px solid '+col+';border-radius:10px;padding:15px;margin-top:10px">'+
      '<div style="color:#ffd700;font-weight:bold;margin-bottom:10px">Ticket #'+s+'</div>'+
      '<div style="display:flex;justify-content:space-between;margin-bottom:10px">'+
        '<span style="color:#aaa">Premio:</span>'+
        '<span style="color:'+col+';font-weight:bold;font-size:1.2rem">S/'+d.total_ganado.toFixed(2)+'</span>'+
      '</div>'+
      (d.total_ganado>0?'<button onclick="pagarTicket('+d.ticket_id+')" style="width:100%;padding:12px;background:linear-gradient(135deg,#27ae60,#1e8449);color:white;border:none;border-radius:8px;font-weight:bold;cursor:pointer;font-size:1rem"> CONFIRMAR PAGO S/'+d.total_ganado.toFixed(2)+'</button>':'<div class="msg err">Sin premio</div>')+
    '</div>';
  });
}

function pagarTicket(tid){
  if(!confirm('Confirmar pago?'))return;
  fetch('/api/pagar-ticket',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticket_id:tid})})
  .then(r=>r.json()).then(d=>{
    if(d.status==='ok'){showGlobal(' Ticket pagado','ok');document.getElementById('op-resultado').innerHTML='';}
    else showGlobal(' '+d.error,'err');
  });
}

function anularTicketAdmin(){
  let s=document.getElementById('an-serial').value.trim();
  if(!s)return;
  if(!confirm('Anular ticket '+s+'?'))return;
  fetch('/api/anular-ticket',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({serial:s})})
  .then(r=>r.json()).then(d=>{
    let c=document.getElementById('an-resultado');
    if(d.status==='ok') c.innerHTML='<div class="msg ok"> '+d.mensaje+'</div>';
    else c.innerHTML='<div class="msg err"> '+d.error+'</div>';
  });
}

document.addEventListener('DOMContentLoaded',()=>{
  let hoy=new Date().toISOString().split('T')[0];
  document.getElementById('rep-ini').value=hoy;
  document.getElementById('rep-fin').value=hoy;
  document.getElementById('res-admin-fecha').value=hoy;
  document.getElementById('res-fecha-input').value=hoy;
  cargarDashboard();
});
</script>
</body></html>'''

# ==================== MAIN ====================
if __name__ == '__main__':
    try:
        init_db()
        port = int(os.environ.get('PORT', 5000))
        print("="*50)
        print("   ZOOLO CASINO LOCAL v1.1 (Estable)")
        print("="*50)
        print(f"   Base de datos: {DB_PATH}")
        print(f"   URL: http://localhost:{port}")
        print(f"   Admin: usuario=admin  password=admin123")
        print("="*50)
        print(f"   Para ngrok: ngrok http "+str(port))
        print("="*50)
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"Error fatal al iniciar: {e}")
        print(f"ERROR FATAL: {e}")
