Bluemix Promocode Application
=============================
Request promo codes with the browser.

Codes are stored in the Bluemix SQL database service (IBM DB2) and sent via email through SendGrid.

Usage
-----
Create a SQL database service and sendgrid service in Bluemix, if you haven't already.
The database schema is `schema.sql`.
You can use the web console to create schema on the Bluemix SQL database.

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
VCAP_SERVICES=<long-JSON-string>
CONFIG=config.py

# Run the app
python2 bluemix_promocodes/__init__.py
```

When running locally you probably want to set `DEBUG=True` in `config.py`. 
