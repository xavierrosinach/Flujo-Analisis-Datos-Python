import pandas as pd
import os
import numpy as np

# ===========================================================================================================================================
# FUNCIÓN 1. PARA DIVIDIR CORRECTAMENTE, SIENDO EL DIVIDENDO 0
# ===========================================================================================================================================
def _safe_div(n, d):
    n = pd.to_numeric(n, errors="coerce")
    d = pd.to_numeric(d, errors="coerce")
    return np.where((d.notna()) & (d != 0), n / d, np.nan)

# ===========================================================================================================================================
# FUNCIÓN 2. AGRUPA SEGÚN LO QUE SE DEFINA
# ===========================================================================================================================================
def filter_df(df_to_group: pd.DataFrame, league: str, season: str, team: str = None, player: str = None) -> pd.DataFrame:

    # Agrupamos por liga y temporada
    df = df_to_group[(df_to_group['league'] == league) & (df_to_group['season'] == season)].copy()

    # Si equipo no es none, agrupamos por equipo
    if team is not None:
        
        # Creamos el slug
        selected_team_slug = team.lower().replace(" ", "-")

        # Comprovamos que la columna equipo este en el dataframe y que el equipo se encuentre tambien
        if ('team_slug' in df.columns) and (selected_team_slug in df['team_slug'].unique().tolist()):
            df = df[df['team_slug'] == selected_team_slug]
        else:
            return pd.DataFrame

    # Idem para jugador
    if player is not None:

        # Creamos el slug
        selected_player_slug = player.lower().replace(" ", "-")

        # Idem para jugador
        if ('player_slug' in df.columns) and (selected_player_slug in df['player_slug'].unique().tolist()):
            df = df[df['player_slug'] == selected_player_slug]
        else:
            return pd.DataFrame

    return df.reset_index(drop=True)

# ===========================================================================================================================================
# FUNCIÓN 3. LIMPIEZA DEL DATAFRAME DE INFORMACIÓN DE LOS JUGADORES
# ===========================================================================================================================================
def player_info_cleaner(player_info_df: pd.DataFrame) -> pd.DataFrame:
    df = player_info_df.copy()

    # Jersey number → int (NaN → 0)
    if 'jersey_number' in df.columns:
        df['jersey_number'] = (pd.to_numeric(df['jersey_number'], errors='coerce').fillna(0).astype(int))

    # Market value → numeric, NaN → 0
    if 'market_value' in df.columns:
        df['market_value'] = (pd.to_numeric(df['market_value'], errors="coerce").fillna(0))

    # Fecha de nacimiento → datetime
    if 'date_birth' in df.columns:
        s = pd.to_numeric(df['date_birth'], errors='coerce')
        unit = "ms" if s.dropna().median() > 1e12 else "s"
        birth = pd.to_datetime(s, unit=unit, errors='coerce')

        today = pd.Timestamp.today().normalize()
        df['age'] = (today.year - birth.dt.year - ((today.month < birth.dt.month) | ((today.month == birth.dt.month) & (today.day < birth.dt.day)))).fillna(0).astype(int)
        df['date_birth'] = birth.dt.strftime('%d/%m/%Y')

    return df

# ===========================================================================================================================================
# FUNCIÓN 4. LIMPIEZA DEL DATAFRAME DE INFORMACIÓN DE LOS PARTIDOS
# ===========================================================================================================================================
def match_info_cleaner(match_info_df: pd.DataFrame) -> pd.DataFrame:
    df = match_info_df.copy()

    # Resultados a integers
    for col in ["home_score", "away_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    
    # Fecha del partido
    if 'date' in df.columns:
        s = pd.to_numeric(df['date'], errors='coerce')
        unit = "ms" if s.dropna().median() > 1e12 else "s"
        date_match = pd.to_datetime(s, unit=unit, errors='coerce')

        df['date'] = date_match.dt.strftime('%d/%m/%Y')
        df["time"] = date_match.dt.strftime("%H:%M") 

    return df

# ===========================================================================================================================================
# FUNCIÓN 5. AÑADIMOS MÁS MÉTRICAS AL PARTIDO
# ===========================================================================================================================================
def add_match_features(df: pd.DataFrame) -> pd.DataFrame:

    # -----------------------------
    # Básicos: tipos + flags
    # -----------------------------
    if "minutesPlayed" in df.columns:
        df["played"] = df["minutesPlayed"] > 0
        if "starter" in df.columns:
            df["start"] = df["played"] & (df["starter"] == True)
            df["sub_appearance"] = df["played"] & (df["starter"] == False)

        # factor per90
        df["p90_factor"] = np.where(df["minutesPlayed"] > 0, 90.0 / df["minutesPlayed"], np.nan)

    # -----------------------------
    # PASING / DISTRIBUCIÓN: accuracies + shares + per90
    # -----------------------------
    if {"accuratePass", "totalPass"}.issubset(df.columns):
        df["pass_accuracy"] = _safe_div(df["accuratePass"], df["totalPass"])

    if {"accurateLongBalls", "totalLongBalls"}.issubset(df.columns):
        df["longball_accuracy"] = _safe_div(df["accurateLongBalls"], df["totalLongBalls"])  # FIX
        # shares
        if "totalPass" in df.columns:
            df["longballs_share_of_passes"] = _safe_div(df["totalLongBalls"], df["totalPass"])

    if {"accurateCross", "totalCross"}.issubset(df.columns):
        df["cross_accuracy"] = _safe_div(df["accurateCross"], df["totalCross"])
        if "totalPass" in df.columns:
            df["cross_share_of_passes"] = _safe_div(df["totalCross"], df["totalPass"])

    if {"accurateThroughBalls", "totalThroughBalls"}.issubset(df.columns):
        df["throughball_accuracy"] = _safe_div(df["accurateThroughBalls"], df["totalThroughBalls"])

    if {"accurateChippedPass", "totalChippedPass"}.issubset(df.columns):
        df["chippedpass_accuracy"] = _safe_div(df["accurateChippedPass"], df["totalChippedPass"])

    if {"accurateKeyPass", "keyPass"}.issubset(df.columns):
        df["keypass_accuracy"] = _safe_div(df["accurateKeyPass"], df["keyPass"])        # A veces accurate key pass no existe

    if {"keyPass", "totalPass"}.issubset(df.columns):
        df["keypass_rate_per_pass"] = _safe_div(df["keyPass"], df["totalPass"])

    if {"bigChanceCreated", "keyPass"}.issubset(df.columns):
        df["bigchance_created_per_keypass"] = _safe_div(df["bigChanceCreated"], df["keyPass"])

    # Pases por 90
    if "p90_factor" in df.columns:
        for col in [
            "totalPass","accuratePass",
            "totalLongBalls","accurateLongBalls",
            "totalCross","accurateCross",
            "keyPass","bigChanceCreated",
            "totalThroughBalls","accurateThroughBalls"
        ]:
            if col in df.columns:
                df[f"{col}_per90"] = df[col] * df["p90_factor"]

    # -----------------------------
    # SHOOTING / FINALIZACIÓN: accuracies + efficiencies + per90
    # -----------------------------
    if {"shotsOnTarget", "totalShot"}.issubset(df.columns):
        df["shot_accuracy_on_target"] = _safe_div(df["shotsOnTarget"], df["totalShot"])

    if {"goals", "totalShot"}.issubset(df.columns):
        df["goal_conversion_per_shot"] = _safe_div(df["goals"], df["totalShot"])

    if {"goals", "shotsOnTarget"}.issubset(df.columns):
        df["goal_conversion_per_sot"] = _safe_div(df["goals"], df["shotsOnTarget"])

    if {"goals", "expectedGoals"}.issubset(df.columns):
        df["goals_minus_xg"] = df["goals"] - df["expectedGoals"]
        df["goals_over_xg"] = _safe_div(df["goals"], df["expectedGoals"])

    if {"expectedGoals", "totalShot"}.issubset(df.columns):
        df["xg_per_shot"] = _safe_div(df["expectedGoals"], df["totalShot"])

    if {"goalAssist", "expectedAssists"}.issubset(df.columns):
        df["assists_minus_xa"] = df["goalAssist"] - df["expectedAssists"]
        df["assists_over_xa"] = _safe_div(df["goalAssist"], df["expectedAssists"])

    if {"goals", "goalAssist"}.issubset(df.columns):
        df["ga"] = df["goals"] + df["goalAssist"]

    if {"expectedGoals", "expectedAssists"}.issubset(df.columns):
        df["xg_xa"] = df["expectedGoals"] + df["expectedAssists"]

    if "p90_factor" in df.columns:
        for col in ["goals","expectedGoals","goalAssist","expectedAssists","totalShot","shotsOnTarget","bigChanceMissed"]:
            if col in df.columns:
                df[f"{col}_per90"] = df[col] * df["p90_factor"]

    # -----------------------------
    # DRIBBLES / 1v1
    # -----------------------------
    if {"successfulDribbles", "totalDribble"}.issubset(df.columns):
        df["dribble_success_rate"] = _safe_div(df["successfulDribbles"], df["totalDribble"])

    if {"successfulDribbles", "totalPass"}.issubset(df.columns):
        df["dribbles_per_pass"] = _safe_div(df["successfulDribbles"], df["totalPass"])

    if "p90_factor" in df.columns:
        for col in ["successfulDribbles","totalDribble","wonContest","totalContest","dispossessed"]:
            if col in df.columns:
                df[f"{col}_per90"] = df[col] * df["p90_factor"]

    if {"wonContest", "totalContest"}.issubset(df.columns):
        df["contest_win_rate"] = _safe_div(df["wonContest"], df["totalContest"])

    # -----------------------------
    # DUELOS / FÍSICO (suelo y aéreo)
    # -----------------------------
    if {"duelWon", "totalDuels"}.issubset(df.columns):
        df["duel_win_rate"] = _safe_div(df["duelWon"], df["totalDuels"])

    if {"groundDuelsWon", "groundDuels"}.issubset(df.columns):
        df["ground_duel_win_rate"] = _safe_div(df["groundDuelsWon"], df["groundDuels"])

    if {"aerialDuelsWon", "aerialDuels"}.issubset(df.columns):
        df["aerial_duel_win_rate"] = _safe_div(df["aerialDuelsWon"], df["aerialDuels"])

    if {"wasFouled", "fouls"}.issubset(df.columns):
        df["fouls_drawn_to_committed"] = _safe_div(df["wasFouled"], df["fouls"])

    if "p90_factor" in df.columns:
        for col in ["duelWon","totalDuels","groundDuelsWon","groundDuels","aerialDuelsWon","aerialDuels","fouls","wasFouled"]:
            if col in df.columns:
                df[f"{col}_per90"] = df[col] * df["p90_factor"]

    # -----------------------------
    # DEFENSA: tackles, interceptions, clearances, blocks, recoveries
    # -----------------------------
    if {"tacklesWon", "tackles"}.issubset(df.columns):
        df["tackle_success_rate"] = _safe_div(df["tacklesWon"], df["tackles"])

    if {"challengeWon", "challengeLost"}.issubset(df.columns):
        df["challenge_total"] = df["challengeWon"] + df["challengeLost"]
        df["challenge_win_rate"] = _safe_div(df["challengeWon"], df["challenge_total"])

    defensive_cols = ["tacklesWon","interceptionWon","blockedShots","clearance","ballRecovery"]
    present_def_cols = [c for c in defensive_cols if c in df.columns]
    if present_def_cols:
        df["def_actions"] = df[present_def_cols].sum(axis=1)

    # Defensa por 90
    if "p90_factor" in df.columns:
        for col in ["tackles","tacklesWon","interceptionWon","blockedShots","clearance","ballRecovery","errorLeadToShot","errorLeadToGoal"]:
            if col in df.columns:
                df[f"{col}_per90"] = df[col] * df["p90_factor"]
        if "def_actions" in df.columns:
            df["def_actions_per90"] = df["def_actions"] * df["p90_factor"]

    # -----------------------------
    # POSSESIÓN: touches, possessionLost, etc.
    # -----------------------------
    if {"possessionLost", "touches"}.issubset(df.columns):
        df["possession_lost_per_touch"] = _safe_div(df["possessionLost"], df["touches"])

    if {"dispossessed", "touches"}.issubset(df.columns):
        df["dispossessed_per_touch"] = _safe_div(df["dispossessed"], df["touches"])

    if {"ballRecovery", "possessionLost"}.issubset(df.columns):
        df["recovery_to_loss_ratio"] = _safe_div(df["ballRecovery"], df["possessionLost"])

    if "p90_factor" in df.columns:
        for col in ["touches","possessionLost","dispossessed"]:
            if col in df.columns:
                df[f"{col}_per90"] = df[col] * df["p90_factor"]

    # -----------------------------
    # DISCIPLINA
    # -----------------------------
    if "yellowCards" in df.columns and "redCards" in df.columns:
        df["cards"] = df["yellowCards"] + 2 * df["redCards"]

    if "p90_factor" in df.columns:
        for col in ["yellowCards","redCards","cards"]:
            if col in df.columns:
                df[f"{col}_per90"] = df[col] * df["p90_factor"]

    # -----------------------------
    # GOALKEEPER (si aplica)
    # -----------------------------
    if {"saves", "shotsOnTargetFaced"}.issubset(df.columns):
        df["gk_save_pct"] = _safe_div(df["saves"], df["shotsOnTargetFaced"])

    if {"goalsConceded", "shotsOnTargetFaced"}.issubset(df.columns):
        df["gk_concede_per_sot"] = _safe_div(df["goalsConceded"], df["shotsOnTargetFaced"])

    if {"goalsConceded", "postShotExpectedGoals"}.issubset(df.columns):
        df["gk_goalsconceded_minus_psxg"] = df["goalsConceded"] - df["postShotExpectedGoals"]

    # Portero por 90
    if "p90_factor" in df.columns:
        for col in ["saves","shotsOnTargetFaced","goalsConceded","postShotExpectedGoals"]:
            if col in df.columns:
                df[f"{col}_per90"] = df[col] * df["p90_factor"]

    # -----------------------------
    # METRICS COMPUESTAS
    # -----------------------------

    # "Attacking contribution" = xG + xA + key passes weighted (si existe)
    if {"expectedGoals", "expectedAssists"}.issubset(df.columns):
        df["attack_value_raw"] = df["expectedGoals"] + df["expectedAssists"]
        if "keyPass" in df.columns:
            df["attack_value_raw"] = df["attack_value_raw"] + 0.05 * df["keyPass"]

    # "Ball progression" (si tienes progressive passes/carries)
    if {"progressivePasses", "progressiveCarries"}.issubset(df.columns):
        df["progression_actions"] = df["progressivePasses"] + df["progressiveCarries"]
    elif "progressivePasses" in df.columns:
        df["progression_actions"] = df["progressivePasses"]
    elif "progressiveCarries" in df.columns:
        df["progression_actions"] = df["progressiveCarries"]

    if "p90_factor" in df.columns:
        for col in ["attack_value_raw","progression_actions","def_actions"]:
            if col in df.columns:
                df[f"{col}_per90"] = df[col] * df["p90_factor"]

    return df

# ===========================================================================================================================================
# FUNCIÓN 6. OBTIENE LAS MÉTRICAS GENERALES DE LOS JUGADORES POR TEMPORADA
# ===========================================================================================================================================
def players_season_summary(df_match_player: pd.DataFrame, by_team: bool = True) -> pd.DataFrame:

    df = df_match_player.copy()

    # Flags mínimos - por si acaso
    if "minutesPlayed" in df.columns:
        df["minutesPlayed"] = pd.to_numeric(df["minutesPlayed"], errors="coerce").fillna(0)
        df["played"] = df["minutesPlayed"] > 0
    else:
        df["minutesPlayed"] = 0
        df["played"] = False

    if "starter" in df.columns:
        df["starter"] = df["starter"].astype("boolean")
        df["start"] = df["played"] & (df["starter"] == True)
    else:
        df["start"] = False

    # Agrupamos
    keys = ["league", "season", "player_slug"]
    if by_team and "team_slug" in df.columns:
        keys.append("team_slug")
    g = df.groupby(keys, dropna=False)

    # -----------------------------------------------------------------------------------------------------------------------------
    # CONTEOS
    # -----------------------------------------------------------------------------------------------------------------------------
    # Si match es id numérico, usamos nunique. Si no existe, usa match_slug.
    match_id_col = "match" if "match" in df.columns else ("match_slug" if "match_slug" in df.columns else None)
    base = g.agg(Matches=("{}".format(match_id_col), "nunique"), MatchesPlayed=("played", "sum"),
                 Starts=("start", "sum"), Minutes=("minutesPlayed", "sum"))

    # -----------------------------------------------------------------------------------------------------------------------------
    # SUMAS DE ESTADÍSTICAS
    # -----------------------------------------------------------------------------------------------------------------------------
    # Cogemos todas las numéricas excepto IDs evidentes
    num_cols = df.select_dtypes(include="number").columns.tolist()
    exclude = set(["minutesPlayed"])  # ya agregada
    # Excluye IDs numéricos típicos si existiesen
    for c in ["match", "player_id", "team_id", "season_id", "league_id"]:
        if c in num_cols:
            exclude.add(c)

    sum_cols = [c for c in num_cols if c not in exclude]
    sums = g[sum_cols].sum(min_count=1) if sum_cols else pd.DataFrame(index=base.index)
    out = pd.concat([base, sums], axis=1).reset_index()

    # -----------------------------------------------------------------------------------------------------------------------------
    # RECALCULO DE ACCURACIES
    # -----------------------------------------------------------------------------------------------------------------------------
    # Pase
    if {"accuratePass", "totalPass"}.issubset(out.columns):
        out["PassAccuracy"] = _safe_div(out["accuratePass"], out["totalPass"])

    # Long balls
    if {"accurateLongBalls", "totalLongBalls"}.issubset(out.columns):
        out["LongBallAccuracy"] = _safe_div(out["accurateLongBalls"], out["totalLongBalls"])

    # Centros
    if {"accurateCross", "totalCross"}.issubset(out.columns):
        out["CrossAccuracy"] = _safe_div(out["accurateCross"], out["totalCross"])

    # Regates
    if {"successfulDribbles", "totalDribble"}.issubset(out.columns):
        out["DribbleSuccessRate"] = _safe_div(out["successfulDribbles"], out["totalDribble"])

    # Duelos
    if {"duelWon", "totalDuels"}.issubset(out.columns):
        out["DuelWinRate"] = _safe_div(out["duelWon"], out["totalDuels"])

    # Tackle %
    if {"tacklesWon", "tackles"}.issubset(out.columns):
        out["TackleSuccessRate"] = _safe_div(out["tacklesWon"], out["tackles"])

    # Shooting accuracy & conversion
    if {"shotsOnTarget", "totalShot"}.issubset(out.columns):
        out["ShotOnTargetRate"] = _safe_div(out["shotsOnTarget"], out["totalShot"])
    if {"goals", "totalShot"}.issubset(out.columns):
        out["GoalPerShot"] = _safe_div(out["goals"], out["totalShot"])
    if {"goals", "shotsOnTarget"}.issubset(out.columns):
        out["GoalPerSoT"] = _safe_div(out["goals"], out["shotsOnTarget"])

    # xG/xA (si existen)
    if {"goals", "expectedGoals"}.issubset(out.columns):
        out["GoalsMinusxG"] = out["goals"] - out["expectedGoals"]
    if {"goalAssist", "expectedAssists"}.issubset(out.columns):
        out["AssistsMinusxA"] = out["goalAssist"] - out["expectedAssists"]
    if {"expectedGoals", "totalShot"}.issubset(out.columns):
        out["xGPerShot"] = _safe_div(out["expectedGoals"], out["totalShot"])

    # -----------------------------------------------------------------------------------------------------------------------------
    # POR 90
    # -----------------------------------------------------------------------------------------------------------------------------
    out["P90Factor"] = np.where(out["Minutes"] > 0, 90.0 / out["Minutes"], np.nan)

    # Define qué quieres llevar a per90 (añade/quita columnas a gusto)
    per90_candidates = ["goals","goalAssist","expectedGoals","expectedAssists","totalShot","shotsOnTarget","keyPass","bigChanceCreated","totalPass","accuratePass","totalLongBalls","accurateLongBalls",
                        "successfulDribbles","totalDribble","duelWon","totalDuels","tacklesWon","tackles","interceptionWon","ballRecovery","clearance","blockedShots","possessionLost","touches","yellowCards","redCards"]
    for c in per90_candidates:
        if c in out.columns:
            out[f"{c}_per90"] = out[c] * out["P90Factor"]

    # -----------------------------------------------------------------------------------------------------------------------------
    # ÍNDICES PARA VALORAR
    # -----------------------------------------------------------------------------------------------------------------------------
    # Ataque: xG + xA + 0.05*keyPass (ajusta pesos)
    if {"expectedGoals", "expectedAssists"}.issubset(out.columns):
        out["AttackIndex"] = out["expectedGoals"] + out["expectedAssists"]
        if "keyPass" in out.columns:
            out["AttackIndex"] = out["AttackIndex"] + 0.05 * out["keyPass"]

    # Defensa: suma de acciones defensivas si existen
    def_cols = [c for c in ["tacklesWon","interceptionWon","blockedShots","clearance","ballRecovery"] if c in out.columns]
    if def_cols:
        out["DefActions"] = out[def_cols].sum(axis=1)
        out["DefActions_per90"] = out["DefActions"] * out["P90Factor"]

    # Índice global simple (normalízalo luego si vas a rankear)
    idx_parts = []
    if "AttackIndex" in out.columns: idx_parts.append("AttackIndex")
    if "DefActions_per90" in out.columns: idx_parts.append("DefActions_per90")
    if idx_parts:
        out["OverallIndex_raw"] = out[idx_parts].sum(axis=1, min_count=1)

    # Limpieza final
    final_df = out.drop(columns=["P90Factor"])

    return final_df

# ===========================================================================================================================================
# FUNCIÓN 7. LIMPIEZA DE ESTADÍSTICAS DE LOS JUGADORES EN UNA TEMPORADA
# ===========================================================================================================================================
def player_stats_cleaner(player_stats_df: pd.DataFrame, league: str, season: str) -> pd.DataFrame:

    # Obtenemos los datos filtrados
    league_df = filter_df(df_to_group=player_stats_df, league=league, season=season)

    # Seleccionamos las columnas numericas
    numeric_cols = league_df.select_dtypes(include='number').columns.tolist()
    numeric_cols = [c for c in numeric_cols if 'match' not in c.lower()]

    # Máscara: suma por fila > 0
    mask = league_df[numeric_cols].fillna(0).sum(axis=1) > 0

    # Filtramos filas y reseteamos índice
    league_df = league_df.loc[mask].reset_index(drop=True)

    # ================================================================================
    # CLEANING DEL DATAFRAME
    # ================================================================================

    # Tipo de starter y minutos jugados, para evitar errores
    if "starter" in league_df.columns:
        league_df["starter"] = league_df["starter"].astype("boolean")
    if "minutesPlayed" in league_df.columns:
        league_df["minutesPlayed"] = pd.to_numeric(league_df["minutesPlayed"], errors="coerce").fillna(0)

    # Fill valores nan con 0 -> solo columnas numericas
    league_df[numeric_cols].fillna(0)

    # Aplicamos la función para obtener más metricas
    cleaned_league_df = add_match_features(df=league_df)

    # ================================================================================
    # CREACIÓN DEL DATAFRAME DE ESTADÍSTICAS POR TEMPORADA
    # ================================================================================
    players_season_summary_team = players_season_summary(df_match_player=cleaned_league_df, by_team=True)
    players_season_summary_no_team = players_season_summary(df_match_player=cleaned_league_df, by_team=False)

    return cleaned_league_df.fillna(0), players_season_summary_team.fillna(0), players_season_summary_no_team.fillna(0)

# ===========================================================================================================================================
# FUNCIÓN 8. CALCULA PERCENTILES POR POSICIÓN Y GRUPOS
# ===========================================================================================================================================
def compute_position_groups(df: pd.DataFrame, position: str, GROUPS: dict) -> pd.DataFrame:

    if df.empty:
        return pd.DataFrame(columns=["player_slug"])

    # Filtrar por posición
    pos_df = df[df["position"] == position].copy()

    if pos_df.empty:
        return pd.DataFrame(columns=["player_slug"])

    outputs = []

    # Iterar grupos
    for group_name, cfg in GROUPS.items():

        metric_cols = [c for c in cfg.get("cols", []) if c in pos_df.columns]
        invert_cols = cfg.get("invert", [])

        if not metric_cols:
            continue

        # Solo player + métricas necesarias
        base = pos_df[["player_slug"] + metric_cols].drop_duplicates("player_slug").copy()

        pct_cols = []

        # Percent_rank por cada métrica
        for col in metric_cols:

            # percent_rank estilo Spark
            pct = base[col].rank(method="min", pct=True)

            # Invertir si toca
            if col in invert_cols:
                pct = 1 - pct

            pct_name = f"__pct_{col}"
            base[pct_name] = pct
            pct_cols.append(pct_name)

        # Media ignorando NaNs
        base[f"pct_{group_name}"] = base[pct_cols].mean(axis=1, skipna=True)

        outputs.append(base[["player_slug", f"pct_{group_name}"]])

    # Merge de todos los grupos
    if not outputs:
        return pos_df[["player_slug"]].drop_duplicates()

    res = outputs[0]

    for t in outputs[1:]:
        res = res.merge(t, on="player_slug", how="outer")

    return res

# ===========================================================================================================================================
# FUNCIÓN PRINCIPAL -  A PARTIR DE LOS DATOS QUE TENEMOS, LOS TRANSFORMAMOS
# ===========================================================================================================================================
def main_processing_pandas(data_path):

    # Grupos percentiles porteros
    GK_GROUPS = {
        # 1) Shot stopping: evitar gols
        "ShotStopping": {
            "cols": ["GoalsMinusxG", "goalsPrevented", "saves_per90"],
            "invert": [],
        },

        # 2) Reliability: errors greus (invertides)
        "Reliability": {
            "cols": ["errorLeadToAGoal", "errorLeadToAShot", "ownGoals"],
            "invert": ["errorLeadToAGoal", "errorLeadToAShot", "ownGoals"],
        },

        # 3) Area control: domini de l’àrea
        "AreaControl": {
            "cols": ["goodHighClaim", "punches", "crossNotClaimed"],
            "invert": ["crossNotClaimed"],
        },

        # 4) Sweeper keeper: joc fora de l’àrea
        "SweeperKeeper": {
            "cols": ["totalKeeperSweeper", "accurateKeeperSweeper"],
            "invert": [],
        },

        # 5) Build-up play: joc amb peus
        "BuildUpPlay": {
            "cols": ["pass_accuracy", "longball_accuracy"],
            "invert": [],
        },
    }

    # Grupos percentiles defensas
    DF_GROUPS = {
        # 1) Defensive actions: defensa directa
        "DefensiveActions": {
            "cols": ["DefActions_per90", "interceptionWon_per90", "ballRecovery_per90"],
            "invert": [],
        },

        # 2) Duels: 1v1
        "Duels": {
            "cols": ["duelWon_per90", "contest_win_rate"],
            "invert": [],
        },

        # 3) Aerial ability: joc aeri
        "AerialAbility": {
            "cols": ["aerialWon", "aerialLost"],
            "invert": ["aerialLost"],
        },

        # 4) Build-up play: sortida de pilota
        "BuildUpPlay": {
            "cols": ["pass_accuracy", "totalProgression", "progressiveBallCarriesCount"],
            "invert": [],
        },

        # 5) Defensive reliability: errors i faltes
        "DefensiveReliability": {
            "cols": ["errorLeadToAGoal", "penaltyConceded", "fouls_per90"],
            "invert": ["errorLeadToAGoal", "penaltyConceded", "fouls_per90"],
        },
    }

    # Grupos percentiles centrocampistast
    MF_GROUPS = {
        # 1) Ball distribution: control del joc
        "BallDistribution": {
            "cols": ["pass_accuracy", "totalPass_per90", "passValueNormalized"],
            "invert": [],
        },

        # 2) Progression: avançar línies
        "Progression": {
            "cols": ["totalProgression", "progressiveBallCarriesCount", "bestBallCarryProgression"],
            "invert": [],
        },

        # 3) Chance creation: generar ocasions
        "ChanceCreation": {
            "cols": ["keyPass_per90", "expectedAssists_per90", "bigChanceCreated_per90"],
            "invert": [],
        },

        # 4) Defensive balance: treball sense pilota
        "DefensiveBalance": {
            "cols": ["DefActions_per90", "ballRecovery_per90"],
            "invert": [],
        },

        # 5) Ball retention: conservar possessió
        "BallRetention": {
            "cols": ["dispossessed_per90", "possessionLostCtrl", "unsuccessfulTouch"],
            "invert": ["dispossessed_per90", "possessionLostCtrl", "unsuccessfulTouch"],
        },
    }

    # Grupos percentiles delanteros
    FW_GROUPS = {
        # 1) Finalización: producción + calidad + eficiencia
        "Finishing": {
            "cols": ["goals_per90", "expectedGoals_per90", "goals_over_xg", "shotValueNormalized", "bigChanceMissed_per90"],
            "invert": ["bigChanceMissed_per90"],
        },

        # 2) Creación: generar para otros
        "ChanceCreation": {
            "cols": ["keyPass_per90", "expectedAssists_per90", "bigChanceCreated_per90", "assists_over_xa", "goalAssist_per90"],
            "invert": [],
        },

        # 3) Amenaza: capacidad de desequilibrar y progresar
        "Threat": {
            "cols": ["dribbleValueNormalized", "totalProgression", "progressiveBallCarriesCount", "attack_value_raw_per90", "totalShots"],
            "invert": [],
        },

        # 4) Participación sin balón: presencia/actividad ofensiva
        "OffBallInvolvement": {
            "cols": ["touches_per90", "wasFouled_per90", "penaltyWon", "totalOffside", "ballCarriesCount"],
            "invert": [],
        },

        # 5) Eficiencia/seguridad: evitar pèrdues i accions negatives
        "Efficiency": {
            "cols": ["dispossessed_per90", "possessionLostCtrl", "unsuccessfulTouch", "fouls_per90", "bigChanceMissed_per90"],
            "invert": ["dispossessed_per90", "possessionLostCtrl", "unsuccessfulTouch", "fouls_per90", "bigChanceMissed_per90"],
        },
    }

    # Paths de los cuatro dataframes
    league_info_path = f'{data_path}/raw/LeagueInfo.csv'
    match_info_path = f'{data_path}/raw/MatchInfo.csv'
    player_info_path = f'{data_path}/raw/PlayerInfo.csv'
    player_stats_path = f'{data_path}/raw/PlayerStats.csv'

    # Lectura de los CSVs si existen
    league_info_df = pd.read_csv(league_info_path, sep=';') if os.path.exists(league_info_path) else pd.DataFrame
    match_info_df = pd.read_csv(match_info_path, sep=';') if os.path.exists(match_info_path) else pd.DataFrame
    player_info_df = pd.read_csv(player_info_path, sep=';') if os.path.exists(player_info_path) else pd.DataFrame
    player_stats_df = pd.read_csv(player_stats_path, sep=';') if os.path.exists(player_stats_path) else pd.DataFrame

    # Cambiamos nombres a columnas de 'slug' para el grouper
    player_info_df = player_info_df.rename(columns={'slug': 'player_slug'})
    player_stats_df = player_stats_df.rename(columns={'slug': 'player_slug'})

    # Cleaning de la información de los partidos y jugadores
    match_info_df_cleaned = match_info_cleaner(match_info_df=match_info_df)
    player_info_df_cleaned = player_info_cleaner(player_info_df=player_info_df)

    # Guardado a carpeta 'clean'
    match_info_df_cleaned.to_csv(f'{data_path}/clean/MatchInfo.csv', sep=';', index=False)
    player_info_df_cleaned.to_csv(f'{data_path}/clean/PlayerInfo.csv', sep=';', index=False)

    # Diccionario para añadir el nombre de los jugadores
    player_dict = (player_info_df_cleaned.set_index("player_slug")["name"].to_dict())

    # Obtenemos los dataframes de ligas y temporadas - listas para concatenar
    list_cleaned_league = []
    list_player_summ_team = []
    list_player_summ_no_team = []

    # Para cada liga y temporada
    for index, row in league_info_df.iterrows():

        # Liga y temporada
        sel_league = row['League']
        sel_season = row['Season']

        # Obtenemos la información
        cleaned_league_df, players_season_summary_team, players_season_summary_no_team = player_stats_cleaner(player_stats_df=player_stats_df, league=sel_league, season=sel_season)

        # Obtención del dataframe con el jugador y su posición aquella temporada - y cruzamos
        players_season_pos = player_info_df_cleaned[(player_info_df_cleaned['league'] == sel_league) & (player_info_df_cleaned['season'] == sel_season)][['player_slug', 'position']]
        players_season_summary_team = players_season_summary_team.merge(players_season_pos, on='player_slug')
        players_season_summary_no_team = players_season_summary_no_team.merge(players_season_pos, on='player_slug')
        
        # Concatenamos
        list_cleaned_league.append(cleaned_league_df)
        list_player_summ_team.append(players_season_summary_team)
        list_player_summ_no_team.append(players_season_summary_no_team)

    # Creación del dataframe único
    cleaned_league_all = pd.concat(list_cleaned_league, ignore_index=True).drop_duplicates()            
    cleaned_league_all.insert(4, "player_name", cleaned_league_all["player_slug"].map(player_dict))         # Añadir los nombres de los jugadores
    player_summ_team_all = pd.concat(list_player_summ_team, ignore_index=True).drop_duplicates()
    player_summ_team_all.insert(3, "player_name", player_summ_team_all["player_slug"].map(player_dict))
    player_summ_no_team_all = pd.concat(list_player_summ_no_team, ignore_index=True).drop_duplicates()
    player_summ_no_team_all.insert(3, "player_name", player_summ_no_team_all["player_slug"].map(player_dict))

    # Lista para cada posición
    gk_list = []
    df_list = []
    mf_list = []
    fw_list = []

    # Obtenemos el porcentil para cada año
    for sel_season in league_info_df['Season'].unique().tolist():

        # Elegimos del dataframe la temporada
        df_to_process = player_summ_no_team_all[player_summ_no_team_all['season'] == sel_season].copy()

        # Procesamos según posición
        gk_percentiles = compute_position_groups(df_to_process, "G", GK_GROUPS)
        df_percentiles = compute_position_groups(df_to_process, "D", DF_GROUPS)
        mf_percentiles = compute_position_groups(df_to_process, "M", MF_GROUPS)
        fw_percentiles = compute_position_groups(df_to_process, "M", MF_GROUPS)

        # Añadimos la temporada
        gk_percentiles.insert(0, "season", sel_season)
        df_percentiles.insert(0, "season", sel_season)
        mf_percentiles.insert(0, "season", sel_season)
        fw_percentiles.insert(0, "season", sel_season)

        # Lo añadimos a las listas
        gk_list.append(gk_percentiles)
        df_list.append(df_percentiles)
        mf_list.append(mf_percentiles)
        fw_list.append(fw_percentiles)

    # Transformamos las listas a dataframes para posteriormente guardarlos en formato CSV
    goalkeeper_percentiles_df = pd.concat(gk_list, ignore_index=True).drop_duplicates().sort_values(by=['season', 'player_slug'])
    goalkeeper_percentiles_df.insert(2, "player_name", goalkeeper_percentiles_df["player_slug"].map(player_dict))
    defender_percentiles_df = pd.concat(df_list, ignore_index=True).drop_duplicates().sort_values(by=['season', 'player_slug'])
    defender_percentiles_df.insert(2, "player_name", defender_percentiles_df["player_slug"].map(player_dict))
    midfielder_percentiles_df = pd.concat(mf_list, ignore_index=True).drop_duplicates().sort_values(by=['season', 'player_slug'])
    midfielder_percentiles_df.insert(2, "player_name", midfielder_percentiles_df["player_slug"].map(player_dict))
    forward_percentiles_df = pd.concat(fw_list, ignore_index=True).drop_duplicates().sort_values(by=['season', 'player_slug'])
    forward_percentiles_df.insert(2, "player_name", forward_percentiles_df["player_slug"].map(player_dict))

    # Guardado en formato CSV
    cleaned_league_all.to_csv(f'{data_path}/clean/PlayerStats.csv', sep=';', index=False)
    player_summ_team_all.to_csv(f'{data_path}/clean/PlayerTeamStatsSummary.csv', sep=';', index=False)
    player_summ_no_team_all.to_csv(f'{data_path}/clean/PlayerStatsSummary.csv', sep=';', index=False)
    goalkeeper_percentiles_df.to_csv(f'{data_path}/clean/GoalkeeperPercentile.csv', sep=';', index=False)
    defender_percentiles_df.to_csv(f'{data_path}/clean/DefenderPercentile.csv', sep=';', index=False)
    midfielder_percentiles_df.to_csv(f'{data_path}/clean/MidfielderPercentile.csv', sep=';', index=False)
    forward_percentiles_df.to_csv(f'{data_path}/clean/ForwardPercentile.csv', sep=';', index=False)

# if __name__ == "__main__":
#     main_processing_pandas(data_path="G:\\FootballData\\data")
