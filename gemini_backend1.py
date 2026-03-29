import os
import json
import requests
import sseclient
import google.generativeai as genai
from typing import Dict, Any, List

# --- KONFIGURATION ---
# Dein Google Gemini API Key. Es wird dringend empfohlen, diesen als Umgebungsvariable zu setzen.
# Beispiel: export GEMINI_API_KEY="AIzaSy..."
GEMINI_API_KEY = "AIzaSyCrVr1TAvPYgabzR4lKR0gd2AOyl8SRYkM"

# Basis-URL deiner BioMCP-Instanz (Standardmäßig lokal)
BIOMCP_BASE_URL = os.getenv("BIOMCP_BASE_URL", "http://127.0.0.1:3000/mcp")


# --- BIOMCP TOOL DEFINITIONEN (Dictionary-basiertes Format für maximale Kompatibilität) ---
def get_biomcp_tools() -> List[Dict[str, Any]]:
    return [
        {
            "function_declarations": [
                {
                    "name": "search",
                    "description": "Sucht in biomedizinischer Literatur, klinischen Studien und genomischen Varianten. Reichert Ergebnisse automatisch mit cBioPortal-Daten an, wenn Gene angegeben werden.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "domain": {
                                "type": "STRING",
                                "enum": ["article", "trial", "variant"],
                                "description": "Die Domäne der Suche: 'article' (Literatur), 'trial' (Studien), 'variant' (Varianten)."
                            },
                            "genes": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                                "description": "Liste von Gen-Symbolen (z.B. ['BRAF', 'TP53'])."
                            },
                            "diseases": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                                "description": "Liste von Krankheiten (z.B. ['melanoma'])."
                            },
                            "keywords": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                                "description": "Zusätzliche Schlagworte (z.B. ['V600E'])."
                            }
                        },
                        "required": ["domain"]
                    }
                },
                {
                    "name": "fetch",
                    "description": "Ruft detaillierte Informationen zu einem spezifischen Artikel, einer Studie oder einer Variante ab.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "domain": {
                                "type": "STRING",
                                "enum": ["article", "trial", "variant"]
                            },
                            "id": {
                                "type": "STRING",
                                "description": "Die ID (PMID, DOI, NCT-Nummer oder rsID)."
                            }
                        },
                        "required": ["domain", "id"]
                    }
                }
            ]
        }
    ]


# --- BIOMCP API AUFRUF (Direkt über requests und sseclient) ---
def call_biomcp_middleware(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Sendet den Function Call an die BioMCP Middleware und verwaltet die SSE Session direkt."""
    print(f"DEBUG: [1/3] Öffne BioMCP Session unter {BIOMCP_BASE_URL}...")

    try:
        session_url = None
        headers = {"Accept": "text/event-stream"}

        # Erhöhtes Timeout für die Session-Initialisierung, da Prefetching lange dauern kann
        # und der Server möglicherweise erst nach einiger Zeit die Session-URL sendet.
        with requests.get(BIOMCP_BASE_URL, headers=headers, stream=True, timeout=120) as r:
            # Verwende sseclient, um Events zu parsen
            client = sseclient.SSEClient(r)
            for event in client.events():
                if event.data:
                    try:
                        # BioMCP sendet die Session-URL als JSON-String im 'data'-Feld
                        event_data = json.loads(event.data)
                        if "url" in event_data:
                            session_url = event_data["url"]
                            print(f"DEBUG: [2/3] BioMCP Session-URL erhalten: {session_url}")
                            break
                    except json.JSONDecodeError:
                        # Manchmal sendet BioMCP auch andere Events, die kein JSON sind
                        print(f"DEBUG: Nicht-JSON Event-Daten: {event.data}")

        if not session_url:
            print(
                "FEHLER: Keine BioMCP Session-URL erhalten. BioMCP Server möglicherweise nicht bereit oder falsche URL.")
            return {"error": "Keine BioMCP Session-URL erhalten."}

        print(f"DEBUG: [3/3] Sende Tool-Befehl '{name}' an Session-URL: {session_url}")
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {"name": name, "arguments": args}
        }

        # Timeout für den eigentlichen Tool-Call
        response = requests.post(session_url, json=payload, timeout=60)
        response.raise_for_status()  # Löst einen HTTPError für schlechte Statuscodes aus

        response_json = response.json()
        print(f"DEBUG: BioMCP Tool-Ergebnis für '{name}': {json.dumps(response_json, indent=2)}")
        return response_json

    except requests.exceptions.Timeout:
        print(f"FEHLER: BioMCP-Timeout beim Aufruf von '{name}'. Server zu langsam oder überlastet.")
        return {"error": "BioMCP-Timeout oder Server überlastet."}
    except requests.exceptions.RequestException as e:
        print(f"FEHLER: BioMCP-Verbindungsfehler beim Aufruf von '{name}': {e}")
        return {"error": f"BioMCP-Verbindungsfehler: {e}"}
    except Exception as e:
        print(f"FEHLER: Unerwarteter Fehler im BioMCP-Aufruf: {e}")
        return {"error": f"Unerwarteter BioMCP-Fehler: {e}"}


# --- CHAT LOGIK ---
def run_chatbot():
    if not GEMINI_API_KEY:
        print("FEHLER: GEMINI_API_KEY nicht gesetzt. Bitte setze ihn als Umgebungsvariable.")
        print("Beispiel: export GEMINI_API_KEY=\"DEIN_SCHLUESSEL\"")
        return

    # Client initialisieren
    genai.configure(api_key=GEMINI_API_KEY)

    # Dynamische Modellauswahl
    model_name = None
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and ('flash' in m.name or 'pro' in m.name):
                model_name = m.name
                print(f"DEBUG: Verfügbares Modell gefunden: {model_name}")
                break
        if not model_name:
            print("FEHLER: Kein geeignetes Gemini-Modell gefunden, das 'generateContent' unterstützt.")
            return
    except Exception as e:
        print(f"FEHLER beim Abrufen der Modellliste: {e}")
        return

    model = genai.GenerativeModel(
        model_name=model_name,
        tools=get_biomcp_tools()
    )

    chat = model.start_chat(history=[])

    print(f"\n--- cBioPortal Chatbot (Gemini + BioMCP Direct V9, Modell: {model_name}) ist bereit! ---")
    print("(Tippe 'exit' zum Beenden)")

    while True:
        user_input = input("\nDu: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        try:
            response = chat.send_message(user_input)

            # Iteriere durch die Antwortteile, um Function Calls zu finden und auszuführen
            for content_part in response.candidates[0].content.parts:
                if content_part.function_call:
                    fn_call = content_part.function_call
                    print(f"DEBUG: Gemini schlägt Tool-Call vor: {fn_call.name} mit Argumenten: {fn_call.args}")

                    # BioMCP aufrufen
                    result = call_biomcp_middleware(fn_call.name, fn_call.args)

                    # Das Ergebnis als FunctionResponse an Gemini zurücksenden
                    response = chat.send_message(
                        genai.types.Part(function_response=genai.types.FunctionResponse(name=fn_call.name,
                                                                                        response={"result": result}))
                    )
                    # Nach dem Tool-Call muss Gemini die finale Antwort generieren
                    # Wir nehmen an, dass die nächste Antwort die finale ist
                    final_response_text = response.text
                    print(f"\nChatbot: {final_response_text}")
                    break  # Nur einen Tool-Call pro Runde verarbeiten
            else:  # Wenn kein Function Call gefunden wurde, direkt die Antwort ausgeben
                print(f"\nChatbot: {response.text}")

        except Exception as e:
            print(f"FEHLER im Chatbot: {e}")


if __name__ == "__main__":
    run_chatbot()