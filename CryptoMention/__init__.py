import collections
import json
import os
import sqlite3
import threading
import time
import os.path
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, request
from flask_login import LoginManager, login_user, login_required, logout_user
from flask_socketio import SocketIO
from flask.ext.bcrypt import Bcrypt
from datetime import datetime, date, timedelta
from collections import defaultdict
from flask_wtf import Form
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import Email, DataRequired


app = Flask(__name__)
app.secret_key = 'randomnumber'
bcrypt = Bcrypt(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "wordfreq.db")
user_db_path = os.path.join(BASE_DIR, "users.db")

sqllite_uri = 'sqlite:///'+user_db_path
app.config['SQLALCHEMY_DATABASE_URI'] = sqllite_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)



socketio = SocketIO(app)
login_manager = LoginManager()
login_manager.init_app(app)

global cur_minutes
global Timer1
cur_minutes = 5

class SignupForm(Form):
    email = StringField('email',
                validators=[DataRequired(),Email()])
    password = PasswordField(
                'password',
                validators=[DataRequired()])
    submit = SubmitField("Sign In")

class User(db.Model):
    email = db.Column(db.String(80), primary_key=True, unique=True)
    password = db.Column(db.String(80))
    def __init__(self, email, password):
        self.email = email
        self.password = password
    def __repr__(self):
        return '<User %r>' % self.email
    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return str(self.email)

class RepeatedTimer(object):
  def __init__(self, interval, function, *args, **kwargs):
    self._timer = None
    self.interval = interval
    self.function = function
    self.args = args
    self.kwargs = kwargs
    self.is_running = False
    self.next_call = time.time()
    self.start()

  def _run(self):
    self.is_running = False
    self.start()
    self.function(*self.args, **self.kwargs)

  def start(self):
    if not self.is_running:
      self.next_call += self.interval
      self._timer = threading.Timer(self.next_call - time.time(), self._run)
      self._timer.start()
      self.is_running = True

  def stop(self):
    self._timer.cancel()
    self.is_running = False

def read_db_historical(time_range,name):
    #print(time_range)
    global cur_minutes
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    past_time = datetime.now() - timedelta(minutes=time_range)
    c.execute("SELECT frequency, date FROM words WHERE date BETWEEN ? AND ? AND name=?",(past_time, datetime.now(),name))
    rows = c.fetchall()
    objects_list = []
    global count
    count = 0
    for row in rows:
        d = collections.OrderedDict()
        #dt = str(row[1])
        #dt = parser.parse(dt)

        d['x'] = count = count +1
        d['y'] = row[0]
        objects_list.append(d)
    sorted_list = sorted(objects_list, key=lambda k: k['x'], reverse=True)
    #sorted_list = objects_list
    sorted_list = sorted_list[0:20]
    #print(sorted_list)
    j = json.dumps(sorted_list)
    socketio.emit('time_change_historical', j)


def read_db(time_range,socketid):
    #print(time_range)
    global Timer1
    global cur_minutes

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    five_minutes = datetime.now() - timedelta(minutes=time_range)
    c.execute("SELECT name, sum(frequency) FROM words WHERE date BETWEEN ? AND ? GROUP BY name ",(five_minutes, datetime.now()))
    rows = c.fetchall()
    objects_list = []
    for row in rows:
        d = collections.OrderedDict()
        d['x'] = str(row[0])
        d['y'] = row[1]
        objects_list.append(d)
    sorted_list = sorted(objects_list, key=lambda k: k['y'],reverse=True)
    sorted_list = sorted_list[0:39]

    #print(sorted_list)
    j = json.dumps(sorted_list)
    socketio.emit('update',j,room=socketid)
    #print(cur_minutes)

    Timer1 = threading.Timer(10,read_db,[cur_minutes,socketid])
    Timer1.start()

def update_coin_table(time_range,socketid):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    five_minutes = datetime.now() - timedelta(minutes=time_range)
    c.execute("SELECT name, sum(frequency) FROM words WHERE date BETWEEN ? AND ? GROUP BY name ",(five_minutes, datetime.now()))
    rows = c.fetchall()

    ob_list = []

    for row in rows:
        g = {}
        g['coin']= str(row[0])
        g['freq']= row[1]
        ob_list.append(g)
    c.close()


    sorted_ob_list = sorted(ob_list, key=lambda k: k['freq'], reverse=True)
    sorted_ob_list = sorted_ob_list[0:199]

    #print('Sorted: ')
    #print(sorted_ob_list)

    new_sorted_ob_list = []
    for item in sorted_ob_list:
        h = {}
        h[str(item['coin'])] = [str(item['freq'])]
        new_sorted_ob_list.append(h)
    #print('New Sorted OB List: ')
    #print(new_sorted_ob_list)
    objects_list = new_sorted_ob_list

    nm_list = []
    for item in sorted_ob_list:
        nm_list.append(item['coin'])
    #print('nm_list: ')
    #print(nm_list)
    name_list = nm_list[0:199]


    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    price_list = []
    l = name_list
    placeholder = '?'  # For SQLite. See DBAPI paramstyle.
    placeholders = ', '.join(placeholder for unused in l)
    query = 'SELECT name, symbol,price_usd, percent_change_1h, percent_change_24h, percent_change_7d FROM coinprice WHERE name collate nocase in (%s)' % (placeholders,)
    #print('name_list: ')
    #print(name_list)

    #print('l: ')
    #print(l)
    c.execute(query, l,)
    rows = c.fetchall()
    for row in rows:
        e = {}
        e[str(row[0]).lower()] = [row[2],row[3],row[4],row[5]]
        price_list.append(e)


    price_list_symbol = []
    b = name_list
    #print('l length:')
    #print(len(b))
    placeholder = '?'  # For SQLite. See DBAPI paramstyle.
    placeholders2 = ', '.join(placeholder for unused in b)
    #print('Pholder length: ')
    #print(len(placeholders2))
    query = 'SELECT name, symbol,price_usd, percent_change_1h, percent_change_24h, percent_change_7d FROM coinprice WHERE symbol COLLATE NOCASE  in (%s)' % (placeholders,)
    # print('name_list: ')
    # print(name_list)
    # print('l: ')
    # print(l)
    c.execute(query, b, )
    rows = c.fetchall()
    for row in rows:
        f = {}
        f[str(row[1]).lower()] = [row[2], row[3], row[4], row[5]]
        price_list_symbol.append(f)


    #print('Object List: ')
    #print(objects_list)
    #print(len(objects_list))
    #print('Price List: ')
    #print(price_list)
    #print(len(price_list))
    #print('Price List Symbols: ')
    #print(price_list_symbol)
    #print(len(price_list_symbol))

    tot_list = objects_list + price_list
    #print('Tot_list: ')
    #print(tot_list)

    temp_dict = defaultdict(list)
    for item in tot_list:
        for k, v in item.items():
            temp_dict[k] += v

    new_list = [{k: v} for k, v in temp_dict.items()]


    new_list = new_list + price_list_symbol
    temp_dict = defaultdict(list)
    for item in new_list:

        for k, v in item.items():
            temp_dict[k] += v

    new_list = [{k: v} for k, v in temp_dict.items()]

    #print('New List: ')
    #print(new_list)

    final_list = []
    for item in new_list:
        for key in item:
            array_list = item[key]
            array_list.insert(0,key)
            #print(array_list)
        final_list.append(array_list)

    for counter, item in enumerate(final_list):
        if len(item) <= 2:
            final_list.pop(counter)


    #print(final_list)
    #print(len(final_list))
    j = json.dumps(final_list)
    socketio.emit('update_coin_table', j, room=socketid)

clients = []
socketid = ''

@socketio.on('connected')
def connected():
    print("%s connected" % (request.sid))
    read_db(5,request.sid)
    update_coin_table(5, socketid)

@socketio.on('disconnect')
def disconnect():
    print("%s disconnected" % (request.sid))


@socketio.on('sub_change')
def sub_reddit_change(sub_change):
    print(sub_change)

@socketio.on('time_change_historical')
def time_change_historical(time_change_historical):
    time_change_historical = 1440
    read_db_historical(time_change_historical, 'btc')

@socketio.on('time_change')
def test_message(time_change):
    #print(time_change)
    global cur_minutes
    global Timer1
    if time_change == 'fmin':
        cur_minutes = 5
    if time_change == 'tmin':
        cur_minutes = 30
    if time_change == 'hr':
        cur_minutes = 60
    if time_change == 'day':
        cur_minutes = 1440

    socketid = request.sid
    read_db(cur_minutes, socketid)
    Timer1.cancel()
    update_coin_table(cur_minutes,socketid)



@app.route('/protected')
@login_required
def protected():
    return "protected area"

@login_manager.user_loader
def load_user(email):
    return User.query.filter_by(email = email).first()

@app.route("/", endpoint='home')
def home():
    return render_template('home.html')

@app.route("/dashboard", endpoint='dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route("/historical", endpoint='historical')
def historical():
    return render_template('historical.html')

@app.route("/about", endpoint='about')
def about():
    return render_template('about.html')


@app.route('/login', methods=['GET','POST'])
def login():
    form = SignupForm()
    if request.method == 'GET':
        return render_template('login.html', form=form)
    elif request.method == 'POST':

        if form.validate_on_submit():
            user=User.query.filter_by(email=form.email.data).first()
            if user:

                if bcrypt.check_password_hash(user.password, form.password.data):
                    login_user(user)
                    return render_template('dashboard.html')
                else:
                    return "Wrong password"
            else:
                return "user doesn't exist"
        else:
            return "form not validated"


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if request.method == 'GET':
        return render_template('signup.html', form = form)
    elif request.method == 'POST':
        if form.validate_on_submit():
            if User.query.filter_by(email=form.email.data).first():
                return "Email address already exists"
            else:
                pw_hash = bcrypt.generate_password_hash(form.password.data)
                newuser = User(form.email.data, pw_hash)
                db.session.add(newuser)
                db.session.commit()
                login_user(newuser)
            return render_template('dashboard.html')
        else:
             return "Form didn't validate"


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return "Logged out"


#rt = RepeatedTimer(10, read_db, cur_minutes ) # it auto-starts, no need of rt.start()
if __name__ == '__main__':
    socketio.run(app)