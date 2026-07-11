import os
import time
from pathlib import Path
from dotenv import load_dotenv
from pydub import AudioSegment
import google.generativeai as genai
from openai import OpenAI

# ---------------------------------------------------------
# 1. CONFIGURAÇÕES E CHAVES
# ---------------------------------------------------------
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not GEMINI_API_KEY or not OPENROUTER_API_KEY:
    print("ERRO: As chaves GEMINI_API_KEY e OPENROUTER_API_KEY precisam estar no arquivo .env")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

# Configurar o cliente do OpenRouter usando a biblioteca da OpenAI
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Modelos que vamos utilizar (agora configuráveis no arquivo .env)
GEMINI_TRANSCRIPTION_MODEL = os.getenv("GEMINI_TRANSCRIPTION_MODEL", "gemini-1.5-flash")
OPENROUTER_DIDACTIC_MODEL = os.getenv("OPENROUTER_DIDACTIC_MODEL", "google/gemini-flash-1.5") 

# ---------------------------------------------------------
# 2. CONFIGURAÇÃO DE DIRETÓRIOS
# ---------------------------------------------------------
BASE_DIR = Path(r"D:\Criar aulas")
AUDIOS_DIR = BASE_DIR / "audios_entrada"
CHUNKS_DIR = BASE_DIR / "temp_chunks"
TRANSCRIPTIONS_DIR = BASE_DIR / "transcricoes"
APOSTILAS_DIR = BASE_DIR / "apostilas_prontas"

# Garantir que as pastas existem
for folder in [AUDIOS_DIR, CHUNKS_DIR, TRANSCRIPTIONS_DIR, APOSTILAS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# 3. FUNÇÕES DO SISTEMA
# ---------------------------------------------------------
def split_audio(audio_path, chunk_length_min=20):
    """Fatia o áudio longo em pedaços menores (em minutos) para a API."""
    print(f"[{audio_path.name}] Carregando áudio. Isso pode levar alguns segundos...")
    try:
        audio = AudioSegment.from_mp3(audio_path)
    except Exception as e:
        print(f"Erro ao carregar o áudio. Verifique se o FFmpeg está instalado no Windows: {e}")
        return []
    
    chunk_length_ms = chunk_length_min * 60 * 1000
    chunks = []
    
    for i in range(0, len(audio), chunk_length_ms):
        chunk = audio[i:i + chunk_length_ms]
        chunk_name = CHUNKS_DIR / f"{audio_path.stem}_part{i//chunk_length_ms + 1}.mp3"
        chunk.export(chunk_name, format="mp3")
        chunks.append(chunk_name)
        print(f"  -> Criado fatia: {chunk_name.name}")
        
    return chunks

def transcribe_audio_gemini(audio_path):
    """Envia o arquivo MP3 para a API do Google para extrair o texto."""
    print(f"Enviando {audio_path.name} para o Gemini transcrever...")
    
    # Upload para o File API do Google
    uploaded_file = genai.upload_file(path=str(audio_path))
    
    # Aguardar processamento do áudio no servidor do Google
    while uploaded_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        uploaded_file = genai.get_file(uploaded_file.name)
        
    if uploaded_file.state.name == "FAILED":
        print(f"\nErro ao processar arquivo no Gemini: {audio_path.name}")
        return ""
    
    # Pedir a transcrição para o modelo Flash
    model = genai.GenerativeModel(GEMINI_TRANSCRIPTION_MODEL)
    prompt = "Transcreva este áudio de forma literal, exata e completa em português. Não resuma e não adicione explicações extras."
    
    response = model.generate_content([uploaded_file, prompt])
    
    # Limpar o arquivo do servidor do Google após transcrever
    genai.delete_file(uploaded_file.name)
    
    return response.text

def generate_didactic_booklet(transcription_text):
    """Lê a transcrição completa e gera a apostila estruturada via OpenRouter."""
    print(f"Gerando apostila didática via OpenRouter (Modelo: {OPENROUTER_DIDACTIC_MODEL})...")
    
    system_prompt = (
        "Você é um especialista em design instrucional e artes visuais (foco em fotografia). "
        "Você receberá a transcrição crua de uma palestra/aula. "
        "Transforme essa transcrição em uma apostila didática completa.\n\n"
        "REGRAS ABSOLUTAS:\n"
        "1. Crie exatamente 5 aulas.\n"
        "2. Crie um 'Glossário Técnico' no início com os termos específicos citados.\n"
        "3. Cada aula deve conter: Introdução do conceito, Exemplos práticos citados no áudio e 1 Desafio Prático ao final de cada aula.\n"
        "4. NÃO ALUCINE INFORMAÇÕES. A didática deve ser extraída APENAS da transcrição, sem adicionar temas fotográficos que não foram mencionados.\n"
        "5. Retorne a resposta com uma formatação limpa e profissional em Markdown."
    )
    
    try:
        response = openrouter_client.chat.completions.create(
            model=OPENROUTER_DIDACTIC_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Aqui está a transcrição base:\n\n{transcription_text}"}
            ],
            temperature=0.3 # Temperatura baixa para garantir fidelidade ao texto
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Erro na geração da apostila no OpenRouter: {e}")
        return "Erro ao gerar a apostila."

# ---------------------------------------------------------
# 4. LOOP PRINCIPAL
# ---------------------------------------------------------
def process_pipeline():
    audio_files = list(AUDIOS_DIR.glob("*.mp3"))
    if not audio_files:
        print(f"Nenhum arquivo .mp3 encontrado na pasta: {AUDIOS_DIR}")
        print("Coloque seus áudios lá e rode o script novamente.")
        return

    for audio_path in audio_files:
        print(f"\n=======================================================")
        print(f"🚀 INICIANDO O PROCESSAMENTO: {audio_path.name}")
        print(f"=======================================================")
        
        # Passo 1: Fatiar
        chunk_paths = split_audio(audio_path, chunk_length_min=20)
        if not chunk_paths:
            continue
            
        full_transcription = ""
        
        # Passo 2: Transcrever Fatias
        for chunk_path in chunk_paths:
            text = transcribe_audio_gemini(chunk_path)
            full_transcription += text + "\n\n"
            # Limpar fatia para poupar HD
            os.remove(chunk_path)
            
        # Passo 3: Salvar Transcrição Completa
        transcription_file = TRANSCRIPTIONS_DIR / f"{audio_path.stem}_transcricao.txt"
        with open(transcription_file, "w", encoding="utf-8") as f:
            f.write(full_transcription)
        print(f"✅ Transcrição salva em: {transcription_file.name}")
        
        # Passo 4: Criar Apostila
        booklet_markdown = generate_didactic_booklet(full_transcription)
        
        # Passo 5: Salvar Apostila
        booklet_file = APOSTILAS_DIR / f"{audio_path.stem}_Apostila.md"
        with open(booklet_file, "w", encoding="utf-8") as f:
            f.write(booklet_markdown)
        print(f"✅ Apostila Didática Gerada: {booklet_file.name}")

if __name__ == "__main__":
    process_pipeline()
    print("\n🎉 Todos os áudios foram processados com sucesso!")
