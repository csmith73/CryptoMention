import collections
import CryptoMention
import json
import os
import sqlite3
import threading
import time
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, request
from flask_login import LoginManager, login_user, login_required, logout_user
from flask_socketio import SocketIO
from CryptoMention.forms import SignupForm
from flask.ext.bcrypt import Bcrypt
from datetime import datetime, date, timedelta


app = Flask(__name__)
app.secret_key = os.urandom(12)
bcrypt = Bcrypt(app)


sqllite_uri = 'sqlite:///users.db'
app.config['SQLALCHEMY_DATABASE_URI'] = sqllite_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

socketio = SocketIO(app)
login_manager = LoginManager()
login_manager.init_app(app)

global cur_minutes
global Timer1
cur_minutes = 5

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


def read_db(time_range):
    print(time_range)
    global cur_minutes
    sqlite_file = 'wordfreq'
    conn = sqlite3.connect(sqlite_file)
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

    print(sorted_list)
    j = json.dumps(sorted_list)
    socketio.emit('update',j)
    print(cur_minutes)
    global Timer1
    Timer1 = threading.Timer(10,read_db,[cur_minutes])
    Timer1.start()

@socketio.on('sub_change')
def sub_reddit_change(sub_change):
    print(sub_change)

@socketio.on('time_change')
def test_message(time_change):
    print(time_change)
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
    Timer1.cancel()
    read_db(cur_minutes)



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


@app.route('/login', methods=['GET','POST'])
def login():
    form = SignupForm()
    if request.method == 'GET':
        return render_template('login.html', form=form)
    elif request.method == 'POST':
        print(form.password.data)
        print(form.email.data)
        if form.validate_on_submit():
            user=User.query.filter_by(email=form.email.data).first()
            if user:

                if bcrypt.check_password_hash(user.password, form.password.data):
                    login_user(user)
                    return "User logged in"
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
            return "User created!!!"
        else:
             return "Form didn't validate"


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return "Logged out"

read_db(cur_minutes)
#rt = RepeatedTimer(10, read_db, cur_minutes ) # it auto-starts, no need of rt.start()
if __name__ == '__main__':
    socketio.run(app)