{{ config(severity="warn") }}

-- Aviso (nao bloqueia): instrumento vigente sem UG/CNPJ nao pode ser acessado
-- por nenhum gestor no Coleta MIR ate o MIR atribuir o identificador.
select chave, tp_instrumento, no_parceiro, dt_fim_vigencia
from {{ ref("coleta_instrumento") }}
where
    co_identificador is null
    and (dt_fim_vigencia is null or dt_fim_vigencia >= current_date)
