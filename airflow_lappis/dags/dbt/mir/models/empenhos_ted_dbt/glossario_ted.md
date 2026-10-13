{% docs glossario_ted %}

**Glossário do painel TED (página 7, épico #506)**

- **Instrumento** — a unidade que o painel conta. É um TED ou um tedinho, uma
  linha de `ted_resumo_orcamentario`, identificado por `id_instrumento`. É a
  mesma unidade da CGPO (74 TEDs + 23 tedinhos = 97 instrumentos).
- **TED** — Termo de Execução Descentralizada registrado no TransfereGov,
  identificado pelo número da transferência (`num_transf`).
  `tipo_instrumento = 'TED'`.
- **Tedinho** — descentralização de crédito do MIR que nunca foi registrada no
  TransfereGov (issue #507). Não tem `num_transf` nem plano de ação; é
  identificado pelo processo ou pela NC (`instrumento_key` em `tedinhos_mir`).
  `tipo_instrumento = 'Tedinho'`.
- **Plano de Ação** — o documento do TransfereGov que detalha um TED (valor
  pactuado, vigência, situação). É um **atributo** do TED, não a unidade de
  contagem: plano ainda não firmado (sem `sq_instrumento`) não é TED e não
  entra no painel, e tedinho não tem plano. Contar `plano_acao` mede outra
  entidade. Por isso o painel não deve exibir um total de planos rotulado como
  TED.

Nos rótulos do painel, **"TEDs" quer dizer instrumentos (TED + tedinho)**. O
filtro "Tipo de Instrumento" separa os dois.

**Cards e filtros da página 7**

| Antes | Rótulo padronizado | Definição |
|---|---|---|
| Qtd Planos de Ação | Qtd TEDs | `count(distinct id_instrumento)` |
| Plano de ação com Empenho | TEDs com Empenho | `situacao_empenho = 'Com empenho'` |
| TEDs Sem Empenho | TEDs sem Empenho | `situacao_empenho = 'Sem empenho'` |
| Qtd Vigentes Plano de Ação | TEDs Vigentes | `situacao_vigencia = 'Vigente'` |
| Qtd Não Vigentes Plano de Ação | TEDs Não Vigentes | `situacao_vigencia = 'Não vigente'` |
| Ano Plano de Ação (filtro) | Ano de Pactuação | `ano_pactuacao` |
| Status Vigência Plano de Ação (filtro) | Situação da Vigência | `situacao_vigencia` |

Cada card de situação tem um bucket explícito que fecha a soma com o total,
para nada sumir num "Em branco": `'Empenho não rastreável (tedinho)'` em
`situacao_empenho` e `'Sem vigência cadastrada'` em `situacao_vigencia`
(tedinho e TED sem plano cadastrado).

{% enddocs %}
