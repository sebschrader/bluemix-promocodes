import contextlib
import json
import logging
import os

from flask import Flask, request, render_template
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.sslify import SSLify
from flask.ext.wtf import Form
import sendgrid
import sys
from wtforms import StringField
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired, EqualTo

from bluemix_promocodes import defaults


def import_cloudfoundry_config(config):
    if 'VCAP_SERVICES' in os.environ:
        services = json.loads(os.getenv('VCAP_SERVICES'))
        for service in services['sqldb']:
            if service['name'] == config['SQLDB_SERVICE']:
                uri = "db2+ibm_db://{username}:{password}@{host}:{port}/{db}"
                config['SQLALCHEMY_DATABASE_URI'] = uri.format(**service['credentials'])
        for service in services['sendgrid']:
            if service['name'] == config['SENDGRID_SERVICE']:
                config['SENDGRID_USERNAME'] = service['credentials']['username']
                config['SENDGRID_PASSWORD'] = service['credentials']['password']


app = Flask(__name__)
handler = logging.StreamHandler(stream=sys.stderr)
handler.setLevel(logging.WARNING)
app.logger.addHandler(handler)
app.config.from_object(defaults)
try:
    from bluemix_promocodes import config
except ImportError:
    config = None
else:
    app.config.from_object(config)


import_cloudfoundry_config(app.config)
db = SQLAlchemy(app)
sslify = SSLify(app, permanent=True)


class User(db.Model):
    id = db.Column(db.Integer(), primary_key=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    ip = db.Column(db.String(39), nullable=False)
    created_at = db.Column(db.DateTime(), nullable=False, default=db.func.now())


class Code(db.Model):
    id = db.Column(db.Integer(), primary_key=True, nullable=False)
    value = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer(), db.ForeignKey(User.id), unique=True, nullable=True)
    user = db.relationship(User, backref=db.backref('code', uselist=False))


def get_sendgrid_client():
    if 'SENDGRID_API_KEY' in app.config:
        username = app.config['SENDGRID_API_KEY']
        password = None
    else:
        username = app.config['SENDGRID_USERNAME']
        password = app.config['SENDGRID_PASSWORD']
    client = sendgrid.SendGridClient(username, password,
                                     raise_errors=True)
    return client


@contextlib.contextmanager
def transaction():
    try:
        yield
        db.session.commit()
    except:
        db.session.rollback()
        raise

def get_user_by_id(user_id):
    return db.session.query(User).filter_by(id=user_id).first()


def get_user_by_email(email):
    return db.session.query(User).filter_by(email=email).first()


def get_code_by_id(code_id):
    return db.session.query(Code).filter_by(id=code_id).first()


def get_code_by_user_id(user_id):
    return db.session.query(Code).filter_by(user_id=user_id).first()


def get_unused_code():
    return db.session.query(Code).filter_by(user=None).limit(1).first()


def allocate_code(user, code):
    code.user = user
    db.session.add(code)


def create_user(email, first_name, last_name, ip):
    user = User(email=email, first_name=first_name, last_name=last_name, ip=ip)
    db.session.add(user)
    return user


def send_code_mail(email, first_name, last_name, code):
    msg = sendgrid.Mail()
    msg.add_to(email)
    msg.set_from(app.config['EMAIL_ADDRESS'])
    msg.set_from_name("IBM Bluemix Promo Codes")
    msg.set_subject("Your IBM Bluemix Promo Code")
    msg.set_text(render_template("mail_body.txt",
                                 email=email, first_name=first_name,
                                 last_name=last_name, code=code))
    msg.smtpapi.add_filter('clicktrack', 'enable', 0)
    msg.smtpapi.add_filter('ganalytics', 'enable', 0)
    msg.smtpapi.add_filter('opentrack', 'enable', 0)
    msg.smtpapi.add_filter('gravatar', 'enable', 0)
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
            first_name = form.first_name.data
            last_name = form.last_name.data
            user = create_user(email, first_name, last_name, request.remote_addr)
            allocate_code(user, code)
            send_code_mail(email, first_name, last_name, code.value)
        return render_template('code_sent.html', email=email)
    return render_template('request_code.html', form=form)


@app.route('/resend-code/<email>')
def resend_code(email):
    with transaction():
        user = get_user_by_email(email)
        if not user:
            return render_template("errors/users_not_exists.html", email=email)
        if not user.code:
            return render_template('errors/generic.html', message="Internal error (No code for request available).")
        send_code_mail(user.email, user.first_name, user.last_name, user.code.value)
        return render_template('code_resent.html', email=email)


if __name__ == '__main__':
    port = int(os.getenv('VCAP_APP_PORT', 8000))
    app.run(port=port)
