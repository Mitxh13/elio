# Elio — Unified AI Command-Line Interface

Elio is a developer-focused CLI application that unifies the world's most advanced reasoning models — Anthropic Claude, Google Gemini, and OpenAI ChatGPT — into a single, uninterrupted terminal workflow. 

[![GitHub stars](https://img.shields.io/github/stars/Elio-labs/elio?style=social)](https://github.com/Elio-labs/elio)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

### Why Elio?

* **Zero-dependency installation** — Packaged as a standalone executable. No Python, pip, or environment configuration required.
* **Unified conversation interface** — Use the exact same commands and UI regardless of whether you are talking to Claude, Gemini, or ChatGPT.
* **Secure by design** — API keys are stored safely in your OS credential vault (macOS Keychain, Windows Credential Manager, Linux Secret Service). None are stored in plain text.
* **Native file attachments** — Attach code files, PDFs, and images directly in the terminal without leaving your workflow.
* **Local privacy** — Conversation history is stored in a local SQLite database. No telemetry, no cloud syncing.

---

### Architecture

```text
       User Terminal (Textual TUI)
                │
            ┌───┴───┐
            ↓       ↓
       Session    File
       Manager   Handler
            │       │
            └───┬───┘
                ↓
        Provider Registry
          /     |     \
     Claude   Gemini   OpenAI
````

-----

### Quick Start

#### Installation

Download the latest installer from the [elio page](https://elioai.pages.dev).

| Operating System | Download File | Notes |
| :--- | :--- | :--- |
| **Windows 10/11 (64-bit)** | `Elio-Setup.exe` | Standard Windows Setup Wizard. Adds `elio` to PATH automatically. |
| **macOS 12+ (Apple Silicon & Intel)** | `Elio-macOS.pkg` | Native macOS Package Installer. |
| **Linux (Debian/Ubuntu)** | `Elio-Linux.deb` | Debian Package (`.deb`). |

#### Setup Your API Keys

Elio connects directly to provider APIs. You only need at least one to get started:

```bash
elio login
```

Select a provider (Anthropic, Google, or OpenAI) and paste your API key when prompted. The key is hidden as you type.

#### Launch the UI

```bash
elio
```

-----

### Commands & Workflows

#### Global CLI Commands

Run these directly from your terminal prompt.

| Command | Description |
| :--- | :--- |
| `elio` | Start the interactive chat UI |
| `elio login` | Add or update API keys for providers |
| `elio logout` | Securely wipe all stored credentials |
| `elio status` | Check which providers are currently connected |
| `elio models` | List all available models and aliases |
| `elio history` | Browse saved conversation sessions |
| `elio config` | Open the config file in your default editor |
| `elio update` | Check for and install the latest version |

#### Interactive TUI Keyboard Shortcuts

While inside the Elio chat interface.

| Shortcut | Action |
| :--- | :--- |
| **Enter** | Send message |
| **Shift+Enter** | New line in input |
| **Ctrl+P** | Open the interactive model selector |
| **Ctrl+U** | Open file attachment prompt |
| **Ctrl+N** | Start a new session |
| **Ctrl+L** | Clear chat panel |
| **Ctrl+B** | Show session history |
| **Ctrl+C** | Interrupt streaming / Quit |

#### Interactive TUI Slash Commands

Type these directly into the chat input bar.

| Command | Description |
| :--- | :--- |
| `/model <alias>` | Switch active model inline (e.g., `/model gemini`) |
| `/attach <path>` | Attach a file to the next message |
| `/clear` | Clear the current conversation context |
| `/history` | List recent sessions in the chat log |
| `/load <id>` | Load a previous session by its ID |
| `/export` | Export the current session as a Markdown file |
| `/tokens` | Show current context window token usage |
| `/status` | Show auth status for all providers |
| `/help` | Show all commands in chat |

-----

### Supported Models & Aliases

Elio utilizes an alias system to route requests to the best model for the job.

| Alias | Provider | Underlying Model | Best For |
| :--- | :--- | :--- | :--- |
| `coding` | Anthropic | claude-sonnet-5 | Coding, debugging & technical reasoning |
| `fast` | Google | gemini-2.5-flash | Fastest free model |
| `research` | Google | gemini-2.5-pro | Research, summarization & web-grounded queries |
| `writing` | OpenAI | gpt-5.6-sol | General content writing & creative tasks |
| `vision` | OpenAI | gpt-5.6-sol | Multi-modal vision tasks |
| `claude-sonnet` | Anthropic | claude-sonnet-5 | Best for coding & reasoning |
| `claude-haiku` | Anthropic | claude-haiku-4-5-20251001 | Fast & affordable |
| `gemini-fast` | Google | gemini-2.5-flash | Fast & free |
| `gemini-pro` | Google | gemini-2.5-pro | Most capable reasoning |
| `gpt-sol` | OpenAI | gpt-5.6-sol | Flagship — complex reasoning |
| `gpt-terra` | OpenAI | gpt-5.6-terra | Balanced intelligence vs cost |
| `gpt-luna` | OpenAI | gpt-5.6-luna | Fast & affordable |

-----

### File Handling

Elio natively processes attachments directly through the CLI context.

| File Type | Handling Strategy |
| :--- | :--- |
| **Images** (`.png`, `.jpg`, `.webp`) | Base64 encoded, sent as image block (Claude + GPT-4o support) |
| **PDF** (`.pdf`) | Base64 encoded as document block (Claude native PDF support) |
| **Text/Code** (`.py`, `.md`, `.json`, etc.) | Read as UTF-8 text, injected into message as code block |

-----

### Configuration & Storage

Elio stores all local data in the `~/.elio/` directory:

  * `~/.elio/config.toml` — Theme settings, default models, context token limits.
  * `~/.elio/history.db` — SQLite database containing session history.
  * `~/.elio/logs/` — Application logs for debugging.

You can edit your configuration at any time by running `elio config`.

-----

### Troubleshooting

  * **"Command not found: elio"**
    The installer may not have updated your current terminal session. Try restarting your terminal. On Windows, you may need to restart your PC. On macOS, ensure `/usr/local/bin` is in your path: `export PATH="$PATH:/usr/local/bin"`
  * **"Invalid API Key" error**
    Run `elio login` and paste the key fresh. Make sure there are no extra spaces before or after the key.
  * **TUI looks broken in my terminal**
    Elio requires a terminal with Unicode and 256-color support. We recommend Windows Terminal (Windows), iTerm2 (macOS), or standard Linux terminals. Avoid using the default macOS Terminal.app or legacy CMD on Windows.

### Uninstallation

  * **Windows:** Go to Settings \> Apps \> Elio and click Uninstall. | Control panel \> uninstall a program \> find Elio \> right & uninstall
  * **macOS:** Drag Elio from Applications to Trash.
  * **Linux:** Run `sudo apt remove elio`.
  * **Deep Clean:** To completely delete all history and configs across any OS, delete the hidden `.elio` folder in your User/Home directory.

-----
## Contributors

<!-- readme: contributors -start -->
<table>
<tr>
    <td align="center"><a href="https://github.com/Mitxh13"><img src="https://avatars.githubusercontent.com/Mitxh13?v=4&s=100" width="100;" alt="Mitxh13/Mitesh"/><br /><sub><b>Mitesh</b></sub></a></td>
</tr>
</table>

-----

## License

MIT

-----

v0.3.5
<!-- | [Issues](https://github.com/Elio-labs/elio/issues)  [Contributing](./CONTRIBUTING.md) -->
