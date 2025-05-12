from datetime import datetime  # ✅ CAMBIO aquí en lugar de `import datetime`
from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2

app = Flask(__name__)
app.secret_key = '1312Itzcoatl'  # ¡NECESARIO para usar session y flash!

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="red_social",
        user="postgres",
        password="Itzcoatl1",
        options="-c client_encoding=UTF8"
    )
def usuario_ya_segue(id1, id2):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM Amistades WHERE id_usuario1 = %s AND id_usuario2 = %s", (id1, id2))
    resultado = cur.fetchone()
    cur.close()
    conn.close()
    return bool(resultado)


@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        contrasena = request.form.get('contrasena')
        
        print("Formulario recibido:", correo, contrasena)  # Depuración

        if not correo or not contrasena:
            flash('Por favor completa todos los campos', 'error')
            return redirect(url_for('login'))

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Consulta segura
            cur.execute("SELECT id_usuario, nombre FROM Usuarios WHERE correo = %s AND contrasena = %s",
                        (correo, contrasena))
            user = cur.fetchone()
            print("Resultado de la consulta:", user)  # 👀 Ver si encuentra al usuario

            if user:
                print("Login exitoso. Redirigiendo a /inicio")
                session['id_usuario'] = user[0]
                session['nombre'] = user[1]
                flash('Inicio de sesión exitoso!', 'success')
                return redirect(url_for('inicio'))
            else:
                print("Credenciales incorrectas")
                flash('Credenciales incorrectas', 'error')

        except Exception as e:
            flash('Error al conectar con la base de datos', 'error')
            app.logger.error(f"Error en login: {str(e)}")
        finally:
            cur.close()
            conn.close()

    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        correo = request.form.get('correo')
        contrasena = request.form.get('contrasena')
        
        if not all([nombre, correo, contrasena]):
            flash('Por favor completa todos los campos', 'error')
            return redirect(url_for('registro'))
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Verificar si el correo ya existe
            cur.execute("SELECT id_usuario FROM Usuarios WHERE correo = %s", (correo,))
            if cur.fetchone():
                flash('Este correo ya está registrado', 'error')
                return redirect(url_for('registro'))
            
            # Crear nuevo usuario
            cur.execute("INSERT INTO Usuarios (nombre, correo, contrasena) VALUES (%s, %s, %s)", 
                       (nombre, correo, contrasena))
            conn.commit()
            flash('Registro exitoso! Por favor inicia sesión', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            conn.rollback()
            flash('Error al registrar el usuario', 'error')
            app.logger.error(f"Error en registro: {str(e)}")
        finally:
            cur.close()
            conn.close()
    
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('login'))

# Rutas de la red social
@app.route('/inicio')
def inicio():
    if 'id_usuario' not in session:
        flash('Por favor inicia sesión primero', 'warning')
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        id_actual = session['id_usuario']

        # Obtener publicaciones
        cur.execute("""
            SELECT p.id_publicacion, u.id_usuario, u.nombre, p.contenido, p.fecha_hora
            FROM Publicaciones p
            JOIN Usuarios u ON p.id_usuario = u.id_usuario
            ORDER BY p.fecha_hora DESC
        """)
        publicaciones = cur.fetchall()

        publicaciones_data = []
        for pub in publicaciones:
            pub_id, id_autor, nombre_autor, contenido, fecha_hora = pub

            # Contar likes
            cur.execute("SELECT COUNT(*) FROM Reacciones WHERE id_publicacion = %s AND tipo_reaccion = 'like'", (pub_id,))
            likes = cur.fetchone()[0]

            # Verificar like del usuario
            cur.execute("""
                SELECT id_reaccion FROM Reacciones 
                WHERE id_publicacion = %s AND id_usuario = %s AND tipo_reaccion = 'like'
            """, (pub_id, id_actual))
            ya_dio_like = cur.fetchone() is not None

            # Obtener comentarios
            cur.execute("""
                SELECT c.texto, u.nombre, c.fecha_hora
                FROM Comentarios c
                JOIN Usuarios u ON c.id_usuario = u.id_usuario
                WHERE c.id_publicacion = %s
                ORDER BY c.fecha_hora ASC
            """, (pub_id,))
            comentarios = [{
                'texto': c[0],
                'usuario': c[1],
                'fecha': c[2]
            } for c in cur.fetchall()]

            # Verificar si ya lo sigue
            cur.execute("""
                SELECT 1 FROM Amistades
                WHERE id_usuario1 = %s AND id_usuario2 = %s
            """, (id_actual, id_autor))
            ya_sigue = cur.fetchone() is not None

            publicaciones_data.append({
                'id_publicacion': pub_id,
                'id_autor': id_autor,                # 🔹 Para botón seguir
                'usuario': nombre_autor,
                'contenido': contenido,
                'fecha_hora': fecha_hora,
                'likes': likes,
                'ya_dio_like': ya_dio_like,
                'comentarios': comentarios,
                'num_comentarios': len(comentarios),
                'ya_sigue': ya_sigue,                # 🔹 Para mostrar "Siguiendo"
                'es_mi_post': id_autor == id_actual  # 🔹 Para evitar seguirse a sí mismo
            })

        return render_template('inicio.html', publicaciones=publicaciones_data, id_actual=id_actual)

    except Exception as e:
        flash('Error al cargar las publicaciones', 'error')
        app.logger.error(f"Error en inicio: {str(e)}")
        return redirect(url_for('login'))
    finally:
        cur.close()
        conn.close()


@app.route('/publicar', methods=['POST'])
def publicar():
    if 'id_usuario' not in session:
        return redirect(url_for('login'))
    
    contenido = request.form.get('contenido')
    if not contenido or len(contenido.strip()) == 0:
        flash('No puedes publicar contenido vacío', 'error')
        return redirect(url_for('inicio'))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO Publicaciones (id_usuario, contenido, fecha_hora)
            VALUES (%s, %s, %s)
        """, (session['id_usuario'], contenido.strip(), datetime.now()))
        conn.commit()
        flash('Publicación creada con éxito!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Error al crear la publicación', 'error')
        app.logger.error(f"Error en publicar: {str(e)}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('inicio'))

@app.route('/comentar', methods=['POST'])
def comentar():
    if 'id_usuario' not in session:
        return redirect(url_for('login'))
    
    id_publicacion = request.form.get('id_publicacion')
    texto = request.form.get('texto')
    
    if not texto or len(texto.strip()) == 0:
        flash('No puedes comentar con texto vacío', 'error')
        return redirect(url_for('inicio'))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verificar que la publicación existe
        cur.execute("SELECT id_publicacion FROM Publicaciones WHERE id_publicacion = %s", (id_publicacion,))
        if not cur.fetchone():
            flash('Publicación no encontrada', 'error')
            return redirect(url_for('inicio'))
        
        # Insertar comentario
        cur.execute("""
            INSERT INTO Comentarios (id_publicacion, id_usuario, texto, fecha_hora)
            VALUES (%s, %s, %s, %s)
        """, (id_publicacion, session['id_usuario'], texto.strip(), datetime.now()))
        conn.commit()
        flash('Comentario añadido!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Error al añadir el comentario', 'error')
        app.logger.error(f"Error en comentar: {str(e)}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('inicio'))

@app.route('/dar_like/<int:id_publicacion>', methods=['POST'])
def dar_like(id_publicacion):
    if 'id_usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Verificar si ya dio like
        cur.execute("""
            SELECT id_reaccion FROM Reacciones 
            WHERE id_usuario = %s AND id_publicacion = %s AND tipo_reaccion = 'like'
        """, (session['id_usuario'], id_publicacion))
        existente = cur.fetchone()

        if existente:
            # Eliminar like
            cur.execute("DELETE FROM Reacciones WHERE id_reaccion = %s", (existente[0],))
            flash('Like eliminado', 'info')
        else:
            # Añadir like
            cur.execute("""
                INSERT INTO Reacciones (id_publicacion, id_usuario, tipo_reaccion)
                VALUES (%s, %s, 'like')
            """, (id_publicacion, session['id_usuario']))
            flash('Like añadido!', 'success')
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash('Error al procesar el like', 'error')
        app.logger.error(f"Error en dar_like: {str(e)}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('inicio'))

@app.route('/explorar')
def explorar():
    if 'id_usuario' not in session:
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        id_actual = session['id_usuario']

        # Recomendaciones: otros usuarios
        cur.execute("SELECT id_usuario, nombre FROM Usuarios WHERE id_usuario != %s", (id_actual,))
        usuarios = cur.fetchall()

        recomendaciones = []
        for id_u, nombre in usuarios:
            recomendaciones.append({
                'id': id_u,
                'nombre': nombre,
                'ya_segue': usuario_ya_segue(id_actual, id_u)
            })

        # Publicaciones recientes con likes y autor
        cur.execute("""
            SELECT p.id_publicacion, p.contenido, p.fecha_hora, u.nombre, u.id_usuario
            FROM Publicaciones p
            JOIN Usuarios u ON p.id_usuario = u.id_usuario
            ORDER BY p.fecha_hora DESC
        """)
        publicaciones = []
        for row in cur.fetchall():
            pub_id, contenido, fecha_hora, nombre, id_autor = row
            cur.execute("SELECT COUNT(*) FROM Reacciones WHERE id_publicacion = %s AND tipo_reaccion = 'like'", (pub_id,))
            likes = cur.fetchone()[0]

            publicaciones.append({
                'id': pub_id,
                'contenido': contenido,
                'fecha_hora': fecha_hora,
                'nombre': nombre,
                'likes': likes,
                'id_autor': id_autor
            })

        # Comentarios recientes (de otros usuarios)
        cur.execute("""
            SELECT c.texto, c.fecha_hora, u.nombre, u.id_usuario
            FROM Comentarios c
            JOIN Usuarios u ON c.id_usuario = u.id_usuario
            WHERE u.id_usuario != %s
            ORDER BY c.fecha_hora DESC
            LIMIT 10
        """, (id_actual,))

        comentarios_recientes = [{
            'texto': row[0],
            'fecha': row[1],
            'usuario': row[2],
            'id_usuario': row[3],
            'ya_segue': usuario_ya_segue(id_actual, row[3])
        } for row in cur.fetchall()]

        cur.close()
        conn.close()

        return render_template(
            'explorar.html',
            recomendaciones=recomendaciones,
            publicaciones=publicaciones,
            comentarios_recientes=comentarios_recientes
        )

    except Exception as e:
        flash('Error al cargar explorar', 'error')
        app.logger.error(f"Error en explorar: {str(e)}")
        return redirect(url_for('inicio'))


@app.route('/perfil/<int:id_usuario>')
def perfil(id_usuario):
    if 'id_usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Obtener nombre
        cur.execute("SELECT nombre FROM Usuarios WHERE id_usuario = %s", (id_usuario,))
        usuario = cur.fetchone()
        if not usuario:
            flash('Usuario no encontrado', 'error')
            return redirect(url_for('inicio'))

        nombre_usuario = usuario[0]

        # Publicaciones
        cur.execute("""
            SELECT id_publicacion, contenido, fecha_hora
            FROM Publicaciones
            WHERE id_usuario = %s
            ORDER BY fecha_hora DESC
        """, (id_usuario,))
        publicaciones = cur.fetchall()

        # Contar seguidores y seguidos
        cur.execute("SELECT COUNT(*) FROM Amistades WHERE id_usuario2 = %s", (id_usuario,))
        seguidores = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM Amistades WHERE id_usuario1 = %s", (id_usuario,))
        seguidos = cur.fetchone()[0]

        # Ver si ya lo sigue
        ya_segue = False
        if id_usuario != session['id_usuario']:
            cur.execute("""
                SELECT 1 FROM Amistades 
                WHERE id_usuario1 = %s AND id_usuario2 = %s
            """, (session['id_usuario'], id_usuario))
            ya_segue = cur.fetchone() is not None

        publicaciones_data = []
        for pub in publicaciones:
            pub_id, contenido, fecha_hora = pub
            cur.execute("SELECT COUNT(*) FROM Reacciones WHERE id_publicacion = %s", (pub_id,))
            likes = cur.fetchone()[0]

            publicaciones_data.append({
                'id_publicacion': pub_id,
                'contenido': contenido,
                'fecha_hora': fecha_hora,
                'likes': likes
            })

        return render_template('perfil.html',
                               nombre_usuario=nombre_usuario,
                               publicaciones=publicaciones_data,
                               seguidores=seguidores,
                               seguidos=seguidos,
                               es_mi_perfil=(id_usuario == session['id_usuario']),
                               ya_segue=ya_segue,
                               id_usuario_perfil=id_usuario)

    except Exception as e:
        flash('Error al cargar perfil', 'error')
        app.logger.error(f"Error en perfil: {str(e)}")
        return redirect(url_for('inicio'))
    finally:
        cur.close()
        conn.close()


@app.route('/seguir/<int:id_usuario2>', methods=['POST'])
def seguir(id_usuario2):
    if 'id_usuario' not in session:
        return redirect(url_for('login'))

    id_usuario1 = session['id_usuario']
    if id_usuario1 == id_usuario2:
        return redirect(request.referrer)

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Insertar relación siguiendo si no existe
        cur.execute("""
            INSERT INTO Amistades (id_usuario1, id_usuario2, estado, fecha_hora)
            VALUES (%s, %s, 'siguiendo', NOW())
            ON CONFLICT (id_usuario1, id_usuario2) DO NOTHING
        """, (id_usuario1, id_usuario2))

        # Verificar si el otro usuario también lo sigue
        cur.execute("""
            SELECT estado FROM Amistades
            WHERE id_usuario1 = %s AND id_usuario2 = %s
        """, (id_usuario2, id_usuario1))
        inverso = cur.fetchone()

        if inverso:
            # Actualizar ambos a 'amistad'
            cur.execute("""
                UPDATE Amistades
                SET estado = 'amistad'
                WHERE (id_usuario1 = %s AND id_usuario2 = %s)
                   OR (id_usuario1 = %s AND id_usuario2 = %s)
            """, (id_usuario1, id_usuario2, id_usuario2, id_usuario1))

        conn.commit()

    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error al seguir: {str(e)}")
    finally:
        cur.close()
        conn.close()

    return redirect(request.referrer)

@app.route('/dejar_de_seguir/<int:id_usuario2>', methods=['POST'])
def dejar_de_seguir(id_usuario2):
    if 'id_usuario' not in session:
        return redirect(url_for('login'))

    id_usuario1 = session['id_usuario']
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Eliminar la relación actual
        cur.execute("""
            DELETE FROM Amistades
            WHERE id_usuario1 = %s AND id_usuario2 = %s
        """, (id_usuario1, id_usuario2))

        # Verificar si el otro lo seguía (y estaban en amistad)
        cur.execute("""
            SELECT estado FROM Amistades
            WHERE id_usuario1 = %s AND id_usuario2 = %s
        """, (id_usuario2, id_usuario1))
        inverso = cur.fetchone()

        if inverso and inverso[0] == 'amistad':
            # El otro sigue, pero ya no es mutuo → baja a 'siguiendo'
            cur.execute("""
                UPDATE Amistades
                SET estado = 'siguiendo'
                WHERE id_usuario1 = %s AND id_usuario2 = %s
            """, (id_usuario2, id_usuario1))

        conn.commit()

    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error al dejar de seguir: {str(e)}")
    finally:
        cur.close()
        conn.close()

    return redirect(request.referrer)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)