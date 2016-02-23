from collections import Sequence
import contextlib
import csv
from datetime import datetime
import json
import logging
from operator import itemgetter
import os
import urlparse

from flask import Blueprint, Flask, Response, jsonify, render_template, request
from flask.ext.basicauth import BasicAuth
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.sslify import SSLify
from flask.ext.wtf import Form, RecaptchaField
from flask.ext.wtf.file import FileField
import sendgrid
import sys

from sqlalchemy import type_coerce
from werkzeug.contrib.fixers import ProxyFix
from werkzeug.exceptions import BadRequest
from wtforms import BooleanField, StringField, ValidationError
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired, EqualTo
from wtforms.widgets import HTMLString

from bluemix_promocodes import defaults


def get_postgresql_uri(services, service_name):
    for service in services['elephantsql']:
        if service['name'] == service_name:
            # Replace the URI scheme
            old = urlparse.urlparse(service['credentials']['uri'])
            new = urlparse.ParseResult('postgresql+psycopg2', *old[1:])
            return urlparse.urlunparse(new)
    return None


def import_cloudfoundry_config(config):
    if 'VCAP_SERVICES' in os.environ:
        services = json.loads(os.getenv('VCAP_SERVICES'))
        for service in services['sendgrid']:
            if service['name'] == config['SENDGRID_SERVICE']:
                config['SENDGRID_USERNAME'] = service['credentials']['username']
                config['SENDGRID_PASSWORD'] = service['credentials']['password']
        if 'ELEPHANTSQL_SERVICE' in config:
            service_name = config['ELEPHANTSQL_SERVICE']
            uri = get_postgresql_uri(services, service_name)
            if uri is None:
                raise RuntimeError('No ElephantSQL service named {} found in '
                                   'the VCAP_SERVICES environment variable. '
                                   'Did you add the service to the application?'
                                   .format(service_name))
            config['SQLALCHEMY_DATABASE_URI'] = uri


app = Flask('bluemix_promocodes')
handler = logging.StreamHandler(stream=sys.stderr)
handler.setLevel(logging.WARNING)
app.logger.addHandler(handler)
app.config.from_object(defaults)
app.config.from_envvar('CONFIG')


import_cloudfoundry_config(app.config)
db = SQLAlchemy(app)
sslify = SSLify(app, permanent=True)


class User(db.Model):
    __tablename__ = app.config['TABLE_PREFIX'] + 'user'
    id = db.Column(db.Integer(), primary_key=True, nullable=False)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    ip = db.Column(db.String(39), nullable=False)
    created_at = db.Column(db.DateTime(), nullable=False, default=db.func.now())
    bounce_count = db.Column(db.Integer(), nullable=False, default=0)


class Code(db.Model):
    __tablename__ = app.config['TABLE_PREFIX'] + 'code'
    id = db.Column(db.Integer(), primary_key=True, nullable=False)
    value = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer(),
                        db.ForeignKey(User.id, onupdate='RESTRICT',
                                      ondelete='SET NULL'),
                        unique=True, index=True, nullable=True)
    user = db.relationship(User, backref=db.backref('code', uselist=False))


with app.app_context():
    db.metadata.create_all(bind=db.engine)


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


def get_code_by_value(value):
    return db.session.query(Code).filter_by(value=value).first()


def get_unused_code():
    return db.session.query(Code).filter_by(user=None).limit(1).first()


def allocate_code(user, code):
    code.user = user
    db.session.add(code)


def create_user(email, first_name, last_name, ip):
    user = User(email=email, first_name=first_name, last_name=last_name, ip=ip)
    db.session.add(user)
    return user


def send_code_mail(email, first_name, last_name, code, send_at=None):
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
    if send_at:
        msg.smtpapi.set_send_at(send_at)
    sg = get_sendgrid_client()
    return sg.send(msg)


def request_wants_json():
    best = request.accept_mimetypes \
        .best_match(['application/json', 'text/html'])
    return best == 'application/json' and \
        request.accept_mimetypes[best] > \
        request.accept_mimetypes['text/html']


class RequestCodeForm(Form):
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    email = EmailField("E-Mail", validators=[DataRequired()])
    verify_email = EmailField("Verify E-Mail",
                              validators=[DataRequired(), EqualTo('email')])
    consent = BooleanField(
        'I agree that IBM is processing my personal information',
        description=HTMLString('See the <a href="http://www.ibm.com'
                               '/privacy/us/en/">IBM Online Privacy Statement'
                               '</a> for details.'),
        validators=[DataRequired()]
    )
    recaptcha = RecaptchaField()


@app.route('/', methods=('GET', 'POST'))
def request_code():
    form = RequestCodeForm()
    if form.validate_on_submit():
        with transaction():
            email = form.email.data
            if get_user_by_email(email):
                return render_template('errors/user_exists.html', email=email)
            code = get_unused_code()
            if not code:
                return render_template('errors/generic.html',
                                       message="No more codes left.")
            first_name = form.first_name.data
            last_name = form.last_name.data
            ip = request.remote_addr
            user = create_user(email, first_name, last_name, ip)
            allocate_code(user, code)
            send_code_mail(email, first_name, last_name, code.value)
        return render_template('code_sent.html', code=code.value, email=email)
    return render_template('request_code.html', form=form)


@app.route('/resend-code/<email>')
def resend_code(email):
    with transaction():
        user = get_user_by_email(email)
        if not user:
            return render_template("errors/user_not_exists.html", email=email)
        if not user.code:
            return render_template(
                'errors/generic.html',
                message="Internal error (No code for request available)."
            )
        value = user.code.value
        send_code_mail(user.email, user.first_name, user.last_name, value)
        return render_template('code_resent.html', code=value, email=email)


class BadAPIRequest(BadRequest):
    def __init__(self):
        response = jsonify(code=self.code, message='Bad Request')
        super(BadAPIRequest, self).__init__(response=response)


def handle_sendgrid_bounce(event):
    try:
        email = event['email']
        reason = event['reason']
        timestamp = event['timestamp']
    except KeyError:
        raise BadAPIRequest()
    with transaction():
        user = get_user_by_email(email)
        user.bounce_count += 1
        if not reason.startswith('4'):
            return
        if user.bounce_count < app.config['MAXIMUM_BOUNCE_COUNT']:
            send_at = timestamp + app.config['BOUNCE_RETRY_DELAY']
            send_code_mail(email, user.first_name, user.last_name,
                           user.code.value, send_at)


def handle_sendgrid_event(event):
    try:
        event_type = event['event']
    except KeyError:
        raise BadAPIRequest()
    if event_type == 'bounce':
        handle_sendgrid_bounce(event)
    else:
        app.logger.warning("Unhandled SendGrid event %r", event)


@app.route('/hooks/sendgrid-events', methods=('POST',))
def receive_sendgrid_events():
    try:
        events = json.loads(request.data)
    except ValueError:
        raise BadAPIRequest()
    if not isinstance(events, Sequence):
        raise BadAPIRequest()
    for event in events:
        handle_sendgrid_event(event)
    return jsonify(message='OK')


admin = Blueprint('admin', 'admin')
basic_auth = BasicAuth(app)


@admin.before_request
@basic_auth.required
def before_request():
    pass


class CSVFileField(FileField):
    def process_formdata(self, valuelist):
        super(CSVFileField, self).process_formdata(valuelist)
        reader = csv.reader(self.data)
        self.data = list(reader)


class ImportCodesForm(Form):
    csv = CSVFileField("CSV File", description="The CSV file must contain a "
                                               "single column without a header",
                       validators=[DataRequired()])

    def validate_csv(self, field):
        if not all(len(row) == 1 for row in field.data):
            raise ValidationError("Your CSV file has multiple columns")


@admin.route('/import-codes', methods=('GET', 'POST'))
def import_codes():
    form = ImportCodesForm()
    if form.validate_on_submit():
        values = map(itemgetter(0), form.csv.data)
        with transaction():
            for value in values:
                if not get_code_by_value(value=value):
                    db.session.add(Code(value=value))
        return render_template('list_codes.html')
    else:
        return render_template('import_codes.html', form=form)


def get_requests():
    return db.session.query(User.id, User.first_name, User.last_name,
                            User.email, User.ip, User.created_at,
                            Code.value).select_from(User).join(Code)


@admin.route('/')
@admin.route('/list-requests')
def list_requests():
    if request_wants_json():
        with transaction():
            result = get_requests()
            return jsonify(rows=[{
                'id': user_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'ip': ip,
                'requested_at': created_at,
                'code': value,
            } for user_id, first_name, last_name, email,
                  ip, created_at, value in result])
    else:
        return render_template('list_requests.html')


@admin.route('/list-codes')
def list_codes():
    if request_wants_json():
        with transaction():
            result = db.session.query(
                Code.id, Code.value,
                type_coerce(Code.user_id, db.Boolean)
            ).select_from(Code).outerjoin(User)
            return jsonify(rows=[{
                'id': code_id,
                'code': value,
                'requested': requested,
            } for code_id, value, requested in result])
    else:
        return render_template('list_codes.html')


@admin.route('/export-requests')
def export_requests():
    requests = get_requests()
    response = Response(mimetype='text/csv')
    writer = csv.writer(response.stream)
    writer.writerow(('First Name', 'Last Name', 'E-Mail', 'IP',
                     'Requested At', 'Code'))
    for row in requests:
        writer.writerow(tuple(unicode(field).encode(encoding='utf-8')
                              for field in row[1:]))
    return response


app.register_blueprint(admin, url_prefix='/admin')


if __name__ == '__main__':
    port = int(os.getenv('VCAP_APP_PORT', 8000))
    app.run(port=port)
else:
    num_proxies = app.config['REVERSE_PROXY_COUNT']
    app.wsgi_app = ProxyFix(app.wsgi_app, num_proxies)
