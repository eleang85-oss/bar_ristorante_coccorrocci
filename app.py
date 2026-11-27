import os
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='static', template_folder='templates')
DB_FILE = os.path.join(os.path.dirname(__file__), 'coccorrocci.db')

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def safe_float(val, default=0.0):
    try:
        if val is None or str(val).strip() == '':
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0):
    try:
        if val is None or str(val).strip() == '':
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS reparti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL
        );
        INSERT OR IGNORE INTO reparti (id, nome) VALUES (1, 'BAR'), (2, 'RISTORANTE');

        CREATE TABLE IF NOT EXISTS ingredienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reparto_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            categoria TEXT,
            um TEXT DEFAULT 'Kg',
            prezzo_lordo REAL DEFAULT 0,
            perc_scarto REAL DEFAULT 0,
            costo_netto REAL DEFAULT 0,
            giacenza REAL DEFAULT 0,
            stock_minimo REAL DEFAULT 0,
            FOREIGN KEY (reparto_id) REFERENCES reparti (id)
        );

        CREATE TABLE IF NOT EXISTS ricette (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reparto_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            categoria TEXT,
            porzioni INTEGER DEFAULT 1,
            prezzo_lordo REAL DEFAULT 0,
            aliquota_iva REAL DEFAULT 10,
            target_fc REAL DEFAULT 30,
            FOREIGN KEY (reparto_id) REFERENCES reparti (id)
        );

        CREATE TABLE IF NOT EXISTS ricetta_ingredienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ricetta_id INTEGER NOT NULL,
            ingrediente_id INTEGER NOT NULL,
            qta_grezza REAL NOT NULL,
            FOREIGN KEY (ricetta_id) REFERENCES ricette (id) ON DELETE CASCADE,
            FOREIGN KEY (ingrediente_id) REFERENCES ingredienti (id)
        );

        CREATE TABLE IF NOT EXISTS movimenti_carico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingrediente_id INTEGER NOT NULL,
            data_ora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            quantita REAL NOT NULL,
            prezzo_lordo REAL NOT NULL,
            num_bolla TEXT,
            fornitore TEXT
        );

        CREATE TABLE IF NOT EXISTS movimenti_scarico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ricetta_id INTEGER NOT NULL,
            data_ora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            porzioni_vendute INTEGER NOT NULL
        );
    """)
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    base_dir = os.path.dirname(__file__)
    tpl_path = os.path.join(base_dir, 'templates', 'index.html')
    if os.path.exists(tpl_path):
        return render_template('index.html')
    root_tpl = os.path.join(base_dir, 'index.html')
    if os.path.exists(root_tpl):
        with open(root_tpl, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Bar Camping Coccorrocci App Live</h1><p>index.html non trovato.</p>", 404

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), filename)

@app.route('/api/reparti', methods=['GET'])
def get_reparti():
    conn = get_db()
    reparti = [dict(row) for row in conn.execute("SELECT * FROM reparti").fetchall()]
    conn.close()
    return jsonify(reparti)

@app.route('/api/ingredienti', methods=['GET', 'POST'])
def handle_ingredienti():
    conn = get_db()
    if request.method == 'POST':
        data = request.json or {}
        reparto_id = safe_int(data.get('reparto_id'), 1)
        nome = str(data.get('nome', '')).strip()
        categoria = str(data.get('categoria', '')).strip()
        um = str(data.get('um', 'Kg')).strip()
        prezzo_lordo = safe_float(data.get('prezzo_lordo'), 0.0)
        perc_scarto = safe_float(data.get('perc_scarto'), 0.0)
        giacenza = safe_float(data.get('giacenza'), 0.0)
        stock_minimo = safe_float(data.get('stock_minimo'), 0.0)

        costo_netto = prezzo_lordo / (1 - (perc_scarto / 100.0)) if perc_scarto < 100.0 else prezzo_lordo

        c = conn.cursor()
        c.execute("""
            INSERT INTO ingredienti (reparto_id, nome, categoria, um, prezzo_lordo, perc_scarto, costo_netto, giacenza, stock_minimo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (reparto_id, nome, categoria, um, prezzo_lordo, perc_scarto, costo_netto, giacenza, stock_minimo))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Ingrediente inserito!"})
    else:
        reparto_id = request.args.get('reparto_id')
        query = "SELECT i.*, r.nome as reparto_nome FROM ingredienti i JOIN reparti r ON i.reparto_id = r.id"
        params = []
        if reparto_id and str(reparto_id).strip().lower() != 'all':
            query += " WHERE i.reparto_id = ?"
            params.append(safe_int(reparto_id, 1))
        query += " ORDER BY i.nome ASC"
        items = [dict(row) for row in conn.execute(query, params).fetchall()]
        conn.close()
        return jsonify(items)

@app.route('/api/ricette', methods=['GET', 'POST'])
def handle_ricette():
    conn = get_db()
    if request.method == 'POST':
        data = request.json or {}
        reparto_id = safe_int(data.get('reparto_id'), 1)
        nome = str(data.get('nome', '')).strip()
        categoria = str(data.get('categoria', '')).strip()
        porzioni = safe_int(data.get('porzioni'), 1)
        prezzo_lordo = safe_float(data.get('prezzo_lordo'), 0.0)
        aliquota_iva = safe_float(data.get('aliquota_iva'), 10.0)
        target_fc = safe_float(data.get('target_fc'), 30.0)

        c = conn.cursor()
        c.execute("""
            INSERT INTO ricette (reparto_id, nome, categoria, porzioni, prezzo_lordo, aliquota_iva, target_fc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (reparto_id, nome, categoria, porzioni, prezzo_lordo, aliquota_iva, target_fc))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Ricetta creata!"})
    else:
        reparto_id = request.args.get('reparto_id')
        query = "SELECT r.*, rep.nome as reparto_nome FROM ricette r JOIN reparti rep ON r.reparto_id = rep.id"
        params = []
        if reparto_id and str(reparto_id).strip().lower() != 'all':
            query += " WHERE r.reparto_id = ?"
            params.append(safe_int(reparto_id, 1))
        query += " ORDER BY r.nome ASC"

        ricette = [dict(row) for row in conn.execute(query, params).fetchall()]

        for r in ricette:
            ings = conn.execute("""
                SELECT ri.qta_grezza, i.costo_netto
                FROM ricetta_ingredienti ri
                JOIN ingredienti i ON ri.ingrediente_id = i.id
                WHERE ri.ricetta_id = ?
            """, (r['id'],)).fetchall()

            costo_totale_ricetta = sum(safe_float(row['qta_grezza']) * safe_float(row['costo_netto']) for row in ings)
            porzioni = safe_int(r['porzioni'], 1)
            costo_porzione = costo_totale_ricetta / porzioni if porzioni > 0 else 0.0
            prezzo_lordo = safe_float(r['prezzo_lordo'], 0.0)
            aliquota_iva = safe_float(r['aliquota_iva'], 10.0)
            prezzo_netto = prezzo_lordo / (1.0 + (aliquota_iva / 100.0))
            food_cost_perc = (costo_porzione / prezzo_netto * 100.0) if prezzo_netto > 0 else 0.0
            margine = prezzo_netto - costo_porzione

            r['costo_totale'] = round(costo_totale_ricetta, 2)
            r['costo_porzione'] = round(costo_porzione, 2)
            r['prezzo_netto'] = round(prezzo_netto, 2)
            r['food_cost_perc'] = round(food_cost_perc, 1)
            r['margine'] = round(margine, 2)
            r['num_ingredienti'] = len(ings)

        conn.close()
        return jsonify(ricette)

@app.route('/api/ricette/<int:ricetta_id>/ingredienti', methods=['GET', 'POST'])
def handle_ricetta_ingredienti(ricetta_id):
    conn = get_db()
    if request.method == 'POST':
        data = request.json or {}
        ingrediente_id = safe_int(data.get('ingrediente_id'))
        qta_grezza = safe_float(data.get('qta_grezza'))
        conn.execute("""
            INSERT INTO ricetta_ingredienti (ricetta_id, ingrediente_id, qta_grezza)
            VALUES (?, ?, ?)
        """, (ricetta_id, ingrediente_id, qta_grezza))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    else:
        ings = [dict(row) for row in conn.execute("""
            SELECT ri.id as link_id, ri.qta_grezza, i.id as ing_id, i.nome, i.um, i.costo_netto, (ri.qta_grezza * i.costo_netto) as costo_linea
            FROM ricetta_ingredienti ri
            JOIN ingredienti i ON ri.ingrediente_id = i.id
            WHERE ri.ricetta_id = ?
        """, (ricetta_id,)).fetchall()]
        conn.close()
        return jsonify(ings)

@app.route('/api/ricette/ingredienti/<int:link_id>', methods=['DELETE'])
def delete_ricetta_ingrediente(link_id):
    conn = get_db()
    conn.execute("DELETE FROM ricetta_ingredienti WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/ricette/<int:ricetta_id>', methods=['DELETE'])
def delete_ricetta(ricetta_id):
    conn = get_db()
    conn.execute("DELETE FROM ricette WHERE id = ?", (ricetta_id,))
    conn.execute("DELETE FROM ricetta_ingredienti WHERE ricetta_id = ?", (ricetta_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/ingredienti/<int:ing_id>', methods=['DELETE'])
def delete_ingrediente(ing_id):
    conn = get_db()
    conn.execute("DELETE FROM ingredienti WHERE id = ?", (ing_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/carico', methods=['POST'])
def registra_carico():
    data = request.json or {}
    ingrediente_id = safe_int(data.get('ingrediente_id'))
    quantita = safe_float(data.get('quantita'))
    prezzo_lordo = safe_float(data.get('prezzo_lordo'))
    num_bolla = str(data.get('num_bolla', '')).strip()
    fornitore = str(data.get('fornitore', '')).strip()

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO movimenti_carico (ingrediente_id, quantita, prezzo_lordo, num_bolla, fornitore)
        VALUES (?, ?, ?, ?, ?)
    """, (ingrediente_id, quantita, prezzo_lordo, num_bolla, fornitore))

    ing = c.execute("SELECT giacenza, perc_scarto FROM ingredienti WHERE id = ?", (ingrediente_id,)).fetchone()
    if ing:
        nuova_giacenza = safe_float(ing['giacenza']) + quantita
        perc_scarto = safe_float(ing['perc_scarto'])
        costo_netto = prezzo_lordo / (1.0 - (perc_scarto / 100.0)) if perc_scarto < 100.0 else prezzo_lordo
        c.execute("""
            UPDATE ingredienti
            SET giacenza = ?, prezzo_lordo = ?, costo_netto = ?
            WHERE id = ?
        """, (nuova_giacenza, prezzo_lordo, costo_netto, ingrediente_id))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Carico registrato con successo!"})

@app.route('/api/scarico', methods=['POST'])
def registra_scarico():
    data = request.json or {}
    ricetta_id = safe_int(data.get('ricetta_id'))
    porzioni_vendute = safe_int(data.get('porzioni_vendute'), 1)

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO movimenti_scarico (ricetta_id, porzioni_vendute)
        VALUES (?, ?)
    """, (ricetta_id, porzioni_vendute))

    ricetta = c.execute("SELECT porzioni FROM ricette WHERE id = ?", (ricetta_id,)).fetchone()
    porzioni_base = safe_int(ricetta['porzioni'], 1) if ricetta else 1
    moltiplicatore = porzioni_vendute / porzioni_base if porzioni_base > 0 else 1.0

    ings = c.execute("""
        SELECT ingrediente_id, qta_grezza FROM ricetta_ingredienti WHERE ricetta_id = ?
    """, (ricetta_id,)).fetchall()

    for item in ings:
        qta_totale_usata = safe_float(item['qta_grezza']) * moltiplicatore
        c.execute("""
            UPDATE ingredienti SET giacenza = giacenza - ? WHERE id = ?
        """, (qta_totale_usata, item['ingrediente_id']))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": f"Scarico registrato per {porzioni_vendute} porzioni!"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
