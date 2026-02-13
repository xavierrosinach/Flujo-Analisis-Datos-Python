# ANÀLISIS GLOBAL DE TEMPORADA - Comparació de les cinc lligues

Ens centrem en el perfil táctic de cda lliga.
* Quines lligues generen més volum ofensiu?
* Quines lligues són més físiques / defensives?
* Quines lligues progressen més la pilota?
* Quina identitat tántica mitja té cada lliga.

### 1. League Offensive Tempo

Mesura quant atac produeix cada lliga independentment del resultat.

Utilitzem expected_goals, attack_value, bigChancesCreated, shots (x90) -> no utilitzem gols perque depenen d'eficàcia

LeagueAttackTempo = sum(mean(variables esmentades))

1. Mostrem el rànquing de més a menys
2. Creem una gráfica (scatterplot) -> x (xg90), y (shots90), size (g90)

### 2. Defensive & Phisical Identity
