# 🏁 F1 Data Center — 1980 a 2026

Dashboard histórico da Fórmula 1 em Python/Streamlit, com base local em SQLite e
importação pela [Jolpica F1 API](https://api.jolpi.ca/ergast/f1/) (estrutura
compatível com a antiga Ergast API).

O painel **não inventa dados**: campo ausente na fonte fica ausente (`NULL`) no
banco, e a classificação oficial vem dos endpoints de standings — nunca de soma
manual de pontos.

Para as temporadas antigas em que a fonte primária não traz pole position,
volta mais rápida ou a classificação completa, esses dados são complementados
pela **Wikipédia** (pt para premiações e en para o qualifying de 1980 a 2002),
com URL e data de importação. A fonte primária sempre tem prioridade.

A temporada **2026 é importada em modo "em andamento"**: entram apenas as etapas
já concluídas e a classificação mostrada é a posição atual. Títulos só aparecem
quando já estão **matematicamente garantidos**; em 2026, Antonelli (pilotos) e
Mercedes (construtores) já asseguraram o título, mas a temporada continua em
andamento até a última etapa.

---

## O que já está pronto

- Importação de **1980 a 2025** (821 GPs encerrados) mais **2026 em andamento**
  (20 de 23 GPs concluídos até o momento).
- Calendário, circuitos, pilotos e equipes.
- Classificação completa (qualifying) quando disponível na fonte ou
  complementada, e corrida completa (grid, voltas, pontos, status, tempo,
  volta mais rápida).
- **Sprints separadas** dos GPs principais.
- Classificação oficial de pilotos e construtores (final nas temporadas
  encerradas; atual em 2026), com pontos, vitórias, **pódios** e **poles**.
- **Poles e voltas rápidas ausentes na fonte primária (1980–2003)**
  complementadas pela Wikipédia (pt), com fonte e data registradas.
- **Qualifying completo de 1980 a 2002**: a primária não traz nenhuma linha em
  1980–1993 e cobre 15/16 GPs em 1994; cobre 17/17 em 1995, 7/16 em 1996,
  10/17 em 1997, 7/16 em 1998, 3/16 em 1999, 4/17 em 2000, 1/17 em 2001 e
  2/17 em 2002. Todo o restante veio da Wikipédia (en), com `source_url` e
  `fetched_at` por linha. A fonte primária sempre tem prioridade nos GPs que
  cobre.
- Dashboard com abas de Corridas, Campeonato, Pilotos, Equipes, Histórico,
  **Ranking** e Qualidade dos dados.
- **Ranking acumulado do período** (top 10 por vitórias, pódios, corridas,
  poles, voltas rápidas, títulos e pontos), que cresce automaticamente quando
  novas temporadas são importadas.
- **Maiores vencedores por século**: dois top 10 na aba Ranking — século XX
  (1980–1999) e século XXI (2000–2026) — com o circuito onde cada piloto mais
  venceu, aproveitamento (%) e empates explicitados. O painel do século XX
  avisa que o recorte está incompleto (faltam 1950–1979).
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
> .\.venv\Scripts\python -m f1dc.wikipedia --seasons 1980,1981,1982,1983,1984,1990,1991,1992,1993,1994,1995,1996,1997,1998,1999,2000,2001,2002,2003
> ```
>
> Para 1980–1992, alguns pilotos que apenas tentaram a classificação não têm
> cadastro na fonte primária. Antes do complemento de qualifying, rode uma vez
> o script que cadastra apenas nome, nacionalidade e URL desses pilotos e da
> equipe Coloni (as linhas de qualifying gravadas depois mantêm fonte e data):
>
> ```powershell
> .\.venv\Scripts\python scripts\seed_wiki_entities.py
> ```
>
> Para completar o qualifying de 1980 a 2002 (GPs ausentes na fonte primária):
>
> ```powershell
> .\.venv\Scripts\python -m f1dc.wikipedia_qualifying --seasons 1980,1981,1982,1983,1984,1990,1991,1992,1993,1994,1996,1997,1998,1999,2000,2001,2002
> ```

### 4. Abrir o painel

```powershell
.\.venv\Scripts\streamlit run app.py
```

O navegador abre em `http://localhost:8501`.

> Também é possível atualizar os dados pelo botão **🔄 Atualizar 2026 da API**
> na barra lateral do painel (ele só reimporta a temporada em andamento).

---

## Comandos úteis

| Ação | Comando |
|---|---|
| Importar tudo | `.\.venv\Scripts\python -m f1dc.ingest` |
| Importar só algumas temporadas | `.\.venv\Scripts\python -m f1dc.ingest --seasons 2024,2025` |
| Cadastrar pilotos/equipes exclusivos da Wikipédia | `.\.venv\Scripts\python scripts\seed_wiki_entities.py` |
| Complementar poles/voltas rápidas | `.\.venv\Scripts\python -m f1dc.wikipedia --seasons 1980,1981,1982,1983,1984,1990,1991,1992,1993,1994,1995,1996,1997,1998,1999,2000,2001,2002,2003` |
| Completar o qualifying de 1980 a 2002 | `.\.venv\Scripts\python -m f1dc.wikipedia_qualifying --seasons 1980,1981,1982,1983,1984,1990,1991,1992,1993,1994,1996,1997,1998,1999,2000,2001,2002` |
| Atualizar depois de um GP | `.\.venv\Scripts\python -m f1dc.ingest --seasons 2026` |
| Atualizar + validar + publicar | `.\.venv\Scripts\python scripts\update_season.py --round 21` |
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

> **Atenção:** reimportar **1980 a 2003** apaga o qualifying e as premiações
> complementares daquelas temporadas. Nesse caso, depois do `f1dc.ingest` rode
> `scripts\seed_wiki_entities.py`,
> `f1dc.wikipedia_qualifying --seasons 1980,1981,1982,1983,1984,1990,1991,1992,1993,1994,1996,1997,1998,1999,2000,2001,2002`
> e `f1dc.wikipedia --seasons 1980,1981,1982,1983,1984,1990,1991,1992,1993,1994,1995,1996,1997,1998,1999,2000,2001,2002,2003`.
> Para 2026 isso não se aplica, porque não há dados complementares da Wikipédia
> nessa temporada.

### Atualização automática das etapas restantes de 2026

As três etapas finais já estão agendadas no **Agendador de Tarefas do Windows**
(pasta `F1DataCenter`), com o script `scripts/update_season.py`:

| Tarefa | GP | Disparo |
|---|---|---|
| `Atualiza2026-R21-LasVegas` | R21 — Las Vegas | 23/11/2026 09:00 |
| `Atualiza2026-R22-Qatar` | R22 — Qatar | 29/11/2026 16:00 |
| `Atualiza2026-R23-AbuDhabi` | R23 — Abu Dhabi | 06/12/2026 13:00 |

Cada tarefa:

1. espera o resultado do GP aparecer na Jolpica (consulta a cada 15 minutos,
   até 6 horas) — não assume horário fixo de término;
2. recusa seguir em frente se a etapa anterior ainda estiver sem resultado
   (evita lacuna na base);
3. reimporta apenas 2026, valida a base inteira e faz
   `PRAGMA wal_checkpoint(TRUNCATE)`;
4. commita `data/f1.db` + `data/validation_report.json` e faz `push`, o que
   dispara o redeploy no Streamlit Cloud;
5. **não** remove 2026 de `IN_PROGRESS_SEASONS` — o encerramento oficial
   continua sendo uma decisão manual, conferida com a fonte externa.

O log fica em `logs/update_season.log`. Para acompanhar:

```powershell
Get-Content logs\update_season.log -Wait -Tail 20
```

Para ver, pausar ou remover as tarefas:

```powershell
schtasks /query /tn F1DataCenter
schtasks /change /tn F1DataCenter\Atualiza2026-R21-LasVegas /disable
schtasks /delete /tn F1DataCenter\Atualiza2026-R21-LasVegas /f
```

Se o PC estiver desligado no horário, a tarefa não dispara sozinha (o
Agendador não tem "executar assim que possível" nesse caso). Nesse dia, rode
manualmente:

```powershell
.\.venv\Scripts\python scripts\update_season.py --round 21
```

(substitua `--round 21` por 22 ou 23 conforme a etapa). O script é idempotente:
se o resultado já estiver importado e nada mudou, ele encerra sem criar commit.

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
├── scripts/
│   ├── update_season.py   # atualização agendada + commit/push (CLI)
│   └── seed_wiki_entities.py  # cadastro mínimo de pilotos/equipes da Wikipédia
├── logs/
│   └── update_season.log  # log das atualizações automáticas
├── f1dc/
│   ├── config.py          # temporadas, caminhos, expectativas
│   ├── api.py             # cliente Jolpica (retry, rate limit, paginação)
│   ├── transform.py       # JSON da API -> linhas do banco
│   ├── db.py              # esquema SQLite e upserts idempotentes
│   ├── ingest.py          # importação por temporada (CLI)
│   ├── wikipedia.py       # poles/voltas rápidas complementares (CLI)
│   ├── wikipedia_qualifying.py  # qualifying de 1980–2002 complementar (CLI)
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
   separada, com URL e data. O qualifying de 1980 a 2002, ausente na primária
   em 1980–1993 e na maior parte dos GPs de 1996–2002, foi complementado pela
   Wikipédia (en) na própria tabela de classificação, com
   `source_url`/`fetched_at` por linha e sem tocar nos GPs da fonte primária.
   Em 1994 a primária cobre 15 de 16 GPs; o GP restante foi complementado e as
   divergências conhecidas ficaram documentadas no código.
6. **Dado ausente ≠ zero.** Campos ausentes ficam `NULL`.

---

## Limitações conhecidas

- Em **1980–1993** a fonte primária não traz nenhuma linha de qualifying; todos
  os GPs de cada ano foram complementados pela Wikipédia (en). Em **1994** a
  primária cobre 15 GPs e o restante foi complementado. Em **1995** o qualifying
  já vem completo da fonte primária. De **1996 a 1999** a primária cobriu 7/16,
  10/17, 7/16 e 3/16 GPs; os demais foram **complementados pela Wikipédia (en)**.
  Em **2000** eram 4 GPs na primária e **13 complementados**; em **2001**, 1 e
  **16**; em **2002**, 2 e **15**. A fonte primária continua tendo prioridade nos
  GPs que já cobria. Há divergências conhecidas documentadas em
  `f1dc/wikipedia_qualifying.py` (1994 R1/R3/R12, 1997 R2/R3/R8/R9, 1998 R3,
  1999 R2 e 2000 R3). Em **2000 R3** (San Marino) há uma
  divergência conhecida: a
  fonte primária repete o tempo de Ralf Schumacher para Barrichello (1:25.871),
  enquanto a Wikipédia e a formula1.com registram 1:25.242; o valor da fonte
  primária foi mantido e documentado. Até **2003** a fonte também não traz volta
  mais rápida em todos os GPs; as poles e voltas rápidas ausentes nesse período
  foram complementadas pela Wikipédia (pt).
- A API pode não trazer volta mais rápida em todos os GPs; nesses casos o painel
  mostra "Não disponível". A única ausência real documentada fora de 1980–2003 é
  Spa 2021 (corrida encerrada sob safety car após 1 volta).
- Penalidades e decisões dos comissários não são inferidas nem exibidas além do
  que a API informa.
- A evolução de pontos por etapa é calculada dos resultados oficiais; a
  classificação exibida é a oficial dos endpoints de standings.
- A pontuação mudou ao longo do período: **até 2009 o vencedor ganhava 10
  pontos; a partir de 2010, 25 pontos** (com o Top 10 pontuando). A soma de
  pontos do painel é informativa e **não é normalizada entre eras**; para
  comparar pilotos de épocas diferentes, use vitórias, pódios e poles.
  Exceções pontuais, como Abu Dhabi 2014 em dobro, vêm da fonte oficial. A regra
  dos melhores resultados vigorou até 1990: em **1980** só os 5 melhores de cada
  metade do campeonato contavam (Jones 71 brutos / 67 oficiais, Reutemann 49 /
  42) e em **1990** só os 11 melhores contavam (Prost 73 brutos / 71 oficiais,
  Piquet 44 / 43). A validação aplica o ajuste oficial sem alterar os resultados
  importados.
- Em 2026 (temporada em andamento), o painel mostra apenas as etapas já
  concluídas e a posição atual. Títulos só aparecem quando matematicamente
  garantidos (Antonelli e Mercedes) ou depois do encerramento.
- Temporadas futuras ou etapas ainda não realizadas não são preenchidas por
  suposição.

---

## Fonte

- API: <https://api.jolpi.ca/ergast/f1/>
- Documentação: <https://github.com/jolpica/jolpica-f1>
- Complemento de poles/voltas rápidas (1980–2003):
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_1980>,
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_1990>,
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_1995>,
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_2000>,
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_2001>,
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_2002> e
  <https://pt.wikipedia.org/wiki/Campeonato_Mundial_de_F%C3%B3rmula_1_de_2003>
- Complemento da classificação de 1980 a 2002: páginas de GP da Wikipédia em
  inglês (por exemplo, <https://en.wikipedia.org/wiki/1980_Dutch_Grand_Prix>,
  <https://en.wikipedia.org/wiki/1996_French_Grand_Prix>,
  <https://en.wikipedia.org/wiki/2000_Australian_Grand_Prix>,
  <https://en.wikipedia.org/wiki/2001_Australian_Grand_Prix> e
  <https://en.wikipedia.org/wiki/2002_Australian_Grand_Prix>), que citam os
  arquivos da FIA.
- Conferência externa: <https://www.formula1.com/> e <https://www.fia.com/>
