import sqlite3
try:
    conn = sqlite3.connect('cryptoedge.db')
    cursor = conn.cursor()
    cursor.execute("SELECT strategy_id, COUNT(*) FROM backtest_results GROUP BY strategy_id")
    rows = cursor.fetchall()
    print("StrategyID | Count")
    print("-----------|------")
    for r in rows:
        print(f"{r[0]:10} | {r[1]:5}")
    conn.close()
except Exception as e:
    print(e)
