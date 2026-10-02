{#
    Padroes de extracao do vinculo NE -> instrumento, compartilhados entre os
    modelos e o teste regex_vinculo_fixtures. Cada macro devolve um literal
    SQL de texto para regexp_match(..., 'i').

    regex_convenio: numero depois de CONVENIO/FOMENTO (6 digitos, ou o formato
    alfanumerico adotado a partir de 2026, ex.: 7AACWU).
    regex_rotulo_transferencia: numero depois do rotulo explicito
    "NUM. TRANSFERENCIA" ou "SICONV" (cenario do antigo numero_transferencia,
    PR #68).
    regex_empenho_origem: NE gerada pela rotina de transferencia de saldo
    (NSSALDO), que cita "EMPENHO DE ORIGEM: 810008/2024NE000092"; grupo 1 = UG,
    grupo 2 = ano + NE + sequencial (o right(ne_ccor, 12) da NE de origem).
#}
{% macro regex_convenio() -%}
    '(?:CONVENIO|FOMENTO|FOMENO)\s*(?:N[°º]?)?\s*\m(\d{6}|\d[0-9A-Z]{5})\M'
{%- endmacro %}

{% macro regex_rotulo_transferencia() -%}
    '(?:NUM\.?\s*TRANSFERENCIA|SICONV)\s*:?\s*\m(\d{6}|\d[0-9A-Z]{5})\M'
{%- endmacro %}

{% macro regex_empenho_origem() -%}
    'EMPENHO\s+DE\s+ORIGEM:\s*(\d{6})/(\d{4}NE\d{6})'
{%- endmacro %}
