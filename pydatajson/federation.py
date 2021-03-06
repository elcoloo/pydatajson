#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extensión de pydatajson para la federación de metadatos de datasets a través de la API de CKAN.
"""
from __future__ import print_function
from ckanapi import RemoteCKAN
from ckanapi.errors import NotFound
from .ckan_utils import map_dataset_to_package, map_theme_to_group
from .search import get_datasets


def push_dataset_to_ckan(catalog, owner_org, dataset_origin_identifier, portal_url, apikey,
                         catalog_id=None, demote_superThemes=True, demote_themes=True):
    """Escribe la metadata de un dataset en el portal pasado por parámetro.

        Args:
            catalog (DataJson): El catálogo de origen que contiene el dataset.
            owner_org (str): La organización a la cual pertence el dataset.
            dataset_origin_identifier (str): El id del dataset que se va a federar.
            portal_url (str): La URL del portal CKAN de destino.
            apikey (str): La apikey de un usuario con los permisos que le permitan crear o actualizar el dataset.
            catalog_id (str): El prefijo con el que va a preceder el id del dataset en catálogo destino.
            demote_superThemes(bool): Si está en true, los ids de los super themes del dataset, se propagan como grupo.
            demote_themes(bool): Si está en true, los labels de los themes del dataset, pasan a ser tags. Sino,
            se pasan como grupo.
        Returns:
            str: El id del dataset en el catálogo de destino.
    """
    dataset = catalog.get_dataset(dataset_origin_identifier)
    ckan_portal = RemoteCKAN(portal_url, apikey=apikey)

    package = map_dataset_to_package(catalog, dataset, owner_org, catalog_id,
                                     demote_superThemes, demote_themes)

    # Get license id
    if dataset.get('license'):
        license_list = ckan_portal.call_action('license_list')
        try:
            ckan_license = next(license_item for license_item in license_list if
                                license_item['title'] == dataset['license'] or
                                license_item['url'] == dataset['license'])
            package['license_id'] = ckan_license['id']
        except StopIteration:
            package['license_id'] = 'notspecified'
    else:
        package['license_id'] = 'notspecified'

    try:
        pushed_package = ckan_portal.call_action(
            'package_update', data_dict=package)
    except NotFound:
        pushed_package = ckan_portal.call_action(
            'package_create', data_dict=package)

    ckan_portal.close()
    return pushed_package['id']


def remove_dataset_from_ckan(identifier, portal_url, apikey):
    ckan_portal = RemoteCKAN(portal_url, apikey=apikey)
    ckan_portal.call_action('dataset_purge', data_dict={'id': identifier})


def remove_datasets_from_ckan(portal_url, apikey, filter_in=None, filter_out=None,
                              only_time_series=False, organization=None):
    """Borra un dataset en el portal pasado por parámetro.

            Args:
                portal_url (str): La URL del portal CKAN de destino.
                apikey (str): La apikey de un usuario con los permisos que le permitan borrar el dataset.
                filter_in(dict): Diccionario de filtrado positivo, similar al de search.get_datasets.
                filter_out(dict): Diccionario de filtrado negativo, similar al de search.get_datasets.
                only_time_series(bool): Filtrar solo los datasets que tengan recursos con series de tiempo.
                organization(str): Filtrar solo los datasets que pertenezcan a cierta organizacion.
            Returns:
                None
    """
    ckan_portal = RemoteCKAN(portal_url, apikey=apikey)
    identifiers = []
    datajson_filters = filter_in or filter_out or only_time_series
    if datajson_filters:
        identifiers += get_datasets(portal_url + '/data.json', filter_in=filter_in, filter_out=filter_out,
                                    only_time_series=only_time_series, meta_field='identifier')
    if organization:
        query = 'organization:"' + organization + '"'
        search_result = ckan_portal.call_action('package_search', data_dict={
                                                'q': query, 'rows': 500, 'start': 0})
        org_identifiers = [dataset['id']
                           for dataset in search_result['results']]
        start = 500
        while search_result['count'] > start:
            search_result = ckan_portal.call_action('package_search',
                                                    data_dict={'q': query, 'rows': 500, 'start': start})
            org_identifiers += [dataset['id']
                                for dataset in search_result['results']]
            start += 500

        if datajson_filters:
            identifiers = set(identifiers).intersection(set(org_identifiers))
        else:
            identifiers = org_identifiers

    for identifier in identifiers:
        ckan_portal.call_action('dataset_purge', data_dict={'id': identifier})


def push_theme_to_ckan(catalog, portal_url, apikey, identifier=None, label=None):
    """Escribe la metadata de un theme en el portal pasado por parámetro.

            Args:
                catalog (DataJson): El catálogo de origen que contiene el theme.
                portal_url (str): La URL del portal CKAN de destino.
                apikey (str): La apikey de un usuario con los permisos que le permitan crear o actualizar el dataset.
                identifier (str): El identificador para buscar el theme en la taxonomia.
                label (str): El label para buscar el theme en la taxonomia.
            Returns:
                str: El name del theme en el catálogo de destino.
        """
    ckan_portal = RemoteCKAN(portal_url, apikey=apikey)
    theme = catalog.get_theme(identifier=identifier, label=label)
    group = map_theme_to_group(theme)
    pushed_group = ckan_portal.call_action('group_create', data_dict=group)
    return pushed_group['name']


def restore_dataset_to_ckan(catalog, owner_org, dataset_origin_identifier, portal_url, apikey):

    return push_dataset_to_ckan(catalog, owner_org, dataset_origin_identifier,
                                portal_url, apikey, None, False, False)


def harvest_dataset_to_ckan(catalog, owner_org, dataset_origin_identifier, portal_url, apikey, catalog_id):

    return push_dataset_to_ckan(catalog, owner_org, dataset_origin_identifier,
                                portal_url, apikey, catalog_id=catalog_id)

