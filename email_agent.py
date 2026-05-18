#!/usr/bin/env python3
"""
Agente de atencion al cliente.

Extraido de la celda 22 de Practica_Agentes.ipynb para que pueda importarse
desde scripts externos.

Estrategia de diseño: clasificador lexico (conteo de palabras) + LLM para redactar la
respuesta segun el sentimiento.

Por que dos pasos en vez de solo el LLM:
  - El clasificador es determinista, instantaneo y funciona aunque Ollama este caido.
  - El LLM solo se usa para variar la redaccion de la respuesta, no para clasificar.
  - Esto garantiza que siempre devolvemos un sentimiento aunque el LLM falle.

Uso programatico:
    from email_agent import classify_sentiment, email_agent
    resultado = email_agent("la comida estaba fria", llm_obj=mi_llm)
"""

# Vocabulario lexico para clasificacion de sentimiento.
# Son conjuntos (set) para que la busqueda sea O(1) en lugar de O(n).
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

# System prompt que guia al LLM hacia respuestas utiles y concisas.
# Maximo 3 frases para que la respuesta no sea excesivamente larga.
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

    Busca cuantas palabras positivas y negativas de los vocabularios
    aparecen en el texto (busqueda de subcadena, insensible a mayusculas).
    El sentimiento con mas coincidencias gana; en empate devuelve neutral.

    No usa LLM: es rapido, determinista y funciona sin conexion.

    Devuelve una tupla (sentimiento, n_positivas, n_negativas) donde
    sentimiento es "favorable", "desfavorable" o "neutral".
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

    Flujo:
    1. classify_sentiment() detecta el tono sin usar el LLM.
    2. Se construye el prompt con el sentimiento detectado para guiar al LLM.
    3. El LLM redacta una respuesta adecuada al tono.

    `llm_obj` debe ser un LangChain ChatModel (p.ej. ChatOllama). Si no se
    pasa, se crea uno con la configuracion por defecto del proyecto. Pasarlo
    explicitamente es mas eficiente cuando ya tienes uno instanciado (evita
    crear una nueva conexion con Ollama en cada llamada).

    Devuelve un dict con claves: sentimiento, score (tupla pos/neg), respuesta.
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
        # Le pasamos el sentimiento detectado para que el LLM adapte el tono
        # sin tener que inferirlo el mismo (es mas rapido y consistente)
        HumanMessage(content=f"[sentimiento detectado: {sentiment}]\nMensaje: {text}"),
    ])
    return {
        "sentimiento": sentiment,
        "score":       (pos, neg),
        "respuesta":   msg.content.strip(),
    }


if __name__ == "__main__":
    import sys
    # Acepta el mensaje por linea de comandos; si no hay argumentos usa un ejemplo
    text = " ".join(sys.argv[1:]) or "La comida estaba fría y el camarero tardó una hora."
    print(f"Mensaje: {text}\n")

    # Fase 1: clasificacion sin LLM (siempre funciona)
    sent, p, n = classify_sentiment(text)
    print(f"Sentimiento (sin LLM): {sent} (pos={p}, neg={n})")

    # Fase 2: respuesta del LLM (requiere Ollama corriendo)
    try:
        out = email_agent(text)
        print(f"\nRespuesta del agente:\n  {out['respuesta']}")
    except Exception as e:
        print(f"\n[LLM no disponible] {e}")
