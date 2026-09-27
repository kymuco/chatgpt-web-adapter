from chatgpt_web_adapter.google_translate_web import GoogleTranslateWebCapability


def main() -> None:
    translator = GoogleTranslateWebCapability()
    result = translator.translate_text(
        "hello",
        source_language="en",
        target_language="es",
    )
    print(result.translated_text)


if __name__ == "__main__":
    main()
