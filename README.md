# **FLUJO DE ANÁLISIS DE DATOS EN PYTHON**

Este proyecto se basa en la creación de un flujo completo en Python para el análisis de datos de jugadores de fútbol. Este tiene la siguiente estructura:

1. Extracción de datos de la página web de datos deportivos 'Sofascore' mediante *scraping*; usando librerías como Pandas o Selenium. Los datos extraídos conforman las estadísticas en los partidos jugados de la temporada 2022/23 a la actual de las cinco grandes ligas europeas, junto con la información general de los jugadores.
2. Procesado de los datos limpiando los obtenidos anteriormente o adquiriendo nuevas métricas. Esta parte se ha realizado tanto con PySpark como con Pandas.
3. Creación de funciones que de forma automatizada creen visualizaciones de los jugadores o equipos de los cuales se quiere realizar un *report*. 
4. Creación de un *report* automatizado que nos aporte información sobre la liga, temporada, equipo o jugador. 