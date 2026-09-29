-- Movimentos financeiros dos convenios (desembolso, contrapartida, desbloqueio,
-- pagamento a fornecedor, tributo), um por linha. Fornecedor -1 nos movimentos
-- que nao sao pagamento e nos pagamentos sem documento valido; tempo -1 nos
-- tributos sem data na origem.
select
    m.id_movimento,
    {{ fk(["m.nr_convenio"]) }} as sk_convenio,
    {{ sk_tempo("m.data_movimento") }} as sk_tempo,
    {{ fk(["m.fornecedor_chave"]) }} as sk_fornecedor,
    m.tipo_movimento,
    m.documento_referencia,
    m.valor,
    m.valor_bloqueado
from {{ ref("convenio_movimento_financeiro") }} as m
