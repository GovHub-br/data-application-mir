-- Falha se alguma agenda de 2024 não encontrar, pelo nome, o código recodificado
-- de 2025+ (ex.: 5 -> 369). Sem o de-para a série histórica quebra no BI; se a
-- fonte renomear uma agenda, a regra de nome_normalizado precisa ser revista.
select ano_ppa, codigo, nome_agenda
from {{ ref('agenda_filtrado_mir') }}
where ano_ppa = 2024 and chave_agenda = codigo
