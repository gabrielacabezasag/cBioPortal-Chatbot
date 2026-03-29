import json
import requests
import os

LLM_API_KEY = os.environ["LLMAPI_KEY"]

def get_biomcp_tools():
    # BioMCP Tool Definitionen im OpenAI-kompatiblen Format
    return [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Sucht in biomedizinischer Literatur, klinischen Studien und genomischen Varianten. Reichert Ergebnisse automatisch mit cBioPortal-Daten an, wenn Gene angegeben werden.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "enum": ["article", "trial", "variant"],
                            "description": "Die Domäne der Suche: 'article', 'trial', 'variant'."
                        },
                        "genes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste von Gen-Symbolen."
                        },
                        "diseases": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste von Krankheiten."
                        },
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Zusätzliche Schlagworte."
                        }
                    },
                    "required": ["domain"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "fetch",
                "description": "Ruft detaillierte Informationen zu einem spezifischen Artikel, einer Studie oder einer Variante ab.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "enum": ["article", "trial", "variant"]
                        },
                        "id": {
                            "type": "string",
                            "description": "Die ID."
                        }
                    },
                    "required": ["domain", "id"]
                }
            }
        }
    ]


def call_biomcp(name: str, args: dict) -> dict:
    # URL der BioMCP-Instanz
    biomcp_url = "http://127.0.0.1:3000/mcp"
    print(f"DEBUG: Rufe BioMCP Tool '{name}' auf mit Argumenten: {args}")
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": args
        }
    }
    try:
        response = requests.post(biomcp_url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"FEHLER: BioMCP Server antwortete mit Status {response.status_code}: {response.text}")
            return {"error": f"BioMCP Serverfehler: {response.status_code}"}
    except requests.exceptions.ConnectionError as ce:
        print(f"FEHLER: BioMCP Verbindungsfehler: {ce}. Ist die BioMCP-Middleware gestartet und unter {biomcp_url} erreichbar?")
        return {"error": f"BioMCP Verbindungsfehler: {str(ce)}"}
    except Exception as e:
        print(f"FEHLER: Unerwarteter Fehler beim BioMCP-Aufruf: {e}")
        return {"error": f"BioMCP Fehler: {str(e)}"}


def run_chatbot():
    # Konfiguration
    fau_key = LLM_API_KEY
    fau_url = "https://hub.nhr.fau.de/api/llmgw/v1/chat/completions"
    fau_model = "gpt-oss-120b"

    print(f"\ncBioPortal Chatbot {fau_model}")

    # Chat-Historie initialisieren
    messages = [
        {"role": "system",
         "content": "Du bist ein hilfreicher Assistent für cBioPortal. Nutze die verfügbaren Tools, um biomedizinische Fragen zu beantworten."}
    ]

    while True:
        user_input = input("\nDu: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        messages.append({"role": "user", "content": user_input})

        try:
            # Anfrage an das FAU Gateway mit Tools
            payload = {
                "model": fau_model,
                "messages": messages,
                "tools": get_biomcp_tools(),
                "tool_choice": "auto",
                "temperature": 0.7
            }
            headers = {
                "Authorization": f"Bearer {fau_key}",
                "Content-Type": "application/json"
            }

            response = requests.post(fau_url, json=payload, headers=headers)

            if response.status_code != 200:
                print(f"FEHLER VOM FAU-SERVER (Status {response.status_code}):")
                print(response.text)
                messages.pop()
                continue

            res_json = response.json()
            resp_msg = res_json["choices"][0].get("message", {})

            if "tool_calls" in resp_msg and resp_msg["tool_calls"]:
                print("DEBUG: LLM möchte ein Tool aufrufen.")
                messages.append(resp_msg)

                for tool_call in resp_msg["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])

                    # BioMCP aufrufen
                    tool_output = call_biomcp(function_name, function_args)

                    messages.append({
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(tool_output)
                    })

                print("DEBUG: Sende Tool-Ergebnis zurück an LLM für finale Antwort.")
                final_response = requests.post(fau_url, json={"model": fau_model, "messages": messages},
                                               headers=headers)

                if final_response.status_code != 200:
                    print(f"FEHLER VOM FAU-SERVER (Status {final_response.status_code}) beim finalen Aufruf:")
                    print(final_response.text)
                    messages.pop()
                    continue

                final_res_json = final_response.json()
                final_resp_msg = final_res_json["choices"][0].get("message", {})
                final_content = final_resp_msg.get("content", "Kein Inhalt in der finalen Antwort.")

                print(f"\nChatbot: {final_content}")
                messages.append({"role": "assistant", "content": final_content})

            else:
                content = resp_msg.get("content", "Kein Inhalt in der Antwort.")
                print(f"\nChatbot: {content}")
                messages.append({"role": "assistant", "content": content})

        except Exception as e:
            print(f"LOKALER FEHLER: {e}")
            messages.pop()

if __name__ == "__main__":
    run_chatbot()