"""Top-level package for the Simple Data Transfer Protocol."""


# BSD 3-Clause License

# Copyright (c) 2024, UC Regents
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.

# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from flask import  Flask, Blueprint, request, render_template, flash, redirect, url_for, session

import os
from authlib.integrations.flask_client import OAuth
import jwt
from uploader import make_SDMLTable_from_upload
from json import loads, JSONDecodeError
import requests


from sdtp import sdtp_server_blueprint

app = Flask(__name__)

wiki_server = Blueprint('sdtp_wiki_server', __name__, template_folder='templates')

additional_routes =[
  {"url": "/upload", "method": ["GET", "POST"], "description": "File uploader.  If a multipart file is not attached to the POST body, displays a file chooser"},
  {"url": "/view_tables", "method": ["GET"], "description": "Shows all the tables in a list, with a link to the table viewer method"},
  {"url": "/view_table?table <i>string, required</i>&filter<i>string, optional</i>", "method": ["GET", "POST"], "description": "Table Viewer.  Displays the first twenty rows of the table (filtered, if filter was applied).  filter, if present is a functional filter expression, e.g. IN_RANGE('<column_name>, <min_val>, <max_val>)"},
  {"url": "/view_base", "method": ["GET", "POST"], "description": "Check out the base template"}
]

def _active_login():
    return "email" in session.keys() and session['email'] is not None

def extended_render(template_name, context):
    '''
    Render the template with context, adding email and user
    if they are defined in this session
    Arguments:
        template_name: name of the template file
        context: a dictionary of contexts for the template
    '''
    if _active_login():
        context["email"] = session["email"]
        context["user"] = session["user"]
    
    return render_template(template_name, **context)

@wiki_server.route('/')
def show_root():
  '''
  Show the API for the table server
  Arguments: None
  '''
  
  context = {
      "routes": sdtp_server_blueprint.ROUTES,
      "table_names": list(sdtp_server_blueprint.table_server.servers.keys()),
      "additional_routes": additional_routes
  }
  return extended_render('greeting.html', context)
  

app.register_blueprint(wiki_server)

app.register_blueprint(sdtp_server_blueprint)

# from google.cloud import bigquery

app.secret_key = os.environ["APP_SECRET"]
root = os.environ['ROOT_URL']


# Configure OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ['CLIENT_ID'],
    client_secret=os.environ['CLIENT_SECRET'],
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    redirect_uri=f'{root}/oauth2callback',
    client_kwargs={'scope': 'email'},
    server_metadata_url = 'https://accounts.google.com/.well-known/openid-configuration'
)


@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/logout')
def logout():
    # if 'google_access_token' in session:
    #     requests.post('https://oauth2.googleapis.com/revoke',
    #     params={'token': session['google_access_token']},
    #     headers = {'content-type': 'application/x-www-form-urlencoded'})
    session.clear()
    return redirect(root)

@app.route('/oauth2callback')
def authorize():
    try:
        # Exchange the authorization code for an access token
        token = google.authorize_access_token()
        session['google_access_token'] = token['access_token']
        
        id_token = token.get('id_token')
        user_info = jwt.decode(id_token, options={"verify_signature": False})
        email = user_info.get('email')
        session['email'] = email
        session['user'] = email.split('@')[0]
        return show_root()
    except Exception as e:
        # Capture and return the error message
        return f'Error: {str(e)}'
# client = bigquery.Client()

@app.route('/cwd')
def cwd():
    return os.getcwd()

from build_filter import create_filter    
from sdtp import check_valid_spec_return_boolean, InvalidDataException

                           
BUCKET_NAME = os.environ['BUCKET_NAME']

from gcs_interface import SDMLStorageBucket

bucket = SDMLStorageBucket(BUCKET_NAME)

table_sample_queries = bucket.get_sdql_samples()

def _render_table(table_name, table, rows, filter_spec = None):
    context = {
        "filter": filter_spec if filter_spec is not None else '',
        "table": {
            "name": table_name,
            "columns": table.schema,
            "rows": rows[:20] if len(rows) > 20 else rows
        }
    }
    if table_name in table_sample_queries.keys():
        context['sample_tables'] = table_sample_queries[table_name]
    return extended_render('table.html', context)


@app.route('/filter_table', methods=['POST'])
def filter_table():
    table_name = request.form.get('table')
    sdtp_filter_str = request.form.get('filter', None)
    table = sdtp_server_blueprint.table_server.get_table(table_name)
    try:
        sdtp_filter_spec = loads(sdtp_filter_str)
        if check_valid_spec_return_boolean(sdtp_filter_spec):
            rows = table.get_filtered_rows(sdtp_filter_spec)
        else:
            # bug!  Needs to check in context of table!
            # Does this go into sdtp or do we do it here...
            # try here then migrate...
            flash(f'{sdtp_filter_str} is not a valid filter specification')
            rows = table.get_filtered_rows()
    except JSONDecodeError as e:
        flash(f'{sdtp_filter_str} is not a valid filter specification')
        rows = table.get_filtered_rows()
    
    return _render_table(table_name, table, rows, sdtp_filter_str)


@app.route('/view_table')
def view_table():
    table_name = request.args.get('table')
    table = sdtp_server_blueprint.table_server.get_table(table_name)
    # sdtp_filter_spec = create_filter(filter)
    # if not check_valid_spec_return_boolean(sdtp_filter_spec):
    #     sdtp_filter_spec = None
    #     filter = ''

    rows = table.get_filtered_rows()
    return _render_table(table_name, table, rows)
    


def _check_email():
    # A  utility to ensure that only registered users 
    # can upload files
    return 'email' in session and session['email'].endswith('berkeley.edu')

def upload_error(message):
    flash(message)
    return redirect(request.url)


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if not _check_email():
        flash('Uploads restricted to individuals with a berkeley.edu account')
        return show_root()
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            # flash('No selected file')
            return redirect(request.url)
        # make_SDMLTable_from_upload checks to maek sure it's an SDML file
        try:
            table_types = set(sdtp_server_blueprint.table_server.factories.keys())
            table_dictionary = make_SDMLTable_from_upload(request.files['file'], table_types)  
        except InvalidDataException as e:
            flash(str(e))
            return redirect(request.url)
        try:
            table_dictionary["name"] = f"{session['user']}/{table_dictionary['name']}"
            gcs_table_spec = {
                "schema":  table_dictionary['table']["schema"],
                "type": "GCSTable",
                "bucket": BUCKET_NAME,
                "blob": f"rowtables/{table_dictionary['name']}.sdml",
            }
            # sdtp_server_blueprint.table_server.add_sdtp_table_from_dictionary(table_dictionary["name"], table_dictionary["table"])
            sdtp_server_blueprint.table_server.add_sdtp_table_from_dictionary(table_dictionary["name"], gcs_table_spec)
        except InvalidDataException as e:
            return upload_error(f'Error {e} in creating the table for  {file.filename}')
        bucket.upload_table('rowtables', table_dictionary)
        bucket.upload_table('gcstables', {"name": table_dictionary['name'], "table": gcs_table_spec})
        return redirect(f"/view_table?table={table_dictionary['name']}")
        
    context = {}
    if _active_login():
        current_user = session['user']
        current_user_tables = [key for key in sdtp_server_blueprint.table_server.servers.keys() if key.startswith(current_user)]
        context['user_tables'] = current_user_tables
    return extended_render('upload_form.html', context)
    

@app.route("/view_tables")
def view_tables():
    table_names = sdtp_server_blueprint.table_server.servers.keys()
    return extended_render('view_tables.html', {"tables":table_names})

@app.route("/view_base")
def view_base():
    return extended_render('base.html', {})

additional_routes =[
    {"url": "/upload", "method": ["GET", "POST"], "description": "File uploader.  If a multipart file is not attached to the POST body, displays a file chooser"},
    {"url": "/view_tables", "method": ["GET"], "description": "Shows all the tables in a list, with a link to the table viewer method"},
    {"url": "/view_table?table <i>string, required</i>&filter<i>string, optional</i>", "method": ["GET", "POST"], "description": "Table Viewer.  Displays the first twenty rows of the table (filtered, if filter was applied).  filter, if present is a functional filter expression, e.g. IN_RANGE('<column_name>, <min_val>, <max_val>)"},
    {"url": "/view_base", "method": ["GET", "POST"], "description": "Check out the base template"}
]

@app.route('/help', methods=['POST', 'GET'])
@app.route('/', methods=['POST', 'GET'])
def show_routes():
    '''
    Show the API for the table server
    Arguments: None
    '''
    pages = sdtp_server_blueprint.ROUTES + additional_routes
    keys = ['url', 'method', 'headers', 'description']
    for page in pages:
        for key in keys:
            if not key in page.keys():
                page[key] = ''

    return extended_render('routes.html', {"pages": pages, "keys": keys})

prefix = os.environ.get('TABLE_PREFIX', None)
table_names = bucket.get_all_table_names(prefix)
for table_name in table_names:
    try:
        table_dict = bucket.get_table_as_dictionary(table_name)
        first_index = len(prefix) if prefix is not None else 0
        key_name = table_name[first_index:-5]
        sdtp_server_blueprint.table_server.add_sdtp_table_from_dictionary(key_name, table_dict)
    except InvalidDataException as e:
        pass # need to put logging in


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))