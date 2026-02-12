from code.scraping import main_scraping
from code.processing_pandas import main_processing_pandas
from code.processing_pyspark import main_processing_spark
# from code.visualizations import main_visualizations
# from code.report import main_report

# Función principal
def main(DATA_PATH: str, TYPE_PROC: str)

    # 1. SCRAPING DE LOS DATOS
    main_scraping(data_path=DATA_PATH)

    # 2. PROCESADO DE LOS DATOS (SEGÚN SPARK O PANDAS)
    if TYPE_PROC == "Pandas":
        main_processing_pandas(data_path=DATA_PATH)
    else:
        main_processing_spark(data_path=DATA_PATH)

    # 3. CREACIÓN DE LAS VISUALIZACIONES

    # 4. CREACIÓN DEL REPORT

# Definición de 
DATA_PATH = "G:\\FootballData\\data"

# Tipo de procesado Pandas/Pyspark
TYPE_PROC = "Pandas"
