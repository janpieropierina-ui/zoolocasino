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
            .then(d => {
                document.getElementById('resultado-historico').style.display = 'block';
                document.getElementById('hist-ventas').textContent = 'S/' + (d.ventas || 0).toFixed(2);
                document.getElementById('hist-balance').textContent = 'S/' + (d.balance || 0).toFixed(2);
            })
            .catch(e => alert('Error: ' + e));
        }
        
        function cerrarModal() {
            document.getElementById('modal-caja').style.display = 'none';
        }
        
        function pagar() {
            let serial = prompt('Ingrese SERIAL del ticket:');
            if (!serial) return;
            fetch('/api/verificar-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) { alert(d.error); return; }
                if (d.total_ganado === 0) { alert('No tiene premio'); return; }
                if (confirm('GANO: S/' + d.total_ganado + '\n¿Pagar ahora?')) {
                    fetch('/api/pagar-ticket', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ticket_id: d.ticket_id})
                    })
                    .then(() => alert('Ticket pagado!'))
                    .catch(e => alert('Error: ' + e));
                }
            })
            .catch(e => alert('Error: ' + e));
        }
        
        function anular() {
            let serial = prompt('Ingrese SERIAL del ticket a anular:');
            if (!serial) return;
            if (!confirm('¿Seguro de anular este ticket?')) return;
            fetch('/api/anular-ticket', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({serial: serial})
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) alert(d.error);
                else alert(d.mensaje);
            })
            .catch(e => alert('Error: ' + e));
        }
        
        function borrarTodo() {
            if (confirm('¿Borrar todo el carrito?')) {
                carrito = [];
                seleccionados = [];
                especiales = [];
                horariosSel = [];
                document.querySelectorAll('.active').forEach(el => el.classList.remove('active'));
                updateTicket();
            }
        }
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
    <title>Admin - ZOOLO CASINO</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0a0a0a; color: white; font-family: 'Segoe UI', sans-serif;
            padding: 20px; min-height: 100vh;
        }
        h2 { color: #ffd700; text-align: center; margin-bottom: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .section {
            background: #1a1a2e; border: 1px solid #333; border-radius: 10px;
            padding: 20px; margin-bottom: 20px;
        }
        .section h3 { color: #ffd700; margin-bottom: 15px; border-bottom: 1px solid #444; padding-bottom: 10px; }
        .form-row { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
        input, select {
            background: #0a0a0a; color: white; border: 1px solid #444;
            padding: 10px; border-radius: 5px; font-size: 1rem;
        }
        button {
            background: #2980b9; color: white; border: none;
            padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold;
        }
        button:hover { background: #3498db; }
        .btn-guardar { background: #27ae60; }
        .btn-guardar:hover { background: #2ecc71; }
        .btn-cargar { background: #f39c12; color: black; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9rem; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #333; }
        th { background: #222; color: #ffd700; }
        tr:hover { background: #252540; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 20px; border-radius: 10px; border: 1px solid #444;
            text-align: center;
        }
        .stat-card h4 { color: #888; font-size: 0.9rem; margin-bottom: 10px; }
        .stat-card .value { color: #ffd700; font-size: 1.8rem; font-weight: bold; }
        .logout-btn {
            position: fixed; top: 20px; right: 20px;
            background: #c0392b; color: white; padding: 10px 20px;
            border-radius: 5px; text-decoration: none;
        }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 2px solid #333; }
        .tab-btn {
            background: transparent; color: #888; border: none;
            padding: 10px 20px; cursor: pointer; font-size: 1rem;
            border-bottom: 2px solid transparent;
        }
        .tab-btn.active { color: #ffd700; border-bottom-color: #ffd700; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .riesgo-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 10px; margin-top: 15px;
        }
        .riesgo-item {
            background: #0a0a0a; padding: 15px; border-radius: 5px;
            border-left: 4px solid #c0392b;
        }
        .riesgo-item.lechuza { border-left-color: #ffd700; }
        .riesgo-item .nombre { color: #888; font-size: 0.8rem; }
        .riesgo-item .monto { color: white; font-size: 1.1rem; font-weight: bold; }
        .riesgo-item .pago { color: #c0392b; font-size: 0.9rem; }
        .riesgo-item.lechuza .pago { color: #ffd700; }
    </style>
</head>
<body>
    <a href="/logout" class="logout-btn">SALIR</a>
    <div class="container">
        <h2>PANEL DE ADMINISTRACION</h2>
        
        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('resultados')">Resultados</button>
            <button class="tab-btn" onclick="showTab('agencias')">Agencias</button>
            <button class="tab-btn" onclick="showTab('reportes')">Reportes</button>
            <button class="tab-btn" onclick="showTab('riesgo')">Riesgo</button>
        </div>

        <div id="tab-resultados" class="tab-content active">
            <div class="section">
                <h3>Cargar Resultado del Dia</h3>
                <div class="form-row">
                    <select id="hora-resultado">
                        {% for h in horarios %}
                        <option value="{{h}}">{{h}}</option>
                        {% endfor %}
                    </select>
                    <select id="animal-resultado">
                        {% for k, v in animales.items() %}
                        <option value="{{k}}">{{k}} - {{v}}</option>
                        {% endfor %}
                    </select>
                    <button class="btn-guardar" onclick="guardarResultado()">GUARDAR RESULTADO</button>
                </div>
                <div id="msg-resultado" style="margin-top:10px;color:#27ae60;"></div>
            </div>
        </div>

        <div id="tab-agencias" class="tab-content">
            <div class="section">
                <h3>Crear Nueva Agencia</h3>
                <div class="form-row">
                    <input type="text" id="new-usuario" placeholder="Usuario (solo minusculas)">
                    <input type="text" id="new-nombre" placeholder="Nombre de la Agencia">
                    <input type="text" id="new-pass" placeholder="Contrasena">
                    <button class="btn-guardar" onclick="crearAgencia()">CREAR AGENCIA</button>
                </div>
                <div id="msg-agencia" style="margin-top:10px;"></div>
            </div>
            
            <div class="section">
                <h3>Lista de Agencias</h3>
                <button class="btn-cargar" onclick="cargarAgencias()">Actualizar Lista</button>
                <table>
                    <thead>
                        <tr><th>ID</th><th>Usuario</th><th>Nombre</th><th>Comision</th></tr>
                    </thead>
                    <tbody id="lista-agencias"></tbody>
                </table>
            </div>
        </div>

        <div id="tab-reportes" class="tab-content">
            <div class="section">
                <h3>Reporte de Hoy</h3>
                <button class="btn-cargar" onclick="cargarReporte()">Cargar Reporte</button>
                <div class="stats" style="margin-top:15px;">
                    <div class="stat-card">
                        <h4>VENTAS TOTALES</h4>
                        <div class="value" id="rep-ventas">S/0</div>
                    </div>
                    <div class="stat-card">
                        <h4>PREMIOS PAGADOS</h4>
                        <div class="value" id="rep-premios">S/0</div>
                    </div>
                    <div class="stat-card">
                        <h4>COMISIONES</h4>
                        <div class="value" id="rep-comisiones">S/0</div>
                    </div>
                    <div class="stat-card">
                        <h4>BALANCE</h4>
                        <div class="value" id="rep-balance">S/0</div>
                    </div>
                </div>
                <table>
                    <thead>
                        <tr><th>Agencia</th><th>Ventas</th><th>Premios</th><th>Comision</th><th>Balance</th></tr>
                    </thead>
                    <tbody id="tabla-reporte"></tbody>
                </table>
            </div>
        </div>

        <div id="tab-riesgo" class="tab-content">
            <div class="section">
                <h3>Analisis de Riesgo - Apuestas de Hoy</h3>
                <button class="btn-cargar" onclick="cargarRiesgo()">Actualizar</button>
                <div id="riesgo-container" class="riesgo-grid"></div>
            </div>
        </div>
    </div>

    <script>
        function showTab(tab) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            event.target.classList.add('active');
        }

        function guardarResultado() {
            const hora = document.getElementById('hora-resultado').value;
            const animal = document.getElementById('animal-resultado').value;
            
            const formData = new FormData();
            formData.append('hora', hora);
            formData.append('animal', animal);
            
            fetch('/admin/guardar-resultado', {
                method: 'POST',
                body: formData
            })
            .then(r => r.json())
            .then(d => {
                document.getElementById('msg-resultado').textContent = d.mensaje || d.error;
            });
        }

        function crearAgencia() {
            const usuario = document.getElementById('new-usuario').value;
            const nombre = document.getElementById('new-nombre').value;
            const pass = document.getElementById('new-pass').value;
            
            if (!usuario || !nombre || !pass) {
                alert('Complete todos los campos');
                return;
            }
            
            const formData = new FormData();
            formData.append('usuario', usuario);
            formData.append('nombre', nombre);
            formData.append('password', pass);
            
            fetch('/admin/crear-agencia', {
                method: 'POST',
                body: formData
            })
            .then(r => r.json())
            .then(d => {
                const msg = document.getElementById('msg-agencia');
                msg.textContent = d.mensaje || d.error;
                msg.style.color = d.error ? '#c0392b' : '#27ae60';
                if (!d.error) {
                    document.getElementById('new-usuario').value = '';
                    document.getElementById('new-nombre').value = '';
                    document.getElementById('new-pass').value = '';
                }
            });
        }

        function cargarAgencias() {
            fetch('/admin/lista-agencias')
            .then(r => r.json())
            .then(d => {
                const tbody = document.getElementById('lista-agencias');
                tbody.innerHTML = d.map(a => `
                    <tr>
                        <td>${a.id}</td>
                        <td>${a.usuario}</td>
                        <td>${a.nombre_agencia}</td>
                        <td>${(a.comision * 100).toFixed(0)}%</td>
                    </tr>
                `).join('');
            });
        }

        function cargarReporte() {
            fetch('/admin/reporte-agencias')
            .then(r => r.json())
            .then(d => {
                if (d.error) { alert(d.error); return; }
                document.getElementById('rep-ventas').textContent = 'S/' + d.global.ventas.toFixed(2);
                document.getElementById('rep-premios').textContent = 'S/' + d.global.pagos.toFixed(2);
                document.getElementById('rep-comisiones').textContent = 'S/' + d.global.comisiones.toFixed(2);
                document.getElementById('rep-balance').textContent = 'S/' + d.global.balance.toFixed(2);
                
                const tbody = document.getElementById('tabla-reporte');
                tbody.innerHTML = d.agencias.map(a => `
                    <tr>
                        <td>${a.nombre}</td>
                        <td>S/${a.ventas.toFixed(2)}</td>
                        <td>S/${a.premios.toFixed(2)}</td>
                        <td>S/${a.comision.toFixed(2)}</td>
                        <td style="color:${a.balance >= 0 ? '#27ae60' : '#c0392b'}">S/${a.balance.toFixed(2)}</td>
                    </tr>
                `).join('');
            });
        }

        function cargarRiesgo() {
            fetch('/admin/riesgo')
            .then(r => r.json())
            .then(d => {
                if (d.error) { alert(d.error); return; }
                const container = document.getElementById('riesgo-container');
                container.innerHTML = Object.entries(d.riesgo).map(([k, v]) => `
                    <div class="riesgo-item ${v.es_lechuza ? 'lechuza' : ''}">
                        <div class="nombre">${k}</div>
                        <div class="monto">Apostado: S/${v.apostado.toFixed(2)}</div>
                        <div class="pago">Pagaria: S/${v.pagaria.toFixed(2)}</div>
                    </div>
                `).join('');
            });
        }
        
        // Cargar datos al iniciar
        cargarAgencias();
        cargarReporte();
    </script>
</body>
</html>
'''

# ==================== INICIAR ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
