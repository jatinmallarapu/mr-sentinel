# Keep inference behind one provider

The review scheduler depends on a structured completion protocol. vLLM and SGLang use the same HTTP adapter. Timeout handling and schema failures remain observable through the application. A provider can still return a plausible but incorrect finding, so the application checks every citation against the submitted diff.
