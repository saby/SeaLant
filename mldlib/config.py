# -*- coding: utf-8 -*-


class MemoryLeakConfig(object):
    """
    Конфигурация.
    Можно подключить метрики, которые будут сниматься перед и после тестов
    и сравниваться между собой.
    Например, размер DOM дерева и количество EventListeners до и после тестов.
    func_metric - код для выполнения черещ домен Runtime
    metrics - кортеж с метриками
    В ответ приходит словарь, откуда достается ['result']['value']
    """

    number_of_test_repeats = 5             # Количество повторов теста в течение одной проверки (для таймлайна необходимо добавить 1 прогревочный и 1 последний повтор)
    unique_header_name = 'unique_header'   # Заголовок запроса, по которому определяется уникальность метода
    host = 'http://localhost'              # Хост для подключения к ноде
    port = '9222'                          # Порт для подключения к ноде
    websocket_url = ''                     # Адрес для  подключения к вебсокету ноды ws://
    measure_repeat = 1                     # Количество перепроверок найденной утечки
    logging_level = 20                     # 0 - NOTSET; 10 - DEBUG; 20 -INFO; 30 - WARNING; 40 - ERROR; 50 - CRITICAL
    leak_size_limit = 400                  # Порог утечки, после которого сигнализировать о ее наличии, КБ
    logging_function = None                # Внешняя функция логгирования, None - внутреннее логгирование
    default_wait_full_load = True          # Использовать функцию ожидания завершения загрузки после каждого повторения теста
                                           # Иначе - можно самостоятельно выбрать место запуска этой функции или не использовать ее
    save_leaked_heapfile = True            # Сохранение heapfile в случае нахождения утечки
    get_xml_table = True                   # Составление xml отчета в случае нахождения утечки
    path_to_save = ''                      # Путь сохранения архива с отчетом и heapfile, по умолчанию создается папка leaks в папке с тестом

    # Дополнительные метрики

    func_metric_1 = "document.getElementsByTagName('*').length"
    func_metric_2 = """
                    Array.from(document.querySelectorAll('*'))
                      .reduce(function(pre, dom){
                        var clks = getEventListeners(dom).click;
                        pre += clks ? clks.length || 0 : 0;
                        return pre
                      }, 0)
                    """
    metrics = (
        (func_metric_1, "DOM элементы"),
        (func_metric_2, "EventListeners")
    )
    cdp = None
    clear_conf_cdp = True
    time_after_last_resp = 7
    heap_interval_min = 2
    heap_interval_max = 7
    max_heap_size = 10000
