'''
NBA Sheets
A small script to update a Google Sheet w/ NBA standings.

Ben Fogarty
Created: 2 December 2020

Last updated: 13 November 2021
'''

import json
import logging

from bs4 import BeautifulSoup
import gspread
import pandas as pd
import requests

SERVICE_KEY_FP = 'service_key.json'
with open('sheet_info.json', 'r') as f:
    SHEET_INFO = json.load(f)

REF_LINK = 'https://github.com/fogarty-ben/nba-sheets/'

STANDINGS_FS_URL = 'https://www.foxsports.com/nba/standings'
LBJ_URL = 'https://www.basketball-reference.com/players/j/jamesle01.html'

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

    missing_cols = {'W-L', 'PCT', 'GB'} - set(df.columns)
    for col in missing_cols:
        df[col] = 0
        logging.error(f"Standings: couldn't find {col} column")


    df['GB'] = df.GB.where(df.GB != '-', 0)
    df['PCT'] = df.PCT.where(df.PCT != '-', 0)
    df['TEAM'] = df.TEAM.str.strip().map(NAMES_MAP)

    df = df.astype({'GB': float,
                    'PCT': float,
                    'RANK': float})


    return df

def get_standings(url):
    '''
    Pull standings from the Fox Sports website.

    url (str): web address of the Fox Sports NBA standings page

    Returns: three pandas dataframes
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

    # will need to update playoff points after play-in
    standings_df['PLAYOFF POINTS'] = [8] * 6 + [4] * 2 + [0] * 7

    cols_ordered = ['RANK', 'PLAYOFF POINTS'] 
    other_cols = standings_df.columns.values.tolist()[1:-1]
    cols_ordered = cols_ordered + other_cols

    return standings_df[cols_ordered], eastern_df, western_df

def parse_bbref_player_pg(url, stat, fxn=str):
    '''
    Retrieve LeBron James' career total points from his Basketball Reference
    page.

    Inputs:
    url (str): web address of the player's profile with the stat
    fxn (function): function to cast the parsed stat to

    Returns: fxn (by default str)
    '''
    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, 'html.parser')
    data_table = soup.find('table', id='totals')

    career_val = (
        data_table
        .find('tfoot')
        .find('tr')
        .find('td', {'data-stat': 'pts'})
        .text
        .strip()
    )

    return fxn(career_val)

def parse_bbref_mvp_tracker(url, player, fxn=str):
    '''
    Retrieve a player's current standing in the Basketball Reference MVP
    standings model.

    ** Not in use since 2021-22 season **

    Inputs:
    url (str): web address of the BBRef standings model
    player (str): name of the player to search for
    fxn (function): function to cast the parsed ranking to

    Returns: fxn (by default string)
    '''
    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, 'html.parser')
    data_table = soup.find('table', id='players')
    table_body = data_table.find('tbody')


    for row in table_body.findAll('tr', ):
        ranking = row.find('th', {'data-stat': 'ranker'}).text
        player_col = row.find('td', {'data-stat': 'player'})
        player_name = player_col.text
        if player_name.lower() == player.lower():
            return fxn(ranking)

    return fxn('Unranked')

def get_combined_wins(
        eastern_standings, western_standings, n_teams, worst=True, fxn=str
    ):
    '''
    Get the total number of wins across the best/worst n_teams in the league by
    winning pct.

    Inputs:
    eastern_standings/western_standings (pd.DataFrame): standings dataframes
        from get_conference_standings(...)
    n_teams (int): number of teams to sum the wins of
    worst (bool): if True, sum across the worst teams; if False, sum across the
        best teams
    fxn (function): function to cast the parsed ranking to


    Returns: fxn (by default str)
    '''
    for df in [eastern_standings, western_standings]:
        df.rename(lambda x: x[5:], axis=1, inplace=True)
    return fxn(
        eastern_standings
        .append(western_standings)
        .sort_values('PCT', ascending=worst)
        .head(n_teams)
        ['W-L']
        .str.extract(r'^(\d+)')
        .astype(int)
        .sum()
        .squeeze()
    )

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

def update_sheet(ws, standings, bot_3_wins, lj_career_points):
    '''
    Write updates to a Google Sheets worksheet.

    Inputs:
    ws (gspread.models.Worksheet): worksheet to update
    standings (pandas dataframe): standings from get_standings call
    bot_3_wins (str): Bottom three teams combined wins
    lj_career_points (str): LeBron James career points 
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
        standings.to_csv('standings.csv')
        ws.update('A2:J16', standings.values.tolist())
        ws.update_cell(17, 1,
                       f'Last updated: {pd.Timestamp.today().ctime()} UTC')

    if isinstance(bot_3_wins, int):
        ws.update_cell(19, 1, 'Combined wins of bottom three teams:')
        ws.update_cell(19, 2, bot_3_wins)
        ws.update_cell(19, 3, f'Last updated: {pd.Timestamp.today().ctime()} UTC')

    if isinstance(lj_career_points, int):
        ws.update_cell(20, 1, 'LeBron James career points:')
        ws.update_cell(20, 2, lj_career_points)
        ws.update_cell(20, 3, f'Last updated: {pd.Timestamp.today().ctime()} UTC')
        
    ws.update_cell(21, 1, f'Automatically updated by {REF_LINK}')

if __name__ == '__main__':
    try:
        standings, eastern_df, western_df = get_standings(STANDINGS_FS_URL)
    except Exception as e:
        print(f'Standings: {e}')
        standings = None

    try:
        bot_3_wins = get_combined_wins(
        eastern_df, western_df, 3, worst=True, fxn=int
    )
    except Exception as e:
        print(f'Bottom three teams combined wins: {e}')
        bot_3_wins = None

    try:
        lj_career_points = parse_bbref_player_pg(LBJ_URL, 'USG%', fxn=int)
    except Exception as e:
        print(f'LeBron James career points: {e}')
        lj_career_points = None

    sheet_id = SHEET_INFO['sheet_id']
    worksheet_name = SHEET_INFO['worksheet_name']

    ws = get_sheet(SERVICE_KEY_FP, sheet_id, worksheet_name)
    update_sheet(ws, standings, bot_3_wins, lj_career_points)

    assert (isinstance(standings, pd.DataFrame) and isinstance(bot_3_wins, int)
            and isinstance(lj_career_points, int)),\
           (f'Standings: {isinstance(standings, pd.DataFrame)}, ' +
            f'Bottom three teams combined wins: {isinstance(bot_3_wins, int)}, ' +
            f'LeBron James career points: {isinstance(lj_career_points, int)}')
