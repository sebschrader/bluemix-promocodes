import contextlib
import sendgrid
import sqlite3
import os

from flask import Flask, request, render_template
from flask.ext.wtf import Form
from wtforms import StringField
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired, EqualTo

from bluemix_promocodes import defaults


def get_db_connection():
    conn = getattr(request, 'db_connection', None)
    if conn is None:
        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        request.db_connection = conn
    return conn


def get_sendgrid_client():
    client = sendgrid.SendGridClient(app.config['SENDGRID_API_KEY'],
                                     raise_errors=True)
    return client


@contextlib.contextmanager
def transaction():
    conn = get_db_connection()
    try:
        yield
        conn.commit()
    except:
        conn.rollback()
        raise


def create_tables():
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    conn.execute('CREATE TABLE IF NOT EXISTS "code" ('
                 'id INTEGER PRIMARY KEY NOT NULL, '
                 'value CHARACTER(64) UNIQUE NOT NULL, '
                 'user_id INTEGER UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS "user" ('
                 'id INTEGER PRIMARY KEY NOT NULL, '
                 'email VARCHAR(255) UNIQUE NOT NULL, '
                 'first_name VARCHAR(255) NOT NULL, '
                 'last_name VARCHAR(255) NOT NULL, '
                 'ip CHAR(39) NOT NULL, '
                 'created_at INTEGER NOT NULL DEFAULT (datetime(\'now\')))')


def get_single_row(query, params):
    """
    Execute a given query and expect a single row as result.

    :raises AssertionError: if more than one result is returned
    :rtype: sqlite3.Row
    """
    conn = get_db_connection()
    cursor = conn.execute(query, params)
    row = cursor.fetchone()
    assert len(cursor.fetchall()) == 0
    return row


def get_user_by_id(user_id):
    row = get_single_row('SELECT id, email, first_name, last_name, ip, created_at '
                         'FROM "user" WHERE id = ?', (user_id,))
    if row:
        assert len(row) == 6
    return row


def get_user_by_email(email):
    row = get_single_row('SELECT id, email, first_name, last_name, ip, created_at '
                         'FROM "user" WHERE email = ?', (email,))
    if row:
        assert len(row) == 6
    return row


def get_code_by_id(code_id):
    row = get_single_row('SELECT id, value, user_id '
                         'FROM "code" WHERE id = ?', (code_id,))
    if row:
        assert len(row) == 3
    return row


def get_code_by_user_id(user_id):
    row = get_single_row('SELECT id, value, user_id '
                         'FROM "code" WHERE user_id = ?', (user_id,))
    if row:
        assert len(row) == 3
    return row


def get_unused_code():
    row = get_single_row('SELECT id, value, user_id '
                         'FROM "code" WHERE user_id IS NULL LIMIT 1', ())
    if row:
        assert len(row) == 3
    return row


def allocate_code(user_id, code_id):
    conn = get_db_connection()
    cursor = conn.execute('UPDATE "code" SET user_id = ? WHERE id = ?', (user_id, code_id))
    assert cursor.rowcount == 1


def create_user(email, first_name, last_name, ip):
    conn = get_db_connection()
    params = (email, first_name, last_name, ip)
    cursor = conn.execute('INSERT INTO "user" (email, first_name, last_name, ip) '
                          'VALUES (?, ?, ?, ?)', params)
    return cursor.lastrowid


app = Flask(__name__)


app.config.from_object(defaults)
try:
    from bluemix_promocodes import config
except ImportError:
    config = None
else:
    app.config.from_object(config)
create_tables()
CONFIG_ENVVAR = 'BLUEMIX_PROMOCODES_CONFIG'
if CONFIG_ENVVAR in os.environ:
    app.config.from_envvar(CONFIG_ENVVAR)


@app.teardown_request
def close_database(error=None):
    conn = getattr(request, 'db_connection', None)
    if conn is not None:
        del request.db_connection
        conn.close()


def send_code_mail(email, first_name, last_name, code):
    msg = sendgrid.Mail()
    msg.add_to(email)
    msg.set_from(app.config['EMAIL_ADDRESS'])
    msg.set_from_name("IBM Bluemix Promo Codes")
    msg.set_subject("Your IBM Bluemix Promo Code")
    msg.set_text(render_template("mail_body.txt",
                                 email=email, first_name=first_name, last_name=last_name, code=code))
    msg.smtpapi.add_filter('clicktrack', 'enable', 0)
    msg.smtpapi.add_filter('ganalytics', 'enable', 0)
    msg.smtpapi.add_filter('opentrack', 'enable', 0)
    msg.smtpapi.add_filter('gravatar', 'enable', 0  )
    sg = get_sendgrid_client()
    status, message = sg.send(msg)


class RequestCodeForm(Form):
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    email = EmailField("E-Mail", validators=[DataRequired()])
    verify_email = EmailField("Verify E-Mail", validators=[DataRequired(), EqualTo('email')])


@app.route('/', methods=('GET', 'POST'))
def request_code():
    form = RequestCodeForm(request.form)
    if form.validate_on_submit():
        with transaction():
            email = form.email.data
            if get_user_by_email(email):
                return render_template('errors/user_exists.html', email=email)
            code = get_unused_code()
            if not code:
                return render_template('errors/generic.html', message="No more codes left.")
            code_id, code_value, code_user_id = code
            first_name = form.first_name.data
            last_name = form.last_name.data
            user_id = create_user(email, first_name, last_name, request.remote_addr)
            allocate_code(user_id, code_id)
            send_code_mail(email, first_name, last_name, code_value)
        return render_template('code_sent.html', email=email)
    return render_template('request_code.html', form=form)


@app.route('/resend-code/<email>')
def resend_code(email):
    with transaction():
        user = get_user_by_email(email)
        if not user:
            return render_template("errors/users_not_exists.html", email=email)
        user_id, email, first_name, last_name, ip, created_at = user
        code = get_code_by_user_id(user_id)
        if not code:
            return render_template('errors/generic.html', message="Internal error (No code for request available).")
        code_id, code_value, code_user_id = code
        send_code_mail(email, first_name, last_name, code_value)
        return render_template('code_sent.html', email=email)


if __name__ == '__main__':
    port = int(os.getenv('VCAP_APP_PORT', 8000))
    app.run(port=port)
