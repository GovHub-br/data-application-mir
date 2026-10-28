"""
Testes de ClienteBase.request projetados por técnica (PTOSS-2).

Cada teste traz no nome/docstring o ID usado no relatório (CP = caixa-preta,
CB = caixa-branca). Usa httpx.MockTransport para que raise_for_status() e
json() tenham o comportamento REAL do httpx (sem mockar a resposta).
"""

from http import HTTPStatus
import logging

import httpx
import pytest

from cliente_base import ClienteBase


# ---------------------------------------------------------------- utilidades
def _cliente(handler) -> ClienteBase:
    """ClienteBase cujo transporte é substituído por um handler em memória."""
    cliente = ClienteBase(base_url="https://api.exemplo.gov.br")
    cliente.client = httpx.Client(
        base_url="https://api.exemplo.gov.br",
        transport=httpx.MockTransport(handler),
    )
    return cliente


def _sequencia(*respostas):
    """Handler que devolve (ou lança) os itens em ordem, repetindo o último."""
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        item = respostas[min(len(chamadas) - 1, len(respostas) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    handler.chamadas = chamadas
    return handler


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    """Elimina o backoff real e registra os tempos pedidos."""
    pedidos = []
    monkeypatch.setattr("cliente_base.time.sleep", lambda s: pedidos.append(s))
    return pedidos


# ======================================================================
# ABORDAGEM 1: CAIXA-PRETA (especificação = docstring) -> complemento CB
# ======================================================================


# ---- CP1: Particionamento de equivalência + valor limite do status HTTP
# Classes: [200..299] sucesso | [300..399] redirecionamento | [400..499]
# erro do cliente | [500..599] erro do servidor.
# Limites testados: 299/300, 399/400, 499/500, 599 e 200.
@pytest.mark.parametrize("status", [200, 201, 299])
def test_CP1_status_2xx_retorna_status_e_json(status):
    handler = _sequencia(httpx.Response(status, json={"ok": True}))
    st, dados = _cliente(handler).request("GET", "/x")
    assert st == status
    assert dados == {"ok": True}
    assert len(handler.chamadas) == 1


@pytest.mark.parametrize("status", [300, 399, 408, 429, 500, 503, 599])
def test_CP1_status_fora_de_2xx_esgota_tentativas(status):
    handler = _sequencia(httpx.Response(status, json={}))
    with pytest.raises(Exception, match="maximum number of attempts"):
        _cliente(handler).request("GET", "/x")
    assert len(handler.chamadas) == ClienteBase.DEFAULT_MAX_RETRIES + 1


# ---- CP2: Particionamento do corpo da resposta de sucesso
@pytest.mark.parametrize("corpo", [{"a": 1}, [1, 2], [], {}])
def test_CP2_corpo_json_valido_e_devolvido(corpo):
    handler = _sequencia(httpx.Response(200, json=corpo))
    _, dados = _cliente(handler).request("GET", "/x")
    assert dados == corpo


# ---- CP3: Particionamento do parâmetro timeout
@pytest.mark.parametrize(
    "kwargs, esperado",
    [
        ({}, ClienteBase.DEFAULT_TIMEOUT),  # não informado -> padrão
        ({"timeout": 30}, 30),  # informado -> preservado
        ({"timeout": 0.001}, 0.001),  # limite inferior positivo
    ],
)
def test_CP3_timeout(kwargs, esperado):
    vistos = []

    def handler(request):
        vistos.append(request.extensions["timeout"]["read"])
        return httpx.Response(200, json={})

    _cliente(handler).request("GET", "/x", **kwargs)
    assert vistos == [esperado]


# ---- CP4: Valor limite do número de tentativas (MAX_RETRIES + 1 = 4)
def test_CP4_sucesso_na_ultima_tentativa_permitida(sem_espera):
    """3 falhas + sucesso na 4ª tentativa (limite exato) -> sucesso."""
    handler = _sequencia(*[httpx.Response(500)] * 3, httpx.Response(200, json=[1]))
    st, dados = _cliente(handler).request("GET", "/x")
    assert (st, dados) == (HTTPStatus.OK, [1])
    assert len(handler.chamadas) == 4
    assert sem_espera == [0, 2, 8]


def test_CP4_falha_uma_alem_do_limite(sem_espera):
    """4 falhas (limite + 1) -> exceção, sem dormir após a última."""
    handler = _sequencia(*[httpx.Response(500)] * 4, httpx.Response(200, json=[1]))
    with pytest.raises(Exception) as exc:
        _cliente(handler).request("GET", "/x")
    assert isinstance(exc.value.__cause__, httpx.HTTPStatusError)
    assert len(handler.chamadas) == 4
    assert sem_espera == [0, 2, 8]


def test_CP4_max_retries_zero_faz_uma_tentativa(monkeypatch, sem_espera):
    monkeypatch.setattr(ClienteBase, "DEFAULT_MAX_RETRIES", 0)
    handler = _sequencia(httpx.Response(500))
    with pytest.raises(Exception):
        _cliente(handler).request("GET", "/x")
    assert len(handler.chamadas) == 1
    assert sem_espera == []


# ---- CB2: laço com zero iterações (ramo de saída do for sem return/raise)
def test_CB2_laco_sem_iteracoes_retorna_500(monkeypatch):
    monkeypatch.setattr(ClienteBase, "DEFAULT_MAX_RETRIES", -1)
    st, dados = _cliente(_sequencia(httpx.Response(200, json={}))).request("GET", "/x")
    assert (st, dados) == (HTTPStatus.INTERNAL_SERVER_ERROR, None)


# ---- CB1 (complemento estrutural): a análise da decisão
# `response.status_code if response else "Unknown"` mostrou que o ramo
# depende de `response` de uma tentativa ANTERIOR. Nenhum teste funcional
# exercitava "tentativa 1 com resposta, tentativa 2 sem resposta".
def test_CB1_log_de_erro_de_rede_nao_reaproveita_status_antigo(caplog):
    handler = _sequencia(httpx.Response(503), httpx.ConnectError("recusada"))
    with caplog.at_level(logging.WARNING), pytest.raises(Exception):
        _cliente(handler).request("GET", "/x")
    avisos = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert "status 503" in avisos[0]
    assert all("status Unknown" in m for m in avisos[1:])


# ======================================================================
# TDD: erros 4xx definitivos não devem ser repetidos (exceto 408 e 429)
# ======================================================================
@pytest.mark.parametrize("status", [400, 401, 404, 422, 499])
def test_TDD_erro_cliente_definitivo_falha_na_primeira_tentativa(status, sem_espera):
    handler = _sequencia(httpx.Response(status))
    with pytest.raises(Exception, match=f"client error {status}") as exc:
        _cliente(handler).request("GET", "/x")
    assert isinstance(exc.value.__cause__, httpx.HTTPStatusError)
    assert len(handler.chamadas) == 1
    assert sem_espera == []


# ---- MC/DC da decisão  A and B and C and D  em _deve_repetir:
# A: erro é HTTPStatusError | B: status >= 400 | C: status <= 499
# D: status não está em {408, 429}.  Erro definitivo <=> A∧B∧C∧D.
def _erro_status(code):
    resp = httpx.Response(code, request=httpx.Request("GET", "https://x"))
    return httpx.HTTPStatusError("erro", request=resp.request, response=resp)


@pytest.mark.parametrize(
    "caso, erro, deve_repetir",
    [
        ("MC1 A=V B=V C=V D=V", _erro_status(404), False),
        ("MC2 A=F (muda só A)", httpx.ConnectError("x"), True),
        ("MC3 B=F (muda só B)", _erro_status(399), True),
        ("MC4 C=F (muda só C)", _erro_status(500), True),
        ("MC5 D=F (muda só D)", _erro_status(429), True),
    ],
)
def test_MCDC_deve_repetir(caso, erro, deve_repetir):
    assert ClienteBase._deve_repetir(erro) is deve_repetir


# ======================================================================
# TDD ciclo 2: status 2xx fora do enum HTTPStatus não pode quebrar
# ======================================================================
@pytest.mark.parametrize("status", [218, 250, 299])
def test_TDD2_status_2xx_nao_registrado_retorna_codigo_numerico(status):
    handler = _sequencia(httpx.Response(status, json={"ok": True}))
    st, dados = _cliente(handler).request("GET", "/x")
    assert st == status
    assert dados == {"ok": True}
    assert len(handler.chamadas) == 1


@pytest.mark.parametrize("status", [200, 201, 226])
def test_TDD2_status_registrado_continua_sendo_httpstatus(status):
    st, _ = _cliente(_sequencia(httpx.Response(status, json={}))).request("GET", "/x")
    assert isinstance(st, HTTPStatus)


# ======================================================================
# TDD ciclo 3: sucesso sem corpo JSON
# Corpo vazio é legítimo (204, DELETE) -> (status, None).
# Corpo não vazio e não JSON (ex.: página HTML de manutenção) -> erro claro.
# ======================================================================
@pytest.mark.parametrize(
    "resp",
    [httpx.Response(204), httpx.Response(200, content=b""), httpx.Response(202)],
)
def test_TDD3_sucesso_com_corpo_vazio_retorna_none(resp):
    st, dados = _cliente(_sequencia(resp)).request("DELETE", "/x")
    assert st == resp.status_code
    assert dados is None


@pytest.mark.parametrize(
    "resp",
    [
        httpx.Response(200, text="ok"),
        httpx.Response(200, html="<html>Em manutenção</html>"),
        httpx.Response(200, text=" "),
    ],
)
def test_TDD3_sucesso_com_corpo_nao_json_falha_com_mensagem_clara(resp):
    handler = _sequencia(resp)
    with pytest.raises(Exception, match="non-JSON response") as exc:
        _cliente(handler).request("GET", "/x")
    assert isinstance(exc.value.__cause__, ValueError)
    assert len(handler.chamadas) == 1
