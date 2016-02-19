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
# (Recommended) Create a virtualenv
virtualenv -p python2 .venv
.venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

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
```bash
# Export the CloudFoundry environment
cf env <app>

# Add the VCAP_SERVICES and CONFIG variables to your environment
export VCAP_SERVICES=<long-JSON-string>
export CONFIG=config.py

# Run the app
python2 bluemix_promocodes/__init__.py
```

When running locally you probably want to set `DEBUG=True` in `config.py`. 

Admin interface
---------------
The admin interface can be reached on the `/admin` endpoint, i.e.
`http://localhost/admin/` if you're running locally or
`https://<app>.mybluemix.net/admin/` if you're running it on Bluemix.

The admin interface is protected with HTTP Basic Auth, the default username is
`admin` and can be changed with the `BASIC_AUTH_USERNAME` option and the
password must be set with the `BASIC_AUTH_PASSWORD` option.
