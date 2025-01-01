'''
NBA Sheets
A small script to update a Google Sheet w/ NBA standings.

Ben Fogarty
Created: 2 December 2020

Last updated: 13 November 2021
'''

import json
import logging
from datetime import datetime

from bs4 import BeautifulSoup
import gspread
import pandas as pd
import pytz
import requests

SERVICE_KEY_FP = 'service_key.json'
with open('sheet_info.json', 'r') as f:
    SHEET_INFO = json.load(f)

REF_LINK = 'https://github.com/fogarty-ben/nba-sheets/'

STANDINGS_FS_URL = 'https://www.foxsports.com/nba/standings'
BRONNY_URL = 'https://www.basketball-reference.com/players/j/jamesbr02.html'
WEMBANYAMA_URL = 'https://www.basketball-reference.com/players/w/wembavi01.html'

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
             'Cavaliers': 'Cleveland Cavaliers'
            }

COLS_MAP = {
    'Timestamp': 'timestamp',
    'Email Address': 'Email',
    'What is your name (government or d.b.a.)?': 'Name',
    'Who will end up with the 1 seed in the Western Conference?': 'Western_1',
    'Who will end up with the 2 seed in the Western Conference?': 'Western_2',
    'Who will end up with the 3 seed in the Western Conference?': 'Western_3',
    'Who will end up with the 4 seed in the Western Conference?': 'Western_4',
    'Who will end up with the 5 seed in the Western Conference?': 'Western_5',
    'Who will end up with the 6 seed in the Western Conference?': 'Western_6',
    'Who will end up with the 7 seed in the Western Conference?': 'Western_7',
    'Who will end up with the 8 seed in the Western Conference?': 'Western_8',
    'Who will end up with the 1 seed in the Eastern Conference?': 'Eastern_1',
    'Who will end up with the 2 seed in the Eastern Conference?': 'Eastern_2',
    'Who will end up with the 3 seed in the Eastern Conference?': 'Eastern_3',
    'Who will end up with the 4 seed in the Eastern Conference?': 'Eastern_4',
    'Who will end up with the 5 seed in the Eastern Conference?': 'Eastern_5',
    'Who will end up with the 6 seed in the Eastern Conference?': 'Eastern_6',
    'Who will end up with the 7 seed in the Eastern Conference?': 'Eastern_7',
    'Who will end up with the 8 seed in the Eastern Conference?': 'Eastern_8',
    'Daddy can only get you so far: How many regular season NBA games will Bronny James play in?': 'Tiebreaker_1',
    'Wembanyama? More like Wemban-NO-ma: How many total blocks will Victor Wembanyama make during the regular season?': 'Tiebreaker_2',
    'Did you do it yet?': 'paid',
    'Are picks valid?': 'are_picks_valid',
    "Bettor or media?": "Picks Source"
}

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
    col_locs = {'Rank': 0,
                'Team': 1}
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
    df['Team'] = df.Team.str.strip().map(NAMES_MAP)

    df = df.astype({'GB': float,
                    'PCT': float,
                    'Rank': int})


    return df

def get_standings(url):
    '''
    Pull standings from the Fox Sports website.

    url (str): web address of the Fox Sports NBA standings page

    Returns: two pandas dataframes
    '''
    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, 'html.parser')
    eastern_html, western_html = soup.findAll('table', class_='data-table')

    eastern_df = get_conference_standings(eastern_html)
    western_df = get_conference_standings(western_html)

    # will need to update playoff points after play-in
    western_df['Playoff Points'] = [8] * 6 + [4] * 2 + [0] * 7
    eastern_df['Playoff Points'] = [8] * 6 + [4] * 2 + [0] * 7

    western_df['Conference'] = "Western"
    eastern_df['Conference'] = "Eastern"

    standings_df = pd.concat([western_df, eastern_df], axis=0)
    standings_df = standings_df[['Conference', 'Rank', 'Team', 'W-L', 'PCT', 'GB', 'Playoff Points']]

    return standings_df

def parse_bbref_player_pg(url, row_id, stat_id, fxn=str):
    '''
    Retrieve season totals from player Basketball Reference pages.

    ** Not in use since 2022-23 **

    Inputs:
    url (str): web address of the player's profile with the stat
    row_id (str): id of the row to pull data from
    stat_id (str): data-stat attribute to pull
    fxn (function): function to cast the parsed stat to

    Returns: fxn (by default str)
    '''
    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, 'html.parser')
    data_table = soup.find('table', id='totals_stats')

    season_val = (
        data_table
        .find('tbody')
        .find('tr', id=row_id)
        .find('td', {'data-stat': stat_id})
        .text
        .strip()
    )

    return fxn(season_val)

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

    ** Not in use since 2022-23 season **

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

def parse_picks_ws(ws):
    '''
    Read each participant's picks from a Google Sheets worksheet.

    Inputs:
    ws (gspread.models.Worksheet): worksheet containing picks

    Returns: tuple of pd.DataFrame (picks) and pd.DataFrame (tiebreakers)
    '''
    df = pd.DataFrame.from_records(ws.get_all_records())
    df = df.rename(COLS_MAP, axis=1)

    is_picks_col = lambda x: (
        x in {'Email', 'Name', 'Picks Source'} or x.startswith('Western_') or x.startswith('Eastern_')
    )
    picks_col_mask = list(map(is_picks_col, df.columns))
    picks_df = df.loc[:, picks_col_mask]

    picks_df = picks_df.melt(
        id_vars=['Email', 'Name', 'Picks Source'], var_name='Pick', value_name='Team'
    )
    picks_df[['Conference', 'Picks Rank']] = (
        picks_df['Pick'].str.split('_', n=1, expand=True)
    )
    picks_df = picks_df.astype({'Picks Rank': int})
    picks_df = picks_df.drop('Pick', axis=1)

    is_tiebreakers_col = lambda x: (
        x in {'Email', 'Name', 'Picks Source'} or x.startswith('Tiebreaker_')
    )
    tiebreakers_mask = list(map(is_tiebreakers_col, df.columns))
    tiebreakers_df = df.loc[:, tiebreakers_mask]

    tiebreakers_df = tiebreakers_df.melt(
        id_vars=['Email', 'Name', 'Picks Source'], var_name='Pick', value_name='Pick Value'
    )

    tiebreakers_df[['Tiebreaker #']] = (
        tiebreakers_df['Pick'].str.split('_', n=1, expand=True).iloc[:, [1]]
    )
    tiebreakers_df = tiebreakers_df.drop('Pick', axis=1)

    return picks_df, tiebreakers_df

def summarize_standings_picks(standings_df, standings_picks_df):
    """
    Summarize the highest, lowest, most common, and percent ranked of picks by
    team.

    Inputs:
    standings_df (pd.DataFrame): standings
    standings_picks_df (pd.DataFrame): standings picks

    Returns: pd.DataFrame
    """
    standings_picks_df = standings_picks_df.loc[
        standings_picks_df['Picks Source'] == "Bettor", :
    ]

    standings_df = standings_df.loc[:, ['Conference', 'Team']].drop_duplicates()
    standings_df['__key__'] = 1
    bettors_df = standings_picks_df.loc[:, ['Email']].drop_duplicates()
    bettors_df['__key__'] = 1

    scaffold_df = (
        standings_df
        .merge(bettors_df, on='__key__', how='inner')
        .drop('__key__', axis=1)
        .merge(
            standings_picks_df, on=['Conference', 'Team', 'Email'], how='left'
        )
        .loc[:, ['Conference', 'Team', 'Picks Rank']]
    )
    scaffold_df['Picks Rank'] = scaffold_df['Picks Rank'].fillna(9)

    summary_df = (
        scaffold_df
        .groupby(['Conference', 'Team'])
        ['Picks Rank']
        .agg([
            'min',
            'max',
            'median',
            lambda x: pd.Series.mode(x).min(),
            lambda x: (x != 9).sum() / x.count()]
        )
        .reset_index()
    )
    summary_df.columns = [
        'Conference',
        'Team',
        'Highest Rank',
        'Lowest Rank',
        'Median Rank',
        'Most Common Rank',
        '# Ranked'
    ]

    for col in ["Highest Rank", "Lowest Rank", "Median Rank", "Most Common Rank"]:
        not_ranked_mask = summary_df[col] > 8
        summary_df[col] = summary_df[col].mask(not_ranked_mask, '')

    return summary_df

def get_existing_ws_names(wb):
    """
    List the names of existing worksheets in a workbook.

    Inputs:
    wb (gspread.models.Spreadsheet): workbook

    Returns: set
    """
    return set(map(lambda x: x.title, wb.worksheets()))

def write_generic(wb, ws_name, df):
    """
    Write a dataframe to a Google Sheet without modifications.

    Inputs:
    wb (spread.models.Spreadsheet): Google Sheet to update
    ws_name (str): name of the sheet to write in
    df (pd.DataFrame): data to write
    """
    n_rows, n_cols = df.shape
    n_rows += 1 # adjust for header
    if not ws_name in get_existing_ws_names(wb):
        wb.add_worksheet(title=ws_name, rows=n_rows, cols=n_cols)
        
    ws = wb.worksheet(ws_name)

    col_names = [df.columns.values.tolist()]
    values = df.values.tolist()
    data = col_names + values
    ws.update(data)

def write_tiebreakers(
    wb, ws_name, tb_1_text, tb_1_value, tb_2_text, tb_2_value
):
    """
    Write tiebreakers to the Google Sheet.

    Inputs:
    wb (spread.models.Spreadsheet): Google Sheet to update
    ws_name (str): name of the sheet to write to
    tb_1_text (str): text description of the first tiebreaker
    tb_1_value (numeric): value of the first tiebreaker
    tb_2_text (str): text description of the second tiebreaker
    tb_2_value (numeric): value of the second tiebreaker
    """
    if not ws_name in get_existing_ws_names(wb):
        wb.add_worksheet(ws_name, rows=3, cols=3)
    
    ws = wb.worksheet(ws_name)

    data = [
        ['Tiebreaker #', 'Tiebreaker Description', 'Tiebreaker Value'],
        [1, tb_1_text, tb_1_value],
        [2, tb_2_text, tb_2_value]
    ]
    ws.update(data)

def write_standings_picks(
    wb, standings_picks_ws_name, standings_picks_df, standings_ws_name
):
    """
    Write standings picks to the Google Sheet.

    Inputs:
    wb (spread.models.Spreadsheet): Google Sheet to update
    ws_name (str): name of the sheet to write to
    standings_picks_df (pd.DataFrame): standings picks data
    standings_ws_name (str): name of the sheet containing NBA standigns
    """
    n_rows, n_cols = standings_picks_df.shape
    if not standings_picks_ws_name in get_existing_ws_names(wb):
        wb.add_worksheet(title=standings_picks_ws_name, rows=n_rows + 1, cols=n_cols + 4)
        
    ws = wb.worksheet(standings_picks_ws_name)

    write_df = standings_picks_df.copy(deep=True)

    team_col_id = write_df.columns.get_loc('Team') + 1
    write_df['Standings Rank'] = [
        f"=XLOOKUP({gspread.utils.rowcol_to_a1(row_id, team_col_id)}, {standings_ws_name}!C$2:C$31, {standings_ws_name}!B$2:B$31)"
        for row_id in range(2, n_rows + 2)
    ]

    picks_rank_col_id = write_df.columns.get_loc('Picks Rank') + 1
    standings_rank_col_id = write_df.columns.get_loc('Standings Rank') + 1
    write_df["Rank Points"] = [
        f"=SWITCH(ABS({gspread.utils.rowcol_to_a1(row_id, picks_rank_col_id)} - {gspread.utils.rowcol_to_a1(row_id, standings_rank_col_id)}), 0, 7, 1, 5, 2, 3, 3, 1, 0)"
        for row_id in range(2, n_rows + 2)
    ]

    write_df['Playoff Points'] = [
        f"=XLOOKUP({gspread.utils.rowcol_to_a1(row_id, team_col_id)}, {standings_ws_name}!C$2:C$31, {standings_ws_name}!G$2:G$31)"
        for row_id in range(2, n_rows + 2)
    ]

    rank_pts_col_id = write_df.columns.get_loc('Rank Points') + 1
    playoff_pts_col_id = write_df.columns.get_loc('Playoff Points') + 1
    write_df["Total Points"] = [
        f"={gspread.utils.rowcol_to_a1(row_id, rank_pts_col_id)} + {gspread.utils.rowcol_to_a1(row_id, playoff_pts_col_id)}"
        for row_id in range(2, n_rows + 2)
    ]    

    col_names = [write_df.columns.values.tolist()]
    values = write_df.values.tolist()
    data = col_names + values
    ws.update(data, value_input_option=gspread.utils.ValueInputOption.user_entered)

def write_tiebreakers_picks(
    wb, tiebreaker_picks_ws_name, tiebreaker_picks_df, tiebreakers_ws_name
):
    """
    Write tiebreakers picks to the Google Sheet.

    Inputs:
    wb (spread.models.Spreadsheet): Google Sheet to update
    ws_name (str): name of the sheet to write to
    standings_picks_df (pd.DataFrame): tiebreakers picks data
    standings_ws_name (str): name of the sheet containing tiebreaker values
    """
    n_rows, n_cols = tiebreaker_picks_df.shape
    if not tiebreaker_picks_ws_name in get_existing_ws_names(wb):
        wb.add_worksheet(title=tiebreaker_picks_ws_name, rows=n_rows + 1, cols=n_cols + 2)
        
    ws = wb.worksheet(tiebreaker_picks_ws_name)

    write_df = tiebreaker_picks_df.copy(deep=True)

    tiebreaker_no_col_id = write_df.columns.get_loc('Tiebreaker #') + 1
    write_df["Actual Value"] = [
        f"=XLOOKUP({gspread.utils.rowcol_to_a1(row_id, tiebreaker_no_col_id)}, {tiebreakers_ws_name}!A$2:A$3, {tiebreakers_ws_name}!C$2:C$3)"
        for row_id in range(2, n_rows + 2)
    ]

    pick_value_col_id = write_df.columns.get_loc('Pick Value') + 1
    actual_value_col_id = write_df.columns.get_loc('Actual Value') + 1
    write_df['Difference'] = [
        f"=ABS({gspread.utils.rowcol_to_a1(row_id, pick_value_col_id)} - {gspread.utils.rowcol_to_a1(row_id, actual_value_col_id)})"
        for row_id in range(2, n_rows + 2)
    ]

    col_names = [write_df.columns.values.tolist()]
    values = write_df.values.tolist()
    data = col_names + values
    ws.update(data, value_input_option=gspread.utils.ValueInputOption.user_entered)

def write_update_timestamps(wb, ws_name, update_timestamps):
    """
    Write the timestamp for when each sheet was last updated.

    Inputs:
    wb (spread.models.Spreadsheet): Google Sheet to update
    ws_name (str): name of the sheet to write to
    update_timestamps (dict): key-value pairs for when each sheet was updated
    """
    is_first_write = False
    if not ws_name in get_existing_ws_names(wb):
        wb.add_worksheet(title=ws_name, rows=len(update_timestamps), cols=2)
        is_first_write = True
        
    ws = wb.worksheet(ws_name)

    data = []
    if is_first_write:
        for desc, timestamp in update_timestamps.items():
            timestamp_str = 'Never'
            if timestamp:
                timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')
            data.append([desc, timestamp_str])
    else:
        descs = ws.col_values(1)
        for i, desc in enumerate(descs):
            if desc in update_timestamps:
                timestamp = update_timestamps[desc]
                timestamp_str = ''
                if timestamp:
                    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')
                data.append([desc, timestamp_str])
            else:
                data.append([desc, ws.get(f"B{i}")])
                print(f'Update timestamp unexpected desc: {desc}')

    ws.update(data)

if __name__ == '__main__':
    try:
        sheet_id = SHEET_INFO['sheet_id']
        wb = gspread.service_account(SERVICE_KEY_FP).open_by_key(sheet_id)
    except Exception as e:
        print(f'Workbook connection error: {e}')
        raise e

    update_timestamps = {}

    try:
        standings_df = get_standings(STANDINGS_FS_URL)
        write_generic(
            wb,
            'Standings',
            standings_df,
        )
        update_timestamps['Standings'] = datetime.now(tz=pytz.utc)
    except Exception as e:
        print(f'Standings error: {e}')
        standings = None
        update_timestamps['Standings'] = None

    try:
        tiebreaker_1_text = "Bronny James games played"
        tiebreaker_1_value =  parse_bbref_player_pg(
            BRONNY_URL, 'totals_stats.2025', 'games', int
        )
        update_timestamps['Tiebreaker #1'] = datetime.now(tz=pytz.utc)
    except Exception as e:
        print(f'Tiebreaker 1 error: {e}')
        tiebreaker_1_value = None
        update_timestamps['Tiebreaker #1'] = None

    try:
        tiebreaker_2_text = "Wembanyama total blocks"
        tiebreaker_2_value = parse_bbref_player_pg(
            WEMBANYAMA_URL, 'totals_stats.2025', 'blk', int
        )
        update_timestamps['Tiebreaker #2'] = datetime.now(tz=pytz.utc)
    except Exception as e:
        print(f'Tiebreaker 2 error: {e}')
        tiebreaker_2_value = None
        update_timestamps['Tiebreaker #2'] = None

    try:
        write_tiebreakers(
            wb,
            'Tiebreakers',
            tiebreaker_1_text,
            tiebreaker_1_value,
            tiebreaker_2_text,
            tiebreaker_2_value
        )
    except Exception as e:
        print(f'Tiebreaker write error: {e}')
        update_timestamps['Tiebreaker #1'] = None
        update_timestamps['Tiebreaker #2'] = None

    try:
        responses_ws_name = SHEET_INFO['responses_ws_name']
        ws = wb.worksheet(responses_ws_name)
        standings_picks_df, tiebreaker_picks_df = parse_picks_ws(ws)
    except Exception as e:
        print(f'Response parsing error: {e}')
        picks_df, tiebreaks_df = None, None

    try:
        write_standings_picks(
            wb, 'Standings Picks', standings_picks_df, 'Standings'
        )
        update_timestamps['Standings Picks'] = datetime.now(tz=pytz.utc)
    except Exception as e:
        print(f'Standings picks write error: {e}')
        update_timestamps['Standings Picks'] = None

    try:
        write_tiebreakers_picks(
            wb, 'Tiebreaker Picks', tiebreaker_picks_df, 'Tiebreakers'
        )
        update_timestamps['Tiebreaker Picks'] = datetime.now(tz=pytz.utc)
    except Exception as e:
        print(f'Tiebreaker picks write error: {e}')
        update_timestamps['Tiebreaker Picks'] = None

    try:
        standings_picks_summary_df = summarize_standings_picks(
            standings_df, standings_picks_df
        )
        write_generic(
            wb, "Standings Picks Summary", standings_picks_summary_df
        )
        update_timestamps['Standings Picks Summary'] = datetime.now(tz=pytz.utc)
    except Exception as e:
        print(f'Standing Picks Summary error: {e}')
        update_timestamps['Standings Picks Summary'] = None

    try:
        write_update_timestamps(wb, 'Last Updated', update_timestamps)
        update_timestamps_written = True
    except Exception as e:
        print(f'Update timestamps write error: {e}')
        update_timestamps_written = False

    assert (
            update_timestamps['Standings'] is not None and
            update_timestamps['Tiebreaker #1'] is not None and
            update_timestamps['Tiebreaker #2'] is not None and
            update_timestamps['Standings Picks'] is not None and
            update_timestamps['Tiebreaker Picks'] is not None and
            update_timestamps['Standings Picks Summary'] is not None and
            update_timestamps_written
        ), (
            f"Standings: {update_timestamps['Standings'] is not None}, " +
            f"Tiebraker 1: {update_timestamps['Tiebreaker #1'] is not None}, " +
            f"Tiebreaker 2: {update_timestamps['Tiebreaker #2'] is not None}, " +
            f"Standings Picks: {update_timestamps['Standings Picks'] is not None}, " +
            f"Tiebreaker Picks: {update_timestamps['Tiebreaker Picks'] is not None}, " +
            f"Standing Picks Summary: {update_timestamps['Standings Picks Summary'] is not None}, " +
            f"Update Timestamps: {update_timestamps_written}"
        )
