# 🖥️ Gerador Automático de Tutoriais em Vídeo - Versão Desktop

Aplicação Desktop nativa profissional desenvolvida em **PySide6 (Qt 6)** com empacotamento completo para **Linux** e **Windows** via **PyInstaller**.

---

## ✨ Recursos da Versão Desktop

- **100% Nativa e Offline-Ready**: Sem necessidade de abrir navegador ou portas de rede locais.
- **Multithreading Seguro (`QThread`)**: Síntese de áudio (edge-tts) e renderização pesada (MoviePy/FFmpeg) ocorrem em segundo plano sem congelar a interface.
- **Gerenciamento de Cenas Dinâmico**:
  - Reordenação fácil de cenas (▲ Subir / ▼ Descer).
  - Duplicação e exclusão rápida de cenas.
  - Seleção de vídeo ou imagem (captura de tela) por diálogo nativo do sistema operacional.
- **Prévia Instantânea de Áudio**: Ouça a voz sintetizada com edge-tts antes de gerar o vídeo.
- **Prévia Visual em Alta Resolução**: Visualize exatamente como ficará o snapshot do frame com a tarja (lower-third) e a legenda discreta antes de renderizar.
- **Portabilidade de Projetos**:
  - Salvar e carregar arquivos de configuração `.json`.
  - Exportar e importar pacotes completos `.zip` (incluindo todas as gravações e imagens).
- **Ações Rápidas Pós-Renderização**:
  - Reproduzir o vídeo diretamente no player padrão do sistema.
  - Abrir a pasta de saída no gerenciador de arquivos (Nautilus, Dolphin, Windows Explorer).
  - Salvar cópia do arquivo em qualquer pasta do computador.

---

## 🚀 Como Executar em Desenvolvimento

### No Linux:
```bash
# Ative o ambiente virtual
source .venv/bin/activate

# Execute a aplicação Desktop
python desktop_app.py
```

### No Windows:
```cmd
# Ative o ambiente virtual
.venv\Scripts\activate

# Execute a aplicação Desktop
python desktop_app.py
```

---

## 📦 Como Compilar Executáveis Nativos

O projeto inclui o arquivo de configuração [`video_automate.spec`](file:///home/manoel/projetos/video-automate/video_automate.spec) já configurado para embutir automaticamente os binários do **FFmpeg** (`imageio_ffmpeg`) e os certificados de segurança SSL (`certifi`). O usuário final que receber o executável **não precisa ter Python ou FFmpeg instalados**.

### 1. Compilação no Linux:
Basta executar o script:
```bash
chmod +x build_linux.sh
./build_linux.sh
```
O executável final autocontido será gerado em:
```text
dist/VideoAutomate
```
Para rodar:
```bash
./dist/VideoAutomate
```

---

### 2. Compilação no Windows:
No Windows (Prompt de Comando ou PowerShell), execute:
```cmd
build_windows.bat
```
ou pelo PowerShell:
```powershell
.\build_windows.ps1
```
O executável `.exe` final será gerado em:
```text
dist\VideoAutomate.exe
```

---

### 3. Compilação Automática na Nuvem (GitHub Actions)
O repositório já conta com o workflow [`.github/workflows/build.yml`](file:///home/manoel/projetos/video-automate/.github/workflows/build.yml). Ao enviar (`git push`) seu código para o GitHub, os executáveis para **Linux** (`VideoAutomate-linux`) e **Windows** (`VideoAutomate-windows.exe`) são gerados e disponibilizados automaticamente na aba **Actions** do seu repositório para download.
