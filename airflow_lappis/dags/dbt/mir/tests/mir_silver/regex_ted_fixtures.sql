-- depends_on: {{ ref("empenhos_por_plano_acao") }}
-- Falha se algum metodo da cascata de num_transf (macro ted_num_transf_metodos,
-- a mesma usada por empenhos_por_plano_acao) deixar de extrair o numero esperado
-- de textos reais conhecidos do ppa_tesouro. Cobre o numero alfanumerico do
-- TransfereGov adotado a partir de 2026 (ex.: 7AADZA). O depends_on acima
-- prende o teste ao modelo que usa as regex: sem um ref, o cosmos nao agenda o
-- teste.
{% set metodos = fromyaml(ted_num_transf_metodos()) %}
with
    casos(metodo, texto, esperado) as (
        values
            (
                'metodo 1',
                'C. CUSTO: FED - TED MIR 14/2026NUMERO DE TRANSFERENCIA:7AADZA-UNIDADE V',
                '7AADZA'
            ),
            (
                'metodo 1',
                'TED 26/2023-MIR-PROM.DE INICIATIVAS ANTIRRACISTAS-NUM.TRANSF.950552.(CO',
                '950552'
            ),
            (
                'metodo 1',
                'TED 23/2025 - MIR - TRANSFERENCIA: 984218 / COORDENADOR',
                '984218'
            ),
            ('metodo 1', 'PAGAMENTO DE 7 DIARIAS - TED MIR', null),
            ('metodo 3', 'DESCENTRALIZACAO TED Nº 7AACRT - UFRJ', '7AACRT'),
            ('metodo 3', 'DESCENTRALIZACAO TED Nº 958784 - UFRB', '958784'),
            (
                'metodo 14',
                'ATENDIMENTO AO PROJETO TRANSFEREGOV Nº 7AAFOB - ENFRENT',
                '7AAFOB'
            ),
            ('metodo 14', 'CONFORME TRANSFEREGOV Nº 984218', '984218'),
            ('metodo 14', 'CONFORME TRANSFEREGOV 2026NE000004', null),
            ('metodo 16', 'TED 11/2026 (7AACRT) - UFRJ', '7AACRT')
    ),

    extraido as (
        select
            metodo,
            texto,
            esperado,
            case
                metodo
                {% for m in metodos %}
                    when '{{ m.label }}'
                    then
                        replace(
                            (regexp_match(texto, '{{ m.regex }}', 'i'))[{{ m.group }}],
                            '.',
                            ''
                        )
                {% endfor %}
            end as obtido
        from casos
    )

select *
from extraido
where upper(obtido) is distinct from esperado
