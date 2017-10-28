### Imports
import uuid
import os, sys
from flask import Flask, redirect, render_template, request, session, url_for, jsonify, g
from flask_compress import Compress
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
import sqlalchemy
# from cs50 import SQL
from passlib.hash import sha256_crypt

### CS50 wrapper for SQLAlchemy
class SQL(object):
    """Wrap SQLAlchemy to provide a simple SQL API."""

    def __init__(self, url):
        """
        Create instance of sqlalchemy.engine.Engine.

        URL should be a string that indicates database dialect and connection arguments.

        http://docs.sqlalchemy.org/en/latest/core/engines.html#sqlalchemy.create_engine
        """
        try:
            self.engine = sqlalchemy.create_engine(url)
        except Exception as e:
            raise RuntimeError(e)

    def execute(self, text, *multiparams, **params):
        """
        Execute a SQL statement.
        """
        try:

            # bind parameters before statement reaches database, so that bound parameters appear in exceptions
            # http://docs.sqlalchemy.org/en/latest/core/sqlelement.html#sqlalchemy.sql.expression.text
            # https://groups.google.com/forum/#!topic/sqlalchemy/FfLwKT1yQlg
            # http://docs.sqlalchemy.org/en/latest/core/connections.html#sqlalchemy.engine.Engine.execute
            # http://docs.sqlalchemy.org/en/latest/faq/sqlexpressions.html#how-do-i-render-sql-expressions-as-strings-possibly-with-bound-parameters-inlined
            statement = sqlalchemy.text(text).bindparams(*multiparams, **params)
            result = self.engine.execute(str(statement.compile(compile_kwargs={"literal_binds": True})))

            # if SELECT (or INSERT with RETURNING), return result set as list of dict objects
            if result.returns_rows:
                rows = result.fetchall()
                return [dict(row) for row in rows]

            # if INSERT, return primary key value for a newly inserted row
            elif result.lastrowid is not None:
                return result.lastrowid

            # if DELETE or UPDATE (or INSERT without RETURNING), return number of rows matched
            else:
                return result.rowcount

        # if constraint violated, return None
        except sqlalchemy.exc.IntegrityError:
            return None

        # else raise error
        except Exception as e:
            raise RuntimeError(e)


### configure flask
app = Flask(__name__)
Compress(app)

app.secret_key = uuid.uuid4().hex

### configure root directory path relative to this file
THIS_FOLDER_G = ""
if getattr(sys, 'frozen', False):
    # frozen
    THIS_FOLDER_G = os.path.dirname(sys.executable)
else:
    # unfrozen
    THIS_FOLDER_G = os.path.dirname(os.path.realpath(__file__))

### configure CS50 Library to use SQLite database
db = SQL("sqlite:///" + THIS_FOLDER_G + "/db/system.db")

### configure mail
app.config.from_pyfile('config.cfg')
mail = Mail(app)
URL_Tokenizer = URLSafeTimedSerializer('Thisisasecret!')

### cities and expertise lists
expertise_file = open(THIS_FOLDER_G + '/expertise_list.txt', 'r')
expertise_file_text = expertise_file.read()
expertise_list = expertise_file_text.split('\n')
expertise_file.close()

cities_file = open(THIS_FOLDER_G + '/cities_list.txt', 'r')
cities_file_text = cities_file.read()
cities_list = cities_file_text.split('\n')
cities_file.close()


### Store current session to global variable "g"
@app.before_request
def before_request():
    g.user_id = None
    g.name = None
    g.logged_in = None
    if "user_id" in session:
        g.user_id = session["user_id"]
        g.name = session["name"]
        g.logged_in = session["logged_in"]

@app.route('/')
def index():
    return render_template('home.html', cities_list=cities_list, expertise_list=expertise_list)

@app.route('/search')
def search():
    city = request.args.get('city')
    primary_expertise = request.args.get('primary_expertise')
    
    if city != '' and primary_expertise != '':
        creatives = db.execute("SELECT * FROM creatives WHERE city=:city AND (primary_expertise=:primary_expertise OR secondary_expertise=:secondary_expertise) AND email_confirmed=:email_confirmed", city=city, primary_expertise=primary_expertise, secondary_expertise=primary_expertise, email_confirmed="true")
    else:
        creatives = db.execute("SELECT * FROM creatives WHERE (city=:city OR primary_expertise=:primary_expertise OR secondary_expertise=:secondary_expertise) AND email_confirmed=:email_confirmed", city=city, primary_expertise=primary_expertise, secondary_expertise=primary_expertise, email_confirmed="true")

    creatives = sorted(creatives, key=lambda k: k['name'].lower()) 

    return render_template('search_results.html', creatives=creatives, total_creatives=len(creatives))
    # return jsonify(creatives)

### Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    elif request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        creatives = db.execute("SELECT * FROM creatives WHERE email=:email", email=email)
        if len(creatives) > 0:
            if creatives[0]['email'] == email and sha256_crypt.verify(password, creatives[0]['password']) is True and creatives[0]['email_confirmed'] == 'true':
                session.pop('user_id', None)
                session.pop('name', None)
                session.pop('logged_in', None)
                session['user_id'] = str(creatives[0]['id'])
                session['name'] = creatives[0]['name']
                session['logged_in'] = True
                # return redirect(url_for('index'))
                return redirect(url_for('user_profile', id=session['user_id']))
            else:
                return render_template('login.html', error='Invalid Email or Password. Or Email not confirmed.')
        else:
            return render_template('login.html', error='Invalid Email or Password.')
    else:
        return redirect(url_for('index'))

### Logout
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("name", None)
    session.pop("logged_in", None)
    return redirect(url_for("index"))

### register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template("register.html", cities_list=cities_list, expertise_list=expertise_list)
    elif request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        city = request.form['city']
        primary_expertise = request.form['primary_expertise']
        secondary_expertise = request.form['secondary_expertise']
        small_intro = request.form['small_intro']
        primary_portfolio = request.form['primary_portfolio']
        personal_website = request.form['personal_website']
        behance = request.form['behance']
        dribbble = request.form['dribbble']
        linkedin = request.form['linkedin']
        github = request.form['github']
        gitlab = request.form['gitlab']
        twitter = request.form['twitter']
        facebook = request.form['facebook']

        if (name == '' or
            email == '' or
            password == '' or
            confirm_password == '' or
            city == '' or
            primary_expertise == '' or
            primary_portfolio == '' or
            primary_portfolio == ''):
            return jsonify([{"status": "error", "msg": "Please fill all required fields."}])
        
        if len(small_intro) > 500:
            return jsonify([{"status": "error", "msg": "Small Intro exceeded 500 characters"}])

        creatives = db.execute("SELECT * FROM creatives WHERE email=:email", email=email)
        if len(creatives) > 0:
            return jsonify([{"status": "error", "msg": "Email already registered."}])

        if password != confirm_password:
            return jsonify([{"status": "error", "msg": "Password did not match."}])

        email_confirmation_token = URL_Tokenizer.dumps(email, salt='email-confirm')

        db.execute("INSERT INTO creatives (name, email, password, city, primary_expertise, secondary_expertise, small_intro, primary_portfolio, personal_website, behance, dribbble, linkedin, github, gitlab, twitter, facebook, email_confirmation_token, email_confirmed) VALUES (:name, :email, :password, :city, :primary_expertise, :secondary_expertise, :small_intro, :primary_portfolio, :personal_website, :behance, :dribbble, :linkedin, :github, :gitlab, :twitter, :facebook, :email_confirmation_token, :email_confirmed)", name=name, email=email, password=sha256_crypt.hash(password), city=city, primary_expertise=primary_expertise, secondary_expertise=secondary_expertise, small_intro=small_intro, primary_portfolio=primary_portfolio, personal_website=personal_website, behance=behance, dribbble=dribbble, linkedin=linkedin, github=github, gitlab=gitlab, twitter=twitter, facebook=facebook, email_confirmation_token=email_confirmation_token, email_confirmed="false")

        msg = Message('Confirm Email', sender='creatives.directory@gmail.com', recipients=[email])
        link = url_for('confirm_email', token=email_confirmation_token, _external=True)
        msg.body = 'Click the following link to confirm your Email at "CREATIVES DIRECTORY"\n{}\n\nDelete this email if you did not register.'.format(link)
        mail.send(msg)
        
        return jsonify([{"status": "success", "msg": "Registration Successful. Please confirm your Email."}])
    else:
        return redirect(url_for('index'))

@app.route('/confirm_email/<token>')
def confirm_email(token):
    try:
        email = URL_Tokenizer.loads(token, salt='email-confirm', max_age=(3600 * 24))
    except SignatureExpired:
        return render_template('status.html', msg="Token Expired!")
    
    db.execute("UPDATE creatives SET email_confirmed=:email_confirmed WHERE email=:email", email_confirmed="true", email=email)
    db.execute("UPDATE creatives SET email_confirmation_token=:empty WHERE email=:email", empty="", email=email)
    
    return render_template('status.html', msg="Email Confirmed!")

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')
    elif request.method == 'POST':
        email = request.form['email']
        
        creatives = db.execute("SELECT * FROM creatives WHERE email=:email", email=email)
        if len(creatives) < 1:
            return render_template('forgot_password.html', error="Email Not Registered.")

        password_reset_token = URL_Tokenizer.dumps(email, salt='password-reset')
        
        db.execute("UPDATE creatives SET password_reset_token=:password_reset_token WHERE email=:email", password_reset_token=password_reset_token, email=email)
        
        msg = Message('Password Reset', sender='creatives.directory@gmail.com', recipients=[email])
        link = url_for('reset_password', token=password_reset_token, _external=True)
        msg.body = 'Click the following link to reset your Password at "CREATIVES DIRECTORY"\n{}\n\nDelete this email if you did not ask for password reset.'.format(link)
        mail.send(msg)
        
        return render_template('forgot_password.html', success="Password reset link sent.")
    else:
        return redirect(url_for('index'))

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        try:
            email = URL_Tokenizer.loads(token, salt='password-reset', max_age=(3600))
        except SignatureExpired:
            return render_template('status.html', msg="Token Expired!")

        return render_template('reset_password.html', token=token)
    elif request.method == 'POST':
        try:
            email = URL_Tokenizer.loads(token, salt='password-reset', max_age=(3600))
        except SignatureExpired:
            return render_template('status.html', msg="Token Expired!")

        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return render_template('reset_password.html', token=token, error="Password did not match.")

        db.execute("UPDATE creatives SET password=:password WHERE email=:email", password=sha256_crypt.hash(password), email=email)
        db.execute("UPDATE creatives SET password_reset_token=:empty WHERE email=:email", empty="", email=email)
        
        return render_template('status.html', msg="Password Reset Successful!")
    else:
        return redirect(url_for('index'))

@app.route('/profile/<id>', methods=['GET', 'POST'])
def user_profile(id):
    if request.method == 'GET':
        creatives = db.execute("SELECT * FROM creatives WHERE id=:id", id=id)
        if len(creatives) < 1:
            return render_template('status.html', msg="Profile Not Found")
        elif creatives[0]['email_confirmed'] != 'true':
            return render_template('status.html', msg="Profile Not Found")
        else:
            show_edit_btn = False
            if g.logged_in is True and g.user_id == id:
                show_edit_btn = True
            creative = creatives[0]
            return render_template('user_profile.html', creative=creative, show_edit_btn=show_edit_btn)
    else:
        return redirect(url_for('index'))

@app.route('/edit_my_profile', methods=['GET', 'POST'])
def edit_my_profile():
    if g.logged_in is True and request.method == 'GET':
        creatives = db.execute("SELECT * FROM creatives WHERE id=:id", id=g.user_id)
        if len(creatives) < 1:
            return render_template('status.html', msg="Profile Not Found")
        elif creatives[0]['email_confirmed'] != 'true':
            return render_template('status.html', msg="Profile Not Found")
        else:
            creative = creatives[0]
            return render_template('edit_my_profile.html', creative=creative, cities_list=cities_list, expertise_list=expertise_list)
    elif g.logged_in is True and request.method == 'POST':
        name = request.form['name']
        city = request.form['city']
        primary_expertise = request.form['primary_expertise']
        secondary_expertise = request.form['secondary_expertise']
        small_intro = request.form['small_intro']
        primary_portfolio = request.form['primary_portfolio']
        personal_website = request.form['personal_website']
        behance = request.form['behance']
        dribbble = request.form['dribbble']
        linkedin = request.form['linkedin']
        github = request.form['github']
        gitlab = request.form['gitlab']
        twitter = request.form['twitter']
        facebook = request.form['facebook']

        if (name == '' or
            city == '' or
            primary_expertise == '' or
            primary_portfolio == '' or
            primary_portfolio == ''):
            return jsonify([{"status": "error", "msg": "Please fill all required fields."}])

        if len(small_intro) > 500:
            return jsonify([{"status": "error", "msg": "Small Intro exceeded 500 characters"}])

        db.execute("UPDATE creatives SET name=:name, city=:city, primary_expertise=:primary_expertise, secondary_expertise=:secondary_expertise, small_intro=:small_intro, primary_portfolio=:primary_portfolio, personal_website=:personal_website, behance=:behance, dribbble=:dribbble, linkedin=:linkedin, github=:github, gitlab=:gitlab, twitter=:twitter, facebook=:facebook WHERE id=:id", name=name, city=city, primary_expertise=primary_expertise, secondary_expertise=secondary_expertise, small_intro=small_intro, primary_portfolio=primary_portfolio, personal_website=personal_website, behance=behance, dribbble=dribbble, linkedin=linkedin, github=github, gitlab=gitlab, twitter=twitter, facebook=facebook, id=g.user_id)

        return jsonify([{"status": "success", "msg": "Profile Edit Successful. Reload the page to confirm."}])
    else:
        return redirect(url_for('index'))

@app.route('/delete_my_account', methods=['GET', 'POST'])
def delete_my_account():
    if g.logged_in is True and request.method == 'POST':
        _id = request.form['_id'];
        if g.user_id != _id:
            return render_template('status.html', msg="Account Deletion Failed. [ERROR: Creds Mismatch]")
        else:
            db.execute("DELETE FROM creatives WHERE id=:id", id=_id)
            
            session.pop("user_id", None)
            session.pop("name", None)
            session.pop("logged_in", None)
            g.user_id = None
            g.name = None
            g.logged_in = None
            
            return render_template('status.html', msg="Account Deletion Successful")
    else:
        return redirect(url_for('index'))

### Run Flask App
if __name__ == "__main__":
    # app.run()
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=80)
