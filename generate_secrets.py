import os
import json

service_key_dict = {
                    "type": os.environ['GKEY_TYPE'],
                    "project_id": os.environ['GKEY_PROJECT_ID'],
                    "private_key_id": os.environ['GKEY_PRIVATE_KEY_ID'],
                    "private_key": os.environ['GKEY_PRIVATE_KEY'].replace('\\n', '\n'),
                    "client_email": os.environ['GKEY_CLIENT_EMAIL'],
                    "client_id": os.environ['GKEY_CLIENT_ID'],
                    "auth_uri": os.environ['GKEY_AUTH_URI'],
                    "token_uri": os.environ['GKEY_TOKEN_URI'],
                    "auth_provider_x509_cert_url": os.environ['GKEY_AUTH_PROVIDER_X509_CERT_URL'],
                    "client_x509_cert_url": os.environ['GKEY_CLIENT_X509_CERT_URL'],
                   }

spreadsheet_dict = {
                    'sheet_id': os.environ['SHEET_ID'],
                    'responses_ws_name': os.environ['RESPONSE_WORKSHEET_NAME']
                   }

with open('service_key.json', 'w') as f:
    json.dump(service_key_dict, f)

with open('sheet_info.json', 'w') as f:
    json.dump(spreadsheet_dict, f)
