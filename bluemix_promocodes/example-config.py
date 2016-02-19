# Name of the SQL Database service in Bluemix/CloudFoundry
SQLDB_SERVICE = 'sqldb-01'
# Name of the Sendgrid service in Bluemix/CloudFoundry
SENDGRID_SERVICE = 'sendgrid-c0'
# A secret key for Flask
SECRET_KEY = 'correcthorsebatterystaple'
# The email address for outgoing mail
EMAIL_ADDRESS = 'me@example.com'
# Debug mode (never set this to True in production!)
DEBUG = False
# Admin password
BASIC_AUTH_PASSWORD = 'fixme'
# Number of reverse proxies between the end user and the app.
# Required to correctly determine the client's IP address
REVERSE_PROXY_COUNT = 2
# The code form is protected by reCAPTCHA
# Request keys for your domain on https://www.google.com/recaptcha/admin
RECAPTCHA_PUBLIC_KEY = ''
RECAPTCHA_PRIVATE_KEY = ''
