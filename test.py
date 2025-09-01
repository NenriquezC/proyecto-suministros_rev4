import psycopg2
import locale

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')  # o 'C.UTF-8'

try:
    conn = psycopg2.connect(
        dbname='sumindb',
        user='postgres',
        password='niki2025',
        host='localhost',
        port='5432'
    )
    print("✅ Conexión exitosa")
    conn.close()
except UnicodeDecodeError as e:
    print("Error de codificación:", e)
except Exception as e:
    print( "Otro error:", e)