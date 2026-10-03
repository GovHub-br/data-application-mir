import html
import logging
import re
import time
import httpx
from cliente_base import ClienteBase

# Início de um TED na página: "Termo de Execução Descentralizada nº X/AAAA" ou
# "TED ... nº X/AAAA" (ex.: "TED da UFG nº 01/2025").
RE_INICIO_TED = re.compile(
    r"^\s*(?:Termo de Execu[cç][aã]o Descentralizada|TED\b[^\n]{0,30}?)\s*n\s*[º°o.]?\s*"
    r"(\d{1,3})\s*/\s*(\d{4})",
    re.I,
)
# Número da transferência no Transferegov: 6 dígitos ou, desde 2026, alfanumérico
# começando por dígito (ex.: 7AABPO).
NUM_TRANSF = r"(?<![0-9A-Z])(\d{6}|\d[A-Z0-9]{5})(?![0-9A-Z])"
RE_TRANSFEREGOV = re.compile(
    r"(?:Transfere\s*gov|\bTED)[^0-9\n]{0,25}?" + NUM_TRANSF, re.I
)
RE_PROCESSO = re.compile(r"\b(\d{5}\.\d{6}/\d{4}-\d{2})\b")
RE_VALOR = re.compile(r"R\$\s*([\d.]+,\d{2})")
RE_PARCEIRO = re.compile(
    r"firmado entre o Minist[ée]rio da Igualdade Racial(?:\s*-\s*MIR)?\s+e\s+"
    r"(?:a|o|as|os)\s+([^.:]+?)(?:\.|:|,\s*cujo|\s+Processo)",
    re.I,
)


def html_para_texto(conteudo_html: str) -> str:
    """
    Texto do corpo da página (div content-core do Plone), uma linha por parágrafo.
    """
    inicio = conteudo_html.find('id="content-core"')
    fim = conteudo_html.find('id="viewlet-below-content"', inicio)
    corpo = conteudo_html[inicio : fim if fim > 0 else None] if inicio >= 0 else ""
    texto = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", corpo, flags=re.S)
    texto = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</div>|</tr>", "\n", texto)
    texto = html.unescape(re.sub(r"<[^>]+>", " ", texto)).replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    return re.sub(r"\n\s*\n+", "\n", texto)


def extrair_teds(texto: str, pagina: str) -> list[dict]:
    """
    Separa o texto da página em blocos, um por TED (do título até o próximo TED),
    e extrai de cada bloco o número da transferência, o processo, o parceiro e o
    valor. Só o primeiro número do Transferegov do bloco é o do TED; os demais
    (aditivos, erros de digitação) ficam em num_transf_alternativos.
    """
    blocos: list[dict] = []
    atual: dict | None = None
    for linha in texto.splitlines():
        m = RE_INICIO_TED.match(linha)
        if m:
            numero_ted = f"{int(m.group(1)):02d}/{m.group(2)}"
            if atual is None or atual["numero_ted"] != numero_ted:
                atual = {"numero_ted": numero_ted, "texto": ""}
                blocos.append(atual)
        if atual is not None:
            atual["texto"] += linha.strip() + "\n"

    teds = []
    for bloco in blocos:
        txt = bloco["texto"]
        transf = list(dict.fromkeys(RE_TRANSFEREGOV.findall(txt)))
        processos = list(dict.fromkeys(RE_PROCESSO.findall(txt)))
        valor = RE_VALOR.search(txt)
        parceiro = RE_PARCEIRO.search(txt)
        teds.append(
            {
                "pagina": pagina,
                "numero_ted": bloco["numero_ted"],
                "num_transf": transf[0] if transf else None,
                "num_transf_alternativos": ";".join(transf[1:]) or None,
                "processo": processos[0] if processos else None,
                "parceiro": (
                    re.sub(r"\s+", " ", parceiro.group(1)).strip() if parceiro else None
                ),
                "valor": valor.group(1) if valor else None,
                "texto": txt.strip(),
            }
        )
    return teds


class ClienteTransferenciasGovBr(ClienteBase):
    """
    Páginas de transferências voluntárias do MIR no gov.br: uma subpágina por ano
    (2023, 2024, 2025-1...) com o número/ano de cada TED e, quase sempre, o número
    da transferência no Transferegov. É a ponte entre o "TED nº 05/2026" citado
    nas NEs e o plano de ação.
    """

    BASE_URL = (
        "https://www.gov.br/igualdaderacial/pt-br/acesso-a-informacao/"
        "convenios-e-transferencias/tranferencias-voluntarias"
    )
    BASE_HEADER = {"User-Agent": "Mozilla/5.0"}
    # Subpáginas por ano: "2023", "2025-1"... ("transferencias-voluntarias-1" fica
    # de fora).
    RE_SUBPAGINA = re.compile(
        r'href="[^"]*/tranferencias-voluntarias/(\d{4}(?:-\d+)?)/?"'
    )

    def __init__(self) -> None:
        super().__init__(
            base_url=ClienteTransferenciasGovBr.BASE_URL,
            headers=ClienteTransferenciasGovBr.BASE_HEADER,
        )
        self.client.follow_redirects = True

    def get_html(self, path: str) -> str:
        """
        GET de uma página HTML, com as mesmas tentativas do ClienteBase (que só
        trata respostas JSON).
        """
        for attempt in range(self.DEFAULT_MAX_RETRIES + 1):
            try:
                response = self.client.get(path, timeout=30)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as e:
                logging.warning(
                    f"[cliente_transferencias_gov_br.py] Falha ao buscar "
                    f"{self.base_url}{path} na tentativa {attempt + 1}: {e}"
                )
                if attempt < self.DEFAULT_MAX_RETRIES:
                    time.sleep(attempt**2 * self.DEFAULT_SLEEP_SECONDS)
                else:
                    raise Exception(
                        "Página falhou após o número máximo de tentativas!"
                    ) from e
        return ""

    def listar_paginas(self) -> list[str]:
        """Subpáginas por ano linkadas na página principal."""
        paginas = list(dict.fromkeys(self.RE_SUBPAGINA.findall(self.get_html(""))))
        logging.info(f"[cliente_transferencias_gov_br.py] Subpáginas: {paginas}")
        return paginas

    def get_teds_pagina(self, pagina: str) -> list[dict]:
        """TEDs de uma subpágina, um registro por TED."""
        texto = html_para_texto(self.get_html(f"/{pagina}"))
        teds = extrair_teds(texto, pagina)
        for ted in teds:
            ted["url"] = f"{self.BASE_URL}/{pagina}"
        logging.info(
            f"[cliente_transferencias_gov_br.py] {len(teds)} TEDs na página {pagina}"
        )
        return teds
