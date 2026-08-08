# Automação de download de dados do CAR/SICAR

Scripts para baixar, de forma automatizada, os arquivos ZIP das camadas do
Cadastro Ambiental Rural (CAR) disponibilizados pelo SICAR — seja de forma
pontual por camada/estado (`downloader.py`), seja o conjunto completo em
loop até terminar (`download_until_done.py`).

## Requisitos

- Python 3.9 ou superior;
- Git instalado e disponível no PATH;
- acesso à internet;
- dependências listadas em [requirements.txt](requirements.txt);
- espaço em disco suficiente para armazenar os arquivos ZIP baixados.

Recomenda-se executar o script em um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

No Windows, ative o ambiente com:

```powershell
.venv\Scripts\Activate.ps1
```

Instale as dependências do projeto com:

```bash
python -m pip install -r requirements.txt
```

A principal dependência é o pacote `SICAR`, usado para acessar os dados do
Cadastro Ambiental Rural. Ele é instalado diretamente do repositório GitHub
do projeto, pois não é instalado a partir de um pacote publicado no PyPI.

Para a resolução automática do captcha por OCR também é necessário ter o
[Tesseract OCR](https://github.com/tesseract-ocr/tesseract) instalado e
disponível no PATH (no Windows, o caminho padrão
`C:\Program Files\Tesseract-OCR` é detectado automaticamente pelo
`download_until_done.py`).

## Sobre o pacote SICAR

Este projeto depende do pacote `SICAR`, instalado a partir do repositório
oficial do autor em [https://github.com/urbanogilson/SICAR#egg=SICAR](https://github.com/urbanogilson/SICAR#egg=SICAR).

O download dos arquivos do CAR/SICAR é realizado por meio dessa biblioteca,
que acessa o serviço do governo e precisa lidar com o desafio de captcha da
plataforma. Neste repositório, a automação resolve esse captcha usando OCR.

> Importante: se o SICAR alterar o método de captcha, ou se houver qualquer
> mudança na forma como o processo de autenticação e download é realizado, o
> fluxo automatizado pode falhar facilmente. Isso torna a solução dependente da
> estabilidade do comportamento do pacote e da página do SICAR.

## Scripts disponíveis

| Script | Uso recomendado |
| --- | --- |
| [downloader.py](downloader.py) | Baixar uma camada (ou todas) de forma pontual, com filtro opcional por estado. |
| [download_until_done.py](download_until_done.py) | Baixar **todas** as combinações de estado × camada em loop, retomando automaticamente até completar o conjunto. |

## Uso do downloader.py

Execute o downloader com:

```bash
python downloader.py
```

Por padrão, o script baixa a camada de propriedades (`property`) para todos
os estados retornados pelo SICAR.

### Opções disponíveis

| Opção | Descrição | Padrão |
| --- | --- | --- |
| `--layer` | Camada a baixar. Aceita uma camada ou `all`. | `property` |
| `--state` | Sigla do estado a baixar, como `SP`, `MT` ou `AC`. Sem essa opção, baixa todos. | todos |

Exemplos:

```bash
# Baixar somente propriedades do estado de São Paulo
python downloader.py --layer property --state SP

# Baixar a camada de vegetação nativa de todos os estados
python downloader.py --layer vegetation

# Baixar todas as camadas de um estado
python downloader.py --layer all --state MT
```

### Camadas disponíveis

| Valor de `--layer` | Camada |
| --- | --- |
| `property` | Área do imóvel/propriedade |
| `app` | Áreas de Preservação Permanente (APP) |
| `vegetation` | Vegetação nativa |
| `reserve` | Reserva Legal |
| `consolidated` | Área consolidada |
| `hydrography` | Hidrografia |
| `fallow` | Área de pousio |
| `restricted` | Uso restrito |
| `administrative` | Servidão administrativa |
| `all` | Todas as camadas acima |

### Estrutura de saída

Os downloads são salvos na pasta `source/`, em um diretório específico para
cada camada:

```text
source/
├── area_overlay/
├── app_overlay/
├── native_vegetation_overlay/
├── legal_reserve_overlay/
├── consolidated_area_overlay/
├── hydrography_overlay/
├── fallow_overlay/
├── restricted_use_overlay/
└── administrative_service_overlay/
```

Os arquivos ZIP encontrados após cada download são movidos para a pasta da
camada correspondente. A pasta `source/` é criada automaticamente quando
necessário.

### Comportamento

- tenta inicializar o cliente SICAR até cinco vezes;
- consulta as datas de disponibilização retornadas pelo SICAR;
- baixa os arquivos por estado;
- permite filtrar um único estado pela sigla;
- aguarda alguns segundos entre os downloads para reduzir a carga sobre o
	serviço;
- registra sucessos e falhas durante o processamento;
- continua o processamento dos demais estados quando um download falha.

## Uso do download_until_done.py

Alternativa ao `downloader.py` para baixar o conjunto completo: todos os
estados retornados pelo SICAR × todas as 9 camadas (27 estados = 243 ZIPs).
O script roda em passes sucessivos até que todos os arquivos estejam
presentes e válidos.

```bash
# Rodar até completar todos os downloads
python download_until_done.py

# Limitar a 10 passes (encerra mesmo se incompleto)
python download_until_done.py --max-passes 10
```

### Comportamento

- um ZIP só conta como concluído se passar na validação `zipfile.is_zipfile`;
	arquivos truncados ou corrompidos são removidos e baixados novamente;
- totalmente retomável: pode ser interrompido a qualquer momento (Ctrl+C) e,
	ao reexecutar, tenta apenas o que ainda está faltando;
- pausa curta após cada download e pausa maior após falhas;
- após 5 falhas consecutivas, reconstrói a sessão do SICAR e aguarda alguns
	minutos (proteção contra bloqueio/captcha do servidor);
- entre passes sem progresso, aplica backoff exponencial (60s até 15min),
	reiniciado sempre que um passe baixa algo;
- exibe progresso com percentual, tempo decorrido e estimativa de conclusão
	(ETA);
- no Windows, adiciona automaticamente `C:\Program Files\Tesseract-OCR` ao
	PATH caso o binário do Tesseract não seja encontrado.

### Estrutura de saída

Mesmo layout de pastas por camada do `downloader.py`, com os ZIPs nomeados
como `{ESTADO}_{CAMADA}.zip` dentro de cada pasta:

```text
source/
├── area_overlay/
│   ├── AC_AREA_IMOVEL.zip
│   ├── ...
│   └── TO_AREA_IMOVEL.zip
├── app_overlay/
│   └── ...
└── ...
```

ZIPs baixados por versões anteriores do script no layout plano (direto em
`source/`) são movidos automaticamente para as subpastas na inicialização.

## Observações

- A disponibilidade dos arquivos depende do serviço do SICAR.
- A execução de `--layer all` pode exigir bastante tempo e espaço em disco.
- O script não remove arquivos já existentes. Verifique o conteúdo de
	`source/` antes de iniciar uma nova execução.
- Em caso de falha, consulte as mensagens exibidas no terminal e tente
	novamente para o estado ou camada correspondente.
