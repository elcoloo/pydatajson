#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests del modulo pydatajson."""

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import with_statement

import os.path
import unittest
import nose
import openpyxl as pyxl
from .context import pydatajson


class HelpersTestCase(unittest.TestCase):

    SAMPLES_DIR = os.path.join("tests", "samples")
    RESULTS_DIR = os.path.join("tests", "results")

    def test_sheet_to_table(self):
        """sheet_to_table convierte hojas de un libro en listas de
        diccionarios"""
        workbook_path = os.path.join(self.SAMPLES_DIR,
                                     "prueba_sheet_to_table.xlsx")
        workbook = pyxl.load_workbook(workbook_path)

        expected_tables = {
            "Imperio": [
                {"Nombre": "Darth Vader", "Jedi": "Poderoso"},
                {"Nombre": "Kylo Ren", "Jedi": "Mas o Menos"}
            ],
            "Rebeldes": [
                {"Nombre": "Luke", "Edad": 56},
                {"Nombre": "Han", "Edad": 122},
                {"Nombre": "Yoda", "Edad": 0}
            ]
        }

        for sheetname in ["Imperio", "Rebeldes"]:
            actual_table = pydatajson.helpers.sheet_to_table(
                workbook[sheetname])
            expected_table = expected_tables[sheetname]
            self.assertEqual(actual_table, expected_table)

    def test_string_to_list_default_separator(self):
        """string_to_list convierte una str separada por "," en una
        lista"""
        strings = [
            " pan , vino,gorriones ,23",
            "economía,\t\tturismo,salud\n",
            """uno,,
            dos,
            tres"""
        ]
        lists = [
            ["pan", "vino", "gorriones", "23"],
            ["economía", "turismo", "salud"],
            ["uno", "", "dos", "tres"]
        ]
        for (string, expected_list) in zip(strings, lists):
            actual_list = pydatajson.helpers.string_to_list(string)
            self.assertListEqual(actual_list, expected_list)

    def test_string_to_list_alternative_separator(self):
        """ string_to_list convierte una str separada por un separador
        alternativo (";") en una lista."""
        actual_list = pydatajson.helpers.string_to_list(
            string="un;;separador;;nuevo", sep=";;")
        expected_list = ["un", "separador", "nuevo"]

        self.assertListEqual(actual_list, expected_list)

    SAMPLE_DICT = pydatajson.readers.read_catalog(
        os.path.join(SAMPLES_DIR, "full_data.json"))

    def test_traverse_dict_correct_keys(self):
        """traverse_dict devuelve un valor si toda clave buscada existe."""
        expected = "onc@modernizacion.gob.ar"
        actual = pydatajson.helpers.traverse_dict(
            self.SAMPLE_DICT, ["dataset", 0, "publisher", "mbox"])

        self.assertEqual(actual, expected)

    def test_traverse_dict_index_out_of_range(self):
        """traverse_dict devuelve el valor por omisión si un índice está fuera
        del rango de su lista."""
        # Usando el valor de retorno por omisión, 'None'
        actual = pydatajson.helpers.traverse_dict(
            self.SAMPLE_DICT, ["dataset", 12, "publisher", "mbox"])
        self.assertIsNone(actual)

        # Usando un valor por omisión distinto.
        expected = "MISSING"
        actual = pydatajson.helpers.traverse_dict(
            self.SAMPLE_DICT, ["dataset", 12, "publisher", "mbox"], expected)

        self.assertEqual(actual, expected)

    def test_traverse_dict_missing_key(self):
        """traverse_dict devuelve el valor por omisión si una clave no existe
        en un diccionario."""
        actual = pydatajson.helpers.traverse_dict(
            self.SAMPLE_DICT, ["dataset", 12, "owner", "mbox"])
        self.assertIsNone(actual)

    def test_traverse_dict_string_index_for_list(self):
        """traverse_dict devuelve el valor por omisión si se pasa un string
        como índice de una lista."""
        actual = pydatajson.helpers.traverse_dict(
            self.SAMPLE_DICT, ["dataset", "0", "owner", "mbox"])
        self.assertIsNone(actual)

    @nose.tools.raises(AssertionError)
    def test_is_list_of_matching_dicts_with_not_list(self):
        """is_list_of_matching_dicts levanta error si el input no es una
        lista."""
        pydatajson.helpers.is_list_of_matching_dicts({})

    @nose.tools.raises(AssertionError)
    def test_is_list_of_matching_dicts_with_list_of_not_dicts(self):
        """is_list_of_matching_dicts levanta error si el input es una
        lista pero alguno de sus elementos no es un diccionario."""
        pydatajson.helpers.is_list_of_matching_dicts([{}, (), {}, {}])

    def test_is_list_of_matching_dicts_with_matched_dicts(self):
        """is_list_of_matching_dicts devuelve True si todos los elementos del
        input tienen las mismas claves."""
        result = pydatajson.helpers.is_list_of_matching_dicts([
            {"a": 1, "b": 2},
            {"a": 1, "b": 2},
            {"a": 1, "b": 2}
        ])

        self.assertTrue(result)

    def test_is_list_of_matching_dicts_with_mismatched_dicts(self):
        """is_list_of_matching_dicts devuelve False si no todos los elementos
        del input tienen las mismas claves."""
        result = pydatajson.helpers.is_list_of_matching_dicts([
            {"a": 1, "b": 2},
            {"a": 1},
            {"a": 1, "b": 2}
        ])

        self.assertFalse(result)


if __name__ == '__main__':
    nose.run(defaultTest=__name__)