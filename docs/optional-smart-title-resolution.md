# Optional smart title resolution

ARM's standard metadata lookup remains the default and adds no model dependencies or weights to the ARM image.

The optional smart matcher asks a local [Ollama](https://ollama.com/) model to choose only among real TMDB/OMDb search candidates. It can use spelling/spacing clues, release year, summaries, popularity and franchise context to handle labels such as \`Mr Mrs Smith Ws\` or to prefer \`The Hunger Games: Catching Fire\` over an unrelated short-title match. If the model is unavailable or returns a low-confidence decision, ARM falls back to its normal title matcher.

## Install the optional model service

Install Ollama on the host or as a separate container on a Docker network that ARM can reach. For a simple Docker test deployment, the Ollama service can be started with persistent model storage:

\`\`\`sh
docker run -d --name ollama --restart unless-stopped \\
  -p 11434:11434 -v ollama-models:/root/.ollama ollama/ollama
docker exec ollama ollama pull qwen2.5:3b
\`\`\`

For a Compose/TrueNAS deployment, use an Ollama service on the same network as ARM or use a host address reachable from the ARM container. The URL must be reachable **from inside ARM**, not merely from your browser. The default example URL \`http://ollama:11434\` assumes an Ollama service named \`ollama\` on a shared container network.

## Enable it in ARM

1. Open **Settings → UI Settings → Optional Smart Title Matching**.
2. Set the Ollama URL and model name; save the settings.
3. Use **Download model weights to Ollama** to request the configured model pull. ARM asks for confirmation because model files can be multiple gigabytes.
4. Enable **Smart title matching** and save.

The model pull button downloads weights to the configured Ollama service; ARM does not install Ollama itself or change the base ARM Python environment. The disc label and candidate titles/years/types plus available plot summaries are sent to the configured local model endpoint when the option is enabled. No candidates are sent to a third-party cloud service by ARM's default configuration.

A local model can still make a wrong selection. ARM accepts only a candidate index returned with confidence at least 0.6; otherwise the regular matcher remains in control. Validate ambiguous results and use ARM's manual title selection when the model cannot distinguish the intended release.
