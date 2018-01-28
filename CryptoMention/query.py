import sqlite3


sqlite_file = 'wordfreq'
conn = sqlite3.connect(sqlite_file)
c = conn.cursor()
c.execute("SELECT name,symbol from coinprice ")
rows = c.fetchall()
print(rows)