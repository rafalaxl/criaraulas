# 🎓 Gerador de Apostilas Didáticas (Transcritor IA)

Este é um sistema automatizado em Python que pega áudios longos (aulas, palestras, podcasts), transcreve o conteúdo de forma precisa e utiliza Inteligência Artificial para estruturar esse conhecimento em uma **Apostila Didática** de 5 aulas, baseando-se estritamente no conteúdo do áudio (sem alucinar dados externos).

Desenvolvido com foco inicial em cursos de **Fotografia e Artes Visuais**, mas facilmente adaptável para qualquer tema.

## 🛠️ Como funciona?
1. **Fatiamento (Chunking):** O sistema fatia arquivos grandes de MP3 (ex: 2 horas) em pedaços de 20 minutos usando `pydub`.
2. **Transcrição (Audio-to-Text):** Envia as fatias para a API do Google Gemini (ultra-rápido para áudios) para extrair o texto de forma fiel.
3. **Didática (Text-to-Booklet):** Pega a transcrição inteira e envia para um modelo de longo contexto no OpenRouter (ex: Gemini Flash ou Claude) pedindo a formatação de um Glossário e 5 aulas contendo teoria, exemplos do áudio e um Desafio Prático.
4. **Saída:** Entrega a apostila prontinha em formato Markdown (`.md`) na pasta de resultados.

---

## ⚙️ Pré-requisitos

Para rodar este projeto na sua máquina, você vai precisar de:
1. **Python 3.8+** instalado.
2. **FFmpeg** instalado na máquina (essencial para o `pydub` fatiar o áudio).
3. Chaves de API do **Google Gemini** e do **OpenRouter**.

### Como instalar o FFmpeg no Windows:
1. Baixe a build do FFmpeg em [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (baixar o `.zip` da release).
2. Extraia o arquivo `.zip`.
3. Copie os arquivos `ffmpeg.exe` e `ffprobe.exe` (dentro da pasta `bin`) e coloque na **mesma pasta deste script** ou adicione a pasta `bin` nas Variáveis de Ambiente (`PATH`) do Windows.

---

## 🚀 Como instalar e rodar

### 1. Clonando o Repositório e Preparando o Ambiente
Abra seu terminal e rode:
```bash
# Clone este repositório
git clone https://github.com/rafalaxl/criaraulas.git
cd criaraulas

# Instale as dependências do Python
pip install -r requirements.txt
```

### 2. Configurando as Chaves de API
1. Na pasta do projeto, você verá um arquivo chamado `.env.example`.
2. Renomeie ele para `.env` (ou apenas copie o conteúdo e crie um `.env`).
3. Abra o arquivo `.env` e coloque as suas chaves e escolha o modelo desejado:

```env
# Chaves de API
GEMINI_API_KEY="sua_chave_gemini_aqui"
OPENROUTER_API_KEY="sua_chave_openrouter_aqui"

# Escolha de Modelos (Altere para testar outras IAs)
GEMINI_TRANSCRIPTION_MODEL="gemini-1.5-flash"
OPENROUTER_DIDACTIC_MODEL="google/gemini-flash-1.5"
```

### 3. Usando o Sistema
1. Jogue seus arquivos `.mp3` de aula dentro da pasta `audios_entrada/`.
2. No terminal, execute o programa:
```bash
python main.py
```
3. Acompanhe os logs no terminal. Ao final do processamento, a transcrição em texto puro estará salva na pasta `transcricoes/` e as suas apostilas estruturadas estarão prontas na pasta `apostilas_prontas/`.

---

## 🔧 Personalização
Se desejar alterar as regras didáticas (ex: mudar para 10 aulas, alterar o estilo do desafio prático, mudar de área de conhecimento), basta abrir o arquivo `main.py` e editar o bloco de texto na variável `system_prompt` da função `generate_didactic_booklet()`.
