import logging

LOGGER_NAME = 'ai_linker'
logger = logging.getLogger(LOGGER_NAME)

class LoggingMixin:
    """
    이 클래스를 상속받는 모든 클래스에게
    'self.logger'와 'self._log' 메소드를 제공하는 믹스인(Mixin).
    """
    @property
    def logger(self):
        # 클래스마다 고유한 이름의 로거를 생성 (예: 'AIAgent', 'ToolLoader')
        return logging.getLogger(self.__class__.__name__)

    def _log(self, message: str, level: str = 'info'):
        """
        콘솔 출력과 중앙 로거('ai_linker')에 로그 기록을 동시에 수행합니다.
        FastAPI 서버가 이 로그를 캡처합니다.
        """
        print(message)
        # 클래스 이름 대신, 통일된 중앙 로거를 사용
        getattr(logger, level, logger.info)(message)