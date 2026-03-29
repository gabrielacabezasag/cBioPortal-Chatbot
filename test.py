import os
from google import genai

MEIN_TEST_KEY = "AIzaSyCrVr1TAvPYgabzR4lKR0gd2AOyl8SRYkM"

def test_verbindung():
    print(f"DEBUG: Starte Test mit Key-Länge: {len(MEIN_TEST_KEY)}")

    try:
        print("DEBUG: Initialisiere Gemini Client...")
        client = genai.Client(api_key=MEIN_TEST_KEY)

        print("DEBUG: Versuche Verbindung zu Google...")
        for model in client.models.list():
            print(f"ERFOLG: Modell gefunden: {model.name}")
            break

        print("\n--- Chatbot Start ---")
        user_input = input("Test-Eingabe (Du): ")
        print(f"Du hast getippt: {user_input}")

    except Exception as e:
        print(f"\nFEHLER BEI DER INITIALISIERUNG:")
        print(str(e))


if __name__ == "__main__":
    test_verbindung()

