# Codex Question Sound for VS Code on macOS

An unofficial, macOS-only patch that adds audible alerts when the OpenAI Codex
VS Code extension asks a question.

> [!WARNING]
> This project modifies the installed extension bundle. It is not affiliated
> with, endorsed by, or supported by OpenAI or Microsoft. Codex updates can
> overwrite the patch or make its internal matching rules incompatible.

## What it does

- Plays one sound when Codex asks a question without a timeout.
- Plays one sound per second while a timed question is counting down.
- Stops both the repeating sound and automatic countdown as soon as the user
  interacts with the question card.
- Stops the sound when the question is answered, resolved, or removed.
- Creates a byte-for-byte backup before changing the extension bundle.

The patch responds specifically to Codex `item/tool/requestUserInput` events.
It does **not** add task-completion sounds or terminal permission-approval
alerts.

## Platform and tested environment

This project supports **macOS only** (the operating system formerly called Mac
OS X). It uses the built-in `/usr/bin/afplay` command and the macOS system sound
`/System/Library/Sounds/Tink.aiff`.

The current patch was developed and tested on:

| Component | Tested configuration |
| --- | --- |
| Mac | MacBook Pro (`MacBookPro11,4`) |
| CPU and memory | Intel Core i7 2.8 GHz, x86_64, 16 GB RAM |
| Operating system | macOS Monterey 12.7.4 (`21H1123`) |
| Visual Studio Code | 1.133.0 |
| Codex extension | `openai.chatgpt` 26.810.52044 (`darwin-x64`) |
| Python | 3.10.9 |

Other Intel Macs may work, but have not been verified. Apple Silicon and newer
macOS releases are currently untested.

## Requirements

- macOS with `/usr/bin/afplay` and the `Tink.aiff` system sound.
- Visual Studio Code with the official OpenAI Codex extension installed.
- Python 3.10 or newer.
- A standard VS Code extension directory at `~/.vscode/extensions`, or an
  explicit `--extension-dir` argument.

## Install

From this project directory, first check whether the installed Codex version is
compatible:

```bash
python3 patch_codex_extension.py --dry-run
```

If the check succeeds, install the patch:

```bash
python3 patch_codex_extension.py
```

Then open the VS Code Command Palette and run **Developer: Reload Window**.

## Restore the original extension

The installer keeps the original `extension.js` beside the patched file with a
`.codex-question-sound.original` suffix. Restore it with:

```bash
python3 patch_codex_extension.py --restore
```

Reload the VS Code window again after restoring.

## After a Codex update

VS Code installs each Codex update in a new versioned directory, so the patch
will normally need to be applied again:

```bash
python3 patch_codex_extension.py --dry-run
python3 patch_codex_extension.py
```

The patcher requires every internal target to match exactly once. If OpenAI
changes the extension bundle, it exits without writing anything instead of
making an ambiguous modification.

## How it works

The script locates the active `openai.chatgpt` installation through VS Code's
extension registry, reads `out/extension.js`, and patches the internal
user-input auto-resolution coordinator. The injected JavaScript launches
`afplay` for question events and owns one repeating timer per conversation.
Question interaction, resolution, and cleanup cancel that timer.

All processing stays local. The project makes no network requests and collects
no telemetry.

## Development and tests

The project has no third-party Python dependencies. Run the tests with:

```bash
python3 -B -m unittest -v test_patch_codex_extension.py
```

## Related projects

- [agent-notify](https://github.com/paultendo/agent-notify) provides broad,
  hook-based notifications for completions, approvals, questions, and errors.
- [codex-attention-notifier](https://github.com/constansino/codex-attention-notifier)
  sends native macOS notifications for Codex permission requests.
- [OpenAI Codex issue #3962](https://github.com/openai/codex/issues/3962)
  tracks the wider request for audible Codex notifications.

Those tools cover broader notification workflows. This project is deliberately
narrow: it targets timed question cards inside the Codex VS Code extension and
stops the repeating alert on user interaction.

## License

MIT. See [LICENSE](LICENSE).
