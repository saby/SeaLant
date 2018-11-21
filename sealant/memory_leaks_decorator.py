# -*- coding: utf-8 -*-
"""
Модуль с основной логикой для декоратора.
Для общения с нодой(Chrome/Node.js) используется Chrome DevTools Protocol:
https://chromedevtools.github.io/devtools-protocol/
"""

import inspect
import pathlib
import shutil
import xml.etree.ElementTree as xml
from functools import wraps
from time import sleep, time

from sealant.cdp import DevToolsProtocolConnection
from sealant.config import MemoryLeakConfig
from sealant.errors import LeakError
from sealant.heapfile_processing import HeapObject, check_leak_with_timeline
from sealant.heapfile_processing import check_leak_with_snapshots
from sealant.logger import log, set_logger

conf = MemoryLeakConfig()


def memleak(timeline=True, host='', port='', ws='',
            wait_func=True):
    """
    Декорируемый объект может быть классом или методом.
    В случае класса устанавливаются параметры подключения к ноде для всех
    тестируемых методов декорируемого класса.
    В случае метода устанавливаются параметры подключения к ноде для текущего
    метода, происходит подключение к ноде, действия по нахождению
    утечки и отключение от ноды.
    Заданные хост/порт или адрес вебсокета имеют следующий приоритет в порядке
    убывания:
    1. В декораторе метода
    2. В декораторе класса
    3. В config.py
    Можно задать только хост/порт или только адрес ws. Заданный адрес ws
    имеет приоритет над хостом/портом.
    :param timeline: если False - проверка с помощью снэпшотов
    :param host: хост для подключения к ноде
    :param port: порт для подключения к ноде
    :param ws: адрес ws:// для подключения к ноде
    :param node_js: нода - Node.js, проверка только размера утечки
    :param wait_func: активировать возможность использования метода cdp.wait_full_load
    """
    def wrapper(obj):
        if inspect.isclass(obj):
            return _wrapper_for_class(obj, host=host, port=port, ws=ws)
        elif inspect.isfunction(obj):
            @wraps(obj)
            def test(*args, **kwargs):
                _wrapper_for_test(obj, timeline, host, port, ws,
                                  wait_func, *args, **kwargs)
            return test
    return wrapper


def _wrapper_for_class(obj, host, port, ws):
    """
    Функция обработки класса в декораторе.
    :param obj: декорируемый класс
    :param host: хост для подключения к ноде
    :param port: порт для подключения к ноде
    :param ws: адрес ws:// для подключения к ноде
    :return: декорируемый класс с привязанным экземпляром класса
    """
    set_logger()
    obj.cdp = conf.cdp = DevToolsProtocolConnection(host=host, port=port, ws=ws)
    conf.clear_conf_cdp = False
    return obj


def _wrapper_for_test(obj, timeline, host, port, ws, wait_func,
                      *args, **kwargs):
    """
    Функция обработки теста в декораторе.
    :param obj: декорируемый тест
    :param timeline: если False - проверка с помощью снэпшотов
    :param host: хост для подключения к ноде
    :param port: порт для подключения к ноде
    :param ws: адрес ws:// для подключения к ноде
    :param wait_func: активировать возможность использования метода cdp.wait_full_load
    """
    if conf.clear_conf_cdp:
        set_logger()
        conf.cdp = DevToolsProtocolConnection(host=host, port=port,
                                                        ws=ws)
    cdp = obj.cdp = conf.cdp
    cdp.name = obj.__name__
    host_name = host or cdp.class_host or conf.host
    port_num = port or cdp.class_port or conf.port
    websocket_url = ws or cdp.class_ws or conf.websocket_url or ''
    cdp.connect_to_node(host_name, port_num, websocket_url)
    cdp.tab.HeapProfiler.enable()
    if wait_func:
        cdp.activate_wait_func()
    measure_repeat = conf.measure_repeat + 1
    step_repeat = conf.number_of_test_repeats
    heap_type = 'heaptimeline' if timeline else 'heapsnapshot'
    for i in range(measure_repeat):
        log('Количество повторов: {0}/{1} '
            'Шагов: {2} '
            'Heap файл: {3}'.format(i + 1, measure_repeat,
                                    step_repeat, heap_type))
        result_metric = []
        dif_result_metrics = []
        result_metric.append(cdp.get_metrics())
        if timeline:
            result = _meas_timeline(obj, step_repeat, wait_func,
                                    *args, **kwargs)
        else:
            result = _meas_snapshot(obj, step_repeat,
                                    *args, **kwargs)
        leaksize, leak = result
        log('Leak is {:.2f} KB'.format(leaksize))
        if result_metric[0]:
            print(result_metric)
            result_metric.append(cdp.get_metrics())
            for j in range(len(result_metric)):
                dif = (result_metric[1][j] - result_metric[0][j]) / step_repeat
                if dif:
                    dif_result_metrics.append([dif, conf.metrics[j][1]])
                    log("Добавлено {}/шаг: {}".format(conf.metrics[j][1], dif))
        if not leak:
            break
        step_repeat += 2
    cdp.disconnect_from_node()
    if leak:
        need_zip = False
        if conf.get_xml_table:
            _create_xml_report(cdp, leaksize, dif_result_metrics, heap_type)
            need_zip = True
        if conf.save_leaked_heapfile:
            print(pathlib.Path('leaks').mkdir(parents=True, exist_ok=True))
            path = "{0}s/{1}".format(heap_type, cdp.name)
            heap_file_location = '{0}leaks/{1}'.format(conf.path_to_save,
                                                       cdp.name)
            need_zip = True
        if need_zip:
            print(shutil.make_archive(heap_file_location, format='zip', root_dir=path))
        shutil.rmtree('{}s'.format(heap_type))
        raise LeakError("В тесте есть утечка")
    shutil.rmtree('{}s'.format(heap_type))
    return True


def _meas_timeline(decorated_function, step_repeat, wait_func,
                   *args, **kwargs):
    """
    Замер утечки с использованием таймлайна.
    Количество повторов тестируемой функции увеличивается на 2:
    добавляются прогревочный и завершающий шаги
    :param decorated_function: тестируемая функция
    :param step_repeat: количество повторов тестируемой функции
    :param args: аргументы тестируемой функции
    :param kwargs: аргументы тестируемой функции
    :return: (размер утечки в шаге в КБ, наличие утечки boolean)
    """
    cdp = conf.cdp
    cdp.tab.HeapProfiler.startTrackingHeapObjects()
    time_of_steps = []
    for i in range(step_repeat):
        start_step = time()
        sleep(0.1)
        decorated_function(*args, **kwargs)
        if conf.default_wait_full_load and wait_func:
            cdp.wait_full_load()
        cdp.twice_collect_garbage()
        time_of_steps.append(time() - start_step)
    heap_file = cdp.get_heap_file(timeline=True)
    heap_calc = HeapObject(heapfile=heap_file)
    heap_calc.parsing_heap_file()
    result = heap_calc.get_leak_size(period_dur=time_of_steps)
    return check_leak_with_timeline(result=result,
                                    leak_size_limit=conf.leak_size_limit)


def _meas_snapshot(decorated_function, step_repeat, *args, **kwargs):
    """
    Замер утечки с использованием снэпшота.
    Перед тестом два прогревочных повторая
    :param decorated_function: тестируемая функция
    :param step_repeat: количество повторов тестируемой функции
    :param args: аргументы тестируемой функции
    :param kwargs: аргументы тестируемой функции
    :return: (размер утечки в шаге в КБ, наличие утечки boolean)
    """
    cdp = conf.cdp
    heap_files = []
    results = []
    for i in range(step_repeat):
        decorated_function(*args, **kwargs)
        cdp.twice_collect_garbage()
        heap_files.append(cdp.get_heap_file(timeline=False))
    for heap_file in heap_files:
        heap_calc = HeapObject(heapfile=heap_file)
        heap_calc.parsing_heap_file()
        results.append(heap_calc.get_leak_size())
    result = check_leak_with_snapshots(result=results,
                                       leak_size_limit=conf.leak_size_limit)
    return result


def _create_xml_report(cdp, leaksize, dif_result_metrics, heap_type):
    root = xml.Element("root")
    main_report = xml.Element("LeakReport")
    root.append(main_report)
    name_report = xml.SubElement(main_report, "TestName")
    name_report.text = cdp.name
    leak_report = xml.SubElement(main_report, "LeakSize")
    leak_report.text = 'Утечка за шаг: {:.2f} KB'.format(leaksize)
    if dif_result_metrics:
        metric_report = []
        for i, dif in enumerate(dif_result_metrics):
            metric_report.append(
                xml.SubElement(main_report, 'Metric_{}'.format(i + 1)))
            metric_report[i].text = "Добавлено {0}/шаг: {1}".format(dif[1],
                                                                    dif[0])
    heap_file_report = xml.SubElement(main_report, 'HeapFile')
    heap_file_report.text = "Cохранение heapfile: {}".format(
        conf.save_leaked_heapfile)
    tree = xml.ElementTree(root)
    with open('{0}s/{1}/report.xml'.format(heap_type, cdp.name), 'wb') as fh:
        tree.write(fh, xml_declaration=True, encoding='utf-8')
