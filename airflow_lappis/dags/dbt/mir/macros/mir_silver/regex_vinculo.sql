{#
  Regex de vinculo NE -> TED, compartilhados entre o modelo e os testes.

    regex_numero_ted: numero/ano do TED na numeracao do MIR ("TED Nº 16/2023",
    "TED MIR 14/2026", "TERMO DE EXECUCAO DESCENTRALIZADA 05/26"); grupo 1 =
    numero, grupo 2 = ano com 2 ou 4 digitos. Liga a NE ao plano pela pagina
    do gov.br (ted_gov_br). Use com 'g' em regexp_matches: a NE pode citar mais
    de um TED.
    regex_empenho_origem: NE gerada pela rotina de transferencia de saldo
    (NSSALDO), que cita "EMPENHO DE ORIGEM: 810008/2024NE000092"; grupo 1 = UG,
    grupo 2 = ano + NE + sequencial (o right(ne_ccor, 12) da NE de origem).
#}

{% macro regex_numero_ted() -%}
    '(?:\mTED|DESCENTRALIZADA)\s*(?:MIR\s*)?(?:N\s*[º°O.]?\s*|NR\.?\s*|NUMERO\s*)?(?<![0-9])([0-9]{1,3})\s*/\s*((?:20)?(?:19|2[0-9]))(?![0-9])'
{%- endmacro %}

{% macro regex_empenho_origem() -%}
    'EMPENHO\s+DE\s+ORIGEM:\s*(\d{6})/(\d{4}NE\d{6})'
{%- endmacro %}

{#
  Métodos da cascata de extração do num_transf de empenhos_por_plano_acao, na ordem
  em que são aplicados (cada NE fica com o primeiro que extrair um valor). Ficam
  em macro para o teste regex_ted_fixtures validar os mesmos regex do modelo.
  O número do TransfereGov é numérico (6 dígitos) ou alfanumérico começando com
  1 ou, a partir de 2026, com 7 (ex.: 7AADZA).
#}
{% macro ted_num_transf_metodos() -%}
    {% set metodos_yaml %}
- label: "metodo 1"
  field: ne_ccor_descricao
  group: 2
  regex: '(FERENCIA|TED|CRICAO|TRANSF.|TRANF.|TRANSFERENCIA)[\s:.-]*(?<![0-9])([0-9]{6}|[17]\w{5}|[0-9]{3}\.[0-9]{3})(?![0-9])'
- label: "metodo 2"
  field: ne_ccor_descricao
  group: 2
  regex: '.*(?:NOTA DE (TRANSFERENCIA|TRANFERENCIA|CREDITO))[:.[:space:]-]*((?=[A-Za-z0-9]*[0-9])[A-Za-z0-9]{6,})'
- label: "metodo 3"
  field: ne_ccor_descricao
  group: 1
  regex: '.*(?:(?:TED(?:[[:space:]]*[-.N∞øº°∅()]*))[[:space:]]*|(?:SIAFI[[:space:]]+N∫))[[:space:].-]*(?<![0-9])(([0-9]{6})|([17][A-Za-z0-9]{5}))(?![0-9])'
- label: "metodo 4"
  field: fonte_recursos_detalhada_descricao
  group: 1
  regex: 'TED(?::)?(?:[[:space:]]+[A-Z/]+)?[[:space:]:-]*N?[∞∫ºo]?[[:space:]]*[0-9/]*[[:space:]:;,-]*[ø-]?[[:space:]]*([0-9]{6}|[17][A-Z0-9]{5})'
- label: "metodo 5"
  field: ne_info_complementar
  group: 1
  regex: '^([0-9]{6}|[17][A-Za-z0-9]{5})$'
- label: "metodo 10"
  field: doc_observacao
  group: 2
  regex: '(FERENCIA|TED|CRICAO|TRANSF.|TRANF.|TRANSFERENCIA)[\s:.-]*(?<![0-9])([0-9]{6}|[17]\w{5}|[0-9]{3}\.[0-9]{3})(?![0-9])'
- label: "metodo 11"
  field: ne_ccor_descricao
  group: 1
  regex: '\mNT[.: ]*(?<![0-9])([0-9]{6}|[17][A-Za-z0-9]{5})(?![0-9])'
- label: "metodo 14"
  field: ne_ccor_descricao
  group: 1
  regex: 'TRANSFEREGOV\s*(?:N[∞∫øºo°.]{0,2}\s*)?(?<![0-9])([0-9]{6}|[17][A-Za-z0-9]{5})(?![0-9])'
- label: "metodo 15"
  field: fonte_recursos_detalhada_descricao
  group: 1
  regex: 'TRANSFEREGOV\s*(?:N[∞∫øºo°.]{0,2}\s*)?(?<![0-9])([0-9]{6}|[17][A-Za-z0-9]{5})(?![0-9])'
- label: "metodo 16"
  field: ne_ccor_descricao
  group: 1
  regex: 'TED[^()]{0,30}?\((?:SIAFI\s+)?(?<![0-9])([0-9]{6}|[17][A-Za-z0-9]{5})(?![0-9])\)'
    {% endset %}
    {{ return(metodos_yaml) }}
{%- endmacro %}
