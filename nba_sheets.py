'''
NBA Sheets
A small script to update a Google Sheet w/ NBA standings.

Ben Fogarty
2 December 2020
'''

import json

from bs4 import BeautifulSoup
import gspread
import pandas as pd
import requests

SERVICE_KEY_FP = 'service_key.json'
with open('sheet_info.json', 'r') as f:
    SHEET_INFO = json.load(f)

REF_LINK = 'https://github.com/fogarty-ben/nba-sheets/'

STANDINGS_FS_URL = 'https://www.foxsports.com/nba/standings'
TY_FS_AST_URL = 'https://www.foxsports.com/nba/trae-young-player-stats?category=assists&seasonType=reg'
KD_FS_MISC_URL = 'https://www.foxsports.com/nba/kevin-durant-player-stats?category=misc&seasonType=reg'

NAMES_MAP = {'Lakers': 'Los Angeles Lakers',
             'Clippers': 'LA Clippers',
             'Nuggets': 'Denver Nuggets',
             'Thunder': 'Oklahoma City Thunder',
             'Rockets': 'Houston Rockets',
             'Jazz': 'Utah Jazz',
             'Mavericks': 'Dallas Mavericks',
             'Trail Blazers': 'Portland Trail Blazers',
             'Grizzlies': 'Memphis Grizzlies',
             'Suns': 'Phoenix Suns',
             'Spurs': 'San Antonio Spurs',
             'Kings': 'Sacramento Kings',
             'Pelicans': 'New Orleans Pelicans',
             'Timberwolves': 'Minnesota Timberwolves',
             'Warriors': 'Golden State Warriors',
             'Bucks': 'Milwaukee Bucks',
             'Raptors': 'Toronto Raptors',
             'Celtics': 'Boston Celtics',
             'Heat': 'Miami Heat',
             'Pacers': 'Indiana Pacers',
             '76ers': 'Philadelphia 76ers',
             'Magic': 'Orlando Magic',
             'Nets': 'Brooklyn Nets',
             'Wizards': 'Washington Wizards',
             'Hornets': 'Charlotte Hornets',
             'Bulls': 'Chicago Bulls',
             'Knicks': 'New York Knicks',
             'Pistons': 'Detroit Pistons',
             'Hawks': 'Atlanta Hawks',
             'Cavaliers': 'Cleveland Cavaliers'}

def get_conference_standings(standings_tbl):
    '''
    Parse an HTML conference standings table from the Fox Sports website.

    Inputs:
    standings_tbl (bs4.element.Tag): HTML conference standings table
    
    Returns: pandas dataframe
    '''
    # find column locations
    i = 0
    cols = {'W-L', 'PCT', 'GB'}
    col_locs = {'RANK': 0,
                'TEAM': 1}
    for col in standings_tbl.findAll('th'):
        colspan = col.get('colspan', 1)
        i += int(colspan)
        content = col.text.strip()
        if content in cols:
            col_locs[content] = i - 1 # correct to 0-based indexing

    # extract standings
    data = []
    for i, row in enumerate(standings_tbl.findAll('tr')):
        if i == 0: # skip header row
            continue
        
        entry = {}
        cells = row.findAll('td')
        for stat, loc in col_locs.items():
            entry[stat] = cells[loc].text.strip().rstrip('XYZ')
        
        data.append(entry)
    df = pd.DataFrame(data)

    df['GB'] = df.GB.where(df.GB != '-', 0)
    df['PCT'] = df.PCT.where(df.PCT != '-', 0)
    df['TEAM'] = df.TEAM.map(NAMES_MAP)

    df = df.astype({'GB': float,
                    'PCT': float,
                    'RANK': int})


    return df

def get_standings(url):
    '''
    Pull standings from the Fox Sports website.

    url (str): web address of the Fox Sports NBA standings page

    Returns: pandas dataframe
    '''
    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, 'html.parser')
    eastern_html, western_html = soup.findAll('table', class_='data-table')

    eastern_df = get_conference_standings(eastern_html)
    eastern_df.rename(lambda x: ('EAST ' + x) if not x == 'RANK' else x, axis=1,
                      inplace=True)
    western_df = get_conference_standings(western_html)
    western_df.rename(lambda x: ('WEST ' + x) if not x == 'RANK' else x, axis=1,
                      inplace=True)

    standings_df = western_df.merge(eastern_df, how='outer', on='RANK')
    standings_df['PLAYOFF POINTS'] = [8] * 8 + [0] * 7
    cols_ordered = ['RANK', 'PLAYOFF POINTS'] 
    other_cols = standings_df.columns.values.tolist()[1:-1]
    cols_ordered = cols_ordered + other_cols

    return standings_df[cols_ordered]

def parse_fs_player_pg(url, stat, fxn=str):
    '''
    Retrieve a stat category from a player's Fox Sports website profile.

    Inputs:
    url (str): web address of the player's profile with the stat
    stat (str): title of the stat to grab
    fxn (function): function to cast the parsed statto

    Returns: fxn (by default str)
    '''
    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, 'html.parser')
    data_tables = soup.findAll('table', class_='data-table')

    # find column
    i = 0
    for col in data_tables[0].findAll('th'):
        colspan = col.get('colspan', 1)
        i += int(colspan)
        content = col.text.strip()
        if content == stat:
            i -= 1 # correct to 0-based indexing
            break

    # get stat
    seasons = data_tables[1].findAll('tr')
    current_season = seasons[-1]
    row = current_season.findAll('td')
    cell = row[i]

    return fxn(cell.text)

def get_sheet(service_key, ss_key, ws_title):
    '''
    Obtain the Google Sheets Worksheet to update.

    Inputs:
    service_key (str): path to service account json key
    ss_key (str): key/id of the google sheet to update, must be shared with the
        service account being used
    ws_title (str): title of the worksheet to update

    Returns: gspread.models.Worksheet
    '''
    gc = gspread.service_account(service_key)
    ss = gc.open_by_key(ss_key)
    ws = ss.worksheet(ws_title)

    return ws

def update_sheet(ws, standings, ty_apg, kd_techs):
    '''
    Write updates to a Google Sheets worksheet.

    Inputs:
    ws (gspread.models.Worksheet): worksheet to update
    standings (pandas dataframe): standings from get_standings call
    ty_apg (float): Trae Young's APG
    kd_techs (int): Kevin Durant's technical fouls
    '''
    # update standings and tie breaks
    if isinstance(standings, pd.DataFrame):
        # add headers if necessary
        for i, col in enumerate(standings.columns):
            cell = ws.acell(f'A{i + 1}')
            if not cell.value == col:
                ws.delete_rows(1)
                ws.insert_row(standings.columns.values.tolist(), index=1)
                break
        # update rows
        ws.update('A2:J16', standings.values.tolist())
        ws.update_cell(17, 1,
                       f'Last updated: {pd.Timestamp.today().ctime()} UTC')

    if isinstance(kd_techs, int):
        ws.update_cell(19, 1, 'Kevin Durant Techs:')
        ws.update_cell(19, 2, kd_techs)
        ws.update_cell(19, 3, f'Last updated: {pd.Timestamp.today().ctime()} UTC')

    if isinstance(ty_apg, float):
        ws.update_cell(20, 1, 'Trae Young APG:')
        ws.update_cell(20, 2, ty_apg)
        ws.update_cell(20, 3, f'Last updated: {pd.Timestamp.today().ctime()} UTC')
        
    ws.update_cell(21, 1, f'Automatically updated by {REF_LINK}')

if __name__ == '__main__':
    try:
        standings = get_standings(STANDINGS_FS_URL)
    except Exception as e:
        print(f'Standings: {e}')
        standings = None

    try:
        ty_apg = parse_fs_player_pg(TY_FS_AST_URL, 'APG', fxn=float)
    except Exception as e:
        print(f'TY APG: {e}')
        ty_apg = None

    try:
        kd_techs = parse_fs_player_pg(KD_FS_MISC_URL, 'TECH', fxn=int)
    except Exception as e:
        print(f'KD Techs: {e}')
        kd_techs = None

    sheet_id = SHEET_INFO['sheet_id']
    worksheet_name = SHEET_INFO['worksheet_name']

    ws = get_sheet(SERVICE_KEY_FP, sheet_id, worksheet_name)
    update_sheet(ws, standings, ty_apg, kd_techs)

    assert (isinstance(standings, pd.DataFrame) and isinstance(ty_apg, float)
            and isinstance(kd_techs, int)),\
           (f'Standings: {isinstance(standings, pd.DataFrame)}, ' +
            f'TY APG: {isinstance(ty_apg, float)}, ' +
            f'KD Techs: {isinstance(kd_techs, int)}')
