"""
GrowthBlast AI v2.0 - Backend Flask
Suite de ferramentas para Growth Team:
- KeyBlast: Gerador de Palavras-Chave Estratégicas
- AdBlast: Gerador de Anúncios com Imagens (DALL-E 3)
"""

import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# Inicializa o cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# =============================================================================
# KEYBLAST - Gerador de Palavras-Chave
# =============================================================================

SYSTEM_PROMPT_KEYWORDS = """Você é um Especialista em Google Ads com foco em Keyword Research e ROI.
Seu trabalho é extrair as palavras-chave com maior potencial de conversão para campanhas de tráfego pago.

CONTEXTO DE EXECUÇÃO:
O usuário fornecerá: Nicho/Ramo, Produto/Oferta e Localização.
Você deve analisar a "Intenção do Usuário" para cada termo e classificar por etapa do funil.

REGRAS DE ANÁLISE:
1. Para cada palavra-chave, avalie:
   - CONCORRÊNCIA: Estime como "Baixa", "Média" ou "Alta" baseado na competitividade do termo
   - CORRESPONDÊNCIA: Sugira "Exata", "Frase" ou "Ampla" baseado na especificidade do termo

2. ESTRUTURA DE FUNIL:
   - FUNDO DE FUNIL (Intenção de Compra): Termos de quem JÁ QUER COMPRAR
     Exemplos: "comprar [produto]", "[produto] preço", "contratar [serviço]", "[produto] promoção"

   - MEIO DE FUNIL (Comparação/Pesquisa): Termos de quem está BUSCANDO SOLUÇÃO
     Exemplos: "melhor [produto]", "[produto] vs [concorrente]", "[produto] vale a pena", "como escolher [produto]"

   - TOPO DE FUNIL (Curiosidade/Problema): Termos para ATRAIR NOVOS PÚBLICOS
     Exemplos: "o que é [tema]", "como [resolver problema]", "dicas de [tema]", "[problema] sintomas"

3. QUANTIDADE:
   - Gere 8-10 palavras para CADA etapa do funil (total: 24-30 palavras)

4. LOCALIZAÇÃO:
   - Adapte os termos para o mercado indicado (Brasil, Portugal, etc.)
   - Use variações regionais quando aplicável

REQUISITO TÉCNICO DE SAÍDA:
Retorne EXCLUSIVAMENTE um objeto JSON puro, sem blocos de código markdown (sem ```json), sem explicações.

Formato obrigatório:
{
  "fundo_funil": [
    {"keyword": "termo aqui", "concorrencia": "Baixa|Média|Alta", "correspondencia": "Exata|Frase|Ampla"}
  ],
  "meio_funil": [
    {"keyword": "termo aqui", "concorrencia": "Baixa|Média|Alta", "correspondencia": "Exata|Frase|Ampla"}
  ],
  "topo_funil": [
    {"keyword": "termo aqui", "concorrencia": "Baixa|Média|Alta", "correspondencia": "Exata|Frase|Ampla"}
  ]
}
"""


def generate_keywords_with_openai(nicho: str, produto: str, localizacao: str) -> dict:
    """Gera palavras-chave estratégicas usando GPT-4o."""

    user_prompt = f"""Gere palavras-chave estratégicas para:

NICHO/RAMO: {nicho}
PRODUTO/OFERTA: {produto}
LOCALIZAÇÃO: {localizacao}

Lembre-se:
- Retorne APENAS o objeto JSON
- Gere 8-10 palavras para CADA etapa do funil
- Adapte os termos para o mercado {localizacao}
- Foque em termos com potencial real de conversão"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_KEYWORDS},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2000,
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
        keywords_data = json.loads(response_text)

        # Valida estrutura
        required_keys = ["fundo_funil", "meio_funil", "topo_funil"]
        for key in required_keys:
            if key not in keywords_data:
                keywords_data[key] = []

        return keywords_data

    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao processar resposta da IA: {str(e)}")
    except Exception as e:
        raise Exception(f"Erro na comunicação com a API: {str(e)}")


@app.route("/generate_keywords", methods=["POST"])
def generate_keywords():
    """Endpoint para gerar palavras-chave estratégicas."""

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

    nicho = data.get("nicho", "").strip()
    produto = data.get("produto", "").strip()
    localizacao = data.get("localizacao", "Brasil").strip()

    if not nicho:
        return jsonify({"success": False, "error": "O campo 'nicho' é obrigatório"}), 400
    if not produto:
        return jsonify({"success": False, "error": "O campo 'produto' é obrigatório"}), 400

    try:
        keywords_data = generate_keywords_with_openai(nicho, produto, localizacao)
        return jsonify({"success": True, "data": keywords_data})

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 422
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# ADBLAST - Gerador de Anúncios com Imagens
# =============================================================================

CHAR_LIMITS = {
    "titulo": 40,
    "descricao": 250,
    "cta": 20
}

SYSTEM_PROMPT_ADS = """Você é um Copywriter Sênior e Estrategista de Tráfego Pago especialista em Direct Response para o mercado brasileiro. Sua especialidade é criar anúncios para Meta Ads (Facebook/Instagram) que param o scroll e geram cliques qualificados.

CONTEXTO DE EXECUÇÃO:
O usuário fornecerá: Cliente, Oferta, Função/Nicho e opcionalmente um Estilo Visual.
Use os frameworks AIDA (Atenção, Interesse, Desejo, Ação) e PAS (Problema, Agitação, Solução).

REGRAS RÍGIDAS DE CONTEÚDO E FORMATO:
1. QUANTIDADE: Gere exatamente 5 variações distintas.
2. LIMITES TÉCNICOS (NÃO ULTRAPASSE):
   - TÍTULO: Máximo 40 caracteres (Direto e impactante).
   - DESCRIÇÃO: Máximo 250 caracteres (Texto mais detalhado, 5-6 linhas, com storytelling).
   - CTA: Máximo 20 caracteres (Curto e imperativo).
   - IMAGE_PROMPT: Crie um prompt em INGLÊS para gerar uma imagem impactante para o anúncio (máximo 200 caracteres).
3. IDIOMA: Português do Brasil (PT-BR) para titulo, descricao e cta. INGLÊS para image_prompt.
4. Tom natural, humano e persuasivo. Evite "IA-speak".

ESTRUTURA DAS VARIAÇÕES:
- Variação 1 (PAS): Foco na dor latente do público e na solução rápida.
- Variação 2 (Benefício): Foco na transformação clara após usar o produto/serviço.
- Variação 3 (Autoridade): Foco em prova social ou tempo de mercado do cliente.
- Variação 4 (Escassez): Foco em tempo limitado ou poucas vagas (Urgência Real).
- Variação 5 (Direct/Hook): Um gancho de curiosidade forte ou pergunta provocativa.

REQUISITO TÉCNICO DE SAÍDA:
Retorne EXCLUSIVAMENTE um array JSON puro, sem blocos de código markdown (sem ```json), sem explicações.
Formato: [{"titulo": "...", "descricao": "...", "cta": "...", "image_prompt": "..."}]

O image_prompt deve descrever uma imagem profissional, moderna e relevante para o anúncio. Exemplo:
"Professional smiling person in modern office with growth charts, vibrant colors, flat design style"
"""


def validate_and_truncate_ads(ads: list) -> list:
    """Valida e trunca os textos dos anúncios para garantir limites de caracteres."""
    validated_ads = []

    for ad in ads:
        validated_ad = {
            "titulo": ad.get("titulo", "")[:CHAR_LIMITS["titulo"]],
            "descricao": ad.get("descricao", "")[:CHAR_LIMITS["descricao"]],
            "cta": ad.get("cta", "")[:CHAR_LIMITS["cta"]],
            "image_prompt": ad.get("image_prompt", "")[:200]
        }
        validated_ads.append(validated_ad)

    return validated_ads


def generate_image_with_dalle(prompt: str, style: str = "") -> str:
    """Gera uma imagem usando DALL-E 3."""
    try:
        full_prompt = prompt
        if style:
            full_prompt = f"{prompt}, {style} style"

        full_prompt = f"Create a professional advertising image: {full_prompt}. High quality, suitable for social media ads, no text overlay."

        response = client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )

        return response.data[0].url

    except Exception as e:
        print(f"Erro ao gerar imagem: {str(e)}")
        return None


def generate_ads_with_openai(oferta: str, cliente: str, nicho: str, estilo_visual: str = "") -> list:
    """Gera variações de anúncios com texto usando GPT-4o."""

    estilo_info = f"\nESTILO VISUAL DESEJADO: {estilo_visual}" if estilo_visual else ""

    user_prompt = f"""Gere 5 variações de anúncios para:

OFERTA PRINCIPAL: {oferta}
CLIENTE/EMPRESA: {cliente}
NICHO/PÚBLICO-ALVO: {nicho}{estilo_info}

Lembre-se:
- Retorne APENAS o array JSON
- Inclua o campo "image_prompt" em INGLÊS para cada variação
- A descrição agora pode ter até 250 caracteres (mais detalhada)"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ADS},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2000,
            temperature=0.7
        )

        response_text = response.choices[0].message.content.strip()

        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()
        ads = json.loads(response_text)
        validated_ads = validate_and_truncate_ads(ads)

        return validated_ads

    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao processar resposta da IA: {str(e)}")
    except Exception as e:
        raise Exception(f"Erro na comunicação com a API: {str(e)}")


@app.route("/generate_ads", methods=["POST"])
def generate_ads():
    """Endpoint para gerar variações de anúncios com imagens."""

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
    cliente = data.get("cliente", "").strip()
    nicho = data.get("nicho", "").strip()
    estilo_visual = data.get("estilo_visual", "").strip()
    generate_images = data.get("generate_images", True)

    if not oferta:
        return jsonify({"success": False, "error": "O campo 'oferta' é obrigatório"}), 400
    if not cliente:
        return jsonify({"success": False, "error": "O campo 'cliente' é obrigatório"}), 400
    if not nicho:
        return jsonify({"success": False, "error": "O campo 'nicho' é obrigatório"}), 400

    try:
        ads = generate_ads_with_openai(oferta, cliente, nicho, estilo_visual)

        if generate_images:
            for ad in ads:
                image_prompt = ad.get("image_prompt", "")
                if image_prompt:
                    image_url = generate_image_with_dalle(image_prompt, estilo_visual)
                    ad["image_url"] = image_url
                else:
                    ad["image_url"] = None
                del ad["image_prompt"]
        else:
            for ad in ads:
                if "image_prompt" in ad:
                    del ad["image_prompt"]
                ad["image_url"] = None

        return jsonify({"success": True, "data": ads})

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
        "service": "GrowthBlast AI",
        "version": "2.0.0",
        "tools": ["KeyBlast", "AdBlast"]
    })


@app.route("/")
def serve_frontend():
    """Serve o frontend index.html na rota raiz."""
    return send_from_directory(".", "index.html")


if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 GrowthBlast AI v2.0 - Backend iniciado!")
    print("="*50)
    print("📍 Servidor: http://localhost:5000")
    print("📡 Endpoints:")
    print("   POST /generate_keywords - KeyBlast (Palavras-Chave)")
    print("   POST /generate_ads      - AdBlast (Anúncios + Imagens)")
    print("   GET  /health            - Health check")
    print("="*50)
    print("🔧 Ferramentas disponíveis:")
    print("   🔑 KeyBlast - Palavras-chave por funil")
    print("   🎨 AdBlast  - Anúncios com DALL-E 3")
    print("="*50 + "\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
