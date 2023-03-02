"""
    First pass implementation of auth.
    Isolated from rest of app first to avoid any conflicts + assess libraries.
    Master file for the feature will be broken up after.
"""

# app logic

# routes


from flask import Blueprint, redirect, request, url_for
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user
)
from authlib.integrations.flask_client import OAuth

oauth = OAuth()
conf_url="https://accounts.google.com/.well-known/openid-configuration"
# the rest should be automatically read from app.config
oauth.register(
    name="google",
    server_metadata_url=conf_url,
    client_kwargs={
    'scope': 'openid email profile'
    }
)

authbp = Blueprint('authbp', __name__)

@authbp.route("/fakehome")
def fakehome():
    print(current_user)
    if current_user.is_authenticated:
        return (
            "<p>Hello, {}! You're logged in! Email: {}</p>"
            "<div><p>Google Profile Picture:</p>"
            '<a class="button" href="/logout">Logout</a>'.format(
                current_user.name, current_user.email
            )
        )
    else:
        return (
            '<a class="button" href="/login">Google Login</a>'
            '<form action="/login-pw" method="post">'
            '<input type="text" name="email" placeholder="email">'
            '<input type="text" name="password" placeholder="password">'
            '<button type="submit">Login</button>'
            '</form>'
            )
    
@authbp.route('/login')
def login():
    print(oauth.google.__dict__)
    redirect_uri = url_for('auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@authbp.route('/login-pw', methods=['POST'])
def login_pw():
    # verify credentials and get user
    # return jwts
    email = request.form.get('email')
    password = request.form.get('password')
    user = User.getby_email(email)
    if not user:
        user = User(email=email)
        user = User.create(user)
        user = User.getby_email(email)
    if user.check_password(password):
        login_user(user)
    return redirect(url_for("fakehome"))

@authbp.route('/authorize')
def auth():
    print("reached here")
    # for our purposes dont need to keep track of this
    token = oauth.google.authorize_access_token()
    userinfo = token['userinfo']
    if userinfo["email_verified"]:
        unique_id = userinfo["sub"]
        users_email = userinfo["email"]
        users_name = userinfo["given_name"]

        user = User.getby_email(users_email)
        if not user:
            new_user = User(googleid=unique_id, email=users_email, name=users_name)
            User.create(new_user)
            user = User.getby_email(users_email)
        result = login_user(user)
        print(result)
        return redirect(url_for("index"))
    else:
        return "User unverified", 400
    

@authbp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for("fakehome"))

# models
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, db.Identity(start=1, cycle=True), primary_key=True)
    googleid = db.Column(db.String(100))
    # username is email
    email = db.Column(db.String(40), unique=True)
    name = db.Column(db.String(100))

    def __str__(self):
        return self.email

    def get_userid(self):
        return self.googleid

    def check_password(self, password):
        return password == 'password'
    
    @staticmethod
    def get(id):
        return User.query.filter_by(id=id).first()
    
    @staticmethod
    def getby_googleid(googleid):
        user = User.query.filter_by(googleid=googleid).first()
        return user

    @staticmethod
    def getby_email(email):
        user = User.query.filter_by(email=email).first()
        return user

    @staticmethod
    def create(user):
        db.session.add(user)
        db.session.commit()