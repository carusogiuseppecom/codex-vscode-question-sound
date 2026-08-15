#!/usr/bin/env python3
"""Add an audible question alert to the installed Codex VS Code extension.

The patch is deliberately narrow: it changes only the request-user-input
coordinator in OpenAI's extension bundle and keeps a byte-for-byte backup.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


EXTENSION_ID = "openai.chatgpt"
PATCH_MARKER = "CODEX_QUESTION_SOUND_PATCH_V1"
BACKUP_SUFFIX = ".codex-question-sound.original"


class PatchError(RuntimeError):
    pass


def _replace_once(source: str, old: str, new: str, description: str) -> str:
    count = source.count(old)
    if count != 1:
        raise PatchError(
            f"Could not locate {description} exactly once (found {count} matches). "
            "The Codex extension bundle may have changed."
        )
    return source.replace(old, new, 1)


def patch_source(source: str) -> tuple[str, bool]:
    """Return (patched_source, changed)."""
    if PATCH_MARKER in source:
        return source, False

    class_start = (
        'nv=class{constructor(e){this.options=e}'
        'pendingRequestByConversationId=new Map;'
    )
    sound_support = (
        'nv=class{constructor(e){this.options=e}'
        f'codexQuestionSoundPatch="{PATCH_MARKER}";'
        'questionSoundIntervals=new Map;'
        'playQuestionSound(){if(process.platform!=="darwin")return;try{'
        'let e=require("node:child_process").spawn("/usr/bin/afplay",'
        '["/System/Library/Sounds/Tink.aiff"],{stdio:"ignore"});'
        'e.once("error",()=>{}),e.unref()}catch{}}'
        'startQuestionSound(e){this.stopQuestionSound(e);'
        'let r=setInterval(()=>this.playQuestionSound(),1e3);'
        'r.unref?.(),this.questionSoundIntervals.set(e,r)}'
        'stopQuestionSound(e){let r=this.questionSoundIntervals.get(e);'
        'r!=null&&(clearInterval(r),this.questionSoundIntervals.delete(e))}'
        'pendingRequestByConversationId=new Map;'
    )
    source = _replace_once(
        source, class_start, sound_support, "the user-input request coordinator"
    )

    request_start = (
        'observeServerRequest(e){if(e.method==="item/tool/requestUserInput")'
        '{let n=e.params.threadId;'
    )
    source = _replace_once(
        source,
        request_start,
        request_start + "this.playQuestionSound();",
        "the Codex question event handler",
    )

    old_snooze = (
        'snoozeRequest(e,r){let n=this.pendingRequestByConversationId.get(e);'
        'if(!(n==null||n.requestId!==r)){if(n.autoResolutionMs!=null)'
        '{this.startCountdown(e,n,n.autoResolutionMs);return}'
        'this.cancelPendingRequestDeadline(n),n.resolutionState='
        '{status:"snoozed"},this.publishState(e,n)}}'
    )
    new_snooze = (
        'snoozeRequest(e,r){let n=this.pendingRequestByConversationId.get(e);'
        'if(!(n==null||n.requestId!==r)){this.cancelPendingRequestDeadline(n),'
        'n.resolutionState={status:"snoozed"},this.publishState(e,n)}}'
    )
    source = _replace_once(
        source,
        old_snooze,
        new_snooze,
        "the question interaction handler",
    )

    countdown_tail = (
        'break}}),this.publishState(e,r)}setPendingRequestTimeout'
    )
    source = _replace_once(
        source,
        countdown_tail,
        'break}}),this.startQuestionSound(e),this.publishState(e,r)}'
        'setPendingRequestTimeout',
        "the countdown start handler",
    )

    cancel_deadline = (
        'cancelPendingRequestDeadline(e){let r=e.timeoutId;'
        'r!=null&&(e.timeoutId=null,clearTimeout(r))}'
    )
    source = _replace_once(
        source,
        cancel_deadline,
        'cancelPendingRequestDeadline(e){this.stopQuestionSound('
        'this.conversationIdByRequestId.get(e.requestId)??"");'
        'let r=e.timeoutId;r!=null&&(e.timeoutId=null,clearTimeout(r))}',
        "the countdown cancellation handler",
    )

    return source, True


def active_extension_directory() -> Path:
    extensions_root = Path.home() / ".vscode" / "extensions"
    registry = extensions_root / "extensions.json"
    if registry.is_file():
        try:
            entries = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PatchError(f"Could not read the VS Code extension registry: {exc}") from exc

        matches = [
            entry
            for entry in entries
            if entry.get("identifier", {}).get("id") == EXTENSION_ID
        ]
        if matches:
            newest = max(
                matches,
                key=lambda entry: entry.get("metadata", {}).get(
                    "installedTimestamp", 0
                ),
            )
            fs_path = newest.get("location", {}).get("fsPath")
            if fs_path:
                return Path(fs_path)

    candidates = list(extensions_root.glob("openai.chatgpt-*"))
    if not candidates:
        raise PatchError("Could not find openai.chatgpt in ~/.vscode/extensions")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def atomic_write(path: Path, data: str) -> None:
    mode = path.stat().st_mode
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def patch_extension(extension_dir: Path, dry_run: bool = False) -> str:
    bundle = extension_dir / "out" / "extension.js"
    backup = bundle.with_name(bundle.name + BACKUP_SUFFIX)
    if not bundle.is_file():
        raise PatchError(f"Could not find the extension bundle: {bundle}")

    original = bundle.read_text(encoding="utf-8")
    patched, changed = patch_source(original)
    if not changed:
        return f"The patch is already installed in {bundle}"
    if dry_run:
        return f"Compatibility check passed: {bundle} can be patched"

    if not backup.exists():
        shutil.copy2(bundle, backup)
    atomic_write(bundle, patched)
    return f"Installed the patch in {bundle}\nBackup: {backup}"


def restore_extension(extension_dir: Path, dry_run: bool = False) -> str:
    bundle = extension_dir / "out" / "extension.js"
    backup = bundle.with_name(bundle.name + BACKUP_SUFFIX)
    if not backup.is_file():
        raise PatchError(f"Could not find the original bundle backup: {backup}")
    if dry_run:
        return f"The original bundle backup is available: {backup}"
    shutil.copy2(backup, bundle)
    return f"Restored the original bundle to {bundle}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add audible Codex question alerts to VS Code on macOS."
    )
    parser.add_argument(
        "--extension-dir",
        type=Path,
        help="Path to an openai.chatgpt-* directory; defaults to the active one.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check compatibility without changing the extension bundle.",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore the byte-for-byte backup created during installation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if sys.platform != "darwin":
            raise PatchError("This patch supports macOS only.")
        extension_dir = args.extension_dir or active_extension_directory()
        if args.restore:
            message = restore_extension(extension_dir, args.dry_run)
        else:
            message = patch_extension(extension_dir, args.dry_run)
    except (OSError, PatchError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
