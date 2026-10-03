-- depends_on: {{ ref("empenhos_por_plano_acao") }}
-- Falha se alguma regex de vinculo NE -> TED (macros regex_numero_ted e
-- regex_empenho_origem) deixar de extrair o numero esperado de textos reais
-- conhecidos do ppa_tesouro. O depends_on acima prende o teste ao modelo que
-- usa as regex: sem um ref, o cosmos nao agenda o teste.
with
    casos(regex, texto, esperado) as (
        values
            ('origem_ug', 'NSSALDO - EMPENHO DE ORIGEM: 810008/2024NE000093', '810008'),
            (
                'origem_sufixo',
                'NSSALDO - EMPENHO DE ORIGEM: 810008/2024NE000093',
                '2024NE000093'
            ),
            ('origem_ug', 'EMISSAO DE EMPENHO VISANDO ATENDER TERMO DE FOMENTO', null),
            (
                'numero_ted',
                'ESTUDANTE VINCULADO AO - TED Nº 16/2023, FIRMADO ENTRE A UFPB E O MIR',
                '16/2023'
            ),
            ('numero_ted', '26NC000056 (UG 810008) - TED MIR 14/2026NUMERO DE', '14/2026'),
            (
                'numero_ted',
                'S3324-CONVENIO ESPECIFICO N.33.24, CONF.TED Nº 15/24, CELEB',
                '15/24'
            ),
            ('numero_ted', 'TERMO DE EXECUCAO DESCENTRALIZADA N. 05/2026 - UFG', '05/2026'),
            ('numero_ted', '23075.074478/2024-83 - TED 33/2024  -  CT 172/2024', '33/2024'),
            -- numero do Transferegov, nao numero/ano
            ('numero_ted', 'TED 984218 - FIOCRUZ', null),
            -- sem barra: nao e numero/ano
            ('numero_ted', 'PRESTACAO DE SERVICO / TED- 18-2023-MIR', null)
    ),

    extraido as (
        select
            regex,
            texto,
            esperado,
            case
                regex
                when 'origem_ug'
                then (regexp_match(texto, {{ regex_empenho_origem() }}, 'i'))[1]
                when 'origem_sufixo'
                then (regexp_match(texto, {{ regex_empenho_origem() }}, 'i'))[2]
                when 'numero_ted'
                then
                    (regexp_match(texto, {{ regex_numero_ted() }}, 'i'))[1]
                    || '/'
                    || (regexp_match(texto, {{ regex_numero_ted() }}, 'i'))[2]
            end as obtido
        from casos
    )

select *
from extraido
where upper(obtido) is distinct from esperado
