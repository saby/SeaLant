# -*- coding: utf-8 -*-
from selenium.webdriver.common.by import By


class MainPageLocators(object):
    """Класс с локаторами"""
    NO_LEAK = (By.ID, 'noleak')
    LEAK = (By.ID, 'grow')
