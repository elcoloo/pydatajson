#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Módulo 'indicators' de Pydatajson

Contiene los métodos para monitorear y generar indicadores de un catálogo o de
una red de catálogos.
"""

from __future__ import print_function, absolute_import, unicode_literals, with_statement

import json
import os
from datetime import datetime

from six import string_types

from . import helpers
from . import readers
from .reporting import generate_datasets_summary

CENTRAL_CATALOG = "http://datos.gob.ar/data.json"
ABSOLUTE_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_FIELDS_PATH = os.path.join(ABSOLUTE_PROJECT_DIR, "fields")


def generate_catalogs_indicators(catalogs, central_catalog=None,
                                 validator=None):
    """Genera una lista de diccionarios con varios indicadores sobre
    los catálogos provistos, tales como la cantidad de datasets válidos,
    días desde su última fecha actualizada, entre otros.

    Args:
        catalogs (str o list): uno o más catalogos sobre los que se quiera
            obtener indicadores
        central_catalog (str): catálogo central sobre el cual comparar los
            datasets subidos en la lista anterior. De no pasarse no se
            generarán indicadores de federación de datasets.

    Returns:
        tuple: 2 elementos, el primero una lista de diccionarios con los
            indicadores esperados, uno por catálogo pasado, y el segundo
            un diccionario con indicadores a nivel global,
            datos sobre la lista entera en general.
    """
    central_catalog = central_catalog or CENTRAL_CATALOG
    assert isinstance(catalogs, string_types + (dict, list))
    # Si se pasa un único catálogo, genero una lista que lo contenga
    if isinstance(catalogs, string_types + (dict,)):
        catalogs = [catalogs]

    # Leo todos los catálogos
    catalogs = [readers.read_catalog(catalog) for catalog in catalogs]

    indicators_list = []
    # Cuenta la cantidad de campos usados/recomendados a nivel global
    fields = {}
    for catalog in catalogs:
        catalog = readers.read_catalog(catalog)

        fields_count, result = _generate_indicators(
            catalog, validator=validator)
        if central_catalog:
            result.update(_federation_indicators(catalog,
                                                 central_catalog))

        indicators_list.append(result)
        # Sumo a la cuenta total de campos usados/totales
        fields = helpers.add_dicts(fields_count, fields)

    # Indicadores de la red entera
    network_indicators = {
        'catalogos_cant': len(catalogs)
    }

    # Sumo los indicadores individuales al total
    indicators_total = indicators_list[0].copy()
    for i in range(1, len(indicators_list)):
        indicators_total = helpers.add_dicts(indicators_total,
                                             indicators_list[i])
    network_indicators.update(indicators_total)
    # Genero los indicadores de la red entera,
    _network_indicator_percentages(fields, network_indicators)

    return indicators_list, network_indicators


def _generate_indicators(catalog, validator=None):
    """Genera los indicadores de un catálogo individual.

    Args:
        catalog (dict): diccionario de un data.json parseado

    Returns:
        dict: diccionario con los indicadores del catálogo provisto
    """
    result = {}
    # Obtengo summary para los indicadores del estado de los metadatos
    result.update(_generate_status_indicators(catalog, validator=validator))
    # Genero los indicadores relacionados con fechas, y los agrego
    result.update(_generate_date_indicators(catalog))
    # Agrego la cuenta de los formatos de las distribuciones
    count = _count_distribution_formats(catalog)
    result.update({
        'distribuciones_formatos_cant': count
    })
    # Agrego porcentaje de campos recomendados/optativos usados
    fields_count = _count_required_and_optional_fields(catalog)
    recomendados_pct = 100 * float(fields_count['recomendado']) / \
        fields_count['total_recomendado']
    optativos_pct = 100 * float(fields_count['optativo']) / \
        fields_count['total_optativo']
    result.update({
        'campos_recomendados_pct': round(recomendados_pct, 2),
        'campos_optativos_pct': round(optativos_pct, 2)
    })
    return fields_count, result


def _federation_indicators(catalog, central_catalog):
    """Cuenta la cantidad de datasets incluídos tanto en la lista
    'catalogs' como en el catálogo central, y genera indicadores a partir
    de esa información.

    Args:
        catalog (dict): catálogo ya parseado
        central_catalog (str o dict): ruta a catálogo central, o un dict
            con el catálogo ya parseado
    """
    central_catalog = readers.read_catalog(central_catalog)
    federados = 0  # En ambos catálogos
    no_federados = 0
    datasets_federados_eliminados_cant = 0
    datasets_federados = []
    datasets_no_federados = []
    datasets_federados_eliminados = []

    # busca c/dataset del catálogo específico a ver si está en el central
    for dataset in catalog.get('dataset', []):
        found = False
        for central_dataset in central_catalog.get('dataset', []):
            if datasets_equal(dataset, central_dataset):
                found = True
                federados += 1
                datasets_federados.append((dataset.get('title'),
                                           dataset.get('landingPage')))
                break
        if not found:
            no_federados += 1
            datasets_no_federados.append((dataset.get('title'),
                                          dataset.get('landingPage')))

    # busca c/dataset del central cuyo publisher podría pertenecer al
    # catálogo específico, a ver si está en el catálogo específico
    # si no está, probablemente signifique que fue eliminado
    filtered_central = _filter_by_likely_publisher(
        central_catalog.get('dataset', []),
        catalog.get('dataset', [])
    )
    for central_dataset in filtered_central:
        found = False
        for dataset in catalog.get('dataset', []):
            if datasets_equal(dataset, central_dataset):
                found = True
                break
        if not found:
            datasets_federados_eliminados_cant += 1
            datasets_federados_eliminados.append(
                (central_dataset.get('title'),
                 central_dataset.get('landingPage'))
            )

    if federados or no_federados:  # Evita división por 0
        federados_pct = 100 * float(federados) / (federados + no_federados)
    else:
        federados_pct = 0

    result = {
        'datasets_federados_cant': federados,
        'datasets_no_federados_cant': no_federados,
        'datasets_federados_eliminados_cant': datasets_federados_eliminados_cant,
        'datasets_federados_eliminados': datasets_federados_eliminados,
        'datasets_no_federados': datasets_no_federados,
        'datasets_federados': datasets_federados,
        'datasets_federados_pct': round(federados_pct, 2)
    }
    return result


def _network_indicator_percentages(fields, network_indicators):
    """Encapsula el cálculo de indicadores de porcentaje (de errores,
    de campos recomendados/optativos utilizados, de datasets actualizados)
    sobre la red de nodos entera.

    Args:
        fields (dict): Diccionario con claves 'recomendado', 'optativo',
            'total_recomendado', 'total_optativo', cada uno con valores
            que representan la cantidad de c/u en la red de nodos entera.

        network_indicators (dict): Diccionario de la red de nodos, con
            las cantidades de datasets_meta_ok y datasets_(des)actualizados
            calculados previamente. Se modificará este argumento con los
            nuevos indicadores.
    """

    # Los porcentuales no se pueden sumar, tienen que ser recalculados

    # % de datasets cuya metadata está ok
    meta_ok = network_indicators['datasets_meta_ok_cant']
    meta_error = network_indicators['datasets_meta_error_cant']
    total_pct = 0.0
    if meta_ok or meta_error:  # Evita división por cero
        total_pct = 100 * float(meta_ok) / (meta_error + meta_ok)
    network_indicators['datasets_meta_ok_pct'] = round(total_pct, 2)

    # % de campos recomendados y optativos utilizados en todo el catálogo
    if fields:  # 'fields' puede estar vacío si ningún campo es válido
        rec_pct = 100 * float(fields['recomendado']) / \
            fields['total_recomendado']

        opt_pct = 100 * float(fields['optativo']) / \
            fields['total_optativo']

        network_indicators.update({
            'campos_recomendados_pct': round(rec_pct, 2),
            'campos_optativos_pct': round(opt_pct, 2)
        })

    # % de datasets actualizados
    act = network_indicators['datasets_actualizados_cant']
    desact = network_indicators['datasets_desactualizados_cant']
    updated_pct = 0
    if act or desact:  # Evita división por cero
        updated_pct = 100 * act / float(act + desact)
    network_indicators['datasets_actualizados_pct'] = round(updated_pct, 2)

    # % de datasets federados
    federados = network_indicators.get('datasets_federados_cant')
    no_federados = network_indicators.get('datasets_no_federados_cant')

    if federados or no_federados:
        federados_pct = 100 * float(federados) / (federados + no_federados)
        network_indicators['datasets_federados_pct'] = \
            round(federados_pct, 2)


def _generate_status_indicators(catalog, validator=None):
    """Genera indicadores básicos sobre el estado de un catálogo

    Args:
        catalog (dict): diccionario de un data.json parseado

    Returns:
        dict: indicadores básicos sobre el catálogo, tal como la cantidad
        de datasets, distribuciones y número de errores
    """
    summary = generate_datasets_summary(catalog, validator=validator)
    cant_ok = 0
    cant_error = 0
    cant_distribuciones = 0
    datasets_total = len(summary)
    for dataset in summary:
        cant_distribuciones += dataset['cant_distribuciones']

        if dataset['estado_metadatos'] == "OK":
            cant_ok += 1
        else:  # == "ERROR"
            cant_error += 1

    datasets_ok_pct = 0
    if datasets_total:
        datasets_ok_pct = round(100 * float(cant_ok) / datasets_total, 2)
    result = {
        'datasets_cant': datasets_total,
        'distribuciones_cant': cant_distribuciones,
        'datasets_meta_ok_cant': cant_ok,
        'datasets_meta_error_cant': cant_error,
        'datasets_meta_ok_pct': datasets_ok_pct
    }
    return result


def _generate_date_indicators(catalog, tolerance=0.2):
    """Genera indicadores relacionados a las fechas de publicación
    y actualización del catálogo pasado por parámetro. La evaluación de si
    un catálogo se encuentra actualizado o no tiene un porcentaje de
    tolerancia hasta que se lo considere como tal, dado por el parámetro
    tolerance.

    Args:
        catalog (dict o str): path de un catálogo en formatos aceptados,
            o un diccionario de python

        tolerance (float): porcentaje de tolerancia hasta que se considere
            un catálogo como desactualizado, por ejemplo un catálogo con
            período de actualización de 10 días se lo considera como
            desactualizado a partir de los 12 con una tolerancia del 20%.
            También acepta valores negativos.

    Returns:
        dict: diccionario con indicadores
    """
    result = {}

    dias_ultima_actualizacion = _days_from_last_update(
        catalog, "modified")
    if not dias_ultima_actualizacion:
        dias_ultima_actualizacion = _days_from_last_update(
            catalog, "issued")

    result['catalogo_ultima_actualizacion_dias'] = \
        dias_ultima_actualizacion

    actualizados = 0
    desactualizados = 0
    periodicity_amount = {}

    for dataset in catalog.get('dataset', []):
        # Parseo la fecha de publicación, y la frecuencia de actualización
        periodicity = dataset.get('accrualPeriodicity')
        if not periodicity:
            continue
        # Si la periodicity es eventual, se considera como actualizado
        if periodicity == 'eventual':
            actualizados += 1
            prev_periodicity = periodicity_amount.get(periodicity, 0)
            periodicity_amount[periodicity] = prev_periodicity + 1
            continue

        # dataset sin fecha de última actualización es desactualizado
        if "modified" not in dataset:
            desactualizados += 1
        else:
            # Calculo el período de días que puede pasar sin actualizarse
            # Se parsea el período especificado por accrualPeriodicity,
            # cumple con el estándar ISO 8601 para tiempos con repetición
            date = helpers.parse_date_string(dataset['modified'])
            days_diff = float((datetime.now() - date).days)
            interval = helpers.parse_repeating_time_interval(
                periodicity) * \
                (1 + tolerance)

            if days_diff < interval:
                actualizados += 1
            else:
                desactualizados += 1

        prev_periodicity = periodicity_amount.get(periodicity, 0)
        periodicity_amount[periodicity] = prev_periodicity + 1

    datasets_total = len(catalog.get('dataset', []))
    actualizados_pct = 0
    if datasets_total:
        actualizados_pct = float(actualizados) / datasets_total
    result.update({
        'datasets_desactualizados_cant': desactualizados,
        'datasets_actualizados_cant': actualizados,
        'datasets_actualizados_pct': 100 * round(actualizados_pct, 2),
        'datasets_frecuencia_cant': periodicity_amount
    })
    return result


def _count_distribution_formats(catalog):
    """Cuenta los formatos especificados por el campo 'format' de cada
    distribución de un catálogo o de un dataset.

    Args:
        catalog (str o dict): path a un catálogo, o un dict de python que

    Returns:
        dict: diccionario con los formatos de las distribuciones
        encontradas como claves, con la cantidad de ellos en sus valores.
    """

    # Leo catálogo
    catalog = readers.read_catalog(catalog)
    catalog_formats = {}

    for dataset in catalog.get('dataset', []):
        dataset_formats = _count_distribution_formats_dataset(dataset)

        for distribution_format in dataset_formats:
            count_catalog = catalog_formats.get(distribution_format, 0)
            count_dataset = dataset_formats.get(distribution_format, 0)
            catalog_formats[
                distribution_format] = count_catalog + count_dataset

    return catalog_formats


def _count_distribution_formats_dataset(dataset):
    formats = {}
    for distribution in dataset['distribution']:
        # 'format' es recomendado, no obligatorio. Puede no estar.
        distribution_format = distribution.get('format', None)

        if distribution_format:
            # Si no está en el diccionario, devuelvo 0
            count = formats.get(distribution_format, 0)

            formats[distribution_format] = count + 1

    return formats


def _days_from_last_update(catalog, date_field="modified"):
    """Calcula días desde la última actualización del catálogo.

    Args:
        catalog (dict): Un catálogo.
        date_field (str): Campo de metadatos a utilizar para considerar
            los días desde la última actualización del catálogo.

    Returns:
        int or None: Cantidad de días desde la última actualización del
            catálogo o None, si no pudo ser calculada.
    """

    # el "date_field" se busca primero a nivel catálogo, luego a nivel
    # de cada dataset, y nos quedamos con el que sea más reciente
    date_modified = catalog.get(date_field, None)
    dias_ultima_actualizacion = None
    # "date_field" a nivel de catálogo puede no ser obligatorio,
    # si no está pasamos
    if isinstance(date_modified, string_types):
        date = helpers.parse_date_string(date_modified)
        dias_ultima_actualizacion = (datetime.now() - date).days

    for dataset in catalog.get('dataset', []):
        date = helpers.parse_date_string(dataset.get(date_field, ""))
        days_diff = float((datetime.now() - date).days) if date else None

        # Actualizo el indicador de días de actualización si corresponde
        if not dias_ultima_actualizacion or \
                (days_diff and days_diff < dias_ultima_actualizacion):
            dias_ultima_actualizacion = days_diff

    if dias_ultima_actualizacion:
        return int(dias_ultima_actualizacion)
    else:
        return None


def _count_required_and_optional_fields(catalog):
    """Cuenta los campos obligatorios/recomendados/requeridos usados en
    'catalog', junto con la cantidad máxima de dichos campos.

    Args:
        catalog (str o dict): path a un catálogo, o un dict de python que
            contenga a un catálogo ya leído

    Returns:
        dict: diccionario con las claves 'recomendado', 'optativo',
            'requerido', 'recomendado_total', 'optativo_total',
            'requerido_total', con la cantidad como valores.
    """

    catalog = readers.read_catalog(catalog)

    # Archivo .json con el uso de cada campo. Lo cargamos a un dict
    catalog_fields_path = os.path.join(CATALOG_FIELDS_PATH,
                                       'fields.json')
    with open(catalog_fields_path) as f:
        catalog_fields = json.load(f)

    # Armado recursivo del resultado
    return _count_fields_recursive(catalog, catalog_fields)


def _count_fields_recursive(dataset, fields):
    """Cuenta la información de campos optativos/recomendados/requeridos
    desde 'fields', y cuenta la ocurrencia de los mismos en 'dataset'.

    Args:
        dataset (dict): diccionario con claves a ser verificadas.
        fields (dict): diccionario con los campos a verificar en dataset
            como claves, y 'optativo', 'recomendado', o 'requerido' como
            valores. Puede tener objetios anidados pero no arrays.

    Returns:
        dict: diccionario con las claves 'recomendado', 'optativo',
            'requerido', 'recomendado_total', 'optativo_total',
            'requerido_total', con la cantidad como valores.
    """

    key_count = {
        'recomendado': 0,
        'optativo': 0,
        'requerido': 0,
        'total_optativo': 0,
        'total_recomendado': 0,
        'total_requerido': 0
    }

    for k, v in fields.items():
        # Si la clave es un diccionario se implementa recursivamente el
        # mismo algoritmo
        if isinstance(v, dict):
            # dataset[k] puede ser o un dict o una lista, ej 'dataset' es
            # list, 'publisher' no. Si no es lista, lo metemos en una.
            # Si no es ninguno de los dos, dataset[k] es inválido
            # y se pasa un diccionario vacío para poder comparar
            elements = dataset.get(k)
            if not isinstance(elements, (list, dict)):
                elements = [{}]

            if isinstance(elements, dict):
                elements = [dataset[k].copy()]
            for element in elements:
                # Llamada recursiva y suma del resultado al nuestro
                result = _count_fields_recursive(element, v)
                for key in result:
                    key_count[key] += result[key]
        # Es un elemento normal (no iterable), se verifica si está en
        # dataset o no. Se suma 1 siempre al total de su tipo
        else:
            # total_requerido, total_recomendado, o total_optativo
            key_count['total_' + v] += 1

            if k in dataset:
                key_count[v] += 1

    return key_count


def datasets_equal(dataset, other, fields_dataset=None,
                   fields_distribution=None, return_diff=False):
    """Función de igualdad de dos datasets: se consideran iguales si
    los valores de los campos 'title', 'publisher.name',
    'accrualPeriodicity' e 'issued' son iguales en ambos.

    Args:
        dataset (dict): un dataset, generado por la lectura de un catálogo
        other (dict): idem anterior

    Returns:
        bool: True si son iguales, False en caso contrario
    """
    dataset_is_equal = True
    dataset_diff = []

    # Campos a comparar. Si es un campo anidado escribirlo como lista
    if not fields_dataset:
        fields_dataset = [
            'title',
            ['publisher', 'name']
        ]

    for field_dataset in fields_dataset:
        if isinstance(field_dataset, list):
            value = helpers.traverse_dict(dataset, field_dataset)
            other_value = helpers.traverse_dict(other, field_dataset)
        else:
            value = dataset.get(field_dataset)
            other_value = other.get(field_dataset)

        if value != other_value:
            dataset_diff.append({
                "error_location": field_dataset,
                "dataset_value": value,
                "other_value": other_value
            })
            dataset_is_equal = False

    if fields_distribution:
        dataset_distributions = dataset.get("distribution")
        other_distributions = other.get("distribution")

        if len(dataset_distributions) != len(other_distributions):
            print("{} distribuciones en origen y {} en destino".format(
                len(dataset_distributions), len(other_distributions)))
            dataset_is_equal = False

        distributions_equal = True
        for dataset_distribution, other_distribution in zip(
                dataset_distributions, other_distributions):

            for field_distribution in fields_distribution:
                if isinstance(field_distribution, list):
                    value = helpers.traverse_dict(
                        dataset_distribution, field_distribution)
                    other_value = helpers.traverse_dict(
                        other_distribution, field_distribution)
                else:
                    value = dataset_distribution.get(field_distribution)
                    other_value = other_distribution.get(field_distribution)

                if value != other_value:
                    dataset_diff.append({
                        "error_location": "{} ({})".format(
                            field_distribution,
                            dataset_distribution.get("title")
                        ),
                        "dataset_value": value,
                        "other_value": other_value
                    })
                    distributions_equal = False

        if not distributions_equal:
            dataset_is_equal = False

    if return_diff:
        return dataset_diff
    else:
        return dataset_is_equal


def _filter_by_likely_publisher(central_datasets, catalog_datasets):
    publisher_names = [
        catalog_dataset["publisher"]["name"]
        for catalog_dataset in catalog_datasets
        if "name" in catalog_dataset["publisher"]
    ]

    filtered_central_datasets = []
    for central_dataset in central_datasets:
        if "name" in central_dataset["publisher"] and \
                central_dataset["publisher"]["name"] in publisher_names:
            filtered_central_datasets.append(central_dataset)

    return filtered_central_datasets
