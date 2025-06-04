# Lamia LLM Adapter Roadmap

## Planned Improvements

- [ ] **Refactor LLM Adapter Interface for Multimodal Support**
  - Introduce `LLMRequest` and `LLMResponse` objects that can wrap any kind of input/output (text, image, audio, etc.).
  - Update adapters to support text-to-image, image-to-text, and other OpenAI-supported transformations.
  - Ensure backward compatibility for current text-to-text use cases.
  - Update documentation and tests to cover new modalities.

---

*Add new roadmap items below as needed.* 