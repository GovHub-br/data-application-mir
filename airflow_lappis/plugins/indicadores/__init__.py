"""Indicadores de monitoramento do MIR.

Cada módulo porta um script entregue pela equipe de BI como funções puras
(``list[dict] -> list[dict]``), sem I/O. A leitura do Postgres e a gravação
dos resultados ficam a cargo dos DAGs em ``dags/indicadores``.
"""
