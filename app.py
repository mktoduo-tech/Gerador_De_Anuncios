"""
AdBlast AI - Backend Flask
Gerador de variações de anúncios usando OpenAI GPT-4
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
CORS(app)  # Habilita CORS para requisições do frontend

# Inicializa o cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Limites de caracteres (Facebook/Instagram Ads)
CHAR_LIMITS = {
    "titulo": 40,      # Headline do Facebook Ads
    "descricao": 125,  # Primary text (mobile optimized)
    "cta": 20          # CTA button text
}

# System prompt para o copywriter AI
SYSTEM_PROMPT = """Você é um Copywriter Sênior e Estrategista de Tráfego Pago especialista em Direct Response para o mercado brasileiro. Sua especialidade é criar anúncios para Meta Ads (Facebook/Instagram) que param o scroll e geram cliques qualificados.

CONTEXTO DE EXECUÇÃO:
O usuário fornecerá: Cliente, Oferta e Função/Nicho.
Use os frameworks AIDA (Atenção, Interesse, Desejo, Ação) e PAS (Problema, Agitação, Solução).

REGRAS RÍGIDAS DE CONTEÚDO E FORMATO:
1. QUANTIDADE: Gere exatamente 5 variações distintas.
2. LIMITES TÉCNICOS (NÃO ULTRAPASSE):
   - TÍTULO: Máximo 40 caracteres (Direto e impactante).
   - DESCRIÇÃO: Máximo 125 caracteres (Foco na primeira linha, otimizado para mobile).
   - CTA: Máximo 18 caracteres (Curto e imperativo).
3. IDIOMA: Português do Brasil (PT-BR), tom natural, humano e persuasivo. Evite "IA-speak" (palavras como "potencialize", "revolucionário", "descubra o segredo").

ESTRUTURA DAS VARIAÇÕES:
- Variação 1 (PAS): Foco na dor latente do público e na solução rápida.
- Variação 2 (Benefício): Foco na transformação clara após usar o produto/serviço.
- Variação 3 (Autoridade): Foco em prova social ou tempo de mercado do cliente.
- Variação 4 (Escassez): Foco em tempo limitado ou poucas vagas (Urgência Real).
- Variação 5 (Direct/Hook): Um gancho de curiosidade forte ou pergunta provocativa.

REQUISITO TÉCNICO DE SAÍDA:
Retorne EXCLUSIVAMENTE um array JSON puro, sem blocos de código markdown (sem ```json), sem explicações ou introduções.
Formato: [{"titulo": "...", "descricao": "...", "cta": "..."}]"""


def validate_and_truncate_ads(ads: list) -> list:
    """
    Valida e trunca os textos dos anúncios para garantir limites de caracteres.

    Args:
        ads: Lista de anúncios gerados pela IA

    Returns:
        Lista de anúncios com textos validados/truncados
    """
    validated_ads = []

    for ad in ads:
        validated_ad = {
            "titulo": ad.get("titulo", "")[:CHAR_LIMITS["titulo"]],
            "descricao": ad.get("descricao", "")[:CHAR_LIMITS["descricao"]],
            "cta": ad.get("cta", "")[:CHAR_LIMITS["cta"]]
        }
        validated_ads.append(validated_ad)

    return validated_ads


def generate_ads_with_openai(oferta: str, cliente: str, nicho: str) -> list:
    """
    Chama a API da OpenAI para gerar variações de anúncios.

    Args:
        oferta: A oferta principal do anúncio
        cliente: Nome do cliente/empresa
        nicho: Função ou nicho de mercado

    Returns:
        Lista de dicionários com as variações de anúncios
    """

    user_prompt = f"""Gere 5 variações de anúncios para:

OFERTA PRINCIPAL: {oferta}
CLIENTE/EMPRESA: {cliente}
NICHO/PÚBLICO-ALVO: {nicho}

Lembre-se: retorne APENAS o array JSON, sem nenhum texto adicional."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            max_tokens=1500,
            temperature=0.7
        )

        # Extrai o texto da resposta
        response_text = response.choices[0].message.content.strip()

        # Remove possíveis marcadores de código markdown
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()

        # Parse do JSON
        ads = json.loads(response_text)

        # Valida e trunca os textos para garantir limites
        validated_ads = validate_and_truncate_ads(ads)

        return validated_ads

    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao processar resposta da IA: {str(e)}")
    except Exception as e:
        raise Exception(f"Erro na comunicação com a API: {str(e)}")


@app.route("/generate_ads", methods=["POST"])
def generate_ads():
    """
    Endpoint para gerar variações de anúncios.

    Espera um JSON com:
    - oferta: string (obrigatório)
    - cliente: string (obrigatório)
    - nicho: string (obrigatório)

    Retorna:
    - success: boolean
    - data: array de objetos {titulo, descricao, cta}
    - error: string (apenas em caso de erro)
    """

    # Verifica se a API key está configurada
    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({
            "success": False,
            "error": "API Key da OpenAI não configurada. Verifique o arquivo .env"
        }), 500

    # Obtém os dados da requisição
    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "error": "Nenhum dado enviado na requisição"
        }), 400

    # Valida campos obrigatórios
    oferta = data.get("oferta", "").strip()
    cliente = data.get("cliente", "").strip()
    nicho = data.get("nicho", "").strip()

    if not oferta:
        return jsonify({
            "success": False,
            "error": "O campo 'oferta' é obrigatório"
        }), 400

    if not cliente:
        return jsonify({
            "success": False,
            "error": "O campo 'cliente' é obrigatório"
        }), 400

    if not nicho:
        return jsonify({
            "success": False,
            "error": "O campo 'nicho' é obrigatório"
        }), 400

    try:
        # Gera as variações de anúncios
        ads = generate_ads_with_openai(oferta, cliente, nicho)

        return jsonify({
            "success": True,
            "data": ads
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 422

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Endpoint de health check para verificar se a API está rodando."""
    return jsonify({
        "status": "healthy",
        "service": "AdBlast AI",
        "version": "1.0.0"
    })


@app.route("/")
def serve_frontend():
    """Serve o frontend index.html na rota raiz."""
    return send_from_directory(".", "index.html")


if __name__ == "__main__":
    print("\n🚀 AdBlast AI - Backend iniciado!")
    print("📍 Servidor rodando em: http://localhost:5000")
    print("📡 Endpoints disponíveis:")
    print("   POST /generate_ads - Gera variações de anúncios")
    print("   GET  /health       - Health check\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
