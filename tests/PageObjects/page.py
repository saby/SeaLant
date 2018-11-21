# -*- coding: utf-8 -*-
from tests.PageObjects.locators import MainPageLocators


class BasePage(object):
    """Базовый класс для инициализации класса страницы"""

    def __init__(self, driver):
        self.driver = driver


class MainPage(BasePage):
    """Класс страницы"""

    def click_leak_button(self):
        """Нажатие на кнопку с созданием утечки"""
        element = self.driver.find_element(*MainPageLocators.LEAK)
        element.click()
        print('Создана утечка +1МБ (+1 DOM, +1 listener)')

    def click_no_leak_button(self):
        """Нажатие на кнопку без создания утечки"""
        element = self.driver.find_element(*MainPageLocators.NO_LEAK)
        element.click()
        print("Не создается утечка")
