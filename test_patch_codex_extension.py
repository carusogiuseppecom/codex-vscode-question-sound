import unittest

from patch_codex_extension import (
    LEGACY_PATCH_MARKER,
    ORIGINAL_NOTIFICATION_HANDLER,
    PATCHED_NOTIFICATION_HANDLER,
    PATCH_MARKER,
    PatchError,
    patch_source,
)


FIXTURE = (
    'nv=class{constructor(e){this.options=e}'
    'pendingRequestByConversationId=new Map;conversationIdByRequestId=new Map;'
    'observeServerRequest(e){if(e.method==="item/tool/requestUserInput")'
    '{let n=e.params.threadId;return}}'
    f'{ORIGINAL_NOTIFICATION_HANDLER}'
    'snoozeRequest(e,r){let n=this.pendingRequestByConversationId.get(e);'
    'if(!(n==null||n.requestId!==r)){if(n.autoResolutionMs!=null)'
    '{this.startCountdown(e,n,n.autoResolutionMs);return}'
    'this.cancelPendingRequestDeadline(n),n.resolutionState={status:"snoozed"},'
    'this.publishState(e,n)}}'
    'startCountdown(e,r,n){this.setPendingRequestTimeout(r,n,()=>{switch(n)'
    '{case"x":break}}),this.publishState(e,r)}setPendingRequestTimeout(e,r,n){}'
    'cancelPendingRequestDeadline(e){let r=e.timeoutId;'
    'r!=null&&(e.timeoutId=null,clearTimeout(r))}}'
)


class PatchSourceTests(unittest.TestCase):
    def test_adds_question_and_successful_completion_sounds(self) -> None:
        patched, changed = patch_source(FIXTURE)
        self.assertTrue(changed)
        self.assertIn(PATCH_MARKER, patched)
        self.assertIn("this.playQuestionSound();", patched)
        self.assertIn("this.startQuestionSound(e)", patched)
        self.assertIn("/usr/bin/afplay", patched)
        self.assertIn("/System/Library/Sounds/Tink.aiff", patched)
        self.assertIn("/System/Library/Sounds/Glass.aiff", patched)
        self.assertIn(PATCHED_NOTIFICATION_HANDLER, patched)
        self.assertIn('e.params.turn?.status==="completed"', patched)
        self.assertNotIn("this.startCountdown(e,n,n.autoResolutionMs)", patched)

    def test_is_idempotent(self) -> None:
        patched, _ = patch_source(FIXTURE)
        patched_again, changed = patch_source(patched)
        self.assertFalse(changed)
        self.assertEqual(patched, patched_again)

    def test_upgrades_version_1_without_duplicating_question_hooks(self) -> None:
        version_2, _ = patch_source(FIXTURE)
        version_1 = version_2.replace(PATCH_MARKER, LEGACY_PATCH_MARKER, 1)
        completion_method_start = version_1.index("playCompletionSound()")
        completion_method_end = version_1.index(
            "startQuestionSound(e)", completion_method_start
        )
        version_1 = (
            version_1[:completion_method_start]
            + version_1[completion_method_end:]
        ).replace(
            PATCHED_NOTIFICATION_HANDLER,
            ORIGINAL_NOTIFICATION_HANDLER,
            1,
        )

        upgraded, changed = patch_source(version_1)

        self.assertTrue(changed)
        self.assertIn(PATCH_MARKER, upgraded)
        self.assertNotIn(LEGACY_PATCH_MARKER, upgraded)
        self.assertEqual(upgraded.count("this.playQuestionSound();"), 1)
        self.assertEqual(upgraded.count("playCompletionSound()"), 2)
        self.assertIn("/System/Library/Sounds/Glass.aiff", upgraded)

    def test_rejects_unknown_bundle(self) -> None:
        with self.assertRaisesRegex(
            PatchError, "The Codex extension bundle may have changed"
        ):
            patch_source("un bundle futuro e incompatibile")


if __name__ == "__main__":
    unittest.main()
