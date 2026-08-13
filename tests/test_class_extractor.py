"""Testes do extrator de classes sem IA (ast Python + scanner genérico)."""
from controol.report.class_extractor import extract_units, language_of


def test_language_of():
    assert language_of("app.py") == "python"
    assert language_of("index.js") in ("javascript", "js")
    assert language_of("App.tsx") in ("typescript", "tsx")
    assert language_of("main.go") == "go"
    assert language_of("arquivo.txt") in ("", "txt")


def test_python_class_com_metodos():
    src = '''"""docstring"""
import os

class Conta:
    def __init__(self, saldo):
        self.saldo = saldo

    def depositar(self, valor):
        self.saldo += valor
        return self.saldo

class Cliente:
    pass

def helper(a, b):
    return a + b
'''
    units = extract_units(src, "python", "banco.py")
    assert len(units) == 3
    conta, cliente, helper = units
    assert (conta.kind, conta.name, conta.start_line, conta.end_line) == ("class", "Conta", 4, 10)
    assert "def depositar" in conta.code
    assert conta.code.lstrip().startswith("class Conta")
    assert cliente.code.strip() == "class Cliente:\n    pass"
    assert helper.kind == "function" and helper.name == "helper"
    # código completo deve estar em unidades distintas
    assert "depositar" not in cliente.code


def test_python_decorator_e_docstring_preservados():
    src = """@dataclass
class Item:
    \"\"\"um item.\"\"\"
    nome: str
    preco: float = 0.0
"""
    units = extract_units(src, "python", "item.py")
    assert len(units) == 1
    assert units[0].name == "Item"
    assert "@dataclass" in units[0].code
    assert "um item." in units[0].code


def test_javascript_function_e_class():
    src = """export function soma(a, b) {
  return a + b;
}

class Carro {
  constructor(marca) { this.marca = marca; }
  buzinar() { return "bi!"; }
}
"""
    units = extract_units(src, "javascript", "carro.js")
    kinds = [(u.kind, u.name) for u in units]
    assert ("function", "soma") in kinds
    assert ("class", "Carro") in kinds
    carro = next(u for u in units if u.name == "Carro")
    assert "buzinar" in carro.code and carro.code.rstrip().endswith("}")
    soma = next(u for u in units if u.name == "soma")
    assert "return a + b" in soma.code


def test_generic_scanner_go():
    src = """package main

type Conta struct {
    Saldo int
}

func depositar(c *Conta, v int) {
    c.Saldo += v
}
"""
    units = extract_units(src, "go", "main.go")
    kinds = [(u.kind, u.name) for u in units]
    assert ("struct", "Conta") in kinds
    # def/fn/func/function são normalizados para "function"
    assert ("function", "depositar") in kinds


def test_sem_units_retorna_vazio():
    assert extract_units("apenas texto sem código", "python", "x.txt") == []
    assert extract_units("", "python", "vazio.py") == []
