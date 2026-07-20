 DXF PROFILE RENDERER
====================================

Ferramenta para processar arquivos DXF, detectar perfis e furos,
gerar imagens automaticamente (com e sem cotas) e compactar o
resultado em um arquivo `ZIP.`

O projeto oferece:
 - Uma interface de linha de comando (main.py)
 - Uma interface gráfica (RenderUI.py) feita em Tkinter
 - Gerar executável com o comando ```pyinstaller --onefile --windowed --icon=assets/icon256x256.ico --name=DxfConversor RenderUI.py```

------------------------------------
FUNCIONALIDADES
------------------------------------
- Leitura de arquivos DXF com ezdxf
- Identificação automática de:
    • Perfis (LWPOLYLINE e POLYLINE)
    • Furos internos
    • Textos e cotas associadas
- Renderização dos perfis em:
    • PNG (com cotas)
    • BMP (sem cotas, ideal para ícones)
- Compactação final em imagens `.zip`

------------------------------------
INTERFACE GRÁFICA DxfConversor (RenderUI.py)
------------------------------------
O arquivo RenderUI.py fornece uma interface simples feita com Tkinter.

Permite:
 - Criar executável da interface gráfica com ```pyinstaller --onefile --windowed --icon=assets/icon256x256.ico --name=DxfConversor RenderUI.py```
 - Selecionar arquivos DXF pelo explorador de arquivos
 - Executar o processamento com um clique
 - Popup que indica o termino do processo
 - Gerar automaticamente o arquivo ZIP de saída

Ideal para uso interno ou por usuários não técnicos.

------------------------------------
USO VIA CLI (main.py)
------------------------------------
Para executar o processamento diretamente:

    python main.py

Por padrão, o script:
 - Lê o arquivo localizado em "files/TEST_CASE_1.dxf"
 - Gera as imagens e salva tudo em:

```sh
    ./output/
      └── imagens.zip
```

Você pode alterar o caminho do arquivo de entrada diretamente
no main.py, conforme sua necessidade.

------------------------------------
PADRÕES ESPERADOS DO MAPA DE PERFIS (DXF)
------------------------------------
Para que o processamento funcione corretamente, o arquivo DXF
deve seguir alguns padrões básicos:

1. PERFIS PRINCIPAIS:
   - Devem ser LWPOLYLINE ou POLYLINE fechadas (closed = True)
   - Todo o mapa deve estar na layer "PERFIS"

2. FUROS:
   - São polilinhas fechadas internas a um perfil principal
   - Devem estar contidas dentro do contorno do perfil

3. TEXTOS (NOMES):
   - O nome do perfil é extraído do texto localizado dentro da área do perfil
   - Textos que contenham "Kg/m" são ignorados

4. COTAS (DIMENSÕES):
   - Entidades DIMENSION ou ROTATEDDIMENSION são associadas automaticamente
     se estiverem próximas ao centro do perfil
     
5. ESPAÇAMENTO:
   - Os perfis devem ter um bom espaçamento um do outro
   - As molduras, logos e "lixos" do mapa de perfis devem ser apagadas, deixando apenas os
     perfis, cotas e informações dos perfis

------------------------------------
ESTRUTURA DO PROJETO
------------------------------------
```sh
dxf_profile_renderer/
 ├── files/
 │    └── ARQUIVO_DE_ENTRADA.dxf       -> Exemplo de entrada
 ├── output/                            -> Gerado automaticamente
 │    └── imagens.zip
 ├── dist
 │    └── DxfConversor.exe
 ├── RenderUI.py                        -> Interface gráfica (Tkinter)
 ├── main.py                            -> CLI e lógica principal
 └── requirements.txt                   -> Dependências
```
------------------------------------
DEPENDÊNCIAS
------------------------------------
Instale as dependências com:

    pip install -r requirements.txt

------------------------------------
PRÓXIMOS PASSOS
------------------------------------


```
[X] Melhorar processamento de perfis com ângulos arqueados
[ ] Suporte a exportação em SVG e PDF
```
------------------------------------
AUTOR E PROPÓSITO
------------------------------------
Projeto desenvolvido para automatizar a extração e visualização
de perfis DXF em fluxos de alimentação do MOF, economizando tempo da equipe de PI, 
economizando 94,5% do tempo de criação de cada perfil individualmente.
