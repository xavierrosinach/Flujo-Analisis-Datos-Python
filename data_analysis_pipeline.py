from code.scraping import main_scraping
from code.processing_pandas import main_processing_pandas
from code.processing_pyspark import main_processing_spark
# from code.visualizations import main_visualizations
# from code.report import main_report

# Librerías para el scraping - debemos hacer la creación del driver aqui
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Función principal
def main(DRIVER, DATA_PATH: str, TYPE_PROC: str, SCRAPING: bool = True, PROCESSING: bool = True, VISUALIZATION: bool = True):

    # 1. SCRAPING DE LOS DATOS
    if SCRAPING:
        main_scraping(driver=DRIVER, data_path=DATA_PATH)

    # 2. PROCESADO DE LOS DATOS (SEGÚN SPARK O PANDAS)
    if PROCESSING:
        if TYPE_PROC == "Pandas":
            main_processing_pandas(data_path=DATA_PATH)
        else:
            main_processing_spark(data_path=DATA_PATH)

    # 3. CREACIÓN DE LAS VISUALIZACIONES

    # 4. CREACIÓN DEL REPORT

if __name__ == "__main__":

    # Creación de un driver general para todo el código
    # options = webdriver.ChromeOptions()
    # options.add_argument("--headless=new")

    # # Servicio con chrome driver
    # service = Service(ChromeDriverManager().install())
    # driver = webdriver.Chrome(service=service, options=options)

    main(DRIVER=None, DATA_PATH="G:\\FootballData\\data", TYPE_PROC="Pandas", SCRAPING=False)
