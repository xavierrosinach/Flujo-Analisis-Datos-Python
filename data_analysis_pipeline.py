from code.scraping import main_scraping
from code.processing_pandas import main_processing_pandas
from code.processing_pyspark import main_processing_spark
from code.visualizations import create_season_visualizations, create_league_visualizations, create_player_visualizations
from code.report import season_report_creator, league_report_creator, player_report_creator

# Librerías para el scraping - debemos hacer la creación del driver aqui
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Función principal
def main_scraping_processing(DRIVER, DATA_PATH: str,  TYPE_PROC: str, SCRAPING: bool = True, PROCESSING: bool = True):

    # 1. SCRAPING DE LOS DATOS
    if SCRAPING:
        main_scraping(driver=DRIVER, data_path=DATA_PATH)

    # 2. PROCESADO DE LOS DATOS (SEGÚN SPARK O PANDAS)
    if PROCESSING:
        if TYPE_PROC == "Pandas":
            main_processing_pandas(data_path=DATA_PATH)
        else:
            main_processing_spark(data_path=DATA_PATH)

if __name__ == "__main__":

    SCRAPING = False
    PROCESSING = False

    if SCRAPING:
        # Creación de un driver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver=None

    # Aplicamos procesado y scraping
    main_scraping_processing(DRIVER=None, DATA_PATH="data_example", TYPE_PROC="Pandas", SCRAPING=False)

    # EJEMPLOS - creación de visualizaciones y de reports para una temporada, una liga, y un jugador
    # Los datos scrapeados y procesados no se van a encontrar a la carpeta de datos de ejemplo por memoria
    
    # TEMPORADA
    create_season_visualizations(data_path="data_example", season='25/26')
    season_report_creator(all_figures_path="data_example/images", season='25/26', all_reports_path="data_example/reports")
    
    # LIGA 
    create_league_visualizations(data_path="data_example", season='25/26', league='Premier League')
    league_report_creator(all_figures_path="data_example/images", season='25/26', league='Premier League', all_reports_path="data_example/reports")

    # JUGADOR
    create_player_visualizations(data_path="data_example", season='25/26', player_slug='ferran-torres')
    player_report_creator(all_figures_path="data_example/images", season='25/26', player='Ferran Torres', all_reports_path="data_example/reports")