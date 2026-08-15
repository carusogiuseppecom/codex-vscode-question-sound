import unittest

from patch_codex_extension import PATCH_MARKER, PatchError, patch_source


FIXTURE = (
    'nv=class{constructor(e){this.options=e}'
    'pendingRequestByConversationId=new Map;conversationIdByRequestId=new Map;'
    'observeServerRequest(e){if(e.method==="item/tool/requestUserInput")'
    '{let n=e.params.threadId;return}}'
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
    def test_adds_sound_and_stops_explicit_countdown(self) -> None:
        patched, changed = patch_source(FIXTURE)
        self.assertTrue(changed)
        self.assertIn(PATCH_MARKER, patched)
        self.assertIn("this.playQuestionSound();", patched)
        self.assertIn("this.startQuestionSound(e)", patched)
        self.assertIn("/usr/bin/afplay", patched)
        self.assertIn("/System/Library/Sounds/Tink.aiff", patched)
        self.assertNotIn("this.startCountdown(e,n,n.autoResolutionMs)", patched)

    def test_is_idempotent(self) -> None:
        patched, _ = patch_source(FIXTURE)
        patched_again, changed = patch_source(patched)
        self.assertFalse(changed)
        self.assertEqual(patched, patched_again)

    def test_rejects_unknown_bundle(self) -> None:
        with self.assertRaisesRegex(
            PatchError, "The Codex extension bundle may have changed"
        ):
            patch_source("un bundle futuro e incompatibile")


if __name__ == "__main__":
    unittest.main()
