# Librerías generales
import os
import csv
import re
from typing import Dict, List, Optional, Tuple

# Librerías de tratamiento de datos
import pandas as pd
from pyspark.sql import SparkSession, DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark import TaskContext

# Configuración - vamos a usar-lo mucho durante el código, para evitar copiar
SEP = ";"
ENCODING = "utf-8"

# =====================================================================================================================================
# FUNCIÓN 0 (util). NORMALIZACIÓN DE COLUMNAS 
# =====================================================================================================================================
def normalize_columns(df: DataFrame) -> DataFrame:

    if df is None or len(df.columns) == 0:
        return df

    # Para cada nombre de la columna
    for c in df.columns:
        new = (c.strip().replace(" ", "_").replace(".", "_").replace("-", "_").lower())
        if new != c:
            df = df.withColumnRenamed(c, new)

    # Unificaciones típicas
    rename_map = {"league": "league", "season": "season", "slug": "player_slug"}
    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df = df.withColumnRenamed(old, new)

    return df


# =====================================================================================================================================
# FUNCIÓN 0 (util). CASTING DE COLUMNAS NUMÉRICAS PARA EVITAR STRINGS
# =====================================================================================================================================
def cast_numeric_cols(df: DataFrame, cols: List[str], as_int: bool = False) -> DataFrame:
    if df is None or len(df.columns) == 0:
        return df

    for c in cols:
        if c not in df.columns:
            continue

        s = F.col(c).cast("string")
        s = F.regexp_replace(s, ",", ".")
        s = F.regexp_replace(s, r"[^\d\.\-]", "")
        s = F.when((s.isNull()) | (s == ""), F.lit(None)).otherwise(s)

        # Si tiene que ser integer lo devolvemos
        if as_int:
            df = df.withColumn(c, s.cast("double").cast("int"))
        else:
            df = df.withColumn(c, s.cast("double"))

    return df

# =====================================================================================================================================
# FUNCIÓN 1. DIVISIÓN SEGURA ENTRE DOS NUMEROS
# =====================================================================================================================================
def safe_div(n_col, d_col):

    # División segura en caso de que el dividendo sea 0
    return F.when((d_col.isNotNull()) & (d_col != F.lit(0)) & (n_col.isNotNull()), n_col.cast("double") / d_col.cast("double")).otherwise(F.lit(None).cast("double"))

# =====================================================================================================================================
# FUNCIÓN 2. FILTRADO POR LIGA/TEMPORADA Y OPCIONALMENTE EQUIPO/JUGADOR
# =====================================================================================================================================
def filter_df(df: DataFrame,league: str,season: str,team: Optional[str] = None,player: Optional[str] = None) -> DataFrame:

    if df is None or len(df.columns) == 0:
        return df

    # Filtra siempre por liga y por temporada
    if "league" not in df.columns or "season" not in df.columns:
        return df.limit(0)

    out = df.filter((F.col("league") == league) & (F.col("season") == season))

    if team is not None:
        selected_team_slug = team.lower().replace(" ", "-")
        if "team_slug" in out.columns:
            out = out.filter(F.col("team_slug") == selected_team_slug)
        else:
            return out.limit(0)

    if player is not None:
        selected_player_slug = player.lower().replace(" ", "-")
        if "player_slug" in out.columns:
            out = out.filter(F.col("player_slug") == selected_player_slug)
        else:
            return out.limit(0)

    return out

# =====================================================================================================================================
# FUNCIÓN 3. LIMPIEZA DEL DATAFRAME DE INFORMACIÓN DE JUGADORES
# =====================================================================================================================================
def player_info_cleaner(player_info_df: DataFrame) -> DataFrame:
    df = player_info_df
    if df is None or len(df.columns) == 0:
        return df

    # Casts principales
    df = cast_numeric_cols(df, ["jersey_number"], as_int=True)
    df = cast_numeric_cols(df, ["market_value"], as_int=False)

    if "jersey_number" in df.columns:
        df = df.withColumn("jersey_number", F.coalesce(F.col("jersey_number"), F.lit(0)).cast("int"))

    if "market_value" in df.columns:
        df = df.withColumn("market_value", F.coalesce(F.col("market_value"), F.lit(0.0)).cast("double"))

    # Fecha de nacimiento a edad valida y fecha valida
    if "date_birth" in df.columns:
        s = F.col("date_birth").cast("double")

        secs = (F.when(s.isNull(), F.lit(None).cast("double")).when(s > F.lit(1e12), s / F.lit(1000.0)).otherwise(s))

        birth_ts = F.to_timestamp(F.from_unixtime(secs))
        birth_date = F.to_date(birth_ts)
        today = F.current_date()

        age = (F.year(today) - F.year(birth_date) - F.when((F.month(today) < F.month(birth_date)) |
                ((F.month(today) == F.month(birth_date)) & (F.dayofmonth(today) < F.dayofmonth(birth_date))), F.lit(1)
            ).otherwise(F.lit(0)))

        df = (df.withColumn("birth_ts", birth_ts).withColumn("age", F.coalesce(age, F.lit(0)).cast("int"))
              .withColumn("date_birth", F.date_format(F.col("birth_ts"), "dd/MM/yyyy")).drop("birth_ts"))

    return df

# =====================================================================================================================================
# FUNCIÓN 4. LIMPIEZA DEL DATAFRAME DE INFORMACIÓN DE PARTIDOS
# =====================================================================================================================================
def match_info_cleaner(match_info_df: DataFrame) -> DataFrame:
    df = match_info_df
    if df is None or len(df.columns) == 0:
        return df

    # Cast scores
    df = cast_numeric_cols(df, ["home_score", "away_score"], as_int=True)

    for colname in ["home_score", "away_score"]:
        if colname in df.columns:
            df = df.withColumn(colname, F.coalesce(F.col(colname), F.lit(0)).cast("int"))

    # Fecha correcta
    if "date" in df.columns:
        df = cast_numeric_cols(df, ["date"], as_int=False)
        s = F.col("date").cast("double")

        secs = (F.when(s.isNull(), F.lit(None).cast("double")).when(s > F.lit(1e12), s / F.lit(1000.0)).otherwise(s))

        dt_ts = F.to_timestamp(F.from_unixtime(secs))

        df = (df.withColumn("date_ts", dt_ts).withColumn("date", F.date_format(F.col("date_ts"), "dd/MM/yyyy"))
              .withColumn("time", F.date_format(F.col("date_ts"), "HH:mm")).drop("date_ts"))

    return df

# =====================================================================================================================================
# FUNCIÓN 5. AÑADIR FEATURES POR PARTIDO
# =====================================================================================================================================
def add_match_features(df: DataFrame) -> DataFrame:
    out = df

    # Flags básicos
    if "minutesplayed" in out.columns:  # tras normalize_columns => minutesplayed
        out = out.withColumn("minutesplayed", F.coalesce(F.col("minutesplayed").cast("double"), F.lit(0.0)))
        out = out.withColumn("played", F.col("minutesplayed") > 0)

        if "starter" in out.columns:
            out = out.withColumn("starter", F.col("starter").cast("boolean"))
            out = out.withColumn("start", (F.col("played") == True) & (F.col("starter") == True))
            out = out.withColumn("sub_appearance", (F.col("played") == True) & (F.col("starter") == False))
        else:
            out = out.withColumn("start", F.lit(False)).withColumn("sub_appearance", F.lit(False))

        out = out.withColumn("p90_factor", F.when(F.col("minutesplayed") > 0, F.lit(90.0) / F.col("minutesplayed")).otherwise(F.lit(None).cast("double")),)
    else:
        out = out.withColumn("minutesplayed", F.lit(0.0)).withColumn("played", F.lit(False)).withColumn("p90_factor", F.lit(None).cast("double"))

    def add_ratio(df0: DataFrame, num: str, den: str, outname: str) -> DataFrame:
        if (num in df0.columns) and (den in df0.columns):
            return df0.withColumn(outname, safe_div(F.col(num), F.col(den)))
        return df0

    # Pase
    out = add_ratio(out, "accuratepass", "totalpass", "pass_accuracy")
    out = add_ratio(out, "accuratelongballs", "totallongballs", "longball_accuracy")
    out = add_ratio(out, "totallongballs", "totalpass", "longballs_share_of_passes")
    out = add_ratio(out, "accuratecross", "totalcross", "cross_accuracy")
    out = add_ratio(out, "totalcross", "totalpass", "cross_share_of_passes")
    out = add_ratio(out, "accuratethroughballs", "totalthroughballs", "throughball_accuracy")
    out = add_ratio(out, "accuratechippedpass", "totalchippedpass", "chippedpass_accuracy")
    out = add_ratio(out, "accuratekeypass", "keypass", "keypass_accuracy")
    out = add_ratio(out, "keypass", "totalpass", "keypass_rate_per_pass")
    out = add_ratio(out, "bigchancecreated", "keypass", "bigchance_created_per_keypass")

    if "p90_factor" in out.columns:
        for c in ["totalpass","accuratepass","totallongballs","accuratelongballs","totalcross","accuratecross",
                  "keypass","bigchancecreated","totalthroughballs","accuratethroughballs"]:
            if c in out.columns:
                out = out.withColumn(f"{c}_per90", F.col(c).cast("double") * F.col("p90_factor"))

    # Tiro
    out = add_ratio(out, "shotsontarget", "totalshot", "shot_accuracy_on_target")
    out = add_ratio(out, "goals", "totalshot", "goal_conversion_per_shot")
    out = add_ratio(out, "goals", "shotsontarget", "goal_conversion_per_sot")
    if ("goals" in out.columns) and ("expectedgoals" in out.columns):
        out = out.withColumn("goals_minus_xg", F.col("goals").cast("double") - F.col("expectedgoals").cast("double"))
        out = out.withColumn("goals_over_xg", safe_div(F.col("goals"), F.col("expectedgoals")))
    out = add_ratio(out, "expectedgoals", "totalshot", "xg_per_shot")

    if ("goalassist" in out.columns) and ("expectedassists" in out.columns):
        out = out.withColumn("assists_minus_xa", F.col("goalassist").cast("double") - F.col("expectedassists").cast("double"))
        out = out.withColumn("assists_over_xa", safe_div(F.col("goalassist"), F.col("expectedassists")))

    if ("goals" in out.columns) and ("goalassist" in out.columns):
        out = out.withColumn("ga", F.col("goals").cast("double") + F.col("goalassist").cast("double"))

    if ("expectedgoals" in out.columns) and ("expectedassists" in out.columns):
        out = out.withColumn("xg_xa", F.col("expectedgoals").cast("double") + F.col("expectedassists").cast("double"))

    if "p90_factor" in out.columns:
        for c in ["goals","expectedgoals","goalassist","expectedassists","totalshot","shotsontarget","bigchancemissed"]:
            if c in out.columns:
                out = out.withColumn(f"{c}_per90", F.col(c).cast("double") * F.col("p90_factor"))

    # Dribblings
    out = add_ratio(out, "successfuldribbles", "totaldribble", "dribble_success_rate")
    out = add_ratio(out, "successfuldribbles", "totalpass", "dribbles_per_pass")
    out = add_ratio(out, "woncontest", "totalcontest", "contest_win_rate")

    if "p90_factor" in out.columns:
        for c in ["successfuldribbles","totaldribble","woncontest","totalcontest","dispossessed"]:
            if c in out.columns:
                out = out.withColumn(f"{c}_per90", F.col(c).cast("double") * F.col("p90_factor"))

    # Duelos
    out = add_ratio(out, "duelwon", "totalduels", "duel_win_rate")
    out = add_ratio(out, "groundduelswon", "groundduels", "ground_duel_win_rate")
    out = add_ratio(out, "aerialduelswon", "aerialduels", "aerial_duel_win_rate")
    out = add_ratio(out, "wasfouled", "fouls", "fouls_drawn_to_committed")

    if "p90_factor" in out.columns:
        for c in ["duelwon","totalduels","groundduelswon","groundduels","aerialduelswon","aerialduels","fouls","wasfouled"]:
            if c in out.columns:
                out = out.withColumn(f"{c}_per90", F.col(c).cast("double") * F.col("p90_factor"))

    # Defensa
    out = add_ratio(out, "tackleswon", "tackles", "tackle_success_rate")
    if ("challengewon" in out.columns) and ("challengelost" in out.columns):
        out = out.withColumn("challenge_total", F.col("challengewon").cast("double") + F.col("challengelost").cast("double"))
        out = out.withColumn("challenge_win_rate", safe_div(F.col("challengewon"), F.col("challenge_total")))

    def_cols = [c for c in ["tackleswon","interceptionwon","blockedshots","clearance","ballrecovery"] if c in out.columns]
    if def_cols:
        out = out.withColumn("def_actions", sum(F.coalesce(F.col(c).cast("double"), F.lit(0.0)) for c in def_cols))

    if "p90_factor" in out.columns:
        for c in ["tackles","tackleswon","interceptionwon","blockedshots","clearance","ballrecovery","errorleadtoshot","errorleadtogoal"]:
            if c in out.columns:
                out = out.withColumn(f"{c}_per90", F.col(c).cast("double") * F.col("p90_factor"))
        if "def_actions" in out.columns:
            out = out.withColumn("def_actions_per90", F.col("def_actions").cast("double") * F.col("p90_factor"))

    # Posesión
    out = add_ratio(out, "possessionlost", "touches", "possession_lost_per_touch")
    out = add_ratio(out, "dispossessed", "touches", "dispossessed_per_touch")
    out = add_ratio(out, "ballrecovery", "possessionlost", "recovery_to_loss_ratio")

    if "p90_factor" in out.columns:
        for c in ["touches","possessionlost","dispossessed"]:
            if c in out.columns:
                out = out.withColumn(f"{c}_per90", F.col(c).cast("double") * F.col("p90_factor"))

    # Disciplina (tarjetas)
    if ("yellowcards" in out.columns) and ("redcards" in out.columns):
        out = out.withColumn("cards", F.col("yellowcards").cast("double") + F.lit(2.0) * F.col("redcards").cast("double"))
    if "p90_factor" in out.columns:
        for c in ["yellowcards","redcards","cards"]:
            if c in out.columns:
                out = out.withColumn(f"{c}_per90", F.col(c).cast("double") * F.col("p90_factor"))

    # Estadisticas del portero
    out = add_ratio(out, "saves", "shotsontargetfaced", "gk_save_pct")
    out = add_ratio(out, "goalsconceded", "shotsontargetfaced", "gk_concede_per_sot")
    if ("goalsconceded" in out.columns) and ("postshotexpectedgoals" in out.columns):
        out = out.withColumn("gk_goalsconceded_minus_psxg", F.col("goalsconceded").cast("double") - F.col("postshotexpectedgoals").cast("double"))

    if "p90_factor" in out.columns:
        for c in ["saves","shotsontargetfaced","goalsconceded","postshotexpectedgoals"]:
            if c in out.columns:
                out = out.withColumn(f"{c}_per90", F.col(c).cast("double") * F.col("p90_factor"))

    # Varias
    if ("expectedgoals" in out.columns) and ("expectedassists" in out.columns):
        out = out.withColumn("attack_value_raw", F.col("expectedgoals").cast("double") + F.col("expectedassists").cast("double"))
        if "keypass" in out.columns:
            out = out.withColumn("attack_value_raw", F.col("attack_value_raw") + F.lit(0.05) * F.col("keypass").cast("double"))

    if ("progressivepasses" in out.columns) and ("progressivecarries" in out.columns):
        out = out.withColumn("progression_actions", F.col("progressivepasses").cast("double") + F.col("progressivecarries").cast("double"))
    elif "progressivepasses" in out.columns:
        out = out.withColumn("progression_actions", F.col("progressivepasses").cast("double"))
    elif "progressivecarries" in out.columns:
        out = out.withColumn("progression_actions", F.col("progressivecarries").cast("double"))

    if "p90_factor" in out.columns:
        for c in ["attack_value_raw","progression_actions","def_actions"]:
            if c in out.columns:
                out = out.withColumn(f"{c}_per90", F.col(c).cast("double") * F.col("p90_factor"))

    return out

# =====================================================================================================================================
# FUNCIÓN 6. RESUMEN DE TEMPORADA POR JUGADOR (CON Y SIN EQUIPO)
# =====================================================================================================================================
def players_season_summary(df_match_player: DataFrame, by_team: bool = True) -> DataFrame:
    df = df_match_player
    if df is None or len(df.columns) == 0:
        return df

    # Flags
    if "minutesplayed" in df.columns:
        df = df.withColumn("minutesplayed", F.coalesce(F.col("minutesplayed").cast("double"), F.lit(0.0)))
        df = df.withColumn("played", F.col("minutesplayed") > 0)
    else:
        df = df.withColumn("minutesplayed", F.lit(0.0)).withColumn("played", F.lit(False))

    if "starter" in df.columns:
        df = df.withColumn("starter", F.col("starter").cast("boolean"))
        df = df.withColumn("start", (F.col("played") == True) & (F.col("starter") == True))
    else:
        df = df.withColumn("start", F.lit(False))

    keys = ["league", "season", "player_slug"]
    if by_team and ("team_slug" in df.columns):
        keys.append("team_slug")

    match_id_col = "match" if "match" in df.columns else ("match_slug" if "match_slug" in df.columns else None)

    agg_exprs = [(F.countDistinct(F.col(match_id_col)).alias("matches") if match_id_col else F.lit(0).cast("long").alias("matches")),
                  F.sum(F.col("played").cast("int")).alias("matchesplayed"), F.sum(F.col("start").cast("int")).alias("starts"),
                  F.sum(F.col("minutesplayed")).alias("minutes")]

    numeric_cols = [f.name for f in df.schema.fields
                    if isinstance(f.dataType, (T.IntegerType, T.LongType, T.FloatType, T.DoubleType, T.ShortType, T.DecimalType))]
    exclude = {"minutesplayed", "match", "player_id", "team_id", "season_id", "league_id"}
    sum_cols = [c for c in numeric_cols if c not in exclude]

    for c in sum_cols:
        agg_exprs.append(F.sum(F.col(c).cast("double")).alias(c))

    out = df.groupBy(*keys).agg(*agg_exprs)

    def add_ratio_df(df0: DataFrame, num: str, den: str, outname: str) -> DataFrame:
        if (num in df0.columns) and (den in df0.columns):
            return df0.withColumn(outname, safe_div(F.col(num), F.col(den)))
        return df0

    # Ratios recalculados otra vez
    out = add_ratio_df(out, "accuratepass", "totalpass", "passaccuracy")
    out = add_ratio_df(out, "accuratelongballs", "totallongballs", "longballaccuracy")
    out = add_ratio_df(out, "accuratecross", "totalcross", "crossaccuracy")
    out = add_ratio_df(out, "successfuldribbles", "totaldribble", "dribblesuccessrate")
    out = add_ratio_df(out, "duelwon", "totalduels", "duelwinrate")
    out = add_ratio_df(out, "tackleswon", "tackles", "tacklesuccessrate")
    out = add_ratio_df(out, "shotsontarget", "totalshot", "shotontargetrate")
    out = add_ratio_df(out, "goals", "totalshot", "goalpershot")
    out = add_ratio_df(out, "goals", "shotsontarget", "goalpersot")
    out = add_ratio_df(out, "expectedgoals", "totalshot", "xgpershot")

    if ("goals" in out.columns) and ("expectedgoals" in out.columns):
        out = out.withColumn("goalsminusxg", F.col("goals").cast("double") - F.col("expectedgoals").cast("double"))
    if ("goalassist" in out.columns) and ("expectedassists" in out.columns):
        out = out.withColumn("assistsminusxa", F.col("goalassist").cast("double") - F.col("expectedassists").cast("double"))

    # Por 90
    out = out.withColumn("p90factor", F.when(F.col("minutes") > 0, F.lit(90.0) / F.col("minutes")).otherwise(F.lit(None).cast("double")))

    per90_candidates = ["goals","goalassist","expectedgoals","expectedassists","totalshot","shotsontarget","keypass","bigchancecreated",
                        "totalpass","accuratepass","totallongballs","accuratelongballs","successfuldribbles","totaldribble","duelwon",
                        "totalduels","tackleswon","tackles","interceptionwon","ballrecovery","clearance","blockedshots","possessionlost",
                        "touches","yellowcards","redcards"]
    for c in per90_candidates:
        if c in out.columns:
            out = out.withColumn(f"{c}_per90", F.col(c).cast("double") * F.col("p90factor"))

    # Índices
    if ("expectedgoals" in out.columns) and ("expectedassists" in out.columns):
        out = out.withColumn("attackindex", F.col("expectedgoals").cast("double") + F.col("expectedassists").cast("double"))
        if "keypass" in out.columns:
            out = out.withColumn("attackindex", F.col("attackindex") + F.lit(0.05) * F.col("keypass").cast("double"))

    def_cols = [c for c in ["tackleswon","interceptionwon","blockedshots","clearance","ballrecovery"] if c in out.columns]
    if def_cols:
        out = out.withColumn("defactions", sum(F.coalesce(F.col(c).cast("double"), F.lit(0.0)) for c in def_cols))
        out = out.withColumn("defactions_per90", F.col("defactions") * F.col("p90factor"))

    idx_parts = [c for c in ["attackindex", "defactions_per90"] if c in out.columns]
    if idx_parts:
        out = out.withColumn("overallindex_raw", sum(F.coalesce(F.col(c).cast("double"), F.lit(0.0)) for c in idx_parts))

    out = out.drop("p90factor")
    return out

# =====================================================================================================================================
# FUNCIÓN 7. LIMPIEZA DE PLAYERSTATS PARA UNA LIGA/TEMPORADA Y CREACIÓ DE RESUMENES Y FEATURES
# =====================================================================================================================================
def player_stats_cleaner(player_stats_df: DataFrame, league: str, season: str) -> Tuple[DataFrame, DataFrame, DataFrame]:
    league_df = filter_df(player_stats_df, league=league, season=season)

    if league_df is None or len(league_df.columns) == 0:
        empty = league_df
        return empty, empty, empty

    # Numericas
    numeric_cols = [f.name for f in league_df.schema.fields 
                    if isinstance(f.dataType, (T.IntegerType, T.LongType, T.FloatType, T.DoubleType, T.ShortType, T.DecimalType)) and ("match" not in f.name.lower())]

    # MAsccara de fila mayor a 0
    if numeric_cols:
        row_sum = sum(F.coalesce(F.col(c).cast("double"), F.lit(0.0)) for c in numeric_cols)
        league_df = league_df.withColumn("_row_sum", row_sum).filter(F.col("_row_sum") > 0).drop("_row_sum")

    # Tipos mínimos
    if "starter" in league_df.columns:
        league_df = league_df.withColumn("starter", F.col("starter").cast("boolean"))
    if "minutesplayed" in league_df.columns:
        league_df = league_df.withColumn("minutesplayed", F.coalesce(F.col("minutesplayed").cast("double"), F.lit(0.0)))

    # Fill nulls numéricas -> 0 (solo numéricas)
    if numeric_cols:
        league_df = league_df.fillna({c: 0 for c in numeric_cols})

    cleaned_league_df = add_match_features(league_df)
    players_season_summary_team = players_season_summary(cleaned_league_df, by_team=True)
    players_season_summary_no_team = players_season_summary(cleaned_league_df, by_team=False)

    return cleaned_league_df, players_season_summary_team, players_season_summary_no_team

# =====================================================================================================================================
# FUNCIÓN 8. CREACIÓN DEL PERCENTIL GROBAL POR GRUPOS DE MÉTRICAS
# =====================================================================================================================================
def overall_percentile_spark(df: DataFrame, metric_cols: List[str],invert_cols: List[str],player_col: str = "player_slug",out_col: str = "pct_group") -> DataFrame:
    existing = [c for c in metric_cols if c in df.columns]
    if not existing:
        return df.select(F.col(player_col)).dropDuplicates([player_col]).withColumn(out_col, F.lit(None).cast("double"))

    base = df.select([F.col(player_col)] + [F.col(c).cast("double").alias(c) for c in existing]).dropDuplicates([player_col])

    pct_cols = []
    out = base
    inv = set(invert_cols)

    for c in existing:
        w = Window.orderBy(F.col(c).asc_nulls_last())
        pct_name = f"__pct_{c}"
        out = out.withColumn(pct_name, F.percent_rank().over(w).cast("double"))
        if c in inv:
            out = out.withColumn(
                pct_name,
                F.when(F.col(pct_name).isNull(), F.lit(None).cast("double")).otherwise(F.lit(1.0) - F.col(pct_name)),
            )
        pct_cols.append(pct_name)

    # Media del valor sin tener en cuenta los nulos
    sum_expr = None
    cnt_expr = None
    for pc in pct_cols:
        v = F.col(pc)
        sum_expr = v if sum_expr is None else (sum_expr + F.coalesce(v, F.lit(0.0)))
        cnt_piece = F.when(v.isNotNull(), F.lit(1)).otherwise(F.lit(0))
        cnt_expr = cnt_piece if cnt_expr is None else (cnt_expr + cnt_piece)

    out = out.withColumn(out_col, F.when(cnt_expr > 0, sum_expr / cnt_expr.cast("double")).otherwise(F.lit(None).cast("double")))
    return out.select(F.col(player_col), F.col(out_col))

# =====================================================================================================================================
# FUNCIÓN 9. PERCENTILES POR POSICIÓN Y POR GRUPO
# =====================================================================================================================================
def compute_position_groups_spark(df: DataFrame, position: str, GROUPS: Dict) -> DataFrame:
    pos_df = df.filter(F.col("position") == position)
    outputs = []

    # Para cada grupo, obtenemos las métricas
    for group_name, cfg in GROUPS.items():
        outputs.append(overall_percentile_spark(pos_df, metric_cols=cfg.get("cols", []),invert_cols=cfg.get("invert", []),
                                                player_col="player_slug",out_col=f"pct_{group_name.lower()}"))

    if not outputs:
        return pos_df.select("player_slug").dropDuplicates(["player_slug"])

    res = outputs[0]
    for t in outputs[1:]:
        res = res.join(t, on="player_slug", how="outer")

    return res

# =====================================================================================================================================
# FUNCIONES DE LECTURA Y ESCRITURA DE DATOS. LECTURA DEL CSV Y ESCRITURA (distintas funciones)
# =====================================================================================================================================
def read_csv_spark(spark: SparkSession,path: str,sep: str = ";",encoding: str = "utf-8",) -> DataFrame:

    if not os.path.exists(path):
        return spark.createDataFrame([], schema=T.StructType([]))

    df = (spark.read.option("header", True).option("sep", sep).option("encoding", encoding).option("inferSchema", True).csv(path))
    return df

# Escribe CSV sin tener en cuenta Hadoop (daba errores)
def write_csv_single_no_hadoop(df: DataFrame, path: str, sep: str = ";", encoding: str = "utf-8") -> None:
    
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    cols = df.columns

    with open(path, "w", newline="", encoding=encoding) as f:
        w = csv.writer(f, delimiter=sep)
        w.writerow(cols)

        # iteración streaming (no toPandas)
        for row in df.select(*cols).toLocalIterator():
            w.writerow([row[c] for c in cols])

# Particiona con Hadoop
def write_csv_partitioned_no_hadoop(df, out_dir, sep=";", encoding="utf-8", max_parts=64):
    os.makedirs(out_dir, exist_ok=True)

    cols = df.columns
    df2 = df.coalesce(max_parts)

    def write_part(it):
        idx = TaskContext.get().partitionId()
        path = os.path.join(out_dir, f"part-{idx:05d}.csv")

        try:
            with open(path, "w", newline="", encoding=encoding) as f:
                w = csv.writer(f, delimiter=sep)
                w.writerow(cols)
                for row in it:
                    w.writerow([row[c] for c in cols])
        except Exception as e:
            raise RuntimeError(f"{path}: {repr(e)}") from e

    df2.select(*cols).rdd.foreachPartition(write_part)

# Crea distintas partes y las mezcla - evitar carga
def merge_parts_to_single(parts_dir: str,final_path: str,encoding: str = "utf-8",) -> None:

    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    part_files = sorted(
        f for f in os.listdir(parts_dir)
        if f.startswith("part-") and f.endswith(".csv")
    )

    first = True
    with open(final_path, "w", encoding=encoding, newline="") as fout:
        for pf in part_files:
            with open(os.path.join(parts_dir, pf), "r", encoding=encoding) as fin:
                for i, line in enumerate(fin):
                    if not first and i == 0:
                        continue
                    fout.write(line)
            first = False

# =====================================================================================================================================
# FUNCIÓN PRINCIPAL - PROCESADO DE LOS DATOS INICIALES SCRAPEADOS
# =====================================================================================================================================
def main_processing_spark(data_path: str) -> None:

    # Entorno de spark
    spark = (SparkSession.builder.appName("processing").config("spark.driver.memory", "8g").config("spark.executor.memory", "8g")
             .config("spark.memory.fraction", "0.6").config("spark.sql.shuffle.partitions", "64").config("spark.sql.adaptive.enabled", "true")
             .config("spark.sql.execution.arrow.pyspark.enabled", "false").config("spark.python.worker.faulthandler.enabled", "true")
             .config("spark.sql.execution.pyspark.udf.faulthandler.enabled", "true").getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")


    # Grupos de porcentiles por posición
    GK_GROUPS = {
        "ShotStopping": {"cols": ["GoalsMinusxG", "goalsPrevented", "saves_per90"], "invert": []},
        "Reliability": {"cols": ["errorLeadToAGoal", "errorLeadToAShot", "ownGoals"], "invert": ["errorLeadToAGoal", "errorLeadToAShot", "ownGoals"]},
        "AreaControl": {"cols": ["goodHighClaim", "punches", "crossNotClaimed"], "invert": ["crossNotClaimed"]},
        "SweeperKeeper": {"cols": ["totalKeeperSweeper", "accurateKeeperSweeper"], "invert": []},
        "BuildUpPlay": {"cols": ["pass_accuracy", "longball_accuracy"], "invert": []}}

    DF_GROUPS = {
        "DefensiveActions": {"cols": ["DefActions_per90", "interceptionWon_per90", "ballRecovery_per90"], "invert": []},
        "Duels": {"cols": ["duelWon_per90", "contest_win_rate"], "invert": []},
        "AerialAbility": {"cols": ["aerialWon", "aerialLost"], "invert": ["aerialLost"]},
        "BuildUpPlay": {"cols": ["pass_accuracy", "totalProgression", "progressiveBallCarriesCount"], "invert": []},
        "DefensiveReliability": {"cols": ["errorLeadToAGoal", "penaltyConceded", "fouls_per90"], "invert": ["errorLeadToAGoal", "penaltyConceded", "fouls_per90"]}}

    MF_GROUPS = {
        "BallDistribution": {"cols": ["pass_accuracy", "totalPass_per90", "passValueNormalized"], "invert": []},
        "Progression": {"cols": ["totalProgression", "progressiveBallCarriesCount", "bestBallCarryProgression"], "invert": []},
        "ChanceCreation": {"cols": ["keyPass_per90", "expectedAssists_per90", "bigChanceCreated_per90"], "invert": []},
        "DefensiveBalance": {"cols": ["DefActions_per90", "ballRecovery_per90"], "invert": []},
        "BallRetention": {"cols": ["dispossessed_per90", "possessionLostCtrl", "unsuccessfulTouch"], "invert": ["dispossessed_per90", "possessionLostCtrl", "unsuccessfulTouch"]}}

    FW_GROUPS = {
        "Finishing": {"cols": ["goals_per90", "expectedGoals_per90", "goals_over_xg", "shotValueNormalized", "bigChanceMissed_per90"], "invert": ["bigChanceMissed_per90"]},
        "ChanceCreation": {"cols": ["keyPass_per90", "expectedAssists_per90", "bigChanceCreated_per90", "assists_over_xa", "goalAssist_per90"], "invert": []},
        "Threat": {"cols": ["dribbleValueNormalized", "totalProgression", "progressiveBallCarriesCount", "attack_value_raw_per90", "totalShots"], "invert": []},
        "OffBallInvolvement": {"cols": ["touches_per90", "wasFouled_per90", "penaltyWon", "totalOffside", "ballCarriesCount"], "invert": []},
        "Efficiency": {"cols": ["dispossessed_per90", "possessionLostCtrl", "unsuccessfulTouch", "fouls_per90", "bigChanceMissed_per90"], "invert": ["dispossessed_per90", "possessionLostCtrl", "unsuccessfulTouch", "fouls_per90", "bigChanceMissed_per90"]}}

    # Lectura de los dataframes de scraping anteriores
    league_info_df = read_csv_spark(spark, f"{data_path}/raw/LeagueInfo.csv", sep=SEP)
    match_info_df  = read_csv_spark(spark, f"{data_path}/raw/MatchInfo.csv",  sep=SEP)
    player_info_df = read_csv_spark(spark, f"{data_path}/raw/PlayerInfo.csv", sep=SEP)
    player_stats_df= read_csv_spark(spark, f"{data_path}/raw/PlayerStats.csv",sep=SEP)

    # Normalización de las columnas con la función creada
    league_info_df  = normalize_columns(league_info_df)
    match_info_df   = normalize_columns(match_info_df)
    player_info_df  = normalize_columns(player_info_df)
    player_stats_df = normalize_columns(player_stats_df)

    # Cleaning de los dataframes básicos
    match_info_df_cleaned  = match_info_cleaner(match_info_df)
    player_info_df_cleaned = player_info_cleaner(player_info_df)

    # Guardado
    write_csv_single_no_hadoop(match_info_df_cleaned,  f"{data_path}/clean/MatchInfo.csv", sep=SEP)
    write_csv_single_no_hadoop(player_info_df_cleaned, f"{data_path}/clean/PlayerInfo.csv", sep=SEP)

    # Diccionario player_slug -> name
    player_name_df = (player_info_df_cleaned.select("player_slug", "name").dropna().dropDuplicates(["player_slug"]))

    # Procesamos por cada liga y cada temporada
    league_rows = league_info_df.select("league", "season").dropna().dropDuplicates().collect()

    # Listas de dataframes vacías que vamos a ir procesando
    cleaned_league_list: List[DataFrame] = []
    summ_team_list: List[DataFrame] = []
    summ_no_team_list: List[DataFrame] = []

    for r in league_rows:
        sel_league = r["league"]
        sel_season = r["season"]

        cleaned_league_df, summ_team_df, summ_no_team_df = player_stats_cleaner(player_stats_df, sel_league, sel_season)

        players_season_pos = (player_info_df_cleaned.filter((F.col("league") == sel_league) & (F.col("season") == sel_season))
                              .select("player_slug", "position").dropDuplicates(["player_slug"]))

        summ_team_df = summ_team_df.join(players_season_pos, on="player_slug", how="left")
        summ_no_team_df = summ_no_team_df.join(players_season_pos, on="player_slug", how="left")

        cleaned_league_list.append(cleaned_league_df)
        summ_team_list.append(summ_team_df)
        summ_no_team_list.append(summ_no_team_df)

    def union_all(dfs: List[DataFrame]) -> DataFrame:
        if not dfs:
            return spark.createDataFrame([], schema=T.StructType([]))
        out = dfs[0]
        for d in dfs[1:]:
            out = out.unionByName(d, allowMissingColumns=True)
        return out

    # Unimos usando la función interna creada
    cleaned_league_all = union_all(cleaned_league_list).dropDuplicates(["league","season","player_slug","match"])
    player_summ_no_team_all = union_all(summ_no_team_list).dropDuplicates(["league","season","player_slug"])
    player_summ_team_all = union_all(summ_team_list).dropDuplicates(["league","season","player_slug","team_slug"])

    # Añadimos nombre del jugador con el diccionario creado
    cleaned_league_all = cleaned_league_all.join(player_name_df, on="player_slug", how="left").withColumnRenamed("name", "player_name")
    player_summ_team_all = player_summ_team_all.join(player_name_df, on="player_slug", how="left").withColumnRenamed("name", "player_name")
    player_summ_no_team_all = player_summ_no_team_all.join(player_name_df, on="player_slug", how="left").withColumnRenamed("name", "player_name")

    # Creación de la carpeta con distintas partes
    tmp_dir = f"{data_path}/clean/_tmp_parts"

    # Guardamos por partes y posteriormente juntamos
    write_csv_partitioned_no_hadoop(cleaned_league_all, out_dir=f"{tmp_dir}/PlayerStats", sep=SEP, encoding=ENCODING, max_parts=32)
    merge_parts_to_single(parts_dir=f"{tmp_dir}/PlayerStats", final_path=f"{data_path}/clean/PlayerStats.csv", encoding=ENCODING)

    write_csv_partitioned_no_hadoop(player_summ_team_all, out_dir=f"{tmp_dir}/PlayerTeamStatsSummary", sep=SEP, encoding=ENCODING, max_parts=32)
    merge_parts_to_single(parts_dir=f"{tmp_dir}/PlayerTeamStatsSummary", final_path=f"{data_path}/clean/PlayerTeamStatsSummary.csv", encoding=ENCODING)

    write_csv_partitioned_no_hadoop(player_summ_no_team_all,out_dir=f"{tmp_dir}/PlayerStatsSummary", sep=SEP, encoding=ENCODING, max_parts=32)
    merge_parts_to_single(parts_dir=f"{tmp_dir}/PlayerStatsSummary", final_path=f"{data_path}/clean/PlayerStatsSummary.csv",encoding=ENCODING)
    
    # Creación de porcentiles por temporada
    seasons = [r["season"] for r in league_info_df.select("season").dropna().dropDuplicates().collect()]

    gk_list: List[DataFrame] = []
    df_list: List[DataFrame] = []
    mf_list: List[DataFrame] = []
    fw_list: List[DataFrame] = []

    # Para cada temporada computamos los porcentiles
    for sel_season in seasons:
        df_to_process = player_summ_no_team_all.filter(F.col("season") == sel_season)

        gk_pct = compute_position_groups_spark(df_to_process, "G", GK_GROUPS).withColumn("season", F.lit(sel_season))
        df_pct = compute_position_groups_spark(df_to_process, "D", DF_GROUPS).withColumn("season", F.lit(sel_season))
        mf_pct = compute_position_groups_spark(df_to_process, "M", MF_GROUPS).withColumn("season", F.lit(sel_season))
        fw_pct = compute_position_groups_spark(df_to_process, "F", FW_GROUPS).withColumn("season", F.lit(sel_season))

        gk_list.append(gk_pct)
        df_list.append(df_pct)
        mf_list.append(mf_pct)
        fw_list.append(fw_pct)

    # Unión
    goalkeeper_percentiles_df = union_all(gk_list).dropDuplicates().orderBy("season", "player_slug")
    defender_percentiles_df   = union_all(df_list).dropDuplicates().orderBy("season", "player_slug")
    midfielder_percentiles_df = union_all(mf_list).dropDuplicates().orderBy("season", "player_slug")
    forward_percentiles_df    = union_all(fw_list).dropDuplicates().orderBy("season", "player_slug")

    # Añadimos player_name
    goalkeeper_percentiles_df = goalkeeper_percentiles_df.join(player_name_df, on="player_slug", how="left").withColumnRenamed("name", "player_name")
    defender_percentiles_df   = defender_percentiles_df.join(player_name_df, on="player_slug", how="left").withColumnRenamed("name", "player_name")
    midfielder_percentiles_df = midfielder_percentiles_df.join(player_name_df, on="player_slug", how="left").withColumnRenamed("name", "player_name")
    forward_percentiles_df    = forward_percentiles_df.join(player_name_df, on="player_slug", how="left").withColumnRenamed("name", "player_name")

    # Guardados percentiles igual que antes
    write_csv_partitioned_no_hadoop(goalkeeper_percentiles_df, f"{tmp_dir}/GoalkeeperPercentile", sep=SEP, encoding=ENCODING, max_parts=16)
    merge_parts_to_single(f"{tmp_dir}/GoalkeeperPercentile", f"{data_path}/clean/GoalkeeperPercentile.csv", encoding=ENCODING)

    write_csv_partitioned_no_hadoop(defender_percentiles_df, f"{tmp_dir}/DefenderPercentile", sep=SEP, encoding=ENCODING, max_parts=16)
    merge_parts_to_single(f"{tmp_dir}/DefenderPercentile", f"{data_path}/clean/DefenderPercentile.csv", encoding=ENCODING)

    write_csv_partitioned_no_hadoop(midfielder_percentiles_df, f"{tmp_dir}/MidfielderPercentile", sep=SEP, encoding=ENCODING, max_parts=16)
    merge_parts_to_single(f"{tmp_dir}/MidfielderPercentile", f"{data_path}/clean/MidfielderPercentile.csv", encoding=ENCODING)

    write_csv_partitioned_no_hadoop(forward_percentiles_df, f"{tmp_dir}/ForwardPercentile", sep=SEP, encoding=ENCODING, max_parts=16)
    merge_parts_to_single(f"{tmp_dir}/ForwardPercentile", f"{data_path}/clean/ForwardPercentile.csv", encoding=ENCODING)

    # PAramos la función
    spark.stop()

# if __name__ == "__main__":
#     main_processing_spark(data_path="G:\\FootballData\\data")
