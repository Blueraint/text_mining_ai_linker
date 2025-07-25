import re

class PrivacyUtils:
    @staticmethod
    def mask_pii(text: str) -> str:
        text = re.sub(r"(\d{6})[-]\d{7}", r"\1-*******", text)
        text = re.sub(r"(\d{3})[-]\d{2}[-]\d{5}", r"\1-**-*****", text)
        return text

    @staticmethod
    def log_securely(message: str):
        print(PrivacyUtils.mask_pii(message))