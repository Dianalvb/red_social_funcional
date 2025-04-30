from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2

app = Flask(__name__)
app.secret_key = 'clave_secreta'

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="red_social",
        user="postgres",
        password="Itzcoatl1",
        options="-c client_encoding=UTF8"
    )

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id_usuario, nombre FROM Usuarios WHERE correo = %s AND contrasena = %s", (correo, contrasena))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            session['id_usuario'] = user[0]
            session['nombre'] = user[1]
            return redirect(url_for('inicio'))
        else:
            return "Credenciales incorrectas"
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO Usuarios (nombre, correo, contrasena) VALUES (%s, %s, %s)", (nombre, correo, contrasena))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('login'))
    return render_template('registro.html')

@app.route('/inicio')
def inicio():
    if 'id_usuario' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT p.id_publicacion, u.nombre, p.contenido FROM Publicaciones p JOIN Usuarios u ON p.id_usuario = u.id_usuario ORDER BY p.fecha_hora DESC")
    publicaciones = cur.fetchall()
    publicaciones_con_comentarios = []
    for pub in publicaciones:
        cur.execute("SELECT texto FROM Comentarios WHERE id_publicacion = %s", (pub[0],))
        comentarios = cur.fetchall()
        publicaciones_con_comentarios.append({
            'id': pub[0],
            'usuario': pub[1],
            'contenido': pub[2],
            'comentarios': comentarios
        })
    cur.close()
    conn.close()
    return render_template('YourPost.html', publicaciones=publicaciones_con_comentarios, usuario=session['nombre'], id_usuario=session['id_usuario'])

@app.route('/publicar', methods=['POST'])
def publicar():
    if 'id_usuario' not in session:
        return redirect(url_for('login'))
    contenido = request.form['contenido']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO Publicaciones (id_usuario, contenido) VALUES (%s, %s)", (session['id_usuario'], contenido))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('inicio'))

@app.route('/comentar', methods=['POST'])
def comentar():
    if 'id_usuario' not in session:
        return redirect(url_for('login'))
    id_publicacion = request.form['id_publicacion']
    texto = request.form['texto']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO Comentarios (id_publicacion, id_usuario, texto) VALUES (%s, %s, %s)", (id_publicacion, session['id_usuario'], texto))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('inicio'))

@app.route('/explorar')
def explorar():
    if 'id_usuario' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id_publicacion, u.id_usuario, u.nombre, p.contenido, p.fecha_hora
        FROM Publicaciones p
        JOIN Usuarios u ON p.id_usuario = u.id_usuario
        ORDER BY p.fecha_hora DESC
    """)
    publicaciones = cur.fetchall()

    publicaciones_data = []
    for pub in publicaciones:
        id_publicacion, id_usuario, nombre, contenido, fecha_hora = pub
        cur.execute("SELECT COUNT(*) FROM Reacciones WHERE id_publicacion = %s", (id_publicacion,))
        likes = cur.fetchone()[0]
        publicaciones_data.append({
            'id_publicacion': id_publicacion,
            'id_usuario': id_usuario,
            'nombre': nombre,
            'contenido': contenido,
            'fecha_hora': fecha_hora,
            'likes': likes
        })

    cur.close()
    conn.close()

    return render_template('explorar.html', publicaciones=publicaciones_data)

@app.route('/perfil/<int:id_usuario>')
def perfil(id_usuario):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT nombre FROM Usuarios WHERE id_usuario = %s", (id_usuario,))
    usuario = cur.fetchone()
    if not usuario:
        return "Usuario no encontrado"

    nombre_usuario = usuario[0]

    cur.execute("""
        SELECT id_publicacion, contenido 
        FROM Publicaciones 
        WHERE id_usuario = %s 
        ORDER BY fecha_hora DESC
    """, (id_usuario,))
    publicaciones = cur.fetchall()

    publicaciones_data = []
    for pub in publicaciones:
        pub_id, contenido = pub
        cur.execute("SELECT COUNT(*) FROM Reacciones WHERE id_publicacion = %s", (pub_id,))
        likes = cur.fetchone()[0]
        publicaciones_data.append({
            'id': pub_id,
            'contenido': contenido,
            'likes': likes
        })

    cur.close()
    conn.close()

    return render_template("perfil.html", publicaciones=publicaciones_data, nombre_usuario=nombre_usuario)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
