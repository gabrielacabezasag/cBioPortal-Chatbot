import os
from openai import OpenAI

MEIN_TEST_KEY = os.environ["LLMAPI_KEY"]
FAU_URL = "https://hub.nhr.fau.de/api/llmgw/v1"
FAU_MODEL = "gpt-oss-120b"


def test_verbindung():
    print(f"DEBUG: Starte Test mit Key-Länge: {len(MEIN_TEST_KEY)}")

    try:
        print("DEBUG: Initialisiere Client...")
        client = OpenAI(api_key=MEIN_TEST_KEY, base_url=FAU_URL)

        print("DEBUG: Versuche Verbindung...")
        models_response = client.models.list()
        available_models = [model.id for model in models_response.data]

        if FAU_MODEL in available_models:
            print(f"ERFOLG: Modell '{FAU_MODEL}' ist verfügbar. Dein API-Key funktioniert!")
        else:
            print(f"WARNUNG: Modell '{FAU_MODEL}' nicht direkt gefunden, aber API-Verbindung erfolgreich.")
            print(f"Verfügbare Modelle: {', '.join(available_models)}")

        print("\nChatbot Start")
        chat_completion = client.chat.completions.create(
            model=FAU_MODEL,
            messages=[
                {"role": "system", "content": "Du bist ein hilfreicher Assistent."},
                {"role": "user", "content": "Hallo, wie geht es dir?"}
            ],
            max_tokens=20
        )
        print("ERFOLG: Test-Chat-Completion erfolgreich!")
        print(f"Antwort des LLM: {chat_completion.choices[0].message.content}")
        print("\nAPI-Key Test ABGESCHLOSSEN")

    except Exception as e:
        print(f"\nFEHLER BEI DER INITIALISIERUNG:")
        print(str(e))


if __name__ == "__main__":
    test_verbindung()
