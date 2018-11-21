# -*- coding: utf-8 -*-
"""
Exceptions
"""


class LeakError(Exception):
    """
    Найдена утечка
    """
    pass


class NoTimeStepError(Exception):
    """
    При записе таймлайна получилось менее 3 шагов
    """
    pass


class NoResultCalcError(Exception):
    """
    Нет результата для проверки утечки
    """
    pass
