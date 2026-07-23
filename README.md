# Automação de download de dados do CAR/SICAR

Script para baixar, de forma automatizada, os arquivos ZIP das camadas do
Cadastro Ambiental Rural (CAR) disponibilizados pelo SICAR. Os arquivos são
organizados automaticamente em pastas separadas por camada.

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

As principais dependências são `SICAR`, usado para acessar os dados do
Cadastro Ambiental Rural, e `logutil`, usado para registrar o andamento e as
falhas dos downloads. O `SICAR` é instalado diretamente do repositório GitHub
do projeto, pois não é instalado a partir de um pacote publicado no PyPI.

## Uso

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

## Camadas disponíveis

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

## Estrutura de saída

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

## Comportamento do script

- tenta inicializar o cliente SICAR até cinco vezes;
- consulta as datas de disponibilização retornadas pelo SICAR;
- baixa os arquivos por estado;
- permite filtrar um único estado pela sigla;
- aguarda alguns segundos entre os downloads para reduzir a carga sobre o
	serviço;
- registra sucessos e falhas durante o processamento;
- continua o processamento dos demais estados quando um download falha.

## Observações

- A disponibilidade dos arquivos depende do serviço do SICAR.
- A execução de `--layer all` pode exigir bastante tempo e espaço em disco.
- O script não remove arquivos já existentes. Verifique o conteúdo de
	`source/` antes de iniciar uma nova execução.
- Em caso de falha, consulte as mensagens exibidas no terminal e tente
	novamente para o estado ou camada correspondente.
