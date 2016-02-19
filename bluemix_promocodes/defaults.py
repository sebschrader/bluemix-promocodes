from datetime import timedelta

SQLALCHEMY_TRACK_MODIFICATIONS = False
REVERSE_PROXY_COUNT = 1
TABLE_PREFIX = ''
BASIC_AUTH_REALM = 'Promocode Administration'
BASIC_AUTH_USERNAME = 'admin'
MAXIMUM_BOUNCE_COUNT = 2
BOUNCE_RETRY_DELAY = int(timedelta(minutes=10).total_seconds())
RECAPTCHA_DATA_ATTRS = {
    'theme': 'dark',
}
