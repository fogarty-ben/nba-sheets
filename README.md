# nba-sheets

Parse NBA standings (and a few random stats) from the Fox Sports website and write them to a Google Sheet.

Ben Fogarty
5 December 2020

# How it works

The repo includes two Python scripts that run nightly via GitHub actions (configured in [`.github/workflows/main.yml`](https://github.com/fogarty-ben/nba-sheets/blob/main/.github/workflows/main.yml)). [`generate_secrets.py`](https://github.com/fogarty-ben/nba-sheets/blob/main/generate_secrets.py) is a small helper script that reads configuration secrets necessary for connecting to Google Sheets and writes them to JSONs that the main script can use. [`nba_sheets.py`](https://github.com/fogarty-ben/nba-sheets/blob/main/nba_sheets.py) is the workhorse script; it parses information from the Fox Sports website, formats it, and uploads it to Google Sheets.

The scripts was developed and runs against Python 3.8.4. Major dependencies include beautifulsoup4, gspread, pandas, and requests. 

# Reusing this repo

To reuse this repo, you'll need to add `SPREADSHEET_ID` and `WORKSHEET_NAME` to your repository's secrets [`nba_sheets.py`](https://github.com/fogarty-ben/nba-sheets/blob/main/nba_sheets.py) to the worksheet you want to update. 

You'll also need to configue a Google service account to access the spreadsheet [as described in this gspread documentation](https://gspread.readthedocs.io/en/latest/oauth2.html#for-bots-using-service-account). Copy values from the generated JSON to your repository's secrets with the naming conventions seen in [`generate_secrets.py`](https://github.com/fogarty-ben/nba-sheets/blob/main/generate_secrets.py) (ex/ `this_field` in the JSON would be saved in secrets at `GKEY_THIS_FIELD`). 

Additionally, update the `REF_LINK` global in [`nba_sheets.py`](https://github.com/fogarty-ben/nba-sheets/blob/main/nba_sheets.py) so that the sheet shows the proper code source.

# Something wrong?

Notice a problems? Standings incorrect? If so, [open an issue here](https://github.com/fogarty-ben/nba-sheets/issues). Other comments are also welcome.
