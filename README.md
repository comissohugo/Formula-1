# 🏁 F1 Data Center — 2000 a 2026

Dashboard histórico da Fórmula 1 em Python/Streamlit, com base local em SQLite e
importação pela [Jolpica F1 API](https://api.jolpi.ca/ergast/f1/) (estrutura
compatível com a antiga Ergast API).

O painel **não inventa dados**: campo ausente na fonte fica ausente (`NULL`) no
banco, e a classificação oficial vem dos endpoints de standings — nunca de soma
manual de pontos.

Para as temporadas antigas em que a fonte primária não traz pole position,
volta mais rápida ou a classificação completa, esses dados são complementados
pela **Wikipédia** (pt para premiações e en para o qualifying de 2000 a 2002),
com URL e data de importação. A fonte primária sempre tem prioridade.

A temporada **2026 é importada em modo "em andamento"**: entram apenas as etapas
já concluídas e a classificação mostrada é a posição atual. Títulos só aparecem
quando já estão **matematicamente garantidos**; em 2026, Antonelli (pilotos) e
Mercedes (construtores) já asseguraram o título, mas a temporada continua em
andamento até a última etapa.

---

## O que já está pronto

- Importação de **2000 a 2025** (503 GPs encerrados) mais **2026 em andamento**
  (20 de 23 GPs concluídos até o momento).
- Calendário, circuitos, pilotos e equipes.
- Classificação completa (qualifying) quando disponível na fonte ou
  complementada, e corrida completa (grid, voltas, pontos, status, tempo,
  volta mais rápida).
- **Sprints separadas** dos GPs principais.
- Classificação oficial de pilotos e construtores (final nas temporadas
  encerradas; atual em 2026), com pontos, vitórias, **pódios** e **poles**.
- **Poles e voltas rápidas ausentes na fonte primária (2000–2003)**
  complementadas pela Wikipédia (pt), com fonte e data registradas.
- **Qualifying completo de 2000 a 2002**: 13 GPs de 2000, 16 de 2001 e 15 de
  2002 complementados pela Wikipédia (en), com prioridade da fonte primária nos
  GPs que ela já cobria.
- Dashboard com abas de Corridas, Campeonato, Pilotos, Equipes, Histórico,
  **Ranking** e Qualidade dos dados.
- **Ranking acumulado do período** (top 10 por vitórias, pódios, corridas,
  poles, voltas rápidas, títulos e pontos), que cresce automaticamente quando
  novas temporadas são importadas.
- **Maiores vencedores do século (desde 2000)**: top 10 por vitórias com o
  circuito onde cada piloto mais venceu, aproveitamento (%) e empates
  explicitados.
- **Vitórias por circuito**: no perfil do piloto (tabela completa por traçado)
  e o top 5 de quem mais venceu em cada circuito, na aba Histórico.
- **Circuitos fora do calendário atual**, calculados pelo calendário importado
  (última edição, número de edições e maior vencedor de cada traçado), sem
  lista manual e sem prever calendário futuro.
- Comparação do piloto com o companheiro de equipe e com **qualquer outro
  piloto da temporada**, com H2H e pontos acumulados.
- Validação automática da base (contagens, campeões, reconciliação de pontos,
  duplicatas, poles, grid, voltas rápidas).
- Exportação CSV das tabelas e **base completa em ZIP** (banco SQLite +
  CSVs + relatório de validação + LEIA-ME).

---

## Como executar no Windows (passo a passo)

### 1. Abrir o terminal na pasta do projeto

```powershell
cd C:\Users\Usuario\Documents\f1-data-center
```

### 2. Criar o ambiente virtual e instalar dependências (só na primeira vez)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 3. Importar os dados (só na primeira vez; leva alguns minutos)

```powershell
.\.venv\Scripts\python -m f1dc.ingest
```

> Para as temporadas em que a fonte primária não traz pole ou volta rápida,
> complemente os dados com a Wikipédia:
>
> ```powershell
> .\.venv\Scripts\python -m f1dc.wikipedia --seasons 2000,2001,2002,2003
> ```
>
> Para completar o qualifying de 2000 a 2002 (GPs ausentes na fonte primária):
>
> ```powershell
> .\.venv\Scripts\python -m f1dc.wikipedia_qualifying --seasons 2000,2001,2002
> ```

### 4. Abrir o painel

```powershell
.\.venv\Scripts\streamlit run app.py
```

O navegador abre em `http://localhost:8501`.

> Também é possível atualizar os dados pelo botão **🔄 Atualizar dados da API**
> na barra lateral do painel.

---

## Comandos úteis

| Ação | Comando |
|---|---|
| Importar tudo | `.\.venv\Scripts\python -m f1dc.ingest` |
| Importar só algumas temporadas | `.\.venv\Scripts\python -m f1dc.ingest --seasons 2024,2025` |
| Complementar poles/voltas rápidas | `.\.venv\Scripts\python -m f1dc.wikipedia --seasons 2000,2001,2002,2003` |
| Completar o qualifying de 2000 a 2002 | `.\.venv\Scripts\python -m f1dc.wikipedia_qualifying --seasons 2000,2001,2002` |
| Atualizar depois de um GP | `.\.venv\Scripts\python -m f1dc.ingest --seasons 2026` |
| Validar a base | `.\.venv\Scripts\python -m f1dc.validate` |
| Rodar os testes | `.\.venv\Scripts\python -m pytest -q` |
| Abrir o painel | `.\.venv\Scripts\streamlit run app.py` |

O relatório de validação fica em `data/validation_report.json` e também aparece
na aba **Qualidade dos dados** do painel.

### Temporada em andamento (2026)

Enquanto a temporada não termina, o projeto usa `IN_PROGRESS_SEASONS = {2026}`
em `f1dc/config.py`:

- só entram no banco as etapas que já têm resultado na fonte;
- a classificação exibida é a **posição atual**, não a final;
- o líder atual não é contado como campeão nem como título no ranking, exceto
  quando o título já está **matematicamente garantido**;
- em 2026, `CLINCHED_CHAMPIONS` registra Antonelli e Mercedes como campeões
  matemáticos; a validação confere a vantagem contra o máximo de pontos ainda
  disponível;
- a validação não exige campeão final nem o total fixo de GPs.

Quando a temporada terminar, remova `2026` de `IN_PROGRESS_SEASONS` **e** de
`CLINCHED_CHAMPIONS`, rode a importação e a validação novamente. O painel
passará a tratá-la como temporada encerrada, com campeão oficial.

### Rotina depois de cada GP (fim de semana de corrida)

Sempre que uma etapa terminar, rode os dois comandos abaixo na pasta do
projeto:

```powershell
.\.venv\Scripts\python -m f1dc.ingest --seasons 2026
.\.venv\Scripts\python -m f1dc.validate
```

O que acontece:

- a importação **regrava** a temporada sem duplicar registros (as etapas já
  importadas são substituídas, não somadas);
- etapas do calendário que **ainda não aconteceram** são ignoradas com o aviso
  `sem resultado na fonte; etapa ainda não realizada, ignorada` — não geram
  erro;
- a validação mostra quantos GPs da temporada já estão concluídos
  (por exemplo, `2026: 21 de 23 GPs concluídos`);
- **reinicie o painel** depois da importação: os dados são lidos do SQLite e o
  cache do Streamlit não expira sozinho.

Se preferir testar antes de gravar na base real, use uma cópia com `--db`:

```powershell
Copy-Item data\f1.db $env:TEMP\f1_teste.db
.\.venv\Scripts\python -m f1dc.ingest --seasons 2026 --db $env:TEMP\f1_teste.db
```

> **Atenção:** reimportar **2000 a 2003** apaga o qualifying e as premiações
> complementares daquelas temporadas. Nesse caso, depois do `f1dc.ingest` rode
> também `f1dc.wikipedia_qualifying --seasons 2000,2001,2002` e
> `f1dc.wikipedia --seasons 2000,2001,2002,2003`. Para 2026 isso não se aplica,
> porque não há dados complementares da Wikipédia nessas temporadas.

---

## Estrutura do projeto

```
f1-data-center/
├── app.py                 # dashboard Streamlit (só lê o banco local)
├── requirements.txt
├── data/
│   ├── f1.db              # banco SQLite (não versionado)
│   └── validation_report.json
├── docs/
│   ├── PROJETO_F1.md      # documento central do projeto
│   ├── CHANGELOG.md
│   └── app_prototipo_original.py
├── f1dc/
│   ├── config.py          # temporadas, caminhos, expectativas
│   ├── api.py             # cliente Jolpica (retry, rate limit, paginação)
│   ├── transform.py       # JSON da API -> linhas do banco
│   ├── db.py              # esquema SQLite e upserts idempotentes
│   ├── ingest.py          # importação por temporada (CLI)
│   ├── wikipedia.py       # poles/voltas rápidas complementares (CLI)
│   ├── wikipedia_qualifying.py  # qualifying de 2000–2002 complementar (CLI)
│   ├── validate.py        # checagens de qualidade (CLI)
│   └── data.py            # agregações usadas pelo dashboard
└── tests/                 # pytest
```

---

## Decisões técnicas importantes

1. **Importação por GP, não por temporada.** Os endpoints de temporada paginam
   por linha de resultado, o que pode truncar um GP no meio da página. Buscar
   `/{season}/{round}/results.json` garante o GP inteiro em uma resposta.
2. **Reimportação idempotente.** Cada temporada é apagada e regravada dentro de
   uma transação. Rodar de novo atualiza sem duplicar.
3. **`points` da API já inclui o ponto de volta mais rápida** quando a regra
   valia (2019–2024). Por isso não somamos bônus por conta própria.
4. **Desclassificação tem duas formas na fonte.** Às vezes vem como
   `positionText = "D"`, às vezes só como `status = "Disqualified"` (ex.:
   Russell em Spa 2024). As duas são tratadas para não contar vitória/pódio
   indevido.
5. **Pole ≠ P1 do grid.** A pole vem da classificação; o grid efetivo é exibido
   em coluna separada. Penalidades não são inferidas. Quando a fonte primária
   não tem a pole/volta rápida, a Wikipédia (pt) preenche a lacuna em tabela
   separada, com URL e data. O qualifying completo de 2000 a 2002, ausente na
   maior parte dos GPs, foi complementado pela Wikipédia (en) na própria tabela
   de classificação, com `source_url`/`fetched_at` por linha e sem tocar nos GPs
   da fonte primária.
6. **Dado ausente ≠ zero.** Campos ausentes ficam `NULL`.

---

## Limitações conhecidas

- Em **2000** a fonte primária trazia qualifying completo em apenas 4 GPs; os
  outros **13 GPs foram complementados pela Wikipédia (en)**. Em **2001** eram
  1 GP na fonte primária e **16 GPs complementados**; em **2002**, 2 GPs e
  **15 GPs complementados**. A fonte primária continua tendo prioridade nos GPs
  que já cobria. Em **2000 R3** (San Marino) há uma divergência conhecida: a
  fonte primária repete o tempo de Ralf Schumacher para Barrichello (1:25.871),
  enquanto a Wikipédia e a formula1.com registram 1:25.242; o valor da fonte
  primária foi mantido e documentado. Até **2003** a fonte também não traz volta
  mais rápida em todos os GPs; as poles e voltas rápidas ausentes nesse período
  foram complementadas pela Wikipédia (pt).
- A API pode não trazer volta mais rápida em todos os GPs; nesses casos o painel
  mostra "Não disponível". A única ausência real documentada fora de 2000–2003 é
  Spa 2021 (corrida encerrada sob safety car após 1 volta).
- Penalidades e decisões dos comissários não são inferidas nem exibidas além do
  que a API informa.
- A evolução de pontos por etapa é calculada dos resultados oficiais; a
  classificação exibida é a oficial dos endpoints de standings.
- A pontuação mudou ao longo do período: **até 2009 o vencedor ganhava 10
  pontos; a partir de 2010, 25 pontos** (com o Top 10 pontuando). A soma de
  pontos do painel é informativa e **não é normalizada entre eras**; para
  comparar pilotos de épocas diferentes, use vitórias, pódios e poles.
  Exceções pontuais, como Abu Dhabi 2014 em dobro, vêm da fonte oficial.
- Em 2026 (temporada em andamento), o painel mostra apenas as etapas já
  concluídas e a posição atual. Títulos só aparecem quando matematicamente
  garantidos (Antonelli e Mercedes) ou depois do encerramento.
- Temporadas futuras ou etapas ainda não realizadas não são preenchidas por
  suposição.

---

## Fonte

- API: <https://api.jolpi.ca/ergast/f1/>
- Documentação: <https://github.com/jolpica/jolpica-f1>
- Complemento de poles/voltas rápidas (2000–2003):
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_2000>,
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_2001>,
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_2002> e
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_2003>
- Complemento da classificação de 2000 a 2002: páginas de GP da Wikipédia em
  inglês (por exemplo, <https://en.wikipedia.org/wiki/2000_Australian_Grand_Prix>,
  <https://en.wikipedia.org/wiki/2001_Australian_Grand_Prix> e
  <https://en.wikipedia.org/wiki/2002_Australian_Grand_Prix>), que citam os
  arquivos da FIA.
- Conferência externa: <https://www.formula1.com/> e <https://www.fia.com/>
