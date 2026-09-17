# 🚀 Gerador Genérico de Vídeos Tutoriais com IA

Motor modular e reutilizável em Python para geração automatizada de vídeos tutoriais. Combina gravações de tela com narração sintetizada por IA (Microsoft Edge TTS), overlays de texto dinâmicos (lower-thirds), imagens de destaque (logos/badges) e sincronização com congelamento de quadro via MoviePy 2.

---

## 📁 Estrutura do Workspace

```text
video-automate/
├── .venv/                 # Ambiente virtual com MoviePy, edge-tts, Pillow e PySide6
├── cenas/                 # Gravações de tela (.mp4) e elementos visuais (.png/.jpg)
│   ├── logo_moodle.png    # Exemplo de imagem/logo para destaque
│   └── badge_dica.png     # Exemplo de badge informativo
├── saida/                 # Pasta de destino dos vídeos compilados (.mp4)
├── desktop_app.py         # Aplicação Desktop nativa em PySide6 (Qt 6)
├── desktop_utils.py       # Utilitários de persistência e preview da versão desktop
├── app.py                 # Interface Web com Streamlit
├── video_automate.spec    # Especificação PyInstaller para compilação (Linux e Windows)
├── build_linux.sh         # Script de compilação para executável Linux
├── build_windows.bat      # Script de compilação para executável Windows (.exe)
├── build_windows.ps1      # Script PowerShell de compilação para Windows
├── config_projeto.json    # Configuração data-driven ativa do tutorial
├── config_exemplo.json    # Modelo de referência documentando todas as propriedades
├── gerador_generico.py    # Motor principal modular de edição e processamento
├── gerar_tutorial.py      # Atalho de execução para o gerador
├── requirements.txt       # Dependências do projeto (Web e Desktop)
├── README_DESKTOP.md      # Guia de uso e compilação da versão Desktop
└── README.md              # Documentação completa

```

---

## 🧩 1. Separação de Configuração (Data-Driven)

Toda a definição do tutorial é desacoplada do código, permitindo criar tutoriais para qualquer sistema ou software apenas editando um arquivo JSON (como [config_projeto.json](file:///home/manoel/projetos/video-automate/config_projeto.json) ou [config_exemplo.json](file:///home/manoel/projetos/video-automate/config_exemplo.json)).

### Estrutura do Arquivo JSON:

```json
{
  "titulo_tutorial": "Título do seu Tutorial",
  "configuracoes_gerais": {
    "voz_padrao": "pt-BR-AntonioNeural",
    "taxa_fala_padrao": "+0%",
    "volume_padrao": "+0%",
    "resolucao_padrao": [1920, 1080],
    "fps_padrao": 30,
    "pausa_final_padrao": 0.5,
    "video_saida": "saida/tutorial_final.mp4",
    "manter_audios_temp": false
  },
  "cenas": [
    {
      "id": "passo_01",
      "titulo": "Acesso ao Painel Inicial",
      "video_path": "cenas/01_login.mp4",
      "texto_narracao": "Abra seu navegador e acesse a página inicial do sistema...",
      "voz": "pt-BR-AntonioNeural",
      "overlay_texto": "Passo 1: Autenticação",
      "imagem_destaque": "cenas/logo_moodle.png",
      "pausa_final": 0.5
    }
  ]
}
```

### Propriedades Suportadas por Cena/Passo:

| Campo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :---: | :--- |
| `video_path` ou `imagem_path` | `string` | **Sim** | Caminho para o arquivo de vídeo (.mp4/.webm) OU captura de tela (.png/.jpg). |
| `texto_narracao` | `string` | **Sim** | Texto a ser narrado pela voz neural da IA (mantém a imagem ou congela o vídeo durante a fala). |
| `id` | `string` | Não | Identificador único da cena (ex: `"passo_01"`). |
| `titulo` | `string` | Não | Título descritivo da etapa. |
| `voz` | `string` | Não | Voz específica para este passo (sobrescreve a voz padrão). |
| `taxa_fala` | `string` | Não | Ajuste de velocidade da narração (ex: `"+10%"`, `"-5%"`). |
| `overlay_texto` | `string` ou `dict` | Não | Tarja de texto estilizada (lower-third) com fundo translúcido e barra de acento. |
| `imagem_destaque` | `string` ou `dict` | Não | Imagem (logo, screenshot, badge) a ser sobreposta no vídeo. |
| `pausa_final` | `float` | Não | Intervalo de silêncio (em segundos) após a fala antes da próxima cena. |

#### Configuração Avançada de Overlays:

```json
"overlay_texto": {
  "texto": "Dica Importante: Validação em 2 Etapas",
  "posicao": "inferior_esquerdo",
  "duracao": 5.0
},
"imagem_destaque": {
  "caminho": "cenas/badge_dica.png",
  "posicao": "superior_direito",
  "tamanho_max": [300, 100],
  "duracao": null
}
```

* **Âncoras de Posição suportadas**: `"inferior_esquerdo"`, `"inferior_direito"`, `"inferior_centro"`, `"superior_esquerdo"`, `"superior_direito"`, `"superior_centro"` ou coordenadas exatas `[x, y]`.

---

## ⚙️ 2. Recursos do Motor Modular ([`gerador_generico.py`](file:///home/manoel/projetos/video-automate/gerador_generico.py))

* **Validação Pré-Voo Robusta**: Antes de iniciar o processamento pesado, o motor verifica se todos os vídeos e imagens existem. Caso contrário, exibe um relatório diagnóstico claro apontando exatamente os arquivos faltantes.
* **Padronização Automática de Resolução**: Todos os clipes são convertidos para a resolução especificada (ex: 1920x1080 a 30 FPS). Clipes gravados com proporções diferentes são redimensionados proporcionalmente e centralizados sem distorção sobre fundo preto.
* **Sincronização com Freeze Frame**: Se a narração for mais longa que a gravação da tela, o último quadro é congelado automaticamente até a narração concluir.
* **Vozes Neurais em Português Brasileiro (pt-BR)**:
  * `pt-BR-AntonioNeural` (Masculina - Didática e amigável)
  * `pt-BR-FranciscaNeural` (Feminina - Natural e clara)
  * `pt-BR-ThalitaMultilingualNeural` (Feminina - Multilíngue)

---

## 💻 3. Como Executar

Ative o ambiente virtual:
```bash
source .venv/bin/activate
```

### Execução Padrão (utiliza `config_projeto.json`):
```bash
python gerador_generico.py
```

### Execução Especificando outro Roteiro / Tutorial:
```bash
python gerador_generico.py --config config_exemplo.json
```

### Modo Demonstração / Teste (Criação Automática de Placeholders):
Cria vídeos e imagens provisórias automaticamente para testar o fluxo sem precisar ter as gravações prontas:
```bash
python gerador_generico.py --gerar-placeholders
```

### Listar Vozes Disponíveis:
```bash
python gerador_generico.py --listar-vozes
```

### Sobrescrita Dinâmica via Linha de Comando:
```bash
python gerador_generico.py -c config_projeto.json -o saida/meu_video.mp4 -v pt-BR-FranciscaNeural -t +10%
```

---

## 🌐 4. Interface Web Interativa (Streamlit)

Para utilizar a interface gráfica web intuitiva e dinâmica com upload de capturas de tela, vídeos e pré-visualização em tempo real:

```bash
streamlit run app.py
```
Acesse `http://localhost:8501` no navegador.

