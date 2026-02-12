# Librerías de análisis de datos
import json
import pandas as pd
from typing import Any, Dict
import os
import numpy as np
import time

# Librerías para acceder a la página web
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===========================================================================================================================================
# FUNCIÓN 1. ENTRA AL LINK DADO EL DRIVER Y EL URL DE LA PÁGINA
# ===========================================================================================================================================
def page_scraper(driver, page_url: str, timeout: int = 10) -> Dict[str, Any]:

    # Usando el driver, entramos a la página - definimos un timeout en segundos por si se tarda
    driver.get(page_url)
    pre = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "pre")))

    # Convertimos los datos en formato JSON
    data_json = json.loads(pre.text)
    return(data_json)

# ===========================================================================================================================================
# FUNCIÓN 2. DADA UNA LIGA, OBTENEMOS UNA LISTA CON LOS IDENTIFICADORES DEL PARTIDO
# ===========================================================================================================================================
def league_matches(driver, league_info_df: pd.DataFrame, league: str, season: str) -> list:

    # Obtenemos la parte del dataframe de la liga
    league_info = league_info_df[(league_info_df['League'] == league) & (league_info_df['Season'] == season)]

    # ID de liga y de temporada
    league_ss_id = league_info['SofascoreLeagueID'].iloc[0]
    season_ss_id = league_info['SofascoreSeasonID'].iloc[0]

    # Lista con los IDs y i para concatenar
    all_matches_ids = []
    i = 0

    # Concatenamos en las páginas de la API mientras pudamos
    while True:
        # URL y scraping
        url = f'https://api.sofascore.com/api/v1/unique-tournament/{league_ss_id}/season/{season_ss_id}/events/last/{i}'
        league_json_info = page_scraper(driver, url)

        # Cortamos si no podemos seguir
        if not league_json_info.get('events'):
            break

        # IDs parcial y concatemaos
        part_matches_id = [event['id'] for event in league_json_info['events']]
        all_matches_ids.extend(part_matches_id)

        i += 1

    return all_matches_ids

# ===========================================================================================================================================
# FUNCIÓN 3. DADO EL ID DE UN PARTIDO, NOS DEVUELVE INFORMACIÓN BÁSICA SOBRE ESTE
# ===========================================================================================================================================
def match_information(driver, league: str, season: str, match_id: int) -> dict:

    # URL y leemos
    event_url = f'https://api.sofascore.com/api/v1/event/{match_id}'
    scraped_event = page_scraper(driver=driver, page_url=event_url)
    match_event = scraped_event['event']

    # Información a obtener
    match_info = {'id': match_event.get('id'),
                  'league': league,
                  'season': season,
                  'slug': f'{match_event.get('slug')}-{season.split('/')[0]}{season.split('/')[1]}',
                  'round': match_event.get('roundInfo', {}).get('round', np.nan),
                  'date': match_event.get('startTimestamp', np.nan),
                  'venue': match_event.get('venue', {}).get('name', np.nan), 
                  'attendance': match_event.get('attendance', np.nan), 
                  'referee': match_event.get('referee', {}).get('name', np.nan),
                  'home_team': match_event.get('homeTeam', {}).get('name', np.nan), 
                  'away_team': match_event.get('awayTeam', {}).get('name', np.nan),
                  'home_score': match_event.get('homeScore', {}).get('display', np.nan),
                  'away_score': match_event.get('awayScore', {}).get('display', np.nan)}
    
    return pd.DataFrame([match_info]), match_info['home_team'], match_info['away_team'], match_info['slug']

# ===========================================================================================================================================
# FUNCIÓN 4. DADO EL ID DE UN PARTIDO, NOS ENCUENTRA INFORMACIÓN Y ESTADÍSTICAS DE LOS JUGADORES A PARTIR DE LA INFORMACIÓN
# ===========================================================================================================================================
def match_player_info_stats(driver, proc_players: list, match_id: int, league: str, season: str, home_team: str, away_team: str, match_slug: str) -> pd.DataFrame:

    # URL y lo leemos
    url = f'https://api.sofascore.com/api/v1/event/{match_id}/lineups'
    match_json = page_scraper(driver, url)

    # Lista con el diccionario con información de los jugadores y con las estadísticas
    players_info = []
    players_stats = []

    # Para cada jugador en el equipo local
    for player in match_json.get('home', {}).get('players', {}):

        # Información del jugador
        player_info = player.get('player', {})
        player_slug = player_info.get('slug')
        team_slug = home_team.lower().replace(" ", "-")
        player_slug_season = f'{player_slug}-{team_slug}-{season.split('/')[0]}{season.split('/')[1]}'

        # Buscamos las estadísticas del jugador y las añadimos - también el slug para identificarlo
        player_statistics = player.get('statistics', {})
        player_statistics = {"league": league,
                             "season": season,
                             "match": match_id,
                             "slug": player_slug,
                             "team_slug": team_slug,
                             "match_slug": match_slug,
                             "starter": False if player['substitute'] else True,
                             "home": True,
                             **player_statistics}
        
        # Eliminar claves si existen - nos van a dar problemas al no ser numericas
        player_statistics.pop("ratingVersions", None)
        player_statistics.pop("statisticsType", None)

        # Añadimos las estadísticas a la lista
        players_stats.append(player_statistics)

        # Únicamente si el jugador no esta procesado en aquella temporada
        if player_slug_season not in proc_players:

            # Creamos un diccionario con la información del jugador
            player_info_dict = {'slug': player_slug,
                                'slug_season': player_slug_season,
                                'league': league,
                                'season': season,
                                'team_slug': team_slug, 
                                'name': player_info.get('name', np.nan),
                                'short_name': player_info.get('shortName', np.nan),
                                'position': player_info.get('position', np.nan),
                                'jersey_number': player_info.get('jerseyNumber', np.nan),
                                'height': player_info.get('height', np.nan),
                                'country': player_info.get('country', {}).get('name', np.nan),
                                'market_value': player_info.get('proposedMarketValueRaw', {}).get('value', np.nan),
                                'date_birth': player_info.get('dateOfBirthTimestamp', np.nan)}
            
            # Añadimos al jugador a nuestra lista
            players_info.append(player_info_dict)

    # Idem para el equipo visitante
    for player in match_json.get('away', {}).get('players', {}):

        # Información del jugador
        player_info = player.get('player', {})
        player_slug = player_info.get('slug')
        team_slug = away_team.lower().replace(" ", "-")
        player_slug_season = f'{player_slug}-{team_slug}-{season.split('/')[0]}{season.split('/')[1]}'

        # Buscamos las estadísticas del jugador y las añadimos - también el slug para identificarlo
        player_statistics = player.get('statistics', {})
        player_statistics = {"league": league,
                             "season": season,
                             "match": match_id,
                             "slug": player_slug,
                             "team_slug": team_slug,
                             "match_slug": match_slug,
                             "starter": False if player['substitute'] else True,
                             "home": False,
                             **player_statistics}
        
        # Eliminar claves si existen - nos van a dar problemas al no ser numericas
        player_statistics.pop("ratingVersions", None)
        player_statistics.pop("statisticsType", None)

        # Añadimos las estadísticas a la lista
        players_stats.append(player_statistics)

        # Únicamente si el jugador no esta procesado en aquella temporada
        if player_slug_season not in proc_players:

            # Creamos un diccionario con la información del jugador
            player_info_dict = {'slug': player_slug,
                                'slug_season': player_slug_season,
                                'league': league,
                                'season': season,
                                'team_slug': team_slug, 
                                'name': player_info.get('name', np.nan),
                                'short_name': player_info.get('shortName', np.nan),
                                'position': player_info.get('position', np.nan),
                                'jersey_number': player_info.get('jerseyNumber', np.nan),
                                'height': player_info.get('height', np.nan),
                                'country': player_info.get('country', {}).get('name', np.nan),
                                'market_value': player_info.get('proposedMarketValueRaw', {}).get('value', np.nan),
                                'date_birth': player_info.get('dateOfBirthTimestamp', np.nan)}
            
            # Añadimos al jugador a nuestra lista
            players_info.append(player_info_dict)

    # Convertimos la información de los jugadores en un dataframe
    return pd.DataFrame(players_info), pd.DataFrame(players_stats)

# ===========================================================================================================================================
# FUNCIÓN 5. DADA UNA TEMPORADA Y UNA LIGA, PROCEDE A HACER EL SCRAPING COMPLETO DE PARTIDOS, INFORMACIÓN DE JUGADORES Y ESTADÍSTICAS
# ===========================================================================================================================================
def full_league_season_scraper(driver, league_info_path: str, match_info_path: str, player_info_path: str, player_stats_path: str,
                               league_info_df: pd.DataFrame, match_info_df: pd.DataFrame, player_info_df: pd.DataFrame, player_stats_df: pd.DataFrame,
                               proc_players: list, proc_matches: list, league: str, season: str, limit_matches: int = None) -> None:

    # Obtenemos los partidos jugados en la liga
    matches_ids = league_matches(driver=driver, league_info_df=league_info_df, league=league, season=season)
    total_league_matches = len(matches_ids)
    matches_to_process = [m for m in matches_ids if m not in proc_matches]              # Partidos a procesar

    # Para el print de información - contadores
    num_match = 1
    total_matches_to_proc = len(matches_to_process) if limit_matches is None else limit_matches    # Partidos a procesar

    # Si no hay partidos a procesar, return
    if total_matches_to_proc == 0:
        return league_info_df, match_info_df, player_info_df, player_stats_df, proc_players, proc_matches, total_league_matches
    
    # Print de información para mostrar que empezamos a procesar una liga
    print('=======================================================================================================')
    print(f'STARTING THE PROCESSING OF THE LEAGUE "{league}" - SEASON {season} (Total matches to process: {total_matches_to_proc})')
    print('-------------------------------------------------------------------------------------------------------')

    # Para cada partido, obtenemos los datos
    for match_id in matches_to_process[:total_matches_to_proc]:
        
        # Información del partido
        match_info, home_team, away_team, match_slug = match_information(driver=driver, league=league, season=season, match_id=match_id)

        # Obtenemos información y las estadísticas de los jugadores
        match_player_info_df, match_player_stats_df = match_player_info_stats(driver=driver, proc_players=proc_players, match_id=match_id, league=league, season=season, 
                                                                              home_team=home_team, away_team=away_team, match_slug=match_slug)

        # ==============================================================================================
        # INFORMACIÓN DEL PARTIDO
        # ==============================================================================================

        # Concatenamos con el dataframe anterior
        match_info_df = pd.concat([match_info_df, match_info], ignore_index=True).drop_duplicates()
        match_info_df = match_info_df.sort_values(by='date')
        match_info_df.to_csv(match_info_path, sep=';', index=False)

        # Añadimos los IDs de partidos a la lista de partidos
        proc_matches.extend(match_info['id'].unique().tolist())
        proc_matches = list(set(proc_matches))
        proc_matches = sorted(proc_matches)

        # ==============================================================================================
        # INFORMACIÓN DE LOS JUGADORES
        # ==============================================================================================
        
        # Añadimos los valores al dataframe y borramos duplicados - guardamos dataframe
        player_info_df = pd.concat([player_info_df, match_player_info_df], ignore_index=True).drop_duplicates()
        player_info_df = player_info_df.sort_values(by='slug')
        player_info_df.to_csv(player_info_path, sep=';', index=False)
        
        # Añadimos los jugadores a la lista de procesados, la ordenamos por nombre de jugador y eliminamos dup
        if (not match_player_info_df.empty and 'slug_season' in match_player_info_df.columns):
            proc_players.extend(match_player_info_df['slug_season'].unique().tolist())
        proc_players = list(set(proc_players))
        proc_players = sorted(proc_players)

        # ==============================================================================================
        # ESTADÍSTICAS DE LOS JUGADORES
        # ==============================================================================================

        # Concatenamos con el dataframe
        player_stats_df = pd.concat([player_stats_df, match_player_stats_df], ignore_index=True).drop_duplicates()
        player_stats_df = player_stats_df.sort_values(by='slug')
        player_stats_df.to_csv(player_stats_path, sep=';', index=False)

        # ==============================================================================================
        # PRINT DE INFORMACIÓN
        # ==============================================================================================
        print(f'[{num_match}/{total_matches_to_proc}] {home_team} - {away_team} PROCESSED')
        num_match += 1

        # ==============================================================================================
        # WAIT DE 3 SEGUNDOS
        # ==============================================================================================
        time.sleep(3)

    # Print de terminar de procesar
    print('-------------------------------------------------------------------------------------------------------')
    print(f'ENDED PROCESSING OF THE LEAGUE "{league}" - SEASON {season} (Matches processed: {total_matches_to_proc})')
    print('=======================================================================================================')
    return league_info_df, match_info_df, player_info_df, player_stats_df, proc_players, proc_matches, total_league_matches

# ===========================================================================================================================================
# FUNCIÓN PRINCIPAL. A PARTIR DEL DRIVER OBTENEMOS TODA LA INFORMACIÓN DE TODAS LAS TEMPORADAS QUE TENEMOS
# ===========================================================================================================================================
def main_scraping(driver, data_path: str):

    # Creamos los paths de los CSVs con información
    league_info_path = f'{data_path}/raw/LeagueInfo.csv'
    match_info_path = f'{data_path}/raw/MatchInfo.csv'
    player_info_path = f'{data_path}/raw/PlayerInfo.csv'
    player_stats_path = f'{data_path}/raw/PlayerStats.csv'

    # Leemos los CSVs con información en caso de que existan
    league_info_df = pd.read_csv(league_info_path, sep=';') if os.path.exists(league_info_path) else pd.DataFrame()
    match_info_df = pd.read_csv(match_info_path, sep=';') if os.path.exists(match_info_path) else pd.DataFrame()
    player_info_df = pd.read_csv(player_info_path, sep=';') if os.path.exists(player_info_path) else pd.DataFrame()
    player_stats_df = pd.read_csv(player_stats_path, sep=';') if os.path.exists(player_info_path) else pd.DataFrame()

    # Obtenemos los jugadores procesados y los partidos procesados
    proc_players = [] if player_info_df.empty else player_info_df['slug_season'].unique().tolist()
    proc_matches = [] if match_info_df.empty else match_info_df['id'].unique().tolist()

    # Actual season
    actual_season = '25/26'

    # Para cada liga en nuestro dataframe
    for _, row in league_info_df.iterrows():

        # Liga y temporada
        league_to_proc = row['League']
        season_to_proc = row['Season']

        # Comprovamos que no se hayan procesado todos los partidos - en caso de que la temporada no sea la actual
        if (row['ProcessedMatches'] != 0) and (row['ProcessedMatches'] == row['TotalMatches']) and (season_to_proc != actual_season):
            continue
        
        # Procesamos la liga
        league_info_df, match_info_df, player_info_df, player_stats_df, proc_players, proc_matches, total_league_matches = full_league_season_scraper(driver=driver, league_info_path=league_info_path, match_info_path=match_info_path, player_info_path=player_info_path,
                                                        player_stats_path=player_stats_path, league_info_df=league_info_df, match_info_df=match_info_df,
                                                        player_info_df=player_info_df, player_stats_df=player_stats_df, proc_players=proc_players,
                                                        proc_matches=proc_matches, league=league_to_proc, season=season_to_proc)    # A la ejecución final, no limitamos

        # Creamos la máscara para actualizar y actualizamos las métricas
        mask = ((league_info_df['League'] == league_to_proc) & (league_info_df['Season'] == season_to_proc))
        league_info_df.loc[mask, 'ProcessedMatches'] = len(match_info_df[(match_info_df['league'] == league_to_proc) & (match_info_df['season'] == season_to_proc)])
        league_info_df.loc[mask, 'TotalMatches'] = total_league_matches
        league_info_df.to_csv(league_info_path, sep=';', index=False)
    
    driver.quit()           # Cerrar el driver

# if __name__ == "__main__":
#     main_scraping(driver=driver, data_path="G:\\FootballData\\data")