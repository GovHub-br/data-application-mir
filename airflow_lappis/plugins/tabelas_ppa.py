"""Configuração das tabelas do PPA/SIOP para a ingestão unificada.

Modelo de unificação (issue #477):

- Os dados abertos do PPA 2024-2027 são publicados em 3 ``.zip`` (2024 original,
  revisões 2025 e 2026). Os zips são **cumulativos** (o de 2026 traz também os
  arquivos ``_2024``/``_2025``) e os nomes de arquivo **variam entre revisões**
  (acentos removidos, renomeações, abreviações e até um typo em 2026).
- Cada zip contribui apenas os CSVs do **seu próprio ano** (2024 -> ``_2024``,
  2025 -> ``_2025``, 2026 -> ``_2026``); a coluna ``ano_ppa`` recebe o ano do zip.
  Assim cada entidade vira **uma única** tabela raw (sem sufixo de ano), empilhando
  as três revisões.
- ``arquivos`` mapeia ``ano -> basename`` do CSV (sem o sufixo ``_{ano}.csv``, que o
  ``ClientePPA`` reconstrói). Anos ausentes para uma tabela são simplesmente omitidos.
- A idempotência é garantida por um surrogate ``id_hash`` (md5 das colunas de
  negócio + ``ano_ppa``, gerado no ``ClientePPA``); por isso a chave de conflito é
  uniforme: ``["id_hash", "ano_ppa"]``.

Tabelas presentes apenas a partir de 2025 e **fora do escopo** da issue #477
(não ingeridas aqui): ``Indicador_Entrega_-_Meta_ODS``,
``Indicador_Obj_Espec_-_Meta_ODS`` e ``Planos_Regionais_Desenvolvimento_-_Entrega``
(``Plano_Reg_Desenv_-_Entrega`` em 2026).
"""

# Chave de conflito/upsert uniforme: id_hash já embute ano_ppa; a coluna de ano
# é mantida explícita para deixar a dimensão de revisão evidente no índice único.
CONFLICT_FIELDS = ["id_hash", "ano_ppa"]


def _tabela(nome_tabela: str, arquivos: dict) -> dict:
    return {
        "nome_tabela": nome_tabela,
        "arquivos": arquivos,
        "conflict_fields": CONFLICT_FIELDS,
        "primary_key": CONFLICT_FIELDS,
        "skip_rows": 0,
    }


TABELAS_PPA = [
    # ------------------------------------------------------------------ #
    # Base PPA
    # ------------------------------------------------------------------ #
    _tabela(
        "acao_nao_orcamentaria",
        {
            2024: "Ação_Não-Orçamentária",
            2025: "Ação_Não-Orçamentária",
            2026: "Ação_Orçamentária",  # renomeado em 2026 (mesma entidade)
        },
    ),
    _tabela("programa", {2024: "Programa", 2025: "Programa", 2026: "Programa"}),
    _tabela(
        "objetivo_geral",
        {2024: "Objetivo_Geral", 2025: "Objetivo_Geral", 2026: "Objetivo_Geral"},
    ),
    _tabela(
        "objetivo_especifico",
        {
            2024: "Objetivo_Específico",
            2025: "Objetivo_Específico",
            2026: "Objetivo_Específico",
        },
    ),
    _tabela(
        "objetivo_estrategico_programa",
        {
            2024: "Objetivo_Estratégico_-_Programa",
            2025: "Objetivo_Estratégico_-_Programa",
            2026: "Objetivos_Estratégicos-Programa",
        },
    ),
    _tabela(
        "meta_objetivo_especifico",
        {
            2024: "Meta_Objetivo_Específico",
            2025: "Meta_Objetivo_Específico",
            2026: "Meta_Objetivo_Específico",
        },
    ),
    _tabela("entrega", {2024: "Entrega", 2025: "Entrega", 2026: "Entrega"}),
    _tabela(
        "meta_entrega",
        {2024: "Meta_Entrega", 2025: "Meta_Entrega", 2026: "Meta_Entrega"},
    ),
    _tabela(
        "indicador_objetivo_especifico",
        {
            2024: "Indicador_Objetivo_Específico",
            2025: "Indicador_Objetivo_Específico",
            2026: "Indicador_Objetivo_Específico",
        },
    ),
    _tabela(
        "indicador_entrega",
        {
            2024: "Indicador_Entrega",
            2025: "Indicador_Entrega",
            2026: "Indicador_Entrega",
        },
    ),
    _tabela(
        "desagregacao_meta_objetivo_especifico",
        {
            2024: "Desagregação_Meta_Objetivo_Específico",
            2025: "Desagregação_Meta_Objetivo_Específico",
            2026: "Desagregacao_Meta_Objet_Espec",
        },
    ),
    _tabela(
        "desagregacao_meta_entrega",
        {
            2024: "Desagregação_Meta_Entrega",
            2025: "Desagregação_Meta_Entrega",
            2026: "Desagregacao_Meta_Entrega",
        },
    ),
    _tabela(
        "regionalizacao_meta_objetivo_especifico",
        {
            2024: "Regionalização_Meta_Objetivo_Específico",
            2025: "Regionalização_Meta_Objetivo_Específico",
            2026: "Regionalizacao_Meta_Objet_Espec",
        },
    ),
    _tabela(
        "regionalizacao_meta_entrega",
        {
            2024: "Regionalização_Meta_Entrega",
            2025: "Regionalização_Meta_Entrega",
            2026: "Regionalizacao_Meta_da_Entrega",
        },
    ),
    _tabela(
        "medida_institucional_objetivo_especifico",
        {
            2024: "Medida_Institucional_Objetivo_Específico",
            2025: "Medida_Institucional_Objetivo_Específico",
            2026: "Medida_Inst_Norm_Obj_Específico",
        },
    ),
    _tabela(
        "medida_institucional_programa",
        {
            2024: "Medida_Institucional_Programa",
            2025: "Medida_Institucional_Programa",
            2026: "Medida_Inst_Norm_Programa",
        },
    ),
    # ------------------------------------------------------------------ #
    # Agendas transversais
    # ------------------------------------------------------------------ #
    _tabela("agenda", {2024: "Agenda", 2025: "Agenda", 2026: "Agenda"}),
    _tabela(
        "agenda_programa",
        {
            2024: "Agenda - Programa",
            2025: "Agenda - Programa",
            2026: "Agenda - Programa",
        },
    ),
    _tabela(
        "agenda_objetivo_geral",
        {
            2024: "Agenda - Objetivo Geral",
            2025: "Agenda - Objetivo Geral",
            2026: "Agenda - Objetivo Geral",
        },
    ),
    _tabela(
        "agenda_objetivo_especifico",
        {
            2024: "Agenda - Objetivo Específico",
            2025: "Agenda - Objetivo Específico",
            2026: "Agenda - Objetivo Específico",
        },
    ),
    _tabela(
        "agenda_entrega",
        {
            2024: "Agenda - Entrega",
            2025: "Agenda - Entrega",
            2026: "Agenda - Entrega",
        },
    ),
    _tabela(
        "agenda_meta_entrega",
        {
            2024: "Agenda - Meta Entrega",
            2025: "Agenda - Meta Entrega",
            2026: "Agenda - Meta Entrega",
        },
    ),
    _tabela(
        "agenda_meta_objetivo_especifico",
        {
            2024: "Agenda - Meta Objetivo Específico",
            2025: "Agenda - Meta Objetivo Específico",
            2026: "Agenda - Meta Objetivo Específico",
        },
    ),
    _tabela(
        "agenda_indicador_entrega",
        {
            2024: "Agenda - Indicador Entrega",
            2025: "Agenda - Indicador Entrega",
            2026: "Agenda - Indicador Entrega",
        },
    ),
    _tabela(
        "agenda_indicador_objetivo_especifico",
        {
            2024: "Agenda - Indicador Objetivo Específico",
            2025: "Agenda - Indicador Objetivo Específico",
            2026: "Agenda - Indicador Objetivo Específico",
        },
    ),
    _tabela(
        "agenda_desagregacao_meta_entrega",
        {
            2024: "Agenda - Desagregação Meta Entrega",
            2025: "Agenda - Desagregação Meta Entrega",
            2026: "Agenda - Desagregacao Meta Entrega",
        },
    ),
    _tabela(
        "agenda_desagregacao_meta_objetivo_especifico",
        {
            2024: "Agenda - Desagregação Meta Objetivo Específico",
            2025: "Agenda - Desagregação Meta Objetivo Específico",
            2026: "Agenda - Desagregacao Meta Objet Espec",
        },
    ),
    _tabela(
        "agenda_regionalizacao_meta_entrega",
        {
            2024: "Agenda - Regionalização Meta Entrega",
            2025: "Agenda - Regionalização Meta Entrega",
            2026: "Agenda - Regionalizacao Meta da Entrega",
        },
    ),
    _tabela(
        "agenda_regionalizacao_meta_objetivo_especifico",
        {
            2024: "Agenda - Regionalização Meta Objetivo Específico",
            2025: "Agenda - Regionalização Meta Objetivo Específico",
            2026: "Agenda - Regionalizacao Meta Objet Espec",
        },
    ),
    _tabela(
        "agenda_medida_institucional_objetivo_especifico",
        {
            2024: "Agenda - Medida Institucional - Objetivo Específico",
            2025: "Agenda - Medida Institucional - Objetivo Específico",
            # typo presente no zip de 2026 ("Específicoífico"):
            2026: "Agenda - Medida Inst Norm Objetivo Específicoífico",
        },
    ),
    _tabela(
        "agenda_medida_institucional_programa",
        {
            2024: "Agenda - Medida Institucional - Programa",
            2025: "Agenda - Medida Institucional - Programa",
            2026: "Agenda - Medida Inst Norm Programa",
        },
    ),
]
