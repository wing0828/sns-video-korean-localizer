import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xsubtitle.core import SubtitleCue, translate_cues_locally, transcribe_video


class QualityTests(unittest.TestCase):
    def test_english_model_and_release(self):
        calls = {}
        class Model:
            def __init__(self, name, **kwargs):
                calls['name'] = name
                self.model = SimpleNamespace(unload_model=lambda: calls.update(released=True))
            def transcribe(self, path, **kwargs):
                calls.update(kwargs)
                return iter([SimpleNamespace(start=0, end=1, text='Hello.')]), SimpleNamespace(duration=1)
        with patch.dict(sys.modules, {'faster_whisper': SimpleNamespace(WhisperModel=Model)}):
            self.assertEqual(transcribe_video(Path('video.mp4'), 'small'), [SubtitleCue(0,1,'Hello.')])
        self.assertEqual(calls['name'], 'small.en')
        self.assertEqual(calls['language'], 'en')
        self.assertEqual(calls['task'], 'transcribe')
        self.assertTrue(calls['released'])

    def test_each_sentence_translated_and_timing_preserved(self):
        calls = []
        class Translator:
            def __init__(self, *args, **kwargs): pass
            def translate_batch(self, tokens, **kwargs):
                calls.append((tokens, kwargs))
                return [SimpleNamespace(hypotheses=[['kor_Hang', '번역', '</s>']])]
            def unload_model(self): pass
        tokenizer = SimpleNamespace(encode=lambda text, **kwargs: [text], decode=lambda tokens: ''.join(tokens))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/'sentencepiece.bpe.model').touch()
            (path/'model.bin').touch()
            with patch.dict(os.environ, {'LOCAL_TRANSLATION_MODEL':directory}), patch.dict(sys.modules, {
                'ctranslate2':SimpleNamespace(Translator=Translator),
                'sentencepiece':SimpleNamespace(SentencePieceProcessor=lambda **kwargs:tokenizer),
            }):
                result=translate_cues_locally([SubtitleCue(3,7,'Hello. Thank you!')])
        self.assertEqual(result,[SubtitleCue(3,7,'번역 번역')])
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0][0][0][0],'eng_Latn')
        self.assertEqual(calls[0][1]['target_prefix'],[['kor_Hang']])
