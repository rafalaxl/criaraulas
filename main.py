import os
import time
from pathlib import Path
from dotenv import load_dotenv
from pydub import AudioSegment
from google import genai
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

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

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
# Pega o diretório exato onde este arquivo main.py está rodando
BASE_DIR = Path(__file__).parent.resolve()

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
    
    # Upload para o File API do Google usando o novo SDK google-genai
    uploaded_file = gemini_client.files.upload(file=audio_path)
    
    # Aguardar processamento do áudio no servidor do Google
    file_info = gemini_client.files.get(name=uploaded_file.name)
    while file_info.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        file_info = gemini_client.files.get(name=uploaded_file.name)
        
    if file_info.state.name == "FAILED":
        print(f"\nErro ao processar arquivo no Gemini: {audio_path.name}")
        return ""
    
    # Pedir a transcrição usando o novo SDK
    prompt = "Transcreva este áudio de forma literal, exata e completa em português. Não resuma e não adicione explicações extras."
    response = gemini_client.models.generate_content(
        model=GEMINI_TRANSCRIPTION_MODEL,
        contents=[prompt, uploaded_file]
    )
    
    # Limpar o arquivo do servidor do Google após transcrever
    gemini_client.files.delete(name=uploaded_file.name)
    
    return response.text

def generate_didactic_booklet(transcription_text):
    """Lê a transcrição completa e gera a apostila estruturada via OpenRouter."""
    print(f"Gerando apostila didática via OpenRouter (Modelo: {OPENROUTER_DIDACTIC_MODEL})...")
    
    system_prompt = (
        "Você é um especialista em design instrucional e artes visuais (foco em fotografia). "
        "Sua tarefa é transformar uma transcrição de aula em uma apostila didática de alto nível, "
        "altamente profissional, limpa e pronta para entrega direta aos alunos.\n\n"
        "REGRAS DE REDAÇÃO E TOM DE VOZ:\n"
        "1. IMPESSOALIDADE TOTAL: Remova TODAS as marcas de oralidade, digressões e referências pessoais "
        "do professor (ex: remova 'eu sou o professor Valter...', 'eu vi um filme...', 'como eu disse...', 'gente', 'né'). "
        "O texto deve ser escrito em tom didático, técnico, impessoal e formal.\n"
        "2. REESCRITA DIDÁTICA: Reescreva o conteúdo com palavras próprias do material didático, mas mantendo "
        "100% dos conceitos técnicos e termos originais do áudio.\n\n"
        "REGRAS DE ESTRUTURA (OBRIGATÓRIO USAR MARKDOWN):\n"
        "1. ESTRUTURA GERAL: Crie exatamente 5 aulas.\n"
        "2. GLOSSÁRIO TÉCNICO (INÍCIO): Apresente os termos técnicos citados no áudio organizados em uma TABELA "
        "contendo as colunas 'Termo' e 'Definição'. Não use listas simples com travessão.\n"
        "3. CONCEITOS E EXPLICAÇÕES: Divida cada aula em seções numeradas, com subtítulos claros e explicações diretas.\n"
        "4. INTEGRAÇÃO DE EXEMPLOS: Não crie uma seção isolada de exemplos. Integre os exemplos práticos citados no áudio "
        "diretamente no corpo do texto explicativo utilizando tabelas ou blocos de destaque (quote blocks `>`).\n"
        "5. INFORMAÇÕES TÉCNICAS EM TABELAS: Sempre que houver especificações técnicas (ex: Diafragma, Obturador, Lentes, "
        "valores de ISO, velocidades, etc.), organize essas informações em tabelas comparativas para facilitar o estudo.\n"
        "6. TABELA-RESUMO (RECAPITULAÇÃO): Ao final da apostila, crie uma tabela-resumo que recapitula todos os temas e "
        "conceitos-chave abordados ao longo das 5 aulas.\n"
        "7. DESAFIOS PRÁTICOS ATUALIZADOS: Ao final de cada aula, inclua um desafio prático contendo instruções "
        "passo a passo extremamente claras, sequenciais e acionáveis para o aluno realizar.\n"
        "8. RESTRIÇÃO ABSOLUTA: Baseie-se 100% apenas no conteúdo transcrito. É proibido introduzir conceitos ou técnicas "
        "que não foram falados no áudio original.\n\n"
        "Formate todo o resultado em Markdown de forma muito elegante e visualmente agradável."
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
