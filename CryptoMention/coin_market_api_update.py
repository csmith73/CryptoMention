import requests
import sqlite3
import json

sqlite_file = 'coinprice.db'
conn = sqlite3.connect(sqlite_file)
c = conn.cursor()



r = requests.get('https://api.coinmarketcap.com/v1/ticker/?limit=0')
j = json.loads(r.text)
print(type(j[1]))
for counter, coin in enumerate(j):
    print(type(coin))
    c.execute("INSERT INTO coinprice VALUES (?,?,?,?,?,?,?)", (str(coin['name']),str(coin['symbol']),coin['price_usd'],coin['percent_change_1h'],coin['percent_change_24h'],coin['percent_change_7d'],counter))
conn.commit()
#c.execute("SELECT frequency, date FROM words WHERE date BETWEEN ? AND ? AND name=?",(past_time, datetime.now(),name))