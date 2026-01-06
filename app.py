"""
Gerador de Anuncios - ODUO
Ferramenta interna para geração de anúncios e títulos para Google Ads.
- Data Hunter: Scraper de Google Autocomplete (A-Z)
- Ad-Intelligence: Análise de intenção + Modelagem de anúncios vencedores
"""

import os
import json
import random
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
import string

# Lista de User-Agents para simular navegadores reais
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
]

load_dotenv()

app = Flask(__name__)

# =============================================================================
# CONFIGURAÇÃO PARA CLOUDFLARE / PROXY REVERSO
# =============================================================================
# ProxyFix corrige headers quando app roda atrás de proxy (Cloudflare, nginx, etc)
# x_for=1: confia no header X-Forwarded-For (IP real do cliente)
# x_proto=1: confia no header X-Forwarded-Proto (http/https)
# x_host=1: confia no header X-Forwarded-Host (domínio original)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# CORS configurado para aceitar requisições do seu domínio
# Em produção, defina ALLOWED_ORIGINS no .env (ex: "https://meudominio.com.br,https://www.meudominio.com.br")
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
CORS(app, origins=allowed_origins, supports_credentials=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# =============================================================================
# DATA HUNTER - Scraper de Google Autocomplete
# =============================================================================

def get_google_autocomplete(query: str) -> list:
    """Busca sugestões do Google Autocomplete para uma query."""
    url = "http://suggestqueries.google.com/complete/search"
    params = {
        "client": "firefox",
        "q": query,
        "hl": "pt-BR"
    }

    # User-Agent aleatório para simular navegador real
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com.br/",
        "DNT": "1"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if len(data) > 1 and isinstance(data[1], list):
                return data[1]
    except Exception as e:
        print(f"Erro no autocomplete: {e}")

    return []


def scrape_autocomplete_az(ramo: str, localizacao: str = "") -> list:
    """Faz varredura de A-Z no Google Autocomplete para um ramo com localização."""
    all_suggestions = set()

    # Define a base da query com ou sem localização
    base_query = f"{ramo} em {localizacao}" if localizacao else ramo

    # Busca base (sem letra)
    base_suggestions = get_google_autocomplete(base_query)
    all_suggestions.update(base_suggestions)

    # Busca com cada letra do alfabeto
    for letter in string.ascii_lowercase:
        query = f"{base_query} {letter}"
        suggestions = get_google_autocomplete(query)
        all_suggestions.update(suggestions)

    # Busca com variações comuns (com localização)
    variations = [
        f"{ramo} em {localizacao} como",
        f"{ramo} em {localizacao} onde",
        f"{ramo} em {localizacao} qual",
        f"{ramo} em {localizacao} quanto",
        f"{ramo} em {localizacao} melhor",
        f"{ramo} em {localizacao} preço",
        f"{ramo} {localizacao}",
        f"comprar {ramo} em {localizacao}",
        f"contratar {ramo} em {localizacao}",
        f"alugar {ramo} em {localizacao}",
        f"{ramo} barato em {localizacao}",
        f"{ramo} perto {localizacao}",
        f"melhor {ramo} em {localizacao}",
        f"{ramo} {localizacao} preço",
    ] if localizacao else [
        f"{ramo} como",
        f"{ramo} onde",
        f"{ramo} qual",
        f"{ramo} quanto",
        f"{ramo} melhor",
        f"{ramo} preço",
        f"comprar {ramo}",
        f"contratar {ramo}",
        f"alugar {ramo}",
        f"{ramo} barato",
        f"{ramo} perto"
    ]

    for variation in variations:
        suggestions = get_google_autocomplete(variation)
        all_suggestions.update(suggestions)

    # Remove duplicatas e retorna lista ordenada
    return sorted(list(all_suggestions))


# =============================================================================
# AD-INTELLIGENCE - Análise e Modelagem de Anúncios
# =============================================================================

SYSTEM_PROMPT_AD_INTELLIGENCE = """Você é um Especialista em Google Ads e Meta Ads com 15 anos de experiência em Performance.
Sua especialidade é "Ad Modeling": analisar dados reais de busca e criar anúncios baseados nos padrões que historicamente dominam o topo das pesquisas.

SUA MISSÃO:
O usuário fornecerá uma lista de "Palavras-Chave Reais" extraídas do Google Autocomplete, os dados do cliente (Oferta, Nome, Nicho) e a LOCALIZAÇÃO do negócio.
Você deve processar esses dados e retornar um plano de guerra para o Gestor de Tráfego.

REGRAS DE FILTRAGEM POR LOCALIZAÇÃO:
- IGNORE qualquer palavra-chave que mencione cidades ou estados DIFERENTES da localização informada pelo usuário.
- Priorize palavras-chave que contenham a localização do cliente ou que sejam genéricas (sem cidade).
- Se uma keyword mencionar "São Paulo" mas o cliente é de "Curitiba", DESCARTE essa keyword.

REGRAS DE MODELAGEM (O QUE COPIAR DOS VENCEDORES):
1. RELEVÂNCIA MÁXIMA: O Título 1 do anúncio DEVE conter a palavra-chave real mais pesquisada (da localização correta).
2. GATILHOS DE CLIQUE (CTR): Use gatilhos de Urgência, Curiosidade ou Benefício Imediato que são padrão em anúncios de alta performance.
3. FORMATO DE TEXTO LONGO: As descrições devem ter entre 4 a 6 linhas, formatadas com quebras de linha para aumentar a legibilidade e o "scroll stop".
4. LOCALIZAÇÃO NOS ANÚNCIOS: Inclua a cidade/região do cliente nos anúncios quando fizer sentido (ex: "em Curitiba", "na região").

ESTRUTURA DE RESPOSTA (JSON PURO):
Retorne um array JSON onde cada objeto represente um "Grupo de Anúncios Profissional":
[
  {
    "termo_real": "A palavra-chave que originou a ideia",
    "intencao": "Fundo, Meio ou Topo de Funil",
    "anuncio_vencedor": {
      "titulo": "Título impactante (max 40 carac.)",
      "descricao": "Texto longo e persuasivo (4+ linhas) focado em conversão",
      "cta": "Chamada para ação matadora"
    },
    "por_que_funciona": "Explicação técnica do porquê esse padrão converte"
  }
]

REQUISITOS TÉCNICOS:
- Proibido usar "IA-speak" (palavras como 'revolucionário', 'potencialize', 'descubra').
- Use português brasileiro coloquial e focado em vendas (Direct Response).
- Gere EXATAMENTE 5 variações de anúncios vencedores.
- Retorne APENAS o JSON bruto, sem explicações fora do código.
- Sem markdown, sem ```json, apenas o array JSON puro."""


def analyze_and_model_ads(keywords: list, oferta: str, cliente: str, nicho: str, localizacao: str = "") -> list:
    """Analisa palavras-chave reais e modela anúncios vencedores usando GPT-4o."""

    # Limita a lista de keywords para não estourar o contexto
    keywords_sample = keywords[:50] if len(keywords) > 50 else keywords
    keywords_str = "\n".join([f"- {kw}" for kw in keywords_sample])

    localizacao_info = f"\n- LOCALIZAÇÃO: {localizacao}" if localizacao else ""

    user_prompt = f"""DADOS DO CLIENTE:
- OFERTA: {oferta}
- NOME/EMPRESA: {cliente}
- NICHO/PÚBLICO: {nicho}{localizacao_info}

PALAVRAS-CHAVE REAIS (extraídas do Google Autocomplete):
{keywords_str}

IMPORTANTE: A localização do cliente é "{localizacao}". Ignore keywords que mencionem outras cidades/estados.

Analise essas palavras-chave reais, identifique as com maior intenção de compra, e crie 5 anúncios vencedores baseados nos padrões que dominam o topo do Google Ads.

Retorne APENAS o JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_AD_INTELLIGENCE},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=3000,
            temperature=0.7
        )

        response_text = response.choices[0].message.content.strip()

        # Remove marcadores markdown se presentes
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()
        ads_data = json.loads(response_text)

        # Valida e limpa os dados
        validated_ads = []
        for ad in ads_data:
            validated_ad = {
                "termo_real": ad.get("termo_real", "")[:100],
                "intencao": ad.get("intencao", "Meio de Funil"),
                "anuncio_vencedor": {
                    "titulo": ad.get("anuncio_vencedor", {}).get("titulo", "")[:40],
                    "descricao": ad.get("anuncio_vencedor", {}).get("descricao", "")[:500],
                    "cta": ad.get("anuncio_vencedor", {}).get("cta", "")[:25]
                },
                "por_que_funciona": ad.get("por_que_funciona", "")[:300]
            }
            validated_ads.append(validated_ad)

        return validated_ads

    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao processar resposta da IA: {str(e)}")
    except Exception as e:
        raise Exception(f"Erro na comunicação com a API: {str(e)}")


# =============================================================================
# IA FALLBACK - Geração de Keywords quando o scraper falha
# =============================================================================

SYSTEM_PROMPT_KEYWORDS_FALLBACK = """Você é um Especialista em Google Ads com 15 anos de experiência em Keyword Research.
Sua missão é gerar uma lista de PALAVRAS-CHAVE DE ALTO VOLUME para um determinado nicho e localização.

CONTEXTO:
O scraper de Google Autocomplete não retornou resultados. Você deve usar seu conhecimento de mercado para gerar
as palavras-chave que PROVAVELMENTE têm maior volume de busca nesse segmento.

REGRAS:
1. Gere 20 palavras-chave relevantes para o ramo/oferta
2. Inclua variações com a localização informada
3. Misture termos de fundo, meio e topo de funil
4. Use padrões reais de busca (ex: "preço", "melhor", "perto de mim", "como funciona")
5. Foque em termos com intenção comercial

ESTRUTURA DE RESPOSTA (JSON PURO):
{
  "keywords": [
    "palavra-chave 1",
    "palavra-chave 2",
    ...
  ]
}

Retorne APENAS o JSON bruto, sem markdown, sem explicações."""


def generate_ai_keywords(ramo: str, localizacao: str, oferta: str, nicho: str) -> list:
    """Gera keywords usando IA quando o scraper falha."""

    user_prompt = f"""Gere 20 palavras-chave de alto volume para:

RAMO: {ramo}
LOCALIZAÇÃO: {localizacao}
OFERTA: {oferta}
NICHO/PÚBLICO: {nicho}

Inclua variações com e sem a localização. Foque em termos que um potencial cliente buscaria no Google.

Retorne APENAS o JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_KEYWORDS_FALLBACK},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )

        response_text = response.choices[0].message.content.strip()

        # Remove marcadores markdown se presentes
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()
        data = json.loads(response_text)

        return data.get("keywords", [])

    except Exception as e:
        print(f"Erro ao gerar keywords com IA: {e}")
        # Fallback final: retorna keywords genéricas baseadas nos inputs
        return [
            f"{ramo} em {localizacao}",
            f"{oferta} {localizacao}",
            f"melhor {ramo} em {localizacao}",
            f"{ramo} preço",
            f"contratar {ramo}",
            f"{oferta} perto de mim",
            f"{ramo} barato",
            f"onde encontrar {ramo}",
            f"{oferta} orçamento",
            f"{nicho} {localizacao}"
        ]


# =============================================================================
# ATIVOS MASSIVOS - Geração de Títulos e Descrições para Google Ads Responsivo
# =============================================================================

SYSTEM_PROMPT_ASSETS = """Você é um Especialista em Google Ads com foco em Anúncios Responsivos de Pesquisa (RSA).
Sua missão é gerar ATIVOS DE ALTA PERFORMANCE para campanhas de busca.

CONTEXTO:
O usuário fornecerá a oferta, localização, e opcionalmente palavras-chave reais do Google.
Você deve gerar ativos otimizados para máximo CTR e Quality Score.

REGRAS PARA TÍTULOS (15 títulos, máximo 30 caracteres cada):
1. Variação de gatilhos: Benefício, Urgência, Curiosidade, Prova Social, Localização
2. Incluir a palavra-chave principal em pelo menos 5 títulos
3. Incluir a localização em pelo menos 3 títulos
4. Usar números quando possível (ex: "10 Anos de Experiência")
5. CTAs curtos em alguns títulos (ex: "Peça Orçamento Grátis")
6. NUNCA ultrapassar 30 caracteres (incluindo espaços)

REGRAS PARA DESCRIÇÕES (4 descrições, máximo 90 caracteres cada):
1. Complementar os títulos com mais detalhes
2. Incluir benefícios específicos e diferenciais
3. Usar gatilhos de urgência ou escassez quando apropriado
4. Incluir CTA claro em cada descrição
5. NUNCA ultrapassar 90 caracteres (incluindo espaços)

ESTRUTURA DE RESPOSTA (JSON PURO):
{
  "titulos": [
    "Título 1 aqui (max 30)",
    "Título 2 aqui (max 30)",
    ... (15 títulos)
  ],
  "descricoes": [
    "Descrição 1 aqui com mais detalhes e CTA (max 90)",
    "Descrição 2 aqui com mais detalhes e CTA (max 90)",
    "Descrição 3 aqui com mais detalhes e CTA (max 90)",
    "Descrição 4 aqui com mais detalhes e CTA (max 90)"
  ]
}

REQUISITOS TÉCNICOS:
- Português brasileiro coloquial e persuasivo
- Proibido "IA-speak" (revolucionário, potencialize, descubra)
- Retorne APENAS o JSON bruto, sem markdown, sem explicações
- RESPEITE RIGOROSAMENTE os limites de caracteres"""


def generate_responsive_assets(oferta: str, localizacao: str, ramo: str, keywords: list | None = None) -> dict:
    """Gera 15 títulos e 4 descrições para Anúncios Responsivos do Google."""

    keywords_info = ""
    if keywords and len(keywords) > 0:
        top_keywords = keywords[:10]
        keywords_info = f"\n\nPALAVRAS-CHAVE REAIS (use como base):\n" + "\n".join([f"- {kw}" for kw in top_keywords])

    user_prompt = f"""Gere ativos para Anúncio Responsivo de Pesquisa:

OFERTA: {oferta}
LOCALIZAÇÃO: {localizacao}
RAMO: {ramo}{keywords_info}

Gere:
- 15 TÍTULOS (máximo 30 caracteres cada)
- 4 DESCRIÇÕES (máximo 90 caracteres cada)

Retorne APENAS o JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ASSETS},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2000,
            temperature=0.8
        )

        response_text = response.choices[0].message.content.strip()

        # Remove marcadores markdown se presentes
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()
        assets_data = json.loads(response_text)

        # Valida e trunca os ativos
        validated_titles = []
        for titulo in assets_data.get("titulos", [])[:15]:
            validated_titles.append(titulo[:30])

        validated_descriptions = []
        for desc in assets_data.get("descricoes", [])[:4]:
            validated_descriptions.append(desc[:90])

        return {
            "titulos": validated_titles,
            "descricoes": validated_descriptions
        }

    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao processar resposta da IA: {str(e)}")
    except Exception as e:
        raise Exception(f"Erro na comunicação com a API: {str(e)}")


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.route("/generate_assets", methods=["POST"])
def generate_assets():
    """Endpoint para gerar ativos massivos para Google Ads Responsivo."""

    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({
            "success": False,
            "error": "API Key da OpenAI não configurada. Verifique o arquivo .env"
        }), 500

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "error": "Nenhum dado enviado na requisição"
        }), 400

    oferta = data.get("oferta", "").strip()
    localizacao = data.get("localizacao", "").strip()
    ramo = data.get("ramo", "").strip()
    keywords = data.get("keywords", [])

    if not oferta:
        return jsonify({"success": False, "error": "O campo 'oferta' é obrigatório"}), 400
    if not localizacao:
        return jsonify({"success": False, "error": "O campo 'localizacao' é obrigatório"}), 400
    if not ramo:
        return jsonify({"success": False, "error": "O campo 'ramo' é obrigatório"}), 400

    try:
        assets = generate_responsive_assets(oferta, localizacao, ramo, keywords)
        return jsonify({"success": True, "data": assets})

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/hunt_keywords", methods=["POST"])
def hunt_keywords():
    """Endpoint Data Hunter: Scrape de autocomplete A-Z."""

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "error": "Nenhum dado enviado na requisição"
        }), 400

    ramo = data.get("ramo", "").strip()

    if not ramo:
        return jsonify({"success": False, "error": "O campo 'ramo' é obrigatório"}), 400

    try:
        keywords = scrape_autocomplete_az(ramo)
        return jsonify({
            "success": True,
            "data": {
                "ramo": ramo,
                "total": len(keywords),
                "keywords": keywords
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/generate_winning_ads", methods=["POST"])
def generate_winning_ads():
    """Endpoint Ad-Intelligence: Análise + Modelagem de anúncios vencedores."""

    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({
            "success": False,
            "error": "API Key da OpenAI não configurada. Verifique o arquivo .env"
        }), 500

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "error": "Nenhum dado enviado na requisição"
        }), 400

    keywords = data.get("keywords", [])
    oferta = data.get("oferta", "").strip()
    cliente = data.get("cliente", "").strip()
    nicho = data.get("nicho", "").strip()

    if not keywords:
        return jsonify({"success": False, "error": "A lista de 'keywords' é obrigatória"}), 400
    if not oferta:
        return jsonify({"success": False, "error": "O campo 'oferta' é obrigatório"}), 400
    if not cliente:
        return jsonify({"success": False, "error": "O campo 'cliente' é obrigatório"}), 400
    if not nicho:
        return jsonify({"success": False, "error": "O campo 'nicho' é obrigatório"}), 400

    try:
        ads = analyze_and_model_ads(keywords, oferta, cliente, nicho)
        return jsonify({"success": True, "data": ads})

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/full_pipeline", methods=["POST"])
def full_pipeline():
    """Endpoint completo: Data Hunter + Ad-Intelligence com lógica de cascata."""

    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({
            "success": False,
            "error": "API Key da OpenAI não configurada. Verifique o arquivo .env"
        }), 500

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "error": "Nenhum dado enviado na requisição"
        }), 400

    ramo = data.get("ramo", "").strip()
    localizacao = data.get("localizacao", "").strip()
    oferta = data.get("oferta", "").strip()
    cliente = data.get("cliente", "").strip()
    nicho = data.get("nicho", "").strip()

    if not ramo:
        return jsonify({"success": False, "error": "O campo 'ramo' é obrigatório"}), 400
    if not localizacao:
        return jsonify({"success": False, "error": "O campo 'localizacao' é obrigatório"}), 400
    if not oferta:
        return jsonify({"success": False, "error": "O campo 'oferta' é obrigatório"}), 400
    if not cliente:
        return jsonify({"success": False, "error": "O campo 'cliente' é obrigatório"}), 400
    if not nicho:
        return jsonify({"success": False, "error": "O campo 'nicho' é obrigatório"}), 400

    try:
        keywords = []
        fallback_mode = None  # None, "sem_localizacao", "ia_prediction"

        # =============================================
        # CASCATA DE FALLBACK
        # =============================================

        # Tentativa 1: Scraper com Ramo + Localização
        print(f"[Pipeline] Tentativa 1: Scraper com '{ramo}' em '{localizacao}'")
        keywords = scrape_autocomplete_az(ramo, localizacao)

        # Tentativa 2: Scraper apenas com Ramo (sem localização)
        if not keywords:
            print(f"[Pipeline] Tentativa 2: Scraper apenas com '{ramo}'")
            fallback_mode = "sem_localizacao"
            keywords = scrape_autocomplete_az(ramo, "")

        # Tentativa 3: IA como backup final
        if not keywords:
            print(f"[Pipeline] Tentativa 3: Gerando keywords com IA")
            fallback_mode = "ia_prediction"
            keywords = generate_ai_keywords(ramo, localizacao, oferta, nicho)

        # Se ainda assim não tiver keywords, usa fallback hardcoded
        if not keywords:
            keywords = [
                f"{ramo} em {localizacao}",
                f"{oferta}",
                f"melhor {ramo}",
                f"{ramo} preço",
                f"contratar {ramo}"
            ]
            fallback_mode = "ia_prediction"

        # =============================================
        # PROCESSAMENTO DOS ANÚNCIOS
        # =============================================

        # Step 2: Ad-Intelligence (com localização)
        ads = analyze_and_model_ads(keywords, oferta, cliente, nicho, localizacao)

        # Monta resposta com info de fallback
        response_data = {
            "success": True,
            "data": {
                "keywords": {
                    "ramo": ramo,
                    "localizacao": localizacao,
                    "total": len(keywords),
                    "list": keywords,
                    "source": "google_autocomplete" if fallback_mode is None else fallback_mode
                },
                "ads": ads,
                "fallback_used": fallback_mode
            }
        }

        # Adiciona mensagem explicativa se usou fallback
        if fallback_mode == "sem_localizacao":
            response_data["data"]["fallback_message"] = f"Busca expandida: resultados para '{ramo}' em todo o Brasil"
        elif fallback_mode == "ia_prediction":
            response_data["data"]["fallback_message"] = "Palavras-chave geradas por IA (Previsão de Alto Volume)"

        return jsonify(response_data)

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# ROTAS GERAIS
# =============================================================================

@app.route("/health", methods=["GET"])
def health_check():
    """Endpoint de health check."""
    return jsonify({
        "status": "healthy",
        "service": "Gerador de Anuncios",
        "version": "1.0.0",
        "tools": ["Data Hunter", "Ad-Intelligence"]
    })


@app.route("/")
def serve_frontend():
    
    """Serve o frontend index.html na rota raiz."""
    return send_from_directory(".", "index.html")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Gerador De Anuncios e Titulos")
    print("="*60)
    print("📍 Servidor: http://localhost:5000")
    print("📡 Endpoints:")
    print("   POST /hunt_keywords        - Data Hunter (Scraper A-Z)")
    print("   POST /generate_winning_ads - Ad-Intelligence (GPT-4o)")
    print("   POST /full_pipeline        - Pipeline Completo")
    print("   GET  /health               - Health check")
    print("="*60)
    print("🔧 Ferramentas:")
    print("   🔍 Data Hunter     - Scraper Google Autocomplete A-Z")
    print("   🧠 Ad-Intelligence - Modelagem de Anúncios Vencedores")
    print("="*60 + "\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
