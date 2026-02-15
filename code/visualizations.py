import pandas as pd
import os
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json

# Filtrador de dataframes a partir de filtros
def dataframe_filter(df_original: pd.DataFrame, league: str = None, season: str = None, team: str = None, player: str = None):
    df = df_original.copy()

    # Filtramos por liga
    if league is not None:
        if "league" in df.columns:
            df = df[df['league'] == league]     # Filtro
    
    # Filtramos por temporada
    if season is not None:
        if "season" in df.columns:
            df = df[df['season'] == season]

    # Filtramos por equipo
    if team is not None:
        if "team_slug" in df.columns:
            team_slug = team.lower().replace(" ", "-")      # Conversioin a slug
            df = df[df['team_slug'] == team_slug]

    # Filtramos por jugador
    if player is not None:
        if "player_slug" in df.columns:
            player_slug = player.lower().replace(" ", "-")      # Conversioin a slug
            df = df[df['player_slug'] == player_slug]

    return df

# Función para sacar las rows con outliers según columnas
def remove_outliers_iqr(df: pd.DataFrame, cols, k=2) -> pd.DataFrame:

    df_clean = df.copy()

    for col in cols:
        Q1 = df_clean[col].quantile(0.25)
        Q3 = df_clean[col].quantile(0.75)
        IQR = Q3 - Q1

        lower = Q1 - k * IQR
        upper = Q3 + k * IQR

        df_clean = df_clean[(df_clean[col] >= lower) & (df_clean[col] <= upper)]

    return df_clean

# ===========================================================================================================================================
# FUNCIÓN 1 - CREACIÓN DE VISUALIZACIONES Y TABLAS SOBRE UNA ÚNICA TEMPORADA, COMPARANDO LIGAS
# ===========================================================================================================================================
def create_season_visualizations(data_path: str, season: str) -> list:

    # A partir de una temporada, obtenemos métricas relevantes para estudiar y comprarar las distintas ligas
    def season_league_comparison_metrics(player_stats_summary_df: pd.DataFrame, goalkeeper_pct_df: pd.DataFrame, defender_pct_df: pd.DataFrame, midfielder_pct_df: pd.DataFrame, forward_pct_df: pd.DataFrame, season: str) -> pd.DataFrame:
        
        # Filtrado del dataframe
        season_df = dataframe_filter(df_original=player_stats_summary_df, season=season)

        # Selección de columnas
        season_df = season_df[['league','Minutes','expectedGoals','goals','attack_value_raw','bigChanceCreated','totalShots','def_actions','duelWon',
                            'aerialWon','fouls','interceptionWon','progressiveBallCarriesCount','passValueNormalized']]

        # Columnas a las cuales vamos a aplicar x90
        cols_per90 = ['expectedGoals','goals','attack_value_raw','bigChanceCreated','totalShots',
                    'def_actions','duelWon','aerialWon','fouls','interceptionWon','progressiveBallCarriesCount']

        # Filtramos jugadores com 0 minutos (poco usual)
        season2526 = season_df[season_df['Minutes'] > 0].copy()

        # Calcular factor per90
        season2526[[c for c in cols_per90]] = (season_df[cols_per90].div(season_df['Minutes'], axis=0).mul(90))       # Mantenemos el mismo nombre

        # Aplicamos los nombres a las columnas
        season_df.columns = ['League','Minutes','ExpectedGoalsPer90','GoalsPer90','AttackValuePer90','BigChancesPer90','ShotsPer90',
                            'DefensiveActionsPer90','DuelsWonPer90','AerialWonPer90','FoulsPer90','InterceptionsPer90','ProgresionsPer90',
                            'PassValueNormalized']

        # Sacamos la columna de minutos
        season_df = season_df.drop(['Minutes'], axis=1)

        # Obtenemos las medidas medias por liga
        season_df = (season_df.groupby('League', as_index=False).mean(numeric_only=True))

        # Obtenemos otras métricas que vamos a usar
        season_df['AttackValue'] = season_df['ExpectedGoalsPer90'] + season_df['BigChancesPer90'] + season_df['AttackValuePer90']
        season_df['DeffenseValue'] = season_df['DefensiveActionsPer90'] + season_df['DuelsWonPer90'] + season_df['AerialWonPer90'] + season_df['InterceptionsPer90']
        season_df['ProgressionValue'] = season_df['ProgresionsPer90'] + season_df['PassValueNormalized']

        # Obtenemos el valor medio de cada variable de los percentiles por liga - función para hacerlo
        def get_season_percentiles_medians(df: pd.DataFrame, season: str) -> pd.DataFrame:

            # Filtramos por liga
            df_filtered = dataframe_filter(df_original=df, season=season).drop(['season', 'player_name', 'player_slug'], axis=1)

            # Agrupamos por liga - obtenemos la mediana
            df_filtered = (df_filtered.groupby('league', as_index=False).median(numeric_only=True))

            return df_filtered

        # Calculamos para cada posición las medianas y cambiamos los nombres en las colunnas
        mean_league_gk_df = get_season_percentiles_medians(df=goalkeeper_pct_df, season=season)
        mean_league_gk_df.columns = ['League','PctShotStoppingGK','PctReliabilityGK','PctAreaControlGK','PctSweeperKeeperGK','PctBuildUpPlayGK']
        mean_league_df_df = get_season_percentiles_medians(df=defender_pct_df, season=season)
        mean_league_df_df.columns = ['League','PctDefensiveActionsDF','PctDuelsDF','PctAerialAbilityDF','PctBuildUpPlayDF','PctDefensiveReliabilityDF']
        mean_league_md_df = get_season_percentiles_medians(df=midfielder_pct_df, season=season)
        mean_league_md_df.columns = ['League','PctBallDistributionMD','PctProgressionMD','PctChanceCreationMD','PctDefensiveBalanceMD','PctBallRetentionMD']
        mean_league_fw_df = get_season_percentiles_medians(df=forward_pct_df, season=season)
        mean_league_fw_df.columns = ['League','PctFinishingFW','PctChanceCreationFW','PctThreatFW','PctOffBallInvolvementFW','PctEfficiencyFW']

        # Unimos el dataframe de información de la liga con la de sus posiciones en uno general
        all_league_info = pd.merge(season_df, mean_league_gk_df, on='League')
        all_league_info = pd.merge(all_league_info, mean_league_df_df, on='League')
        all_league_info = pd.merge(all_league_info, mean_league_md_df, on='League')
        all_league_info = pd.merge(all_league_info, mean_league_fw_df, on='League')

        # Colores de las ligas para diferenciar
        LEAGUE_COLORS = {"Bundesliga": "#D20515", "La Liga": "#FF8C00", "Ligue 1": "#0055A4",
                        "Premier League": "#6A0DAD", "Serie A": "#008C45"}
        all_league_info['Color'] = all_league_info['League'].map(LEAGUE_COLORS)

        return all_league_info

    # Creación de un scatterplot de amenaza ofensiva de la liga
    def offensive_thread_scatter_creation(df: pd.DataFrame, season: str, figures_path: str = None):

        # SCATTERPLOT PARA LA AMENAZA OFENSIVA PARA CADA LIGA - Compara goles esperados con tiros y goles finales
        scatter_offensive_thread = px.scatter(df, x="ExpectedGoalsPer90", y="ShotsPer90", color="GoalsPer90",     # Color gradiente
                                            text="League", color_continuous_scale="Reds",  size_max=60)

        # Mostramos un texto con la liga encima del punto para una mejor comprensión
        scatter_offensive_thread.update_traces(textposition="top center", marker=dict(size=20, line=dict(width=1)))

        # Layout de título y ejes
        scatter_offensive_thread.update_layout(
            title=dict(text=f"AMENAZA OFENSIVA DE LAS CINCO GRANDES LIGAS - TEMPORADA {season}<br><sup> Tiros por 90 vs. Goles esperados por 90 vs. Goles por 90 (media por jugador)</sup>",  # Subtitulo
                    x=0.5),
            xaxis_title="Goles esperados por 90", yaxis_title="Tiros por 90",
            coloraxis_colorbar=dict(title="Goles por 90"))
        
        # Guardamos si el path no es nulo
        if figures_path is not None:
            name_figure = f'LeaguesAttackingThreadComparison{season.replace('/','')}.png'       # Nombre de la figura   
            final_figure_path = os.path.join(figures_path, name_figure)                         # Nombre final del path a guardar la figura
            scatter_offensive_thread.write_image(final_figure_path, width=1400, height=800, scale=2)    # Guardado de la figura

        return scatter_offensive_thread

    # Comparación de las ligas más físicas a partir de valores de duelos
    def physicality_map_creation(df: pd.DataFrame, season: str, figures_path: str = None): 

        # SCATTERPLOT DE POTENCIA FÍSICA POR LIGA - compara duelos y duelos aereos ganados
        scatter_physicality = px.scatter(df, x="DuelsWonPer90", y="AerialWonPer90", color="Color",     # Color de la lga
                                        text="League", size_max=60)

        # Mostramos un texto con la liga encima del punto para una mejor comprensión
        scatter_physicality.update_traces(textposition="top center", marker=dict(size=20, line=dict(width=1)))

        # Layout de título y ejes
        scatter_physicality.update_layout(
            title=dict(text=f"MAPA DE PORTENTO FÍSICO POR LIGA - TEMPORADA {season}<br><sup> Duelos ganados por 90 vs. Duelos aereos (media por jugador)</sup>",  # Subtitulo
                    x=0.5),
            xaxis_title="Duelos ganados por 90", yaxis_title="Duelos aereos por 90", showlegend=False)
        
        # Guardamos si el path no es nulo
        if figures_path is not None:
            name_figure = f'LeaguesPhysicalityMap{season.replace('/','')}.png'       # Nombre de la figura   
            final_figure_path = os.path.join(figures_path, name_figure)                         # Nombre final del path a guardar la figura
            scatter_physicality.write_image(final_figure_path, width=1400, height=800, scale=2)    # Guardado de la figura

        return scatter_physicality

    # Comparación del estilo físico de las ligas
    def tactical_style_creation(df: pd.DataFrame, season: str, figures_path: str = None): 

        # SCATTERPLOT DE ESTILO TÁCTICO POR LIGA - comparación de valores defensivos y ofensivos
        scatter_tact_style = px.scatter(df, x="DeffenseValue", y="AttackValue", color="Color",     # Color de la lga
                                        text="League", size_max=60)

        # Mostramos un texto con la liga encima del punto para una mejor comprensión
        scatter_tact_style.update_traces(textposition="top center", marker=dict(size=20, line=dict(width=1)))

        # Layout de título y ejes
        scatter_tact_style.update_layout(
            title=dict(text=f"ESTILO TÁCTICO POR LIGA - TEMPORADA {season}<br><sup> Comparación de métricas defensivas y ofensivas a partir de los datos de los jugadores</sup>",  # Subtitulo
                    x=0.5),
            xaxis_title="Valor defensivo", yaxis_title="Valor ofensivo", showlegend=False)
        
        # Guardamos si el path no es nulo
        if figures_path is not None:
            name_figure = f'LeaguesTacticalStyle{season.replace('/','')}.png'       # Nombre de la figura   
            final_figure_path = os.path.join(figures_path, name_figure)                         # Nombre final del path a guardar la figura
            scatter_tact_style.write_image(final_figure_path, width=1400, height=800, scale=2)    # Guardado de la figura

        return scatter_tact_style

    # Creación de un gráfico de radar para mostrar los percentiles por cada posición y liga
    def radar_5metrics_creation(df: pd.DataFrame, position: str, season: str, title: str, figures_path: str = None):

        # Labels según posición
        if position == 'Goalkeeper':
            labels = {'PctShotStoppingGK': 'Shot Stopping', 'PctReliabilityGK': 'Reliability', 'PctAreaControlGK': 'Area Control', 'PctSweeperKeeperGK': 'Sweeper Keeper', 'PctBuildUpPlayGK': 'Build-up Play'}
            
        elif position == 'Defender':
            labels = {'PctDefensiveActionsDF': 'Defensive Actions', 'PctDuelsDF': 'Duels', 'PctAerialAbilityDF': 'Aerial Ability', 'PctBuildUpPlayDF': 'Build-up Play', 'PctDefensiveReliabilityDF': 'Defensive Reliability'}
            
        elif position == 'Midfielder':
            labels = {'PctBallDistributionMD': 'Ball Distribution', 'PctProgressionMD': 'Progression', 'PctChanceCreationMD': 'Chance Creation', 'PctDefensiveBalanceMD': 'Defensive Balance', 'PctBallRetentionMD': 'Ball Retention'}

        elif position == 'Forward':
            labels = {'PctFinishingFW': 'Finishing', 'PctChanceCreationFW': 'Chance Creation', 'PctThreatFW': 'Threat', 'PctOffBallInvolvementFW': 'Ball Involvement', 'PctEfficiencyFW': 'Efficiency'}

        # Metricas
        metrics = list(labels.keys())

        # Categorias a mostrar
        categories = [labels.get(m, m) for m in metrics]
        categories = categories + [categories[0]]

        # Calculamos el rango dinámico del radar para mejorar la comprensión
        global_min = df[metrics].min().min() - 0.01
        global_max = df[metrics].max().max() + 0.01

        # Creación de la figura
        radar = go.Figure()

        # Una línea para cada liga
        for _, row in df.iterrows():
            values = [row[m] for m in metrics] + [row[metrics[0]]]
            trace_kwargs = dict(r=values, theta=categories, name=str(row['League']), mode="lines+markers", line=dict(width=2), marker=dict(size=6))

            # Pintamos de color
            trace_kwargs["line"]["color"] = row['Color']
            trace_kwargs["marker"]["color"] = row['Color']

            radar.add_trace(go.Scatterpolar(**trace_kwargs))

        # Títulos del gráfico
        radar.update_layout(
            title=dict(text=title, x=0.5, xanchor="center"),
            polar=dict(radialaxis=dict(visible=True,range=[global_min, global_max])),
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
            margin=dict(b=100))
        
        # Guardamos si el path no es nulo
        if figures_path is not None:
            name_figure = f'Leagues{position}RadarChart{season.replace('/','')}.png'       # Nombre de la figura   
            final_figure_path = os.path.join(figures_path, name_figure)                         # Nombre final del path a guardar la figura
            radar.write_image(final_figure_path, width=1400, height=800, scale=2)    # Guardado de la figura
        
        return radar

    # Creación de un violin plot de la metrica que queramos
    def violin_plot_creation(df: pd.DataFrame, metric: str, metric_title: str, season: str, subtitle: str, figures_path: str = None):

        # Ligas, colores
        leagues = ['Serie A', 'Bundesliga', 'La Liga', 'Ligue 1', 'Premier League']
        border_color = {"Bundesliga": "rgba(210, 5, 21, 1)", "La Liga": "rgba(255, 140, 0, 1)", "Ligue 1": "rgba(0, 85, 164, 1)",
                        "Premier League": "rgba(106, 13, 173, 1)", "Serie A": "rgba(0, 140, 69, 1)"}
        fill_color = {"Bundesliga": "rgba(210, 5, 21, 0.3)", "La Liga": "rgba(255, 140, 0, 0.3)", "Ligue 1": "rgba(0, 85, 164, 0.3)",
                    "Premier League": "rgba(106, 13, 173, 0.3)", "Serie A": "rgba(0, 140, 69, 0.3)"}
        
        # Creación del violin plot
        violin = go.Figure()

        # Por liga creamos el violin
        for league in leagues:

            # Info
            df_league = df[df['league'] == league]
            violin.add_trace(go.Violin(x=df_league['league'], y=df_league[metric], name=league, box_visible=True, 
                            meanline_visible=True, fillcolor=fill_color[league], line_color=border_color[league]))
            
        # Layout
        title = "COMPARACIÓN DE LA DISTRIBUCIÓN DE LOS PERCENTILES"
        violin.update_layout(title=dict(text=f"{title}<br><sup> {subtitle}</sup>", x=0.5, xanchor="center"), yaxis_title='Value')

        # Guardamos si el path no es nulo
        if figures_path is not None:
            name_figure = f'Leagues{metric_title}ViolinChart{season.replace('/','')}.png'       # Nombre de la figura   
            final_figure_path = os.path.join(figures_path, name_figure)                         # Nombre final del path a guardar la figura
            violin.write_image(final_figure_path, width=1400, height=800, scale=2)    # Guardado de la figura
        
        return violin
        
    # Paths de procesado y figuras
    proc_data_path = os.path.join(data_path, 'clean')
    all_figures_path = os.path.join(data_path, 'images')

    # Creamos el path de imagenes de la temporada
    figures_path = os.path.join(all_figures_path, season.replace('/', ''), 'seasons')
    os.makedirs(figures_path, exist_ok=True)

    # Lectura de todos los datos que necesitaremos
    player_team_stats_summary_df = pd.read_csv(os.path.join(proc_data_path, "PlayerTeamStatsSummary.csv"), sep=';')
    defender_pct_df = pd.read_csv(os.path.join(proc_data_path, "DefenderPercentile.csv"), sep=';')
    midfielder_pct_df = pd.read_csv(os.path.join(proc_data_path, "MidfielderPercentile.csv"), sep=';')
    forward_pct_df = pd.read_csv(os.path.join(proc_data_path, "ForwardPercentile.csv"), sep=';')
    goalkeeper_pct_df = pd.read_csv(os.path.join(proc_data_path, "GoalkeeperPercentile.csv"), sep=';')

    # Filtramos por temporada
    player_team_stats_summary_df = dataframe_filter(df_original=player_team_stats_summary_df, season=season)
    defender_pct_df = dataframe_filter(df_original=defender_pct_df, season=season)
    midfielder_pct_df = dataframe_filter(df_original=midfielder_pct_df, season=season)
    forward_pct_df = dataframe_filter(df_original=forward_pct_df, season=season)
    goalkeeper_pct_df = dataframe_filter(df_original=goalkeeper_pct_df, season=season)

    # Obtenemos el dataframe que nos va a ayudar a crear las visualizaciones
    df = season_league_comparison_metrics(player_stats_summary_df=player_team_stats_summary_df, goalkeeper_pct_df=goalkeeper_pct_df, defender_pct_df=defender_pct_df,
                                        midfielder_pct_df=midfielder_pct_df, forward_pct_df=forward_pct_df, season=season)

    # Selección de las columnas que quedemos guardar y guardado
    df_to_save = df[['League', 'AttackValue', 'DeffenseValue', 'ProgressionValue']].sort_values(by='League')
    df_to_save.to_csv(os.path.join(figures_path, f'LeagueMetrics{season.replace('/','')}.csv'), sep=';', index=False)

    # Lista para concatenar todos los graficos
    all_vis = []

    # Creación de los gráficos scatter simples
    all_vis.append(offensive_thread_scatter_creation(df=df, season=season, figures_path=figures_path))
    all_vis.append(physicality_map_creation(df=df, season=season, figures_path=figures_path))
    all_vis.append(tactical_style_creation(df=df, season=season, figures_path=figures_path))

    # Para cada posición, creamos los radar charts
    all_vis.append(radar_5metrics_creation(df=df, position='Goalkeeper', season=season, figures_path=figures_path, title="COMPARACIÓN DE LOS PERCENTILES MEDIOS POR JUGADOR EN DISTINTAS FACETAS DEL JUEGO (PORTEROS)"))
    all_vis.append(radar_5metrics_creation(df=df, position='Defender', season=season, figures_path=figures_path, title="COMPARACIÓN DE LOS PERCENTILES MEDIOS POR JUGADOR EN DISTINTAS FACETAS DEL JUEGO (DEFENSAS)"))
    all_vis.append(radar_5metrics_creation(df=df, position='Midfielder', season=season, figures_path=figures_path, title="COMPARACIÓN DE LOS PERCENTILES MEDIOS POR JUGADOR EN DISTINTAS FACETAS DEL JUEGO (CENTROCAMPISTAS)"))
    all_vis.append(radar_5metrics_creation(df=df, position='Forward', season=season, figures_path=figures_path, title="COMPARACIÓN DE LOS PERCENTILES MEDIOS POR JUGADOR EN DISTINTAS FACETAS DEL JUEGO (DELANTEROS)"))

    # Para cada métrica de cada una de las posiciones, obtenemos las gráficas de violines para ver la liga con los mejores jugadores en cada ambito - porteros
    all_vis.append(violin_plot_creation(df=goalkeeper_pct_df, metric='pct_ShotStopping', metric_title='GKShotStopping', season=season, subtitle=f"Shot stopping en porteros temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=goalkeeper_pct_df, metric='pct_Reliability', metric_title='GKReliability', season=season, subtitle=f"Reliability en porteros temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=goalkeeper_pct_df, metric='pct_AreaControl', metric_title='GKAreaControl', season=season, subtitle=f"Area control en porteros temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=goalkeeper_pct_df, metric='pct_SweeperKeeper', metric_title='GKSweeperKeeper', season=season, subtitle=f"Sweeper keeper en porteros temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=goalkeeper_pct_df, metric='pct_BuildUpPlay', metric_title='GKBuildUpPlay', season=season, subtitle=f"Build-up play en porteros temporada {season}", figures_path=figures_path))

    # Defensas
    all_vis.append(violin_plot_creation(df=defender_pct_df, metric='pct_DefensiveActions', metric_title='DFDefensiveActions', season=season, subtitle=f"Defensive actions en defensas temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=defender_pct_df, metric='pct_Duels', metric_title='DFDuels', season=season, subtitle=f"Duels en defensas temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=defender_pct_df, metric='pct_AerialAbility', metric_title='DFAerialAbility', season=season, subtitle=f"Aerial ability en defensas temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=defender_pct_df, metric='pct_BuildUpPlay', metric_title='DFBuildUpPlay', season=season, subtitle=f"Build-up play en defensas temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=defender_pct_df, metric='pct_DefensiveReliability', metric_title='DFDefensiveReliability', season=season, subtitle=f"Defensive reliability en defensas temporada {season}", figures_path=figures_path))

    # Centrocampistas
    all_vis.append(violin_plot_creation(df=midfielder_pct_df, metric='pct_BallDistribution', metric_title='MDBallDistribution', season=season, subtitle=f"Ball distribution en centrocampistas temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=midfielder_pct_df, metric='pct_Progression', metric_title='MDProgression', season=season, subtitle=f"Progression en centrocampistas temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=midfielder_pct_df, metric='pct_ChanceCreation', metric_title='MDChanceCreation', season=season, subtitle=f"Chance creation en centrocampistas temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=midfielder_pct_df, metric='pct_DefensiveBalance', metric_title='MDDefensiveBalance', season=season, subtitle=f"Defensive balance en centrocampistas temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=midfielder_pct_df, metric='pct_BallRetention', metric_title='MDBallRetention', season=season, subtitle=f"Ball retention en centrocampistas temporada {season}", figures_path=figures_path))

    # Delanteros
    all_vis.append(violin_plot_creation(df=forward_pct_df, metric='pct_Finishing', metric_title='FWFinishing', season=season, subtitle=f"Finishing en delanteros temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=forward_pct_df, metric='pct_ChanceCreation', metric_title='FWChanceCreation', season=season, subtitle=f"Chance creation en delanteros temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=forward_pct_df, metric='pct_Threat', metric_title='FWThreat', season=season, subtitle=f"Threat en delanteros temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=forward_pct_df, metric='pct_OffBallInvolvement', metric_title='FWOffBallInvolvement', season=season, subtitle=f"Off-ball involvement en delanteros temporada {season}", figures_path=figures_path))
    all_vis.append(violin_plot_creation(df=forward_pct_df, metric='pct_Efficiency', metric_title='FWEfficiency', season=season, subtitle=f"Efficiency en delanteros temporada {season}", figures_path=figures_path))

    return all_vis

# ===========================================================================================================================================
# FUNCIÓN 2 - CREACIÓN DE VISUALIZACIONES Y TABLAS SOBRE UNA LIGA EN UNA TEMPORADA, COMPARANDO EQUIPOS
# ===========================================================================================================================================
def create_league_visualizations(data_path: str, season: str, league: str) -> list:

    # Construcción de la tabla clasificatoria de la liga
    def build_league_table(league: str, season: str, match_info_df: pd.DataFrame, player_stats_df: pd.DataFrame, figures_path: str = None) -> pd.DataFrame:

        # A partir de las stats de los jugadores, obtenemos los xg de un partido
        player_xg_match = player_stats_df[['match_slug', 'team_slug', 'expectedGoals']].copy()
        team_xg_match = (player_xg_match.groupby(["match_slug", "team_slug"], as_index=False)["expectedGoals"].sum()).drop_duplicates()

        # Añadimos los xg against
        team_xg_match = team_xg_match.merge(team_xg_match, on="match_slug", suffixes=("", "_opp"))
        team_xg_match = team_xg_match[team_xg_match["team_slug"] != team_xg_match["team_slug_opp"]]         # Seleccionamos aquellos que tienen equipo diferente
        team_xg_match = team_xg_match.drop_duplicates(subset="match_slug", keep="first")        # Solo primer equipo
        team_xg_match = team_xg_match[['match_slug','expectedGoals','expectedGoals_opp']]
        team_xg_match.columns = ['slug', 'home_xg', 'away_xg']

        # Unimos el dataframe de información con los xg para obtener un df más amplio
        match_info_df = match_info_df.merge(team_xg_match, on='slug')
        df = match_info_df.copy()

        # Asegura numéricos
        df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce")
        df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce")
        df["home_xg"] = pd.to_numeric(df["home_xg"], errors="coerce")
        df["away_xg"] = pd.to_numeric(df["away_xg"], errors="coerce")

        # Si hay partidos sin marcador todavía, los quitamos de la clasificación
        df = df.dropna(subset=["home_score", "away_score"])

        # Filas (home)
        home = pd.DataFrame({"Equipo": df["home_team"], "Partidos": 1, "Goles favor": df["home_score"], "Goles contra": df["away_score"],
                            "xG favor": df["home_xg"], "xG contra": df["away_xg"],"Victorias": (df["home_score"] > df["away_score"]).astype(int), 
                            "Empates": (df["home_score"] == df["away_score"]).astype(int), "Derrotas": (df["home_score"] < df["away_score"]).astype(int),
                            "Puntos": np.select([df["home_score"] > df["away_score"], df["home_score"] == df["away_score"]], [3, 1], default=0)})

        # Filas (away)
        away = pd.DataFrame({"Equipo": df["away_team"], "Partidos": 1, "Goles favor": df["away_score"], "Goles contra": df["home_score"],
                            "xG favor": df["away_xg"], "xG contra": df["home_xg"],"Victorias": (df["away_score"] > df["home_score"]).astype(int), 
                            "Empates": (df["home_score"] == df["away_score"]).astype(int), "Derrotas": (df["away_score"] < df["home_score"]).astype(int),
                            "Puntos": np.select([df["away_score"] > df["home_score"], df["home_score"] == df["away_score"]], [3, 1], default=0)})

        # Juntamos por equipo, y sumamos
        table = pd.concat([home, away], ignore_index=True).groupby("Equipo", as_index=False).sum()

        # Diferencia de goles y de xG
        table["Diferencia goles"] = table["Goles favor"] - table["Goles contra"]
        table["Diferencia xG"] = table["xG favor"] - table["xG contra"]

        # Orden por puntos y diferencia de goles (aún más goles a favor)
        table = table.sort_values(["Puntos", "Diferencia goles", "Goles favor", "Equipo"], ascending=[False, False, False, True]).reset_index(drop=True)

        # Añadimos posición
        table.insert(0, "Pos", table.index + 1)

        # Reordenamos
        table = table[['Pos', 'Equipo', 'Partidos', 'Victorias', 'Empates', 'Derrotas', 'Puntos', 'Goles favor', 'Goles contra', 
                    'Diferencia goles', 'xG favor', 'xG contra',  'Diferencia xG']]
        
        # Guardamos
        if figures_path is not None:
            table_path = os.path.join(figures_path, f'StandingTable{league.replace(' ','')}{season.replace('/','')}.csv')
            table.to_csv(table_path, sep=';', index=False)

        return table

    # Creación del dataframe de índices de los equipos
    def build_indices_table(league: str, season: str, player_stats_df: pd.DataFrame, league_table: pd.DataFrame, teams_slug_dict: dict, figures_path: str = None) -> pd.DataFrame:

        df = player_stats_df.copy()

        # Selección de columnas
        df = df[['team_slug','minutesPlayed','expectedGoals','goals','attack_value_raw','bigChanceCreated','totalShots','def_actions','duelWon',
                'aerialWon','fouls','interceptionWon','progressiveBallCarriesCount','passValueNormalized']]

        # Columnas a las cuales vamos a aplicar x90
        cols_per90 = ['expectedGoals','goals','attack_value_raw','bigChanceCreated','totalShots', 
                    'def_actions','duelWon','aerialWon','fouls','interceptionWon','progressiveBallCarriesCount']

        # Filtramos jugadores com 0 minutos (poco usual)
        df = df[df['minutesPlayed'] > 0].copy()

        # Calcular factor per90
        df[[c for c in cols_per90]] = (df[cols_per90].div(df['minutesPlayed'], axis=0).mul(90))

        # Generamos métricas de ataque, defensa y progressión
        df['AttackValue'] = df['expectedGoals'] + df['bigChanceCreated'] + df['attack_value_raw']
        df['DeffenseValue'] = df['def_actions'] + df['duelWon'] + df['aerialWon'] + df['interceptionWon']
        df['ProgressionValue'] = df['progressiveBallCarriesCount'] + df['passValueNormalized']

        # Suma por equipo de valores
        df = df.groupby("team_slug", as_index=False).sum()

        # Creamos índices de ataque, defensa, y progresión
        df["AttackIndex"] = (df["AttackValue"].rank(method="min", ascending=False).astype(int))
        df["DefenseIndex"] = (df["DeffenseValue"].rank(method="min", ascending=False).astype(int))
        df["ProgressionIndex"] = (df["ProgressionValue"].rank(method="min", ascending=False).astype(int))

        # Modificamos la columna de indices para mostrar los valores
        df["AttackIndex"] = (df["AttackIndex"].astype(str) + " (" + df["AttackValue"].round(2).astype(str)+ ")")
        df["DefenseIndex"] = (df["DefenseIndex"].astype(str) + " (" + df["DeffenseValue"].round(2).astype(str)+ ")")
        df["ProgressionIndex"] = (df["ProgressionIndex"].astype(str) + " (" + df["ProgressionValue"].round(2).astype(str)+ ")")

        # Añadimos el nombre del equipo y añadimos posición
        df['Equipo'] = df['team_slug'].map(teams_slug_dict)
        df = df.merge(league_table, on='Equipo')
        df = df.sort_values(by='Pos')

        # Seleccionamos columnas
        df = df[['Pos', 'Equipo', 'AttackIndex', 'DefenseIndex', 'ProgressionIndex']]
        df.columns = ['Posición', 'Equipo', 'Índice ofensivo', 'Índice defensivo', 'Índice progressión']

        # Guardamos
        if figures_path is not None:
            table_path = os.path.join(figures_path, f'IndicesTable{league.replace(' ','')}{season.replace('/','')}.csv')
            df.to_csv(table_path, sep=';', index=False)

        return df

    # Obtención del dataframe de los mejores 20 porteros
    def best_gk_dataframe(league: str, season: str, goalkeeper_pct_df: pd.DataFrame, figures_path: str = None) -> pd.DataFrame:

        df = goalkeeper_pct_df.copy()

        # Pesos según metrica - aplicamos
        weights = {"pct_ShotStopping": 0.25, "pct_Reliability": 0.25, "pct_AreaControl": 0.25, "pct_SweeperKeeper": 0.15, "pct_BuildUpPlay": 0.10}
        df["GK_Index"] = sum(df[col] * w for col, w in weights.items())

        # Top 20 porteros 
        df = df.sort_values(by='GK_Index', ascending=False)
        df = df.head(20)
        df["Rank"] = (df["GK_Index"].rank(ascending=False, method="dense").astype(int))

        # Seleccionamos columnas y renombramos
        df = df[['Rank', 'player_name', 'GK_Index', 'pct_ShotStopping', 'pct_Reliability', 'pct_AreaControl', 'pct_SweeperKeeper', 'pct_BuildUpPlay']]
        df.columns = ['Rango', 'Jugador', 'Índice portero', 'Paradas', 'Fiabilidad', 'Control área', 'Salidas', 'Creación']    

        # Guardamos
        if figures_path is not None:
            table_path = os.path.join(figures_path, f'GoalkeeperRanking{league.replace(' ','')}{season.replace('/','')}.csv')
            df.to_csv(table_path, sep=';', index=False)

        return df

    # Obtención del dataframe de los mejores 20 defensas
    def best_df_dataframe(league: str, season: str, defender_pct_df: pd.DataFrame, figures_path: str = None) -> pd.DataFrame:

        df = defender_pct_df.copy()

        # Pesos según metrica - aplicamos
        weights = {"pct_DefensiveActions": 0.20, "pct_Duels": 0.15, "pct_AerialAbility": 0.05, "pct_BuildUpPlay": 0.10, "pct_DefensiveReliability": 0.50}
        df["DF_Index"] = sum(df[col] * w for col, w in weights.items())

        # Top 20 porteros 
        df = df.sort_values(by='DF_Index', ascending=False)
        df = df.head(20)
        df["Rank"] = (df["DF_Index"].rank(ascending=False, method="dense").astype(int))

        # Seleccionamos columnas y renombramos
        df = df[['Rank', 'player_name', 'DF_Index', 'pct_DefensiveActions', 'pct_Duels', 'pct_AerialAbility', 'pct_BuildUpPlay', 'pct_DefensiveReliability']]
        df.columns = ['Rango', 'Jugador', 'Índice defensa', 'Volumen defensivo', 'Duelos', 'Juego aéreo', 'Salida balón', 'Fiabilidad']    

        # Guardamos
        if figures_path is not None:
            table_path = os.path.join(figures_path, f'DefenderRanking{league.replace(' ','')}{season.replace('/','')}.csv')
            df.to_csv(table_path, sep=';', index=False)

        return df

    # Obtención del dataframe de los mejores 20 centrocampistas
    def best_md_dataframe(league: str, season: str, midfielder_pct_df: pd.DataFrame, figures_path: str = None) -> pd.DataFrame:

        df = midfielder_pct_df.copy()

        # Pesos según metrica - aplicamos
        weights = {"pct_BallDistribution": 0.40, "pct_Progression": 0.20, "pct_ChanceCreation": 0.20, "pct_DefensiveBalance": 0.10, "pct_BallRetention": 0.10}
        df["MD_Index"] = sum(df[col] * w for col, w in weights.items())

        # Top 20 porteros 
        df = df.sort_values(by='MD_Index', ascending=False)
        df = df.head(20)
        df["Rank"] = (df["MD_Index"].rank(ascending=False, method="dense").astype(int))

        # Seleccionamos columnas y renombramos
        df = df[['Rank', 'player_name', 'MD_Index', 'pct_BallDistribution', 'pct_Progression', 'pct_ChanceCreation', 'pct_DefensiveBalance', 'pct_BallRetention']]
        df.columns = ['Rango', 'Jugador', 'Índice centrocampista', 'Distribución balón', 'Progressión', 'Creación ocasiones', 'Balance defensivo', 'Retención balón']    

        # Guardamos
        if figures_path is not None:
            table_path = os.path.join(figures_path, f'MidfielderRanking{league.replace(' ','')}{season.replace('/','')}.csv')
            df.to_csv(table_path, sep=';', index=False)

        return df

    # Obtención del dataframe de los mejores 20 delanteros
    def best_fw_dataframe(league: str, season: str, forward_pct_df: pd.DataFrame, figures_path: str = None) -> pd.DataFrame:

        df = forward_pct_df.copy()

        # Pesos según metrica - aplicamos
        weights = {"pct_Finishing": 0.40, "pct_ChanceCreation": 0.15, "pct_Threat": 0.25, "pct_OffBallInvolvement": 0.05, "pct_Efficiency": 0.15}
        df["FW_Index"] = sum(df[col] * w for col, w in weights.items())

        # Top 20 porteros 
        df = df.sort_values(by='FW_Index', ascending=False)
        df = df.head(20)
        df["Rank"] = (df["FW_Index"].rank(ascending=False, method="dense").astype(int))

        # Seleccionamos columnas y renombramos
        df = df[['Rank', 'player_name', 'FW_Index', 'pct_Finishing', 'pct_ChanceCreation', 'pct_Threat', 'pct_OffBallInvolvement', 'pct_Efficiency']]
        df.columns = ['Rango', 'Jugador', 'Índice delantero', 'Finalización', 'Creación ocasiones', 'Amenaza', 'Sin balón', 'Eficiencia']    

        # Guardamos
        if figures_path is not None:
            table_path = os.path.join(figures_path, f'ForwardRanking{league.replace(' ','')}{season.replace('/','')}.csv')
            df.to_csv(table_path, sep=';', index=False)

        return df

    # Creación de tres scatterplots mostrando las métricas normalizadas de ataque, defensa y progresión
    def create_metrics_scatters(league: str, season: str, indices_table: pd.DataFrame, figures_path: str = None):

        # Función pra crear un scatter con nuestras condiciones
        def create_general_metrics_scatter(df: pd.DataFrame, xaxis: str, yaxis: str, title: str, subtitle: str, xaxis_title: str, yaxis_title: str):
            
            # Scatterplot para comprarar la ofensividad y defensividad de los equipos
            scatter = px.scatter(df, x=xaxis, y=yaxis, color="Posición",
                                text="Equipo", color_continuous_scale="Blues_r",  size_max=15)

            # Mostramos un texto con el equipo
            scatter.update_traces(textposition="top center", marker=dict(size=15, line=dict(width=1)))

            # Layout de título y ejes
            scatter.update_layout(
                title=dict(text=f"{title}<br><sup> {subtitle}</sup>", x=0.5),
                xaxis_title=xaxis_title, yaxis_title=yaxis_title,
                coloraxis_colorbar=dict(title="Posición"))
            
            return scatter
        
        df = indices_table.copy()

        # Obtenemos los valores
        df["AttackValue"] = df["Índice ofensivo"].str.extract(r"\((.*?)\)").astype(float)
        df["DefensiveValue"] = df["Índice defensivo"].str.extract(r"\((.*?)\)").astype(float)
        df["ProgressionValue"] = df["Índice progressión"].str.extract(r"\((.*?)\)").astype(float)

        # Normalizamos de 0 a 1
        cols = ["AttackValue", "DefensiveValue", "ProgressionValue"]
        df[[c + "_norm" for c in cols]] = (df[cols] - df[cols].min()) / (df[cols].max() - df[cols].min())

        # Obtenemos los tres dataframes
        attack_vs_defense = create_general_metrics_scatter(df, xaxis='AttackValue_norm', yaxis='DefensiveValue_norm', title='COMPARACIÓN COMPORTAMIENTOS OFENSIVOS Y DEFENSIVOS',
                                                        subtitle=f'Equipos {league} temporada {season}', xaxis_title='Valor ofensivo', yaxis_title='Valor defensivo')
        attack_vs_progression = create_general_metrics_scatter(df, xaxis='AttackValue_norm', yaxis='ProgressionValue_norm', title='COMPARACIÓN COMPORTAMIENTOS OFENSIVOS Y DE PROGRESIÓN',
                                                            subtitle=f'Equipos {league} temporada {season}', xaxis_title='Valor ofensivo', yaxis_title='Progresión')
        defense_vs_progression = create_general_metrics_scatter(df, xaxis='DefensiveValue_norm', yaxis='ProgressionValue_norm', title='COMPARACIÓN COMPORTAMIENTOS DEFENSIVOS Y DE PROGRESIÓN',
                                                            subtitle=f'Equipos {league} temporada {season}', xaxis_title='Valor defensivo', yaxis_title='Progresión')
        
        # Si podemos guardar los gráficos:
        if figures_path is not None:
            figure_1_path = os.path.join(figures_path, f'AttackDefenseTeams{league.replace(' ','')}{season.replace('/','')}.png')
            attack_vs_defense.write_image(figure_1_path, width=1400, height=800, scale=2)
            figure_2_path = os.path.join(figures_path, f'AttackProgressionTeams{league.replace(' ','')}{season.replace('/','')}.png')
            attack_vs_progression.write_image(figure_2_path, width=1400, height=800, scale=2)
            figure_3_path = os.path.join(figures_path, f'DefenseProgressionTeams{league.replace(' ','')}{season.replace('/','')}.png')
            defense_vs_progression.write_image(figure_3_path, width=1400, height=800, scale=2)

        return attack_vs_defense, attack_vs_progression, defense_vs_progression

    # Creación de los dumbbell charts de los goles a favor y goles en contra
    def create_goals_dumbbell_charts(league: str, season: str, league_table: pd.DataFrame, figures_path: str = None):

        # Función para la creación de un dumbbell chart
        def create_dumbbell_chart(league_table: pd.DataFrame, var1: str, var2: str, var1_title: str, var2_title: str, col1: str, col2:str, title: str, subtitle: str, axis_title: str):

            # Ordenar para que el gráfico sea más legible
            df = league_table.copy()
            df = df.sort_values('Pos', ascending=False).reset_index(drop=True)

            fig = go.Figure()

            # Líneas
            for _, row in df.iterrows():
                fig.add_trace(go.Scatter(x=[row[var1], row[var2]],
                                        y=[row['Equipo'], row['Equipo']],
                                        mode="lines", line=dict(width=1, color="grey"),
                                        showlegend=False, hoverinfo="skip"))
                
            # Etiquetas dinamicas
            text_goles = []
            text_xg = []
            pos_goles = []
            pos_xg = []

            for _, row in df.iterrows():

                goles = row[var1]
                xg = row[var2]

                # Definir cuál es mayor y menor
                if goles >= xg:
                    text_goles.append(f"{goles}")
                    text_xg.append(f"{xg:.2f}")
                    pos_goles.append("middle right")   # mayor → derecha
                    pos_xg.append("middle left")       # menor → izquierda
                else:
                    text_goles.append(f"{goles}")
                    text_xg.append(f"{xg:.2f}")
                    pos_goles.append("middle left")
                    pos_xg.append("middle right")

            # Puntos
            fig.add_trace(go.Scatter(x=df[var1], y=df['Equipo'], mode="markers+text", name=var1_title, marker=dict(size=10, color=col1), 
                                    text=text_goles, textposition=pos_goles))
            fig.add_trace(go.Scatter(x=df[var2], y=df['Equipo'], mode="markers+text", name=var2_title, marker=dict(size=10, color=col2), 
                                    text=text_xg, textposition=pos_xg))

            # Layout títulos
            fig.update_layout(title=dict(text=f"<b>{title}</b><br> <sup>{subtitle}</sup>", x=0.5, xanchor="center"), 
                            template="plotly_white", height=700, xaxis_title=axis_title, yaxis_title="")
            
            return fig

        # Dumbbell chart goles a favor
        goals_xg_comp = create_dumbbell_chart(league_table=league_table, var1='Goles favor', var2='xG favor', col1='#1C0770', col2='#3A9AFF',
                                            var1_title='Goles', var2_title='Goles esperados', axis_title='Goles vs. goles esperados',
                                            title='COMPARATIVA DE GOLES Y GOLES ESPERADOS (A FAVOR) POR EQUIPO', subtitle=f'{league} temporada {season}')

        # Dumbbell chart goles en contra
        goalsa_xga_comp = create_dumbbell_chart(league_table=league_table, var1='Goles contra', var2='xG contra', col1="#CF2121", col2="#DC7A7A",
                                                var1_title='Goles en contra', var2_title='Goles en contra esperados', axis_title='Goles en contra vs. goles en contra esperados',
                                                title='COMPARATIVA DE GOLES Y GOLES ESPERADOS (EN CONTRA) POR EQUIPO', subtitle=f'{league} temporada {season}')

        # Si podemos guardar los gráficos:
        if figures_path is not None:
            figure_1_path = os.path.join(figures_path, f'GoalsVsExpectedGoals{league.replace(' ','')}{season.replace('/','')}.png')
            goals_xg_comp.write_image(figure_1_path, width=1400, height=800, scale=2)
            figure_2_path = os.path.join(figures_path, f'AgainstGoalsVsExpectedGoals{league.replace(' ','')}{season.replace('/','')}.png')
            goalsa_xga_comp.write_image(figure_2_path, width=1400, height=800, scale=2)

        return goals_xg_comp, goalsa_xga_comp

    # Paths de procesado y figuras
    proc_data_path = os.path.join(data_path, 'clean')
    all_figures_path = os.path.join(data_path, 'images')

    # Creamos el path de imagenes de la temporada
    figures_path = os.path.join(all_figures_path, season.replace('/', ''), 'leagues')
    os.makedirs(figures_path, exist_ok=True)

    # Lectura de todos los datos que necesitaremos
    match_info_df = pd.read_csv(os.path.join(proc_data_path, "MatchInfo.csv"), sep=';')
    player_stats_df = pd.read_csv(os.path.join(proc_data_path, "PlayerStats.csv"), sep=';')
    defender_pct_df = pd.read_csv(os.path.join(proc_data_path, "DefenderPercentile.csv"), sep=';')
    midfielder_pct_df = pd.read_csv(os.path.join(proc_data_path, "MidfielderPercentile.csv"), sep=';')
    forward_pct_df = pd.read_csv(os.path.join(proc_data_path, "ForwardPercentile.csv"), sep=';')
    goalkeeper_pct_df = pd.read_csv(os.path.join(proc_data_path, "GoalkeeperPercentile.csv"), sep=';')

    # Creamos diccionario con slug de todos los equipos para insertar el nombre en un futuro
    all_teams = sorted(set(match_info_df['home_team']).union(match_info_df['away_team']))
    teams_slug_dict = {}
    for team in all_teams:
        slug = (team.lower().replace(" ", "-"))
        teams_slug_dict[slug] = team

    # Filtramos dataframes por liga y por temporada
    match_info_df = dataframe_filter(df_original=match_info_df, season=season, league=league)
    player_stats_df = dataframe_filter(df_original=player_stats_df, season=season, league=league)
    defender_pct_df = dataframe_filter(df_original=defender_pct_df, season=season, league=league)
    midfielder_pct_df = dataframe_filter(df_original=midfielder_pct_df, season=season, league=league)
    forward_pct_df = dataframe_filter(df_original=forward_pct_df, season=season, league=league)
    goalkeeper_pct_df = dataframe_filter(df_original=goalkeeper_pct_df, season=season, league=league)

    # A retornar - dataframes y vis
    dataframes_and_vis = []

    # Creación de la clasificación de la liga
    league_table = build_league_table(league=league, season=season, match_info_df=match_info_df, player_stats_df=player_stats_df, figures_path=figures_path)
    indices_table = build_indices_table(league=league, season=season, player_stats_df=player_stats_df, teams_slug_dict=teams_slug_dict, league_table=league_table, figures_path=figures_path)
    dataframes_and_vis.append([league_table, indices_table])

    # Creación de los rankings de posiciones
    dataframes_and_vis.append(best_gk_dataframe(league=league, season=season, goalkeeper_pct_df=goalkeeper_pct_df, figures_path=figures_path))
    dataframes_and_vis.append(best_df_dataframe(league=league, season=season, defender_pct_df=defender_pct_df, figures_path=figures_path))
    dataframes_and_vis.append(best_md_dataframe(league=league, season=season, midfielder_pct_df=midfielder_pct_df, figures_path=figures_path))
    dataframes_and_vis.append(best_fw_dataframe(league=league, season=season, forward_pct_df=forward_pct_df, figures_path=figures_path))

    # Creación de los scatters de metricas y dumbbell charts de goles y xg
    attack_vs_defense, attack_vs_progression, defense_vs_progression = create_metrics_scatters(league=league, season=season, indices_table=indices_table, figures_path=figures_path)
    dataframes_and_vis.append([attack_vs_defense, attack_vs_progression, defense_vs_progression])
    goals_xg_comp, goalsa_xga_comp = create_goals_dumbbell_charts(league=league, season=season, league_table=league_table, figures_path=figures_path)
    dataframes_and_vis.append([goals_xg_comp, goalsa_xga_comp])

    return dataframes_and_vis

# ===========================================================================================================================================
# FUNCIÓN 3 - CREACIÓN DE VISUALIZACIONES Y TABLAS DE UN SIMPLE JUGADOR
# ===========================================================================================================================================
def create_player_visualizations(data_path: str, season: str, player_slug: str) -> list:

    # A partir de las stats del jugador y su posición, obtenemos métricas diferenciadas por posición para mostrar
    def obtain_player_metrics(stats_filtered_df: pd.DataFrame, position: str) -> dict:
        
        # Metrics por posición
        if position == 'G':
            metrics = ['saves_per90','goalsPrevented','goals_minus_xg','penaltySave','goodHighClaim','crossNotClaimed', 
                    'totalKeeperSweeper','accurateKeeperSweeper','accuratePass_per90','pass_accuracy']
        elif position == 'D':
            metrics = ['def_actions_per90','interceptionWon_per90','duelWon_per90','contest_win_rate','aerialWon',
                    'ballRecovery_per90','pass_accuracy','totalProgression','accurateOppositionHalfPasses','outfielderBlock']
        elif position == 'M':
            metrics = ['passValueNormalized','totalPass_per90','keyPass_per90','expectedAssists_per90','totalProgression',
                    'progressiveBallCarriesCount','def_actions_per90','ballRecovery_per90','dispossessed_per_touch','touches_per90']
        elif position == 'F':
            metrics = ['goals_per90','expectedGoals_per90','goals_over_xg','totalShots','bigChanceCreated_per90','shotValueNormalized',
                    'onTargetScoringAttempt','attack_value_raw_per90','touches_per90','dispossessed_per90','p90_factor']     # En caso que sea delantero añadimos minutos porque necesitamos calcular tiros por 90
        else:
            metrics = []

        # Buscamos metricas en nuestro dataframe
        metrics_df = stats_filtered_df[metrics].copy()

        # En caso que sea delantero
        if position == 'F':
            metrics_df['totalShots'] = metrics_df['totalShots'] * metrics_df['p90_factor']
            metrics_df.drop(columns=['p90_factor'])

        # Guardamos toda la información sumada en formato diccionario (con nombres editados)
        if position == 'G':
            metrics_dict = {
                'Paradas por 90': float(round(metrics_df['saves_per90'].sum(), 2)),
                'Goles evitados': float(round(metrics_df['goalsPrevented'].sum(), 2)),
                'Goles menos xG': float(round(metrics_df['goals_minus_xg'].sum(), 2)),
                'Penaltis parados': int(round(metrics_df['penaltySave'].sum(), 0)),
                'Reclamaciones altas': int(round(metrics_df['goodHighClaim'].sum(), 0)),
                'Centros no reclamados': int(round(metrics_df['crossNotClaimed'].sum(), 0)),
                'Barridos totales': int(round(metrics_df['totalKeeperSweeper'].sum(), 0)),
                'Barridos precisos': int(round(metrics_df['accurateKeeperSweeper'].sum(), 0)),
                'Pases precisos por 90': float(round(metrics_df['accuratePass_per90'].sum(), 2)),
                'Precisión de pase (%)': float(round(metrics_df['pass_accuracy'].mean() * 100, 2))}
        elif position == 'D':
            metrics_dict = {
                'Acciones defensivas por 90': float(round(metrics_df['def_actions_per90'].sum(), 2)),
                'Intercepciones por 90': float(round(metrics_df['interceptionWon_per90'].sum(), 2)),
                'Duelos ganados por 90': float(round(metrics_df['duelWon_per90'].sum(), 2)),
                'Win rate duelos (%)': float(round(metrics_df['contest_win_rate'].mean() * 100, 2)),
                'Aéreos ganados': int(round(metrics_df['aerialWon'].sum(), 0)),
                'Recuperaciones por 90': float(round(metrics_df['ballRecovery_per90'].sum(), 2)),
                'Precisión de pase (%)': float(round(metrics_df['pass_accuracy'].mean() * 100, 2)),
                'Progresiones totales': int(round(metrics_df['totalProgression'].sum(), 0)),
                'Pases campo rival': int(round(metrics_df['accurateOppositionHalfPasses'].sum(), 0)),
                'Bloqueos': int(round(metrics_df['outfielderBlock'].sum(), 0))}
        elif position == 'M':
            metrics_dict = {
                'Valor de pase': float(round(metrics_df['passValueNormalized'].mean(), 2)),
                'Pases por 90': float(round(metrics_df['totalPass_per90'].sum(), 2)),
                'Key passes por 90': float(round(metrics_df['keyPass_per90'].sum(), 2)),
                'xA por 90': float(round(metrics_df['expectedAssists_per90'].sum(), 2)),
                'Progresiones totales': int(round(metrics_df['totalProgression'].sum(), 0)),
                'Conducciones progresivas': int(round(metrics_df['progressiveBallCarriesCount'].sum(), 0)),
                'Acciones defensivas por 90': float(round(metrics_df['def_actions_per90'].sum(), 2)),
                'Recuperaciones por 90': float(round(metrics_df['ballRecovery_per90'].sum(), 2)),
                'Pérdidas por toque': float(round(metrics_df['dispossessed_per_touch'].mean(), 2)),
                'Toques por 90': float(round(metrics_df['touches_per90'].sum(), 2))}
        elif position == 'F':
            metrics_dict = {
                'Goles por 90': float(round(metrics_df['goals_per90'].sum(), 2)),
                'xG por 90': float(round(metrics_df['expectedGoals_per90'].sum(), 2)),
                'Goles sobre xG': float(round(metrics_df['goals_over_xg'].sum(), 2)),
                'Tiros por 90': float(round(metrics_df['totalShots'].sum(), 2)),
                'Big chances creadas por 90': float(round(metrics_df['bigChanceCreated_per90'].sum(), 2)),
                'Valor de tiro': float(round(metrics_df['shotValueNormalized'].mean(), 2)),
                'Tiros a puerta': int(round(metrics_df['onTargetScoringAttempt'].sum(), 0)),
                'Valor ofensivo por 90': float(round(metrics_df['attack_value_raw_per90'].sum(), 2)),
                'Toques por 90': float(round(metrics_df['touches_per90'].sum(), 2)),
                'Pérdidas por 90': float(round(metrics_df['dispossessed_per90'].sum(), 2))}
        
        return metrics_dict

    # Creación de un scatterplot según métricas para resaltar nuestro jugador seleccionado
    def comparison_players_metrics(player_info_df: pd.DataFrame, player_stats_df: pd.DataFrame, season: str, position: str, player_slug: str, player_name: str, 
                                xaxis: str, yaxis: str, xaxis_title: str, yaxis_title: str, name_figure: str = None, figures_path: str = None):
        
        # Filtrado de las estadísticas por temporada
        stats = dataframe_filter(df_original=player_stats_df, season=season).copy()

        # Seleccionamos jugadores de la posición y filtramos el dataframe
        players_position = (player_info_df.loc[player_info_df['position'] == position, 'player_slug'].dropna().unique().tolist())
        stats = stats[stats['player_slug'].isin(players_position)].copy()

        # Selección de columnas y valor medio por jugador
        stats = (stats[['player_slug', xaxis, yaxis]].groupby('player_slug', as_index=False).mean().copy())

        # Sacamos outliers y valores en 0
        stats = remove_outliers_iqr(df=stats, cols=[xaxis, yaxis]).copy()
        stats = stats[(stats[xaxis] > 0) & (stats[yaxis] > 0)].copy()

        # Split: otros vs seleccionado
        other_players = stats.loc[stats['player_slug'] != player_slug].copy()
        sel_player = stats.loc[stats['player_slug'] == player_slug].copy()

        # Si el jugador no está (por outliers / filtro >0), lo reinsertamos sin romper el plot
        if sel_player.empty:
            # Intentar recuperar su media antes de filtrar outliers/>0
            sel_raw = (dataframe_filter(df_original=player_stats_df, season=season)
                    .loc[lambda d: d['player_slug'] == player_slug, ['player_slug', xaxis, yaxis]]
                    .groupby('player_slug', as_index=False).mean())
            sel_player = sel_raw.copy()

        # Asignación segura (sin SettingWithCopyWarning)
        sel_player.loc[:, 'player_name'] = player_name

        # Base
        fig = px.scatter(other_players, x=xaxis, y=yaxis, color_discrete_sequence=['#AEB6BF'], labels={xaxis: xaxis_title, yaxis: yaxis_title})

        # Añadimos jugador seleccionado con leyenda
        if not sel_player.empty:
            fig.add_scatter(x=sel_player[xaxis], y=sel_player[yaxis], mode='markers+text', text=sel_player['player_name'], 
                            textposition='top center', marker=dict(size=14, color='#E63946'), showlegend=False)
            
        # Definimos el título según posición
        if position == 'G':
            title='COMPARACIÓN ENTRE EL JUGADOR SELECCIONADO Y LOS OTROS PORTEROS'
        elif position == 'D':
            title='COMPARACIÓN ENTRE EL JUGADOR SELECCIONADO Y LOS OTROS DEFENSAS'
        elif position == 'M':
            title='COMPARACIÓN ENTRE EL JUGADOR SELECCIONADO Y LOS OTROS CENTROCAMPISTAS'
        elif position == 'F':
            title='COMPARACIÓN ENTRE EL JUGADOR SELECCIONADO Y LOS OTROS DELANTEROS'

        # Títulos
        fig.update_traces(marker=dict(size=8), selector=dict(mode='markers'))
        fig.update_layout(template='plotly_white', xaxis_title=xaxis_title, yaxis_title=yaxis_title, showlegend=False, 
                        title=dict(text=f"{title}<br><sup>{xaxis_title} vs {yaxis_title} (Temporada {season})</sup>", x=0.5, xanchor='center'))

        # Guardamos
        if figures_path is not None:
            figure_path = os.path.join(figures_path, f'{name_figure}{player_name.replace(' ','')}{season.replace('/','')}.png')
            fig.write_image(figure_path, width=1400, height=800, scale=2)

        return fig

    # Radar de comparación de estadísticas por temporada
    def radar_player_seasons(df: pd.DataFrame, position: str, player_name: str, subtitle: str, figures_path: str = None):

            # Labels según posición
            if position == 'G':
                labels = {'pct_ShotStopping': 'Shot Stopping', 'pct_Reliability': 'Reliability', 'pct_AreaControl': 'Area Control', 'pct_SweeperKeeper': 'Sweeper Keeper', 'pct_BuildUpPlay': 'Build-up Play'}
            elif position == 'D':
                labels = {'pct_DefensiveActions': 'Defensive Actions', 'pct_Duels': 'Duels', 'pct_AerialAbility': 'Aerial Ability', 'pct_BuildUpPlay': 'Build-up Play', 'pct_DefensiveReliability': 'Defensive Reliability'}
            elif position == 'M':
                labels = {'pct_BallDistribution': 'Ball Distribution', 'pct_Progression': 'Progression', 'pct_ChanceCreation': 'Chance Creation', 'pct_DefensiveBalance': 'Defensive Balance', 'pct_BallRetention': 'Ball Retention'}
            elif position == 'F':
                labels = {'pct_Finishing': 'Finishing', 'pct_ChanceCreation': 'Chance Creation', 'pct_Threat': 'Threat', 'pct_OffBallInvolvement': 'Ball Involvement', 'pct_Efficiency': 'Efficiency'}

            # Metricas
            metrics = list(labels.keys())

            # Categorias a mostrar
            categories = [labels.get(m, m) for m in metrics]
            categories = categories + [categories[0]]

            # Creación de la figura
            radar = go.Figure()

            # Una línea para cada liga
            for _, row in df.iterrows():
                values = [row[m] for m in metrics] + [row[metrics[0]]]
                trace_kwargs = dict(r=values, theta=categories, name=str(row['season']), mode="lines+markers", line=dict(width=2), marker=dict(size=6))

                # Pintamos de color
                trace_kwargs["line"]["color"] = row['Color']
                trace_kwargs["marker"]["color"] = row['Color']

                radar.add_trace(go.Scatterpolar(**trace_kwargs))

            # Títulos del gráfico
            radar.update_layout(
                title=dict(text=f"COMPARACIÓN DE MÉTRICAS SEGÚN TEMPORADA<br><sup>{subtitle}</sup>", x=0.5, xanchor="center"),
                polar=dict(radialaxis=dict(visible=True,range=[0, 1])),
                showlegend=True,
                legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
                margin=dict(b=100))
            
            # Guardamos si el path no es nulo
            if figures_path is not None:
                name_figure = f'PlayerRadarChart{player_name.replace(' ','')}.png'       # Nombre de la figura   
                final_figure_path = os.path.join(figures_path, name_figure)                         # Nombre final del path a guardar la figura
                radar.write_image(final_figure_path, width=1400, height=800, scale=2)    # Guardado de la figura
            
            return radar

    # Paths
    proc_data_path = os.path.join(data_path, 'clean')
    all_figures_path = os.path.join(data_path, 'images')

    # Creamos el path de imagenes de la temporada
    figures_path = os.path.join(all_figures_path, season.replace('/', ''), 'players')
    os.makedirs(figures_path, exist_ok=True)

    # Lectura de todos los datos que necesitaremos
    player_info_df = pd.read_csv(os.path.join(proc_data_path, "PlayerInfo.csv"), sep=';')
    player_stats_df = pd.read_csv(os.path.join(proc_data_path, "PlayerStats.csv"), sep=';')
    defender_pct_df = pd.read_csv(os.path.join(proc_data_path, "DefenderPercentile.csv"), sep=';')
    midfielder_pct_df = pd.read_csv(os.path.join(proc_data_path, "MidfielderPercentile.csv"), sep=';')
    forward_pct_df = pd.read_csv(os.path.join(proc_data_path, "ForwardPercentile.csv"), sep=';')
    goalkeeper_pct_df = pd.read_csv(os.path.join(proc_data_path, "GoalkeeperPercentile.csv"), sep=';')

    # Filtramos por jugador en temporada
    info_filtered_df = dataframe_filter(df_original=player_info_df, season=season, player=player_slug)
    stats_filtered_df = dataframe_filter(df_original=player_stats_df, season=season, player=player_slug)

    # Posición formateada
    position_map = {'G': 'Portero', 'D': 'Defensa', 'M': 'Mediocentro', 'F': 'Delantero'}
    pos_letter = info_filtered_df['position'].iloc[0]
    pos_label = position_map.get(pos_letter, pos_letter)

    # Equipo formateado (quitar "-" y Capitalizar palabras)
    team_raw = info_filtered_df['team_slug'].iloc[0]
    team_label = team_raw.replace('-', ' ').title()

    # Lista a return
    return_list = []

    # Creación de un diccionario con información sobre el jugador
    player_info_dict = {
        'Jugador': info_filtered_df['name'].iloc[0],
        'Liga': f"{info_filtered_df['league'].iloc[0]} ({info_filtered_df['season'].iloc[0]})",
        'Equipo': team_label,
        'Posición': pos_label,
        'Número': int(info_filtered_df['jersey_number'].iloc[0]),
        'Altura': f"{int(info_filtered_df['height'].iloc[0])} cm",
        'País': info_filtered_df['country'].iloc[0],
        'Valor de mercado': f"{round(int(info_filtered_df['market_value'].iloc[0]) / 1_000_000, 2)} (millones) €",
        'Edad': f"{int(info_filtered_df['age'].iloc[0])} ({info_filtered_df['date_birth'].iloc[0]})"}

    # Obtención del diccionario con métricas
    player_metrics_dict = obtain_player_metrics(stats_filtered_df=stats_filtered_df, position=pos_letter)

    # Adjuntamos en un simple diccionario las metricas y la información del jugador
    player_dict = {'INFO': player_info_dict, 'METRICS': player_metrics_dict}
    json_path = os.path.join(figures_path, f'InfoMetrics{player_info_dict['Jugador'].replace(' ','')}{season.replace('/','')}.json')
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(player_dict, f, ensure_ascii=False, indent=4)
    return_list.append(player_dict)

    # Creamos las gráficas de comparación según posición - y gráfica de radar para el jugador
    if pos_letter == 'G':
        fig1 = comparison_players_metrics(player_info_df=player_info_df, player_stats_df=player_stats_df, season=season, position=pos_letter,
                                        player_slug=player_slug, player_name=player_info_dict['Jugador'], xaxis='saves_per90', yaxis='goalsPrevented',
                                        xaxis_title='Paradas por 90', yaxis_title='Goles evitados', figures_path=figures_path, name_figure='Fig1')
        fig2 = comparison_players_metrics(player_info_df=player_info_df, player_stats_df=player_stats_df, season=season, position=pos_letter,
                                        player_slug=player_slug, player_name=player_info_dict['Jugador'], xaxis='accurateKeeperSweeper', yaxis='pass_accuracy',
                                        xaxis_title='Barridos precisos', yaxis_title='Precisión de pase', figures_path=figures_path, name_figure='Fig2')
        
        # Dataframe con posiciones
        df_pct_position = pd.read_csv(os.path.join(proc_data_path, "GoalkeeperPercentile.csv"), sep=';')
        player_pct_df = dataframe_filter(df_original=df_pct_position, player=player_slug)

        # Aplicamos colores
        color_map = {'22/23': '#2A9D8F', '23/24': '#264653', '24/25': '#E9C46A', '25/26': '#E63946'}
        player_pct_df['Color'] = player_pct_df['season'].map(color_map)

        radar_player = radar_player_seasons(df=player_pct_df, position=pos_letter, player_name=player_info_dict['Jugador'], 
                                            subtitle=f'Jugador: {player_info_dict['Jugador']}', figures_path=figures_path)

    elif pos_letter == 'D':
        fig1 = comparison_players_metrics(player_info_df=player_info_df, player_stats_df=player_stats_df, season=season, position=pos_letter,
                                        player_slug=player_slug, player_name=player_info_dict['Jugador'], xaxis='def_actions_per90', yaxis='pass_accuracy',
                                        xaxis_title='Acciones defensivas por 90', yaxis_title='Precisión de pase', figures_path=figures_path, name_figure='Fig1')
        fig2 = comparison_players_metrics(player_info_df=player_info_df, player_stats_df=player_stats_df, season=season, position=pos_letter,
                                        player_slug=player_slug, player_name=player_info_dict['Jugador'], xaxis='duelWon_per90', yaxis='ballRecovery_per90',
                                        xaxis_title='Duelos ganados', yaxis_title='Recuperación de balón', figures_path=figures_path, name_figure='Fig2')
        
        # Dataframe con posiciones
        df_pct_position = pd.read_csv(os.path.join(proc_data_path, "DefenderPercentile.csv"), sep=';')
        player_pct_df = dataframe_filter(df_original=df_pct_position, player=player_slug)

        # Aplicamos colores
        color_map = {'22/23': '#2A9D8F', '23/24': '#264653', '24/25': '#E9C46A', '25/26': '#E63946'}
        player_pct_df['Color'] = player_pct_df['season'].map(color_map)

        radar_player = radar_player_seasons(df=player_pct_df, position=pos_letter, player_name=player_info_dict['Jugador'], 
                                            subtitle=f'Jugador: {player_info_dict['Jugador']}', figures_path=figures_path)

    elif pos_letter == 'M':
        fig1 = comparison_players_metrics(player_info_df=player_info_df, player_stats_df=player_stats_df, season=season, position=pos_letter,
                                        player_slug=player_slug, player_name=player_info_dict['Jugador'], xaxis='ballRecovery_per90', yaxis='expectedAssists_per90',
                                        xaxis_title='Recuperación de balón por 90', yaxis_title='Asistencias esperadas por 90', figures_path=figures_path, name_figure='Fig1')
        fig2 = comparison_players_metrics(player_info_df=player_info_df, player_stats_df=player_stats_df, season=season, position=pos_letter,
                                        player_slug=player_slug, player_name=player_info_dict['Jugador'], xaxis='pass_accuracy', yaxis='passValueNormalized',
                                        xaxis_title='Precisión de pase', yaxis_title='Valor de pase normalizado', figures_path=figures_path, name_figure='Fig2')
        
        # Dataframe con posiciones
        df_pct_position = pd.read_csv(os.path.join(proc_data_path, "MidfielderPercentile.csv"), sep=';')
        player_pct_df = dataframe_filter(df_original=df_pct_position, player=player_slug)

        # Aplicamos colores
        color_map = {'22/23': '#2A9D8F', '23/24': '#264653', '24/25': '#E9C46A', '25/26': '#E63946'}
        player_pct_df['Color'] = player_pct_df['season'].map(color_map)

        radar_player = radar_player_seasons(df=player_pct_df, position=pos_letter, player_name=player_info_dict['Jugador'], 
                                            subtitle=f'Jugador: {player_info_dict['Jugador']}', figures_path=figures_path)

    elif pos_letter == 'F':
        fig1 = comparison_players_metrics(player_info_df=player_info_df, player_stats_df=player_stats_df, season=season, position=pos_letter,
                                        player_slug=player_slug, player_name=player_info_dict['Jugador'], xaxis='expectedGoals_per90', yaxis='goals_per90',
                                        xaxis_title='Goles esperados por 90', yaxis_title='Goles por 90', figures_path=figures_path, name_figure='Fig1')
        fig2 = comparison_players_metrics(player_info_df=player_info_df, player_stats_df=player_stats_df, season=season, position=pos_letter,
                                        player_slug=player_slug, player_name=player_info_dict['Jugador'], xaxis='totalShots', yaxis='shotValueNormalized',
                                        xaxis_title='Tiros', yaxis_title='Valor de tiro normalizado', figures_path=figures_path, name_figure='Fig2')
        
        # Dataframe con posiciones
        df_pct_position = pd.read_csv(os.path.join(proc_data_path, "ForwardPercentile.csv"), sep=';')
        player_pct_df = dataframe_filter(df_original=df_pct_position, player=player_slug)

        # Aplicamos colores
        color_map = {'22/23': '#2A9D8F', '23/24': '#264653', '24/25': '#E9C46A', '25/26': '#E63946'}
        player_pct_df['Color'] = player_pct_df['season'].map(color_map)

        radar_player = radar_player_seasons(df=player_pct_df, position=pos_letter, player_name=player_info_dict['Jugador'], 
                                            subtitle=f'Jugador: {player_info_dict['Jugador']}', figures_path=figures_path)
    
    return_list.append([fig1, fig2, radar_player])
    return return_list