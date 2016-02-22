Bluemix Promocode Application
=============================
Request promo codes with the browser.

Codes are stored in the Bluemix SQL database service (IBM DB2) and sent via email through SendGrid.

Usage
-----
Create a SQL database service and sendgrid service in Bluemix, if you haven't already.
The app will automatically set up the tables and indexes during startup,
if they don't exists.
In addition a SQL script that creates the database schema can be found in
`schema.sql`, if you want to create the database manually.
You can use the web console that is reachable from the Bluemix interface to
execute SQL commands.

The code form is protected by reCAPTCHA to prevent bots from requesting codes.
You have to request a public/private key from
[Google](https://www.google.com/recaptcha/admin)
and put it in your config file.

```bash
# Install JavaScript/CSS dependencies
bower install

# Edit configs
cp bluemix-promocodes/example-config.py bluemix-promocodes/config.py
${EDITOR} bluemix-promocodes/config.py

cp example-manifest.yml manifest.yml
${EDITOR} manifest.yml

# Login into Bluemix
cf api https://api.ng.bluemix.net
cf login -u <user> -o <org> -s <space>

# Push the app
cf push --no-start

# Bind the services to your app
cf bind-service <app> <sendgrid-service>
cf bind-service <app> <sqldb-service>

# Set the CONFIG environment variable
cf set-env <app> CONFIG config.py

# Start the app
cf start <app>
```

Running the App locally
-----------------------
To run the app locally, you need Python 2 and pip. It is highly recommend that
you also use a virtualenv for the dependencies of the app.

### Installing the dependencies
```bash
# (Recommended) Create a virtualenv
virtualenv -p python2 .venv
. .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### Creating a development config
For development, you probably want to use a different configuration, e.g. to run
the app in debug mode by setting

```python
DEBUG = True
```

```bash
# Use a separate config file dev-config.py
cp bluemix_promocodes/config.py bluemix_promocodes/dev-config.py
${EDITOR} bluemix_promocodes/dev-config.py
```

### Option 1: Using the Bluemix SQL database
You have two options to run the app locally. You can run it with the remote
Bluemix database or a local SQLite database.

To use the remote Bluemix database we need its connection information.
```bash
# Obtain the CloudFoundry environment variables
cf env <app>

# Add the VCAP_SERVICES environment variable to run.sh
${EDITOR} run.sh
```

### Option 2: Using a local SQLite database
Instead of using the remote SQL database in Bluemix, which probably contains
the production data and has a much bigger latency, a local SQLite database may
also be used, just point the `SQLALCHEMY_DATABASE_URI` in your `dev-config.py`
to a location where you would like your local database to be stored, e.g.:

```python
SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/test.db'
```

### Run the app
```bash
# Run the app with the integrated development server
./run.sh
```

Admin interface
---------------
The admin interface can be reached on the `/admin` endpoint, i.e.
`http://localhost/admin/` if you're running locally or
`https://<app>.mybluemix.net/admin/` if you're running it on Bluemix.

The admin interface is protected with HTTP Basic Auth, the default username is
`admin` and can be changed with the `BASIC_AUTH_USERNAME` option and the
password must be set with the `BASIC_AUTH_PASSWORD` option.
