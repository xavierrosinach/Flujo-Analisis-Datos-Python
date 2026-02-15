import pandas as pd
import os
import markdown
from tabulate import tabulate
from datetime import datetime
import json

# CSS + HTML
def apply_style(html: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
<style>

body {{
    font-family: 'Roboto', sans-serif;
    background-color: #f7f9fc;
    margin: 40px;
    color: #333;
}}

h1 {{
    color:#1f3a5f;
    text-align:center;
    margin-bottom:20px;
}}

h2 {{
    color:#2f5d9a;
    margin-top:25px;
}}

h3 {{
    color:#355f8a;
}}

h4 {{
    color:#1f3a5f;
    text-align:center;
}}

table {{
    border-collapse: collapse;
    width: 70%;
    margin: 20px auto;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    background:white;
}}

th, td {{
    border: 1px solid #ddd;
    padding: 12px 15px;
    text-align: center;
}}

th {{
    background-color:#4da3ff;
    color:white;
    font-weight:700;
}}

tr:nth-child(even) {{
    background-color:#f2f6fb;
}}

img {{
    display: block;
    margin-left: auto;
    margin-right: auto;
    width: 50%;
}}

.img-grid-2x1 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-top: 20px;
    width: 100%; 
}}

.img-grid-2x1 img {{
    width: 100%;
    border-radius: 8px;
    box-shadow: 0 3px 8px rgba(0,0,0,0.12);
}}

.img-grid-2x2plus1 {{
    display: grid;
    grid-template-columns: repeat(2,1fr);
    gap:20px;
    margin-top:20px;
}}

.img-grid-2x2plus1 img {{
    width:100%;
    border-radius:8px;
    box-shadow:0 3px 8px rgba(0,0,0,0.12);
}}

.img-single-center {{
    display:flex;
    justify-content:center;
    margin-top:20px;
}}

.img-single-center img {{
    width:50%;
    border-radius:8px;
    box-shadow:0 3px 8px rgba(0,0,0,0.12);
}}

footer {{
    margin-top:40px;
    text-align:center;
    font-size:0.9em;
    color:#555;
}}

footer a {{
    text-decoration:none;
    font-weight:bold;
}}

</style>
</head>
<body>

{html}

<footer>
<b>Xavier Rosinach Capell</b><br>
<i>Sports Data Scientist and Engineer</i><br><br>
<a href="https://github.com/xavierrosinach" target="_blank" style="color:#333; margin-right:15px;">GitHub</a>
<a href="https://www.linkedin.com/in/xavierrosinach/" target="_blank" style="color:#0077b5;">LinkedIn</a><br><br>
<span style="font-size:0.8em; color:#999;">&copy; {datetime.now().year} Xavier Rosinach Capell. Todos los derechos reservados.</span>
</footer>

</body>
</html>
"""

# Tabla markdown
def add_df(df_path: str):
    if os.path.exists(df_path):
        df = pd.read_csv(df_path, sep=';')
        return tabulate(df, headers='keys', tablefmt='github', showindex=False)
    return ""

# ===========================================================================================================================================
# FUNCIÓN 1 - CREACIÓN DEL REPORT DE UNA TEMPORADA
# ===========================================================================================================================================
def season_report_creator(all_figures_path: str, season: str, all_reports_path: str):

    season_tag = season.replace("/", "")
    figures_path = os.path.join(all_figures_path, season_tag, 'seasons')
    reports_path = os.path.join(all_reports_path, season_tag, 'seasons')
    os.makedirs(reports_path, exist_ok=True)

    def img(p: str) -> str:
        return os.path.relpath(p, reports_path).replace("\\","/")

    parts = []

    # CABECERA
    parts.append(f"# *REPORT* DE LA TEMPORADA {season}")
    parts.append("#### Comparación de estadísticas entre ligas")
    parts.append("---")

    leagues_csv = os.path.join(figures_path, f"LeagueMetrics{season_tag}.csv")
    parts.append("## 1. Estadísticas generales")
    parts.append("")
    parts.append(add_df(leagues_csv))
    parts.append("")
    parts.append("---")

    # GRUPO 1 (2 arriba + 1 abajo centrada)
    src1 = img(os.path.join(figures_path, f"LeaguesAttackingThreadComparison{season_tag}.png"))
    src2 = img(os.path.join(figures_path, f"LeaguesPhysicalityMap{season_tag}.png"))
    src3 = img(os.path.join(figures_path, f"LeaguesTacticalStyle{season_tag}.png"))

    # parts.append("---")
    parts.append("## 2. Estadísticas medias por jugador según cada liga")
    parts.append("")
    parts.append(f"""
<div class="img-grid-2x2plus1">
<img src="{src1}">
<img src="{src2}">
</div>

<div class="img-single-center">
<img src="{src3}">
</div>
""".strip())
    parts.append("---")

    # RADARS (2x2)
    src4 = img(os.path.join(figures_path, f"LeaguesGoalkeeperRadarChart{season_tag}.png"))
    src5 = img(os.path.join(figures_path, f"LeaguesDefenderRadarChart{season_tag}.png"))
    src6 = img(os.path.join(figures_path, f"LeaguesMidfielderRadarChart{season_tag}.png"))
    src7 = img(os.path.join(figures_path, f"LeaguesForwardRadarChart{season_tag}.png"))

    parts.append("## 3. Comparación de perfiles medios por posición")
    parts.append("")
    parts.append(f"""
<div class="img-grid-2x2plus1">
<img src="{src4}">
<img src="{src5}">
<img src="{src6}">
<img src="{src7}">
</div>
""".strip())
    parts.append("---")

    # FUNCIÓN PARA BLOQUES DE 5 IMÁGENES
    def render_group(paths):
        s = [img(p) for p in paths]
        return f"""
<div class="img-grid-2x2plus1">
<img src="{s[0]}">
<img src="{s[1]}">
<img src="{s[2]}">
<img src="{s[3]}">
</div>

<div class="img-single-center">
<img src="{s[4]}">
</div>
""".strip()

    parts.append("## 4. Distribución de percentiles de los jugadores según posición")
    parts.append("")
    parts.append("### 4.1. Porteros")
    parts.append(render_group([
        os.path.join(figures_path,f"LeaguesGKShotStoppingViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesGKReliabilityViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesGKAreaControlViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesGKSweeperKeeperViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesGKBuildUpPlayViolinChart{season_tag}.png")]))

    parts.append("### 4.2. Defensas")
    parts.append(render_group([
        os.path.join(figures_path,f"LeaguesDFDefensiveActionsViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesDFDuelsViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesDFAerialAbilityViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesDFBuildUpPlayViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesDFDefensiveReliabilityViolinChart{season_tag}.png")]))

    parts.append("### 4.3. Centrocampistas")
    parts.append(render_group([
        os.path.join(figures_path,f"LeaguesMDBallDistributionViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesMDProgressionViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesMDChanceCreationViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesMDDefensiveBalanceViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesMDBallRetentionViolinChart{season_tag}.png")]))

    parts.append("### 4.4. Delanteros")
    parts.append(render_group([
        os.path.join(figures_path,f"LeaguesFWFinishingViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesFWChanceCreationViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesFWThreatViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesFWOffBallInvolvementViolinChart{season_tag}.png"),
        os.path.join(figures_path,f"LeaguesFWEfficiencyViolinChart{season_tag}.png")]))
    parts.append("---")

    markdown_content = "\n".join(parts)

    md_file = os.path.join(reports_path, f"SeasonReport{season_tag}.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    html_content = markdown.markdown(markdown_content, extensions=["tables", "extra"])

    html_file = os.path.join(reports_path, f"SeasonReport{season_tag}.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(apply_style(html_content, f"Report Temporada {season}"))

    # Borrar fichero y carpeta
    os.remove(md_file)

# ===========================================================================================================================================
# FUNCIÓN 2 - CREACIÓN DEL REPORT DE UNA LIGA
# ===========================================================================================================================================
def league_report_creator(all_figures_path: str, season: str, league: str, all_reports_path: str):

    season_tag = season.replace("/", "")
    league_tag = league.replace(' ','')
    figures_path = os.path.join(all_figures_path, season_tag, 'leagues')
    reports_path = os.path.join(all_reports_path, season_tag, 'leagues')
    os.makedirs(reports_path, exist_ok=True)

    def img(p: str) -> str:
        return os.path.relpath(p, reports_path).replace("\\","/")

    parts = []

    # CABECERA
    parts.append(f"# *REPORT* DE LA LIGA {league.upper()} EN LA TEMPORADA {season}")
    parts.append("#### Comparación de estadísticas entre equipos y jugadores")
    parts.append("---")

    standing_table = os.path.join(figures_path, f"IndicesTable{league_tag}{season_tag}.csv")
    parts.append("## 1. Tabla de clasificación")
    parts.append("")
    parts.append(add_df(standing_table))
    parts.append("")
    parts.append("---")

    # GRUPO 1 - mejores jugadores por posición
    best_gk = os.path.join(figures_path, f"GoalkeeperRanking{league_tag}{season_tag}.csv")
    best_df = os.path.join(figures_path, f"DefenderRanking{league_tag}{season_tag}.csv")
    best_md = os.path.join(figures_path, f"MidfielderRanking{league_tag}{season_tag}.csv")
    best_fw = os.path.join(figures_path, f"ForwardRanking{league_tag}{season_tag}.csv")
    parts.append("## 2. Mejores jugadores por posición")
    parts.append("")
    parts.append("### 2.1. Porteros")
    parts.append(add_df(best_gk))
    parts.append("")
    parts.append("### 2.2. Defensas")
    parts.append(add_df(best_df))
    parts.append("")
    parts.append("### 2.3. Centrocampistas")
    parts.append(add_df(best_md))
    parts.append("")
    parts.append("### 2.4. Delanteros")
    parts.append(add_df(best_fw))
    parts.append("")
    parts.append("---")

    # GRUPO 2 - metricas por equipo
    src1 = img(os.path.join(figures_path, f"AttackDefenseTeams{league_tag}{season_tag}.png"))
    src2 = img(os.path.join(figures_path, f"AttackProgressionTeams{league_tag}{season_tag}.png"))
    src3 = img(os.path.join(figures_path, f"DefenseProgressionTeams{league_tag}{season_tag}.png"))

    # parts.append("---")
    parts.append("## 3. Comparación de métricas avanzadas por equipo")
    parts.append("")
    parts.append(f"""
<div class="img-grid-2x2plus1">
<img src="{src1}">
<img src="{src2}">
</div>

<div class="img-single-center">
<img src="{src3}">
</div>
""".strip())
    parts.append("---")

    # COMPARACIÓN DE GOLES CON GOLES ESPERADOS
    src4 = img(os.path.join(figures_path, f"GoalsVsExpectedGoals{league_tag}{season_tag}.png"))
    src5 = img(os.path.join(figures_path, f"AgainstGoalsVsExpectedGoals{league_tag}{season_tag}.png"))

    parts.append("## 4. Comparación de goles con goles esperados")
    parts.append("")
    parts.append(f"""
<div class="img-grid-2x1">
<img src="{src4}">
<img src="{src5}">
</div>
""".strip())
    parts.append("---")
        
    markdown_content = "\n".join(parts)

    md_file = os.path.join(reports_path, f"LeagueReport{league_tag}{season_tag}.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    html_content = markdown.markdown(markdown_content, extensions=["tables", "extra"])

    html_file = os.path.join(reports_path, f"LeagueReport{league_tag}{season_tag}.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(apply_style(html_content, f"Report Liga {league} Temporada {season}"))

    # Borrar fichero y carpeta
    os.remove(md_file)

# ===========================================================================================================================================
# FUNCIÓN 3 - CREACIÓN DEL REPORT DE UN JUGADOR
# ===========================================================================================================================================
def player_report_creator(all_figures_path: str, season: str, player: str, all_reports_path: str):

    season_tag = season.replace("/", "")
    player_tag = player.replace(' ','')
    figures_path = os.path.join(all_figures_path, season_tag, 'players')
    reports_path = os.path.join(all_reports_path, season_tag, 'players')
    os.makedirs(reports_path, exist_ok=True)

    def img(p: str) -> str:
        return os.path.relpath(p, reports_path).replace("\\","/")

    parts = []

    # CABECERA
    parts.append(f"# *REPORT* DE {player.upper()} EN LA TEMPORADA {season}")
    parts.append("#### Obtención de metricas principales y comparación con otros jugadores")
    parts.append("---")

    info_and_metrics = os.path.join(figures_path, f"InfoMetrics{player_tag}{season_tag}.json")
    with open(info_and_metrics, "r", encoding="utf-8") as f:
        player_info_and_metrics = json.load(f)
    info = player_info_and_metrics['INFO']
    metrics = player_info_and_metrics['METRICS']
    parts.append("## 1. Información general")
    parts.append("")
    
    for i in info:
        parts.append(f"- **{i}**: {info[i]}")
        parts.append("")
    parts.append("---")

    parts.append("## 2. Estadísticas principales (según posición)")
    parts.append("")
    
    for m in metrics:
        parts.append(f"- **{m}**: {metrics[m]}")
        parts.append("")
    parts.append("---")


    # COMPARACIÓN DE GOLES CON GOLES ESPERADOS
    src1 = img(os.path.join(figures_path, f"Fig1{player_tag}{season_tag}.png"))
    src2 = img(os.path.join(figures_path, f"Fig2{player_tag}{season_tag}.png"))

    parts.append("## 3. Comparación con otros jugadores de su misma posición")
    parts.append("")
    parts.append(f"""
<div class="img-grid-2x1">
<img src="{src1}">
<img src="{src2}">
</div>
""".strip())
    parts.append("---")

    # COMPARACIÓN CON OTRAS TEMPORADAS
    src3 = img(os.path.join(figures_path, f"PlayerRadarChart{player_tag}.png"))
    parts.append("## 4. Rendimiento del jugador según las temporadas")
    parts.append("")
    parts.append(f"""
<div class="img-single-center">
<img src="{src3}">
</div>
""".strip())
    parts.append("---")
        
    markdown_content = "\n".join(parts)

    md_file = os.path.join(reports_path, f"PlayerReport{player_tag}{season_tag}.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    html_content = markdown.markdown(markdown_content, extensions=["tables", "extra"])

    html_file = os.path.join(reports_path, f"PlayerReport{player_tag}{season_tag}.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(apply_style(html_content, f"Report Jugador {player} Temporada {season}"))

    # Borrar fichero y carpeta
    os.remove(md_file)