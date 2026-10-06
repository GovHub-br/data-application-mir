import http
import logging
from typing import Any
from cliente_base import ClienteBase


class ClienteTed(ClienteBase):
    BASE_URL = "https://api.transferegov.gestao.gov.br/ted/"
    BASE_HEADER = {"accept": "application/json"}

    def __init__(self) -> None:
        super().__init__(base_url=ClienteTed.BASE_URL)

    def get_ted_by_programa_beneficiario(self, tx_codigo_siorg: str) -> list | None:

        endpoint = f"programa_beneficiario?tx_codigo_siorg=eq.{tx_codigo_siorg}"
        logging.info(
            f"[cliente_ted.py] Fetching ted for programa beneficiario: {tx_codigo_siorg}"
        )
        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )
        if status == http.HTTPStatus.OK and isinstance(data, list):
            logging.info(
                "[cliente_ted.py] Successfully fetched ted for programa beneficiario: "
                f"{tx_codigo_siorg}"
            )
            return data
        else:
            logging.warning(
                "[cliente_ted.py] Failed to fetch ted for programa beneficiario: "
                f"{tx_codigo_siorg} with status: {status}"
            )
            return None

    def get_programa_by_id_programa(self, id_programa: str) -> list | None:

        endpoint = f"programa?id_programa=eq.{id_programa}"
        logging.info(f"[cliente_ted.py] Fetching programa for id_programa: {id_programa}")
        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )
        if status == http.HTTPStatus.OK and isinstance(data, list):
            logging.info(
                "[cliente_ted.py] Successfully fetched programa for id_programa: "
                f"{id_programa}"
            )
            return data
        else:
            logging.warning(
                "[cliente_ted.py] Failed to fetch programa for id_programa: "
                f"{id_programa} with status: {status}"
            )
            return None

    def get_planos_acao_by_id_programa(self, id_programa: str) -> list | None:

        endpoint = f"plano_acao?id_programa=eq.{id_programa}"
        logging.info(
            f"[cliente_ted.py] Fetching planos de ação for id_programa: {id_programa}"
        )
        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )
        if status == http.HTTPStatus.OK and isinstance(data, list):
            logging.info(
                "[cliente_ted.py] Successfully fetched planos de ação for id_programa: "
                f"{id_programa}"
            )
            return data
        else:
            logging.warning(
                "[cliente_ted.py] Failed to fetch planos de ação for id_programa: "
                f"{id_programa} with status: {status}"
            )
            return None

    def get_programas_by_sigla_unidade_descentralizadora(self, sigla: str) -> list | None:
        endpoint = f"programa?sigla_unidade_descentralizadora=eq.{sigla}"
        logging.info(f"Fetching programas for sigla_unidade_descentralizadora: {sigla}")
        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )
        if status == http.HTTPStatus.OK and isinstance(data, list):
            logging.info(
                f"Successfully fetched programas for sigla_unidade_descentralizadora: "
                f"{sigla}"
            )
            return data
        else:
            logging.warning(
                f"Failed to fetch programas for sigla_unidade_descentralizadora: "
                f"{sigla} with status: {status}"
            )
            return None

    def get_notas_de_credito_by_id_plano_acao(self, id_plano_acao: int) -> list | None:
        endpoint = f"nota_credito?id_plano_acao=eq.{id_plano_acao}"

        logging.info(f"Buscando notas de crédito pelo plano de ação: {id_plano_acao}")

        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )

        if status == http.HTTPStatus.OK and isinstance(data, list):
            logging.info(f"Notas de crédito obtidas para plano de ação {id_plano_acao}")
            return data
        else:
            logging.warning(f"Falha ao buscar notas de crédito - Status: {status}")
            return None

    def get_programacao_financeira_by_id_plano_acao(
        self, id_plano_acao: int
    ) -> list | None:
        endpoint = f"programacao_financeira?id_plano_acao=eq.{id_plano_acao}"

        logging.info(
            f"Buscando programação financeira pelo plano de ação: {id_plano_acao}"
        )

        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )

        if status == http.HTTPStatus.OK and isinstance(data, list):
            logging.info(
                f"Programação financeira obtidas para plano de ação {id_plano_acao}"
            )
            return data
        else:
            logging.warning(f"Falha ao buscar programação financeira - Status: {status}")
            return None

    def get_todos_programas(self, limit: int = 1000, offset: int = 0) -> list | None:
        """
        Função ATÔMICA: Busca uma única 'fatia' (página) de programas.
        """
        headers = {
            **self.BASE_HEADER, 
            "Range-Unit": "items", 
            "Range": f"{offset}-{offset + limit - 1}"
        }
        
        endpoint = "programa"
        logging.info(f"[cliente_ted.py] Fetching programas (offset: {offset}, limit: {limit})")
        
        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=headers
        )
        
        if status == http.HTTPStatus.OK and isinstance(data, list):
            logging.info(f"[cliente_ted.py] Sucesso ao buscar {len(data)} programas no offset {offset}.")
            return data
        else:
            logging.error(f"[cliente_ted.py] Erro ao buscar programas. Status: {status}")
            return None

    def get_all_programas(self, limit: int = 1000) -> list:
        """
        Itera por todas as fatias de dados até o fim.
        Segue a lógica da 'get_all_deputados'.
        """
        all_programas = []
        current_offset = 0

        while True:
            programas = self.get_todos_programas(limit=limit, offset=current_offset)

            if not programas:
                break

            all_programas.extend(programas)

            if len(programas) < limit:
                logging.info("[cliente_ted.py] Última página alcançada.")
                break

            current_offset += limit

        logging.info(f"[cliente_ted.py] Carga completa finalizada. Total: {len(all_programas)} programas.")
        return all_programas

def _separar_unidade(rotulo: str | None) -> tuple[str | None, str | None, str | None]:
    """Separa o rótulo do portal ("426 - UFRJ - Universidade ...") em id, sigla e nome."""
    if not rotulo:
        return None, None, None
    partes = [p.strip() for p in rotulo.split(" - ", 2)]
    while len(partes) < 3:
        partes.append(None)
    return partes[0], partes[1], partes[2]


def _texto(valor: Any) -> str | None:
    """Grava números e booleanos como texto, como na tabela da API de dados abertos."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, float):
        return f"{valor:.2f}"
    return str(valor)


def plano_acao_portal_para_registro(plano: dict) -> dict:
    """
    Converte um plano de ação do portal do sistema TED para os nomes de coluna da
    API de dados abertos (transfere_gov.planos_acao), mais os campos que só o
    portal tem (UG das unidades, unidade descentralizadora, termo assinado).
    """
    _, sigla_desc, nome_desc = _separar_unidade(plano.get("unidadeDescentralizadaF"))
    _, sigla_exec, nome_exec = _separar_unidade(plano.get("unidadeResponsavelExecucaoF"))
    id_descentralizadora, sigla_descentralizadora, _ = _separar_unidade(
        plano.get("unidadeDescentralizadoraF")
    )
    _, sigla_acomp, nome_acomp = _separar_unidade(
        plano.get("unidadeResponsavelAcompanhamentoF")
    )
    return {
        "id_plano_acao": _texto(plano.get("id")),
        "id_programa": _texto(plano.get("programaFk")),
        "codigo_plano_acao": _texto(plano.get("codigo")),
        "versao_plano_acao": _texto(plano.get("versao")),
        "sigla_unidade_descentralizada": sigla_desc,
        "unidade_descentralizada": nome_desc,
        "cd_ug_unidade_descentralizada": _texto(
            plano.get("cdUnidadeDescentralizadaGestora")
        ),
        "sigla_unidade_responsavel_execucao": sigla_exec,
        "unidade_responsavel_execucao": nome_exec,
        "cd_ug_unidade_responsavel_execucao": _texto(
            plano.get("cdUnidadeResponsavelExecucaoGestora")
        ),
        "id_unidade_descentralizadora": id_descentralizadora,
        "sigla_unidade_descentralizadora": sigla_descentralizadora,
        "sigla_unidade_responsavel_acompanhamento": sigla_acomp,
        "unidade_responsavel_acompanhamento": nome_acomp,
        "vl_total_plano_acao": _texto(plano.get("vlTotal")),
        "vl_beneficiario_especifico": _texto(plano.get("vlBeneficiarioEspecifico")),
        "vl_chamamento_publico": _texto(plano.get("vlChamamentoPublico")),
        "dt_inicio_vigencia": _texto(plano.get("dtInicioVigencia")),
        "dt_fim_vigencia": _texto(plano.get("dtFimVigencia")),
        "tx_objeto_plano_acao": plano.get("txObjeto"),
        "tx_justificativa_plano_acao": plano.get("txJustificativa"),
        "in_forma_execucao_direta": _texto(plano.get("inFormaExecucaoDireta")),
        "in_forma_execucao_particulares": _texto(
            plano.get("inFormaExecucaoParticulares")
        ),
        "in_forma_execucao_descentralizada": _texto(
            plano.get("inFormaExecucaoDescentralizada")
        ),
        "tx_situacao_plano_acao": plano.get("txSituacao"),
        "aa_ano_plano_acao": _texto(plano.get("aaAno")),
        "sq_instrumento": plano.get("sequencialInstrumento"),
        "aa_instrumento": _texto(plano.get("anoInstrumento")),
        "in_termo_execucao_assinado": _texto(plano.get("hasTermoExecucaoAssinado")),
    }


class ClienteTedPortal(ClienteBase):
    """
    API pública do portal do sistema TED (ted.transferegov.sistema.gov.br), a mesma
    usada pela consulta de planos de ação. Fica à frente da API de dados abertos:
    situação e número do instrumento aparecem aqui antes.
    """

    BASE_URL = "https://ted.transferegov.sistema.gov.br/ted-backend/api/public/"
    BASE_HEADER = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}

    def __init__(self) -> None:
        super().__init__(base_url=ClienteTedPortal.BASE_URL)

    def get_planos_acao_by_unidade_descentralizadora(
        self, id_unidade_descentralizadora: str
    ) -> list | None:
        """
        Busca todos os planos de ação de uma unidade descentralizadora (ex.: MIR =
        308823). Hoje o portal devolve tudo na página 0, mas o laço segue as
        páginas enquanto vierem dados e não se alcançar o total informado.
        """
        planos: list = []
        pagina = 0
        while True:
            endpoint = (
                "planos-acao?unidadeDescentralizadoraFk="
                f"{id_unidade_descentralizadora}&page={pagina}"
            )
            status, data = self.request(
                http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
            )
            if status != http.HTTPStatus.OK or not isinstance(data, dict):
                logging.warning(
                    f"[cliente_ted.py] Falha ao buscar planos de ação no portal "
                    f"(página {pagina}) - Status: {status}"
                )
                return None
            itens = data.get("data") or []
            planos.extend(item["planoAcao"] for item in itens if item.get("planoAcao"))
            total = data.get("count") or 0
            if not itens or len(planos) >= total:
                break
            pagina += 1

        logging.info(
            f"[cliente_ted.py] {len(planos)} planos de ação obtidos no portal para a "
            f"unidade {id_unidade_descentralizadora}"
        )
        return planos
