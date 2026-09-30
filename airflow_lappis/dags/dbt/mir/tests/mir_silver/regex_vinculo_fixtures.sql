-- depends_on: {{ ref("vinculo_ne_convenio") }}
-- Falha se alguma regex de vinculo NE -> instrumento deixar de extrair o
-- numero esperado de textos reais conhecidos do ppa_tesouro. O depends_on
-- acima prende o teste ao modelo que usa as regex: sem um ref, o cosmos nao
-- agenda o teste.
with
    casos(regex, texto, esperado) as (
        values
            (
                'rotulo',
                'ATENDER DESPESA,  NUM. TRANSFERENCIA : 947867, REFERENTE',
                '947867'
            ),
            ('rotulo', 'TED 22/2025, NUM. TRANSFERENCIA: 984056. PROCESSO', '984056'),
            (
                'rotulo',
                'DESTAQUE PARA ATENDER AO TED 00021/2023 - NUM TRANSFERENCIA 948966',
                '948966'
            ),
            ('rotulo', 'UFSM/FATEC, CONVENIO SICONV 979943/2025 - UFSM/FATEC', '979943'),
            ('rotulo', 'PROJETO NEABI - TED/MIR, SICONV 7AACWU, PROC.', '7AACWU'),
            ('rotulo', 'SERVICO DE REPARO EM BENS IMOVEIS. SICONV SEM NUMERO', null),
            (
                'convenio',
                'EMISSAO DE EMPENHO VISANDO ATENDER TERMO DE FOMENTO 965655/2024',
                '965655'
            ),
            ('convenio', 'CONVENIO N° 7AAAOI - PREFEITURA', '7AAAOI'),
            ('convenio', 'CONVENIO UFSM/FATEC, PROJETO', null),
            ('origem_ug', 'NSSALDO - EMPENHO DE ORIGEM: 810008/2024NE000093', '810008'),
            (
                'origem_sufixo',
                'NSSALDO - EMPENHO DE ORIGEM: 810008/2024NE000093',
                '2024NE000093'
            ),
            ('origem_ug', 'EMISSAO DE EMPENHO VISANDO ATENDER TERMO DE FOMENTO', null)
    ),

    extraido as (
        select
            regex,
            texto,
            esperado,
            case
                regex
                when 'rotulo'
                then (regexp_match(texto, {{ regex_rotulo_transferencia() }}, 'i'))[1]
                when 'convenio'
                then (regexp_match(texto, {{ regex_convenio() }}, 'i'))[1]
                when 'origem_ug'
                then (regexp_match(texto, {{ regex_empenho_origem() }}, 'i'))[1]
                when 'origem_sufixo'
                then (regexp_match(texto, {{ regex_empenho_origem() }}, 'i'))[2]
            end as obtido
        from casos
    )

select *
from extraido
where upper(obtido) is distinct from esperado
