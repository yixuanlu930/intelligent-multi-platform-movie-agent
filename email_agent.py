#!/usr/bin/env python3
"""
Agente de atencion al cliente.

Extraido de la celda 22 de Practica_Agentes.ipynb para que pueda importarse
desde scripts externos.

Estrategia: clasificador lexico (conteo de palabras) + LLM para redactar la
respuesta segun el sentimiento. El clasificador es determinista y rapido; el
LLM solo se usa para variar la redaccion, no para clasificar.

Uso programatico:
    from email_agent import classify_sentiment, email_agent
    resultado = email_agent("la comida estaba fria", llm_obj=mi_llm)
"""

# Vocabulario lexico para clasificacion de sentimiento
POSITIVE_WORDS = {
    "gracias", "genial", "excelente", "fantástico", "fantastico",
    "increíble", "increible", "perfecto", "maravilloso", "recomiendo",
    "feliz", "contento", "alegra", "alegro", "agradable", "disfruté",
    "disfrutado", "encanta", "encantado", "buen", "buena",
}
NEGATIVE_WORDS = {
    "frío", "frio", "horrible", "malo", "mala", "pésimo", "pesimo",
    "asco", "sucio", "sucia", "caro", "cara", "lento", "lenta",
    "tarde", "roto", "rota", "reclamo", "queja", "defectuoso",
    "defectuosa", "problema", "esperar", "decepción", "decepcion",
}

# System prompt que guia al LLM hacia respuestas utiles y concisas
EMAIL_SYSTEM_PROMPT = (
    "Eres un agente de atención al cliente cordial. "
    "Responde al mensaje del cliente con un tono adecuado a su sentimiento. "
    "Máximo 3 frases. "
    "- Si es desfavorable: pide disculpas y ofrece una acción correctiva. "
    "- Si es favorable: agradece sinceramente y refuerza el vínculo. "
    "- Si es neutral: contesta con información útil."
)


def classify_sentiment(text):
    """
    Clasifica el sentimiento de un texto usando conteo lexico.
    Devuelve (sentimiento, n_positivas, n_negativas).
    """
    norm = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in norm)
    neg = sum(1 for w in NEGATIVE_WORDS if w in norm)
    if pos > neg:
        return "favorable", pos, neg
    if neg > pos:
        return "desfavorable", pos, neg
    return "neutral", pos, neg


def email_agent(text, llm_obj=None):
    """
    Analiza el sentimiento del mensaje y genera una respuesta contextualizada.

    `llm_obj` debe ser un LangChain ChatModel (p.ej. ChatOllama). Si no se
    pasa, se crea uno con la configuracion por defecto del proyecto. Pasarlo
    explicitamente es mas eficiente cuando ya tienes uno instanciado.
    """
    # Imports diferidos para que el modulo se pueda importar aunque langchain
    # no este instalado, siempre que no se invoque email_agent().
    from langchain_core.messages import SystemMessage, HumanMessage

    if llm_obj is None:
        from langchain_ollama import ChatOllama
        import config
        llm_obj = ChatOllama(model=config.OLLAMA_MODEL, base_url=config.OLLAMA_URL, temperature=0.7)

    sentiment, pos, neg = classify_sentiment(text)

    msg = llm_obj.invoke([
        SystemMessage(content=EMAIL_SYSTEM_PROMPT),
        # Pasamos el sentimiento al LLM para que adapte el tono
        HumanMessage(content=f"[sentimiento detectado: {sentiment}]\nMensaje: {text}"),
    ])
    return {
        "sentimiento": sentiment,
        "score":       (pos, neg),
        "respuesta":   msg.content.strip(),
    }


if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or "La comida estaba fría y el camarero tardó una hora."
    print(f"Mensaje: {text}\n")
    sent, p, n = classify_sentiment(text)
    print(f"Sentimiento (sin LLM): {sent} (pos={p}, neg={n})")
    try:
        out = email_agent(text)
        print(f"\nRespuesta del agente:\n  {out['respuesta']}")
    except Exception as e:
        print(f"\n[LLM no disponible] {e}")
