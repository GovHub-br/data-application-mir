"""Testes de cobertura e sanidade dos joins MIR da DAG i7_completude.

Importa apenas os dicts de configuração do módulo da DAG, sem instanciar
o DAG em si (o que exigiria Airflow e conexões).
"""

import sys
import types
from unittest.mock import MagicMock

import pytest


def _carregar_dag_module():
    """Carrega i7_completude_dag substituindo imports que precisam do Airflow."""
    import importlib.util, os

    stubs = {
        "airflow": MagicMock(),
        "airflow.decorators": MagicMock(),
        "airflow.models": MagicMock(),
        "cliente_postgres": MagicMock(),
        "postgres_helpers": MagicMock(),
        "schedule_loader": MagicMock(),
        "indicadores": types.ModuleType("indicadores"),
        "indicadores.i7_completude": MagicMock(),
    }
    saved = {name: sys.modules.get(name) for name in stubs}
    for name, stub in stubs.items():
        sys.modules[name] = stub
    try:
        path = os.path.join(
            os.path.dirname(__file__),
            "../../airflow_lappis/dags/indicadores/mir/i7_completude_dag.py",
        )
        spec = importlib.util.spec_from_file_location("i7_completude_dag", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


_dag = _carregar_dag_module()
FONTES = _dag.FONTES
SICONV_MIR_JOINS = _dag.SICONV_MIR_JOINS


def test_todas_as_tabelas_siconv_tem_join() -> None:
    tabelas_siconv = set(FONTES["Convênios"][1])
    assert tabelas_siconv == set(SICONV_MIR_JOINS.keys())


def test_join_usa_cod_orgao_sup_67000() -> None:
    for tabela, (join_sql, mir_cond) in SICONV_MIR_JOINS.items():
        assert "67000" in mir_cond, f"{tabela}: esperado cod_orgao_sup = 67000"


def test_proposta_tem_condicao_direta_sem_join() -> None:
    join_sql, mir_cond = SICONV_MIR_JOINS["proposta"]
    assert join_sql == ""
    assert "cod_orgao_sup" in mir_cond


def test_convenio_join_via_id_proposta() -> None:
    join_sql, mir_cond = SICONV_MIR_JOINS["convenio"]
    assert "id_proposta" in join_sql
    assert "proposta" in join_sql


@pytest.mark.parametrize("tabela", [
    "cronograma_desembolso", "meta_crono_fisico", "historico_situacao",
])
def test_tabelas_com_id_proposta_usam_join_direto(tabela: str) -> None:
    join_sql, _ = SICONV_MIR_JOINS[tabela]
    assert "id_proposta" in join_sql
    assert "nr_convenio" not in join_sql


@pytest.mark.parametrize("tabela", [
    "empenho", "desbloqueio", "pagamento", "desembolso", "licitacao",
])
def test_tabelas_sem_id_proposta_usam_join_via_nr_convenio(tabela: str) -> None:
    join_sql, _ = SICONV_MIR_JOINS[tabela]
    assert "nr_convenio" in join_sql
    assert "proposta" in join_sql


def test_teds_e_emendas_nao_estao_no_siconv_mir_joins() -> None:
    tabelas_ted = set(FONTES["TEDs"][1])
    tabelas_emendas = set(FONTES["Emendas"][1])
    assert not tabelas_ted & set(SICONV_MIR_JOINS.keys())
    assert not tabelas_emendas & set(SICONV_MIR_JOINS.keys())
