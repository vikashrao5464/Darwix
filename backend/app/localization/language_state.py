import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PH_LANGUAGES = {'en': ('en', 'english'), 'fil': ('fil', 'filipino'), 'fil-en': ('fil', 'taglish')}
ID_LANGUAGES = {'id-formal': ('id', 'formal'), 'id-colloquial': ('id', 'colloquial'), 'id-en-mixed': ('id', 'mixed')}


class LanguageState(BaseModel):
    model_config = ConfigDict(extra='forbid', serialize_by_alias=True)
    market: Literal['PH', 'ID']
    primary_language: str
    register_name: str = Field(alias='register')
    last_detected_language: str
    preferred_response_language: str

    @classmethod
    def create(cls, market, language=None):
        language = language or ('en' if market == 'PH' else 'id-formal')
        options = PH_LANGUAGES if market == 'PH' else ID_LANGUAGES
        if language not in options:
            raise ValueError('language_not_available_for_market')
        primary, register = options[language]
        return cls(market=market, primary_language=primary, register=register,
                   last_detected_language=language, preferred_response_language=language)

    def update(self, text, explicit=None):
        tokens = set(re.findall(r"[a-z]+", text.casefold()))
        language = explicit
        if not explicit and tokens <= {'yes', 'no', 'oo', 'opo', 'po', 'sige', 'ya', 'iya', 'boleh', 'baik', 'tidak', 'nggak', 'gak', 'hindi', 'thanks'}:
            return self
        if not language and self.market == 'PH':
            fil = tokens & {'ako', 'po', 'opo', 'oo', 'hindi', 'sige', 'pwede', 'puwede', 'magkano', 'kailan',
                            'bayad', 'paki', 'tao', 'kausap', 'wala', 'ng', 'nang', 'ang', 'naman', 'bukas', 'ano', 'gusto', 'kinatawan'}
            en = tokens & {'what', 'how', 'please', 'can', 'want', 'my', 'the', 'have', 'need', 'already', 'call',
                           'premium', 'policy', 'coverage', 'beneficiary', 'rider', 'lapse', 'callback', 'bank', 'referral'}
            # Particles in an otherwise uninterpretable ASR fragment do not
            # establish a language switch. Preserve the current fallback register.
            if fil - {'po', 'ng', 'nang', 'ang', 'naman'}:
                language = 'fil-en' if en else 'fil'
            elif len(tokens & {'what', 'how', 'please', 'want', 'already', 'have', 'need', 'english'}) >= 1:
                language = 'en'
        if not language and self.market == 'ID':
            # Short acknowledgements/finance terms alone preserve current register.
            mixed = tokens & {'payment', 'due', 'overdue', 'callback', 'cash', 'flow', 'installment'}
            colloquial = tokens & {'nggak', 'gak', 'ga', 'enggak', 'udah', 'aku', 'nih', 'dong', 'aja', 'banget', 'telpon'}
            formal = tokens & {'saya', 'mohon', 'silakan', 'bersedia', 'anda', 'apakah'}
            if mixed:
                language = 'id-en-mixed'
            elif colloquial:
                language = 'id-colloquial'
            elif formal:
                language = 'id-formal'
        if language:
            next_state = self.create(self.market, language)
            self.primary_language = next_state.primary_language
            self.register_name = next_state.register
            self.last_detected_language = language
            self.preferred_response_language = language
        return self

    @property
    def register(self):
        return self.register_name

    @property
    def asr_language(self):
        # Whisper calls Filipino/Tagalog "tl". Auto detection allows Taglish.
        return None if self.market == 'PH' and self.register == 'taglish' else 'tl' if self.primary_language == 'fil' else 'id' if self.market == 'ID' else 'en'

    @property
    def tts_language(self):
        return 'fil-en' if self.register == 'taglish' else 'fil' if self.primary_language == 'fil' else 'id' if self.market == 'ID' else 'en'
