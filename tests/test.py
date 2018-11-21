# -*- coding: utf-8 -*-
"""
Пример использования декораторов для нахождения утечек памяти
"""

from os import getcwd
from unittest import TestCase, main

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from sealant import memleak
from tests.PageObjects.page import MainPage


class TestsCaseExample(TestCase):

    @classmethod
    def setUpClass(cls):
        binary = r'.\bin\chromedriver'
        options = Options()
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--headless")
        options.add_argument("--proxy-bypass-list=*")
        options.add_argument("--proxy-server='direct://'")
        options.add_argument("--incognito")
        options.add_argument("--start-maximized")
        options.add_argument("--window-size=1920,1080")
        cls.driver = webdriver.Chrome(executable_path=binary, options=options)
        cls.driver.get(url='file:///'+getcwd()+'/index.html')

    def setUp(self):
        self.page = MainPage(self.driver)

    @memleak(timeline=True)
    def test_leak_timeline(self):
        """Есть утечка, замер таймлайном"""
        self.page.click_leak_button()

    @memleak(timeline=False)
    def test_leak_snap(self):
        """Есть утечка, замер снэпшотом"""
        self.page.click_leak_button()

    @memleak(timeline=True)
    def test_no_leak_timeline(self):
        """Нет утечки, замер таймлайном"""
        self.page.click_no_leak_button()

    @memleak(timeline=False)
    def test_no_leak_snap(self):
        """Нет утечки, замер снэпшотом"""
        self.page.click_no_leak_button()

    def test_no_checking_leak(self):
        """Есть утечка, нет замера"""
        self.page.click_leak_button()

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()


if __name__ == '__main__':
    main()
