"""Indicador I7 — Completude e Qualidade dos Dados.

Porte de ``i7_completude.py`` (equipe de BI, idêntico nas pastas TED e
Convênios). Função pura — a lógica de completude é a do script original;
a origem dos dados muda de forma mais profunda que nos outros indicadores.

DECISÃO DE ARQUITETURA (alinhada com a usuária antes de implementar, já que
a issue #497 deixou isso em aberto — não é um porte mecânico como o I1/I2):

 1. "Arquivo-fonte" (pasta do OneDrive: TEDs/Convênios/Emendas) virou tabela
    BRONZE do dbt: ``siafi_dbt.*`` (de ``empenhos_ted_dbt/bronze``),
    ``siconv_dbt.*`` (de ``siconv_dbt/bronze``), ``emendas.*`` (de
    ``emendas_dbt/bronze``). Evidência: a BI registrou "Convênios (16
    arquivos)" no script original — ``siconv_dbt/bronze`` tem exatamente 16
    models.
 2. O campo ``data_extracao`` (tirado do timestamp no nome do arquivo CSV)
    foi REMOVIDO. Não existe equivalente confiável no pipeline: a tabela
    ``metadata.models_metadata`` teria o dado (``dt_transform`` por
    schema+tabela), mas o post-hook que a preenche
    (``register_model_metadata()``) não está configurado no
    ``dbt_project.yml`` para os models de TED/Convênios/Emendas — ou seja,
    hoje ela não é confiável para essas tabelas.

CORRIGIDO RODANDO CONTRA O POSTGRES REAL (não previsto na leitura do código):
 a. Três models de ``empenhos_ted_dbt/bronze`` têm ``alias`` customizado no
    dbt (config ``alias="..._mir"``): o nome da tabela no Postgres não é o
    nome do arquivo ``.sql``. Afeta ``pf_ptres`` -> ``pf_ptres_mir``,
    ``pf_tesouro`` -> ``pf_tesouro_mir``, ``pf_transfere`` ->
    ``pf_transfere_mir``. Os outros ~38 models bronze das três pastas não
    têm alias. A DAG usa os nomes reais.
 b. Algumas bronzes de Convênios têm milhões de linhas (ex.:
    ``cronograma_desembolso`` = 2,7M, ``meta_crono_fisico`` = 1,5M) — bem
    maiores que os CSVs que a BI processava. Ler todas as bronzes e só
    depois processar (acumular tudo em memória antes de calcular) estourou
    a memória do worker do Airflow (SIGKILL). Por isso a lógica foi
    separada em ``completude_tabela`` (processa uma tabela, chamada pela
    DAG logo após o fetch, descartando as linhas em seguida) e
    ``consolidar_i7`` (só enxerga os resultados já agregados, pequenos).
    ``calcular_i7`` continua existindo para teste com volume pequeno, mas a
    DAG não a usa.

AVISO DE VALIDAÇÃO: ao contrário do I1/I2, os números deste módulo NÃO são
comparáveis por regressão aos CSVs que a BI publicou em `Resultados/`
(``i7_completude_*_ted.csv``, ``i7_completude_*_convenios.csv``) — aquele
resultado foi calculado sobre um export específico do OneDrive, com nomes de
coluna e cardinalidade diferentes das tabelas bronze do dbt. A lógica
(critério de ausência, faixas, heurística) foi portada byte a byte e é
testada com dados sintéticos; os números absolutos só saem certos quando a
DAG roda contra o Postgres real.

DEFINIÇÃO (inalterada — a fórmula e as faixas já batiam com a ficha):
    Completude (%) = (células preenchidas / células totais) × 100, por
    coluna e por tabela. Faixas: OK <10% ausente, ATENÇÃO 10-50%,
    CRÍTICO >50%.

CRITÉRIO DE "AUSENTE":
    Uma célula é considerada ausente quando está vazia/só espaços, ou
    contém um marcador de ausência dos sistemas de origem: "SEM
    INFORMACAO", "SEM INFORMAÇÃO", "-8", "-9" (códigos SIAFI). Zeros e
    "NAO"/"SIM" são PREENCHIDOS.

DECISÃO HERDADA DO SCRIPT ORIGINAL — heurística de tipo de ausência:
    "dado_faltante" x "estrutural_suspeita" é HEURÍSTICA, NÃO CLASSIFICAÇÃO
    CURADA (coluna 100% ausente -> "estrutural_suspeita"; ausência parcial
    -> "dado_faltante"). É sugestão de triagem, não verdade validada — só a
    equipe de domínio pode dirimir isso caso a caso.
"""

from typing import Any

MARCADORES_AUSENCIA = {"", "SEM INFORMACAO", "SEM INFORMAÇÃO", "-8", "-9"}


def _txt(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def _esta_ausente(valor: Any) -> bool:
    return _txt(valor).upper() in MARCADORES_AUSENCIA


def completude_tabela(
    pasta: str, nome_tabela: str, linhas: list[dict]
) -> tuple[list[dict], dict | None]:
    """Completude de uma tabela: uma linha por coluna + um resumo da tabela.

    Retorna ``(linhas_colunas, linha_tabela)``. ``linha_tabela`` é ``None``
    quando a tabela está vazia (nada a reportar).
    """
    if not linhas:
        return [], None

    colunas = list(linhas[0].keys())
    n_registros = len(linhas)
    ausentes_por_col = {col: 0 for col in colunas}
    for linha in linhas:
        for col in colunas:
            if _esta_ausente(linha.get(col)):
                ausentes_por_col[col] += 1

    linhas_colunas = []
    for col in colunas:
        ausentes = ausentes_por_col[col]
        pct = ausentes / n_registros * 100

        if pct == 0:
            tipo_sugerido = "completo"
        elif pct >= 99.95:
            tipo_sugerido = "estrutural_suspeita"
        else:
            tipo_sugerido = "dado_faltante"

        linhas_colunas.append({
            "pasta": pasta,
            "arquivo": nome_tabela,
            "coluna": col,
            "n_registros": n_registros,
            "n_ausentes": ausentes,
            "pct_ausente": round(pct, 1),
            "pct_preenchido": round(100 - pct, 1),
            "faixa": "OK" if pct < 10 else ("ATENCAO" if pct <= 50 else "CRITICO"),
            "tipo_ausencia_sugerido": tipo_sugerido,
        })

    celulas_total = n_registros * len(colunas)
    celulas_ausentes = sum(ausentes_por_col.values())
    pct_arquivo = celulas_ausentes / celulas_total * 100 if celulas_total else 0.0

    linha_tabela = {
        "pasta": pasta,
        "arquivo": nome_tabela,
        "n_registros": n_registros,
        "n_colunas": len(colunas),
        "pct_celulas_ausentes": round(pct_arquivo, 1),
        "n_colunas_criticas": sum(
            1 for c in colunas if ausentes_por_col[c] / n_registros > 0.5
        ),
        "n_colunas_estruturais_suspeitas": sum(
            1 for c in colunas if ausentes_por_col[c] / n_registros >= 0.9995
        ),
    }
    return linhas_colunas, linha_tabela


def consolidar_i7(
    linhas_colunas: list[dict], linhas_tabelas: list[dict]
) -> dict[str, list[dict]]:
    """Monta as seis saídas do I7 a partir dos resultados já agregados.

    Separado de ``completude_tabela`` de propósito: esta função só enxerga
    o resultado agregado (algumas linhas por tabela), não as linhas brutas
    (que podem ser milhões). A DAG chama ``completude_tabela`` uma tabela
    bronze por vez e descarta as linhas brutas antes de ler a próxima —
    ver aviso de memória no docstring do módulo.
    """
    linhas_colunas = sorted(
        linhas_colunas,
        key=lambda x: (-x["pct_ausente"], x["pasta"], x["arquivo"], x["coluna"]),
    )

    return {
        "i7_completude_colunas": linhas_colunas,
        "i7_completude_arquivos": linhas_tabelas,
        "i7_completude_colunas_ted": [l for l in linhas_colunas if l["pasta"] == "TEDs"],
        "i7_completude_arquivos_ted": [l for l in linhas_tabelas if l["pasta"] == "TEDs"],
        "i7_completude_colunas_convenios": [
            l for l in linhas_colunas if l["pasta"] == "Convênios"
        ],
        "i7_completude_arquivos_convenios": [
            l for l in linhas_tabelas if l["pasta"] == "Convênios"
        ],
    }


def calcular_i7(tabelas: dict[str, dict[str, list[dict]]]) -> dict[str, list[dict]]:
    """Calcula as seis saídas do I7 a partir das tabelas bronze já em memória.

    ``tabelas`` é ``{pasta: {nome_tabela: linhas}}`` — ex.:
    ``{"TEDs": {"planos_acao_ted": [...], ...}, "Convênios": {...}, ...}``.

    Conveniente para teste (volume pequeno). A DAG NÃO usa esta função —
    ela chamaria ``fetch_table`` de todas as bronzes antes de processar
    qualquer uma, o que estourou a memória do worker contra o Postgres real
    (algumas bronzes de Convênios têm milhões de linhas). A DAG usa
    ``completude_tabela`` + ``consolidar_i7`` diretamente, tabela por vez.
    """
    linhas_colunas: list[dict] = []
    linhas_tabelas: list[dict] = []

    for pasta, tabelas_pasta in tabelas.items():
        for nome_tabela in sorted(tabelas_pasta):
            cols, resumo = completude_tabela(
                pasta, nome_tabela, tabelas_pasta[nome_tabela]
            )
            if resumo is None:
                continue
            linhas_colunas.extend(cols)
            linhas_tabelas.append(resumo)

    return consolidar_i7(linhas_colunas, linhas_tabelas)
