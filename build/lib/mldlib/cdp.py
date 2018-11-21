# -*- coding: utf-8 -*-
"""
Модуль для подключения и получения данных с ноды(Chrome/Node.js)
- снэпшотов/таймлайнов, размер DOM дерева, количевство EventListeners и др.
с использованием pyСhrome библиотеки.
Используется Chrome DevTools Protocol:
https://chromedevtools.github.io/devtools-protocol
"""


from datetime import datetime
import json
import pathlib
from time import time, sleep
import pychrome
import requests
from sealant.config import SeaLantConfig
from sealant.logger import log


conf = SeaLantConfig()


class DevToolsProtocolConnection:
    """
    Класс для подключения и обмена информацией с нодой
    """
    def __init__(self, host='', port='', ws=''):
        """
        :param host: хост для подключения к ноде
        :param port: порт для подключения к ноде
        :param ws: адрес ws:// для подключения к ноде
        """
        self.class_host = host
        self.class_port = port
        self.class_ws = ws
        self.last_response = time()   # Время последнего ответа для определения завершения сетевой активности по http
        self.requests = [set(), set()]  # [активные запросы, все вызванные методы]
        self.stats_all = [[0, 0, 0]]  # Список обновления фрагментов памяти вида [идентификатор, число объектов, размер]
        self.started = False
        self.name = 'undefined'

    def connect_to_node(self, host, port, ws_url=''):
        """
        Подключение к ноду. Если задан адрес ws - сразу подключается к нему.
        Иначе получаем адрес используя заданный хост/порт
        :param host: хост для подключения к ноде
        :param port: порт для подключения к ноде
        :param ws_url: адрес для  подключения к вебсокету ноды ws://
        """
        websocket_url = ws_url or self._websocket_debugger_url(host, port)
        self.tab = pychrome.Tab(description='mld', id='mld', type='mld',
                                webSocketDebuggerUrl=websocket_url)
        self.tab.start()
        self.started = True
        log('Подключено к ноде: {}'.format(websocket_url))
        return True

    @staticmethod
    def _websocket_debugger_url(host, port):
        """
        Получение адреса ws по хосту/порту
        :return: адрес ws
        """
        geturl = requests.get("{0}:{1}/json".format(host, port))
        return json.loads(geturl.content)[0]['webSocketDebuggerUrl']

    def disconnect_from_node(self):
        """
        Отключение от ноды и удаление подписок на события.
        При использовании стандартноо метода tab.stop валится ошибка о
        получении сообщения Null. Поэтому вручную останавливаем цикл мониторящий
        получаемые сообщения и закрываем ws.
        """
        self.tab._stopped.set()
        self.tab.wait()
        self.tab.stop()
        self.tab.del_all_listeners()
        self.started = False
        log('Отключено от ноды')
        return True

    def get_heap_file(self, timeline=True):
        """
        Функция получения снэпшота/таймлайна.
        :param timeline: True/False - heaptimeline/heapsnapshot
        :return: относительный путь загруженного файла
        """
        heap_profiler = self.tab.HeapProfiler
        heap_profiler.addHeapSnapshotChunk = self._record_heapchunks_to_file
        heap_file_type = 'heaptimeline' if timeline else 'heapsnapshot'
        path = "{0}s/{1}/".format(heap_file_type, self.name)
        pathlib.Path(path).mkdir(parents=True, exist_ok=True)
        heap_file_name = '{0}%H_%M_%S.{1}'.format(path, heap_file_type)
        self.heap_file_name = datetime.strftime(datetime.now(), heap_file_name)
        self.heap_file_out = open(self.heap_file_name, 'w')
        log('Получение ' + heap_file_type)
        if timeline:
            heap_profiler.stopTrackingHeapObjects()
        else:
            heap_profiler.takeHeapSnapshot()
        self._last_record_chunk_time = time()
        while time() - self._last_record_chunk_time < 2:
            sleep(1)
        log('Получено')
        self.heap_file_out.close()
        return self.heap_file_name

    def get_metrics(self):
        """
        :return: значения заданных в конфиге дополнительных метрик
        """
        result = []
        if conf.metrics:
            for metric_params in conf.metrics:
                metric = self.tab.Runtime.evaluate(expression=metric_params[0],
                                                   includeCommandLineAPI=True,
                                                   returnByValue=True)
                result.append(metric['result']['value'])
        return result

    def activate_wait_func(self):
        """
        Активируем домен Network и вешаем подписчиков для использования
        функции ожидания завершения загрузки.
        """
        self.tab.Network.enable()
        self.tab.Network.requestWillBeSent = self._update_sent_requests
        self.tab.Network.loadingFailed = self._update_network_responses
        self.tab.Network.loadingFinished = self._update_network_responses
        self.tab.HeapProfiler.heapStatsUpdate = self._update_memory_allocation
        return True

    def wait_full_load(self, time_after_last_resp=7, heap_interval_min=2,
                       heap_interval_max=7, max_heap_size=10000):
        """
        Метод полного ожидания завершения действия по двум критериям.
        Критерий сети: Нет уникальных активных запросов в течение
        заданного времени (по дефолту 7 сек).
        Критерий памяти (КП): объем памяти за заданный промежуток времени
        менее заданной уставки.
        (по умолчанию за промежуток с 2 до 7 сек от текущего момента времени)
        Если ожидание более 300 сек - продолжаем тест.
        Для использования необходимо добавить:
        self.cdp.wait_full_load()
        в самом тесте после строки, в которой необходимо дождаться завершения
        загрузки (см. tests/test.py).
        :param time_after_last_resp: время с последнего уникального запроса, сек
        :param heap_interval_min: начало заданного промежутка для КП, сек
        :param heap_interval_max: конец заданного промежутка для КП, сек
        :param max_heap_size: уставка объема памяти, байт
        """
        self.last_response = time()
        start_cycle = time()
        rules = [True]
        while any(rules):
            if time() - start_cycle > 300:
                log('Не дождались завершения загрузки за 300 секунд')
                break
            start = time()
            size = 0
            size_last = 0
            for statsallnew in sorted(self.stats_all, reverse=True):
                if statsallnew[0] > start - heap_interval_min:
                    size_last += statsallnew[2]
                elif statsallnew[0] > start - heap_interval_max:
                    size += statsallnew[2]
                else:
                    break
            rules = [size_last > max_heap_size * 10, size > max_heap_size,
                     len(self.requests[0]) > 0,
                     (time() - self.last_response) < time_after_last_resp]
        self.stats_all = [[0, 0, 0]]
        self.requests = [set(), set()]
        log('Загружено')
        return True

    def twice_collect_garbage(self):
        """
        Дважды вызывает GC
        """
        self.tab.HeapProfiler.collectGarbage()
        self.tab.HeapProfiler.collectGarbage()
        log('Вызов GC')
        return True

    def _update_memory_allocation(self, **kwargs):
        """
        Обработчик, получающий и обрабатывающий обновления объемов памяти,
        занимаемых фрагментами.
        Все новые фрагменты добавляются к "self.stats_all",
        у существующих обновляется объем занимаемой памяти.
        Сообщения состоят из триплетов:
        id фрагмента, кол-во объектов во фрагменте, объем занимаемой памяти.
        """
        stats_update = kwargs['statsUpdate']
        stats = ([time(), stats_update[i], stats_update[i + 2]]
                 for i in range(0, len(stats_update), 3))
        for stat in stats:
            indexes = [indexes[1] for indexes in self.stats_all]
            if stat[1] in indexes:
                i = indexes.index(stat[1])
                self.stats_all[i][2] = stat[2]
            else:
                self.stats_all.append(stat)

    def _update_sent_requests(self, **kwargs):
        """
        Обработчик http запросов.
        Все новые запросы добавляются к "self.requests" .
        Если не задан/не найден уникальный header - то добавляется по requestId.
        """
        try:
            method_name = kwargs['request']['headers'][conf.unique_header_name]
        except KeyError:
            method_name = kwargs['requestId']
        if method_name not in self.requests[1]:
            self.requests[1].add(method_name)
            self.requests[0].add(kwargs['requestId'])

    def _update_network_responses(self, **kwargs):
        """
        Обработчик http ответов.
        При получаении ответа если id есть в запросах - он удаляется из активных
        """
        try:
            self.requests[0].remove(kwargs['requestId'])
            self.last_response = time()
        except KeyError:
            pass

    def _record_heapchunks_to_file(self, **kwargs):
        """
        Обработчик чанков снапшота/таймлайна.
        """
        self.heap_file_out.write(kwargs['chunk'])
        self._last_record_chunk_time = time()
