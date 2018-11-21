# -*- coding: utf-8 -*-
"""
Модуль опеределения функции логгирования.
Можно в конфиге задать свою функццию логгирования
По умолчанию испоьзуется встроенная библиотека logging
"""
import logging
import sys

from sealant.config import MemoryLeakConfig

conf = MemoryLeakConfig


def log(*args, **kwargs):
    """
    Функция логгирования
    """
    return conf.logging_function(*args, **kwargs)


def set_logger():
    """
    Настраиваем логгирование. Если не задана внешняя функция - используется
    стандартная библиотека logging на уровне info
    """
    if not conf.logging_function:
        log_stream = logging.getLogger()
        log_stream.level = conf.logging_level
        stream = logging.StreamHandler(stream=sys.stdout)
        formatter = logging.Formatter('%(asctime)s %(message)s')
        stream.setFormatter(formatter)
        log_stream.addHandler(stream)
        conf.logging_function = log_stream.info
    return True
