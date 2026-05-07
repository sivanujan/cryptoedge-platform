import sqlite3
try:
    conn = sqlite3.connect('cryptoedge.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, coin_count FROM strategies")
    rows = cursor.fetchall()
    print("ID | Name | CoinCount")
    print("---|------|----------")
    for r in rows:
        print(f"{r[0]:2} | {r[1]:20} | {r[2]:10}")
    conn.close()
except Exception as e:
    print(e)
