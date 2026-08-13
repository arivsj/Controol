"""Testes do parser de diff unificado (`git diff --unified=N`)."""
from controol.report.diffing import parse_unified_diff


def test_adicao_simples():
    diff = """diff --git a/a.py b/a.py
index 111..222 100644
--- a/a.py
+++ b/a.py
@@ -1,2 +1,3 @@
 x = 1
+y = 2
 z = 3
"""
    lines = parse_unified_diff(diff)
    kinds = [ln.kind for ln in lines]
    assert kinds == ["hunk", " ", "+", " "]
    added = [ln.text for ln in lines if ln.kind == "+"]
    assert added == ["y = 2"]


def test_remocao_e_linhas_contando():
    diff = """@@ -3,3 +3,2 @@
 a
-b
-c
 d
"""
    lines = parse_unified_diff(diff)
    kinds = [ln.kind for ln in lines]
    assert kinds == ["hunk", " ", "-", "-", " "]
    removed = [ln.text for ln in lines if ln.kind == "-"]
    assert removed == ["b", "c"]
    # contadores de linha
    ctx = [ln for ln in lines if ln.kind == " "]
    assert ctx[0].old_no == 3 and ctx[0].new_no == 3
    # duas linhas removidas: a linha "d" fica em new 4 (3+2-2+1), old 6 (3+2+1)
    assert ctx[-1].old_no == 6 and ctx[-1].new_no == 4


def test_metadados_sao_ignorados():
    diff = """diff --git a/x.py b/x.py
new file mode 100644
index 000..123
--- /dev/null
+++ b/x.py
@@ -0,0 +1,2 @@
+linha um
+linha dois
"""
    lines = parse_unified_diff(diff)
    assert all(ln.kind != "hunk" or ln.text.startswith("@@") for ln in lines)
    added = [ln.text for ln in lines if ln.kind == "+"]
    assert added == ["linha um", "linha dois"]


def test_vazio():
    assert parse_unified_diff("") == []


def test_sem_hunk_retorna_vazio():
    # sem cabeçalho @@ não há contexto para contar linhas
    assert parse_unified_diff("diff --git a/x b/x\n--- a/x\n+++ b/x\n") == []
