# -*- coding: utf-8 -*-
"""
Модуль расчета heapsnapshot/heaptimeline.
Файл в формате json, для расчета достаточно получить списки nodes и samples.
nodes: ["type","name","id","self_size","edge_count","trace_node_id"] - параметры
ноды из кучи.
Для расчеты нужны поля: "id" - уникальный id ноды,"self_size" - размер в памяти
на момент сохранения для heapsnapshot или на момент останова записи для
heaptimeline.
samples: ["timestamp_us","last_assigned_id"]
временные отметки на heaptimeline. timestamp_us - время в мс,
last_assigned_id - id последней созданной ноды кучи
Для heapsnapshot список samples будет пустым.
"""


import json
from sealant.errors import NoResultCalcError, NoTimeStepError
from sealant.logger import log


class HeapObject:
    """
    Класс расчета heapsnapshot/heaptimeline
    Методы класса позволяют распарсить heap файл и рассчитать размеры
    кучи в каждом шаге heaptimeline или в каждом файле heapsnapshot.
    """
    def __init__(self, heapfile):
        """
        :param heapfile: Расположение heaptimeline/heapsnapshot
        """
        self.json_file = heapfile
        self.nodes = {}
        self.samples = []
        self.result = None

    def parsing_heap_file(self):
        """
        Парсинг json файла heaptimeline/heapsnapshot.
        """
        with open(self.json_file) as file:
            timeline = json.load(file)
            nodes = timeline['nodes']
            samples = timeline['samples']
            for i in range(len(nodes[::6])):
                self.nodes[int(nodes[i * 6 + 2])] = int(nodes[i * 6 + 3])
            self.samples = [[int(samples[i * 2]), int(samples[i * 2 + 1])]
                            for i in range(len((samples[::2])))]
        return True

    def get_leak_size(self, period_dur=''):
        """
        Расчет утечки по имеющимся self.nodes и self.samples
        Для расчета с таймлайном необходимо задать period_dur
        Для таймлайна - считается объем занятой памяти в каждый шаг,
        результат возвращается списком.
        Для снэпшота - считает общий объем занятой памяти,
        результат возвращается числом.
        :param period_dur: длительность одного шага, сек
        :return: результат расчета, КБ
        """
        if self.samples:
            if len(period_dur) < 5:
                raise NoTimeStepError("Количество шагов менее 5 для таймлайна")
            log('Старт расчета heaptimeline')
            period_dur = [x * 1000000 for x in period_dur]
            result = [0]
            step = 1
            nodes_keys = (key for key in sorted(self.nodes))
            nodes_key = 0
            while nodes_key <= self.samples[0][1]:
                nodes_key = next(nodes_keys)
            for timestamp_us, last_assigned_id in self.samples:
                curr_dur = sum(period_dur[:step])
                while timestamp_us > curr_dur and not step >= len(period_dur):
                    step += 1
                    result.append(0)
                    curr_dur = sum(period_dur[:step])
                while nodes_key <= last_assigned_id:
                    if step > 0:
                        result[step-1] += self.nodes[nodes_key]
                    nodes_key = next(nodes_keys)
            self.result = [x / 1000 for x in result[1:-1]]
            log('Результат {} КБ/шаг'.format(self.result))
        else:
            log('Старт расчета heapsnapshot')
            heap_sum = 0
            for nodes_key in sorted(self.nodes):
                heap_sum = heap_sum + self.nodes[nodes_key]
            self.result = heap_sum / 1000
            log('Результат {} КБ'.format(self.result))
        return self.result


def check_leak_with_timeline(steps, result, leak_size_limit):
    """
    Проверка наличия утечки в подаваемых на вход данных result.
    :param result: список с размерами кучи в каждом шаге таймлайна, КБ
    :param steps: количество повторов тестируемой функции
    :param leak_size_limit: размер уставки для сигнализации об утечке памяти, КБ
    :return: размер утечки в КБ, наличие утечки
    """
    if len(result) < 2:
        raise NoResultCalcError('В аргументе result менее 2 значений')
    leak_size = 0
    for i in range(int(steps*0.5) + 1):
        leak_size += sorted(result)[i]
    leak_size /= int(steps*0.5) + 1
    is_leak = True if leak_size > leak_size_limit else False
    return leak_size, is_leak


def check_leak_with_snapshots(result, leak_size_limit):
    """
    Проверка наличия утечки в подаваемых на вход данных result.
    Используется метод аппроксимации размеров кучи в снэпшотах, и определение
    приблизительного размера утечки между конечным точками полученного отрезка.
    :param result: список с размерами кучи в каждом снэпшоте, КБ
    :param leak_size_limit: размер уставки для сигнализации об утечке памяти, КБ
    :return: размер утечки в КБ, наличие утечки
    """
    if len(result) < 2:
        raise NoResultCalcError('В аргументе result менее 2 значений')
    steps = len(result)
    sum_leaks = 0
    sum_steps = 0
    sum_steps2 = 0
    leaks_steps = 0
    for i in range(steps):
        sum_leaks += result[i]
        sum_steps += i + 1
        sum_steps2 += (i + 1) ** 2
        leaks_steps += (i + 1) * result[i]
    a = steps * sum_steps2 - sum_steps ** 2
    a1 = steps * leaks_steps - sum_steps * sum_leaks
    leak_size = a1 / a
    is_leak = True if leak_size > leak_size_limit else False
    return leak_size, is_leak
